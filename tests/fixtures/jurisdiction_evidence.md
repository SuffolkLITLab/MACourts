# Jurisdiction evidence notes

Verified 2026-09-03 against current Massachusetts sources.

## Bellingham — Metro South Housing Court, Canton Session

Current Massachusetts Court System sources consistently assign Bellingham to **Metro South Housing Court - Canton Session**:

- Courts serving Bellingham: https://www.mass.gov/info-details/courts-serving-bellingham
- Canton Session overview: https://www.mass.gov/locations/metro-south-housing-court-canton-session
- Worcester Session overview (Bellingham is no longer listed): https://www.mass.gov/locations/central-housing-court-worcester-session
- Brockton Session overview (now lists only Abington, Bridgewater, Brockton, East Bridgewater, West Bridgewater, and Whitman): https://www.mass.gov/locations/metro-south-housing-court-brockton-session

The prior MACourts rule could return Central Housing Court - Worcester Session because Bellingham appeared in an old hard-coded list. That behavior is stale and should not be preserved.

## Freetown — concurrent Fall River / New Bedford Housing Court sessions

The external sources are not perfectly consistent, but the stronger jurisdiction evidence supports **both** Southeast Housing Court sessions:

- Fall River Session currently says it serves Freetown:
  https://www.mass.gov/locations/southeast-housing-court-fall-river-session
- New Bedford Session currently says it serves Freetown:
  https://www.mass.gov/locations/southeast-housing-court-new-bedford-session
- An official state audit's jurisdiction appendix explicitly lists Freetown and Westport in both columns and states that they may bring cases to either Housing Court:
  https://www.mass.gov/doc/southeast-division-of-the-housing-court-department/download
- Massachusetts General Laws also preserve concurrent Fall River / New Bedford District Court jurisdiction for Freetown and Westport, consistent with the historical territorial split:
  https://malegislature.gov/Laws/GeneralLaws/PartIII/TitleI/Chapter218/Section1

There is a conflicting newer Mass.gov page, "Courts serving Freetown," which names only the New Bedford Housing Court session:
https://www.mass.gov/info-details/courts-serving-freetown

Because both current session pages still affirm service and the explicit jurisdiction record says either session is permitted, MACourts treats **Fall River + New Bedford** as the court-finder result. The town-specific page should be rechecked periodically in case the Trial Court publishes a formal jurisdiction change.

## Devens — a single venue, routed through Ayer

Devens is a regional enterprise zone on the former Fort Devens, spanning land in
Ayer, Harvard, Lancaster, and Shirley. The municipality alias spreadsheet lists
it against all four, which is geographically right and jurisdictionally wrong:
Mass.gov names Devens as a single service area under Ayer's courts.

- Ayer District Court serves "Ashby, Ayer, Boxborough, Dunstable, Groton,
  Littleton, Pepperell, Shirley, Townsend, Westford, and Devens Regional
  Enterprise Zone": https://www.mass.gov/locations/ayer-district-court
- Northeast Housing Court - Lowell Session names Devens in its service list:
  https://www.mass.gov/locations/northeast-housing-court-lowell-session
- Ayer is in Middlesex County, so Superior, Juvenile, and Probate & Family
  follow Middlesex (Middlesex Probate and Family Court - North, in Lowell,
  names Ayer and Shirley):
  https://www.mass.gov/locations/middlesex-probate-and-family-court-north-lowell

Expanding the alias to all four towns returned three Housing Court sessions for
one address, plus both Middlesex and Worcester Superior and Probate courts. The
alias is overridden to Ayer alone.

## Middleborough — concurrent Plymouth / Brockton Probate & Family sessions

Plymouth County's Probate and Family Court hears matters in two locations, at 52
Obery Street in Plymouth and 215 Main Street in Brockton, and both list the same
27 Plymouth County towns — Middleborough among them.

- Plymouth Probate and Family Court:
  https://www.mass.gov/locations/plymouth-probate-and-family-court
- Brockton Probate and Family Court:
  https://www.mass.gov/locations/brockton-probate-and-family-court

The legacy chains spelled the town "middleborough" in the Plymouth rule and
"middleboro" in the Brockton rule, so neither list contained both spellings and
each spelling returned only one of the two courts. Corrected via
`CITY_SPELLING_FIXES`, which is where the other legacy misspellings are handled.

## Gosnold, Tisbury, Truro, Wellfleet — Southeast Housing Court, Barnstable session

The Barnstable session's page states it serves "Barnstable, Dukes and Nantucket
County" and lists Tisbury, Vineyard Haven (Tisbury's village), Truro, and
Wellfleet by name:
https://www.mass.gov/locations/southeast-housing-court-barnstable-session

Gosnold is not in that village list, but it is in Dukes County, and Edgartown
District Court serves "Edgartown, Oak Bluffs, Tisbury, West Tisbury, Chilmark,
Aquinnah, Gosnold, and the Elizabeth Islands":
https://www.mass.gov/locations/edgartown-district-court

The legacy Barnstable-session list named 19 of the 23 towns in those three
counties. The four it missed fell through to the Southeast Plymouth session,
whose legacy list repeats every Cape and Islands town — an artifact of the
``elif`` chain, since the earlier rules always claim them first. Adding the four
to the Barnstable list makes the rule self-sufficient rather than dependent on
county inference.

