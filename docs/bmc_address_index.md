# BMC address index

`macourts/data/bmc_addresses.sqlite` lets `Location(street_address=..., city="Boston")`
resolve a Boston Municipal Court division with no geocoding, no network access,
and no runtime GIS operation. This page covers where the data comes from, how
it's compiled, its schema, its resolution rules, and how it's kept current.

## Where the data comes from

Boston's Street Address Management (SAM) system publishes every address in the
city as a public ArcGIS FeatureServer layer:

```
https://gisportal.boston.gov/arcgis/rest/services/SAM/Live_SAM_Address/FeatureServer/0
```

`scripts/fetch_boston_sam.py` downloads the full layer — house number, street
name and its components, ZIP, mailing neighborhood, ward, and point geometry —
into a frozen, gzip-compressed JSONL snapshot (`build/sam/addresses.jsonl.gz`
plus `source.json`), paginating past the service's 2,000-record page limit.
There is no separate published master-street/alias/suffix-crosswalk service on
this host; every address record already carries `FULL_STREET_NAME` plus its
component fields (`STREET_BODY`, `STREET_SUFFIX_ABBR`, `STREET_FULL_SUFFIX`,
`STREET_PREFIX`, `STREET_SUFFIX_DIR`), which is enough to derive canonical and
suffix-variant street spellings without a second source.

`scripts/build_bmc_address_index.py` then:

1. Loads `boston_wards.geojson` through the same
   `BostonMunicipalCourtMatcher` runtime code uses, and spatially assigns every
   SAM address point to a BMC division via
   `court_for_coordinates(point, allow_nearest=False)` — the same method, same
   polygons, same division names the coordinate-based matcher uses. An address
   whose point isn't covered by any ward polygon is left out of the index and
   reported in the QA output rather than assigned to a nearest guess.
2. Ignores `UNIT` entirely (a unit can't change BMC jurisdiction) and expands a
   SAM range address (e.g. `6-10 A St`, meaning one building/entrance spans
   house numbers 6, 8, and 10) into its individual house numbers at the
   range's own odd/even parity — this is authoritative SAM data about one
   address entity, not interpolation between unrelated addresses.
3. Collapses rows that share `(street_id, house number, ZIP)` and resolve to
   the same division. If identical rows resolve to *different* divisions
   (possible right at a ward boundary, where SAM sometimes carries two
   slightly offset points for the same address), the key is excluded from the
   index and reported as a build conflict rather than picking one.
4. Builds `street_names` from SAM's `FULL_STREET_NAME` (canonical) plus
   generated suffix (`St`/`Street`) and directional-prefix/suffix
   (`N`/`North`, `S`/`South`, ...) spelling variants.
5. Writes the rows in sorted order, runs `VACUUM` and `PRAGMA integrity_check`,
   and computes a logical content SHA-256 over the sorted division/street/
   address rows (not the raw SQLite file bytes, which vary run to run even for
   identical content).

Nothing at runtime talks to SAM or does GIS work; `macourts/boston_address.py`
only ever opens the compiled SQLite file.

## Schema

```sql
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE divisions (id INTEGER PRIMARY KEY, court_name TEXT NOT NULL UNIQUE);
CREATE TABLE street_names (
    name_key  TEXT NOT NULL,
    street_id INTEGER NOT NULL,  -- SAM's own STREET_ID
    kind      INTEGER NOT NULL,  -- 0 canonical, 1 alias (unused, see above), 2 generated variant
    PRIMARY KEY (name_key, street_id)
) WITHOUT ROWID;
CREATE TABLE addresses (
    street_id   INTEGER NOT NULL,
    number_key  TEXT NOT NULL,
    zip_code    INTEGER NOT NULL DEFAULT 0,  -- e.g. 2118 for "02118"
    division_id INTEGER NOT NULL,
    PRIMARY KEY (street_id, number_key, zip_code)
) WITHOUT ROWID;
```

No coordinates, geometry, parcel/building IDs, or units are stored — nothing
that isn't needed after compilation. Both tables are `WITHOUT ROWID`, so each
one's primary key *is* a clustered B-tree over exactly the columns `resolve()`
filters on (`name_key`; `street_id, number_key`) — there are deliberately no
secondary indexes, since one on the same leading columns would just be a
same-size duplicate of what the primary key already provides (confirmed with
`EXPLAIN QUERY PLAN`: both lookups use `SEARCH ... USING PRIMARY KEY`). A SAM
range address (e.g. `6-10 A St`) is stored only as its expanded individual
house numbers, not also as the literal range string — a real caller types
their own house number, never a range. `zip_code` is stored as an integer
(dropping the leading zero from the stored bytes) since it's cheaper than TEXT
and nothing in `macourts.boston_address` ever hands a raw `zip_code` value
back to a caller — `resolve()` only ever returns `court_name`. Reconstruct the
leading zero (`str(value).zfill(5)`) if you query this column directly.
Together these decisions are most of why the compiled database is
~2.4&nbsp;MB rather than the ~6&nbsp;MB a first, unoptimized build produced.

`zip_code` itself is **not optional**: duplicate street names recur across
different Boston streets far more than you'd guess (e.g. "A St" names two
distinct street segments in South Boston; "Adams St" names four across
different neighborhoods), and 5,902 of the ~50,000 `(street name, house
number)` combinations sharing a name with another street genuinely resolve to
different BMC divisions depending on which physical street is meant. ZIP is
what disambiguates them; dropping the column was evaluated and rejected for
that reason.

## Runtime resolution rules

`BostonAddressIndex.resolve(street_address, zip_code=None)` never does fuzzy,
phonetic, or nearest-street matching, and never interpolates a house number
that isn't in the index. An address it doesn't recognize comes back
`not_found` rather than a guess:

| Situation | `match_kind` |
| --- | --- |
| Street name not in the index | `not_found` |
| Street exists, house number doesn't | `not_found` |
| One matching row, or several rows all in the same division | `success` |
| A ZIP is given and exactly one candidate division matches it | `success` |
| A ZIP is given but matches none of the candidate rows | `zip_mismatch` |
| Rows resolve to more than one division and the ZIP doesn't disambiguate | `ambiguous` |

`macourts.boston.BostonMunicipalCourtMatcher.division()` only consults this
index when `location.coordinates` is absent — a geocoded point always takes
priority, so existing coordinate-based callers are unaffected.

## Validation against known addresses

`scripts/build_bmc_address_index.py`'s own QA report covers every compiled
row. As an independent cross-check, every real, geocoded Boston location in
`tests/fixtures/massachusetts_addresses_diverse_and_geocoded.xlsx` (Boston
Public Library branches, spanning all 8 BMC divisions) resolves to the same
division through the address index as it does through the existing
coordinate-based matcher — see `tests/test_bmc_address_data.py`.

## Refreshing the data

`.github/workflows/update_bmc_addresses.yml` runs the fetch/build/compare
pipeline on a schedule (~January 15 and ~July 15) and on demand. It:

1. Fetches a fresh SAM snapshot and builds a candidate database.
2. Compares its logical content hash against the committed one — if nothing
   changed, the workflow exits without opening a PR.
3. Otherwise runs the full test suite and a wheel-packaging check against the
   candidate data, uploads the snapshot and QA report as workflow artifacts,
   and opens a PR with the refreshed `bmc_addresses.sqlite` and
   `bmc_addresses.meta.json`, using the comparison report as the PR body.

To run the pipeline locally:

```bash
python scripts/fetch_boston_sam.py --out build/sam
python scripts/build_bmc_address_index.py
python scripts/compare_bmc_address_index.py \
    --old-db macourts/data/bmc_addresses.sqlite \
    --new-db macourts/data/bmc_addresses.sqlite
```

## Known data-quality notes (first build, 2026-09)

- **~1.2% of SAM address points fall outside every BMC ward polygon** (mostly
  labeled "Boston", "East Boston", or "Dorchester" in SAM's own
  `MAILING_NEIGHBORHOOD` field). This is a pre-existing mismatch between the
  ward-boundary GIS layer and SAM's address points — the same boundary
  geometry the coordinate-based matcher already uses (and already falls back
  to `geometry_nearest` for) — not something introduced by the address index.
  These addresses are simply absent from the index rather than assigned a
  guess; a lookup for one returns `not_found`.
- **7 address keys, out of ~155,800, are genuine build conflicts**: SAM
  carries two slightly offset points for the same `(street, number, ZIP)`
  that land in different divisions, always right at a ward boundary (e.g.
  Walnut Park in Roxbury/West Roxbury, Huntington Ave in Central/Roxbury).
  These are excluded from the index by design rather than resolved by
  picking one division.

Both are reported by every build in `build/bmc_address_report.md`; the
percentage/count thresholds in the build script are worth revisiting against
a few more refresh cycles' worth of data before tightening them.
