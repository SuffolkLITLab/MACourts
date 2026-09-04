"""Indexing Massachusetts municipalities, counties, and community aliases."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from .catalog import load_data
from .models import (
    Coordinates,
    Location,
    MatchReason,
    damerau_levenshtein_distance,
    fuzzy_match_threshold,
    norm,
    replace_location,
)

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
        # Every canonical municipality name and every alias/neighborhood
        # name, as the candidate pool typo rescue matches a misspelled city
        # against -- one unified pass covers both "Sommerville" (a canonical
        # town, typo'd) and "Drochester" (an alias/neighborhood, typo'd).
        self._fuzzy_candidates = frozenset(self.municipalities) | frozenset(
            self.aliases
        )

    def fuzzy_correct_city(self, city: object | None) -> str | None:
        """A single municipality/alias spelling within typo-rescue distance of ``city``.

        Returns ``None`` if ``city`` is already recognized (nothing to
        correct), if nothing is close enough, or if more than one candidate
        is -- an ambiguous typo rescue is refused, matching every other
        fuzzy-match safeguard in this package.
        """
        city_key = norm(city)
        if not city_key or city_key in self._fuzzy_candidates:
            return None
        threshold = fuzzy_match_threshold(city_key)
        if threshold is None:
            return None
        candidates = {
            candidate
            for candidate in self._fuzzy_candidates
            if abs(len(candidate) - len(city_key)) <= threshold
            and damerau_levenshtein_distance(city_key, candidate, threshold)
            <= threshold
        }
        return next(iter(candidates)) if len(candidates) == 1 else None

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
    ) -> list[tuple[Location, Location | None, Location | None]]:
        """Expand locations whose city is an alias into their canonical municipality locations.

        Each result is ``(resolved_location, alias_origin, fuzzy_origin)``:
        ``alias_origin`` is set when the resolution went through an
        alias/neighborhood lookup (not a canonical name), ``fuzzy_origin`` is
        set when the city didn't match anything until it was typo-corrected.
        A location can have neither, either, or both set -- a typo'd alias
        (e.g. "Dorchestr", one edit from "Dorchester") sets both.
        """
        input_locations = (
            [locations] if isinstance(locations, Location) else list(locations)
        )
        expanded: list[tuple[Location, Location | None, Location | None]] = []

        for loc in input_locations:
            city = loc.city
            if not city or self.is_canonical_municipality(city):
                expanded.append((loc, None, None))
                continue

            matches = self.resolve_place(city, county=loc.county)
            fuzzy_origin = None
            if not matches:
                corrected = self.fuzzy_correct_city(city)
                if corrected is not None:
                    matches = self.resolve_place(corrected, county=loc.county)
                    if matches:
                        fuzzy_origin = loc
            if not matches:
                expanded.append((loc, None, None))
                continue

            for match in matches:
                resolved = replace_location(
                    loc,
                    city=match.name,
                    county=match.county,
                )
                alias_origin = loc if not match.is_canonical else None
                expanded.append((resolved, alias_origin, fuzzy_origin))

        return expanded


def get_county(place_name: object | None) -> str | None:
    """Helper function to look up the Massachusetts county for a canonical place name or alias."""
    return MunicipalityIndex.from_package_data().get_county(place_name)


def is_canonical_municipality(place_name: object | None) -> bool:
    """Helper function to check if a place name is one of the 351 official Massachusetts municipalities."""
    return MunicipalityIndex.from_package_data().is_canonical_municipality(place_name)
