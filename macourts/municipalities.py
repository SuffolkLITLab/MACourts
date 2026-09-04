"""Indexing Massachusetts municipalities, counties, and community aliases."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from .catalog import load_data
from .models import Coordinates, Location, MatchReason, norm, replace_location

MUNICIPALITY_ALIASES_FILE = "municipality_aliases.json"


@dataclass(frozen=True)
class MunicipalityMatch:
    """A resolved canonical municipality and its county."""

    name: str
    county: str
    is_canonical: bool = True


class MunicipalityIndex:
    """Fast in-memory index for the 351 Massachusetts municipalities and community aliases."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.municipalities: dict[str, dict[str, str]] = data.get("municipalities", {})
        self.aliases: dict[str, list[dict[str, str]]] = data.get("aliases", {})
        self._canonical_list = tuple(
            m["name"]
            for _, m in sorted(self.municipalities.items(), key=lambda item: item[1]["name"])
        )
        by_county: dict[str, list[str]] = {}
        for m in self.municipalities.values():
            by_county.setdefault(m["county"], []).append(m["name"])
        self._by_county = {
            county: tuple(sorted(names)) for county, names in sorted(by_county.items())
        }

    @classmethod
    @lru_cache(maxsize=1)
    def from_package_data(
        cls, filename: str = MUNICIPALITY_ALIASES_FILE
    ) -> "MunicipalityIndex":
        """Load the packaged municipality and alias JSON dataset."""
        return cls(load_data(filename))

    def is_canonical_municipality(self, place_name: object | None) -> bool:
        """True if the given name is one of the 351 official Massachusetts cities or towns."""
        return norm(place_name) in self.municipalities

    def canonical_name(self, place_name: object | None) -> str | None:
        """Return the official capitalization of a municipality, or None if unknown."""
        entry = self.municipalities.get(norm(place_name))
        return entry["name"] if entry else None

    def get_county(self, place_name: object | None) -> str | None:
        """Return the county for a canonical municipality or unambiguous community alias."""
        key = norm(place_name)
        if not key:
            return None

        # 1. Direct canonical municipality match
        if key in self.municipalities:
            return self.municipalities[key]["county"]

        # 2. Check alias index
        if key in self.aliases:
            targets = self.aliases[key]
            if not targets:
                return None
            first_county = targets[0]["county"]
            if all(t["county"] == first_county for t in targets):
                return first_county

        return None

    def resolve_alias(self, alias: object | None) -> tuple[MunicipalityMatch, ...]:
        """Return all canonical municipality targets for a given village or neighborhood alias."""
        key = norm(alias)
        if not key or key not in self.aliases:
            return ()
        return tuple(
            MunicipalityMatch(
                name=target["municipality"],
                county=target["county"],
                is_canonical=False,
            )
            for target in self.aliases[key]
        )

    def resolve_place(
        self, place_name: object | None, county: object | None = None
    ) -> tuple[MunicipalityMatch, ...]:
        """Resolve a place name (canonical or alias), disambiguating by county when provided."""
        key = norm(place_name)
        if not key:
            return ()
        norm_county = norm(county)

        entry = self.municipalities.get(key)
        canonical = (
            (
                MunicipalityMatch(
                    name=entry["name"],
                    county=entry["county"],
                    is_canonical=True,
                ),
            )
            if entry is not None
            else ()
        )
        if canonical and (not norm_county or norm_county == norm(entry["county"])):
            return canonical

        targets = list(self.aliases.get(key, ()))
        if targets and norm_county:
            narrowed = [t for t in targets if norm(t["county"]) == norm_county]
            # A name that is itself a municipality only gives way to a village of
            # the same name when the caller's county actually points at one;
            # otherwise a slightly wrong county would return an unrelated town.
            targets = narrowed if narrowed or canonical else targets
        if targets:
            return tuple(
                MunicipalityMatch(
                    name=target["municipality"],
                    county=target["county"],
                    is_canonical=False,
                )
                for target in targets
            )

        return canonical

    def canonical_municipalities(self) -> tuple[str, ...]:
        """All 351 official Massachusetts cities and towns in alphabetical order."""
        return self._canonical_list

    def canonical_municipalities_by_county(self) -> dict[str, tuple[str, ...]]:
        """Map of county names to their constituent canonical municipalities."""
        return self._by_county

    def expand(
        self, locations: Location | Iterable[Location]
    ) -> list[tuple[Location, Location | None]]:
        """Expand locations whose city is an alias into their canonical municipality locations."""
        input_locations = (
            [locations] if isinstance(locations, Location) else list(locations)
        )
        expanded: list[tuple[Location, Location | None]] = []

        for loc in input_locations:
            city = loc.city
            if not city or self.is_canonical_municipality(city):
                expanded.append((loc, None))
                continue

            matches = self.resolve_place(city, county=loc.county)
            if not matches:
                expanded.append((loc, None))
                continue

            for match in matches:
                resolved = replace_location(
                    loc,
                    city=match.name,
                    county=match.county,
                )
                expanded.append((resolved, loc))

        return expanded


def get_county(place_name: object | None) -> str | None:
    """Helper function to look up the Massachusetts county for a canonical place name or alias."""
    return MunicipalityIndex.from_package_data().get_county(place_name)


def is_canonical_municipality(place_name: object | None) -> bool:
    """Helper function to check if a place name is one of the 351 official Massachusetts municipalities."""
    return MunicipalityIndex.from_package_data().is_canonical_municipality(place_name)
