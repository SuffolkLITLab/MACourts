"""Loading and indexing the packaged Massachusetts court records."""

from __future__ import annotations

import json
from collections import defaultdict
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from .models import CourtRecord, norm

LEGACY_FILES = {
    "housing_courts": "Housing Court",
    "bmc": "Boston Municipal Court",
    "district_courts": "District Court",
    "superior_courts": "Superior Court",
    "land_court": "Land Court",
    "juvenile_courts": "Juvenile Court",
    "probate_and_family_courts": "Probate and Family Court",
    "appeals_court": "Appeals Court",
    "supreme_judicial_court": "Supreme Judicial Court",
}


def package_data():
    """Return the installed package data directory as an importlib Traversable."""
    return files("macourts").joinpath("data")


def load_data(name: str):
    """Read one packaged JSON data file."""
    resource = package_data().joinpath(name)
    with resource.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


class CourtCatalog:
    def __init__(self, records: Iterable[CourtRecord] = ()) -> None:
        self.records = tuple(records)
        index: dict[tuple[str, str], list[CourtRecord]] = defaultdict(list)
        location_index: dict[tuple[str, str], list[CourtRecord]] = defaultdict(list)
        for record in self.records:
            index[(norm(record.department), norm(record.name))].append(record)
            location_index[
                (norm(record.department), norm(record.location_name))
            ].append(record)
        self._index = {key: tuple(value) for key, value in index.items()}
        self._location_index = {
            key: tuple(value) for key, value in location_index.items()
        }

    def resolve(self, name: str, department: str) -> tuple[CourtRecord, ...]:
        return self._index.get((norm(department), norm(name)), ())

    def names(self, department: str) -> tuple[str, ...]:
        """Distinct semantic court names in one department, in catalog order."""
        department_key = norm(department)
        seen = {}
        for record in self.records:
            if norm(record.department) == department_key:
                seen.setdefault(norm(record.name), record.name)
        return tuple(seen.values())

    def resolve_location(
        self,
        location_name: str,
        department: str,
    ) -> tuple[CourtRecord, ...]:
        """Resolve a physical/session location rather than a semantic court name."""
        return self._location_index.get(
            (norm(department), norm(location_name)),
            (),
        )

    def filing_location_for(self, record: CourtRecord) -> CourtRecord | None:
        """Return the record that accepts filings for an appearance/session record."""
        matches = self.resolve_location(record.filing_location_name, record.department)
        return matches[0] if matches else None

    def filing_locations(
        self,
        department: str | None = None,
    ) -> tuple[CourtRecord, ...]:
        """Return locations that accept filings according to court metadata."""
        department_key = norm(department) if department else None
        return tuple(
            record
            for record in self.records
            if record.accepts_filings
            and (
                department_key is None
                or norm(record.department) == department_key
            )
        )

    def resolve_court_code(self, court_code: str) -> tuple[CourtRecord, ...]:
        """Resolve a current or historical/alternate Trial Court docket code."""
        return tuple(
            record
            for record in self.records
            if record.matches_court_code(court_code)
        )

    @classmethod
    def from_legacy_directory(cls, directory: str | Path) -> "CourtCatalog":
        records: list[CourtRecord] = []
        root = Path(directory)
        for stem, department in LEGACY_FILES.items():
            path = root / f"{stem}.json"
            if not path.exists():
                continue
            with path.open(encoding="utf-8-sig") as handle:
                for item in json.load(handle):
                    records.append(CourtRecord.from_legacy(item, department))
        return cls(records)

    @classmethod
    def from_package_data(cls) -> "CourtCatalog":
        records: list[CourtRecord] = []
        root = package_data()
        for stem, department in LEGACY_FILES.items():
            resource = root.joinpath(f"{stem}.json")
            if not resource.is_file():
                continue
            with resource.open("r", encoding="utf-8-sig") as handle:
                for item in json.load(handle):
                    records.append(CourtRecord.from_legacy(item, department))
        return cls(records)
