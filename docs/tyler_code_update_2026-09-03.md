# Tyler E-Filing Court Code Ingestion & Audit — 2026-09-03

- **Date & Time:** 2026-09-03 22:03:04 EDT
- **Author/Agent:** Antigravity AI (Suffolk LIT Lab Pair Programming)
- **Source Endpoints:**
  - Production (Live): `https://efile.suffolklitlab.org/jurisdictions/massachusetts/codes/courts?with_names=True` (Proxy API v1.4.0, commit `efd1857`)
  - Development (Test): `https://efile-test.suffolklitlab.org/jurisdictions/massachusetts/codes/courts?with_names=True` (Proxy API v1.4.0, commit `bbb9155`)

---

## Overview

This update ingests verified Tyler Odyssey / EFM court location identifiers (`tyler_code`) into MACourts packaged dataset files where `tyler_code` was previously unpopulated or `null`.

Before this update, only `district_courts.json`, `bmc.json`, `appeals_court.json`, `supreme_judicial_court.json`, and parts of `housing_courts.json` had populated `tyler_code` attributes. `probate_and_family_courts.json`, `superior_courts.json`, `land_court.json`, and `juvenile_courts.json` carried `court_code` but lacked explicit Tyler route keys.

---

## Dataset Updates Applied

### 1. Land Court (`macourts/data/land_court.json`)
- **Records Updated:** 1
- **Assigned Tyler Code:** `"210"`
- Verified identical in both Prod and Dev endpoints; active for initial and subsequent filings.

### 2. Probate and Family Court (`macourts/data/probate_and_family_courts.json`)
- **Records Updated:** 19 (across all 14 county divisions)
- **Assigned Tyler Codes:**
  - Barnstable (`P72`): `"335"`
  - Berkshire (`P76`): `"341"`
  - Bristol (`P73` — Taunton, Fall River, New Bedford): `"350"`
  - Dukes (`P74`): `"337"`
  - Essex (`P77` — Salem, Lawrence): `"352"` (Active Dev pilot)
  - Franklin (`P78`): `"303"`
  - Hampden (`P79`): `"342"`
  - Hampshire (`P80`): `"343"`
  - Middlesex (`P81` — Cambridge, Lowell): `"344"`
  - Nantucket (`P75`): `"345"`
  - Norfolk (`P82`): `"346"`
  - Plymouth (`P83` — Plymouth, Brockton): `"347"`
  - Suffolk (`P84`): `"339"`
  - Worcester (`P85`): `"348"`

### 3. Superior Court (`macourts/data/superior_courts.json`)
- **Records Updated:** 20 (across all 14 county locations/sessions)
- **Assigned Tyler Codes:**
  - Barnstable (`72`): `"1165"`
  - Berkshire (`76`): `"1179"`
  - Bristol (`73` — Taunton, Fall River, New Bedford): `"1126"` (Active Dev pilot)
  - Dukes (`74`): `"1175"`
  - Essex (`77` — Salem, Lawrence, Newburyport): `"1177"`
  - Franklin (`78`): `"1178"`
  - Hampden (`79`): `"1181"`
  - Hampshire (`80`): `"1180"`
  - Middlesex (`81` — Cambridge, Lowell): `"1176"` (Active Dev pilot)
  - Nantucket (`75`): `"1185"`
  - Norfolk (`82`): `"1196"`
  - Plymouth (`83` — Plymouth, Brockton): `"1186"`
  - Suffolk (`84`): `"1235"`
  - Worcester (`85`): `"1195"`

### 4. Juvenile Court (`macourts/data/juvenile_courts.json`)
- **Records Updated:** 42 records mapped to the 36 Tyler session filing routes:
  - Barnstable County: Barnstable (`1036:BA`), Falmouth (`1036:FA`), Martha's Vineyard / Edgartown (`1036:MV`), Nantucket (`1036:NK`), Orleans (`1036:OL`), Plymouth session under Barnstable (`1036:PY`)
  - Berkshire County: Great Barrington (`985:GB`), North Adams (`985:NA`), Pittsfield (`985:PT`)
  - Bristol County: Attleboro (`1015:AT`), Fall River (`1015:FV`), New Bedford (`1015:NE`), Taunton (`1015:TN`)
  - Essex County: Lawrence (`705:LA`), Lynn (`705:LY`), Newburyport (`705:NP`), Salem (`705:SA`)
  - Franklin-Hampshire County: Belchertown (`965:BE`), Greenfield (`965:GF`), Hadley (`965:HA`), Orange (`965:OG`)
  - Hampden County: Holyoke (`986:HO`), Springfield (`986:SP`), Palmer (`986:SP` filing route)
  - Middlesex County: Cambridge (`1095:CA`), Framingham (`1095:FH`), Lowell (`1095:LO`), Waltham (`1095:CA` session)
  - Norfolk County: Dedham (`885:DE`), Quincy (`885:DE` filing route), Stoughton (`null` — appearance-only, filings to Dedham)
  - Plymouth County: Brockton (`1037:BK`), Hingham (`1037:HI`), Wareham (`1037:WH`)
  - Suffolk County: Boston (`1086:BO` — Dev pilot), Chelsea (`1086:BO` filing route), Dorchester (`1086:BO` filing route), West Roxbury (`1086:BO` filing route)
  - Worcester County: Dudley (`915:DU`), Fitchburg (`915:FI`), Leominster (`915:LE`), Milford (`915:MI`), Worcester (`915:WC`)

### 5. Crosswalk Updates (`macourts/data/court_code_crosswalk.json`)
- Updated to document the direct Tyler codes and API endpoint sources alongside Trial Court case-number codes and legacy location codes.

---

## Tyler Environment Differences Summary

1. **Juvenile Zero-Padding Discrepancy:**
   - Prod codes omit leading zero: `705:LA`, `885:DE`, `915:FI`, `965:BE`, `985:GB`, `986:HO`.
   - Dev/Test codes include leading zero: `0705:LA`, `0885:DE`, `0915:FI`, `0965:BE`, `0985:GB`, `0986:HO`.
   - Dudley `915:DU` has no leading zero in either environment.
2. **Superior Court Availability:**
   - Prod contains all 14 county Superior Court locations (`1126`, `1165`, `1175`, `1176`, `1177`, `1178`, `1179`, `1180`, `1181`, `1185`, `1186`, `1195`, `1196`, `1235`).
   - Dev contains only Bristol (`1126`) and Middlesex (`1176`).
3. **Housing Court Metro South:**
   - Prod contains Metro South (`1265`) and Southeast Barnstable (`555:CI`). Dev lacks these two nodes.
4. **Dev Fileability Flags:**
   - In Prod, 152 of 164 courts are open for filings (`initial=True, subsequent=True`).
   - In Dev, only select pilot courts are fileable (`initial=True, subsequent=True`), while other courts remain configured with `initial=False, subsequent=False`.
