"""Download the NCBI Disease corpus (test split) and convert it to leankg gold JSONL.

Source: Doğan, Leaman & Lu (2014), NCBI Disease corpus,
https://www.ncbi.nlm.nih.gov/CBBresearch/Dogan/DISEASE/ — distributed by NCBI for research
use. Check the terms on that page before redistributing anything derived from it.
The data is written under ./data/ (git-ignored) and is never committed.

Usage: uv run python scripts/download_ncbi_disease.py [--limit 400]
Then:  uv run leankg eval --domain health_stress --setup A --lang en \
           --gold data/ncbi_disease/gold.en.jsonl --types Condition
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

from leankg.eval.converters import NCBI_TYPE_MAP, pubtator_to_gold
from leankg.eval.gold import dump_gold

URL = "https://www.ncbi.nlm.nih.gov/CBBresearch/Dogan/DISEASE/NCBItestset_corpus.zip"
OUT = Path("data/ncbi_disease")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400, help="max sentences to keep")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "NCBItestset_corpus.txt"
    if not raw.exists():
        print(f"downloading {URL}")
        req = urllib.request.Request(URL, headers={"User-Agent": "leankg-dataset-script"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        except OSError as exc:
            print(f"download failed: {exc}", file=sys.stderr)
            return 1
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".txt"))
            raw.write_bytes(zf.read(name))
    gold = pubtator_to_gold(raw, NCBI_TYPE_MAP, "ncbi", limit_sentences=args.limit)
    path = dump_gold(gold, OUT / "gold.en.jsonl")
    n_ents = sum(len(g.entities) for g in gold)
    print(f"wrote {path}: {len(gold)} sentences, {n_ents} Condition mentions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
