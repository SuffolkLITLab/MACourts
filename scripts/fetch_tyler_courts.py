#!/usr/bin/env python3
"""Snapshot the Massachusetts court names Tyler's EFSP reports.

The Suffolk LIT Lab EFSP proxy lists every Tyler court location code with its
display name at ``/jurisdictions/massachusetts/codes/courts?with_names=true``.
The list is public and differs by environment: staging (test) lacks many
production courts and zero-pads Juvenile county prefixes (``0705:LA`` vs.
``705:LA`` in prod). A listed court may still have e-filing turned off, so
each court also records whether it accepts initial (new case) and subsequent
filings, from the ``fileable_type`` filter. This script writes both lists to
``macourts/data/tyler_courts.json`` so the package never talks to a live
service at runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ENVIRONMENTS = {
    "prod": "https://efile.suffolklitlab.org",
    "test": "https://efile-test.suffolklitlab.org",
}
COURTS_PATH = "/jurisdictions/massachusetts/codes/courts?with_names=true"
DEFAULT_OUT = (
    Path(__file__).resolve().parent.parent / "macourts" / "data" / "tyler_courts.json"
)


def _fetch(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def fetch_courts(base_url: str) -> dict[str, dict[str, object]]:
    url = base_url + COURTS_PATH
    initial = {court["code"] for court in _fetch(url + "&fileable_type=INITIAL")}
    subsequent = {court["code"] for court in _fetch(url + "&fileable_type=SUBSEQUENT")}
    return {
        court["code"]: {
            "name": court["name"].strip(),
            "initial": court["code"] in initial,
            "subsequent": court["code"] in subsequent,
        }
        for court in _fetch(url)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    snapshot = {
        "fetched_on": date.today().isoformat(),
        "sources": {
            env: base_url + COURTS_PATH for env, base_url in ENVIRONMENTS.items()
        },
        "environments": {
            env: dict(sorted(fetch_courts(base_url).items()))
            for env, base_url in ENVIRONMENTS.items()
        },
    }
    args.out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    for env, courts in snapshot["environments"].items():
        print(f"{env}: {len(courts)} courts", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
