"""Print spaCy/GiNZA dependency parses (use before writing dependency patterns).

Usage: uv run python scripts/dump_parse.py en "Stress causes insomnia." [...]
       uv run python scripts/dump_parse.py ja --file sentences.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

from leankg.lang.base import make_profile


def dump(lang: str, sentences: list[str]) -> str:
    nlp = make_profile(lang).load_nlp()
    out = []
    for text in sentences:
        doc = nlp(text)
        out.append(f"# {text}")
        for t in doc:
            out.append(
                f"{t.i}\t{t.text}\t{t.lemma_}\t{t.pos_}\t{t.tag_}\t{t.dep_}\t{t.head.i}\t{t.morph}"
            )
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    lang, *rest = sys.argv[1:]
    if rest and rest[0] == "--file":
        rest = [ln for ln in Path(rest[1]).read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(dump(lang, rest))
