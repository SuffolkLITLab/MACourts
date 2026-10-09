"""Massachusetts docket-number parsing (the "smart docket" tool).

Ported from ``MACourtList`` in docassemble-MACourts. A docket number like
``1577CV00982`` encodes the filing year (``15``), the court (``77``, Essex
County Superior Court), the case type (``CV``, Civil), and a sequence number
(``00982``). The formats differ by department; see the sources listed in
``court_code_crosswalk.json``.

The Juvenile Court publishes no format. Its docket numbers (e.g.
``26YO0010NE``: year, case type, sequence, session) end in a session code that
usually matches the suffix of the session's Tyler code (``1015:NE``).

Each identification also carries the Tyler EFSP court codes and names for its
locations, from the ``tyler_courts.json`` snapshot of the EFSP proxy's court
list (refreshed by ``scripts/fetch_tyler_courts.py``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from datetime import date
from typing import Iterable, Mapping

from .catalog import CourtCatalog, load_data
from .models import CourtRecord, norm

# Case-type codes by department, from the mass.gov "Get to know the case
# number format" page for each one. Several case types share a code (e.g.
# Civil, Marriage Waiver, and Non Support are all CV), so each code maps to
# the general name. The Juvenile Court has no published format.
DISTRICT_COURT_CASE_TYPE_CODES = {
    "AC": "Application for Criminal Complaint",
    "AD": "Appeal",
    "CI": "Civil Infraction",
    "CR": "Criminal",
    "CV": "Civil",
    "IC": "Interstate Compact",
    "IN": "Inquest",
    "MH": "Mental Health",
    "MV": "Civil Motor Vehicle",
    "RO": "Abuse Prevention Order",
    "SC": "Small Claims",
    "SP": "Supplementary Process",
    "SU": "Summary Process (Eviction)",
    "SW": "Administrative Search Warrant",
}

# The Boston Municipal Court page lists the same codes as the District Court's.
BMC_CASE_TYPE_CODES = DISTRICT_COURT_CASE_TYPE_CODES

# SP and SU are the reverse of the District Court's.
HOUSING_COURT_CASE_TYPE_CODES = {
    "CR": "Criminal",
    "CV": "Civil",
    "PC": "Probable Cause",
    "SC": "Small Claims",
    "SP": "Summary Process (Eviction)",
    "SU": "Supplementary Process",
    "TK": "Ticket Hearings",
}

# The Superior Court calls these "case groups".
SUPERIOR_COURT_CASE_TYPE_CODES = {
    "BP": "Bail Petition",
    "CR": "Criminal",
    "CV": "Civil",
}

# Servicemembers cases were filed as MISC through 2014, and Severed cases are
# filed as REG.
LAND_COURT_CASE_TYPE_CODES = {
    "MISC": "Miscellaneous",
    "PS": "Permit Session",
    "REG": "Registration",
    "SBQ": "Subsequent",
    "SM": "Servicemembers",
    "TL": "Tax Lien",
    "VP": "Void Provisions",
}

# "AD" is Adoption here, but Appeal in the District Court and BMC.
PROBATE_FAMILY_COURT_CASE_TYPE_CODES = {
    "AB": "Protection from Abuse",
    "AD": "Adoption",
    "CA": "Change of Name",
    "CS": "Custody, Support, and Parenting Time",
    "CW": "Child Welfare",
    "DO": "Domestic Relations, Other",
    "DR": "Domestic Relations",
    "EA": "Estates and Administration",
    "GD": "Guardianship",
    "JP": "Joint Petition",
    "PE": "Parentage in Equity",
    "PM": "Probate Abuse / Conservator",
    "PO": "Probate, Other",
    "PP": "Equity-Partition",
    "QC": "Equity Complaint",
    "QP": "Equity Petition",
    "SJ": "Special Immigration Juvenile Status",
    "SK": "Wills for Safekeeping",
    "WD": "Parentage",
    "XY": "Proxy Guardianship",
}

PROBATE_FAMILY_COURT_CASE_GROUP_CODES = {
    "A": "Adoption",
    "C": "Change of Name",
    "D": "Domestic Relations",
    "E": "Equity",
    "W": "Parentage",
    "P": "Probate",
    "R": "Protection from Abuse",
    "X": "Proxy Guardianship",
    "S": "Wills for Safekeeping",
}

CASE_TYPE_CODES_BY_DEPARTMENT = {
    "District Court": DISTRICT_COURT_CASE_TYPE_CODES,
    "Boston Municipal Court": BMC_CASE_TYPE_CODES,
    "Housing Court": HOUSING_COURT_CASE_TYPE_CODES,
    "Superior Court": SUPERIOR_COURT_CASE_TYPE_CODES,
    "Land Court": LAND_COURT_CASE_TYPE_CODES,
    "Probate and Family Court": PROBATE_FAMILY_COURT_CASE_TYPE_CODES,
}

APPELLATE_DEPARTMENTS = frozenset({"appeals court", "supreme judicial court"})

# Supreme Judicial Court docket prefixes and their Tyler court codes. The
# catalog's "sjc" ("Supreme Judicial Court - Commonwealth") has e-filing
# turned off in production.
SJC_TYLER_CODES = {
    "SJC": "sjc:commfc",  # "Supreme Judicial Court - Full Court"
    "SJ": "sjc:singlej",  # "Supreme Judicial Court - Suffolk - Single Justice"
    "BD": "sjc:suffolk",  # "Supreme Judicial Court - Suffolk - Bar Docket"
}

# Land Court: "07 TL 001026", or for Subsequent cases "15 SBQ 00025 09 - 001".
_LAND_COURT_RE = re.compile(
    r"^\d{2}[\s-]*(%s)(?=[\s-]*\d)"
    % "|".join(sorted(LAND_COURT_CASE_TYPE_CODES, key=len, reverse=True)),
    re.I,
)
# Appeals Court: "2020-P-0874" (panel) or "2020-J-0123" (single justice).
_APPEALS_COURT_RE = re.compile(r"^\d{4}\s*-\s*([PJ])\s*-\s*\d+$", re.I)
# Supreme Judicial Court: "SJC-13103", "SJ-2020-0123", or "BD-2020-0123".
_SJC_RE = re.compile(r"^(SJC|SJ|BD)\s*-\s*\d", re.I)
# Juvenile Court: "26YO0010NE" (year, case type, sequence, session code). No
# official format is published; this is the shape of every number on the
# Juvenile Court's public daily lists.
_JUVENILE_COURT_RE = re.compile(r"^\d{2}[A-Z]{2}\d{4}([A-Z]{2})$", re.I)
_PROBATE_CASE_GROUP_RE = re.compile(r"^[A-Z]{2}\d{2}([A-Z])\d", re.I)

_FIND_COURT_CODE_RE = re.compile(
    r"(?<=^\d{2})(\d{2}|H\d{2})(?!-)|^[A-Z]{2}(?=\d{2})", re.I
)
_FIND_CASE_TYPE_CODE_RE = re.compile(r"(?<!^)[A-Z]{2,4}(?!-)", re.I)
_ANY_NUMBERS_RE = re.compile(r"\d")
_FIND_YEAR_RE = re.compile(
    r"^\d{2}(?=\d{2}[A-Z]|H|\s|[A-Z]{2}\d{4}[A-Z]{2}$)|(?<=^[A-Z]{2})\d{2}|\d{4}(?=-)|\d{2}(?=-)", re.I
)
_FIND_SEQUENCE_NUMBER_RE = re.compile(r"\d{2,}(?=$|[A-Z]+$)", re.I)


@dataclass(frozen=True)
class DocketCourt:
    """The fields shared by every court session a docket number matches.

    A field is ``None`` when the matching sessions disagree on it, e.g. the
    name of an ``H84`` (Eastern Housing Court) docket, which may be heard in
    Boston, Chelsea, or Middlesex.
    """

    name: str | None
    department: str | None
    court_code: str | None
    tyler_code: str | None
    description: str | None


@dataclass(frozen=True)
class TylerCourt:
    """A Tyler EFSP court location: the code to file with, Tyler's name for it,
    and whether it accepts initial (new case) and subsequent filings.

    ``name`` is ``None``, and both flags ``False``, when the environment's court
    list doesn't include the code; staging lacks many courts that production
    has. A listed court can still have e-filing turned off.
    """

    code: str
    name: str | None
    initial: bool = False
    subsequent: bool = False

    @property
    def accepts_efiling(self) -> bool:
        return self.initial or self.subsequent


@dataclass(frozen=True)
class DocketCourtIdentification:
    """Which department, and which court locations, a docket number belongs to.

    ``department`` is always set: one of the seven Trial Court departments,
    "Appeals Court", or "Supreme Judicial Court". ``court_code`` is the code as
    written in the docket number (``77``, ``H84``, ``ES``, the Juvenile session
    code ``NE``, or the Appeals Court's ``P``/``J``), or ``None`` when the format
    has none (Land Court, Supreme Judicial Court). ``name`` is the court name
    shared by every location, or ``None`` when they differ (``H84`` covers
    Eastern Housing Court and its Chelsea and Middlesex sessions).

    ``locations`` is empty only for a Juvenile Court session code that
    doesn't match any session. ``tyler_courts`` are the Tyler EFSP court
    locations to file with, in the parser's Tyler environment.
    """

    department: str
    court_code: str | None
    name: str | None
    locations: tuple[CourtRecord, ...]
    tyler_courts: tuple[TylerCourt, ...] = ()

    @property
    def existing_case_courts(self) -> tuple[TylerCourt, ...]:
        """The Tyler courts the existing case with this docket number could be
        filed into: every candidate that accepts subsequent filings.

        Usually one. A Southeast Housing Court (``H83``) number gives all five
        sessions, since each has its own Tyler code.
        """
        return tuple(court for court in self.tyler_courts if court.subsequent)


def _probate_site_codes() -> dict[str, str]:
    """Map current Probate docket site prefixes (``ES``) to legacy codes (``P77``)."""
    crosswalk = load_data("court_code_crosswalk.json")
    legacy_to_current = crosswalk["departments"]["Probate and Family Court"][
        "legacy_to_current"
    ]
    return {current: legacy for legacy, current in legacy_to_current.items()}


def _juvenile_session_exceptions() -> dict[str, str]:
    """Juvenile docket session codes that aren't their Tyler code's suffix."""
    crosswalk = load_data("court_code_crosswalk.json")
    sessions = crosswalk["departments"]["Juvenile Court"]["docket_session_codes"]
    return dict(sessions["differs_from_tyler_code"])


def _tyler_key(code: str) -> str:
    """Compare Tyler codes across environments: staging writes ``0705:LA``, prod ``705:LA``."""
    prefix, colon, suffix = code.partition(":")
    if colon and prefix.isdigit():
        return f"{int(prefix)}:{suffix}".casefold()
    return code.casefold()


def _historical_records() -> tuple[CourtRecord, ...]:
    return tuple(
        CourtRecord.from_legacy(item, item["department"])
        for item in load_data("historical_courts.json")
    )


class DocketNumberParser:
    """Identify the court and case type a Massachusetts docket number belongs to.

    ``historical`` holds retired courts (e.g. Winchendon District Court, code
    ``70``) whose codes still appear on older docket numbers; they are only
    consulted when no current court has the code.

    ``tyler_environment`` ("prod" or "test") picks which Tyler EFSP court list
    names the courts and supplies the codes in that environment's spelling.
    ``tyler_courts`` overrides the packaged snapshot with ``{environment:
    {code: {"name": ..., "initial": bool, "subsequent": bool}}}``.
    """

    def __init__(
        self,
        catalog: CourtCatalog | None = None,
        historical: Iterable[CourtRecord] | None = None,
        probate_site_codes: dict[str, str] | None = None,
        tyler_environment: str = "prod",
        tyler_courts: Mapping[str, Mapping[str, Mapping[str, object]]] | None = None,
        juvenile_session_exceptions: Mapping[str, str] | None = None,
    ) -> None:
        self.catalog = catalog if catalog is not None else CourtCatalog.from_package_data()
        self.historical = tuple(
            historical if historical is not None else _historical_records()
        )
        self.probate_site_codes = (
            probate_site_codes if probate_site_codes is not None else _probate_site_codes()
        )
        if tyler_courts is None:
            tyler_courts = load_data("tyler_courts.json")["environments"]
        if tyler_environment not in tyler_courts:
            raise ValueError(
                f"Unknown Tyler environment {tyler_environment!r}; expected one of {sorted(tyler_courts)}"
            )
        self.tyler_environment = tyler_environment
        self._tyler_courts = {
            _tyler_key(code): TylerCourt(
                code,
                str(court["name"]),
                bool(court.get("initial")),
                bool(court.get("subsequent")),
            )
            for code, court in tyler_courts[tyler_environment].items()
        }
        # Tyler's names for every environment, to place a Juvenile session.
        self._tyler_names = {
            _tyler_key(code): str(court["name"])
            for environment in tyler_courts.values()
            for code, court in environment.items()
        }
        self.juvenile_session_exceptions = dict(
            juvenile_session_exceptions
            if juvenile_session_exceptions is not None
            else _juvenile_session_exceptions()
        )

    def _filing_tyler_code(self, record: CourtRecord) -> str | None:
        """A location's Tyler code, or its filing location's when it has none
        (the Stoughton sessions file through Canton and Dedham)."""
        if record.tyler_code:
            return record.tyler_code
        filing_location = self.catalog.filing_location_for(record)
        return filing_location.tyler_code if filing_location else None

    def tyler_court(self, tyler_code: str) -> TylerCourt:
        """Tyler's code spelling and name for a court in this parser's environment."""
        return self._tyler_courts.get(_tyler_key(tyler_code), TylerCourt(tyler_code, None))

    def _juvenile_locations(self, session_code: str) -> tuple[CourtRecord, ...]:
        """The Juvenile Court session(s) a docket session code (``NE``) refers to."""
        juvenile = self._department_records("Juvenile Court")
        exception = self.juvenile_session_exceptions.get(session_code)
        if exception:
            return tuple(record for record in juvenile if norm(record.name) == norm(exception))
        matching = tuple(
            record
            for record in juvenile
            if record.tyler_code
            and norm(record.tyler_code.partition(":")[2]) == norm(session_code)
        )
        if len(matching) <= 1:
            return matching
        # Several sessions file under one Tyler code (Palmer and Springfield
        # under 986:SP); the code's own session is the one Tyler names
        # ("Juvenile Court -- Hampden County -- Springfield").
        tyler_name = self._tyler_names.get(_tyler_key(matching[0].tyler_code or ""), "")
        place = tyler_name.rpartition("--")[2].strip()
        named = tuple(
            record for record in matching if place and norm(record.name).startswith(norm(place))
        )
        return named or matching

    def _department_records(self, department: str) -> tuple[CourtRecord, ...]:
        return tuple(
            record
            for record in self.catalog.records
            if norm(record.department) == norm(department)
        )

    def identify_court(self, docket_number: str) -> DocketCourtIdentification:
        """The department and court locations a docket number belongs to.

        Raises ``KeyError`` when the docket number doesn't identify a court.
        """
        docket_number = docket_number.strip()
        search = _FIND_COURT_CODE_RE.search(docket_number)
        if search:
            court_code = search.group().upper()
            search_court_code = self.probate_site_codes.get(court_code, court_code)
            matching = self.catalog.resolve_court_code(search_court_code) or tuple(
                record
                for record in self.historical
                if record.matches_court_code(search_court_code)
            )
            if not matching:
                raise KeyError(
                    f"{court_code} (i.e. {search_court_code}) (from {docket_number}) isn't a valid court code"
                )
            return self._identification(matching[0].department, court_code, matching)

        juvenile = _JUVENILE_COURT_RE.search(docket_number)
        if juvenile:
            session_code = juvenile.group(1).upper()
            return self._identification(
                "Juvenile Court", session_code, self._juvenile_locations(session_code)
            )
        # Land Court docket numbers have no court code, just year + case type.
        if _LAND_COURT_RE.search(docket_number):
            return self._identification(
                "Land Court", None, self._department_records("Land Court")
            )
        if not _ANY_NUMBERS_RE.search(docket_number):
            raise KeyError(
                f"{docket_number} doesn't have any number digits in it, it's not likely a docket number"
            )
        sjc = _SJC_RE.search(docket_number)
        if sjc:
            tyler_code = SJC_TYLER_CODES.get(sjc.group(1).upper())
            return self._identification(
                "Supreme Judicial Court",
                None,
                self._department_records("Supreme Judicial Court"),
                tyler_codes=(tyler_code,) if tyler_code else None,
            )
        appeals = _APPEALS_COURT_RE.search(docket_number)
        if appeals:
            court_code = appeals.group(1).upper()
            matching = tuple(
                record
                for record in self._department_records("Appeals Court")
                if record.matches_court_code(court_code)
            )
            if matching:
                return self._identification("Appeals Court", court_code, matching)
        raise KeyError(
            f"{docket_number} doesn't have a court code, and isn't an appellate case, might be a variant"
        )

    def _identification(
        self,
        department: str,
        court_code: str | None,
        locations: tuple[CourtRecord, ...],
        tyler_codes: Iterable[str] | None = None,
    ) -> DocketCourtIdentification:
        names = {record.name for record in locations}
        if tyler_codes is None:
            tyler_codes = (
                code for record in locations if (code := self._filing_tyler_code(record))
            )
        return DocketCourtIdentification(
            department=department,
            court_code=court_code,
            name=names.pop() if len(names) == 1 else None,
            locations=locations,
            tyler_courts=tuple(
                self.tyler_court(code) for code in dict.fromkeys(tyler_codes)
            ),
        )

    def courts_from_docket_number(self, docket_number: str) -> tuple[CourtRecord, ...]:
        """Every court session (physical location) a docket number could belong to.

        Raises ``KeyError`` when the docket number doesn't identify a court
        location, including a Juvenile Court number with an unknown session
        code; :meth:`identify_court` still gives its department.
        """
        identification = self.identify_court(docket_number)
        if not identification.locations:
            raise KeyError(
                f"{docket_number} is a {identification.department} number, but its "
                f"session code {identification.court_code} isn't mapped to a location"
            )
        return identification.locations

    def court_from_docket_number(self, docket_number: str) -> DocketCourt | None:
        """Only the information that is the same across every matching court session."""
        matching = self.courts_from_docket_number(docket_number)

        def shared(values: Iterable[str | None]) -> str | None:
            distinct = set(values)
            return distinct.pop() if len(distinct) == 1 else None

        court = DocketCourt(
            name=shared(record.name for record in matching),
            department=shared(record.department for record in matching),
            court_code=shared(record.court_code for record in matching),
            tyler_code=shared(record.tyler_code for record in matching),
            description=shared(record.raw.get("description") for record in matching),
        )
        if court.name is None and court.court_code is None and court.description is None:
            return None
        return court

    def case_type_from_docket_number(self, docket_number: str) -> str | None:
        """The case type (e.g. "Civil"), "Appellate" for appellate dockets, or ``None``.

        Raises ``KeyError`` when the docket number has a case-type code that
        doesn't exist in the matching court's department.
        """
        court = self.court_from_docket_number(docket_number)
        if not court:
            return None
        if norm(court.department) in APPELLATE_DEPARTMENTS:
            # Without the lower court's docket number we can't tell what kind
            # of case is on appeal. "AD" (Appeal) is a trial court code.
            return "Appellate"
        search = _FIND_CASE_TYPE_CODE_RE.search(docket_number)
        if not search:
            return None
        case_type_code = search.group().upper()
        codes = CASE_TYPE_CODES_BY_DEPARTMENT.get(court.department or "", {})
        if case_type_code not in codes:
            raise KeyError(
                f"{case_type_code} (from {docket_number}) isn't a valid case type code for {court.department}"
            )
        return codes[case_type_code]

    def case_group_from_docket_number(self, docket_number: str) -> str | None:
        """The Probate and Family Court case group (the "A" in ``ES15A0064AD``).

        ``None`` for every other department, whose docket numbers have none.
        """
        court = self.court_from_docket_number(docket_number)
        if not court or norm(court.department) != norm("Probate and Family Court"):
            return None
        search = _PROBATE_CASE_GROUP_RE.search(docket_number)
        if not search:
            return None
        case_group_code = search.group(1).upper()
        if case_group_code not in PROBATE_FAMILY_COURT_CASE_GROUP_CODES:
            raise KeyError(
                f"{case_group_code} (from {docket_number}) isn't a valid Probate and Family Court case group"
            )
        return PROBATE_FAMILY_COURT_CASE_GROUP_CODES[case_group_code]


@lru_cache(maxsize=1)
def _default_parser() -> DocketNumberParser:
    return DocketNumberParser()


def identify_court_from_docket_number(docket_number: str) -> DocketCourtIdentification:
    """:meth:`DocketNumberParser.identify_court` using the packaged court data."""
    return _default_parser().identify_court(docket_number)


def get_year_from_docket_number(
    docket_number: str, today: date | None = None
) -> str | None:
    """The four-digit filing year, or ``None`` if the docket number has none.

    Every docket number except Supreme Judicial Court panel numbers includes
    the year. Raises ``ValueError`` for a year after ``today``: no such case
    can have been filed yet.
    """
    search = _FIND_YEAR_RE.search(docket_number)
    if not search:
        return None
    case_year = search.group()
    current_year = str((today or date.today()).year)
    if case_year[-2:] > current_year[-2:]:
        raise ValueError(f"docket number has a year in the future: {case_year}")
    if len(case_year) == 4:
        return case_year
    return current_year[:2] + case_year


def get_sequence_number_from_docket_number(docket_number: str) -> str | None:
    search = _FIND_SEQUENCE_NUMBER_RE.search(docket_number)
    return search.group() if search else None
