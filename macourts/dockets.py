"""Massachusetts docket-number parsing (the "smart docket" tool).

Ported from ``MACourtList`` in docassemble-MACourts. A docket number like
``1577CV00982`` encodes the filing year (``15``), the court (``77``, Essex
County Superior Court), the case type (``CV``, Civil), and a sequence number
(``00982``). The formats differ by department; see the sources listed in
``court_code_crosswalk.json``.

The Juvenile Court publishes no format. Its docket numbers (e.g.
``26YO0010NE``: year, case type, sequence, session) end in a session code that
usually matches the suffix of the session's Tyler code (``1015:NE``).

Parsing tolerates the variations people write (any case, spaces, dashes, and
missing leading zeros), and :func:`docket_number_variants` gives the exact
spellings to try in a Tyler case search, which matches only the stored form.

Each identification also carries the Tyler EFSP court codes and names for its
locations, from the ``tyler_courts.json`` snapshot of the EFSP proxy's court
list (refreshed by ``scripts/fetch_tyler_courts.py``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from datetime import date
from types import MappingProxyType
from typing import Iterable, Mapping

from .catalog import CourtCatalog, load_data
from .models import DASH_CHARS, CourtRecord, norm

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

# Supreme Judicial Court docket prefixes and their Tyler court codes. The
# catalog's "sjc" ("Supreme Judicial Court - Commonwealth") has e-filing
# turned off in production.
SJC_TYLER_CODES = {
    "SJC": "sjc:commfc",  # "Supreme Judicial Court - Full Court"
    "SJ": "sjc:singlej",  # "Supreme Judicial Court - Suffolk - Single Justice"
    "BD": "sjc:suffolk",  # "Supreme Judicial Court - Suffolk - Bar Docket"
}

# Every format below was checked against mass.gov's case number format pages
# and against docket numbers in the Tyler EFSP. Tyler's docket search matches
# only the exact stored spelling: upper case, zero-padded, and with any "-EF"
# suffix (seen on e-filed District Court cases, e.g. "2362SC002985-EF").
_DASHES = str.maketrans(dict.fromkeys(DASH_CHARS, "-"))
_EF_SUFFIX_RE = re.compile(r"(?<=\d)[\s\-_./]*EF$")
_NON_ALPHANUMERIC_RE = re.compile(r"[^A-Z0-9]")

# Formats, matched against the docket number with punctuation removed.
# District Court, BMC, and Superior Court: "1448CV001026", "1473CV00213".
_TRIAL_COURT_RE = re.compile(r"(\d{2})(\d{2})([A-Z]{2})(\d{1,6})")
# Housing Court: "15H84CV000436".
_HOUSING_COURT_RE = re.compile(r"(\d{2})(H\d{2})([A-Z]{2})(\d{1,6})")
# Probate and Family Court: "ES15A0064AD".
_PROBATE_COURT_RE = re.compile(r"([A-Z]{2})(\d{2})([A-Z])(\d{1,4})([A-Z]{2})")
# Older Probate and Family Court numbers still in Tyler: "ES94D2029DV1",
# "ES86D0383D1", and the yearless "ES43951".
_LEGACY_PROBATE_COURT_RE = re.compile(r"([A-Z]{2})(\d{2})([A-Z])(\d{4})([A-Z]{1,2})(\d)")
_YEARLESS_PROBATE_COURT_RE = re.compile(r"([A-Z]{2})(\d{4,6})")
# Juvenile Court: "26YO0010NE" (year, case type, sequence, session code). No
# official format is published; this is the shape of every number on the
# Juvenile Court's public daily lists.
_JUVENILE_COURT_RE = re.compile(r"(\d{2})([A-Z]{2})(\d{1,4})([A-Z]{2})")
# Land Court: "07 TL 001026".
_LAND_COURT_RE = re.compile(
    r"(\d{2})(%s)(\d{1,6})"
    % "|".join(sorted(LAND_COURT_CASE_TYPE_CODES, key=len, reverse=True))
)
# Appeals Court: "2020-P-0874" (panel) or "2020-J-0123" (single justice).
_APPEALS_COURT_RE = re.compile(r"(\d{4}|\d{2})([PJ])(\d{1,4})")
# Supreme Judicial Court: "SJC-05546" (full court), "SJ-2021-0189" (single
# justice), "BD-2020-0123" (bar docket).
_SJC_FULL_COURT_RE = re.compile(r"SJC(\d{1,5})")
_SJC_COUNTY_RE = re.compile(r"(SJ|BD)(\d{4})(\d{4})")

# Matched against the punctuated docket number, where the separators matter.
# Land Court Subsequent: "06 SBQ 27811 11 - 001" (year, plan number, month,
# sequence number).
_LAND_COURT_SUBSEQUENT_RE = re.compile(r"(\d{2})\s*SBQ\s*(\d{1,5})\s+(\d{1,2})\s*-?\s*(\d{1,3})")
_SJC_COUNTY_SPACED_RE = re.compile(r"(SJ|BD)\s*-?\s*(\d{4}|\d{2})\s*-\s*(\d{1,4})")

# Docket numbers that don't fit any format, for the year and sequence number.
_FIND_YEAR_RE = re.compile(r"^\d{4}(?=-)|^\d{2}(?=\d{2}[A-Z]|H|\s|-)|(?<=^[A-Z]{2})\d{2}", re.I)
_FIND_SEQUENCE_NUMBER_RE = re.compile(r"\d{2,}(?=$|[A-Z]+$)", re.I)


@lru_cache(maxsize=1)
def _crosswalk() -> Mapping[str, object]:
    return load_data("court_code_crosswalk.json")


@lru_cache(maxsize=1)
def _superior_court_codes() -> frozenset[str]:
    return frozenset(_crosswalk()["departments"]["Superior Court"]["codes"].values())


@lru_cache(maxsize=1)
def _probate_site_codes() -> Mapping[str, str]:
    """Map current Probate docket site prefixes (``ES``) to legacy codes (``P77``)."""
    legacy_to_current = _crosswalk()["departments"]["Probate and Family Court"][
        "legacy_to_current"
    ]
    return MappingProxyType({current: legacy for legacy, current in legacy_to_current.items()})


@lru_cache(maxsize=1)
def _juvenile_session_exceptions() -> Mapping[str, str]:
    """Juvenile docket session codes that aren't their Tyler code's suffix."""
    sessions = _crosswalk()["departments"]["Juvenile Court"]["docket_session_codes"]
    return MappingProxyType(dict(sessions["differs_from_tyler_code"]))


@lru_cache(maxsize=1)
def _tyler_courts_snapshot() -> Mapping[str, Mapping[str, Mapping[str, object]]]:
    return load_data("tyler_courts.json")["environments"]


def _clean(docket_number: str) -> str:
    return docket_number.translate(_DASHES).strip().upper()


def _shared(values: Iterable[str | None]) -> str | None:
    """The value every item has, or ``None`` when they differ."""
    distinct = set(values)
    return distinct.pop() if len(distinct) == 1 else None


def _pad(number: str, width: int) -> str:
    """Zero-pad a sequence number to its format's width, dropping extra zeros."""
    return number.lstrip("0").zfill(width)


def _full_year(year: str, today: date | None = None) -> str:
    """Expand a two-digit year: no later than this year, so ``99`` is 1999."""
    if len(year) == 4:
        return year
    current_year = (today or date.today()).year
    century = current_year // 100 * 100
    full = century + int(year)
    return str(full if full <= current_year else full - 100)


@dataclass(frozen=True)
class ParsedDocketNumber:
    """A docket number split into its parts, with its canonical spelling.

    ``format`` is one of "trial" (District Court, BMC, or Superior Court),
    "housing", "probate", "legacy_probate", "juvenile", "land",
    "land_subsequent", "appeals", or "sjc". ``court_code`` is the court, site,
    or session code (``77``, ``H84``, ``ES``, ``NE``), the Appeals Court's
    ``P``/``J``, or the SJC's ``SJC``/``SJ``/``BD``. ``year`` is as written:
    two digits, or four for the Appeals Court and SJC.

    ``normalized`` is the spelling the courts and Tyler use, e.g.
    ``2356SP012345`` for a handwritten ``23-56SP-12345``.
    """

    format: str
    normalized: str
    year: str | None
    court_code: str | None
    case_type_code: str | None
    sequence: str | None
    case_group_code: str | None = None
    efiled: bool = False


def parse_docket_number(docket_number: str) -> ParsedDocketNumber | None:
    """Split a Massachusetts docket number into its parts, or ``None``.

    Tolerates the variations people write: any case, and spaces, dashes,
    slashes, or dots between the parts, and missing leading zeros in the
    sequence number. So ``23-56sp-12345`` parses to ``2356SP012345``.
    """
    text = _clean(docket_number)
    efiled = bool(_EF_SUFFIX_RE.search(text))
    if efiled:
        text = _EF_SUFFIX_RE.sub("", text)
    ef = "-EF" if efiled else ""
    compact = _NON_ALPHANUMERIC_RE.sub("", text)

    if match := _LAND_COURT_SUBSEQUENT_RE.fullmatch(text):
        year, plan, month, sequence = match.groups()
        return ParsedDocketNumber(
            "land_subsequent",
            f"{year} SBQ {_pad(plan, 5)} {month.zfill(2)} - {_pad(sequence, 3)}",
            year,
            None,
            "SBQ",
            _pad(sequence, 3),
        )
    if match := _HOUSING_COURT_RE.fullmatch(compact) or _TRIAL_COURT_RE.fullmatch(compact):
        year, court_code, case_type, sequence = match.groups()
        # The Superior Court's sequence numbers have five digits, not six.
        sequence = _pad(sequence, 5 if court_code in _superior_court_codes() else 6)
        return ParsedDocketNumber(
            "housing" if court_code.startswith("H") else "trial",
            f"{year}{court_code}{case_type}{sequence}{ef}",
            year,
            court_code,
            case_type,
            sequence,
            efiled=efiled,
        )
    if match := _LAND_COURT_RE.fullmatch(compact):
        year, case_type, sequence = match.groups()
        sequence = _pad(sequence, 6)
        return ParsedDocketNumber(
            "land", f"{year} {case_type} {sequence}", year, None, case_type, sequence
        )
    if match := _APPEALS_COURT_RE.fullmatch(compact):
        year, court_code, sequence = match.groups()
        year = _full_year(year)
        sequence = _pad(sequence, 4)
        return ParsedDocketNumber(
            "appeals", f"{year}-{court_code}-{sequence}", year, court_code, None, sequence
        )
    if match := _SJC_FULL_COURT_RE.fullmatch(compact):
        sequence = _pad(match.group(1), 5)
        return ParsedDocketNumber("sjc", f"SJC-{sequence}", None, "SJC", None, sequence)
    if match := _SJC_COUNTY_SPACED_RE.fullmatch(text) or _SJC_COUNTY_RE.fullmatch(compact):
        court_code, year, sequence = match.groups()
        year = _full_year(year)
        sequence = _pad(sequence, 4)
        return ParsedDocketNumber(
            "sjc", f"{court_code}-{year}-{sequence}", year, court_code, None, sequence
        )
    site_codes = _probate_site_codes()
    if match := _PROBATE_COURT_RE.fullmatch(compact):
        site, year, case_group, sequence, case_type = match.groups()
        if site in site_codes:
            sequence = _pad(sequence, 4)
            return ParsedDocketNumber(
                "probate",
                f"{site}{year}{case_group}{sequence}{case_type}",
                year,
                site,
                case_type,
                sequence,
                case_group_code=case_group,
            )
    if match := _LEGACY_PROBATE_COURT_RE.fullmatch(compact):
        site, year, case_group, sequence, case_type, _ = match.groups()
        if site in site_codes:
            return ParsedDocketNumber(
                "legacy_probate", compact, year, site, case_type, sequence, case_group
            )
    if match := _YEARLESS_PROBATE_COURT_RE.fullmatch(compact):
        site, sequence = match.groups()
        if site in site_codes:
            return ParsedDocketNumber("legacy_probate", compact, None, site, None, sequence)
    if match := _JUVENILE_COURT_RE.fullmatch(compact):
        year, case_type, sequence, session_code = match.groups()
        sequence = _pad(sequence, 4)
        return ParsedDocketNumber(
            "juvenile",
            f"{year}{case_type}{sequence}{session_code}",
            year,
            session_code,
            case_type,
            sequence,
        )
    return None


def normalize_docket_number(docket_number: str) -> str | None:
    """The canonical spelling of a docket number, or ``None`` if it isn't one.

    ``normalize_docket_number("23-56sp-12345") == "2356SP012345"``.
    """
    parsed = parse_docket_number(docket_number)
    return parsed.normalized if parsed else None


def docket_number_variants(docket_number: str) -> tuple[str, ...]:
    """Spellings of a docket number to try in a Tyler case search, best first.

    Tyler only finds a case by its exact stored spelling, which people often
    don't write: the canonical form comes first, then the same number with or
    without the "-EF" suffix e-filed trial court cases carry, then the input
    as written (upper-cased) in case it's a format this module doesn't know.
    """
    written = re.sub(r"\s+", " ", _clean(docket_number))
    parsed = parse_docket_number(docket_number)
    variants = []
    if parsed:
        variants.append(parsed.normalized)
        if parsed.format in ("trial", "housing"):
            if parsed.efiled:
                variants.append(parsed.normalized.removesuffix("-EF"))
            else:
                variants.append(parsed.normalized + "-EF")
    if written:
        variants.append(written)
    return tuple(dict.fromkeys(variants))


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


def _tyler_key(code: str) -> str:
    """Compare Tyler codes across environments: staging writes ``0705:LA``, prod ``705:LA``."""
    prefix, colon, suffix = code.partition(":")
    if colon and prefix.isdigit():
        return f"{int(prefix)}:{suffix}".casefold()
    return code.casefold()


@lru_cache(maxsize=1)
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
        tyler_environment: str = "prod",
        tyler_courts: Mapping[str, Mapping[str, Mapping[str, object]]] | None = None,
    ) -> None:
        self.catalog = catalog if catalog is not None else CourtCatalog.from_package_data()
        by_department: dict[str, list[CourtRecord]] = {}
        for record in self.catalog.records:
            by_department.setdefault(norm(record.department), []).append(record)
        self._by_department = {key: tuple(value) for key, value in by_department.items()}
        self.historical = tuple(
            historical if historical is not None else _historical_records()
        )
        self._historical_catalog = CourtCatalog(self.historical)
        self.probate_site_codes = _probate_site_codes()
        if tyler_courts is None:
            tyler_courts = _tyler_courts_snapshot()
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
        # Tyler's names, to place a Juvenile session: this environment's
        # first, then any other's for courts this one doesn't list.
        self._tyler_names = {
            _tyler_key(code): str(court["name"])
            for environment in sorted(tyler_courts, key=lambda env: env == tyler_environment)
            for code, court in tyler_courts[environment].items()
        }

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
        exception = _juvenile_session_exceptions().get(session_code)
        if exception:
            return self.catalog.resolve(exception, "Juvenile Court")
        juvenile = self._department_records("Juvenile Court")
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
        return self._by_department.get(norm(department), ())

    def identify_court(self, docket_number: str) -> DocketCourtIdentification:
        """The department and court locations a docket number belongs to.

        Tolerates the variations :func:`parse_docket_number` does. Raises
        ``KeyError`` when the docket number doesn't identify a court.
        """
        return self._identify(self._parse(docket_number), docket_number)

    @staticmethod
    def _parse(docket_number: str) -> ParsedDocketNumber:
        parsed = parse_docket_number(docket_number)
        if parsed is None:
            raise KeyError(f"{docket_number!r} isn't a recognized docket number format")
        return parsed

    def _identify(
        self, parsed: ParsedDocketNumber, docket_number: str
    ) -> DocketCourtIdentification:
        if parsed.format in ("trial", "housing", "probate", "legacy_probate"):
            search_court_code = self.probate_site_codes.get(parsed.court_code, parsed.court_code)
            matching = self.catalog.resolve_court_code(
                search_court_code
            ) or self._historical_catalog.resolve_court_code(search_court_code)
            if not matching:
                raise KeyError(
                    f"{parsed.court_code} (i.e. {search_court_code}) (from {docket_number}) isn't a valid court code"
                )
            return self._identification(matching[0].department, parsed.court_code, matching)
        if parsed.format == "juvenile":
            return self._identification(
                "Juvenile Court", parsed.court_code, self._juvenile_locations(parsed.court_code)
            )
        if parsed.format in ("land", "land_subsequent"):
            # Land Court docket numbers have no court code, just year + case type.
            return self._identification(
                "Land Court", None, self._department_records("Land Court")
            )
        if parsed.format == "sjc":
            return self._identification(
                "Supreme Judicial Court",
                None,
                self._department_records("Supreme Judicial Court"),
                tyler_codes=(SJC_TYLER_CODES[parsed.court_code],),
            )
        matching = tuple(
            record
            for record in self._department_records("Appeals Court")
            if record.matches_court_code(parsed.court_code)
        )
        if not matching:
            raise KeyError(f"{docket_number!r} has no matching Appeals Court record")
        return self._identification("Appeals Court", parsed.court_code, matching)

    def _identification(
        self,
        department: str,
        court_code: str | None,
        locations: tuple[CourtRecord, ...],
        tyler_codes: Iterable[str] | None = None,
    ) -> DocketCourtIdentification:
        if tyler_codes is None:
            tyler_codes = (
                code for record in locations if (code := self._filing_tyler_code(record))
            )
        return DocketCourtIdentification(
            department=department,
            court_code=court_code,
            name=_shared(record.name for record in locations),
            locations=locations,
            tyler_courts=tuple(
                self.tyler_court(code) for code in dict.fromkeys(tyler_codes)
            ),
        )

    @staticmethod
    def _locations(
        identification: DocketCourtIdentification, docket_number: str
    ) -> tuple[CourtRecord, ...]:
        if not identification.locations:
            raise KeyError(
                f"{docket_number} is a {identification.department} number, but its "
                f"session code {identification.court_code} isn't mapped to a location"
            )
        return identification.locations

    def courts_from_docket_number(self, docket_number: str) -> tuple[CourtRecord, ...]:
        """Every court session (physical location) a docket number could belong to.

        Raises ``KeyError`` when the docket number doesn't identify a court
        location, including a Juvenile Court number with an unknown session
        code; :meth:`identify_court` still gives its department.
        """
        return self._locations(self.identify_court(docket_number), docket_number)

    def court_from_docket_number(self, docket_number: str) -> DocketCourt | None:
        """Only the information that is the same across every matching court session."""
        identification = self.identify_court(docket_number)
        matching = self._locations(identification, docket_number)
        tyler_courts = identification.tyler_courts
        court = DocketCourt(
            name=identification.name,
            department=identification.department,
            court_code=_shared(record.court_code for record in matching),
            tyler_code=tyler_courts[0].code if len(tyler_courts) == 1 else None,
            description=_shared(record.raw.get("description") for record in matching),
        )
        if court.name is None and court.court_code is None and court.description is None:
            return None
        return court

    def case_type_from_docket_number(self, docket_number: str) -> str | None:
        """The case type (e.g. "Civil"), "Appellate" for appellate dockets, or ``None``.

        ``None`` too for the Juvenile Court, which publishes no case-type codes,
        and for older Probate and Family Court numbers whose codes are no longer
        listed. Raises ``KeyError`` when a current-format docket number has a
        case-type code that doesn't exist in its department.
        """
        parsed = self._parse(docket_number)
        department = self._identify(parsed, docket_number).department
        if parsed.format in ("appeals", "sjc"):
            # Without the lower court's docket number we can't tell what kind
            # of case is on appeal. "AD" (Appeal) is a trial court code.
            return "Appellate"
        codes = CASE_TYPE_CODES_BY_DEPARTMENT.get(department)
        if not parsed.case_type_code or codes is None:
            return None
        if parsed.case_type_code in codes:
            return codes[parsed.case_type_code]
        if parsed.format == "legacy_probate":
            return None
        raise KeyError(
            f"{parsed.case_type_code} (from {docket_number}) isn't a valid case type code for {department}"
        )

    def case_group_from_docket_number(self, docket_number: str) -> str | None:
        """The Probate and Family Court case group (the "A" in ``ES15A0064AD``).

        ``None`` for every other department, whose docket numbers have none.
        """
        parsed = self._parse(docket_number)
        self._identify(parsed, docket_number)
        if not parsed.case_group_code:
            return None
        if parsed.case_group_code not in PROBATE_FAMILY_COURT_CASE_GROUP_CODES:
            raise KeyError(
                f"{parsed.case_group_code} (from {docket_number}) isn't a valid Probate and Family Court case group"
            )
        return PROBATE_FAMILY_COURT_CASE_GROUP_CODES[parsed.case_group_code]


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

    Every docket number except Supreme Judicial Court full court numbers
    includes the year. A two-digit year is the latest one not after ``today``
    (``99`` is 1999). Raises ``ValueError`` for a four-digit year after
    ``today``: no such case can have been filed yet.
    """
    parsed = parse_docket_number(docket_number)
    if parsed:
        year = parsed.year
    else:
        search = _FIND_YEAR_RE.search(docket_number.strip())
        year = search.group() if search else None
    if not year:
        return None
    if len(year) == 4 and int(year) > (today or date.today()).year:
        raise ValueError(f"docket number has a year in the future: {year}")
    return _full_year(year, today)


def get_sequence_number_from_docket_number(docket_number: str) -> str | None:
    parsed = parse_docket_number(docket_number)
    if parsed:
        return parsed.sequence
    search = _FIND_SEQUENCE_NUMBER_RE.search(docket_number)
    return search.group() if search else None
