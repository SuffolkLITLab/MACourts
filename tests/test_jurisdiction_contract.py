import json
from pathlib import Path

import pytest

from macourts import (
    Coordinates,
    CourtCatalog,
    Location,
    build_default_finder,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jurisdiction_cases.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
CONTRACT_CASES = [case for case in CASES if case["status"] == "contract"]
REVIEW_CASES = [case for case in CASES if case["status"] == "review"]

DEPARTMENTS = [
    "Boston Municipal Court",
    "District Court",
    "Housing Court",
    "Juvenile Court",
    "Probate and Family Court",
    "Superior Court",
    "Land Court",
    "Appeals Court",
    "Supreme Judicial Court",
]


@pytest.fixture(scope="module")
def finder():
    return build_default_finder()


@pytest.fixture(scope="module")
def catalog():
    return CourtCatalog.from_package_data()


def make_location(case):
    data = case["location"]
    coordinates = None
    if "latitude" in data and "longitude" in data:
        coordinates = Coordinates(
            latitude=data["latitude"],
            longitude=data["longitude"],
        )
    return Location(
        city=data.get("city"),
        county=data.get("county"),
        state=data.get("state"),
        postal_code=data.get("postal_code"),
        neighborhood=data.get("neighborhood"),
        coordinates=coordinates,
    )


@pytest.mark.parametrize("case", CONTRACT_CASES, ids=lambda case: case["id"])
def test_jurisdiction_contract(finder, case):
    matches = finder.find(make_location(case), [case["department"]])

    actual = sorted(match.name for match in matches)
    expected = sorted(case["expected"])
    assert actual == expected, case["rationale"]

    expected_reason = case.get("expected_reason")
    if expected_reason:
        assert matches
        for match in matches:
            assert expected_reason in {reason.kind for reason in match.reasons}


@pytest.mark.parametrize("case", CONTRACT_CASES, ids=lambda case: case["id"])
def test_every_contract_match_resolves_to_a_court_record(finder, case):
    for match in finder.find(make_location(case), [case["department"]]):
        assert match.records, f'{case["id"]}: {match.name} has no catalog record'


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_all_named_expected_courts_exist_in_packaged_catalog(catalog, case):
    names = []
    names.extend(case.get("expected", []))
    names.extend(case.get("legacy_expected", []))
    names.extend(case.get("possible", []))

    for name in names:
        assert catalog.resolve(name, case["department"]), (
            f'{case["id"]}: expected court {name!r} is missing from '
            f'{case["department"]} package data'
        )


def test_contract_case_ids_are_unique():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))


def test_review_cases_are_explicit_and_actionable():
    for case in REVIEW_CASES:
        assert case.get("legacy_expected")
        assert len(case.get("possible", [])) >= 2
        assert case.get("rationale")


def test_every_department_has_contract_coverage():
    covered = {case["department"] for case in CONTRACT_CASES}
    assert covered == set(DEPARTMENTS)


def test_bmc_contract_has_an_interior_point_for_every_division(catalog):
    catalog_names = set(catalog.names("Boston Municipal Court"))
    covered_names = {
        case["expected"][0]
        for case in CONTRACT_CASES
        if case["department"] == "Boston Municipal Court"
        and case.get("expected_reason") == "geometry"
        and case.get("expected")
    }
    assert covered_names == catalog_names


def test_out_of_state_addresses_match_nothing(finder):
    location = Location(city="Boston", county="Suffolk County", state="NY")
    assert finder.find(location) == []


def test_finder_covers_every_department_for_a_single_address(finder):
    matches = finder.find(
        Location(city="Worcester", county="Worcester County", state="MA")
    )
    assert {match.department for match in matches} == set(DEPARTMENTS) - {
        "Boston Municipal Court"
    }
