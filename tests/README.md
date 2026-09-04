# Jurisdiction test contracts

`fixtures/jurisdiction_cases.json` is the human-reviewable behavioral contract for court matching.

## Status values

- **contract** — intended behavior. Every department now has a matcher, so a contract case must pass exactly.
- **review** — legacy behavior and packaged source data are ambiguous or contradictory. These cases are intentionally *not* frozen as exact behavior until we decide what result users should see.

The current suite contains representative and edge cases for every court department, and every one of them runs against the shared implementation through `build_default_finder()`. Cases cover concurrent jurisdiction, county-plus-town conjunctions, county exclusions, Boston neighborhood rules, Suffolk County inference for bare neighborhood city names, ZIP-only lookups, and the retired-court and misspelled-town corrections described in [Jurisdiction rules](../docs/jurisdiction_rules.md).

BMC coordinates are stable interior points derived from the packaged `boston_wards.geojson`, plus Winthrop, negative cases, and a nearest-polygon fallback point. The purpose is to catch geometry/data changes that silently move an address into a different BMC division.

Concurrent-jurisdiction cases deliberately compare the whole result set rather than just checking that one court is present.


`tests/test_matching.py` complements this file with unit tests for the rule engine itself, plus the coverage assertions that keep the rule data and the court catalog in sync in both directions.

## External evidence

When a jurisdiction rule is disputed or stale, record the supporting official sources in
`fixtures/jurisdiction_evidence.md` and add source URLs / a verification date to the
specific contract case. Bellingham, Freetown, Westport, Stoughton, and the Winchendon/Gardner consolidation are the current examples of this audit trail.
