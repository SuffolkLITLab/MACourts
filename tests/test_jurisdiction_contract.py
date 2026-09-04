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


# Place names in the rule data that deliberately answer differently from the
# municipality they sit in, because the Trial Court gives them their own venue.
INTENTIONAL_VENUE_EXCEPTIONS = {
    "charlestown",
    "east boston",
}


def test_spelling_variants_in_rules_agree_with_their_municipality(finder):
    """A rule naming a variant spelling must not answer differently from the town.

    `match_named_place` lets a name the rule data spells out win before it is
    normalized, which is what gives East Boston its Chelsea sessions. The same
    precedence turns a *spelling* variant into a bug when the two spellings land
    in different rules: "middleboro" once returned Brockton Probate & Family and
    "middleborough" returned Plymouth, for one town served by both.
    """
    index = finder.municipality_index
    rule_cities = {
        city.casefold()
        for block in json.loads(
            (Path(__file__).parents[1] / "macourts" / "data" / "jurisdiction_rules.json")
            .read_text(encoding="utf-8")
        )["departments"]
        for rule in block["rules"]
        for city in rule.get("cities", ())
    }

    divergent = {}
    for name in sorted(rule_cities - set(INTENTIONAL_VENUE_EXCEPTIONS)):
        if index.is_canonical_municipality(name):
            continue
        targets = index.resolve_alias(name)
        if len(targets) != 1:
            continue  # a village spanning several towns, not a spelling variant
        canonical = targets[0].name
        variant_courts = {m.name for m in finder.find(Location(city=name))}
        town_courts = {m.name for m in finder.find(Location(city=canonical))}
        if variant_courts != town_courts:
            divergent[name] = (canonical, sorted(town_courts ^ variant_courts))

    assert not divergent, f"spelling variants answering differently: {divergent}"


@pytest.mark.parametrize(
    "county", ["Barnstable County", "Dukes County", "Nantucket County"]
)
def test_barnstable_housing_session_names_its_whole_territory(finder, county):
    """The session serves three whole counties, so its city list must name them all.

    The rule sits in a ``first`` chain behind a county rule that already covers
    these towns, which is what let four of them go unnamed for so long. Asserting
    on the rule data rather than through `find()` keeps the check independent of
    that ordering.
    """
    rules = json.loads(
        (Path(__file__).parents[1] / "macourts" / "data" / "jurisdiction_rules.json")
        .read_text(encoding="utf-8")
    )
    listed = {
        city.casefold()
        for block in rules["departments"]
        if block["department"] == "Housing Court"
        for rule in block["rules"]
        if rule["courts"] == ["Southeast Housing Court - Barnstable session"]
        for city in rule.get("cities", ())
    }
    towns = finder.municipality_index.canonical_municipalities_by_county()[county]
    assert not [t for t in towns if t.casefold() not in listed]


METRO_SOUTH_BROCKTON_TOWNS = {
    "Abington",
    "Bridgewater",
    "Brockton",
    "East Bridgewater",
    "West Bridgewater",
    "Whitman",
}


def test_metro_south_sessions_match_the_published_roster(finder):
    """Brockton keeps six towns; Canton takes Norfolk County except Brookline.

    The Brockton rule sits ahead of the Canton county rule in the ``first``
    chain, so an over-broad Brockton list silently shadows Canton rather than
    conflicting with it.
    """
    def housing(town):
        return [m.name for m in finder.find(Location(city=town), ["Housing Court"])]

    for town in sorted(METRO_SOUTH_BROCKTON_TOWNS):
        assert housing(town) == ["Metro South Housing Court - Brockton Session"], town

    norfolk = finder.municipality_index.canonical_municipalities_by_county()[
        "Norfolk County"
    ]
    for town in norfolk:
        if town == "Brookline":
            assert housing(town) == ["Eastern Housing Court"]
        elif town == "Stoughton":
            assert housing(town) == ["Metro South Housing Court - Stoughton Session"]
        else:
            assert housing(town) == [
                "Metro South Housing Court - Canton Session"
            ], town

    # Metro South's territory does not reach the Cape.
    assert housing("Eastham") == ["Southeast Housing Court - Barnstable session"]
