# Jurisdiction test contracts

`fixtures/jurisdiction_cases.json` is the human-reviewable behavioral contract for court matching.

## Status values

- **contract** — intended behavior. If the department matcher exists in shared MACourts, the test must pass exactly.
- **review** — legacy behavior and packaged source data are ambiguous or contradictory. These cases are intentionally *not* frozen as exact behavior until we decide what result users should see.

The current suite contains representative and edge cases for every court department. BMC and statewide court cases run against the shared implementation now. District, Housing, Superior, Probate & Family, and Juvenile cases are marked expected-failure until those matchers are ported; when a matcher is added, wire it into `run_implemented_matcher()`.

BMC coordinates are stable interior points derived from the packaged `boston_wards.geojson`, plus Winthrop, negative cases, and a nearest-polygon fallback point. The purpose is to catch geometry/data changes that silently move an address into a different BMC division.

Concurrent-jurisdiction cases deliberately compare the whole result set rather than just checking that one court is present.


## External evidence

When a jurisdiction rule is disputed or stale, record the supporting official sources in
`fixtures/jurisdiction_evidence.md` and add source URLs / a verification date to the
specific contract case. Bellingham and Freetown are the first examples of this audit trail.
