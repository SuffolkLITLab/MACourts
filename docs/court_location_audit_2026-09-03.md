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

## Remaining follow-up

1. Verify EFSP/Tyler identifiers for the newly added Stoughton Housing session.
   No current authoritative public source was found for a session-specific
   Tyler identifier, so MACourts intentionally leaves those fields null rather
   than guessing.
2. Decide how LITEFile should present part-time hearing sessions when the
   official filing/correspondence address is a different session.
3. Periodically rerun the roster-count and address audit; court session data
   changes more frequently than the old scrape cadence captured.
