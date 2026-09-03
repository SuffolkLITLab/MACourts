# MACourts

A dependency-light, plain-Python Massachusetts court lookup and jurisdiction-matching library intended to be shared by [docassemble-MACourts](https://github.com/SuffolkLITLab/docassemble-MACourts) and [LITEFile](https://github.com/SuffolkLITLab/LITEFile).

## Design boundary

- Keep Shapely: Boston Municipal Court division matching is genuinely geometric.
- Avoid GeoPandas in the runtime lookup path: standard-library JSON + Shapely is enough.
- Do not import docassemble, Django, or an EFSP client in the shared layer.
- Keep geocoding in the caller. The shared layer accepts city/county/ZIP and optional coordinates.
- Own the Massachusetts court records, BMC geometry, ZIP lookup data, jurisdiction rules, and matching code.
- Return semantic court names plus reasons, with local court/session records as optional enrichment.

## Package data

The maintained court catalogs and geographic lookup data are bundled inside `macourts/data/` and included in installed distributions. Code accesses them through `importlib.resources`, so callers do not need to know a filesystem path.

Current data includes District, Housing, BMC, Superior, Juvenile, Probate and Family, Land, Appeals, and Supreme Judicial Court records; Boston ward/BMC geometry; and the legacy Massachusetts ZIP lookup table used for compatibility work.

## Current prototype

The package currently includes:

- plain `Location`, `CourtRecord`, and `CourtMatch` models;
- loading the existing MACourts JSON schema directly from package resources;
- a composable `CourtFinder`;
- data-driven city/county rules;
- BMC Shapely point-in-polygon matching, including Winthrop and nearest-polygon fallback;
- statewide court matching;
- a duck-typed adapter for docassemble `Address` objects without importing docassemble.

Integration and compatibility work for the existing docassemble package is tracked in [docassemble-MACourts issue #130](https://github.com/SuffolkLITLab/docassemble-MACourts/issues/130).
