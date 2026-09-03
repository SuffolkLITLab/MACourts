# MACourts

A dependency-light, plain-Python Massachusetts court lookup and jurisdiction-matching library intended to be shared by [docassemble-MACourts](https://github.com/SuffolkLITLab/docassemble-MACourts) and [LITEFile](https://github.com/SuffolkLITLab/LITEFile).

## Design boundary

- Keep Shapely: Boston Municipal Court division matching is genuinely geometric.
- Avoid GeoPandas in the runtime lookup path: standard-library JSON + Shapely is enough.
- Do not import docassemble, Django, or an EFSP client in the shared layer.
- Keep geocoding in the caller. The shared layer accepts city/county/ZIP and optional coordinates.
- Read the existing docassemble-MACourts JSON format unchanged during migration.
- Return semantic court names plus reasons, with local court/session records as optional enrichment.

## Current prototype

`macourts_core.py` includes:

- plain `Location`, `CourtRecord`, and `CourtMatch` models;
- legacy JSON catalog loading;
- a data-driven city/county rule matcher;
- BMC Shapely point-in-polygon matching, including Winthrop and nearest-polygon fallback;
- statewide court matching;
- a composable `CourtFinder`;
- a duck-typed adapter for docassemble `Address` objects without importing docassemble.

This repository is the shared core. Integration and compatibility work for the existing docassemble package is tracked in [docassemble-MACourts issue #130](https://github.com/SuffolkLITLab/docassemble-MACourts/issues/130).
