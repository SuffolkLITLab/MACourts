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
        ],
    )
    connection.executemany(
        "INSERT INTO addresses VALUES (?, ?, ?, ?)",
        [
            (1, "100", 2118, 1),
            # Same street+number, two ZIPs, same division: still a clean match.
            (1, "200", 2118, 1),
            (1, "200", 2119, 1),
            # The duplicate-name case: same number on both streets, different
            # ZIPs and different divisions.
            (2, "50", 2120, 1),
            (3, "50", 2121, 2),
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
    resolution = index.resolve("100 Main St", zip_code="09999")
    assert resolution.match_kind == ZIP_MISMATCH
    assert resolution.court_name is None


def test_resolve_unparseable_address_is_not_found(index: BostonAddressIndex) -> None:
    resolution = index.resolve("Main St")
    assert resolution.match_kind == NOT_FOUND
