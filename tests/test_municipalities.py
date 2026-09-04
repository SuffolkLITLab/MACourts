from __future__ import annotations

import pytest

from macourts import (
    CourtFinder,
    Location,
    MunicipalityIndex,
    MunicipalityMatch,
    build_default_finder,
    get_county,
    is_canonical_municipality,
)

EXPECTED_COUNTIES = {
    "Barnstable County",
    "Berkshire County",
    "Bristol County",
    "Dukes County",
    "Essex County",
    "Franklin County",
    "Hampden County",
    "Hampshire County",
    "Middlesex County",
    "Nantucket County",
    "Norfolk County",
    "Plymouth County",
    "Suffolk County",
    "Worcester County",
}


@pytest.fixture(scope="module")
def muni_index():
    return MunicipalityIndex.from_package_data()


@pytest.fixture(scope="module")
def finder():
    return build_default_finder()


def test_municipality_index_loads_all_351_municipalities(muni_index):
    canonical = muni_index.canonical_municipalities()
    assert len(canonical) == 351
    assert "Boston" in canonical
    assert "Springfield" in canonical
    assert "Worcester" in canonical
    assert "Manchester-by-the-Sea" in canonical


def test_every_municipality_has_valid_county(muni_index):
    for name in muni_index.canonical_municipalities():
        county = muni_index.get_county(name)
        assert county in EXPECTED_COUNTIES, f"{name} has unexpected county: {county}"


def test_municipalities_by_county_covers_all_14_counties(muni_index):
    by_county = muni_index.canonical_municipalities_by_county()
    assert set(by_county.keys()) == EXPECTED_COUNTIES
    total_munis = sum(len(munis) for munis in by_county.values())
    assert total_munis == 351


def test_is_canonical_municipality(muni_index):
    assert muni_index.is_canonical_municipality("Boston")
    assert muni_index.is_canonical_municipality("boston")
    assert muni_index.is_canonical_municipality("North Attleborough")
    assert not muni_index.is_canonical_municipality("Hyannis")
    assert not muni_index.is_canonical_municipality("Dorchester")
    assert not muni_index.is_canonical_municipality("Nonexistent Town")


def test_canonical_name_capitalization(muni_index):
    assert muni_index.canonical_name("boston") == "Boston"
    assert muni_index.canonical_name("MANCHESTER-BY-THE-SEA") == "Manchester-by-the-Sea"
    assert muni_index.canonical_name("west springfield") == "West Springfield"
    assert muni_index.canonical_name("unknown place") is None


def test_get_county_helper_function():
    # Module-level convenience function
    assert get_county("Springfield") == "Hampden County"
    assert get_county("cambridge") == "Middlesex County"
    assert get_county("Barnstable") == "Barnstable County"
    assert get_county("Pittsfield") == "Berkshire County"
    assert get_county("Nantucket") == "Nantucket County"
    assert get_county("Edgartown") == "Dukes County"
    assert get_county("Salem") == "Essex County"
    assert get_county("Greenfield") == "Franklin County"
    assert get_county("Northampton") == "Hampshire County"
    assert get_county("Dedham") == "Norfolk County"
    assert get_county("Plymouth") == "Plymouth County"
    assert get_county("Boston") == "Suffolk County"
    assert get_county("Worcester") == "Worcester County"
    assert get_county("New Bedford") == "Bristol County"

    # Single-municipality community aliases
    assert get_county("Hyannis") == "Barnstable County"
    assert get_county("Whitinsville") == "Worcester County"
    assert get_county("Woods Hole") == "Barnstable County"
    assert get_county("Florence") == "Hampshire County"
    assert get_county("Dorchester") == "Suffolk County"

    # Unknown
    assert get_county("Narnia") is None
    assert get_county(None) is None


def test_resolve_alias(muni_index):
    # Single target alias
    matches = muni_index.resolve_alias("Hyannis")
    assert len(matches) == 1
    assert matches[0] == MunicipalityMatch("Barnstable", "Barnstable County", is_canonical=False)

    matches_whitinsville = muni_index.resolve_alias("Whitinsville")
    assert len(matches_whitinsville) == 1
    assert matches_whitinsville[0] == MunicipalityMatch("Northbridge", "Worcester County", is_canonical=False)

    # Multi-target alias (e.g. Shelburne Falls spans Shelburne and Buckland in Franklin County)
    matches_shelburne = muni_index.resolve_alias("Shelburne Falls")
    target_names = {m.name for m in matches_shelburne}
    assert target_names == {"Shelburne", "Buckland"}
    for m in matches_shelburne:
        assert m.county == "Franklin County"


def test_resolve_place_with_county_disambiguation(muni_index):
    # Canonical place
    matches = muni_index.resolve_place("Worcester")
    assert len(matches) == 1
    assert matches[0].name == "Worcester"
    assert matches[0].is_canonical is True

    # Multi-county alias disambiguated by county
    matches_ch_norfolk = muni_index.resolve_place("Chestnut Hill", county="Norfolk County")
    assert any(m.name == "Brookline" for m in matches_ch_norfolk)
    assert all(m.county == "Norfolk County" for m in matches_ch_norfolk)

    matches_ch_middlesex = muni_index.resolve_place("Chestnut Hill", county="Middlesex County")
    assert any(m.name == "Newton" for m in matches_ch_middlesex)
    assert all(m.county == "Middlesex County" for m in matches_ch_middlesex)


def test_location_with_inferred_county():
    # Canonical town with missing county using get_county lookup
    loc = Location(city="Worcester")
    inferred = loc.with_inferred_county(get_county)
    assert inferred.county == "Worcester County"
    assert inferred.city == "Worcester"

    loc_salem = Location(city="Salem")
    assert loc_salem.with_inferred_county(get_county).county == "Essex County"

    # Alias with missing county
    loc_hyannis = Location(city="Hyannis")
    assert loc_hyannis.with_inferred_county(get_county).county == "Barnstable County"

    # Default Boston neighborhood behavior without passing a lookup
    loc_dorchester = Location(city="Dorchester")
    assert loc_dorchester.with_inferred_county().county == "Suffolk County"

    # Existing county is preserved
    loc_explicit = Location(city="Cambridge", county="Middlesex County")
    assert loc_explicit.with_inferred_county(get_county).county == "Middlesex County"


def test_finder_resolves_village_aliases(finder):
    # Lookup using Hyannis (village in Barnstable)
    matches_hyannis = finder.find(Location(city="Hyannis"))
    match_names = {m.name for m in matches_hyannis}
    assert "Barnstable District Court" in match_names
    assert "Barnstable Juvenile Court" in match_names
    assert "Barnstable Probate and Family Court" in match_names
    assert "Barnstable County Superior Court" in match_names
    assert "Southeast Housing Court - Barnstable session" in match_names

    # Lookup using Whitinsville (village in Northbridge)
    matches_whitinsville = finder.find(Location(city="Whitinsville"))
    whitinsville_names = {m.name for m in matches_whitinsville}
    assert "Uxbridge District Court" in whitinsville_names
    assert "Milford Juvenile Court" in whitinsville_names
    assert "Worcester County Superior Court" in whitinsville_names

    # Lookup using Florence (village in Northampton)
    matches_florence = finder.find(Location(city="Florence"))
    florence_names = {m.name for m in matches_florence}
    assert "Northampton District Court" in florence_names
    assert "Hadley Juvenile Court" in florence_names
    assert "Hampshire County Superior Court" in florence_names


def test_missing_canonical_juvenile_court_additions(finder):
    # Finding 3 fixes
    brookline = finder.find(Location(city="Brookline", county="Norfolk County"), court_types=["Juvenile Court"])
    assert [m.name for m in brookline] == ["Dedham Juvenile Court"]

    mt_washington = finder.find(Location(city="Mount Washington", county="Berkshire County"), court_types=["Juvenile Court"])
    assert [m.name for m in mt_washington] == ["Great Barrington Juvenile Court"]

    savoy = finder.find(Location(city="Savoy", county="Berkshire County"), court_types=["Juvenile Court"])
    assert [m.name for m in savoy] == ["North Adams Juvenile Court"]

    truro = finder.find(Location(city="Truro", county="Barnstable County"), court_types=["Juvenile Court"])
    assert [m.name for m in truro] == ["Orleans Juvenile Court"]


def test_named_place_rules_win_over_the_canonical_municipality(finder):
    """A rule that names the neighborhood beats normalizing it to "Boston"."""
    east_boston = {m.name for m in finder.find(Location(city="East Boston"))}
    assert "Eastern Housing Court - Chelsea Session" in east_boston
    assert "Chelsea Juvenile Court" in east_boston
    assert "Eastern Housing Court" not in east_boston

    charlestown = {m.name for m in finder.find(Location(city="Charlestown"))}
    assert "Eastern Housing Court - Chelsea Session" in charlestown
    # Charlestown has no Juvenile rule of its own, so that department still
    # falls back to the canonical municipality.
    assert "Boston Juvenile Court" in charlestown

    # ZIP 02129's place name is literally "Charlestown".
    assert "Eastern Housing Court - Chelsea Session" in {
        m.name for m in finder.find_by_postal_code("02129")
    }


def test_departments_with_no_named_rule_still_use_the_municipality(finder):
    """East Boston reaches Suffolk's county-level courts through Boston."""
    names = {m.name for m in finder.find(Location(city="East Boston"))}
    assert "Suffolk County Superior Court" in names
    assert "Suffolk Probate and Family Court" in names


def test_inferred_county_disambiguates_a_multi_county_alias(finder):
    """"Mattapan" names both a Boston neighborhood and a corner of Milton."""
    names = {m.name for m in finder.find(Location(city="Mattapan"))}
    assert "Suffolk County Superior Court" in names
    assert "Norfolk County Superior Court" not in names
    assert "Quincy District Court" not in names

    # An explicit county still picks the other target.
    milton = {m.name for m in finder.find(Location(city="Mattapan", county="Norfolk County"))}
    assert "Norfolk County Superior Court" in milton


def test_a_county_rule_never_pre_empts_a_named_municipal_rule(finder):
    """Stoughton's own session must win over the Norfolk-wide Canton session.

    "East Stoughton" carries no county, so the finder infers Norfolk from the
    alias — which is enough for the Canton county rule to match the un-expanded
    location and, in a ``first`` chain, to hide the earlier Stoughton rule that
    the canonical municipality reaches.
    """
    names = {m.name for m in finder.find(Location(city="East Stoughton"))}
    assert "Metro South Housing Court - Stoughton Session" in names
    assert "Metro South Housing Court - Canton Session" not in names


def test_resolve_place_keeps_a_municipality_when_the_county_is_wrong():
    index = MunicipalityIndex.from_package_data()
    assert index.resolve_place("Franklin", county="Franklin County") == (
        MunicipalityMatch("Franklin", "Norfolk County", True),
    )
    assert index.resolve_place("Belmont", county="Norfolk County") == (
        MunicipalityMatch("Belmont", "Middlesex County", True),
    )
    # A county that does point at a same-named village still disambiguates.
    assert index.resolve_place("Franklin", county="Hampshire County") == (
        MunicipalityMatch("Belchertown", "Hampshire County", False),
    )


