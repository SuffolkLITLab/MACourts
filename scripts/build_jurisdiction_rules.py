"""Build ``macourts/data/jurisdiction_rules.json`` from the legacy chains.

Extraction is mechanical (see ``extract_legacy_jurisdiction_rules``); everything
this script changes on top of it is listed in ``CORRECTIONS`` with a reason, and
mirrored in ``docs/jurisdiction_rules.md``. Regenerate with::

    python scripts/build_jurisdiction_rules.py \
        --legacy ~/docassemble-MACourts/docassemble/MACourts/macourts.py

Nothing at runtime needs this script: the generated JSON is package data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_legacy_jurisdiction_rules import extract

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "macourts" / "data" / "jurisdiction_rules.json"

# --- corrections -----------------------------------------------------------
#
# Legacy spelling mistakes. Each of these silently dropped a town out of its
# court's service list, because the legacy code compared casefolded literals.
CITY_SPELLING_FIXES = {
    "northreading": "north reading",
    "pepperrell": "pepperell",
    "southamptom": "southampton",
    "nahunt": "nahant",
    "middleboro": "middleborough",
}

# Not a municipality: a stray list entry in the Berkshire housing chain.
DROPPED_CITIES = {"county"}

# Retired courts, replaced by their successor from historical_courts.json.
COURT_RENAMES = {
    "District Court": {"Winchendon District Court": "Gardner District Court"},
    # The packaged Housing Court catalog spells this session with a lowercase
    # "session"; keep one canonical spelling so matches resolve to a record.
    "Housing Court": {
        "Southeast Housing Court - Barnstable Session": (
            "Southeast Housing Court - Barnstable session"
        )
    },
}

# Towns removed from a court's legacy service list, with the reason.
CITY_REMOVALS = {
    ("Housing Court", "Central Housing Court - Worcester Session"): {
        # Current Mass.gov no longer lists Bellingham here; it is Metro South.
        "bellingham",
    },
    ("Housing Court", "Metro South Housing Court - Brockton Session"): {
        # Bellingham and Stoughton have moved off the Brockton session roster.
        "bellingham",
        "stoughton",
    },
    ("Housing Court", "Southeast Housing Court - Fall River Session"): {
        # Handled by the concurrent Fall River / New Bedford rule below.
        "freetown",
        "westport",
    },
    ("Housing Court", "Southeast Housing Court - New Bedford Session"): {
        "freetown",
        "westport",
    },
}

# Towns missing from legacy service lists, added per current Mass.gov rosters.
CITY_ADDITIONS = {
    ("Juvenile Court", "Dedham Juvenile Court"): {
        # Mass.gov Norfolk Juvenile Court session for Brookline.
        "brookline",
    },
    ("Juvenile Court", "Great Barrington Juvenile Court"): {
        # Mass.gov Southern Berkshire Juvenile Court session for Mount Washington.
        "mount washington",
    },
    ("Juvenile Court", "North Adams Juvenile Court"): {
        # Mass.gov Northern Berkshire Juvenile Court session for Savoy.
        "savoy",
    },
    ("Juvenile Court", "Orleans Juvenile Court"): {
        # Mass.gov Barnstable Second District Juvenile Court session for Truro.
        "truro",
    },
}

# Rules with no legacy equivalent, inserted before the named court's own rule.
# ``mass.gov`` sources are recorded in docs/jurisdiction_rules.md.
INSERTED_RULES = [
    (
        "Housing Court",
        "Metro South Housing Court - Brockton Session",
        {
            "courts": ["Metro South Housing Court - Stoughton Session"],
            "cities": ["stoughton"],
            "note": "Stoughton has its own Metro South session; filings go to Canton.",
        },
    ),
    (
        "Housing Court",
        "Southeast Housing Court - Fall River Session",
        {
            "courts": [
                "Southeast Housing Court - Fall River Session",
                "Southeast Housing Court - New Bedford Session",
            ],
            "cities": ["freetown", "westport"],
            "note": "Concurrent jurisdiction; both sessions list these towns.",
        },
    ),
]

KEY_ORDER = (
    "courts",
    "counties",
    "cities",
    "excluded_cities",
    "neighborhoods",
    "require_all",
    "note",
)


def clean_cities(values: list[str]) -> list[str]:
    cleaned = [
        CITY_SPELLING_FIXES.get(value, value)
        for value in values
        if value not in DROPPED_CITIES
    ]
    return sorted(dict.fromkeys(cleaned))


def apply_corrections(data: dict) -> dict:
    departments = []
    for block in data["departments"]:
        department = block["department"]
        renames = COURT_RENAMES.get(department, {})
        rules = []
        for rule in block["rules"]:
            courts = [renames.get(court, court) for court in rule["courts"]]
            removals: set[str] = set()
            additions: set[str] = set()
            for court in courts:
                removals |= CITY_REMOVALS.get((department, court), set())
                additions |= CITY_ADDITIONS.get((department, court), set())
            cities = sorted(dict.fromkeys([
                city for city in clean_cities(rule.get("cities", [])) if city not in removals
            ] + list(additions)))
            corrected = {
                "courts": courts,
                "counties": sorted(dict.fromkeys(rule.get("counties", []))),
                "cities": cities,
                "excluded_cities": clean_cities(rule.get("excluded_cities", [])),
                "neighborhoods": [
                    {"city": group.get("city"), "names": sorted(dict.fromkeys(group["names"]))}
                    for group in rule.get("neighborhoods", [])
                ],
                "require_all": bool(rule.get("require_all")),
            }
            if not (
                corrected["cities"]
                or corrected["counties"]
                or corrected["neighborhoods"]
            ):
                continue
            rules.append(corrected)

        for target_department, before_court, new_rule in INSERTED_RULES:
            if target_department != department:
                continue
            index = next(
                (
                    position
                    for position, rule in enumerate(rules)
                    if before_court in rule["courts"]
                ),
                len(rules),
            )
            rules.insert(
                index,
                {
                    "courts": new_rule["courts"],
                    "counties": [],
                    "cities": sorted(new_rule.get("cities", [])),
                    "excluded_cities": [],
                    "neighborhoods": [],
                    "require_all": False,
                    "note": new_rule.get("note"),
                },
            )

        departments.append(
            {
                "department": department,
                "selection": block["selection"],
                "rules": [
                    {key: rule[key] for key in KEY_ORDER if rule.get(key)}
                    for rule in rules
                ],
            }
        )
    return {"schema_version": 1, "departments": departments}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--legacy",
        type=Path,
        default=Path("~/docassemble-MACourts/docassemble/MACourts/macourts.py").expanduser(),
    )
    parser.add_argument("--out", type=Path, default=OUTPUT)
    arguments = parser.parse_args()

    data = apply_corrections(extract(arguments.legacy))
    arguments.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for block in data["departments"]:
        courts = {court for rule in block["rules"] for court in rule["courts"]}
        print(
            f'{block["department"]}: {len(block["rules"])} rules, '
            f'{len(courts)} courts, selection={block["selection"]}'
        )


if __name__ == "__main__":
    main()
