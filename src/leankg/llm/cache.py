"""SQLite cache for LLM verdicts + the near-duplicate normalization used for dedupe.

Cache key (docs/GROQ.md): ``sha256(normalized_sentence + entity_list + schema_version +
model + prompt_version)``. Stored verdicts omit the ``case_id`` (restored on read), so the
same sentence in another document or run is a hit.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path

from leankg.models import HardCase, LLMVerdict

_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"\d")


def normalize_sentence(text: str) -> str:
    """NFKC, collapse whitespace, digits → 0, lowercase (for keys and near-dup matching)."""
    t = unicodedata.normalize("NFKC", text)
    return _DIGITS.sub("0", _WS.sub(" ", t)).strip().lower()


def entity_signature(case: HardCase) -> str:
    return "|".join(f"{e.index}:{normalize_sentence(e.surface)}:{e.type}" for e in case.entities)


def cache_key(case: HardCase, model: str, prompt_version: str, schema_version: str) -> str:
    allowed = ";".join(f"{a.head}>{a.tail}:{','.join(a.types)}" for a in case.allowed)
    link = "|".join(case.link_question.option_ids) if case.link_question is not None else ""
    payload = "\x1f".join(
        [normalize_sentence(case.sentence), entity_signature(case), allowed, link,
         schema_version, model, prompt_version]
    )  # fmt: skip
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class VerdictCache:
    """Thread-safe SQLite cache (one file, created on first use)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS verdicts (key TEXT PRIMARY KEY, verdict TEXT NOT NULL, "
            "model TEXT, created REAL)"
        )
        self._conn.commit()

    def get(self, key: str, case_id: str) -> LLMVerdict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT verdict FROM verdicts WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        data["case_id"] = case_id
        return LLMVerdict.model_validate(data)

    def put(self, key: str, verdict: LLMVerdict, model: str) -> None:
        data = verdict.model_dump()
        data.pop("case_id", None)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO verdicts (key, verdict, model, created) VALUES (?, ?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), model, time.time()),
            )
            self._conn.commit()

    def __len__(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0])

    def close(self) -> None:
        self._conn.close()
