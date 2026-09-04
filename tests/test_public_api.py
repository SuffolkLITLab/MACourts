"""Smoke tests for the exported `macourts` API and the packaged data files."""

from types import SimpleNamespace

from shapely.geometry import Polygon

from macourts import (
    BostonMunicipalCourtMatcher,
    Coordinates,
    CourtCatalog,
    CourtFinder,
    CourtRecord,
    Location,
    LocationRule,
    RuleMatcher,
    location_from_object,
    package_data,
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


def test_packaged_catalog_is_available():
    catalog = CourtCatalog.from_package_data()
    assert catalog.resolve(
        "Brighton Division, Boston Municipal Court",
        "Boston Municipal Court",
    )


def test_packaged_bmc_geometry_is_available():
    matcher = BostonMunicipalCourtMatcher.from_package_data()
    assert matcher.areas


def test_zip_data_is_packaged():
    assert package_data().joinpath("ma_zip_codes.json").is_file()
