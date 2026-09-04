#!/usr/bin/env python3
"""Diff two compiled ``bmc_addresses.sqlite`` databases and report what changed.

Used by the refresh workflow to decide whether a rebuild is worth a PR (the
logical content hash is unchanged -> nothing to do) and, when it is, to write
a human-readable change report for the PR body.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        divisions = dict(connection.execute("SELECT id, court_name FROM divisions"))
        addresses = {
            (street_id, number_key, zip_code): divisions[division_id]
            for street_id, number_key, zip_code, division_id in connection.execute(
                "SELECT street_id, number_key, zip_code, division_id FROM addresses"
            )
        }
        streets = {
            row[0]
            for row in connection.execute("SELECT DISTINCT name_key FROM street_names")
        }
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    finally:
        connection.close()
    return {
        "divisions": set(divisions.values()),
        "addresses": addresses,
        "streets": streets,
        "metadata": metadata,
    }


def diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_keys, new_keys = set(old["addresses"]), set(new["addresses"])
    added = new_keys - old_keys
    removed = old_keys - new_keys
    changed = {
        key
        for key in old_keys & new_keys
        if old["addresses"][key] != new["addresses"][key]
    }
    return {
        "hash_changed": old["metadata"].get("logical_hash")
        != new["metadata"].get("logical_hash"),
        "added_addresses": added,
        "removed_addresses": removed,
        "changed_division_addresses": changed,
        "added_streets": new["streets"] - old["streets"],
        "removed_streets": old["streets"] - new["streets"],
        "added_divisions": new["divisions"] - old["divisions"],
        "removed_divisions": old["divisions"] - new["divisions"],
    }


def format_key(key: tuple[int, str, int]) -> str:
    street_id, number_key, zip_code = key
    # zip_code is stored as an int (see build_bmc_address_index.py); restore
    # the leading zero for the human-facing PR report.
    zip_display = str(zip_code).zfill(5) if zip_code else ""
    return f"street_id={street_id} number={number_key!r} zip={zip_display!r}"


def write_report(report_path: Path, old: dict, new: dict, result: dict) -> None:
    lines = ["# BMC address index comparison", ""]
    if not result["hash_changed"]:
        lines.append("No logical content change since the committed database.")
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines += [
        f"- Old data version: {old['metadata'].get('data_version')}",
        f"- New data version: {new['metadata'].get('data_version')}",
        f"- Addresses added: {len(result['added_addresses'])}",
        f"- Addresses removed: {len(result['removed_addresses'])}",
        f"- Addresses changing division: {len(result['changed_division_addresses'])}",
        f"- Street names added: {len(result['added_streets'])}",
        f"- Street names removed: {len(result['removed_streets'])}",
        f"- BMC divisions added: {sorted(result['added_divisions']) or 'none'}",
        f"- BMC divisions removed: {sorted(result['removed_divisions']) or 'none'}",
        "",
    ]
    if result["changed_division_addresses"]:
        lines += ["## Addresses changing division (needs review)", ""]
        for key in sorted(result["changed_division_addresses"])[:100]:
            lines.append(
                f"- {format_key(key)}: "
                f"{old['addresses'][key]} -> {new['addresses'][key]}"
            )
        if len(result["changed_division_addresses"]) > 100:
            lines.append(
                f"- ... and {len(result['changed_division_addresses']) - 100} more"
            )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-db", type=Path, required=True)
    parser.add_argument("--new-db", type=Path, required=True)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "build"
        / "bmc_address_comparison.md",
    )
    args = parser.parse_args()

    if not args.old_db.exists():
        print(f"No existing database at {args.old_db}; treating as first build.")
        old = {
            "divisions": set(),
            "addresses": {},
            "streets": set(),
            "metadata": {},
        }
    else:
        old = load(args.old_db)
    new = load(args.new_db)

    result = diff(old, new)
    write_report(args.report, old, new, result)

    changed_flag = "true" if result["hash_changed"] else "false"
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"changed={changed_flag}\n")

    if not result["hash_changed"]:
        print("Logical content unchanged; no PR needed.")
        return 0

    print(
        f"Content changed: +{len(result['added_addresses'])} "
        f"-{len(result['removed_addresses'])} addresses, "
        f"{len(result['changed_division_addresses'])} changed division. "
        f"See {args.report}."
    )
    if len(result["changed_division_addresses"]) > 50:
        print(
            "warning: more than 50 addresses changed division; "
            "this needs careful review before merging.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
