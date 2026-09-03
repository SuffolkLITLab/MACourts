# Massachusetts court location audit — 2026-09-03

This audit compares the runtime court-location data in `macourts/data/` with the
current Massachusetts Court System location directories and current individual
Mass.gov court pages.

## Source precedence

1. Current department-specific Mass.gov location directory.
2. Current individual Mass.gov location page.
3. Current related-location pages for corroboration.
4. MassGIS courthouse metadata as a secondary physical-location cross-check.

The department directory is treated as the authoritative roster of *current*
court locations. Historical courts are kept separately when they are still
needed to interpret older docket numbers.

## Roster reconciliation

| Department | Current Mass.gov locations | MACourts current records | Result |
| --- | ---: | ---: | --- |
| District Court | 61 | 61 | reconciled |
| Housing Court | 24 | 24 | reconciled |
| Boston Municipal Court | 8 | 8 | reconciled |
| Superior Court | 20 | 20 | reconciled |
| Juvenile Court | 42 | 42 | reconciled |
| Probate and Family Court | 19 | 19 | reconciled |
| Land Court | 1 | 1 | reconciled |
| Appeals Court | 1 physical location / 2 semantic records | 2 | reconciled |
| Supreme Judicial Court | 1 | 1 | reconciled |

Primary roster sources:

- District: https://www.mass.gov/orgs/district-court/locations
- Housing: https://www.mass.gov/orgs/housing-court/locations
- BMC: https://www.mass.gov/orgs/boston-municipal-court/locations
- Superior: https://www.mass.gov/orgs/superior-court/locations
- Juvenile: https://www.mass.gov/orgs/juvenile-court/locations
- Probate and Family: https://www.mass.gov/orgs/probate-and-family-court/locations
- Land: https://www.mass.gov/orgs/land-court
- Appeals: https://www.mass.gov/orgs/appeals-court
- SJC: https://www.mass.gov/orgs/massachusetts-supreme-judicial-court
- MassGIS courthouse metadata: https://www.mass.gov/info-details/massgis-data-courthouses

All current records now carry `address_verified: "2026-09-03"` and an
`address_source` pointing either to the individual court page or the relevant
department directory.

## Material corrections

### District Court

**Winchendon District Court is no longer a current filing court.** The Trial
Court states that Gardner and Winchendon were consolidated into Gardner
District Court pursuant to St. 2025, c. 9. The current District roster contains
61 locations. The Winchendon record was moved to `historical_courts.json` so
old docket code 70 can still be documented without presenting Winchendon as a
current filing location.

Source:
https://www.mass.gov/locations/gardner-district-court

Gardner's service description was updated to include Ashburnham, Gardner,
Hubbardston, Petersham, Phillipston, Royalston, Templeton, Westminster, and
Winchendon.

**Fall River District Court** was updated from the former 5th-floor / 02720
record to the current address:

> 186 S. Main St., 2nd Floor, Fall River, MA 02721

Source:
https://www.mass.gov/locations/fall-river-district-court

**Springfield District Court** now separates the physical court address from
the mailing address:

- Physical: 50 State St., Springfield, MA 01103
- Mailing: 50 State Street, Springfield, MA 01102

Source:
https://www.mass.gov/locations/springfield-district-court

### Housing Court

**Metro South Housing Court – Stoughton Session** was missing and has been
added. It sits at:

> 1288 Central St., Stoughton, MA 02072

The session serves Stoughton only and sits on the second Friday of each month.
Mass.gov expressly directs *all filings and correspondence* to the Canton
session at 35 Shawmut Road, Canton, MA 02021, so MACourts stores both the
hearing location and the filing address.

Source:
https://www.mass.gov/locations/metro-south-housing-court-stoughton-session

Other Housing corrections include:

- Metro South Brockton ZIP corrected to 02301.
- Eastern Housing Court's official location identity recorded as
  **Eastern Housing Court - Boston Session**, while preserving the semantic
  court name for backwards compatibility.
- Northeast Housing Court Lynn and Salem structured addresses corrected to
  56 Federal St., Salem, MA 01970.
- Chelsea's malformed city/county/address fields corrected.
- Central Dudley, Leominster, and Marlborough city fields normalized.
- Current contact data refreshed for Boston, Canton, Lowell, Lynn, Salem,
  Woburn, and Barnstable.
- Barnstable now records that filings/correspondence go to New Bedford.

Sources:
https://www.mass.gov/locations/eastern-housing-court-boston-session
https://www.mass.gov/locations/northeast-housing-court-lynn-session
https://www.mass.gov/locations/northeast-housing-court-salem-session
https://www.mass.gov/locations/southeast-housing-court-barnstable-session
https://www.mass.gov/locations/metro-south-housing-court-brockton-session

### Boston Municipal Court

All eight BMC physical locations reconcile with the current BMC roster.
The Central Division structured city was normalized to Boston, with
Edward W. Brooke Courthouse retained as the building name. Brighton's current
phone prompt was also refreshed.

Source:
https://www.mass.gov/orgs/boston-municipal-court/locations

### Superior Court

All 20 current physical locations are present. The old data flattened several
distinct sessions to the same countywide semantic court name. MACourts now
preserves the semantic `name` while adding a distinct `location_name` for:

- Bristol County Superior Court-Fall River
- Bristol County Superior Court-New Bedford
- Essex County Superior Court - Lawrence
- Essex County Superior Court - Newburyport
- Middlesex County Superior Court - Lowell
- Plymouth County Superior Court - Brockton

This is important for filing/location UX without changing the existing
countywide matching API.

Address corrections include:

- Bristol/Fall River ZIP: 02721.
- Hampden physical address: 50 State St., Springfield, MA 01103, with mailing
  P.O. Box 559, Springfield, MA 01102 stored separately.
- Nantucket: 16 Broad St., Nantucket, MA 02554, Nantucket County.
- Plymouth's county corrected to Plymouth County.

**Plymouth ZIP discrepancy:** the current Superior Court page displays
`52 Obery St., Plymouth, MA 02630`. Current Probate, Juvenile, District-related,
and Law Library pages for the same 52 Obery St. building use **02360**.
MACourts uses 02360 and records this discrepancy in the court record rather
than propagating the apparent Mass.gov typo.

Sources:
https://www.mass.gov/locations/hampden-county-superior-court
https://www.mass.gov/locations/nantucket-county-superior-court
https://www.mass.gov/locations/plymouth-county-superior-court
https://www.mass.gov/locations/plymouth-probate-and-family-court
https://www.mass.gov/locations/plymouth-juvenile-court
https://www.mass.gov/locations/plymouth-district-court

### Juvenile Court

The old JSON contained 43 rows while the current Juvenile directory contains
42 locations. The extra row was a duplicate **Springfield Juvenile Court** with
court code `J23`. The Trial Court code listing identifies Springfield Juvenile
Court as `J69`; the J69 row was kept and the J23 duplicate removed.

Other corrections include:

- Barnstable mailing P.O. Box updated to 1209.
- Brockton unit added: #270.
- Edgartown removed stale "Unit 4" and stores PO Box 550 as mailing address.
- Boston and Milford physical/mailing fields separated.
- Newburyport structured address normalized.
- Current phone data refreshed for Chelsea, Falmouth, Springfield, Stoughton,
  and West Roxbury.

Sources:
https://www.mass.gov/orgs/juvenile-court/locations
https://www.mass.gov/info-details/trial-court-codes-court-location-listing
https://www.mass.gov/locations/brockton-juvenile-court
https://www.mass.gov/locations/barnstable-juvenile-court
https://www.mass.gov/locations/springfield-juvenile-court

### Probate and Family Court

All 19 primary Probate and Family Court locations reconcile with the current
department directory. Current official location identities are stored for the
Middlesex North/Lowell and South/Woburn locations without changing the existing
semantic matching names.

The following satellite locations are now represented as satellite metadata,
not as independent courts:

- **Suffolk / Chelsea:** Chelsea District Court, 120 Broadway, Chelsea, MA
  02150; Tuesday-Thursday, 8:30 a.m.-3:00 p.m.
- **Hampshire / Belchertown:** Eastern Hampshire District Court, 205 State St.,
  Route 202, Belchertown, MA 01007; first and third Thursday, 9:00 a.m.-noon.
- **Hampden / Chicopee:** Chicopee City Hall, 274 Front Street, Chicopee, MA
  01013; Mass.gov says it has been temporarily closed for renovations since
  November 1, 2024.

Sources:
https://www.mass.gov/locations/suffolk-probate-and-family-court
https://www.mass.gov/locations/hampshire-probate-and-family-court
https://www.mass.gov/locations/hampden-probate-and-family-court

### Land, Appeals, and SJC

- Land Court: 3 Pemberton Square, 5th floor, Boston, MA 02108.
- Appeals Court: John Adams Courthouse, One Pemberton Square, Room 1200,
  Boston, MA 02108.
- Supreme Judicial Court: John Adams Courthouse, 1 Pemberton Square,
  Suite 2500, Boston, MA 02108.

Sources:
https://www.mass.gov/orgs/land-court
https://www.mass.gov/orgs/appeals-court
https://www.mass.gov/orgs/massachusetts-supreme-judicial-court

## Locations discovered but not modeled as independent filing courts

Some current Mass.gov pages expose part-time/satellite locations that should
not automatically become standalone filing targets:

- Stoughton Housing Court is a real hearing session, but filings go to Canton.
  It **is** included as a Housing location because the Housing department
  directory counts it among its 24 sessions.
- Probate satellite offices are attached to their parent Probate court and are
  **not** part of the 19-location Probate directory; they are stored as
  satellite metadata instead.
- Hampden's Chicopee Probate satellite is currently closed.
- Superior county courts with multiple buildings are represented with
  `location_name` rather than being collapsed to a single physical address.

## Filing location versus appearance location metadata

The location audit exposed a distinction that is important to both consumers of
this package:

- docassemble interviews often need to tell a litigant **where to appear** and
  separately **where papers must be filed or mailed**;
- LITEFile primarily needs the filing destination, while an appearance location
  is useful corroborating information that can help the filer confirm they have
  selected the right court.

MACourts therefore uses the following metadata on court records:

- `location_name`: durable human-facing identity of the physical/session
  location. This is separate from the semantic `name` when one countywide
  court has several buildings or sessions.
- `accepts_filings`: whether that physical/session location itself accepts
  filings/correspondence. It defaults to `true` for ordinary court records.
- `filing_location`: the `location_name` of the canonical filing destination
  when `accepts_filings` is false.
- `appearance_locations`: reverse cross-reference from a filing location to
  the session(s) where a case filed through it may be heard.
- `filing_address`: an alternate filing/correspondence address when the
  appearance location and filing location differ.

Examples verified in this audit:

- **Metro South Housing Court - Stoughton Session**
  - `accepts_filings: false`
  - `filing_location: "Metro South Housing Court - Canton Session"`
  - appearance/hearing location: 1288 Central St., Stoughton
  - filing/correspondence location: 35 Shawmut Road, Canton
- **Southeast Housing Court - Barnstable Session**
  - `accepts_filings: false`
  - `filing_location: "Southeast Housing Court - New Bedford Session"`
  - filings/correspondence are directed to New Bedford.

The reverse filing records list those appearance sessions in
`appearance_locations`.

### Why this is not called `fileable`

The package deliberately does **not** use a static `fileable` boolean as a
synonym for Tyler e-filing support. LITEFile already uses Tyler's
`fileable_only` API parameter, and live e-filing availability can depend on
filing phase, category, case type, filing type, and Tyler environment.

In fact, current LITEFile code fetches the full named court catalog with
`fileable_only=False` because Tyler's court-level `fileable_only` filter can
omit courts that nevertheless have valid fileable categories (the code
specifically calls out Cambridge District Court). LITEFile then verifies the
selected hierarchy through the category/type endpoints.

So:

- `accepts_filings` = court-administration fact about the physical/session
  location;
- live EFSP "fileability" = runtime Tyler taxonomy fact that LITEFile must query.

Source code:
https://github.com/SuffolkLITLab/LITEFile/blob/main/efile_app/efile/services/taxonomy_classification.py

## Tyler / EFSP court-code provenance and maintenance

The legacy data contains several identifiers that look similar but were
obtained differently and have different meanings.

### 1. `court_code`: Massachusetts Trial Court / docket code

This is the Massachusetts court code used in docket numbers (for example,
District Court code 70 for the now-retired Winchendon District Court). It is
not the Tyler e-filing location identifier.

Current public Trial Court code listing:
https://www.mass.gov/info-details/trial-court-codes-court-location-listing

Historical court codes may remain useful after a court closes or consolidates,
which is why retired locations should be kept separately from the current
filing-location roster.

### 2. `tyler_code`: Tyler / EFSP court route key

The original project did not infer these from Mass.gov. Closed PR #45 documents
that District and BMC Tyler codes were retrieved from the Suffolk e-file proxy:

https://github.com/SuffolkLITLab/docassemble-MACourts/pull/45

The endpoint used at the time was:

`/jurisdictions/massachusetts/codes/courts?with_names=True`

and the PR specifically references:

https://efile-test.suffolklitlab.org/jurisdictions/massachusetts/codes/courts?with_names=True

The current LITEFile implementation still uses the same family of live proxy
endpoints:

- `GET /jurisdictions/{jurisdiction}/codes/courts/`
- parameters: `fileable_only=False`, `with_names=True`
- then:
  - `/codes/courts/{court}/categories`
  - `/case_types/`
  - `/filing_types/`

Current implementation:
https://github.com/SuffolkLITLab/LITEFile/blob/main/efile_app/efile/services/taxonomy_classification.py

The practical maintenance procedure for a Tyler route key is therefore:

1. Query the **target environment** (staging or production) through the e-file
   proxy for all named Massachusetts courts.
2. Match the Tyler label to the durable MACourts filing/location identity.
   Do not use the numeric/string route key itself as the durable identity.
3. For the intended filing phase, confirm that the selected route exposes the
   expected fileable category/case-type/filing-type hierarchy.
4. Record the observed route key with the environment, source, and verification
   date.
5. If a Trial Court session exists but Tyler has no separate route for it,
   leave the Tyler key null and cross-reference the canonical filing location
   rather than inventing a code.

This last rule is especially relevant to **Stoughton Housing Court**.

### Tyler route keys can and do change

PR #74 documents a production problem that required changing the Metro South
Housing `tyler_code` from `1550` to `1265`:

https://github.com/SuffolkLITLab/docassemble-MACourts/pull/74

The current LITEFile checked-in Tyler staging catalog from August 2026 provides
another warning against treating these keys as permanent identities. It has no
separate Canton or Stoughton entry and no route `1265`; it still exposes:

- `Southeast Housing Court - Brockton` -> `555:BR`

Snapshot:
https://github.com/SuffolkLITLab/LITEFile/blob/main/benchmarking/promptfoo/data/tyler_catalog/massachusetts/courts.json

The LITEFile benchmarking code itself describes numeric Tyler values as dated
route-key observations rather than durable "gold" identities.

Because `1265` was maintained from a production incident while the August
2026 checked-in staging catalog shows `555:BR`, the Metro South values in
MACourts are now explicitly marked **needs re-verification**. This may reflect
a stage/production difference, a Tyler rename, or a later routing change.

### 3. `tyler_lower_court_code` and `tyler_prod_lower_court_code`

These are a separate Tyler concept used when filing an Appeals Court matter:
Tyler requires a "lower court" code identifying the court being appealed from.
They are **not** the same as `tyler_code`.

PR #38 records how the project discovered them after Tyler confirmed the values
were not publicly documented:

https://github.com/SuffolkLITLab/docassemble-MACourts/pull/38

The procedure was:

1. Log in to Tyler File & Serve for the target environment:
   - stage: `https://massachusetts-stage.tylertech.cloud/ofsweb/`
   - production: `https://massachusetts.tylertech.cloud/ofsweb/`
2. Under **New Filing**, choose **Start a new case**.
3. Open browser developer/network tools.
4. Select **Appeals Court (Single Justice)** as the filing location.
5. Find the request to `GetEnvelopeCodeConfigs`.
6. Read the returned JSON at:
   `obj["DropDownsLocation"]["LowerCourtCodes"]`.

The legacy README records the stage request as:

`/OfsWeb/FileAndServeModule/Envelope/GetEnvelopeCodeConfigs?isLocationChanged=true&locationId=120`

A stale or missing value typically surfaces as Tyler error:

`168, Lower court code not found`

PR #71 later established a separate production field because production and
stage returned different lower-court-code values:

https://github.com/SuffolkLITLab/docassemble-MACourts/pull/71

PR #74 notes that the values happened to match again when it was checked, but
that should not be assumed permanently.

PR #105 documents another important edge case: Tyler's lower-court list had not
caught up with the Metro South Housing reorganization, so the project reused
the old Southeast Housing lower-court code based on Trial Court communication:

https://github.com/SuffolkLITLab/docassemble-MACourts/pull/105

That should be treated as an explicitly documented compatibility workaround,
not evidence that Tyler's labels and current Massachusetts court organization
are always one-to-one.

### Recommended identifier policy going forward

For MACourts/LITEFile:

- use `location_name` + filing relationships as the durable local identity;
- use `court_code` for Massachusetts docket/history semantics;
- treat `tyler_code` as a dated environment-specific EFSP route-key
  observation;
- query live Tyler taxonomy before LITEFile actually offers an e-filing target;
- keep stage and production lower-court codes distinct unless both have been
  independently verified to match;
- do not guess codes for newly discovered sessions;
- record provenance whenever a Tyler value is changed.

## Remaining follow-up

1. Re-verify the Metro South Housing Tyler route in both staging and production.
   The legacy value `1265` conflicts with the August 2026 LITEFile staging
   snapshot, which still exposes `Southeast Housing Court - Brockton` as
   `555:BR`.
2. Confirm whether Stoughton has any independent Tyler route in production. If
   it does not, keep it as an appearance-only location that files through the
   canonical Metro South filing route.
3. Add explicit Tyler provenance fields (`source`, `environment`,
   `verified_on`) the next time each legacy route key is independently
   refreshed.
4. Periodically rerun the roster-count, address, filing-location, and Tyler
   crosswalk audits; these datasets change on different schedules.
