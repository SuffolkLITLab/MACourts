"""Unit tests for the jurisdiction rule engine and the finder that drives it."""

import pytest

from macourts import (
    BostonMunicipalCourtMatcher,
    Coordinates,
    CourtCatalog,
    CourtFinder,
    JuvenileCourtMatcher,
    Location,
    LocationRule,
    NeighborhoodRule,
    RuleMatcher,
    ZipIndex,
    build_default_finder,
    build_matchers,
    load_data,
    load_jurisdiction_rules,
    normalize_postal_code,
)
from macourts.boston import JUVENILE_DIVISIONS

RULE_DEPARTMENTS = {
    "District Court",
    "Housing Court",
    "Juvenile Court",
    "Probate and Family Court",
    "Superior Court",
}


@pytest.fixture(scope="module")
def finder():
    return build_default_finder()


@pytest.fixture(scope="module")
def catalog():
    return CourtCatalog.from_package_data()


@pytest.fixture(scope="module")
def rule_matchers():
    return load_jurisdiction_rules()


# --- rule data -------------------------------------------------------------


def test_every_rule_department_is_loaded(rule_matchers):
    assert set(rule_matchers) == RULE_DEPARTMENTS


def test_rule_courts_all_exist_in_the_packaged_catalog(rule_matchers, catalog):
    for department, matcher in rule_matchers.items():
        known = set(catalog.names(department))
        named = {name for rule in matcher.rules for name in rule.court_names}
        assert named <= known, sorted(named - known)


def test_every_court_that_accepts_filings_is_reachable(rule_matchers, catalog):
    """A court no rule can return is a hole in the jurisdiction data.

    Appearance-only sessions are exempt: they are scheduled by the court rather
    than chosen from an address.
    """
    for department, matcher in rule_matchers.items():
        reachable = {name for rule in matcher.rules for name in rule.court_names}
        if department == "Juvenile Court":
            reachable |= set(JUVENILE_DIVISIONS.values())
        unreachable = {
            record.name
            for record in catalog.records
            if record.department == department
            and record.accepts_filings
            and record.name not in reachable
        }
        assert not unreachable, (department, sorted(unreachable))


def test_appearance_only_sessions_are_marked_rather_than_silently_unreachable(catalog):
    stoughton = catalog.resolve("Stoughton Juvenile Court", "Juvenile Court")[0]
    assert stoughton.accepts_filings is False
    assert stoughton.filing_location_name == "Dedham Juvenile Court"
    assert catalog.filing_location_for(stoughton).name == "Dedham Juvenile Court"


def test_rule_selection_modes_match_how_each_department_publishes_venue(rule_matchers):
    # Concurrent jurisdiction is normal in these departments.
    assert rule_matchers["District Court"].selection == "all"
    assert rule_matchers["Juvenile Court"].selection == "all"
    assert rule_matchers["Probate and Family Court"].selection == "all"
    # These are ordered chains: the first matching rule wins.
    assert rule_matchers["Housing Court"].selection == "first"
    assert rule_matchers["Superior Court"].selection == "first"


def test_rule_data_has_no_stray_or_misspelled_towns():
    data = load_data("jurisdiction_rules.json")
    cities = {
        city
        for block in data["departments"]
        for rule in block["rules"]
        for city in rule.get("cities", [])
    }
    assert cities.isdisjoint({"county", "northreading", "pepperrell", "southamptom", "nahunt"})
    assert {"north reading", "pepperell", "southampton", "nahant"} <= cities


def test_rules_are_stored_casefolded():
    data = load_data("jurisdiction_rules.json")
    for block in data["departments"]:
        for rule in block["rules"]:
            for key in ("cities", "counties", "excluded_cities"):
                for value in rule.get(key, []):
                    assert value == value.casefold(), (block["department"], value)


# --- rule semantics --------------------------------------------------------


def test_or_semantics_match_either_city_or_county():
    rule = LocationRule(
        department="Superior Court",
        court_names=("Suffolk County Superior Court",),
        cities=frozenset({"winthrop"}),
        counties=frozenset({"suffolk county"}),
    )
    assert rule.matches(Location(city="Winthrop", county="Norfolk County"))
    assert rule.matches(Location(city="Somewhere", county="Suffolk County"))
    assert not rule.matches(Location(city="Somewhere", county="Norfolk County"))


def test_require_all_semantics_need_both_city_and_county():
    rule = LocationRule(
        department="Probate and Family Court",
        court_names=("Middlesex Probate and Family Court - South",),
        cities=frozenset({"newton"}),
        counties=frozenset({"middlesex county"}),
        require_all=True,
    )
    assert rule.matches(Location(city="Newton", county="Middlesex County"))
    assert not rule.matches(Location(city="Newton", county="Norfolk County"))
    assert not rule.matches(Location(city="Concord", county="Middlesex County"))


def test_excluded_cities_veto_a_county_rule(finder):
    matches = finder.find(
        Location(city="Brookline", county="Norfolk County"), ["Housing Court"]
    )
    assert [match.name for match in matches] == ["Eastern Housing Court"]


def test_neighborhood_rule_can_be_scoped_to_one_city():
    rule = NeighborhoodRule(names=frozenset({"eagle hill"}), city="boston")
    assert rule.matches(Location(city="Boston", neighborhood="Eagle Hill"))
    assert not rule.matches(Location(city="Chelsea", neighborhood="Eagle Hill"))
    assert not rule.matches(Location(city="Boston"))


def test_first_selection_stops_at_the_first_matching_rule():
    matcher = RuleMatcher(
        [
            LocationRule("Housing Court", ("Specific Session",), cities=frozenset({"x"})),
            LocationRule("Housing Court", ("General Session",), cities=frozenset({"x"})),
        ],
        selection="first",
    )
    assert [c.name for c in matcher.match(Location(city="X"))] == ["Specific Session"]


def test_all_selection_keeps_concurrent_jurisdiction():
    matcher = RuleMatcher(
        [
            LocationRule("District Court", ("A District Court",), cities=frozenset({"x"})),
            LocationRule("District Court", ("B District Court",), cities=frozenset({"x"})),
        ],
        selection="all",
    )
    assert [c.name for c in matcher.match(Location(city="X"))] == [
        "A District Court",
        "B District Court",
    ]


def test_unknown_selection_mode_is_rejected():
    with pytest.raises(ValueError):
        RuleMatcher([], selection="sometimes")


# --- location normalization ------------------------------------------------


def test_bare_boston_neighborhood_city_infers_suffolk_county():
    assert Location(city="Dorchester").with_inferred_county().county == "Suffolk County"
    assert Location(city="West Roxbury").with_inferred_county().county == "Suffolk County"


def test_inference_never_overwrites_a_supplied_county():
    location = Location(city="Boston", county="Norfolk County")
    assert location.with_inferred_county().county == "Norfolk County"


def test_non_boston_cities_are_left_without_a_county():
    assert Location(city="Worcester").with_inferred_county().county is None


# --- ZIP expansion ---------------------------------------------------------


def test_postal_code_only_locations_are_detected():
    assert Location(postal_code="02072").is_postal_code_only
    assert not Location(city="Stoughton", postal_code="02072").is_postal_code_only
    assert not Location(postal_code="02072", coordinates=Coordinates(42.0, -71.0)).is_postal_code_only


def test_four_digit_postal_codes_are_zero_padded():
    assert normalize_postal_code(2072) == "02072"
    assert normalize_postal_code("02072") == "02072"
    assert normalize_postal_code(None) == ""


def test_zip_plus_four_falls_back_to_the_five_digit_zip():
    index = ZipIndex.from_package_data()
    assert index.locations("02072-1234")[0].city == "Stoughton"


def test_zip_expansion_unions_every_place_the_zip_covers():
    """A ZIP spanning several towns expands to one location per town.

    The packaged table happens to be one-place-per-ZIP today, but callers can
    supply a richer table, so the split is exercised directly.
    """
    index = ZipIndex(
        {
            "01234": {
                "place_name": "Freetown, Westport",
                "county_name": "Bristol",
                "latitude": 41.8,
                "longitude": -71.0,
            }
        }
    )
    locations = index.locations("01234")
    assert [location.city for location in locations] == ["Freetown", "Westport"]
    assert {location.county for location in locations} == {"Bristol County"}


def test_zip_expansion_feeds_every_covered_town_into_matching():
    index = ZipIndex(
        {
            "01234": {
                "place_name": "Freetown, Westport",
                "county_name": "Bristol",
                "latitude": 41.8,
                "longitude": -71.0,
            }
        }
    )
    finder = CourtFinder(
        build_matchers(),
        catalog=CourtCatalog.from_package_data(),
        zip_index=index,
    )
    matches = finder.find_by_postal_code("01234", ["District Court"])
    assert [match.name for match in matches] == [
        "Fall River District Court",
        "New Bedford District Court",
    ]


def test_finder_records_the_zip_it_expanded_from(finder):
    matches = finder.find_by_postal_code("02072", ["Housing Court"])
    assert matches
    reasons = {reason.kind for match in matches for reason in match.reasons}
    assert "postal_code" in reasons


def test_unknown_zip_leaves_only_the_statewide_courts(finder):
    """An unrecognized ZIP still names a Massachusetts address, not a venue."""
    matches = finder.find_by_postal_code("99999")
    assert {match.department for match in matches} == {
        "Land Court",
        "Appeals Court",
        "Supreme Judicial Court",
    }


# --- Boston Municipal Court and the sessions derived from it ---------------


def test_juvenile_bmc_divisions_replace_the_city_rule(finder):
    # A point inside the West Roxbury BMC division, given only as "Boston".
    location = Location(
        city="Boston",
        county="Suffolk County",
        coordinates=Coordinates(42.258556551409946, -71.15905884432543),
    )
    matches = finder.find(location, ["Juvenile Court"])
    assert [match.name for match in matches] == ["West Roxbury Juvenile Court"]
    assert {reason.kind for reason in matches[0].reasons} == {"bmc_division"}


def test_juvenile_falls_back_to_city_rules_outside_those_divisions(finder):
    matches = finder.find(
        Location(city="Worcester", county="Worcester County"), ["Juvenile Court"]
    )
    assert [match.name for match in matches] == ["Worcester Juvenile Court"]


def test_juvenile_matcher_needs_no_coordinates_to_work():
    rules = load_jurisdiction_rules()["Juvenile Court"]
    matcher = JuvenileCourtMatcher(rules, BostonMunicipalCourtMatcher.from_package_data())
    candidates = matcher.match(Location(city="Nantucket", county="Nantucket County"))
    assert [candidate.name for candidate in candidates] == ["Nantucket Juvenile Court"]


def test_bmc_division_returns_none_outside_boston():
    matcher = BostonMunicipalCourtMatcher.from_package_data()
    assert matcher.division(Location(city="Worcester", county="Worcester County")) is None


# --- finder composition ----------------------------------------------------


ALL_DEPARTMENTS = RULE_DEPARTMENTS | {
    "Boston Municipal Court",
    "Land Court",
    "Appeals Court",
    "Supreme Judicial Court",
}


def test_boston_reaches_every_department_except_the_district_court(finder):
    """Inside Boston the BMC has the District Court's trial jurisdiction."""
    matches = finder.find(
        Location(
            city="Boston",
            county="Suffolk County",
            coordinates=Coordinates(42.336633930640154, -71.06846838831075),
        )
    )
    assert {match.department for match in matches} == ALL_DEPARTMENTS - {
        "District Court"
    }


def test_two_addresses_together_reach_all_nine_departments(finder):
    matches = finder.find(
        [
            Location(
                city="Boston",
                county="Suffolk County",
                coordinates=Coordinates(42.336633930640154, -71.06846838831075),
            ),
            Location(city="Worcester", county="Worcester County"),
        ]
    )
    assert {match.department for match in matches} == ALL_DEPARTMENTS


def test_finder_accepts_several_locations_at_once(finder):
    matches = finder.find(
        [
            Location(city="Worcester", county="Worcester County"),
            Location(city="Springfield", county="Hampden County"),
        ],
        ["Superior Court"],
    )
    assert [match.name for match in matches] == [
        "Hampden County Superior Court",
        "Worcester County Superior Court",
    ]


def test_court_types_filter_is_honoured_by_every_matcher(finder):
    location = Location(city="Boston", county="Suffolk County")
    for department in ("Housing Court", "Superior Court", "Land Court"):
        matches = finder.find(location, [department])
        assert matches
        assert {match.department for match in matches} == {department}


def test_matches_carry_their_catalog_records(finder):
    matches = finder.find(
        Location(city="New Bedford", county="Bristol County"), ["Superior Court"]
    )
    assert matches[0].name == "Bristol County Superior Court"
    # Bristol Superior sits in three locations under one semantic name.
    assert len(matches[0].records) == 3


def test_finder_without_a_zip_index_leaves_postal_code_only_locations_alone():
    plain = CourtFinder(build_matchers(), catalog=CourtCatalog.from_package_data())
    assert plain.find(Location(postal_code="02072"), ["Housing Court"]) == []


def test_four_digit_postal_code_strings_are_zero_padded(finder):
    """A ZIP that lost its leading zero in a spreadsheet still routes."""
    assert normalize_postal_code("2072") == "02072"
    assert normalize_postal_code("02072") == "02072"
    assert normalize_postal_code("02072-1234") == "02072-1234"
    assert [m.name for m in finder.find_by_postal_code("2072")] == [
        m.name for m in finder.find_by_postal_code("02072")
    ]
