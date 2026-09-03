from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any, Collection, Iterable, Mapping

from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep


def norm(value: object | None) -> str:
    return "" if value is None else str(value).strip().casefold()


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Location:
    city: str | None = None
    county: str | None = None
    state: str | None = "Massachusetts"
    postal_code: str | None = None
    neighborhood: str | None = None
    coordinates: Coordinates | None = None

    def is_massachusetts(self) -> bool:
        return not norm(self.state) or norm(self.state) in {"ma", "massachusetts"}


@dataclass(frozen=True)
class CourtRecord:
    name: str
    department: str
    court_code: str | None = None
    tyler_code: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_legacy(cls, item: Mapping[str, Any], department: str) -> "CourtRecord":
        return cls(
            name=str(item["name"]),
            department=department,
            court_code=str(item["court_code"]) if item.get("court_code") is not None else None,
            tyler_code=str(item["tyler_code"]) if item.get("tyler_code") is not None else None,
            raw=dict(item),
        )


@dataclass(frozen=True)
class MatchReason:
    kind: str
    detail: str
    source: str


@dataclass(frozen=True)
class Candidate:
    name: str
    department: str
    reason: MatchReason


@dataclass(frozen=True)
class CourtMatch:
    name: str
    department: str
    reasons: tuple[MatchReason, ...]
    records: tuple[CourtRecord, ...] = ()


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


class CourtCatalog:
    def __init__(self, records: Iterable[CourtRecord] = ()) -> None:
        self.records = tuple(records)
        index: dict[tuple[str, str], list[CourtRecord]] = defaultdict(list)
        for record in self.records:
            index[(norm(record.department), norm(record.name))].append(record)
        self._index = {key: tuple(value) for key, value in index.items()}

    def resolve(self, name: str, department: str) -> tuple[CourtRecord, ...]:
        return self._index.get((norm(department), norm(name)), ())

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


@dataclass(frozen=True)
class LocationRule:
    department: str
    court_names: tuple[str, ...]
    cities: frozenset[str] = frozenset()
    counties: frozenset[str] = frozenset()
    priority: int = 100

    def matches(self, location: Location) -> bool:
        checks = []
        if self.cities:
            checks.append(norm(location.city) in self.cities)
        if self.counties:
            checks.append(norm(location.county) in self.counties)
        return any(checks)


class RuleMatcher:
    def __init__(self, rules: Iterable[LocationRule]) -> None:
        self.rules = tuple(sorted(rules, key=lambda rule: rule.priority))

    def match(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        if not location.is_massachusetts():
            return []
        allowed = {norm(value) for value in court_types} if court_types else None
        result = []
        for rule in self.rules:
            if allowed is not None and norm(rule.department) not in allowed:
                continue
            if not rule.matches(location):
                continue
            reason = MatchReason(
                "location_rule",
                "city/county rule matched",
                "jurisdiction_rules",
            )
            result.extend(
                Candidate(name, rule.department, reason) for name in rule.court_names
            )
        return result


BMC = "Boston Municipal Court"
BOSTON_ALIASES = {
    "allston",
    "boston",
    "brighton",
    "charlestown",
    "dorchester",
    "east boston",
    "jamaica plain",
    "roxbury",
    "south boston",
    "west roxbury",
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
    ):
        self.areas = tuple(_Area(name, geometry) for name, geometry in areas)
        self.prepared = tuple(prep(area.geometry) for area in self.areas)
        self.source = source
        if not self.areas:
            raise ValueError("at least one BMC geometry is required")

    @classmethod
    def _from_geojson_data(
        cls,
        data: Mapping[str, Any],
        source: str,
    ) -> "BostonMunicipalCourtMatcher":
        areas = []
        for feature in data["features"]:
            courthouse = feature.get("properties", {}).get("courthouse")
            geometry = feature.get("geometry")
            if courthouse and geometry:
                areas.append((str(courthouse), shape(geometry)))
        return cls(areas, source=source)

    @classmethod
    def from_geojson(cls, path: str | Path) -> "BostonMunicipalCourtMatcher":
        path = Path(path)
        with path.open(encoding="utf-8") as handle:
            return cls._from_geojson_data(json.load(handle), path.name)

    @classmethod
    def from_package_data(cls) -> "BostonMunicipalCourtMatcher":
        resource = package_data().joinpath("boston_wards.geojson")
        with resource.open("r", encoding="utf-8") as handle:
            return cls._from_geojson_data(json.load(handle), resource.name)

    @staticmethod
    def full_name(courthouse: str) -> str:
        if "boston municipal court" in courthouse.casefold():
            return courthouse
        return f"{courthouse.strip()} Division, Boston Municipal Court"

    def match(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        if not location.is_massachusetts():
            return []
        if court_types and norm(BMC) not in {norm(value) for value in court_types}:
            return []
        if norm(location.city) == "winthrop":
            return [
                Candidate(
                    "East Boston Division, Boston Municipal Court",
                    BMC,
                    MatchReason(
                        "special_case",
                        "Winthrop is served by East Boston BMC",
                        "legacy rule",
                    ),
                )
            ]
        if norm(location.city) not in BOSTON_ALIASES or location.coordinates is None:
            return []

        point = Point(
            location.coordinates.longitude,
            location.coordinates.latitude,
        )
        for area, prepared in zip(self.areas, self.prepared):
            if prepared.covers(point):
                return [
                    Candidate(
                        self.full_name(area.courthouse),
                        BMC,
                        MatchReason(
                            "geometry",
                            f"point covered by {area.courthouse} area",
                            self.source,
                        ),
                    )
                ]

        nearest = min(self.areas, key=lambda area: point.distance(area.geometry))
        return [
            Candidate(
                self.full_name(nearest.courthouse),
                BMC,
                MatchReason(
                    "geometry_nearest",
                    f"nearest area is {nearest.courthouse}",
                    self.source,
                ),
            )
        ]


class StatewideMatcher:
    courts = (
        ("Land Court", "Land Court"),
        ("Appeals Court", "Appeals Court"),
        ("Supreme Judicial Court", "Supreme Judicial Court"),
    )

    def match(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        if not location.is_massachusetts():
            return []
        allowed = {norm(value) for value in court_types} if court_types else None
        return [
            Candidate(
                name,
                department,
                MatchReason("statewide", "statewide court", "built-in"),
            )
            for department, name in self.courts
            if allowed is None or norm(department) in allowed
        ]


class CourtFinder:
    def __init__(
        self,
        matchers: Iterable[Any],
        catalog: CourtCatalog | None = None,
    ) -> None:
        self.matchers = tuple(matchers)
        self.catalog = catalog or CourtCatalog()

    def find(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[CourtMatch]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for matcher in self.matchers:
            for candidate in matcher.match(location, court_types):
                key = (norm(candidate.department), norm(candidate.name))
                state = grouped.setdefault(
                    key,
                    {
                        "name": candidate.name,
                        "department": candidate.department,
                        "reasons": [],
                    },
                )
                if candidate.reason not in state["reasons"]:
                    state["reasons"].append(candidate.reason)
        return sorted(
            [
                CourtMatch(
                    state["name"],
                    state["department"],
                    tuple(state["reasons"]),
                    self.catalog.resolve(
                        state["name"],
                        state["department"],
                    ),
                )
                for state in grouped.values()
            ],
            key=lambda match: (match.department, match.name),
        )


def location_from_object(address: Any) -> Location:
    """Duck-type a docassemble Address without importing docassemble."""
    location = getattr(address, "location", None)
    latitude = getattr(location, "latitude", None)
    longitude = getattr(location, "longitude", None)
    coordinates = None
    if latitude not in (None, "") and longitude not in (None, ""):
        coordinates = Coordinates(float(latitude), float(longitude))
    return Location(
        city=getattr(address, "city", None),
        county=getattr(address, "county", None),
        state=getattr(address, "state", None),
        postal_code=getattr(address, "zip", None),
        neighborhood=getattr(address, "neighborhood", None),
        coordinates=coordinates,
    )
