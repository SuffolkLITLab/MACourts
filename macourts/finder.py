"""Composing matchers into a court finder."""

from __future__ import annotations

from dataclasses import dataclass
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

    def match_named_place(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        """Statewide courts say nothing about a place name, so they never match one."""
        return []


@dataclass(frozen=True)
class _Attempt:
    """One location to run the matchers against, and why it differs from the input."""

    location: Location
    zip_origin: Location | None = None
    alias_origin: Location | None = None
    fuzzy_origin: Location | None = None

    @property
    def reasons(self) -> tuple[MatchReason, ...]:
        reasons = []
        if self.zip_origin is not None:
            reasons.append(
                MatchReason(
                    "postal_code",
                    f"ZIP {self.zip_origin.postal_code} covers {self.location.city}",
                    "ma_zip_codes.json",
                )
            )
        if self.alias_origin is not None:
            reasons.append(
                MatchReason(
                    "alias",
                    f"'{self.alias_origin.city}' is an alias/locality in {self.location.city}",
                    "municipality_aliases.json",
                )
            )
        if self.fuzzy_origin is not None:
            reasons.append(
                MatchReason(
                    "fuzzy_place",
                    f"'{self.fuzzy_origin.city}' fuzzy-matched to {self.location.city}",
                    "municipality_aliases.json",
                )
            )
        return tuple(reasons)


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

    def _attempts(
        self,
        location: Location | Iterable[Location],
    ) -> list[tuple[_Attempt, tuple[_Attempt, ...]]]:
        """Pair each location to match on with the alias expansions to fall back to.

        The county is inferred *before* the alias index is consulted, so that a
        village name shared by several counties ("Mattapan" is both a Boston
        neighborhood and a corner of Milton) resolves to the one the address is
        actually in rather than fanning out across all of them.
        """
        locations = (
            [location] if isinstance(location, Location) else list(location)
        )
        if self.zip_index is not None:
            zip_pairs = self.zip_index.expand(locations)
        else:
            zip_pairs = [(item, None) for item in locations]

        index = self.municipality_index
        attempts: list[tuple[_Attempt, tuple[_Attempt, ...]]] = []
        for loc, zip_origin in zip_pairs:
            given = loc.with_inferred_county(index.get_county if index else None)
            expansions: tuple[_Attempt, ...] = ()
            if index is not None:
                expansions = tuple(
                    _Attempt(resolved, zip_origin, alias_origin, fuzzy_origin)
                    for resolved, alias_origin, fuzzy_origin in index.expand([given])
                    if alias_origin is not None or fuzzy_origin is not None
                )
            attempts.append((_Attempt(given, zip_origin), expansions))
        return attempts

    def _run(
        self,
        matcher: Any,
        given: _Attempt,
        expansions: tuple[_Attempt, ...],
        court_types: Collection[str] | None,
    ) -> list[tuple[_Attempt, list[Candidate]]]:
        """Match one matcher, preferring the caller's own place name over its expansion.

        A village or neighborhood is only routed through its canonical
        municipality when no rule names the place itself. Normalizing first
        would throw away exactly the rules that exist because a place's venue
        differs from its municipality's — East Boston's Chelsea sessions, say —
        and, in an ordered ``first`` chain, would let a county-wide rule stand in
        for the more specific municipal one.

        A matcher without `match_named_place` is treated as never place-specific,
        so custom matchers keep seeing the canonical municipality.
        """
        if not expansions:
            return [(given, matcher.match(given.location, court_types))]
        named_place = getattr(matcher, "match_named_place", None)
        candidates = named_place(given.location, court_types) if named_place else []
        if candidates:
            return [(given, candidates)]
        return [
            (attempt, matcher.match(attempt.location, court_types))
            for attempt in expansions
        ]

    def find(
        self,
        location: Location | Iterable[Location],
        court_types: Collection[str] | None = None,
    ) -> list[CourtMatch]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for given, expansions in self._attempts(location):
            for matcher in self.matchers:
                for attempt, candidates in self._run(
                    matcher, given, expansions, court_types
                ):
                    for candidate in candidates:
                        key = (norm(candidate.department), norm(candidate.name))
                        state = grouped.setdefault(
                            key,
                            {
                                "name": candidate.name,
                                "department": candidate.department,
                                "reasons": [],
                            },
                        )
                        for reason in (*attempt.reasons, candidate.reason):
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
        street_address=getattr(address, "address", None),
    )
