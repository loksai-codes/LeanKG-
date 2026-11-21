"""Resolver: everything that keeps LLM calls low around a client.

1. **cache** — SQLite, keyed per case (docs/GROQ.md);
2. **dedupe** — near-identical sentences with the same entities inside one run share one
   answer (normalized text, RapidFuzz ratio ≥ ``dedupe_threshold``);
3. **batching** — ``batch_size`` cases per request, grouped by language so the right
   few-shot examples are attached;
4. **budget cap** — when ``budget_calls`` requests or ``budget_tokens`` tokens are used up,
   the remaining cases are *skipped* (the caller keeps them as unverified candidates) —
   never an exception;
5. **logging** — every fresh answer is appended to a JSONL log for ``leankg review-llm``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from leankg.config import LLMConfig
from leankg.llm.cache import VerdictCache, cache_key, entity_signature, normalize_sentence
from leankg.llm.prompt import PROMPT_VERSION
from leankg.models import HardCase, LLMVerdict

log = logging.getLogger(__name__)


@dataclass
class LangCounts:
    cases: int = 0
    cache_hits: int = 0
    dedupe_hits: int = 0
    sent: int = 0
    budget_skipped: int = 0
    failed: int = 0


@dataclass
class ResolveResult:
    verdicts: dict[str, LLMVerdict] = field(default_factory=dict)
    skipped: set[str] = field(default_factory=set)
    by_lang: dict[str, LangCounts] = field(default_factory=lambda: defaultdict(LangCounts))
    budget_exhausted: bool = False
    errors: list[str] = field(default_factory=list)


def schema_version(ontology_relations: dict[str, Any]) -> str:
    payload = json.dumps(ontology_relations, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


class Resolver:
    def __init__(
        self,
        client: Any,
        cfg: LLMConfig,
        schema_ver: str = "",
        cache: VerdictCache | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        self.client = client
        self.cfg = cfg
        self.schema_ver = schema_ver
        self.cache = cache
        self.log_path = Path(log_path) if log_path else None
        self._lock = threading.Lock()
        self.requests_made = 0

    # ------------------------------------------------------------- helpers
    def _key(self, case: HardCase) -> str:
        return cache_key(case, getattr(self.client, "model", ""), PROMPT_VERSION, self.schema_ver)

    def _dedupe(self, cases: list[HardCase]) -> tuple[list[HardCase], dict[str, str]]:
        """Representatives to send + mapping duplicate case_id → representative case_id."""
        from rapidfuzz import fuzz

        reps: list[HardCase] = []
        alias: dict[str, str] = {}
        groups: dict[tuple[str, str], list[tuple[str, HardCase]]] = defaultdict(list)
        for case in cases:
            sig = (case.lang, entity_signature(case))
            norm = normalize_sentence(case.sentence)
            match = None
            for other_norm, other in groups[sig]:
                if other_norm == norm or fuzz.ratio(other_norm, norm) >= self.cfg.dedupe_threshold:
                    match = other
                    break
            if match is not None and [a.model_dump() for a in match.allowed] == [
                a.model_dump() for a in case.allowed
            ]:
                alias[case.case_id] = match.case_id
                continue
            groups[sig].append((norm, case))
            reps.append(case)
        return reps, alias

    def _budget_left(self) -> bool:
        usage = self.client.usage
        tokens = usage.tokens_in + usage.tokens_out
        return self.requests_made < self.cfg.budget_calls and tokens < self.cfg.budget_tokens

    def _log(self, batch: list[HardCase], verdicts: list[LLMVerdict]) -> None:
        if self.log_path is None:
            return
        by_id = {v.case_id: v for v in verdicts}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.log_path.open("a", encoding="utf-8") as fh:
            for case in batch:
                v = by_id.get(case.case_id)
                if v is None:
                    continue
                fh.write(
                    json.dumps(
                        {"model": getattr(self.client, "model", ""), "case": case.model_dump(),
                         "verdict": v.model_dump()},
                        ensure_ascii=False,
                    )
                    + "\n"
                )  # fmt: skip

    # ------------------------------------------------------------- resolve
    def resolve(self, cases: list[HardCase]) -> ResolveResult:
        res = ResolveResult()
        pending: list[HardCase] = []
        keys: dict[str, str] = {}
        for case in cases:
            res.by_lang[case.lang].cases += 1
            key = self._key(case)
            keys[case.case_id] = key
            hit = self.cache.get(key, case.case_id) if self.cache and self.cfg.use_cache else None
            if hit is not None:
                res.verdicts[case.case_id] = hit
                res.by_lang[case.lang].cache_hits += 1
            else:
                pending.append(case)

        reps, alias = self._dedupe(pending)
        by_lang: dict[str, list[HardCase]] = defaultdict(list)
        for case in reps:
            by_lang[case.lang].append(case)
        batches = [
            group[i : i + self.cfg.batch_size]
            for _lang, group in sorted(by_lang.items())
            for i in range(0, len(group), self.cfg.batch_size)
        ]

        def run(batch: list[HardCase]) -> tuple[list[HardCase], list[LLMVerdict] | None, str]:
            with self._lock:
                if not self._budget_left():
                    return batch, None, "budget"
                self.requests_made += 1
            try:
                return batch, self.client.classify(batch), ""
            except Exception as exc:
                log.warning("LLM batch failed: %s", exc)
                return batch, [], str(exc)

        workers = max(1, self.cfg.max_concurrency)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for batch, verdicts, err in pool.map(run, batches):
                if verdicts is None:
                    res.budget_exhausted = True
                    for c in batch:
                        res.skipped.add(c.case_id)
                        res.by_lang[c.lang].budget_skipped += 1
                    continue
                if err:
                    res.errors.append(err)
                    for c in batch:
                        res.skipped.add(c.case_id)
                        res.by_lang[c.lang].failed += 1
                    continue
                got = {v.case_id: v for v in verdicts}
                self._log(batch, verdicts)
                for c in batch:
                    res.by_lang[c.lang].sent += 1
                    v = got.get(c.case_id)
                    if v is None:
                        res.skipped.add(c.case_id)
                        res.by_lang[c.lang].failed += 1
                        continue
                    res.verdicts[c.case_id] = v
                    if self.cache is not None and self.cfg.use_cache:
                        self.cache.put(keys[c.case_id], v, getattr(self.client, "model", ""))

        cases_by_id = {c.case_id: c for c in cases}
        for dup, rep in alias.items():
            case = cases_by_id[dup]
            if rep in res.verdicts:
                v = res.verdicts[rep].model_copy(update={"case_id": dup})
                res.verdicts[dup] = v
                res.by_lang[case.lang].dedupe_hits += 1
                if self.cache is not None and self.cfg.use_cache:
                    self.cache.put(keys[dup], v, getattr(self.client, "model", ""))
            else:
                res.skipped.add(dup)
                res.by_lang[case.lang].budget_skipped += int(res.budget_exhausted)
        return res
