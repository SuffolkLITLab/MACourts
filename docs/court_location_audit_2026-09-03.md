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

## Second-source verification and Mass.gov discrepancies

Mass.gov is the best source for the Trial Court's own current presentation of
its locations, but it is not treated as infallible. For material address
changes in this audit, the preferred standard is:

1. compare the current Mass.gov court page with the previous MACourts value;
2. look for an independent government, court-generated, legal-aid, municipal,
   or reputable court-directory source;
3. preserve a discrepancy note rather than silently overwriting when sources
   conflict;
4. prefer actual court-generated notices or other government records over
   general web directories.

### Court-code registry caveat

The Mass.gov page titled **Trial Court codes - Court location listing** is not a
live-location roster. It says it was last updated **March 19, 2021**:

https://www.mass.gov/info-details/trial-court-codes-court-location-listing

That page remains useful for docket/history semantics, but it contains stale or
ambiguous entries. Two examples matter to MACourts:

- it still lists Winchendon District Court code `70`, even though Winchendon
  has since been consolidated into Gardner. Code 70 is therefore kept as
  historical metadata, not a current filing location;
- it lists **Springfield Juvenile Court twice**, as both `J23` and `J69`.
  MACourts keeps one current Springfield physical location, uses `J69` as its
  primary code, and preserves `J23` as `court_code_aliases` for historical
  docket lookup. We no longer claim that J23 is simply "wrong."

The older code page also omits `H82` for Metro South Housing Court. A newer
June 2025 Housing Court case-number guide explicitly identifies Metro South as
`H82`:

https://www.mass.gov/info-details/housing-court-get-to-know-the-case-number-format

Independent legal-aid materials cite actual Metro South cases such as
`23-H82-SP-1763`, `23-H82-SP-951`, and `22-H82-SP-2338`:

https://www.masslegalhelp.org/es/node/182
https://www.masslegalhelp.org/es/node/183

For that reason, the Stoughton appearance session now carries
`court_code: "H82"` while its separate Tyler/EFSP route remains null and must
be resolved through the Canton filing location.

### Full current-code reconciliation

The current MACourts records were compared against the March 2021 Trial Court
code registry, with newer department-specific sources used where the old
registry is demonstrably stale.

| Department | Reconciliation |
| --- | --- |
| District Court | All 61 current MACourts primary codes are represented in the 2021 registry. Code `70` for Winchendon is preserved only in historical metadata because the physical court has since consolidated into Gardner. |
| Boston Municipal Court | All 8 BMC codes agree. The numerical listing often drops leading zeroes, so `01` and `1` are treated as equivalent representations of the same code. |
| Superior Court | All current county-level codes agree with the registry. Multiple physical sessions within Bristol, Essex, Middlesex, and Plymouth correctly share the same county code. |
| Probate and Family Court | All current `P72` through `P85` county codes agree. Multiple physical locations within one county share the county code. |
| Juvenile Court | Every current MACourts primary code is represented in the registry. Springfield is the exception in interpretation, not presence: the registry lists both `J23` and `J69` for the same Springfield Juvenile Court. MACourts uses one physical record with J69 primary and J23 as an alias. The old registry also contains many juvenile locations that are no longer separate entries in the current Juvenile Court location roster, so those entries are not evidence of missing current courthouses. |
| Housing Court | `H77`, `H79`, `H83`, `H84`, and `H85` agree with the 2021 registry. `H82` (Metro South) is missing from that old page but is explicitly documented in the June 2025 Housing Court case-number guide and appears in real Metro South docket citations. All Metro South sessions, including Stoughton, therefore use divisional court code H82. |
| Land / Appeals / SJC | The legacy JSON fields for these courts are not validated by the Trial Court location-code registry and should not be presented as though they are the same identifier system. Their application/EFSP semantics need separate provenance. |

This comparison reinforces that `court_code`, `tyler_code`, and Tyler's
Appeals lower-court codes must remain distinct fields.

### Address corroboration results

#### Fall River District Court — likely recent intra-building move

Previous MACourts data and several sources that were current through 2025 list:

- 186 S. Main St., **5th Floor**
- Fall River, MA **02720**

Examples:

- Massachusetts Legal Help, *2025 Legal Tactics Directory*:
  https://www.masslegalhelp.org/sites/default/files/2025-08/Directory%20Legal%20Tactics%202025%20-%20Update%208-26-2025.pdf
- WomensLaw courthouse directory:
  https://www.womenslaw.org/find-help/ma/courthouse-locations/all

Current Mass.gov instead says **2nd Floor / 02721**. That newer floor is also
corroborated outside Mass.gov by current Bristol County court-directory pages
and a current Massachusetts criminal-defense directory:

- https://bristolcounty.massachusettscourt.us/court-records.html
- https://www.kevinrcollinslaw.com/fall-river-district-court/

This looks more like a recent move within the same 186 S. Main Street building
than a historical scrape error. MACourts keeps **2nd Floor / 02721**, but the
record carries the source conflict instead of describing the older 5th-floor
data as merely erroneous.

#### Springfield District / Hampden Superior — physical versus mailing ZIP

The audited records separate the physical courthouse at **50 State Street,
Springfield, MA 01103** from mailing addresses using **01102**.

The Massachusetts Secretary of the Commonwealth's *Commissioners to Qualify*
directory independently includes Hampden County Superior Court personnel at
50 State Street, Springfield, MA 01103:

https://www.sec.state.ma.us/divisions/commissions/download/commissioners-to-qualify.pdf

The change is therefore modeled as physical-versus-mailing metadata, not as a
claim that the older 01102 data was wholly wrong.

#### Metro South Housing Court - Brockton — ZIP 02301

The Auditor of the Commonwealth's formal Metro South Housing Court audit is
addressed to:

> 215 Main Street, Suite 160, Brockton, MA 02301

Archive copy:
https://archives.lib.state.ma.us/bitstreams/1a64f099-118c-42b3-b22c-4e17d9630e27/download

That independently supports the audited physical ZIP of **02301**.

#### Northeast Housing Lynn/Salem — 56 Federal Street, Salem

The old JSON contained parser-corrupted values such as `"St. Salem"` and
`"56 Federal"`. CourtReference independently lists the relevant Essex court
locations at 56 Federal Street, Salem, supporting the structured normalization:

https://www.courtreference.com/Essex-County-Massachusetts-Courts.htm

#### Plymouth County Superior Court — Mass.gov ZIP appears wrong

Mass.gov's Superior Court page currently says:

> 52 Obery St., Plymouth, MA **02630**

But Mass.gov's District, Probate, Housing, and Juvenile records for the same
building use **02360**. More importantly for this second-source pass,
CourtReference independently lists Plymouth County Superior Court - Plymouth at:

> 52 Obery Street, Plymouth, MA **02360**

https://www.courtreference.com/Plymouth-County-Massachusetts-Courts.htm

MACourts therefore keeps **02360** and explicitly treats the Superior page's
02630 as a likely Mass.gov typo.

#### Nantucket County Superior Court — 02554

CourtReference independently lists:

> Nantucket County Superior Court, 16 Broad Street, Nantucket, MA 02554

https://www.courtreference.com/Nantucket-County-Massachusetts-Courts.htm

This supports the correction from the old `02544` value to **02554**.

#### Barnstable Juvenile Court — corrected back to P.O. Box 427

This second-source pass found that the earlier audit accepted a likely Mass.gov
error. Mass.gov currently displays:

> P.O. Box **1209**, Barnstable, MA **02630-0427**

The box number and ZIP+4 suffix are internally suspicious. Independent sources
consistently identify the Juvenile Court as **P.O. Box 427**:

- CourtReference:
  https://www.courtreference.com/courts/10362/barnstable-juvenile-court
- RecordsFinder, database updated November 2025:
  https://recordsfinder.com/court/courthouses/ma/barnstable/barnstable/barnstable-juvenile-court/
- an actual Trial Court summons by publication for Barnstable County Juvenile
  Court used `Route 6A, PO Box 427, Barnstable, MA 02630`:
  https://zeta.creativecirclecdn.com/chief/files/20230510-141627-phpoUwxcU.pdf

MACourts now uses **P.O. Box 427** while retaining ZIP+4 `02630-0427`.

#### Edgartown Juvenile Court — restore Unit 4

Mass.gov currently gives 12 Mariner's Way without a unit. Two independent
sources preserve the more specific physical location:

- Dukes County's own court directory:
  https://www.dukescounty.gov/DCCourts
- CourtReference:
  https://www.courtreference.com/courts/21533/edgartown-juvenile-court

Both identify **12 Mariner's Way, Unit 4**, with P.O. Box 550. MACourts now
restores `Unit 4` while keeping the P.O. Box as separate mailing metadata.

#### Brockton Juvenile Court — Suite 270

A June 2026 summons by publication generated for the Trial Court identifies:

> Plymouth County Juvenile Court  
> 215 Main Street, Suite 270  
> Brockton, MA 02301

https://wareham.theweektoday.com/node/157950

That is strong court-generated corroboration for the audited Suite 270 value.

#### Newburyport Juvenile Court — Route 1 / Traffic Circle

CourtReference independently gives:

> 188 State Street, Route 1, Traffic Circle, Newburyport, MA 01950

https://www.courtreference.com/courts/10699/newburyport-juvenile-court

This supports retaining the route/traffic-circle qualifier in structured
address metadata.

#### Land Court — 5th Floor

Boston.gov independently directs taxpayers to:

> Land Court, 3 Pemberton Square, 5th Floor, Boston, MA 02108

https://www.boston.gov/departments/law/what-tax-title-process

This supports the 5th-floor addition.

#### Supreme Judicial Court — Suite 2500

Recent Massachusetts SJC slip opinions reproduced by Justia carry the Reporter
of Decisions contact address at:

> John Adams Courthouse, 1 Pemberton Square, Suite 2500, Boston, MA 02108-1750

Examples:
https://law.justia.com/cases/massachusetts/supreme-court/2026/sjc-13866.html
https://law.justia.com/cases/massachusetts/supreme-court/2026/sjc-13867.html

This independently corroborates the SJC suite/address.

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
