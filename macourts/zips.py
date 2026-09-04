"""ZIP-code expansion for addresses that carry nothing else to match on."""

from __future__ import annotations

import re
from typing import Iterable

from .catalog import load_data
from .models import Coordinates, Location

ZIP_FILE = "ma_zip_codes.json"
_PLACE_SEPARATORS = re.compile(r"\s*[,/;]\s*")
_ZIP_PLUS_FOUR = re.compile(r"\b(\d{5})-?\d{4}\b")


def normalize_postal_code(value: object | None) -> str:
    """Return a five-digit ZIP, zero-padding the four-digit integers we see."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        text = value.strip()
        # A ZIP that lost its leading zero to a spreadsheet arrives as "2072".
        return text.zfill(5) if text.isdigit() and len(text) < 5 else text
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return ""
    if numeric < 0:
        return ""
    return str(numeric).zfill(5) if numeric < 10000 else str(numeric)


def _split_places(value: object | None) -> list[str]:
    if not value:
        return []
    parts = (part.strip() for part in _PLACE_SEPARATORS.split(str(value).strip()))
    return list(dict.fromkeys(part for part in parts if part))


def _county_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or cleaned.casefold().endswith("county"):
        return cleaned
    return f"{cleaned} County"


class ZipIndex:
    """Map a Massachusetts ZIP code onto the places it covers.

    A ZIP can span several municipalities, so this returns one `Location` per
    place name. Callers union the courts matched for each.
    """

    def __init__(self, records: dict[str, dict]) -> None:
        self.records = records

    @classmethod
    def from_package_data(cls, filename: str = ZIP_FILE) -> "ZipIndex":
        return cls(load_data(filename))

    def record(self, postal_code: object | None) -> dict | None:
        normalized = normalize_postal_code(postal_code)
        if not normalized:
            return None
        found = self.records.get(normalized)
        if found is None:
            plus_four = _ZIP_PLUS_FOUR.search(normalized)
            if plus_four:
                found = self.records.get(plus_four.group(1))
        return found

    def locations(self, postal_code: object | None) -> tuple[Location, ...]:
        record = self.record(postal_code)
        if record is None:
            return ()
        places = _split_places(record.get("place_name")) or _split_places(
            record.get("community_name")
        )
        if not places:
            return ()

        counties = [_county_name(name) for name in _split_places(record.get("county_name"))]
        if len(counties) == 1:
            counties = counties * len(places)
        elif len(counties) != len(places):
            counties = [""] * len(places)

        latitude = record.get("latitude")
        longitude = record.get("longitude")
        coordinates = (
            Coordinates(float(latitude), float(longitude))
            if latitude is not None and longitude is not None
            else None
        )
        normalized = normalize_postal_code(postal_code)
        return tuple(
            Location(
                city=place,
                county=counties[index] or None,
                state=record.get("state_name") or record.get("state_code") or "MA",
                postal_code=normalized,
                coordinates=coordinates,
            )
            for index, place in enumerate(places)
        )

    def expand(self, locations: Iterable[Location]) -> list[tuple[Location, Location | None]]:
        """Pair each location with the ZIP-derived location it was expanded from.

        Locations that already carry a city, county, or coordinates pass through
        unchanged with ``None`` as the origin.
        """
        expanded: list[tuple[Location, Location | None]] = []
        for location in locations:
            if not location.is_postal_code_only:
                expanded.append((location, None))
                continue
            derived = self.locations(location.postal_code)
            if not derived:
                expanded.append((location, None))
                continue
            expanded.extend((candidate, location) for candidate in derived)
        return expanded
