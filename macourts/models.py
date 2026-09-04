"""Plain value types shared by every part of the lookup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def norm(value: object | None) -> str:
    """Casefold a value for comparison, treating ``None`` as empty."""
    return "" if value is None else str(value).strip().casefold()


# Boston neighborhoods that Massachusetts addresses commonly give as the city.
# They are all in Suffolk County and all inside the BMC's geometry.
BOSTON_CITY_ALIASES = frozenset(
    {
        "allston",
        "boston",
        "brighton",
        "charlestown",
        "dorchester",
        "east boston",
        "hyde park",
        "jamaica plain",
        "mattapan",
        "roslindale",
        "roxbury",
        "south boston",
        "west roxbury",
    }
)

MASSACHUSETTS = frozenset({"ma", "massachusetts"})


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
    street_address: str | None = None

    def is_massachusetts(self) -> bool:
        return not norm(self.state) or norm(self.state) in MASSACHUSETTS

    @property
    def is_postal_code_only(self) -> bool:
        """True when a ZIP is the only thing we can match on."""
        return bool(self.postal_code) and not (
            self.city or self.county or self.neighborhood or self.coordinates
        )

    def with_inferred_county(self, county_lookup: Any | None = None) -> "Location":
        """Fill in Suffolk County for bare Boston-neighborhood cities.

        Every jurisdiction rule set treats a missing county as unmatchable, but
        addresses written as "Dorchester, MA" or "Brighton, MA" carry no county
        at all. Legacy MACourts special-cased this for each department; doing it
        once here keeps the rule data free of the workaround.
        """
        if norm(self.county):
            return self
        if not self.city:
            return self
        if norm(self.city) in BOSTON_CITY_ALIASES:
            return replace_location(self, county="Suffolk County")
        if county_lookup is not None:
            inferred = county_lookup(self.city)
            if inferred:
                return replace_location(self, county=inferred)
        return self



def replace_location(location: Location, **changes: Any) -> Location:
    """`dataclasses.replace` for `Location`, spelled out for readability."""
    values = {
        "city": location.city,
        "county": location.county,
        "state": location.state,
        "postal_code": location.postal_code,
        "neighborhood": location.neighborhood,
        "coordinates": location.coordinates,
        "street_address": location.street_address,
    }
    values.update(changes)
    return Location(**values)


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

    @property
    def location_name(self) -> str:
        """Human-facing identity of this physical/session location."""
        return str(self.raw.get("location_name") or self.name)

    @property
    def accepts_filings(self) -> bool:
        """Whether this location itself accepts filings/correspondence.

        This is court-administration metadata, not a promise that the live EFSP
        accepts every filing type at this location. LITEFile should still query
        the live Tyler taxonomy for e-filing availability.
        """
        return bool(self.raw.get("accepts_filings", True))

    @property
    def filing_location_name(self) -> str:
        """Canonical location to use for filing when this is appearance-only."""
        return str(self.raw.get("filing_location") or self.location_name)

    @property
    def appearance_location_names(self) -> tuple[str, ...]:
        """Locations where matters filed through this record may be heard."""
        values = self.raw.get("appearance_locations")
        if not values:
            return (self.location_name,)
        return tuple(str(value) for value in values)

    @property
    def court_code_aliases(self) -> tuple[str, ...]:
        """Historical or alternate Trial Court docket/location codes."""
        values = self.raw.get("court_code_aliases") or ()
        return tuple(str(value) for value in values)

    def matches_court_code(self, value: str) -> bool:
        """Match a primary or historical/alternate Trial Court code."""
        target = norm(value)
        return (
            (self.court_code is not None and norm(self.court_code) == target)
            or target in {norm(alias) for alias in self.court_code_aliases}
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
