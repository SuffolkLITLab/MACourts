#!/usr/bin/env python3
"""Download a frozen snapshot of Boston's live SAM address layer.

Boston's Street Address Management (SAM) system is exposed as a public,
paginated ArcGIS FeatureServer layer. This script downloads the full address
table (WGS84 point geometry plus the fields the address-index builder needs)
into a gzip-compressed JSONL snapshot, so ``build_bmc_address_index.py`` never
talks to a live service itself and every build is reproducible from a frozen
input.

There is no separate published master-street/alias/suffix-crosswalk service on
this host: every address record already carries ``FULL_STREET_NAME`` plus its
component parts (``STREET_BODY``, ``STREET_SUFFIX_ABBR``, ``STREET_FULL_SUFFIX``,
``STREET_PREFIX``, ``STREET_SUFFIX_DIR``), which is enough to build canonical
and suffix-variant street names at compile time. So this script fetches only
the one address layer.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SERVICE_URL = (
    "https://gisportal.boston.gov/arcgis/rest/services/"
    "SAM/Live_SAM_Address/FeatureServer/0"
)

FIELDS = [
    "SAM_ADDRESS_ID",
    "STREET_NUMBER",
    "IS_RANGE",
    "RANGE_FROM",
    "RANGE_TO",
    "UNIT",
    "FULL_STREET_NAME",
    "STREET_ID",
    "STREET_PREFIX",
    "STREET_BODY",
    "STREET_SUFFIX_ABBR",
    "STREET_FULL_SUFFIX",
    "STREET_SUFFIX_DIR",
    "ZIP_CODE",
    "MAILING_NEIGHBORHOOD",
    "WARD",
    "last_edited_date",
]

PAGE_SIZE = 2000
DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "build" / "sam"


def _get_json(url: str, params: dict[str, Any], *, retries: int = 3) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full_url, timeout=60) as response:
                payload = json.loads(response.read())
            if "error" in payload:
                raise RuntimeError(f"ArcGIS error: {payload['error']}")
            return payload
        except (urllib.error.URLError, RuntimeError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_record_count() -> int:
    payload = _get_json(
        f"{SERVICE_URL}/query",
        {"where": "1=1", "returnCountOnly": "true", "f": "json"},
    )
    return int(payload["count"])


def fetch_max_last_edited() -> int | None:
    payload = _get_json(
        f"{SERVICE_URL}/query",
        {
            "where": "1=1",
            "outStatistics": json.dumps(
                [
                    {
                        "statisticType": "max",
                        "onStatisticField": "last_edited_date",
                        "outStatisticFieldName": "max_edited",
                    }
                ]
            ),
            "f": "json",
        },
    )
    features = payload.get("features") or []
    if not features:
        return None
    return features[0]["attributes"].get("max_edited")


def iter_address_pages(page_size: int = PAGE_SIZE) -> Iterator[list[dict[str, Any]]]:
    offset = 0
    while True:
        payload = _get_json(
            f"{SERVICE_URL}/query",
            {
                "where": "1=1",
                "outFields": ",".join(FIELDS),
                "resultRecordCount": page_size,
                "resultOffset": offset,
                "orderByFields": "OBJECTID",
                "outSR": 4326,
                "f": "json",
            },
        )
        features = payload.get("features", [])
        if not features:
            return
        yield features
        offset += len(features)
        if not payload.get("exceededTransferLimit") and len(features) < page_size:
            return


def fetch_snapshot(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    addresses_path = out_dir / "addresses.jsonl.gz"

    fetched_at = datetime.now(timezone.utc).isoformat()
    expected_count = fetch_record_count()
    max_last_edited = fetch_max_last_edited()

    written = 0
    with gzip.open(addresses_path, "wt", encoding="utf-8") as handle:
        for page in iter_address_pages():
            for feature in page:
                row = dict(feature["attributes"])
                geometry = feature.get("geometry") or {}
                row["X_COORD"] = geometry.get("x")
                row["Y_COORD"] = geometry.get("y")
                handle.write(json.dumps(row, separators=(",", ":")))
                handle.write("\n")
                written += 1
            print(f"  fetched {written}/{expected_count} address rows", file=sys.stderr)

    source = {
        "service_url": SERVICE_URL,
        "fetched_at": fetched_at,
        "expected_record_count": expected_count,
        "written_record_count": written,
        "max_last_edited_date": max_last_edited,
        "fields": FIELDS,
        "output_srid": 4326,
        "street_alias_source": None,
        "street_suffix_crosswalk_source": None,
        "note": (
            "No standalone master-street/alias/suffix service is published on "
            "this ArcGIS host; canonical and suffix-variant street names are "
            "derived from FULL_STREET_NAME and its component fields on each "
            "address record."
        ),
    }
    with (out_dir / "source.json").open("w", encoding="utf-8") as handle:
        json.dump(source, handle, indent=2, sort_keys=True)
        handle.write("\n")

    if written != expected_count:
        print(
            f"warning: wrote {written} rows but the service reported "
            f"{expected_count} at query time (data may have changed mid-fetch)",
            file=sys.stderr,
        )

    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for the frozen snapshot (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    print(f"Fetching Boston SAM address snapshot from {SERVICE_URL}", file=sys.stderr)
    source = fetch_snapshot(args.out)
    print(
        f"Wrote {source['written_record_count']} address rows to "
        f"{args.out / 'addresses.jsonl.gz'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
