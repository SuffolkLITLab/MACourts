"""Unit tests for the Boston street-address parser and SQLite resolver.

Parser tests are purely synthetic (no database). Resolver tests build a tiny
temporary SQLite database with the same schema
``scripts/build_bmc_address_index.py`` writes, covering the resolution rules
from the design doc: canonical/variant spelling, duplicate street names,
ZIP disambiguation, ambiguity, and ZIP conflicts.
"""

from __future__ import annotations

import sqlite3

import pytest

from macourts.boston_address import (
    AMBIGUOUS,
    NOT_FOUND,
    SUCCESS,
    ZIP_MISMATCH,
    BostonAddressIndex,
    ParsedStreetAddress,
    parse_street_address,
)

# --- parser ------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("123 Main St", ParsedStreetAddress("123", "MAIN ST")),
        ("123 Main Street", ParsedStreetAddress("123", "MAIN STREET")),
        ("123 Main St.", ParsedStreetAddress("123", "MAIN ST")),
        ("123 Main St, Apt 4", ParsedStreetAddress("123", "MAIN ST")),
        ("123 Main St #4", ParsedStreetAddress("123", "MAIN ST")),
        ("12A Main St", ParsedStreetAddress("12A", "MAIN ST")),
        ("12-14 Main St", ParsedStreetAddress("12-14", "MAIN ST")),
        ("6 1/2 Main St", ParsedStreetAddress("6 1/2", "MAIN ST")),
        ("  700   Boylston   St  ", ParsedStreetAddress("700", "BOYLSTON ST")),
        ("123 N Beacon St", ParsedStreetAddress("123", "N BEACON ST")),
        ("123 Charles St S", ParsedStreetAddress("123", "CHARLES ST S")),
    ],
)
def test_parse_street_address(value: str, expected: ParsedStreetAddress) -> None:
    assert parse_street_address(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, "Main St", "Boston, MA"],
)
def test_parse_street_address_rejects_unparseable_input(value) -> None:
    assert parse_street_address(value) is None


# --- resolver ------------------------------------------------------------

SCHEMA = """
CREATE TABLE metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE divisions (
    id         INTEGER PRIMARY KEY,
    court_name TEXT NOT NULL UNIQUE
);

CREATE TABLE street_names (
    name_key  TEXT NOT NULL,
    street_id INTEGER NOT NULL,
    kind      INTEGER NOT NULL,
    PRIMARY KEY (name_key, street_id)
) WITHOUT ROWID;

CREATE INDEX street_names_by_name ON street_names(name_key);

CREATE TABLE addresses (
    street_id   INTEGER NOT NULL,
    number_key  TEXT NOT NULL,
    zip_code    INTEGER NOT NULL DEFAULT 0,
    division_id INTEGER NOT NULL,
    exact       INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (street_id, number_key, zip_code)
) WITHOUT ROWID;

CREATE INDEX addresses_by_street_number ON addresses(street_id, number_key);
"""

CENTRAL = "Central Division, Boston Municipal Court"
ROXBURY = "Roxbury Division, Boston Municipal Court"


@pytest.fixture()
def index(tmp_path) -> BostonAddressIndex:
    db_path = tmp_path / "test_bmc_addresses.sqlite"
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA)
    connection.executemany(
        "INSERT INTO metadata VALUES (?, ?)",
        [("data_version", "test-fixture")],
    )
    connection.executemany(
        "INSERT INTO divisions VALUES (?, ?)",
        [(1, CENTRAL), (2, ROXBURY)],
    )
    connection.executemany(
        "INSERT INTO street_names VALUES (?, ?, ?)",
        [
            # street_id=1: canonical + suffix variant, single division.
            ("MAIN ST", 1, 0),
            ("MAIN STREET", 1, 2),
            # street_id=2 and street_id=3 share the name_key "OAK AVE" but
            # resolve to different divisions -- the duplicate-street-name case.
            ("OAK AVE", 2, 0),
            ("OAK AVE", 3, 0),
            # street_id=4 exists but has no addresses rows at all.
            ("PINE ST", 4, 0),
            # street_id=9/10: a typo of "NEWBURY ST" ("NEWBERY ST", distance 1)
            # is equally close to "NEWBERN ST" -- only house-number
            # verification (street_id=9 has 279, street_id=10 doesn't) picks
            # NEWBURY out.
            ("NEWBURY ST", 9, 0),
            ("NEWBERN ST", 10, 0),
            # street_id=11/12: both within typo-rescue distance of a
            # deliberately misspelled query, both carrying the queried house
            # number, but in different divisions -- a fuzzy match must not
            # silently pick one.
            ("OAK ST", 11, 0),
            ("OAT ST", 12, 0),
            # street_id=13: a 4-character name a typo must never be rescued
            # against, no matter how close ("D ST" vs a 1-edit "K ST").
            ("D ST", 13, 0),
            ("K ST", 14, 0),
        ],
    )
    connection.executemany(
        "INSERT INTO addresses VALUES (?, ?, ?, ?, ?)",
        [
            (1, "100", 2118, 1, 1),
            # Same street+number, two ZIPs, same division: still a clean match.
            (1, "200", 2118, 1, 1),
            (1, "200", 2119, 1, 1),
            # The duplicate-name case: same number on both streets, different
            # ZIPs and different divisions.
            (2, "50", 2120, 1, 1),
            (3, "50", 2121, 2, 1),
            # A nearest-boundary-fallback-only address (see
            # docs/bmc_address_index.md): resolvable, but not exact.
            (1, "300", 2118, 1, 0),
            # NEWBURY ST has #279; NEWBERN ST does not (only #10).
            (9, "279", 2118, 1, 1),
            (10, "10", 2118, 1, 1),
            # OAK ST and OAT ST both have #77, in different divisions.
            (11, "77", 2118, 1, 1),
            (12, "77", 2119, 2, 1),
            # D ST and K ST both have #5.
            (13, "5", 2118, 1, 1),
            (14, "5", 2118, 1, 1),
        ],
    )
    connection.commit()
    connection.close()
    return BostonAddressIndex.from_path(db_path)


def test_resolve_success_via_canonical_name(index: BostonAddressIndex) -> None:
    resolution = index.resolve("100 Main St")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL
    assert resolution.data_version == "test-fixture"
    assert resolution.exact is True


def test_resolve_success_marks_nearest_boundary_fallback_as_inexact(
    index: BostonAddressIndex,
) -> None:
    resolution = index.resolve("300 Main St")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL
    assert resolution.exact is False


def test_resolve_success_via_generated_variant(index: BostonAddressIndex) -> None:
    resolution = index.resolve("100 Main Street")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL


def test_resolve_success_multiple_rows_same_division(
    index: BostonAddressIndex,
) -> None:
    resolution = index.resolve("200 Main St")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL


def test_resolve_not_found_unknown_street(index: BostonAddressIndex) -> None:
    resolution = index.resolve("100 Elm St")
    assert resolution.match_kind == NOT_FOUND
    assert resolution.court_name is None


def test_resolve_not_found_street_exists_number_absent(
    index: BostonAddressIndex,
) -> None:
    resolution = index.resolve("999 Pine St")
    assert resolution.match_kind == NOT_FOUND


def test_resolve_ambiguous_duplicate_street_name(index: BostonAddressIndex) -> None:
    resolution = index.resolve("50 Oak Ave")
    assert resolution.match_kind == AMBIGUOUS
    assert resolution.court_name is None


def test_resolve_zip_disambiguates_duplicate_street_name(
    index: BostonAddressIndex,
) -> None:
    resolution = index.resolve("50 Oak Ave", zip_code="02120")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL

    resolution = index.resolve("50 Oak Ave", zip_code="02121")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == ROXBURY


def test_resolve_zip_mismatch_is_not_silently_ignored(
    index: BostonAddressIndex,
) -> None:
    # ZIP only matters once the street+number alone is ambiguous (the
    # duplicate-name "Oak Ave" case): an unmatched ZIP there is a real
    # signal, unlike an unmatched ZIP on an otherwise-unambiguous address
    # (see test_resolve_unambiguous_address_ignores_a_mismatched_zip).
    resolution = index.resolve("50 Oak Ave", zip_code="09999")
    assert resolution.match_kind == ZIP_MISMATCH
    assert resolution.court_name is None


def test_resolve_unambiguous_address_ignores_a_mismatched_zip(
    index: BostonAddressIndex,
) -> None:
    # Real-world ZIPs on third-party records often name a neighboring postal
    # ZIP rather than SAM's own; when every candidate row already agrees on
    # one division, that's a stronger signal than an unmatched ZIP.
    resolution = index.resolve("100 Main St", zip_code="09999")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL


def test_resolve_unparseable_address_is_not_found(index: BostonAddressIndex) -> None:
    resolution = index.resolve("Main St")
    assert resolution.match_kind == NOT_FOUND


# --- typo rescue --------------------------------------------------------


def test_resolve_rescues_a_street_name_typo(index: BostonAddressIndex) -> None:
    resolution = index.resolve("100 Msin St")  # substitution, distance 1
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL
    assert resolution.fuzzy_street is True


def test_resolve_house_number_prunes_a_close_but_wrong_street(
    index: BostonAddressIndex,
) -> None:
    # "Newbery" is distance 1 from both "Newbury" (has #279) and "Newbern"
    # (doesn't) -- only checking whether the queried house number actually
    # exists on each candidate street picks Newbury out.
    resolution = index.resolve("279 Newbery St")
    assert resolution.match_kind == SUCCESS
    assert resolution.court_name == CENTRAL
    assert resolution.fuzzy_street is True


def test_resolve_fuzzy_candidates_in_different_divisions_are_ambiguous(
    index: BostonAddressIndex,
) -> None:
    # "Oab St" is distance 1 from both "Oak St" and "Oat St"; both carry
    # #77, but in different divisions, so this must not silently pick one.
    resolution = index.resolve("77 Oab St")
    assert resolution.match_kind == AMBIGUOUS
    assert resolution.court_name is None


def test_resolve_never_fuzzy_matches_a_short_name(index: BostonAddressIndex) -> None:
    # "F St" is distance 1 from "D St", but 4-character names are never
    # fuzzy-matched, regardless of distance (protects names like "K St").
    resolution = index.resolve("5 F St")
    assert resolution.match_kind == NOT_FOUND


def test_resolve_allow_fuzzy_false_disables_typo_rescue(
    index: BostonAddressIndex,
) -> None:
    resolution = index.resolve("100 Msin St", allow_fuzzy=False)
    assert resolution.match_kind == NOT_FOUND


def test_resolve_exact_match_never_reports_fuzzy(index: BostonAddressIndex) -> None:
    resolution = index.resolve("100 Main St")
    assert resolution.match_kind == SUCCESS
    assert resolution.fuzzy_street is False
