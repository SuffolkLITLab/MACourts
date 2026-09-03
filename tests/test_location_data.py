import json

from macourts import CourtCatalog, package_data


EXPECTED_CURRENT_COUNTS = {
    "district_courts.json": 61,
    "housing_courts.json": 24,
    "bmc.json": 8,
    "superior_courts.json": 20,
    "juvenile_courts.json": 42,
    "probate_and_family_courts.json": 19,
    "land_court.json": 1,
    "appeals_court.json": 2,
    "supreme_judicial_court.json": 1,
}


def load(name):
    resource = package_data().joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8-sig"))


def test_current_location_counts_match_2026_massgov_rosters():
    for filename, expected in EXPECTED_CURRENT_COUNTS.items():
        assert len(load(filename)) == expected, filename


def test_every_current_court_has_address_audit_provenance():
    for filename in EXPECTED_CURRENT_COUNTS:
        for court in load(filename):
            assert court.get("address_verified") == "2026-09-03", (
                filename,
                court.get("name"),
            )
            assert court.get("address_source"), (filename, court.get("name"))


def test_winchendon_is_historical_not_current():
    current_names = {court["name"] for court in load("district_courts.json")}
    assert "Winchendon District Court" not in current_names

    historical = load("historical_courts.json")
    winchendon = next(
        court for court in historical if court["name"] == "Winchendon District Court"
    )
    assert winchendon["active"] is False
    assert winchendon["successor"] == "Gardner District Court"


def test_stoughton_housing_session_is_present_with_separate_filing_address():
    housing = load("housing_courts.json")
    stoughton = next(
        court
        for court in housing
        if court["name"] == "Metro South Housing Court - Stoughton Session"
    )
    assert stoughton["address"]["address"] == "1288 Central St."
    assert stoughton["filing_address"] == {
        "city": "Canton",
        "zip": "02021",
        "state": "MA",
        "address": "35 Shawmut Road",
    }
    assert stoughton["tyler_code"] is None


def test_juvenile_locations_have_unique_names_and_current_springfield_code():
    juvenile = load("juvenile_courts.json")
    names = [court["name"] for court in juvenile]
    assert len(names) == len(set(names))
    springfield = next(
        court for court in juvenile if court["name"] == "Springfield Juvenile Court"
    )
    assert springfield["court_code"] == "J69"


def test_superior_physical_location_names_are_unique():
    superior = load("superior_courts.json")
    location_names = [court["location_name"] for court in superior]
    assert len(location_names) == len(set(location_names))


def test_known_structured_address_repairs():
    housing = {court["name"]: court for court in load("housing_courts.json")}
    assert housing["Northeast Housing Court - Lynn Session"]["address"]["city"] == "Salem"
    assert housing["Northeast Housing Court - Salem Session"]["address"]["address"] == "56 Federal St."
    assert housing["Eastern Housing Court - Chelsea Session"]["address"]["county"] == "Suffolk County"

    district = {court["name"]: court for court in load("district_courts.json")}
    assert district["Fall River District Court"]["address"]["zip"] == "02721"
    assert district["Springfield District Court"]["address"]["zip"] == "01103"

    superior = {
        court["location_name"]: court for court in load("superior_courts.json")
    }
    assert superior["Nantucket County Superior Court"]["address"]["zip"] == "02554"
    assert superior["Plymouth County Superior Court"]["address"]["county"] == "Plymouth County"

    land = load("land_court.json")[0]
    assert land["address"]["unit"] == "5th floor"


def test_filing_and_appearance_relationships_are_resolvable():
    catalog = CourtCatalog.from_package_data()

    stoughton = catalog.resolve_location(
        "Metro South Housing Court - Stoughton Session",
        "Housing Court",
    )[0]
    canton = catalog.resolve_location(
        "Metro South Housing Court - Canton Session",
        "Housing Court",
    )[0]
    barnstable = catalog.resolve_location(
        "Southeast Housing Court - Barnstable Session",
        "Housing Court",
    )[0]
    new_bedford = catalog.resolve_location(
        "Southeast Housing Court - New Bedford Session",
        "Housing Court",
    )[0]

    assert stoughton.accepts_filings is False
    assert stoughton.filing_location_name == canton.location_name
    assert catalog.filing_location_for(stoughton) == canton
    assert "Metro South Housing Court - Stoughton Session" in canton.appearance_location_names

    assert barnstable.accepts_filings is False
    assert barnstable.filing_location_name == new_bedford.location_name
    assert catalog.filing_location_for(barnstable) == new_bedford
    assert "Southeast Housing Court - Barnstable Session" in new_bedford.appearance_location_names


def test_filing_location_filter_excludes_appearance_only_sessions():
    catalog = CourtCatalog.from_package_data()
    housing_filing_locations = {
        record.location_name
        for record in catalog.filing_locations("Housing Court")
    }

    assert "Metro South Housing Court - Stoughton Session" not in housing_filing_locations
    assert "Southeast Housing Court - Barnstable Session" not in housing_filing_locations
    assert "Metro South Housing Court - Canton Session" in housing_filing_locations
    assert "Southeast Housing Court - New Bedford Session" in housing_filing_locations


def test_tyler_route_keys_are_not_used_as_filing_identity():
    housing = {
        (court.get("location_name") or court["name"]): court
        for court in load("housing_courts.json")
    }
    stoughton = housing["Metro South Housing Court - Stoughton Session"]
    canton = housing["Metro South Housing Court - Canton Session"]

    assert stoughton["tyler_code"] is None
    assert stoughton["filing_location"] == "Metro South Housing Court - Canton Session"
    assert canton["tyler_code_status"] == "needs_reverification"
