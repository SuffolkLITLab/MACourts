"""Boston Municipal Court geometry, and the sessions that depend on it.

BMC division boundaries are genuinely geometric — they follow Boston ward lines
rather than municipal lines — so this is the one department that needs Shapely
and a geocoded point. Two Juvenile Court sessions inherit those same boundaries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Iterable, Mapping

from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

from .boston_address import BostonAddressIndex
from .catalog import package_data
from .models import (
    BOSTON_CITY_ALIASES,
    Candidate,
    Coordinates,
    Location,
    MatchReason,
    norm,
)
from .rules import RuleMatcher

BMC = "Boston Municipal Court"
JUVENILE = "Juvenile Court"

# Winthrop is a separate municipality, but the BMC serves it out of East Boston.
WINTHROP_DIVISION = "East Boston Division, Boston Municipal Court"

# BMC divisions whose territory has its own Juvenile Court session. Legacy
# MACourts resolved these before any city rule, and so does this matcher.
JUVENILE_DIVISIONS = {
    "West Roxbury Division, Boston Municipal Court": "West Roxbury Juvenile Court",
    "Dorchester Division, Boston Municipal Court": "Dorchester Juvenile Court",
}


@dataclass(frozen=True)
class _Area:
    courthouse: str
    geometry: BaseGeometry


class BostonMunicipalCourtMatcher:
    def __init__(
        self,
        areas: Iterable[tuple[str, BaseGeometry]],
        source: str = "boston_wards.geojson",
        address_index: BostonAddressIndex | None = None,
    ):
        self.areas = tuple(_Area(name, geometry) for name, geometry in areas)
        self.prepared = tuple(prep(area.geometry) for area in self.areas)
        self.source = source
        self.address_index = address_index
        if not self.areas:
            raise ValueError("at least one BMC geometry is required")

    @classmethod
    def _from_geojson_data(
        cls,
        data: Mapping[str, Any],
        source: str,
        address_index: BostonAddressIndex | None = None,
    ) -> "BostonMunicipalCourtMatcher":
        areas = []
        for feature in data["features"]:
            courthouse = feature.get("properties", {}).get("courthouse")
            geometry = feature.get("geometry")
            if courthouse and geometry:
                areas.append((str(courthouse), shape(geometry)))
        return cls(areas, source=source, address_index=address_index)

    @classmethod
    def from_geojson(
        cls,
        path: str | Path,
        address_index: BostonAddressIndex | None = None,
    ) -> "BostonMunicipalCourtMatcher":
        path = Path(path)
        with path.open(encoding="utf-8") as handle:
            return cls._from_geojson_data(
                json.load(handle), path.name, address_index=address_index
            )

    @classmethod
    def from_package_data(cls) -> "BostonMunicipalCourtMatcher":
        resource = package_data().joinpath("boston_wards.geojson")
        with resource.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls._from_geojson_data(
            data,
            resource.name,
            address_index=BostonAddressIndex.from_package_data(),
        )

    @staticmethod
    def full_name(courthouse: str) -> str:
        if "boston municipal court" in courthouse.casefold():
            return courthouse
        return f"{courthouse.strip()} Division, Boston Municipal Court"

    def court_for_coordinates(
        self,
        coordinates: Coordinates,
        *,
        allow_nearest: bool = True,
    ) -> Candidate | None:
        """Resolve the BMC division whose polygon covers a point.

        This is the one piece of geometry logic shared by runtime matching and
        the address-index compiler, so both agree on exactly the same polygons
        and division naming. The compiler calls this with ``allow_nearest=False``
        so that an address the polygons don't actually cover is reported as a
        build-time QA gap rather than silently assigned to whatever is nearest.
        """
        point = Point(coordinates.longitude, coordinates.latitude)
        for area, prepared in zip(self.areas, self.prepared):
            if prepared.covers(point):
                return Candidate(
                    self.full_name(area.courthouse),
                    BMC,
                    MatchReason(
                        "geometry",
                        f"point covered by {area.courthouse} area",
                        self.source,
                    ),
                )

        if not allow_nearest:
            return None

        nearest = min(self.areas, key=lambda area: point.distance(area.geometry))
        return Candidate(
            self.full_name(nearest.courthouse),
            BMC,
            MatchReason(
                "geometry_nearest",
                f"nearest area is {nearest.courthouse}",
                self.source,
            ),
        )

    def division(self, location: Location) -> Candidate | None:
        """Resolve the BMC division serving a location, or None."""
        if not location.is_massachusetts():
            return None
        if norm(location.city) == "winthrop":
            return Candidate(
                WINTHROP_DIVISION,
                BMC,
                MatchReason(
                    "special_case",
                    "Winthrop is served by East Boston BMC",
                    "legacy rule",
                ),
            )
        if norm(location.city) not in BOSTON_CITY_ALIASES:
            return None
        if location.coordinates is not None:
            return self.court_for_coordinates(location.coordinates)
        if location.street_address and self.address_index is not None:
            resolution = self.address_index.resolve(
                location.street_address, zip_code=location.postal_code
            )
            if resolution.match_kind == "success" and resolution.court_name:
                source = "bmc_addresses.sqlite"
                if resolution.data_version:
                    source = f"{source}:{resolution.data_version}"
                if resolution.exact:
                    kind, detail = "address_index", "exact Boston SAM address matched"
                else:
                    # Mirrors geometry_nearest: BMC divisions have concurrent,
                    # not exclusive, jurisdiction across Boston, so the SAM
                    # address's nearest-ward-boundary division is a safe
                    # answer, just one worth telling apart from a strict
                    # containment match.
                    kind, detail = (
                        "address_index_nearest",
                        "nearest-boundary Boston SAM address matched",
                    )
                return Candidate(
                    resolution.court_name,
                    BMC,
                    MatchReason(kind, f"{detail} {resolution.court_name}", source),
                )
        return None

    def match(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        if court_types and norm(BMC) not in {norm(value) for value in court_types}:
            return []
        candidate = self.division(location)
        return [candidate] if candidate else []

    def match_named_place(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        """BMC divisions are resolved from the city name itself, never a county."""
        return self.match(location, court_types)


class JuvenileCourtMatcher:
    """Juvenile Court matching, with the two BMC-derived sessions taking priority.

    Inside Boston the Juvenile Court follows BMC division lines rather than the
    city, so an address in the West Roxbury or Dorchester division goes to that
    division's Juvenile Court *instead of* the city rule's Boston Juvenile Court.
    """

    def __init__(
        self,
        rules: RuleMatcher,
        bmc_matcher: BostonMunicipalCourtMatcher,
        divisions: Mapping[str, str] = JUVENILE_DIVISIONS,
    ) -> None:
        self.rules = rules
        self.bmc_matcher = bmc_matcher
        self.divisions = dict(divisions)

    def match(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        if court_types and norm(JUVENILE) not in {norm(value) for value in court_types}:
            return []
        if not location.is_massachusetts():
            return []
        return self._match(location, court_types, self.rules.match)

    def match_named_place(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        """`match`, kept only where a BMC division or a rule names this place."""
        if court_types and norm(JUVENILE) not in {norm(value) for value in court_types}:
            return []
        if not location.is_massachusetts():
            return []
        return self._match(location, court_types, self.rules.match_named_place)

    def _match(
        self,
        location: Location,
        court_types: Collection[str] | None,
        rule_match: Any,
    ) -> list[Candidate]:
        division = self.bmc_matcher.division(location)
        if division is not None and division.name in self.divisions:
            return [
                Candidate(
                    self.divisions[division.name],
                    JUVENILE,
                    MatchReason(
                        "bmc_division",
                        f"{division.name} territory has its own Juvenile Court",
                        division.reason.source,
                    ),
                )
            ]
        return rule_match(location, court_types)
