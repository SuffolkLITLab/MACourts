"""Data-driven city/county/neighborhood jurisdiction rules.

Every Trial Court department except the Boston Municipal Court decides venue
from the municipality (and sometimes the county or Boston neighborhood) of an
address. Those assignments live in ``data/jurisdiction_rules.json`` rather than
in code, so they can be diffed against Mass.gov when the Trial Court publishes a
change. See ``scripts/build_jurisdiction_rules.py`` for how that file is built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping

from .catalog import load_data
from .models import Candidate, Location, MatchReason, norm

RULES_FILE = "jurisdiction_rules.json"

#: A rule set where every matching rule contributes ("concurrent jurisdiction").
SELECT_ALL = "all"
#: A rule set where only the first matching rule contributes (an ordered chain).
SELECT_FIRST = "first"


@dataclass(frozen=True)
class NeighborhoodRule:
    """Match a named neighborhood, optionally only within one city."""

    names: frozenset[str]
    city: str | None = None

    def matches(self, location: Location) -> bool:
        if not norm(location.neighborhood):
            return False
        if self.city and norm(location.city) != norm(self.city):
            return False
        return norm(location.neighborhood) in self.names


@dataclass(frozen=True)
class LocationRule:
    """One jurisdiction assignment: a place test plus the courts it serves.

    City, county, and neighborhood tests are OR-ed by default, matching how the
    Trial Court publishes service areas ("this county, plus these towns"). A
    handful of rules — the Middlesex Probate divisions, the Metro South Canton
    session — are only correct as a conjunction, and set ``require_all``.
    ``excluded_cities`` always vetoes, whichever mode is in force.
    """

    department: str
    court_names: tuple[str, ...]
    cities: frozenset[str] = frozenset()
    counties: frozenset[str] = frozenset()
    neighborhoods: tuple[NeighborhoodRule, ...] = ()
    excluded_cities: frozenset[str] = frozenset()
    require_all: bool = False
    note: str | None = None

    def matches(self, location: Location) -> bool:
        if norm(location.city) in self.excluded_cities:
            return False
        checks = []
        if self.cities:
            checks.append(norm(location.city) in self.cities)
        if self.counties:
            checks.append(norm(location.county) in self.counties)
        if self.neighborhoods:
            checks.append(any(rule.matches(location) for rule in self.neighborhoods))
        if not checks:
            return False
        return all(checks) if self.require_all else any(checks)

    @property
    def reason_detail(self) -> str:
        if self.note:
            return self.note
        parts = []
        if self.cities:
            parts.append("city")
        if self.counties:
            parts.append("county")
        if self.neighborhoods:
            parts.append("neighborhood")
        joiner = " and " if self.require_all else "/"
        return f"{joiner.join(parts)} rule matched"

    @classmethod
    def from_data(cls, item: Mapping[str, Any], department: str) -> "LocationRule":
        return cls(
            department=department,
            court_names=tuple(item["courts"]),
            cities=frozenset(norm(city) for city in item.get("cities", ())),
            counties=frozenset(norm(county) for county in item.get("counties", ())),
            neighborhoods=tuple(
                NeighborhoodRule(
                    names=frozenset(norm(name) for name in group["names"]),
                    city=group.get("city"),
                )
                for group in item.get("neighborhoods", ())
            ),
            excluded_cities=frozenset(
                norm(city) for city in item.get("excluded_cities", ())
            ),
            require_all=bool(item.get("require_all")),
            note=item.get("note"),
        )


class RuleMatcher:
    """Run an ordered set of `LocationRule` objects against a location.

    ``selection`` is applied per department: ``"all"`` lets every matching rule
    contribute (concurrent jurisdiction), ``"first"`` stops at the first match
    (an ordered chain, where earlier rules are the more specific exceptions).
    """

    def __init__(
        self,
        rules: Iterable[LocationRule],
        selection: str = SELECT_ALL,
        source: str = "jurisdiction_rules",
    ) -> None:
        if selection not in (SELECT_ALL, SELECT_FIRST):
            raise ValueError(f"unknown selection mode: {selection!r}")
        self.rules = tuple(rules)
        self.selection = selection
        self.source = source

    def match(
        self,
        location: Location,
        court_types: Collection[str] | None = None,
    ) -> list[Candidate]:
        if not location.is_massachusetts():
            return []
        allowed = {norm(value) for value in court_types} if court_types else None
        candidates: list[Candidate] = []
        satisfied: set[str] = set()
        for rule in self.rules:
            department = norm(rule.department)
            if allowed is not None and department not in allowed:
                continue
            if self.selection == SELECT_FIRST and department in satisfied:
                continue
            if not rule.matches(location):
                continue
            satisfied.add(department)
            reason = MatchReason("location_rule", rule.reason_detail, self.source)
            candidates.extend(
                Candidate(name, rule.department, reason) for name in rule.court_names
            )
        return candidates


def load_jurisdiction_rules(filename: str = RULES_FILE) -> dict[str, RuleMatcher]:
    """Build one `RuleMatcher` per department from packaged rule data."""
    data = load_data(filename)
    matchers = {}
    for block in data["departments"]:
        department = block["department"]
        matchers[department] = RuleMatcher(
            [LocationRule.from_data(item, department) for item in block["rules"]],
            selection=block["selection"],
            source=filename,
        )
    return matchers
