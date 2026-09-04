# Using MACourts with addresses

MACourts matches Massachusetts locations to courts. It deliberately does **not**
parse street addresses or geocode them: your application supplies the city,
county, state, ZIP code, and (when needed) latitude/longitude.

That separation keeps the library dependency-light and lets callers use any
address or geocoding service they prefer.

## Install

Install the current package directly from GitHub:

```bash
python -m pip install git+https://github.com/SuffolkLITLab/MACourts.git
```

MACourts requires Python 3.10+ and Shapely.

## Address inputs

The main input type is `Location`:

```python
from macourts import Coordinates, Location

location = Location(
    city="Boston",
    county="Suffolk County",
    state="MA",
    postal_code="02118",
    neighborhood="South End",
    coordinates=Coordinates(
        latitude=42.336633930640154,
        longitude=-71.06846838831075,
    ),
)
```

The fields have different roles:

| Field | Example | Notes |
| --- | --- | --- |
| `city` | `"Boston"` | Used by city-based rules and BMC matching. |
| `county` | `"Suffolk County"` | Used by county-based rules. |
| `state` | `"MA"` | `"MA"` and `"Massachusetts"` are accepted. Non-Massachusetts locations are rejected by the built-in matchers. |
| `postal_code` | `"02118"` | Used on its own when nothing else is supplied: the ZIP expands to the municipalities it covers. |
| `neighborhood` | `"South End"` | Used by the East Boston neighborhood rules for Housing and Juvenile Court. |
| `coordinates` | `Coordinates(...)` | Required for geographic BMC division matching inside Boston. |

There is intentionally no street-line field. If you start with something like
`"123 Main St, Boston, MA 02118"`, parse/geocode it outside MACourts and pass
the resulting jurisdiction fields into `Location`.

## A finder covering every department

`build_default_finder()` assembles every matcher, the packaged court catalog,
and the ZIP lookup table:

```python
from macourts import build_default_finder

finder = build_default_finder()
```

It covers all nine departments:

| Department | Matched by |
| --- | --- |
| Boston Municipal Court | packaged BMC ward geometry, plus the Winthrop special case |
| District Court | city/county rules |
| Housing Court | ordered city/county/neighborhood rules |
| Juvenile Court | city/county/neighborhood rules, with two sessions following BMC division lines |
| Probate and Family Court | city/county rules |
| Superior Court | ordered county rules |
| Land Court | statewide |
| Appeals Court (Single Justice) | statewide |
| Supreme Judicial Court | statewide |

Passing no `court_types` returns every court serving the address:

```python
from macourts import Location

for match in finder.find(Location(city="Springfield", county="Hampden County")):
    print(match.department, "-", match.name)
```

Output:

```text
Appeals Court - Massachusetts Appeals Court (Single Justice)
District Court - Springfield District Court
Housing Court - Western Housing Court - Springfield Session
Juvenile Court - Springfield Juvenile Court
Land Court - Land Court
Probate and Family Court - Hampden Probate and Family Court
Superior Court - Hampden County Superior Court
Supreme Judicial Court - Supreme Judicial Court
```

The jurisdiction rules behind this are data, not code; see
[Jurisdiction rules](jurisdiction_rules.md) for the file format, the selection
modes, and how to regenerate it.

The examples below reuse this `finder`.

## Example: a Boston address with coordinates

Boston Municipal Court divisions are geographic, so a Boston address should be
geocoded before matching.

```python
from macourts import Coordinates, Location

location = Location(
    city="Boston",
    county="Suffolk County",
    state="MA",
    postal_code="02118",
    coordinates=Coordinates(
        latitude=42.336633930640154,
        longitude=-71.06846838831075,
    ),
)

matches = finder.find(location, ["Boston Municipal Court"])

for match in matches:
    print(match.name)
```

Output:

```text
Central Division, Boston Municipal Court
```

Each `CourtMatch` also includes reasons and any matching catalog records:

```python
match = matches[0]

print(match.reasons[0].kind)       # geometry
print(match.reasons[0].detail)
print(match.records[0].court_code) # when present in the catalog
```

## Example: a Boston neighborhood name in the city field

MACourts recognizes the common Boston place-name aliases — Allston, Brighton,
Charlestown, Dorchester, East Boston, Hyde Park, Jamaica Plain, Mattapan,
Roslindale, Roxbury, South Boston, and West Roxbury. They tell the BMC matcher
that the location is inside the Boston geography, and they let every other
department fill in Suffolk County when the address carries no county at all.

```python
from macourts import Coordinates, Location

location = Location(
    city="Dorchester",
    county="Suffolk County",
    state="MA",
    coordinates=Coordinates(
        latitude=42.26635042771657,
        longitude=-71.09789540837042,
    ),
)

matches = finder.find(location, ["Boston Municipal Court"])

print(matches[0].name)
```

Output:

```text
Dorchester Division, Boston Municipal Court
```

Coordinates still control the division. The alias tells MACourts that the
location should be considered part of the Boston BMC geography.

## Example: Winthrop without coordinates

Winthrop is a built-in special case and is served by East Boston BMC. Coordinates
are not required for this case.

```python
from macourts import Location

location = Location(
    city="Winthrop",
    county="Suffolk County",
    state="MA",
    postal_code="02152",
)

matches = finder.find(location, ["Boston Municipal Court"])

print(matches[0].name)
print(matches[0].reasons[0].kind)
```

Output:

```text
East Boston Division, Boston Municipal Court
special_case
```

## Example: a Massachusetts address for a statewide court

Statewide courts do not need coordinates, and a city/county-level location is
enough.

```python
from macourts import Location

location = Location(
    city="Pittsfield",
    county="Berkshire County",
    state="MA",
)

matches = finder.find(location, ["Land Court"])

print(matches[0].name)
```

Output:

```text
Land Court
```

The same `StatewideMatcher` also supports `"Appeals Court"` and
`"Supreme Judicial Court"`.

## Example: concurrent jurisdiction

Some towns are served by more than one court, and `find()` returns all of them
rather than picking one.

```python
from macourts import Location

location = Location(city="Freetown", county="Bristol County", state="MA")

for match in finder.find(location, ["District Court", "Housing Court"]):
    print(match.name)
```

Output:

```text
Fall River District Court
New Bedford District Court
Southeast Housing Court - Fall River Session
Southeast Housing Court - New Bedford Session
```

## Example: a Boston neighborhood that changes the venue

East Boston neighborhoods are heard in Chelsea, so the `neighborhood` field
changes the answer for an address whose city is just "Boston".

```python
from macourts import Location

location = Location(
    city="Boston",
    county="Suffolk County",
    state="MA",
    neighborhood="Maverick Square",
)

print(finder.find(location, ["Housing Court"])[0].name)
```

Output:

```text
Eastern Housing Court - Chelsea Session
```

## Example: a ZIP code and nothing else

When a location carries only a ZIP, the finder expands it to the municipalities
that ZIP covers and unions the results. Each match records which ZIP it came
from.

```python
from macourts import Location

matches = finder.find_by_postal_code("02072", ["Housing Court"])

print(matches[0].name)
print([reason.kind for reason in matches[0].reasons])
```

Output:

```text
Metro South Housing Court - Stoughton Session
['postal_code', 'location_rule']
```

`find()` also accepts several locations at once, unioning their courts — useful
when a ZIP crosses municipal lines and you want to resolve it yourself.

## Example: an out-of-state address

The built-in matchers do not return Massachusetts courts for a location in
another state.

```python
from macourts import Location

location = Location(
    city="Providence",
    county="Providence County",
    state="RI",
)

matches = finder.find(location, ["Land Court"])

assert matches == []
```

## Example: supply your own city/county rule

The packaged rules are ordinary `LocationRule` objects, so an application can
add its own — for a rule the Trial Court has just changed, say, ahead of a
MACourts release.

```python
from macourts import (
    CourtCatalog,
    CourtFinder,
    Location,
    LocationRule,
    RuleMatcher,
)

catalog = CourtCatalog.from_package_data()

superior_rules = RuleMatcher(
    [
        LocationRule(
            department="Superior Court",
            court_names=("Suffolk County Superior Court",),
            cities=frozenset({"boston", "winthrop"}),
            counties=frozenset({"suffolk county"}),
        )
    ]
)

finder_with_rules = CourtFinder([superior_rules], catalog)

matches = finder_with_rules.find(
    Location(
        city="Boston",
        county="Suffolk County",
        state="MA",
    ),
    ["Superior Court"],
)

print(matches[0].name)
print(matches[0].records[0].court_code)
```

The rule values are normalized case-insensitively before comparison.

## Example: use a docassemble-style `Address` object

MACourts includes a duck-typed adapter for docassemble `Address` objects, but
does not import docassemble itself.

```python
from macourts import build_default_finder, location_from_object

# address is an existing docassemble-style Address object.
location = location_from_object(address)

matches = build_default_finder().find(location)
```

The adapter reads:

- `address.city`
- `address.county`
- `address.state`
- `address.zip`
- `address.neighborhood`
- `address.location.latitude`
- `address.location.longitude`

Latitude and longitude are optional, but BMC geometry needs them for Boston
addresses other than the Winthrop special case.

## Working with catalog records

Matching answers the jurisdiction question; the packaged `CourtCatalog` adds
court metadata.

```python
from macourts import CourtCatalog

catalog = CourtCatalog.from_package_data()

records = catalog.resolve(
    "Central Division, Boston Municipal Court",
    "Boston Municipal Court",
)

for record in records:
    print(record.location_name)
    print(record.court_code)
    print(record.tyler_code)
    print(record.accepts_filings)
    print(record.filing_location_name)
```

Some semantic courts have more than one physical/session record, so
`match.records` and `catalog.resolve(...)` return tuples rather than assuming
there is exactly one location.

For an appearance-only session, use `catalog.filing_location_for(record)` to
resolve the location that accepts filings.

## Choosing which address fields to provide

A practical rule of thumb:

| Address you have | What to pass |
| --- | --- |
| Full street address in Boston | Geocode externally; pass city/state plus coordinates, and county/ZIP when available. |
| Boston neighborhood address | Pass the neighborhood/place name as `city` if it is one of the supported aliases, plus coordinates. |
| Winthrop address | `city="Winthrop"` and `state="MA"` are sufficient for BMC matching. |
| Massachusetts address for Land/Appeals/SJC | City/state are sufficient; county/ZIP are still useful metadata. |
| Massachusetts address for any other department | City is usually enough; pass county too, since a few rules need both. |
| East Boston address written as "Boston" | Pass `neighborhood` as well, or the Chelsea sessions will be missed. |
| ZIP-only address | Pass it as `postal_code` and let the finder expand it, or use `find_by_postal_code()`. |
| docassemble `Address` | Use `location_from_object(address)`. |

## Notes for production callers

- Keep geocoding in the caller and cache it according to the terms of your
  geocoding provider.
- Prefer a real geocoded point for Boston BMC matching. If a Boston point falls
  outside the packaged polygons, the matcher returns the nearest BMC area and
  records the reason as `geometry_nearest`.
- Use `court_types` when calling `find()` if you only want a particular
  department.
- Expect more than one match. Concurrent jurisdiction is normal in the District,
  Juvenile, and Probate & Family Courts, and several semantic courts sit in more
  than one location.
- Treat the catalog's filing-location metadata separately from live EFSP/Tyler
  availability. MACourts can identify the legal filing location, while a live
  filing system should still verify its current route/category taxonomy.
- An empty match is meaningful: it can mean the address is outside
  Massachusetts, required location data is missing, or no configured matcher
  covers the requested department.
