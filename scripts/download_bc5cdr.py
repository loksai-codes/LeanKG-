"""Download the BioCreative V CDR corpus (BC5CDR) and convert diseases to leankg gold JSONL.

Source: Li et al. (2016), BioCreative V CDR task corpus,
https://biocreative.bioinformatics.udel.edu/tasks/biocreative-v/track-3-cdr/ — released for
research. Check the terms on that page before redistributing anything derived from it.
Only Disease mentions are kept (mapped to the health_stress `Condition` type). The data is
written under ./data/ (git-ignored) and is never committed.

Usage: uv run python scripts/download_bc5cdr.py [--limit 400]
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

from leankg.eval.converters import BC5CDR_TYPE_MAP, pubtator_to_gold
from leankg.eval.gold import dump_gold

URL = "https://biocreative.bioinformatics.udel.edu/media/store/files/2016/CDR_Data.zip"
OUT = Path("data/bc5cdr")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400, help="max sentences to keep")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "CDR_TestSet.PubTator.txt"
    if not raw.exists():
        print(f"downloading {URL}")
        req = urllib.request.Request(URL, headers={"User-Agent": "leankg-dataset-script"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except OSError as exc:
            print(f"download failed: {exc}", file=sys.stderr)
            return 1
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.endswith("CDR_TestSet.PubTator.txt"))
            raw.write_bytes(zf.read(name))
    gold = pubtator_to_gold(raw, BC5CDR_TYPE_MAP, "bc5cdr", limit_sentences=args.limit)
    path = dump_gold(gold, OUT / "gold.en.jsonl")
    n_ents = sum(len(g.entities) for g in gold)
    print(f"wrote {path}: {len(gold)} sentences, {n_ents} Condition mentions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
