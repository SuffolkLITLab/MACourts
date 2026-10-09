"""Docket-number parsing, ported from docassemble-MACourts' test_docket_numbers.py."""

from datetime import date

import pytest

from macourts import (
    DocketNumberParser,
    get_sequence_number_from_docket_number,
    get_year_from_docket_number,
    TylerCourt,
    identify_court_from_docket_number,
)


@pytest.fixture(scope="module")
def parser():
    return DocketNumberParser()


@pytest.mark.parametrize(
    "docket_number, expected_name",
    [
        ("1577CV00982", "Essex County Superior Court"),
        ("1577cv00982", "Essex County Superior Court"),
        # Winchendon (70) was consolidated into Gardner, but old dockets keep the code.
        ("1670CV000072", "Winchendon District Court"),
        ("1401CV001026", "Central Division, Boston Municipal Court"),
        ("07 TL 001026", "Land Court"),
        ("2020-P-0874", "Massachusetts Appeals Court (Panel)"),
        ("2020-p-0874", "Massachusetts Appeals Court (Panel)"),
        ("2020-J-0123", "Massachusetts Appeals Court (Single Justice)"),
        ("SJC-13103", "Supreme Judicial Court"),
        ("sjc-13103", "Supreme Judicial Court"),
    ],
)
def test_court_name(parser, docket_number, expected_name):
    assert parser.court_from_docket_number(docket_number).name == expected_name


# The regex doesn't yet handle hyphenated "variations" of the trial court
# format (e.g. 1577-CV-00982), even the unambiguous ones.


@pytest.mark.parametrize(
    "docket_number, expected_names",
    [
        (
            "15H84CV000436",
            {
                "Eastern Housing Court",
                "Eastern Housing Court - Middlesex Session",
                "Eastern Housing Court - Chelsea Session",
            },
        ),
        (
            "15h84cv000436",
            {
                "Eastern Housing Court",
                "Eastern Housing Court - Middlesex Session",
                "Eastern Housing Court - Chelsea Session",
            },
        ),
        (
            "ES15A0064AD",
            {"Essex Probate and Family Court", "Lawrence Probate and Family Court"},
        ),
        (
            "es15A0064ad",
            {"Essex Probate and Family Court", "Lawrence Probate and Family Court"},
        ),
    ],
)
def test_court_names(parser, docket_number, expected_names):
    matching = parser.courts_from_docket_number(docket_number)
    assert {record.name for record in matching} == expected_names
    assert len(matching) == len(expected_names)


def test_court_keeps_only_shared_fields(parser):
    court = parser.court_from_docket_number("15H84CV000436")
    assert court.name is None
    assert court.department == "Housing Court"
    assert court.court_code == "H84"


@pytest.mark.parametrize(
    "docket_number",
    [
        "",
        "complete gibberish",
        "123098120398213098123",
        "12",
        "9999CV00000",
        "1000-K-1234",
    ],
)
def test_court_not_found(parser, docket_number):
    with pytest.raises(KeyError):
        parser.courts_from_docket_number(docket_number)


@pytest.mark.parametrize(
    "docket_number, expected_case_type",
    [
        ("1577CV00982", "Civil"),
        ("1577cv00982", "Civil"),
        ("1448CV001026", "Civil"),
        ("1448SU001026", "Summary Process (Eviction)"),
        ("1448SP001026", "Supplementary Process"),
        ("1401RO001026", "Abuse Prevention Order"),
        # The Housing Court reverses the District Court's SP and SU.
        ("15H84SP000436", "Summary Process (Eviction)"),
        ("15H84SU000436", "Supplementary Process"),
        ("15H84TK000436", "Ticket Hearings"),
        ("1473CV00213", "Civil"),
        ("1473BP00213", "Bail Petition"),
        ("07 TL 001026", "Tax Lien"),
        ("07 VP 001026", "Void Provisions"),
        ("07 MISC 000456", "Miscellaneous"),
        ("15 SBQ 00025 09 - 001", "Subsequent"),
        ("ES15W0064WD", "Parentage"),
        ("SU15X0064SJ", "Special Immigration Juvenile Status"),
        # AD is Adoption in Probate and Family Court but Appeal elsewhere.
        ("ES15A0064AD", "Adoption"),
        ("1401AD001026", "Appeal"),
        ("2020-P-0874", "Appellate"),
        ("SJC-13103", "Appellate"),
    ],
)
def test_case_type(parser, docket_number, expected_case_type):
    assert parser.case_type_from_docket_number(docket_number) == expected_case_type


@pytest.mark.parametrize(
    "docket_number",
    [
        "1577ZZ00982",
        # Codes that exist, but only in another department.
        "1473SU00213",
        "15H84MV000436",
        "1448BP001026",
        "ES15A0064CV",
    ],
)
def test_unknown_case_type(parser, docket_number):
    with pytest.raises(KeyError):
        parser.case_type_from_docket_number(docket_number)


@pytest.mark.parametrize(
    "docket_number, expected_case_group",
    [
        ("ES15A0064AD", "Adoption"),
        ("MI20D0123DR", "Domestic Relations"),
        ("SU15W0064WD", "Parentage"),
        ("1577CV00982", None),
    ],
)
def test_case_group(parser, docket_number, expected_case_group):
    assert parser.case_group_from_docket_number(docket_number) == expected_case_group


@pytest.mark.parametrize(
    "docket_number, expected_name",
    [
        ("1448CV001026", "Ayer District Court"),
        ("1409CV001026", "Brookline District Court"),
        ("1408CV001026", "Brighton Division, Boston Municipal Court"),
        ("1473CV00213", "Bristol County Superior Court"),
        ("07 VP 001026", "Land Court"),
        ("15 SBQ 00025 09 - 001", "Land Court"),
        ("2020-J-0123", "Massachusetts Appeals Court (Single Justice)"),
        ("SJ-2020-0123", "Supreme Judicial Court"),
        ("BD-2020-0123", "Supreme Judicial Court"),
    ],
)
def test_mass_gov_examples(parser, docket_number, expected_name):
    """Examples from each department's mass.gov case number format page."""
    assert parser.court_from_docket_number(docket_number).name == expected_name


@pytest.mark.parametrize(
    "docket_number, department, court_code, name, location_count",
    [
        ("1448CV001026", "District Court", "48", "Ayer District Court", 1),
        ("1670CV000072", "District Court", "70", "Winchendon District Court", 1),
        (
            "1401CV001026",
            "Boston Municipal Court",
            "01",
            "Central Division, Boston Municipal Court",
            1,
        ),
        ("15H84CV000436", "Housing Court", "H84", None, 3),
        ("1473CV00213", "Superior Court", "73", "Bristol County Superior Court", 3),
        ("ES15A0064AD", "Probate and Family Court", "ES", None, 2),
        ("07 TL 001026", "Land Court", None, "Land Court", 1),
        ("26YO0010NE", "Juvenile Court", "NE", "New Bedford Juvenile Court", 1),
        # Palmer also files under 986:SP; Tyler names that code Springfield.
        ("25yo0002sp", "Juvenile Court", "SP", "Springfield Juvenile Court", 1),
        ("26YO0023DO", "Juvenile Court", "DO", "Dorchester Juvenile Court", 1),
        ("26YO0001ZZ", "Juvenile Court", "ZZ", None, 0),
        (
            "2020-P-0874",
            "Appeals Court",
            "P",
            "Massachusetts Appeals Court (Panel)",
            1,
        ),
        ("SJC-13103", "Supreme Judicial Court", None, "Supreme Judicial Court", 1),
    ],
)
def test_identify_court(parser, docket_number, department, court_code, name, location_count):
    identification = parser.identify_court(docket_number)
    assert identification.department == department
    assert identification.court_code == court_code
    assert identification.name == name
    assert len(identification.locations) == location_count
    assert {record.department for record in identification.locations} <= {department}


def test_identify_court_module_function():
    identification = identify_court_from_docket_number(" 15H84CV000436 ")
    assert identification.department == "Housing Court"
    assert {record.name for record in identification.locations} == {
        "Eastern Housing Court",
        "Eastern Housing Court - Middlesex Session",
        "Eastern Housing Court - Chelsea Session",
    }


def test_every_docket_court_code_is_in_one_department(parser):
    """A code in a docket number must never be ambiguous between departments."""
    codes = {
        record.court_code
        for record in parser.catalog.records + parser.historical
        if record.court_code
    } | set(parser.probate_site_codes.values())
    for code in codes:
        departments = {record.department for record in parser.catalog.resolve_court_code(code)}
        assert len(departments) <= 1, (code, departments)


@pytest.mark.parametrize(
    "docket_number",
    # The session code ("SP", "NP") must not be mistaken for the Appeals
    # Court's "P", nor "SM" in the case type for a Land Court case type.
    ["26YO0010NE", "25YO0002SP", "26YO0008NP", "26DL0001DO", "26SM0001NE"],
)
def test_juvenile_court_is_not_another_department(parser, docket_number):
    assert parser.identify_court(docket_number).department == "Juvenile Court"


def test_juvenile_court_unknown_session(parser):
    with pytest.raises(KeyError):
        parser.courts_from_docket_number("26YO0001ZZ")


@pytest.mark.parametrize(
    "docket_number, tyler_courts",
    [
        ("1473CV00213", [("1126", "Superior Court - Bristol")]),
        ("15H84SP000436", [("537", "Housing - Eastern (Boston)")]),
        ("1401CV001026", [("1245", "BMC - Central")]),
        ("ES15A0064AD", [("352", "Probate and Family - Essex")]),
        ("26YO0002LA", [("705:LA", "Juvenile Court -- Essex County -- Lawrence")]),
        # Dorchester files through Boston.
        ("26YO0023DO", [("1086:BO", "Juvenile Court -- Suffolk County -- Boston")]),
        ("07 TL 001026", [("210", "Land Court")]),
        ("2020-P-0874", [("appeals:acp", "Appeals Court - Panel (P docket)")]),
        ("SJC-13103", [("sjc:commfc", "Supreme Judicial Court - Full Court")]),
        ("SJ-2020-0123", [("sjc:singlej", "Supreme Judicial Court - Suffolk - Single Justice")]),
        ("BD-2020-0123", [("sjc:suffolk", "Supreme Judicial Court – Suffolk – Bar Docket")]),
    ],
)
def test_tyler_courts(parser, docket_number, tyler_courts):
    identification = parser.identify_court(docket_number)
    assert [(c.code, c.name) for c in identification.tyler_courts] == tyler_courts


def test_tyler_test_environment_uses_its_own_code_spelling():
    parser = DocketNumberParser(tyler_environment="test")
    identification = parser.identify_court("26YO0002LA")
    (court,) = identification.tyler_courts
    assert (court.code, court.name) == ("0705:LA", "Juvenile Court -- Essex County -- Lawrence")
    # Staging lacks many production courts; the code is kept, without a name.
    assert parser.identify_court("1477CV00213").tyler_courts == (TylerCourt("1177", None),)


@pytest.mark.parametrize(
    "docket_number, tyler_code",
    [
        ("1448CV001026", "336"),
        ("1401CV001026", "1245"),
        # Three Eastern Housing sessions, but one Tyler court.
        ("15H84SP000436", "537"),
        ("15H82SP000436", "1265"),
        ("1473CV00213", "1126"),
        ("ES15A0064AD", "352"),
        ("26YO0023DO", "1086:BO"),
        ("07 TL 001026", "210"),
        ("2020-J-0123", "appeals:acsj"),
        ("SJC-13103", "sjc:commfc"),
        # Retired, but Tyler still takes filings in its existing cases.
        ("1670CV000072", "437"),
    ],
)
def test_existing_case_courts(parser, docket_number, tyler_code):
    courts = parser.identify_court(docket_number).existing_case_courts
    assert [court.code for court in courts] == [tyler_code]


def test_existing_case_courts_several_candidates(parser):
    """Southeast Housing Court sessions share H83 but file under separate codes."""
    identification = parser.identify_court("15H83SP000436")
    assert {court.code for court in identification.existing_case_courts} == {
        "555:CI",
        "555:FR",
        "555:NB",
        "555:PL",
        "555:TA",
    }


def test_existing_case_courts_require_subsequent_filing():
    parser = DocketNumberParser(
        tyler_courts={"prod": {"336": {"name": "District Court - Ayer", "initial": True}}}
    )
    assert parser.identify_court("1448CV001026").existing_case_courts == ()


def test_unknown_tyler_environment():
    with pytest.raises(ValueError):
        DocketNumberParser(tyler_environment="staging")


def test_every_catalog_tyler_code_is_in_prod(parser):
    missing = {
        record.tyler_code
        for record in parser.catalog.records
        if record.tyler_code and parser.tyler_court(record.tyler_code).name is None
    }
    assert not missing


def test_prod_efiling_status(parser):
    # Every current court the catalog routes filings to accepts e-filing in
    # prod, except the SJC's "Commonwealth" node, which docket numbers avoid.
    not_fileable = {
        record.tyler_code
        for record in parser.catalog.records
        if record.tyler_code and not parser.tyler_court(record.tyler_code).accepts_efiling
    }
    assert not_fileable == {"sjc"}
    for docket_number in ["SJC-13103", "SJ-2020-0123", "BD-2020-0123"]:
        (court,) = parser.identify_court(docket_number).tyler_courts
        assert court.initial and court.subsequent
    # Winchendon was consolidated into Gardner: existing cases only.
    (winchendon,) = parser.identify_court("1670CV000072").tyler_courts
    assert (winchendon.initial, winchendon.subsequent) == (False, True)


@pytest.mark.parametrize(
    "docket_number, expected_year",
    [
        ("1577CV00982", "2015"),
        ("15-0982", "2015"),
        ("15-CV-00982", "2015"),
        ("2015-982", "2015"),
        ("2015-00982", "2015"),
        ("ES15A0064AD", "2015"),
        ("07 TL 001026", "2007"),
        ("26YO0010NE", "2026"),
        # 2020 is harder to parse: "20" also starts the four-digit form.
        ("2077CV00982", "2020"),
        ("20-0982", "2020"),
        ("20-CV-00982", "2020"),
        ("2020-982", "2020"),
        ("2020-00982", "2020"),
    ],
)
def test_year(docket_number, expected_year):
    assert get_year_from_docket_number(docket_number) == expected_year


def test_year_without_one():
    assert get_year_from_docket_number("SJC-13103") is None


def test_year_in_the_future():
    with pytest.raises(ValueError):
        get_year_from_docket_number("2677CV00982", today=date(2025, 1, 1))
    assert get_year_from_docket_number("2577CV00982", today=date(2025, 1, 1)) == "2025"


@pytest.mark.parametrize(
    "docket_number, expected_sequence",
    [
        ("1577CV00982", "00982"),
        ("ES15A0064AD", "0064"),
        ("2020-P-0874", "0874"),
        ("SJC-13103", "13103"),
        ("1448CV001026", "001026"),
        ("07 TL 000456", "000456"),
        ("15 SBQ 00025 09 - 001", "001"),
    ],
)
def test_sequence_number(docket_number, expected_sequence):
    assert get_sequence_number_from_docket_number(docket_number) == expected_sequence
