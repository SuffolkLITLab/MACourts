# Jurisdiction rules

Every Massachusetts Trial Court department except the Boston Municipal Court
decides venue from the *municipality* of an address — sometimes with a county
fallback, occasionally with a Boston neighborhood. Those assignments live in
`macourts/data/jurisdiction_rules.json` rather than in Python, so they can be
diffed against Mass.gov when the Trial Court publishes a change.

## What the file contains

| Department | Rules | Courts named | Selection |
| --- | --- | --- | --- |
| District Court | 62 | 61 | `all` |
| Housing Court | 27 | 24 | `first` |
| Juvenile Court | 39 | 39 | `all` |
| Probate and Family Court | 16 | 19 | `all` |
| Superior Court | 14 | 14 | `first` |

Boston Municipal Court venue is geometric (`data/boston_wards.geojson`), and the
Land, Appeals, and Supreme Judicial Courts are statewide, so none of them appear
here.

## Rule shape

```json
{
  "courts": ["Metro South Housing Court - Canton Session"],
  "counties": ["norfolk county"],
  "excluded_cities": ["brookline", "newton"],
  "require_all": true
}
```

- `courts` — the semantic court names this rule returns. More than one name
  means concurrent jurisdiction.
- `cities`, `counties`, `neighborhoods` — place tests, stored casefolded. They
  are **OR**-ed, matching how the Trial Court publishes service areas ("this
  county, plus these towns").
- `require_all` — AND the tests instead. Only correct for a handful of rules,
  such as the two Middlesex Probate divisions, which split one county by town.
- `excluded_cities` — always vetoes, in either mode.
- `neighborhoods` — `{"city": "boston", "names": [...]}`; used for the East
  Boston neighborhoods that are heard in Chelsea.

## Selection modes

`selection` says what happens when several rules in a department match:

- `all` — every matching rule contributes. District, Juvenile, and Probate &
  Family genuinely have concurrent jurisdiction in places (Freetown files in
  either Fall River or New Bedford; Swansea has three Probate sessions).
- `first` — the first matching rule wins. Housing and Superior are ordered
  chains where earlier rules are the specific exceptions to a later county rule.
  Rule order in the file is therefore significant for these two departments.

## Regenerating the file

The rules were lifted mechanically out of the `if`/`elif` chains in
[docassemble-MACourts](https://github.com/SuffolkLITLab/docassemble-MACourts)'s
`macourts.py`:

```bash
python scripts/build_jurisdiction_rules.py \
    --legacy ~/docassemble-MACourts/docassemble/MACourts/macourts.py
```

`scripts/extract_legacy_jurisdiction_rules.py` does the parsing and refuses to
guess: any legacy construct it does not recognize is reported rather than
silently dropped. Two constructs are deliberately *not* turned into rules,
because they are implemented in code instead:

- the "infer Suffolk County when the city is a Boston neighborhood" preamble,
  which the legacy code repeated in each department
  (`Location.with_inferred_county`);
- the two Juvenile sessions whose territory follows BMC division lines
  (`macourts.boston.JUVENILE_DIVISIONS`).

## Corrections applied on top of the legacy data

`scripts/build_jurisdiction_rules.py` holds these in named tables at the top of
the file, each with its reason. They are the *only* behavioral differences from the legacy
chains; a sweep of all 558 municipalities in the packaged ZIP table produces no
others.

### Retired courts

| Was | Now | Why |
| --- | --- | --- |
| Winchendon District Court | Gardner District Court | Consolidated under St. 2025, c. 9. Ashburnham, Phillipston, Royalston, Templeton, and Winchendon now file in Gardner. |

### Misspelled towns

Each of these silently dropped a town out of its court's service list, because
the legacy code compared casefolded string literals:

| Legacy | Corrected | Effect |
| --- | --- | --- |
| `northreading` | `north reading` | North Reading had no Probate & Family match at all |
| `pepperrell` | `pepperell` | Pepperell had no Probate & Family match at all |
| `southamptom` | `southampton` | Southampton matched only through its county |
| `nahunt` | `nahant` | Nahant matched only through its county |
| `middleboro` | `middleborough` | Middleborough was dropped from the Brockton Probate & Family list |
| `county` | *(dropped)* | Not a municipality; a stray entry in the Berkshire housing list |

### Housing Court jurisdiction updates

Verified 2026-09-03; see also
[`tests/fixtures/jurisdiction_evidence.md`](../tests/fixtures/jurisdiction_evidence.md).

- **Bellingham** → Metro South Housing Court - Canton Session. Removed from the
  Central Worcester and Metro South Brockton lists, which no longer name it.
- **The Metro South roster** — Mass.gov now gives the Brockton session six
  towns (Abington, Bridgewater, Brockton, East Bridgewater, West Bridgewater,
  Whitman) and the Canton session the whole of Norfolk County except Brookline.
  The legacy Brockton list carried 34 towns, so 25 Norfolk County towns —
  Quincy, Milton, Braintree, Dedham, Needham and the rest — were answered with
  Brockton instead of Canton, and a stray "Eastham" sent a Cape Cod town there
  too. The Brockton rule sat ahead of the Canton county rule in the `first`
  chain, so it shadowed it.
- **Stoughton** → Metro South Housing Court - Stoughton Session, a session
  Mass.gov now lists separately. Filings and correspondence still go to Canton;
  that is recorded as `accepts_filings` / `filing_location` on the record, not
  as a venue rule.
- **Freetown and Westport** → both the Fall River and New Bedford sessions. Both
  session pages list these towns and the Southeast Division's published
  jurisdiction appendix says either may be used.
- **Gosnold, Tisbury, Truro, and Wellfleet** → Southeast Housing Court -
  Barnstable session. The session serves all of Barnstable, Dukes, and Nantucket
  counties, but the legacy city list named only 19 of their 23 towns, so these
  four fell through to the Plymouth session's over-broad list. The county rule
  ahead of both already covered them; naming them keeps the answer right when a
  caller supplies a contradictory county.
- **`Southeast Housing Court - Barnstable session`** — the packaged catalog
  spells this with a lowercase "session". One canonical spelling is used so
  matches always resolve to a record.

### Alias corrections

Verified 2026-09-03; see also
[`tests/fixtures/jurisdiction_evidence.md`](../tests/fixtures/jurisdiction_evidence.md).

- **Devens** → Ayer. The source spreadsheet lists Devens against all four towns
  whose land the former base spans (Ayer, Harvard, Lancaster, Shirley), which
  made a Devens address return three Housing Court sessions and two counties'
  Superior and Probate courts. Mass.gov routes the whole enterprise zone through
  Ayer, in Middlesex. The override lives in
  `scripts/build_municipality_aliases.py`.
- **Middleborough** → both the Plymouth and Brockton Probate & Family sessions.
  Plymouth County's Probate and Family Court sits in two locations and both
  serve the whole county; the legacy lists split the two spellings of the town
  between them, so each spelling returned a different court.

## Coverage

`tests/test_matching.py` asserts that every court in the packaged catalog which
accepts filings is reachable from some rule, and that every court named by a
rule exists in the catalog.

Sessions that do not accept filings are exempt from the reachability check, but
not necessarily unreachable — the distinction is between *where a matter is
heard* and *where it is filed*. Metro South Housing Court's Stoughton session is
returned for Stoughton addresses and directs its filings to Canton. Stoughton
Juvenile Court is the other case: Mass.gov says cases are heard there "when
scheduled by the court", so no address selects it, and its record points at
Dedham Juvenile Court as the filing location.
