"""Convert public corpora into the leankg gold format.

* PubTator (NCBI Disease, BC5CDR): title|abstract text with offset annotations. Documents
  are split into sentences with the language profile; annotations crossing a sentence
  boundary are dropped. Annotation types are mapped to ontology types (unmapped → dropped).
* MaintIE (manufacturing, M5) lives in its own converter once its format is confirmed.

The datasets themselves are never committed: download them with ``scripts/download_*.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from leankg.eval.gold import GoldEntity, GoldExample

NCBI_TYPE_MAP = {
    "SpecificDisease": "Condition",
    "DiseaseClass": "Condition",
    "Modifier": "Condition",
    "CompositeMention": "Condition",
}
BC5CDR_TYPE_MAP = {"Disease": "Condition"}  # Chemical has no health_stress type


@dataclass
class PubTatorDoc:
    pmid: str
    text: str
    annotations: list[tuple[int, int, str, str, str]] = field(default_factory=list)
    """(start, end, surface, type, concept id)"""


_TITLE = re.compile(r"^(\d+)\|t\|(.*)$")
_ABSTRACT = re.compile(r"^(\d+)\|a\|(.*)$")


def read_pubtator(path: str | Path) -> Iterator[PubTatorDoc]:
    doc: PubTatorDoc | None = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            if doc is not None:
                yield doc
                doc = None
            continue
        if m := _TITLE.match(line):
            doc = PubTatorDoc(pmid=m.group(1), text=m.group(2))
            continue
        if (m := _ABSTRACT.match(line)) and doc is not None:
            doc.text = f"{doc.text} {m.group(2)}"
            continue
        parts = line.split("\t")
        if doc is not None and len(parts) >= 5 and parts[1].isdigit():
            start, end = int(parts[1]), int(parts[2])
            if parts[3] and doc.text[start:end] == parts[3]:
                doc.annotations.append(
                    (start, end, parts[3], parts[4], parts[5] if len(parts) > 5 else "")
                )
    if doc is not None:
        yield doc


def pubtator_to_gold(
    path: str | Path,
    type_map: dict[str, str],
    source: str,
    *,
    limit_sentences: int | None = None,
    keep_empty: bool = True,
) -> list[GoldExample]:
    """Sentence-level gold examples (EN) from a PubTator file."""
    from leankg.lang.en import EnglishProfile

    splitter = EnglishProfile()
    out: list[GoldExample] = []
    for doc in read_pubtator(path):
        for k, (s, e) in enumerate(splitter.split_sentences(doc.text)):
            text = doc.text[s:e]
            ents = [
                GoldEntity(start=a - s, end=b - s, text=surface, type=type_map[t], id=None)
                for a, b, surface, t, _cid in sorted(doc.annotations)
                if t in type_map and a >= s and b <= e
            ]
            if not ents and not keep_empty:
                continue
            # drop overlapping gold spans (keep the longest)
            ents.sort(key=lambda x: (x.start, -(x.end - x.start)))
            dedup: list[GoldEntity] = []
            for ent in ents:
                if dedup and ent.start < dedup[-1].end:
                    continue
                dedup.append(ent)
            out.append(
                GoldExample(
                    id=f"{source}-{doc.pmid}-s{k}",
                    lang="en",
                    text=text,
                    entities=dedup,
                    source=source,
                )
            )
            if limit_sentences is not None and len(out) >= limit_sentences:
                return out
    return out
