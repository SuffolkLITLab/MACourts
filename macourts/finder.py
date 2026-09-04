"""Composing matchers into a court finder."""

from __future__ import annotations

from typing import Any, Collection, Iterable

from .boston import BostonMunicipalCourtMatcher, JuvenileCourtMatcher
from .catalog import CourtCatalog
from .models import (
    Candidate,
    Coordinates,
    CourtMatch,
    Location,
    MatchReason,
    norm,
)
from .municipalities import MunicipalityIndex
from .rules import RuleMatcher, load_jurisdiction_rules
from .zips import ZipIndex


class StatewideMatcher:
    """Courts with statewide jurisdiction, which every MA address can reach."""

    courts = (
        ("Land Court", "Land Court"),
        ("Appeals Court", "Massachusetts Appeals Court (Single Justice)"),
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
    """Run every matcher over one or more locations and merge the results."""

    def __init__(
        self,
        matchers: Iterable[Any],
        catalog: CourtCatalog | None = None,
        zip_index: ZipIndex | None = None,
        municipality_index: MunicipalityIndex | None = None,
    ) -> None:
        self.matchers = tuple(matchers)
        self.catalog = catalog or CourtCatalog()
        self.zip_index = zip_index
        self.municipality_index = municipality_index

    def _locations(
        self,
        location: Location | Iterable[Location],
    ) -> list[tuple[Location, Location | None, Location | None]]:
        locations = (
            [location] if isinstance(location, Location) else list(location)
        )
        if self.zip_index is not None:
            zip_pairs = self.zip_index.expand(locations)
        else:
            zip_pairs = [(item, None) for item in locations]

        expanded_pairs: list[tuple[Location, Location | None, Location | None]] = []
        for loc, zip_origin in zip_pairs:
            if self.municipality_index is not None:
                muni_pairs = self.municipality_index.expand([loc])
                for resolved, alias_origin in muni_pairs:
                    expanded_pairs.append(
                        (
                            resolved.with_inferred_county(
                                self.municipality_index.get_county
                            ),
                            zip_origin,
                            alias_origin,
                        )
                    )
            else:
                expanded_pairs.append(
                    (
                        loc.with_inferred_county(),
                        zip_origin,
                        None,
                    )
                )
        return expanded_pairs

    def find(
        self,
        location: Location | Iterable[Location],
        court_types: Collection[str] | None = None,
    ) -> list[CourtMatch]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for resolved, zip_origin, alias_origin in self._locations(location):
            reasons = []
            if zip_origin is not None:
                reasons.append(
                    MatchReason(
                        "postal_code",
                        f"ZIP {zip_origin.postal_code} covers {resolved.city}",
                        "ma_zip_codes.json",
                    )
                )
            if alias_origin is not None:
                reasons.append(
                    MatchReason(
                        "alias",
                        f"'{alias_origin.city}' is an alias/locality in {resolved.city}",
                        "municipality_aliases.json",
                    )
                )
            for matcher in self.matchers:
                for candidate in matcher.match(resolved, court_types):
                    key = (norm(candidate.department), norm(candidate.name))
                    state = grouped.setdefault(
                        key,
                        {
                            "name": candidate.name,
                            "department": candidate.department,
                            "reasons": [],
                        },
                    )
                    for reason in (*reasons, candidate.reason):
                        if reason not in state["reasons"]:
                            state["reasons"].append(reason)
        return sorted(
            [
                CourtMatch(
                    state["name"],
                    state["department"],
                    tuple(state["reasons"]),
                    self.catalog.resolve(state["name"], state["department"]),
                )
                for state in grouped.values()
            ],
            key=lambda match: (match.department, match.name),
        )

    def find_by_postal_code(
        self,
        postal_code: str,
        court_types: Collection[str] | None = None,
    ) -> list[CourtMatch]:
        """Find courts for a bare ZIP code, unioning every place it covers."""
        return self.find(Location(postal_code=postal_code), court_types)


def build_matchers(
    bmc_matcher: BostonMunicipalCourtMatcher | None = None,
    rule_matchers: dict[str, RuleMatcher] | None = None,
) -> list[Any]:
    """Assemble the full set of department matchers from packaged data."""
    bmc_matcher = bmc_matcher or BostonMunicipalCourtMatcher.from_package_data()
    rule_matchers = dict(
        rule_matchers if rule_matchers is not None else load_jurisdiction_rules()
    )
    juvenile_rules = rule_matchers.pop("Juvenile Court", None)

    matchers: list[Any] = [bmc_matcher]
    if juvenile_rules is not None:
        matchers.append(JuvenileCourtMatcher(juvenile_rules, bmc_matcher))
    matchers.extend(rule_matchers[name] for name in sorted(rule_matchers))
    matchers.append(StatewideMatcher())
    return matchers


def build_default_finder() -> CourtFinder:
    """A `CourtFinder` covering every Massachusetts court department.

    This is the entry point most callers want::

        finder = build_default_finder()
        finder.find(Location(city="Springfield", county="Hampden County"))
    """
    return CourtFinder(
        build_matchers(),
        catalog=CourtCatalog.from_package_data(),
        zip_index=ZipIndex.from_package_data(),
        municipality_index=MunicipalityIndex.from_package_data(),
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
