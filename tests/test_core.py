from types import SimpleNamespace

from shapely.geometry import Polygon

from macourts_core import (
    BostonMunicipalCourtMatcher,
    Coordinates,
    CourtCatalog,
    CourtFinder,
    CourtRecord,
    Location,
    LocationRule,
    RuleMatcher,
    location_from_object,
)


def test_bmc_geometry_and_boundary():
    polygon = Polygon(
        [(-71.2, 42.3), (-71.0, 42.3), (-71.0, 42.5), (-71.2, 42.5)]
    )
    matcher = BostonMunicipalCourtMatcher([("Brighton", polygon)])
    result = matcher.match(
        Location(city="Boston", coordinates=Coordinates(42.3, -71.1)),
        ["Boston Municipal Court"],
    )
    assert result[0].name == "Brighton Division, Boston Municipal Court"


def test_rule_matcher_and_catalog_enrichment():
    matcher = RuleMatcher(
        [
            LocationRule(
                department="Superior Court",
                court_names=("Suffolk County Superior Court",),
                cities=frozenset({"boston"}),
                counties=frozenset({"suffolk county"}),
            )
        ]
    )
    catalog = CourtCatalog(
        [
            CourtRecord(
                "Suffolk County Superior Court",
                "Superior Court",
                court_code="S30",
            )
        ]
    )
    result = CourtFinder([matcher], catalog).find(
        Location(city="Boston"),
        ["Superior Court"],
    )
    assert result[0].records[0].court_code == "S30"


def test_docassemble_adapter_is_duck_typed():
    address = SimpleNamespace(
        city="Boston",
        county="Suffolk County",
        state="MA",
        zip="02108",
        location=SimpleNamespace(latitude=42.36, longitude=-71.06),
    )
    location = location_from_object(address)
    assert location.coordinates == Coordinates(42.36, -71.06)
