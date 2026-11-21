"""Download plain-text Japanese Wikipedia articles on Toyota Production System concepts.

Licence: Japanese Wikipedia text is CC BY-SA 4.0 (and GFDL). Each file gets an attribution
header (title, URL, licence). Files go to ./data/ja_wikipedia_tps/ (git-ignored); if you
redistribute anything derived from them, keep the attribution and share-alike terms.

Usage: uv run python domains/manufacturing/scripts/download_ja_wikipedia_tps.py
Then:  uv run leankg build data/ja_wikipedia_tps --domain manufacturing
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TITLES = ["トヨタ生産方式", "自働化", "アンドン", "ポカヨケ", "なぜなぜ分析", "カイゼン",
          "ジャストインタイム生産システム", "かんばん方式", "現地現物"]  # fmt: skip
API = "https://ja.wikipedia.org/w/api.php"
OUT = Path("data/ja_wikipedia_tps")


def fetch(title: str) -> str | None:
    q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1,
                                "titles": title, "format": "json", "redirects": 1})  # fmt: skip
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "leankg-dataset-script"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        pages = json.loads(resp.read())["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("extract")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for title in TITLES:
        try:
            text = fetch(title)
        except OSError as exc:
            print(f"{title}: failed: {exc}", file=sys.stderr)
            continue
        if not text:
            print(f"{title}: no article", file=sys.stderr)
            continue
        url = "https://ja.wikipedia.org/wiki/" + urllib.parse.quote(title)
        header = f"# {title}\n# 出典: Wikipedia日本語版 {url} (CC BY-SA 4.0)\n\n"
        (OUT / f"{title}.txt").write_text(header + text, encoding="utf-8")
        ok += 1
        time.sleep(1)
    print(f"wrote {ok} articles to {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
