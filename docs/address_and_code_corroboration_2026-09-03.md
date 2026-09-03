# Court address and code corroboration — 2026-09-03

This is a second-source check of the September 2026 MACourts location audit. It was prompted by a known limitation: Mass.gov is often the best available current roster, but individual court pages and code tables can contain stale or incorrect details.

The goal here is to distinguish:

- **current court/session existence**;
- **MassCourts docket/site codes**;
- **physical court address**;
- **mailing/filing address**;
- **Tyler/EFSP route keys**.

Those are related but are not interchangeable.

## Court-code findings

### The consolidated Mass.gov code list is not a current-location roster

The public `Trial Court codes - Court location listing` says it was last updated March 19, 2021. It still contains closed or historical locations, including Winchendon District Court code 70. It should therefore be used as a historical/docket-code registry, not as proof that a court remains an active filing location.

For current docket-code semantics, the department-specific case-number-format pages are better sources:

- District Court: https://www.mass.gov/info-details/district-court-get-to-know-the-case-number-format
- Boston Municipal Court: https://www.mass.gov/info-details/boston-municipal-court-get-to-know-the-case-number-format
- Housing Court: https://www.mass.gov/info-details/housing-court-get-to-know-the-case-number-format
- Superior Court: https://www.mass.gov/info-details/superior-court-get-to-know-the-case-number-format
- Probate and Family Court: https://www.mass.gov/info-details/probate-and-family-court-get-to-know-the-case-number-format
- Land Court: https://www.mass.gov/info-details/land-court-get-to-know-the-case-number-format

The normalized crosswalk is stored in `macourts/data/court_code_crosswalk.json`.

### District Court

The current District case-number format agrees with MACourts' active District codes. Gardner is code **63**. Winchendon code **70** remains historically meaningful but does not imply a current Winchendon filing location after the 2025 consolidation.

### Boston Municipal Court

The current BMC format confirms the eight division codes:

- Central 01
- Roxbury 02
- South Boston 03
- Charlestown 04
- East Boston 05
- West Roxbury 06
- Dorchester 07
- Brighton 08

These agree with MACourts.

### Housing Court

The current Housing Court case-number page defines division-level codes, not separate codes for each hearing session:

- Eastern H84
- Central H85
- Metro South H82
- Northeast H77
- Southeast H83
- Western H79

That means Brockton, Canton, and Stoughton are all **H82** for MassCourts docket identity even though they are distinct physical/session locations. MACourts now records Stoughton as H82 while keeping its Tyler route key null because no separate Tyler route was verified.

### Superior Court

The current Superior format confirms county-level codes 72 through 85. Multiple physical sessions in the same county share the county docket code; for example Bristol's Taunton, Fall River, and New Bedford locations are all Bristol/73. This supports keeping `location_name` separate from semantic/docket identity.

### Probate and Family Court

This is the largest semantic mismatch in the legacy data.

The old JSON stores `court_code` values such as `P72`, `P73`, etc. Those appear in the older Trial Court location-code registry, but current Probate docket numbers use two-letter **site prefixes**, for example:

- Barnstable BA
- Berkshire BE
- Bristol BR
- Dukes DU
- Essex ES
- Franklin FR
- Hampden HD
- Hampshire HS
- Middlesex MI
- Nantucket NA
- Norfolk NO
- Plymouth PL
- Suffolk SU
- Worcester WO

MACourts therefore treats the existing P72-P85 values as legacy location-code metadata and documents the current docket prefix separately in `court_code_crosswalk.json` rather than silently redefining the legacy field.

### Land Court

Land Court case numbers do not contain a court-location/site code. They are formatted as year + case type + sequence. A synthetic Land Court `court_code` should not be invented merely for schema uniformity.

### Juvenile Court

The 2021 Trial Court registry contains both current and historical/alternate Juvenile codes. In particular, Springfield appears as both **J23** and **J69** in the published registry. MACourts' one-physical-location model is preferable: keep one Springfield court record, use J69 as primary, and preserve J23 as an alias for old docket interpretation.

## Address corroboration outside Mass.gov

### Plymouth Superior Court — 52 Obery St., Plymouth, MA 02360

**Confidence: high.**

Mass.gov's Superior page currently shows ZIP `02630`, which is a Barnstable ZIP and conflicts with other sources for the exact same building.

Independent corroboration for **02360**:

1. Plymouth County government lists its Clerk of Courts at `Plymouth Trial Court, 52 Obery Street, Suite 2041, Plymouth 02360`:
   https://www.plymouthcountyma.gov/home/files/plymouth-county-booklet-2021-2022
2. The Town of Plymouth FY2026 assessment identifies `52 OBERY ST` as Commonwealth of Massachusetts state property in Plymouth:
   https://www.plymouth-ma.gov/DocumentCenter/View/142/FY2026-Real-Estate-Assessment-by-Parcel-ID-PDF
3. Plymouth County District Attorney directions identify the Plymouth Trial Court building as `52 Obery Street, Plymouth, MA 02360`:
   https://plymouthda.com/directions/plymouth-district-court/
4. Waze and business/location datasets geocode 52 Obery St as Plymouth MA 02360.

There are also third-party court directories that repeat the Superior-specific `02630` value, so this is a good example of a typo propagating from an official source. The property, county-government, and same-building evidence strongly favors 02360.

### Springfield District Court — physical address 50 State St., Springfield, MA 01103

**Confidence: high.**

Independent corroboration:

1. City of Springfield's own government site identifies Springfield District Court at 50 State St. and separately uses 01102 for the P.O.-box/mailing address:
   https://www.springfield-ma.gov/cos/contact-us
2. Massachusetts public-official financial-interest filings for Springfield District Court personnel identify their public position at `50 State Street, Springfield, MA 01103` (indexed by StateReference):
   https://sfi.statereference.com/
3. Current map/business data identifies Springfield District Court at 50 State St., Springfield MA 01103.

This supports keeping physical ZIP 01103 separate from mailing ZIP 01102.

### Nantucket County Superior Court — 16 Broad St., Nantucket, MA 02554

**Confidence: high.**

Independent corroboration:

1. An actual 2024 Trial Court Clerk's Notice, publicly hosted outside Mass.gov, gives the court name and address as `Nantucket County Superior Court, 16 Broad Street, P.O. Box 967, Nantucket, MA 02554`:
   https://img1.wsimg.com/blobby/go/8aee19b0-e21b-418f-901d-5be8fc9174b1/2275CV00025%20Clerk%27s%20Notice%20%28eDoc%29-407499850.pdf
2. Current map/business data places Nantucket County Superior Court at 16 Broad St., Nantucket MA 02554.

Some directories contain a `02544` typo. The court-generated notice and geocoded location support 02554.

### Edgartown Juvenile Court — 12 Mariner's Way, Unit 4; P.O. Box 550

**Confidence: high.**

The first Mass.gov-only pass removed `Unit 4`. That was too aggressive.

Independent sources support restoring it:

1. Dukes County government's court page lists `PO Box 550 (12 Mariner's Way, Unit 4), Edgartown, MA 02539`:
   https://www.dukescounty.gov/DCCourts
2. CourtReference independently lists `12 Mariner's Way, Unit 4, PO Box 550`:
   https://www.courtreference.com/courts/21533/edgartown-juvenile-court

MACourts now keeps the physical unit and mailing box separately.

### Brockton Juvenile Court — 215 Main Street, Suite 270, Brockton MA 02301

**Confidence: high.**

A June 2026 summons by publication, reproducing a Trial Court Juvenile Court notice in a local newspaper, gives `Plymouth County Juvenile Court, 215 Main Street, Suite 270, Brockton, MA 02301`:
https://wareham.theweektoday.com/node/157950

That is stronger evidence than a generic directory because it is a current court-generated notice republished by an independent outlet.

### Salem/Lynn Northeast Housing sessions — 56 Federal St., Salem MA 01970

**Confidence: high for building; high for current session use when combined with current court roster.**

Independent corroboration:

1. A Massachusetts Legislature task-force report identifies the J. Michael Ruane Judicial Center at `56 Federal Street, Salem MA 01970` and explicitly lists **Housing Court** among the departments using the facility:
   https://malegislature.gov/Bills/189/SD2144.pdf
2. Independent court directories also identify the Northeast Housing Salem/Lynn sessions at 56 Federal Street.

This supports correcting malformed legacy structured addresses that had the Lynn/Salem session location wrong.

### Stoughton Housing session — 1288 Central St., Stoughton MA 02072

**Confidence: medium-high for the hearing location; high that filings go elsewhere.**

Outside Mass.gov, Stoughton District Court is consistently located at the same `1288 Central St.` courthouse, including independent court directories. That corroborates the physical building. However, independent sources specifically naming the *new Housing session* at that building are sparse, which is expected for a part-time/newer session.

Because the session's filing destination is Canton and the Tyler catalog does not expose a separate verified Stoughton route, MACourts treats Stoughton as an appearance/hearing location and does not infer an independent Tyler filing identity.

### Fall River District Court — 186 S. Main St.; floor/ZIP change

**Confidence: high for the building and ZIP 02721; medium for the 2nd-floor change.**

The old data said `5th Floor, 02720`. The current Mass.gov page says `2nd Floor, 02721`.

Independent evidence is mixed:

Evidence supporting **02721**:

1. Property-record data for the state-owned parcel identifies `186 S Main St, Fall River, MA 02721`:
   https://www.loopnet.com/property/186-s-main-st-fall-river-ma-02721/25005-002833538/
2. A Trial Court facility report identifies the Fall River Trial Court at 186 South Main Street, Fall River MA 02721.
3. Current practitioner guidance from a Massachusetts criminal-defense attorney lists `186 S. Main St., 2nd Floor, Fall River, MA 02721`:
   https://www.kevinrcollinslaw.com/fall-river-district-court/

Evidence still showing the older **5th Floor / 02720** form includes Waze, CourtReference, WomensLaw, and the August 2025 MassLegalHelp directory.

Conclusion: the building and 02721 ZIP are well supported. The floor change appears recent and is not yet consistently propagated outside the Trial Court. Keep the current 2nd-floor value, but treat the floor as a recent/medium-confidence operational detail that should be rechecked rather than as immutable location identity.

## Evidence policy going forward

For a material address change, prefer at least two independent signals where feasible:

1. current Trial Court/Mass.gov location page;
2. a court-generated notice, summons, docket artifact, jury notice, or filing instruction;
3. city/county government or property-record evidence for the physical building;
4. a current legal-aid/bar/practitioner directory;
5. map/business geocoding as corroboration, not sole authority.

If those conflict:

- preserve the dispute in metadata/audit notes;
- separate physical, mailing, filing, and appearance addresses instead of forcing one string;
- avoid changing a floor/unit/P.O.-box detail on Mass.gov evidence alone;
- prefer court-generated case documents and local government property/address evidence over generic scraped directories;
- date the verification so later maintainers know when to recheck it.
