#!/usr/bin/env python3
"""Compile a frozen Boston SAM snapshot into ``bmc_addresses.sqlite``.

Reads the JSONL snapshot written by ``fetch_boston_sam.py``, spatially assigns
every address to a BMC division using the *same* polygon matcher runtime code
uses (:meth:`BostonMunicipalCourtMatcher.court_for_coordinates`, called with
``allow_nearest=False`` so an address outside every ward polygon is reported as
a QA gap rather than silently assigned), and writes the narrow, exact-match
SQLite schema that :mod:`macourts.boston_address` reads at runtime.

Nothing here talks to a live service — see ``fetch_boston_sam.py`` for that.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from macourts.boston import BMC, BostonMunicipalCourtMatcher  # noqa: E402
from macourts.boston_address import normalize_zip_code  # noqa: E402
from macourts.boston_address import normalize_street_text  # noqa: E402
from macourts.models import Coordinates  # noqa: E402

DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "build" / "sam"
DEFAULT_WARDS_PATH = REPO_ROOT / "macourts" / "data" / "boston_wards.geojson"
DEFAULT_DB_PATH = REPO_ROOT / "macourts" / "data" / "bmc_addresses.sqlite"
DEFAULT_META_PATH = REPO_ROOT / "macourts" / "data" / "bmc_addresses.meta.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "build" / "bmc_address_report.md"

KIND_CANONICAL = 0
KIND_ALIAS = 1
KIND_VARIANT = 2

# Directional abbreviation <-> full-word pairs SAM uses in STREET_PREFIX and
# STREET_SUFFIX_DIR, used to generate "N Beacon St" <-> "North Beacon Street".
DIRECTIONS = {
    "N": "NORTH",
    "S": "SOUTH",
    "E": "EAST",
    "W": "WEST",
    "NE": "NORTHEAST",
    "NW": "NORTHWEST",
    "SE": "SOUTHEAST",
    "SW": "SOUTHWEST",
}

MAX_EXPANDED_RANGE = 1000  # sanity guard against a garbage RANGE_FROM/RANGE_TO


def iter_snapshot_rows(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def normalize_number_text(value: str) -> str:
    text = value.strip().upper()
    text = text.replace("–", "-").replace("—", "-")
    return " ".join(text.split())


def expand_number_keys(row: dict[str, Any]) -> set[str]:
    """One or more ``number_key`` values a runtime address could resolve to.

    A non-range address just contributes its own number. A range address (SAM's
    ``IS_RANGE``) describes several house numbers sharing one entrance/parcel —
    e.g. "6-10 A St" is 6, 8, and 10 on a single building — so each individual
    number is expanded from ``RANGE_FROM``/``RANGE_TO`` at the block's own
    odd/even parity. This is authoritative SAM data about one address entity,
    not interpolation between unrelated addresses.
    """
    if row.get("IS_RANGE") and row.get("RANGE_FROM") and row.get("RANGE_TO"):
        range_from, range_to = str(row["RANGE_FROM"]), str(row["RANGE_TO"])
        if range_from.isdigit() and range_to.isdigit():
            lo, hi = int(range_from), int(range_to)
            if lo <= hi and hi - lo <= MAX_EXPANDED_RANGE:
                step = 2 if (hi - lo) % 2 == 0 else 1
                # A real caller types their own single house number, never the
                # literal SAM range string ("6-10"), so only the expanded
                # individual numbers are worth storing here.
                return {str(n) for n in range(lo, hi + 1, step)}

    street_number = row.get("STREET_NUMBER")
    if street_number:
        literal = normalize_number_text(str(street_number))
        if literal:
            return {literal}
    return set()


def street_name_variants(row: dict[str, Any]) -> dict[str, int]:
    """``{name_key: kind}`` for one street, canonical plus generated variants."""
    canonical = normalize_street_text(str(row["FULL_STREET_NAME"]))

    prefix_options = [None]
    if row.get("STREET_PREFIX"):
        prefix = str(row["STREET_PREFIX"]).strip().upper()
        prefix_options = sorted({prefix, DIRECTIONS.get(prefix, prefix)})

    suffix_options: list[str | None] = [None]
    abbr = row.get("STREET_SUFFIX_ABBR")
    full = row.get("STREET_FULL_SUFFIX")
    if abbr or full:
        suffix_options = sorted({s for s in (abbr, full) if s})

    dir_options = [None]
    if row.get("STREET_SUFFIX_DIR"):
        suffix_dir = str(row["STREET_SUFFIX_DIR"]).strip().upper()
        dir_options = sorted({suffix_dir, DIRECTIONS.get(suffix_dir, suffix_dir)})

    body = str(row["STREET_BODY"]) if row.get("STREET_BODY") else None

    variants: dict[str, int] = {canonical: KIND_CANONICAL}
    for prefix, suffix, suffix_dir in itertools.product(
        prefix_options, suffix_options, dir_options
    ):
        pieces = [p for p in (prefix, body, suffix, suffix_dir) if p]
        if not pieces:
            continue
        variant = normalize_street_text(" ".join(pieces))
        if variant and variant not in variants:
            variants[variant] = KIND_VARIANT
    return variants


def build_index(
    snapshot_dir: Path,
    wards_path: Path,
) -> dict[str, Any]:
    matcher = BostonMunicipalCourtMatcher.from_geojson(wards_path)
    all_divisions = sorted(
        {matcher.full_name(area.courthouse) for area in matcher.areas}
    )
    division_ids = {name: i + 1 for i, name in enumerate(all_divisions)}

    street_names: dict[str, dict[str, int]] = {}  # street_id -> {name_key: kind}
    # (street_id, number_key, zip) -> set of division names seen for that key
    address_divisions: dict[tuple[int, str, str], set[str]] = defaultdict(set)

    raw_row_count = 0
    unmatched_points = 0
    seen_street_ids: set[int] = set()

    for row in iter_snapshot_rows(snapshot_dir / "addresses.jsonl.gz"):
        raw_row_count += 1
        street_id = row.get("STREET_ID")
        x, y = row.get("X_COORD"), row.get("Y_COORD")
        if street_id is None or x is None or y is None:
            continue

        if street_id not in seen_street_ids:
            seen_street_ids.add(street_id)
            variants = street_name_variants(row)
            street_names[street_id] = variants

        candidate = matcher.court_for_coordinates(
            Coordinates(latitude=y, longitude=x), allow_nearest=False
        )
        if candidate is None:
            unmatched_points += 1
            continue

        zip_code = normalize_zip_code(row.get("ZIP_CODE")) or ""
        for number_key in expand_number_keys(row):
            address_divisions[(street_id, number_key, zip_code)].add(candidate.name)

    conflicts: list[tuple[int, str, str, list[str]]] = []
    addresses: dict[tuple[int, str, str], str] = {}
    for key, divisions in address_divisions.items():
        if len(divisions) > 1:
            conflicts.append((*key, sorted(divisions)))
            continue
        addresses[key] = next(iter(divisions))

    return {
        "matcher": matcher,
        "all_divisions": all_divisions,
        "division_ids": division_ids,
        "street_names": street_names,
        "addresses": addresses,
        "conflicts": conflicts,
        "raw_row_count": raw_row_count,
        "unmatched_points": unmatched_points,
    }


def logical_hash(
    division_ids: dict[str, int],
    street_names: dict[int, dict[str, int]],
    addresses: dict[tuple[int, str, str], str],
) -> str:
    hasher = hashlib.sha256()
    for name in sorted(division_ids):
        hasher.update(f"D\t{division_ids[name]}\t{name}\n".encode())
    for street_id in sorted(street_names):
        for name_key in sorted(street_names[street_id]):
            kind = street_names[street_id][name_key]
            hasher.update(f"S\t{name_key}\t{street_id}\t{kind}\n".encode())
    for (street_id, number_key, zip_code), division_name in sorted(addresses.items()):
        hasher.update(
            f"A\t{street_id}\t{number_key}\t{zip_code}\t{division_name}\n".encode()
        )
    return hasher.hexdigest()


def write_database(
    db_path: Path,
    *,
    division_ids: dict[str, int],
    street_names: dict[int, dict[str, int]],
    addresses: dict[tuple[int, str, str], str],
    metadata: dict[str, str],
) -> None:
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            PRAGMA user_version = 1;

            CREATE TABLE metadata (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) WITHOUT ROWID;

            CREATE TABLE divisions (
                id         INTEGER PRIMARY KEY,
                court_name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE street_names (
                name_key  TEXT NOT NULL,
                street_id INTEGER NOT NULL,
                kind      INTEGER NOT NULL,
                PRIMARY KEY (name_key, street_id)
            ) WITHOUT ROWID;

            CREATE TABLE addresses (
                street_id   INTEGER NOT NULL,
                number_key  TEXT NOT NULL,
                -- A 5-digit MA ZIP stored as an int, e.g. 2118 for "02118" --
                -- cheaper than TEXT, and safe here because nothing in
                -- macourts.boston_address ever hands a raw zip_code value
                -- back to a caller; only court_name comes out of resolve().
                -- Reconstruct the leading zero (str(v).zfill(5)) if you ever
                -- query this column directly.
                zip_code    INTEGER NOT NULL DEFAULT 0,
                division_id INTEGER NOT NULL,
                PRIMARY KEY (street_id, number_key, zip_code)
            ) WITHOUT ROWID;
            """
        )
        # No secondary indexes: both tables are WITHOUT ROWID, so their
        # primary key IS a clustered B-tree over exactly the columns
        # `resolve()` filters on (name_key; street_id, number_key) -- a
        # separate index on the same leading columns would just be a
        # same-size duplicate of data the primary key already provides.
        # `EXPLAIN QUERY PLAN` confirms both lookups use the primary key.

        connection.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        connection.executemany(
            "INSERT INTO divisions (id, court_name) VALUES (?, ?)",
            sorted((i, name) for name, i in division_ids.items()),
        )
        connection.executemany(
            "INSERT INTO street_names (name_key, street_id, kind) VALUES (?, ?, ?)",
            sorted(
                (name_key, street_id, kind)
                for street_id, variants in street_names.items()
                for name_key, kind in variants.items()
            ),
        )
        connection.executemany(
            "INSERT INTO addresses (street_id, number_key, zip_code, division_id) "
            "VALUES (?, ?, ?, ?)",
            sorted(
                (
                    street_id,
                    number_key,
                    int(zip_code) if zip_code else 0,
                    division_ids[division_name],
                )
                for (
                    street_id,
                    number_key,
                    zip_code,
                ), division_name in addresses.items()
            ),
        )
        connection.commit()
        connection.execute("VACUUM")
        (ok,) = connection.execute("PRAGMA integrity_check").fetchone()
        if ok != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {ok}")
    finally:
        connection.close()


def write_report(
    report_path: Path,
    *,
    result: dict[str, Any],
    source: dict[str, Any],
    data_version: str,
    logical_hash_value: str,
    db_size: int,
) -> None:
    divisions_count = defaultdict(int)
    for division_name in result["addresses"].values():
        divisions_count[division_name] += 1

    lines = [
        f"# BMC address index build report ({data_version})",
        "",
        f"- SAM snapshot fetched: {source.get('fetched_at')}",
        f"- SAM max last-edited timestamp: {source.get('max_last_edited_date')}",
        f"- Raw SAM address rows: {result['raw_row_count']}",
        f"- Compiled unique address keys: {len(result['addresses'])}",
        f"- Distinct streets: {len(result['street_names'])}",
        f"- Street name rows (canonical + variants): "
        f"{sum(len(v) for v in result['street_names'].values())}",
        f"- BMC divisions represented: {len(divisions_count)} / "
        f"{len(result['all_divisions'])}",
        f"- SQLite size: {db_size / 1_000_000:.2f} MB",
        f"- Logical content hash: {logical_hash_value}",
        f"- Points not contained by any BMC polygon: {result['unmatched_points']} "
        f"({result['unmatched_points'] / max(result['raw_row_count'], 1):.2%})",
        f"- Ambiguous/conflicting address keys: {len(result['conflicts'])}",
        "",
        "## Addresses per BMC division",
        "",
    ]
    for name in sorted(divisions_count):
        lines.append(f"- {name}: {divisions_count[name]}")

    if result["conflicts"]:
        lines += ["", "## Conflicting address keys (excluded from the index)", ""]
        for street_id, number_key, zip_code, divisions in result["conflicts"][:50]:
            lines.append(
                f"- street_id={street_id} number={number_key!r} zip={zip_code!r}: "
                f"{', '.join(divisions)}"
            )
        if len(result["conflicts"]) > 50:
            lines.append(f"- ... and {len(result['conflicts']) - 50} more")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--wards-path", type=Path, default=DEFAULT_WARDS_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--meta-path", type=Path, default=DEFAULT_META_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--data-version",
        default=datetime.now(timezone.utc).strftime("%Y-%m"),
        help="Version tag stored in metadata and used in MatchReason.source",
    )
    args = parser.parse_args()

    with (args.snapshot_dir / "source.json").open(encoding="utf-8") as handle:
        source = json.load(handle)

    print("Compiling address index from snapshot...", file=sys.stderr)
    result = build_index(args.snapshot_dir, args.wards_path)

    missing_divisions = set(result["all_divisions"]) - set(result["addresses"].values())
    logical_hash_value = logical_hash(
        result["division_ids"], result["street_names"], result["addresses"]
    )

    metadata = {
        "data_version": args.data_version,
        "logical_hash": logical_hash_value,
        "source_service_url": source.get("service_url", ""),
        "source_fetched_at": source.get("fetched_at", ""),
        "source_max_last_edited_date": str(source.get("max_last_edited_date", "")),
        "raw_row_count": str(result["raw_row_count"]),
        "address_count": str(len(result["addresses"])),
        "street_count": str(len(result["street_names"])),
        "conflict_count": str(len(result["conflicts"])),
        "unmatched_point_count": str(result["unmatched_points"]),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }

    write_database(
        args.db_path,
        division_ids=result["division_ids"],
        street_names=result["street_names"],
        addresses=result["addresses"],
        metadata=metadata,
    )
    db_size = args.db_path.stat().st_size

    args.meta_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    write_report(
        args.report_path,
        result=result,
        source=source,
        data_version=args.data_version,
        logical_hash_value=logical_hash_value,
        db_size=db_size,
    )

    print(f"Wrote {args.db_path} ({db_size / 1_000_000:.2f} MB)", file=sys.stderr)
    print(f"Wrote {args.meta_path}", file=sys.stderr)
    print(f"Wrote {args.report_path}", file=sys.stderr)
    if missing_divisions:
        print(
            f"warning: {len(missing_divisions)} BMC division(s) have zero "
            f"addresses: {sorted(missing_divisions)}",
            file=sys.stderr,
        )
    if result["conflicts"]:
        print(
            f"warning: {len(result['conflicts'])} conflicting address key(s) "
            "excluded from the index (see the report)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
