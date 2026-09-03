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

## Data freshness

Court locations were reconciled against the current Massachusetts Court System
directories on September 3, 2026. The audit includes roster counts, address
corrections, retired/new sessions, physical-vs-mailing addresses, and source
links:

- [Court location audit — 2026-09-03](docs/court_location_audit_2026-09-03.md)

Each current court record includes `address_verified` and `address_source`
metadata. Retired court metadata used for historical docket interpretation is
kept separately from current filing locations.


## Filing versus appearance locations

Court records distinguish the physical/session location from the place where
filings must be directed:

- `location_name` — physical/session identity;
- `accepts_filings` — whether that location itself accepts filings;
- `filing_location` — canonical filing location when it does not;
- `appearance_locations` — reverse links from a filing location to hearing/
  appearance sessions.

For example, Metro South Housing Court - Stoughton Session is an appearance
location but filings are directed to the Canton Session.

This metadata is deliberately separate from live Tyler/EFSP "fileability".
LITEFile should use MACourts to choose the legal filing location, then confirm
the current Tyler route/category hierarchy at runtime.

See [the 2026-09-03 court location audit](docs/court_location_audit_2026-09-03.md)
for the field semantics and the documented procedure for recovering/updating
Tyler court and lower-court codes.
