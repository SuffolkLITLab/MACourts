import json
from pathlib import Path

import pytest

from macourts import (
    BostonMunicipalCourtMatcher,
    Coordinates,
    CourtCatalog,
    Location,
    StatewideMatcher,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jurisdiction_cases.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
CONTRACT_CASES = [case for case in CASES if case["status"] == "contract"]
REVIEW_CASES = [case for case in CASES if case["status"] == "review"]

_BMC_MATCHER = None
_STATEWIDE_MATCHER = StatewideMatcher()


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


def run_implemented_matcher(case):
    """Run departments already implemented in the shared package.

    Other department cases remain executable contracts and are xfailed until
    their matcher is ported. Add each new matcher here as migration progresses.
    """
    global _BMC_MATCHER

    location = make_location(case)
    department = case["department"]

    if department == "Boston Municipal Court":
        if _BMC_MATCHER is None:
            _BMC_MATCHER = BostonMunicipalCourtMatcher.from_package_data()
        return _BMC_MATCHER.match(location, [department])

    if department in {"Land Court", "Appeals Court", "Supreme Judicial Court"}:
        return _STATEWIDE_MATCHER.match(location, [department])

    return None


@pytest.mark.parametrize("case", CONTRACT_CASES, ids=lambda case: case["id"])
def test_jurisdiction_contract(case):
    matches = run_implemented_matcher(case)
    if matches is None:
        pytest.xfail(
            f'{case["department"]} matcher has not been ported to shared MACourts yet'
        )

    actual = sorted(match.name for match in matches)
    expected = sorted(case["expected"])
    assert actual == expected, case["rationale"]

    expected_reason = case.get("expected_reason")
    if expected_reason:
        assert matches
        assert all(match.reason.kind == expected_reason for match in matches)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_all_named_expected_courts_exist_in_packaged_catalog(case):
    catalog = CourtCatalog.from_package_data()
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


def test_bmc_contract_has_an_interior_point_for_every_division():
    catalog = CourtCatalog.from_package_data()
    catalog_names = {
        record.name
        for record in catalog.records
        if record.department == "Boston Municipal Court"
    }
    covered_names = {
        case["expected"][0]
        for case in CONTRACT_CASES
        if case["department"] == "Boston Municipal Court"
        and case.get("expected_reason") == "geometry"
        and case.get("expected")
    }
    assert covered_names == catalog_names
