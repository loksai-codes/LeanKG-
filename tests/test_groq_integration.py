"""Live Groq tests. Skipped unless GROQ_API_KEY is set (env or .env). Costs fractions of a cent.

Run: uv run pytest -m integration tests/test_groq_integration.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from leankg.config import load_config
from leankg.models import AllowedRelation, Document, HardCase, HardCaseEntity, HardCaseReason

from .conftest import ROOT

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def cfg():  # type: ignore[no-untyped-def]
    pytest.importorskip("groq")
    config = load_config(ROOT / "leankg.toml", dotenv=ROOT / ".env")
    if config.llm.api_key is None:
        pytest.skip("GROQ_API_KEY not set")
    config.llm.provider = "groq"
    return config


def test_configured_model_is_served(cfg) -> None:  # type: ignore[no-untyped-def]
    from leankg.llm.groq_client import GroqClient

    client = GroqClient(cfg.llm)
    assert cfg.llm.model in client.list_models()


def test_live_classify_en_and_ja(cfg) -> None:  # type: ignore[no-untyped-def]
    from leankg.llm.groq_client import GroqClient

    client = GroqClient(cfg.llm)
    cases = [
        HardCase(
            case_id="en1", doc_id="d", sent_id="s1", lang="en",
            sentence="Seal wear was found to be the reason for the oil leak.",
            entities=[HardCaseEntity(index=0, surface="Seal wear", type="Cause", mention_id="m0"),
                      HardCaseEntity(index=1, surface="oil leak", type="FailureMode", mention_id="m1")],
            allowed=[AllowedRelation(head=1, tail=0, types=["CAUSED_BY"])],
            reasons=[HardCaseReason.NO_RULE_RELATION],
        ),
        HardCase(
            case_id="ja1", doc_id="d", sent_id="s2", lang="ja",
            sentence="摩耗は漏れの原因ではなかった。",
            entities=[HardCaseEntity(index=0, surface="摩耗", type="Cause", mention_id="m2"),
                      HardCaseEntity(index=1, surface="漏れ", type="FailureMode", mention_id="m3")],
            allowed=[AllowedRelation(head=1, tail=0, types=["CAUSED_BY"])],
            reasons=[HardCaseReason.COMPLEX_NEGATION],
        ),
    ]  # fmt: skip
    verdicts = {v.case_id: v for v in client.classify(cases)}
    assert verdicts["en1"].relations[0].type == "CAUSED_BY"
    assert verdicts["ja1"].relations
    assert verdicts["ja1"].relations[0].negated is True
    assert client.usage.tokens_in > 0


def test_live_build_then_cache(cfg, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from leankg.pipeline import Pipeline

    cfg.llm.cache_path = str(tmp_path / "cache.sqlite")
    cfg.llm.log_path = str(tmp_path / "log.jsonl")
    text = "ホースの亀裂が見つかった。\n\nThe seal and the leak were inspected."
    first = Pipeline.from_domain("manufacturing", config=cfg, setup="C", skip=["gliner", "embed"])
    first.run([Document(id="d", text=text)])
    assert first.report.llm_requests >= 1
    second = Pipeline.from_domain("manufacturing", config=cfg, setup="C", skip=["gliner", "embed"])
    second.run([Document(id="d", text=text)])
    assert second.report.llm_requests == 0
    assert second.report.cache_hit_rate == 1.0
