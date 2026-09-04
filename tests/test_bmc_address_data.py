"""Integrity checks for the packaged ``bmc_addresses.sqlite`` compiled index.

These exercise the file that actually ships, as opposed to
``test_boston_address.py``'s synthetic fixture database.
"""

from __future__ import annotations

import sqlite3

import pytest

from macourts.boston_address import BostonAddressIndex

# The 8 BMC divisions the catalog and boston_wards.geojson both name.
EXPECTED_DIVISIONS = {
    "Brighton Division, Boston Municipal Court",
    "Central Division, Boston Municipal Court",
    "Charlestown Division, Boston Municipal Court",
    "Dorchester Division, Boston Municipal Court",
    "East Boston Division, Boston Municipal Court",
    "Roxbury Division, Boston Municipal Court",
    "South Boston Division, Boston Municipal Court",
    "West Roxbury Division, Boston Municipal Court",
}

# Stable, public addresses (Boston Public Library branches) unlikely to change
# BMC division, cross-checked against tests/fixtures geocoded coordinates.
STABLE_LOOKUPS = [
    ("700 Boylston St", "02116", "Central Division, Boston Municipal Court"),
    ("690 Adams St", "02122", "Dorchester Division, Boston Municipal Court"),
    ("40 Academy Hill Rd", "02135", "Brighton Division, Boston Municipal Court"),
    ("179 Main St", "02129", "Charlestown Division, Boston Municipal Court"),
    ("646 East Broadway", "02127", "South Boston Division, Boston Municipal Court"),
    ("365 Bremen St", "02128", "East Boston Division, Boston Municipal Court"),
    ("1961 Centre St", "02132", "West Roxbury Division, Boston Municipal Court"),
    ("41 Geneva Ave", "02121", "Dorchester Division, Boston Municipal Court"),
]


@pytest.fixture(scope="module")
def index() -> BostonAddressIndex:
    built = BostonAddressIndex.from_package_data()
    if built is None:
        pytest.skip(
            "bmc_addresses.sqlite is not built; run "
            "scripts/fetch_boston_sam.py and scripts/build_bmc_address_index.py"
        )
    return built


def test_opens_successfully(index: BostonAddressIndex) -> None:
    assert index.data_version


def test_integrity_check(index: BostonAddressIndex) -> None:
    connection = index.connection
    (result,) = connection.execute("PRAGMA integrity_check").fetchone()
    assert result == "ok"


def test_has_every_bmc_division(index: BostonAddressIndex) -> None:
    connection = index.connection
    names = {row[0] for row in connection.execute("SELECT court_name FROM divisions")}
    assert names == EXPECTED_DIVISIONS


def test_plausible_record_counts(index: BostonAddressIndex) -> None:
    connection = index.connection
    (address_count,) = connection.execute("SELECT COUNT(*) FROM addresses").fetchone()
    (street_count,) = connection.execute(
        "SELECT COUNT(DISTINCT street_id) FROM street_names"
    ).fetchone()
    assert address_count > 50_000
    assert street_count > 1_000


@pytest.mark.parametrize("street_address, zip_code, expected_division", STABLE_LOOKUPS)
def test_stable_address_lookups(
    index: BostonAddressIndex,
    street_address: str,
    zip_code: str,
    expected_division: str,
) -> None:
    resolution = index.resolve(street_address, zip_code=zip_code)
    assert resolution.match_kind == "success"
    assert resolution.court_name == expected_division


def test_no_foreign_key_orphans(index: BostonAddressIndex) -> None:
    connection = index.connection
    (orphans,) = connection.execute(
        """
        SELECT COUNT(*) FROM addresses
        WHERE division_id NOT IN (SELECT id FROM divisions)
        """
    ).fetchone()
    assert orphans == 0

    (orphans,) = connection.execute(
        """
        SELECT COUNT(*) FROM addresses
        WHERE street_id NOT IN (SELECT street_id FROM street_names)
        """
    ).fetchone()
    assert orphans == 0
