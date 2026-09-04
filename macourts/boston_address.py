"""Deterministic Boston street-address lookup, backed by a compiled SQLite index.

Boston addresses inside the BMC's territory can be resolved to a division
without geocoding, because the City's Street Address Management (SAM) system
already knows every valid address and its ward. ``scripts/build_bmc_address_index.py``
spatially assigns every SAM address to a BMC division (using the same polygons
and division names as :mod:`macourts.boston`) and compiles the result into
``macourts/data/bmc_addresses.sqlite``. This module only ever reads that file.

Everything here is deliberately boring: normalization is a fixed set of string
rules, and resolution is an exact-match SQL lookup. There is no fuzzy matching,
no nearest-street fallback, and no house-number interpolation. An address this
module doesn't recognize comes back ``not_found`` rather than a guess.
"""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from contextlib import ExitStack
from dataclasses import dataclass
from importlib.resources import as_file
from pathlib import Path
from typing import Any

from .catalog import package_data

DB_FILENAME = "bmc_addresses.sqlite"

_DASH_CHARS = "‐‑‒–—―−"
_APOSTROPHE_CHARS = "‘’ʼ`´"

_UNIT_KEYWORD_RE = re.compile(
    r"\s+(?:APT|APARTMENT|UNIT|STE|SUITE|FL|FLOOR|RM|ROOM|BLDG|BUILDING|NO)\b.*$"
)
_HASH_UNIT_RE = re.compile(r"\s*#.*$")
_WHITESPACE_RE = re.compile(r"\s+")

_NUMBER_RE = re.compile(
    r"""^
    (?P<number>
        \d+(?:-\d+)?
        [A-Z]?
        (?:\s+\d+/\d+)?
    )
    \s+
    (?P<street>.+)
    $""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class ParsedStreetAddress:
    """The house number and street name, normalized for exact-match lookup."""

    number_key: str
    street_key: str


@dataclass(frozen=True)
class AddressResolution:
    """The outcome of resolving one street address against the compiled index."""

    court_name: str | None
    match_kind: str
    normalized_number: str | None
    normalized_street: str | None
    data_version: str | None
    #: Only meaningful when match_kind is "success". True when some SAM point
    #: at this address was strictly inside its division's ward polygon; False
    #: when every one needed the compiler's nearest-boundary fallback (see
    #: docs/bmc_address_index.md) -- a safe answer since BMC divisions have
    #: concurrent, not exclusive, jurisdiction across Boston, but worth a
    #: caller being able to tell apart from a strict-containment match.
    exact: bool | None = None


NOT_FOUND = "not_found"
SUCCESS = "success"
AMBIGUOUS = "ambiguous"
ZIP_MISMATCH = "zip_mismatch"


def normalize_street_text(value: str) -> str:
    """Apply the fixed character-normalization rules used on both sides of the index.

    ``parse_street_address`` uses this on the street portion of user input, and
    ``build_bmc_address_index.py`` uses it on SAM's ``FULL_STREET_NAME`` and its
    generated spelling variants, so a street name normalizes identically however
    it got here. This step never removes a unit suffix or a house number.
    """
    text = unicodedata.normalize("NFKC", value).upper()
    for ch in _APOSTROPHE_CHARS:
        text = text.replace(ch, "'")
    for ch in _DASH_CHARS:
        text = text.replace(ch, "-")
    text = text.replace(".", "")
    return _WHITESPACE_RE.sub(" ", text).strip()


def parse_street_address(value: str) -> ParsedStreetAddress | None:
    """Parse a house number and street name out of a free-text street address.

    This never does fuzzy matching: it only extracts and normalizes the number
    and street text so they can be looked up by exact string equality against
    the compiled index's spelling variants. Unrecognized shapes return ``None``.
    """
    if not value or not value.strip():
        return None

    # Anything after the first comma is unit/city/state, not the street.
    text = value.split(",", 1)[0]
    text = normalize_street_text(text)
    text = _UNIT_KEYWORD_RE.sub("", text)
    text = _HASH_UNIT_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return None

    match = _NUMBER_RE.match(text)
    if not match:
        return None

    number_key = _WHITESPACE_RE.sub(" ", match.group("number")).strip()
    street_key = _WHITESPACE_RE.sub(" ", match.group("street")).strip()
    if not number_key or not street_key:
        return None
    return ParsedStreetAddress(number_key=number_key, street_key=street_key)


def normalize_zip_code(value: str | None) -> str | None:
    """Reduce a ZIP to its 5-digit form, or ``None`` if it doesn't have one."""
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < 5:
        return None
    return digits[:5]


class BostonAddressIndex:
    """Exact-match street-address lookup against the compiled SQLite index.

    Opening the SQLite connection is deferred to the first call to
    :meth:`resolve`, so constructing a :class:`BostonMunicipalCourtMatcher`
    (which builds one of these from packaged data) never touches the database
    for callers who only ever match on coordinates or a city name.
    """

    def __init__(self, db_path: str | Path | Any) -> None:
        self._db_path = db_path
        self._connection: sqlite3.Connection | None = None
        self._data_version: str | None = None
        self._exit_stack: ExitStack | None = None

    @classmethod
    def from_path(cls, path: str | Path) -> "BostonAddressIndex":
        return cls(Path(path))

    @classmethod
    def from_package_data(cls) -> "BostonAddressIndex | None":
        """Build an index over the packaged database, or ``None`` if it isn't built yet.

        The database is generated data (see ``scripts/build_bmc_address_index.py``)
        and may be absent in a checkout that hasn't run the build yet; callers
        should treat ``None`` the same as "no street-address lookup available".
        """
        resource = package_data().joinpath(DB_FILENAME)
        if not resource.is_file():
            return None
        return cls(resource)

    def _connect(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        try:
            fspath = os.fspath(self._db_path)
        except TypeError:
            self._exit_stack = ExitStack()
            materialized = self._exit_stack.enter_context(as_file(self._db_path))
            fspath = os.fspath(materialized)
        connection = sqlite3.connect(f"file:{fspath}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        self._connection = connection
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'data_version'"
        ).fetchone()
        self._data_version = row[0] if row else None
        return connection

    @property
    def data_version(self) -> str | None:
        self._connect()
        return self._data_version

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying read-only SQLite connection, opened on first access."""
        return self._connect()

    def resolve(
        self,
        street_address: str,
        zip_code: str | None = None,
    ) -> AddressResolution:
        """Resolve one street address to a BMC division, or explain why not."""
        connection = self._connect()
        parsed = parse_street_address(street_address)
        if parsed is None:
            return AddressResolution(None, NOT_FOUND, None, None, self._data_version)

        street_ids = [
            row[0]
            for row in connection.execute(
                "SELECT street_id FROM street_names WHERE name_key = ?",
                (parsed.street_key,),
            )
        ]
        if not street_ids:
            return AddressResolution(
                None,
                NOT_FOUND,
                parsed.number_key,
                parsed.street_key,
                self._data_version,
            )

        placeholders = ",".join("?" for _ in street_ids)
        rows = connection.execute(
            f"""
            SELECT division_id, zip_code, exact
            FROM addresses
            WHERE street_id IN ({placeholders}) AND number_key = ?
            """,
            (*street_ids, parsed.number_key),
        ).fetchall()
        if not rows:
            return AddressResolution(
                None,
                NOT_FOUND,
                parsed.number_key,
                parsed.street_key,
                self._data_version,
            )

        # ZIP only matters when the street+number alone is ambiguous: real ZIPs
        # on third-party records (food licenses, etc.) commonly name a
        # neighboring postal ZIP rather than SAM's own, and every row already
        # agreeing on one division is a stronger signal than that ZIP is.
        divisions = {row[0] for row in rows}
        if len(divisions) > 1:
            target_zip = normalize_zip_code(zip_code)
            if target_zip:
                # zip_code is stored as an int (see build_bmc_address_index.py);
                # target_zip is always a 5-digit string, so int() is exact.
                zip_rows = [row for row in rows if row[1] == int(target_zip)]
                if not zip_rows:
                    return AddressResolution(
                        None,
                        ZIP_MISMATCH,
                        parsed.number_key,
                        parsed.street_key,
                        self._data_version,
                    )
                divisions = {row[0] for row in zip_rows}
            if len(divisions) > 1:
                return AddressResolution(
                    None,
                    AMBIGUOUS,
                    parsed.number_key,
                    parsed.street_key,
                    self._data_version,
                )

        division_id = next(iter(divisions))
        court_row = connection.execute(
            "SELECT court_name FROM divisions WHERE id = ?", (division_id,)
        ).fetchone()
        court_name = court_row[0] if court_row else None
        exact = any(row[2] for row in rows if row[0] == division_id)
        return AddressResolution(
            court_name,
            SUCCESS,
            parsed.number_key,
            parsed.street_key,
            self._data_version,
            exact=bool(exact),
        )
