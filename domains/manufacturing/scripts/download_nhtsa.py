"""Download NHTSA vehicle complaints into a CSV that `leankg build` can read.

Source: NHTSA public API (https://api.nhtsa.gov/complaints/complaintsByVehicle). NHTSA data
is published by a US government agency; check https://www.nhtsa.gov for current terms.
Complaint texts are written by the public and may contain personal details — they're kept
under ./data/nhtsa/ (git-ignored) and never committed.

Usage: uv run python domains/manufacturing/scripts/download_nhtsa.py --limit 500
Then:  uv run leankg build data/nhtsa/complaints.csv --domain manufacturing \
           --csv-text-column summary --csv-id-column odiNumber
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
VEHICLES = [("honda", "accord", 2015), ("toyota", "camry", 2016), ("ford", "f-150", 2018),
            ("chevrolet", "malibu", 2016), ("nissan", "altima", 2017), ("hyundai", "sonata", 2015)]  # fmt: skip
OUT = Path("data/nhtsa")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for make, model, year in VEHICLES:
        q = urllib.parse.urlencode({"make": make, "model": model, "modelYear": year})
        try:
            req = urllib.request.Request(
                f"{API}?{q}", headers={"User-Agent": "leankg-dataset-script"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except OSError as exc:
            print(f"{make} {model} {year}: download failed: {exc}", file=sys.stderr)
            continue
        for r in data.get("results", []):
            if r.get("summary"):
                rows.append({"odiNumber": str(r.get("odiNumber", "")), "make": make, "model": model,
                             "year": str(year), "components": r.get("components", ""),
                             "summary": r["summary"]})  # fmt: skip
        time.sleep(1)
        if len(rows) >= args.limit:
            break
    rows = rows[: args.limit]
    path = OUT / "complaints.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["odiNumber", "make", "model", "year", "components", "summary"]
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}: {len(rows)} complaints")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
