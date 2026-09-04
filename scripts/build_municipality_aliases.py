#!/usr/bin/env python3
"""Convert massachusetts_municipalities_counties_aliases.xlsx to optimized JSON.

This script parses the authoritative MassGIS municipalities and MAPC/community
alias dataset into a lightweight, deterministic JSON structure for sub-millisecond
loading at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "macourts" / "data"
EXCEL_PATH = DATA_DIR / "massachusetts_municipalities_counties_aliases.xlsx"
OUTPUT_PATH = DATA_DIR / "municipality_aliases.json"

# Aliases the source spreadsheet lists against every municipality whose land they
# touch, but which the Trial Court treats as a single venue. Each is recorded in
# docs/jurisdiction_rules.md with its Mass.gov source.
ALIAS_OVERRIDES: dict[str, list[dict[str, str]]] = {
    # Devens spans Ayer, Harvard, Lancaster, and Shirley, but Mass.gov routes the
    # whole enterprise zone through Ayer: Ayer District Court names the "Devens
    # Regional Enterprise Zone", and the Northeast Housing Court's Lowell session
    # names Devens. Both are Middlesex, as is Ayer.
    "devens": [{"municipality": "Ayer", "county": "Middlesex County"}],
    "devens regional enterprise zone": [
        {"municipality": "Ayer", "county": "Middlesex County"}
    ],
}


def normalize_county(county_name: str) -> str:
    cleaned = county_name.strip()
    if not cleaned:
        return ""
    if cleaned.casefold().endswith("county"):
        return cleaned
    return f"{cleaned} County"


def build_data(excel_path: Path = EXCEL_PATH) -> dict[str, Any]:
    df_muni = pd.read_excel(excel_path, sheet_name="Municipalities", header=3)
    df_alias = pd.read_excel(excel_path, sheet_name="Alias Index", header=3)

    # 1. Canonical Municipalities (351 expected)
    municipalities: dict[str, dict[str, str]] = {}
    for _, row in df_muni.iterrows():
        muni = str(row["Municipality"]).strip()
        county = normalize_county(str(row["County"]))
        if muni and muni != "nan":
            municipalities[muni.casefold()] = {
                "name": muni,
                "county": county,
            }

    if len(municipalities) != 351:
        raise ValueError(
            f"Expected exactly 351 canonical municipalities, found {len(municipalities)}"
        )

    # 2. Alias Index
    aliases: dict[str, list[dict[str, str]]] = {}
    for _, row in df_alias.iterrows():
        alias = str(row["Alias"]).strip()
        muni = str(row["Municipality"]).strip()
        county = normalize_county(str(row["County"]))
        if not alias or alias == "nan":
            continue

        alias_key = alias.casefold()
        entry = {
            "municipality": muni,
            "county": county,
        }

        if alias_key not in aliases:
            aliases[alias_key] = []

        if entry not in aliases[alias_key]:
            aliases[alias_key].append(entry)

    aliases.update(ALIAS_OVERRIDES)

    # Sort aliases deterministically
    sorted_aliases: dict[str, list[dict[str, str]]] = {}
    for alias_key in sorted(aliases.keys()):
        # Sort targets by municipality name, then county
        sorted_targets = sorted(
            aliases[alias_key], key=lambda x: (x["municipality"], x["county"])
        )
        sorted_aliases[alias_key] = sorted_targets

    sorted_munis = {k: municipalities[k] for k in sorted(municipalities.keys())}

    return {
        "schema_version": 1,
        "metadata": {
            "source": "massachusetts_municipalities_counties_aliases.xlsx",
            "canonical_municipality_count": len(sorted_munis),
            "alias_count": len(sorted_aliases),
        },
        "municipalities": sorted_munis,
        "aliases": sorted_aliases,
    }


def main() -> None:
    data = build_data(EXCEL_PATH)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(
        f"Wrote {data['metadata']['canonical_municipality_count']} municipalities and "
        f"{data['metadata']['alias_count']} aliases to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
