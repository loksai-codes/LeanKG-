"""LLM fallback: schema, prompt, cache, resolver, clients (all with fakes — no network)."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from leankg.config import Config, LLMConfig
from leankg.llm.base import LLMError
from leankg.llm.cache import VerdictCache, cache_key, normalize_sentence
from leankg.llm.fake_client import FakeClient
from leankg.llm.groq_client import GroqClient, parse_reset
from leankg.llm.ollama_client import OllamaClient
from leankg.llm.prompt import PROMPT_VERSION, build_messages
from leankg.llm.resolver import Resolver
from leankg.llm.schema import response_format, strict_violations, verdict_schema
from leankg.llm.validate import check_verdict, parse_response
from leankg.models import (
    AllowedRelation,
    Document,
    HardCase,
    HardCaseEntity,
    HardCaseReason,
    LLMRelation,
    LLMVerdict,
)
from leankg.pipeline import Pipeline

from .conftest import ROOT
from .helpers import make_ctx

SNAPSHOTS = Path(__file__).parent / "snapshots"


def _case(cid: str = "c1", lang: str = "en", sentence: str = "Wear may cause leaks.") -> HardCase:
    if lang == "ja":
        ents = [("摩耗", "Cause"), ("漏れ", "FailureMode")]
    else:
        ents = [("Wear", "Cause"), ("leaks", "FailureMode")]
    return HardCase(
        case_id=cid,
        doc_id="d",
        sent_id=f"s-{cid}",
        lang=lang,
        sentence=sentence,
        entities=[
            HardCaseEntity(index=i, surface=s, type=t, mention_id=f"m{i}")
            for i, (s, t) in enumerate(ents)
        ],
        allowed=[AllowedRelation(head=1, tail=0, types=["CAUSED_BY"])],
        reasons=[HardCaseReason.NO_RULE_RELATION],
    )


# --------------------------------------------------------------- schema
def test_schema_is_strict_mode_compliant() -> None:
    schema = verdict_schema()
    assert strict_violations(schema) == []
    rel = schema["properties"]["verdicts"]["items"]["properties"]["relations"]["items"]
    assert set(rel["required"]) == {"head", "tail", "type", "negated", "hedged", "confidence"}
    link = schema["properties"]["verdicts"]["items"]["properties"]["link_choice"]
    assert link["type"] == ["integer", "null"]
    fmt = response_format()
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True


def test_strict_violations_detects_problems() -> None:
    assert strict_violations({"type": "object", "properties": {"a": {}}, "required": []})


# --------------------------------------------------------------- prompt
@pytest.mark.parametrize("lang", ["en", "ja"])
def test_prompt_snapshot(lang: str) -> None:
    pack = make_ctx("manufacturing").require_pack()
    sentence = "Wear may cause leaks." if lang == "en" else "摩耗は漏れの原因かもしれない。"
    messages = build_messages(
        [_case(lang=lang, sentence=sentence)], {"en": "EN-HINTS", "ja": "JA-HINTS"}
    )
    rendered = f"PROMPT_VERSION={PROMPT_VERSION}\n" + "\n---\n".join(
        f"[{m['role']}]\n{m['content']}" for m in messages
    )
    snap = SNAPSHOTS / f"prompt_{lang}.txt"
    if not snap.exists():  # first run writes the snapshot; review it, then commit
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(rendered, encoding="utf-8")
    assert rendered == snap.read_text(encoding="utf-8")
    assert pack.name == "manufacturing"


def test_prompt_attaches_language_hints() -> None:
    user = build_messages([_case(lang="ja")], {"en": "EN-HINTS", "ja": "JA-HINTS"})[1]["content"]
    assert "EN-HINTS" in user
    assert "JA-HINTS" in user
    user_en = build_messages([_case()], {"en": "EN-HINTS", "ja": "JA-HINTS"})[1]["content"]
    assert "JA-HINTS" not in user_en


# --------------------------------------------------------- validation
def test_verdict_checks_indices_and_types() -> None:
    case = _case()
    v = LLMVerdict(case_id="c1", relations=[
        LLMRelation(head=1, tail=0, type="CAUSED_BY", confidence=0.9),
        LLMRelation(head=0, tail=1, type="CAUSED_BY", confidence=0.9),  # wrong direction
        LLMRelation(head=5, tail=0, type="CAUSED_BY", confidence=0.9),  # bad index
        LLMRelation(head=1, tail=0, type="PART_OF", confidence=0.9),  # not allowed
    ], link_choice=3)  # fmt: skip
    clean, problems = check_verdict(case, v)
    assert [(r.head, r.tail, r.type) for r in clean.relations] == [(1, 0, "CAUSED_BY")]
    assert clean.link_choice is None
    assert len(problems) == 4


def test_parse_response_salvages() -> None:
    text = 'noise {"verdicts": [{"case_id": "c1", "relations": [], "link_choice": null}]} tail'
    assert parse_response(text)[0].case_id == "c1"
    assert parse_response("not json") == []


# --------------------------------------------------------------- cache
def test_cache_roundtrip_and_key(tmp_path: Path) -> None:
    cache = VerdictCache(tmp_path / "c.sqlite")
    case = _case()
    key = cache_key(case, "m", "p1", "s1")
    assert key == cache_key(_case(cid="other"), "m", "p1", "s1")  # case id not in the key
    assert key != cache_key(case, "m2", "p1", "s1")
    assert key != cache_key(case, "m", "p2", "s1")
    v = LLMVerdict(
        case_id="c1", relations=[LLMRelation(head=1, tail=0, type="CAUSED_BY", confidence=0.7)]
    )
    cache.put(key, v, "m")
    got = cache.get(key, "new-id")
    assert got is not None
    assert got.case_id == "new-id"
    assert got.relations == v.relations
    assert normalize_sentence(" Ｅ-1234  Leak ") == "e-0000 leak"


# ------------------------------------------------------------ resolver
def _responder(case: HardCase) -> LLMVerdict:
    return LLMVerdict(case_id=case.case_id,
                      relations=[LLMRelation(head=1, tail=0, type="CAUSED_BY", confidence=0.8)])  # fmt: skip


def test_resolver_cache_dedupe_batching(tmp_path: Path) -> None:
    cfg = LLMConfig(provider="fake", batch_size=2, max_concurrency=1)
    client = FakeClient(responder=_responder)
    cache = VerdictCache(tmp_path / "c.sqlite")
    resolver = Resolver(client, cfg, "s", cache, tmp_path / "log.jsonl")
    cases = [
        _case("a", sentence="Wear may cause leaks."),
        _case("b", sentence="Wear may cause leaks!"),  # near duplicate -> dedupe
        _case("c", sentence="Seal wear causes leaks."),
        _case("d", lang="ja", sentence="摩耗は漏れの原因かもしれない。"),
    ]
    res = resolver.resolve(cases)
    assert set(res.verdicts) == {"a", "b", "c", "d"}
    assert res.by_lang["en"].dedupe_hits == 1
    assert all({c.lang for c in batch} in ({"en"}, {"ja"}) for batch in client.calls)
    assert sum(len(b) for b in client.calls) == 3
    assert (tmp_path / "log.jsonl").read_text(encoding="utf-8").count("\n") == 3
    # second run: everything from cache, no new requests
    calls_before = len(client.calls)
    res2 = Resolver(client, cfg, "s", cache).resolve(cases)
    assert len(client.calls) == calls_before
    assert res2.by_lang["en"].cache_hits == 3
    assert res2.by_lang["ja"].cache_hits == 1


def test_budget_cap_degrades_instead_of_failing() -> None:
    cfg = LLMConfig(
        provider="fake", batch_size=1, budget_calls=1, max_concurrency=1, use_cache=False
    )
    client = FakeClient(responder=_responder)
    cases = [
        _case(str(i), sentence=f"Sentence number {i} about wear and leaks {'x' * i * 10}.")
        for i in range(3)
    ]
    res = Resolver(client, cfg, "s").resolve(cases)
    assert res.budget_exhausted
    assert len(res.verdicts) == 1
    assert len(res.skipped) == 2


def test_failed_batch_is_skipped_not_raised() -> None:
    def boom(case: HardCase) -> LLMVerdict:
        raise RuntimeError("provider down")

    res = Resolver(FakeClient(responder=boom), LLMConfig(use_cache=False), "s").resolve([_case()])
    assert res.skipped == {"c1"}
    assert res.errors


# --------------------------------------------------------------- Groq
class FakeRateLimit(Exception):
    status_code = 429

    def __init__(self, headers: dict[str, str]) -> None:
        super().__init__("rate limited")
        self.response = SimpleNamespace(status_code=429, headers=headers)


class FakeGroqSDK:
    def __init__(
        self, content: str, fail_times: int = 0, models: tuple[str, ...] = ("openai/gpt-oss-20b",)
    ) -> None:
        self.content = content
        self.fail_times = fail_times
        self.requests: list[dict[str, Any]] = []
        self.models = SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id=m) for m in models])
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise FakeRateLimit({"retry-after": "2"})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(prompt_tokens=500, completion_tokens=60),
        )


ANSWER = ('{"verdicts": [{"case_id": "c1", "relations": [{"head": 1, "tail": 0, "type": "CAUSED_BY",'
          ' "negated": false, "hedged": true, "confidence": 0.81}], "link_choice": null}]}')  # fmt: skip


def _groq_cfg(**kw: Any) -> LLMConfig:
    return LLMConfig(provider="groq", model="openai/gpt-oss-20b", **kw)


def test_groq_request_shape_and_usage() -> None:
    sdk = FakeGroqSDK(ANSWER)
    client = GroqClient(_groq_cfg(), client=sdk)
    verdicts = client.classify([_case()])
    assert verdicts[0].relations[0].hedged is True
    req = sdk.requests[0]
    assert req["model"] == "openai/gpt-oss-20b"
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["extra_body"] == {"reasoning_effort": "low", "include_reasoning": False}
    assert "stream" not in req
    assert "tools" not in req
    assert (client.usage.requests, client.usage.tokens_in, client.usage.tokens_out) == (1, 500, 60)


def test_groq_429_retry_after_then_success() -> None:
    waits: list[float] = []
    sdk = FakeGroqSDK(ANSWER, fail_times=2)
    client = GroqClient(_groq_cfg(), client=sdk, sleep=waits.append)
    assert client.classify([_case()])
    assert len(waits) == 2
    assert all(2.0 <= w <= 2.5 for w in waits)  # retry-after + jitter
    assert client.usage.retries == 2


def test_groq_gives_up_after_max_retries() -> None:
    sdk = FakeGroqSDK(ANSWER, fail_times=10)
    client = GroqClient(_groq_cfg(max_retries=1), client=sdk, sleep=lambda s: None)
    with pytest.raises(LLMError, match="429"):
        client.classify([_case()])


def test_groq_model_check_fails_clearly() -> None:
    sdk = FakeGroqSDK(ANSWER, models=("some/other-model",))
    client = GroqClient(_groq_cfg(), client=sdk)
    with pytest.raises(LLMError, match="leankg llm-models"):
        client.classify([_case()])


def test_groq_needs_key_and_model() -> None:
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqClient(_groq_cfg())
    with pytest.raises(LLMError, match="model"):
        GroqClient(LLMConfig(provider="groq"), client=object())


def test_groq_escalation_for_low_confidence() -> None:
    low = ANSWER.replace("0.81", "0.3")
    sdk = FakeGroqSDK(low, models=("openai/gpt-oss-20b", "openai/gpt-oss-120b"))
    client = GroqClient(_groq_cfg(escalation_model="openai/gpt-oss-120b"), client=sdk)
    client.classify([_case()])
    assert [r["model"] for r in sdk.requests] == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    assert client.usage.escalations == 1


@pytest.mark.parametrize(("value", "seconds"), [("2", 2.0), ("7.66s", 7.66), ("2m59.56s", 179.56),
                                                ("120ms", 0.12), ("", None), ("soon", None)])  # fmt: skip
def test_parse_reset(value: str, seconds: float | None) -> None:
    got = parse_reset(value)
    assert got == pytest.approx(seconds) if seconds is not None else got is None


# -------------------------------------------------------------- Ollama
def test_ollama_client_with_fake() -> None:
    class FakeOllama:
        def chat(self, **kw: Any) -> dict[str, Any]:
            assert kw["format"]["type"] == "object"
            return {"message": {"content": ANSWER}, "prompt_eval_count": 100, "eval_count": 20}

        def list(self) -> dict[str, Any]:
            return {"models": [{"model": "qwen3:8b"}]}

    client = OllamaClient(LLMConfig(provider="ollama", model="qwen3:8b"), client=FakeOllama())
    assert client.classify([_case()])[0].relations[0].type == "CAUSED_BY"
    assert client.list_models() == ["qwen3:8b"]
    assert client.usage.tokens_in == 100


# --------------------------------------------- pipeline: router + LLM stage
FAKE_FIXTURE = ROOT / "tests" / "fixtures" / "fake_llm.json"


def _pipe(tmp_path: Path, setup: str = "C") -> Pipeline:
    cfg = Config()
    cfg.llm.provider = "fake"
    cfg.llm.fake_fixture = str(FAKE_FIXTURE)
    cfg.llm.cache_path = str(tmp_path / "cache.sqlite")
    cfg.llm.log_path = str(tmp_path / "llm_log.jsonl")
    return Pipeline.from_domain("manufacturing", config=cfg, setup=setup, skip=["gliner", "embed"])


def test_hard_case_resolved_by_llm(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    doc = pipe.run([Document(id="d", text="ホースの亀裂が見つかった。")])[0]
    assert doc.hard_cases
    assert HardCaseReason.NO_RULE_RELATION in doc.hard_cases[0].reasons or doc.hard_cases[0].reasons
    llm = [t for t in doc.triples if t.method == "llm"]
    assert [(t.type, t.status) for t in llm] == [("HAS_FAILURE_MODE", "accepted")]
    assert pipe.report.llm_requests == 1
    assert pipe.report.llm_call_rate == 1.0
    assert pipe.report.by_lang["ja"].llm_sentences == 1


def test_second_build_hits_cache(tmp_path: Path) -> None:
    text = "ホースの亀裂が見つかった。\n\nThe seal and the leak were inspected."
    _pipe(tmp_path).run([Document(id="d", text=text)])
    pipe2 = _pipe(tmp_path)
    pipe2.run([Document(id="d", text=text)])
    assert pipe2.report.llm_requests == 0
    assert pipe2.report.cache_hit_rate == 1.0


def test_confident_rule_sentences_are_not_routed(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    doc = pipe.run([Document(id="d", text="The gearbox is part of the conveyor.")])[0]
    assert doc.hard_cases == []
    assert pipe.report.llm_requests == 0


def test_llm_none_keeps_candidates_unverified(tmp_path: Path) -> None:
    pipe = Pipeline.from_domain("manufacturing", llm="none", setup="C", skip=["gliner", "embed"])
    doc = pipe.run([Document(id="d", text="ホースの亀裂が見つかった。")])[0]
    assert doc.hard_cases  # still routed (so hard-case rate is reported)
    assert {t.status for t in doc.triples} <= {"unverified", "accepted", "negative"}
    assert pipe.report.llm_call_rate == 0.0
    assert pipe.report.hard_case_rate > 0


def test_setup_d_routes_every_multi_entity_sentence(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path, setup="D")
    doc = pipe.run([Document(id="d", text="The gearbox is part of the conveyor.")])[0]
    assert doc.hard_cases[0].reasons == [HardCaseReason.ROUTE_ALL]
    assert not [t for t in doc.triples if t.method in ("dep", "trigger")]


# -------------------------------------------------------------- review-llm
def test_review_llm_suggest_and_apply(tmp_path: Path) -> None:
    from leankg.domain.loader import load_pack
    from leankg.llm import review

    pack_dir = tmp_path / "manufacturing"
    shutil.copytree(ROOT / "domains" / "manufacturing", pack_dir)
    pack = load_pack(pack_dir)
    entries = []
    for i, s in enumerate(["摩耗が漏れを誘起した。", "腐食が亀裂を誘起した。"]):
        a, b = ("摩耗", "漏れ") if i == 0 else ("腐食", "亀裂")
        case = HardCase(
            case_id=f"c{i}", doc_id="d", sent_id="s", lang="ja", sentence=s,
            entities=[HardCaseEntity(index=0, surface=a, type="Cause", mention_id="m0"),
                      HardCaseEntity(index=1, surface=b, type="FailureMode", mention_id="m1")],
            allowed=[AllowedRelation(head=1, tail=0, types=["CAUSED_BY"])],
            reasons=[HardCaseReason.NO_RULE_RELATION],
        )  # fmt: skip
        verdict = LLMVerdict(
            case_id=f"c{i}",
            relations=[LLMRelation(head=1, tail=0, type="CAUSED_BY", confidence=0.9)],
        )
        entries.append((case, verdict))
    triggers, _ = review.suggest(entries, pack, min_count=2)
    assert [(t.lang, t.relation, t.phrase, t.position, t.order) for t in triggers] == [
        ("ja", "CAUSED_BY", "誘起", "after", "reverse")
    ]
    written = review.apply(pack, triggers, [])
    assert written[0].name == "relations.ja.learned.yaml"
    reloaded = load_pack(pack_dir)
    assert any(r.id.startswith("learned-") for r in reloaded.relations_for("ja").triggers)
    assert any(r.id == "ja-trig-genin-after" for r in reloaded.relations_for("ja").triggers)
