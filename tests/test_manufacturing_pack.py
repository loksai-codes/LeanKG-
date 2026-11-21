"""Manufacturing pack data files (M5: no engine changes)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .conftest import DOMAINS

PACK = DOMAINS / "manufacturing"


def _load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, PACK / "scripts" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_maintie_converter_maps_types_and_relations() -> None:
    mod = _load_script("download_maintie")
    rec = {
        "tokens": ["<id>", "air", "conditioner", "thermostat", "not", "working"],
        "entities": [
            {"start": 1, "end": 3, "type": "PhysicalObject/EmittingObject/ElectricCoolingObject"},
            {"start": 3, "end": 4, "type": "PhysicalObject/SensingObject/TemperatureSensingObject"},
            {"start": 4, "end": 6, "type": "State/UndesirableState/FailedState"},
        ],
        "relations": [
            {"head": 0, "tail": 1, "type": "hasPart"},
            {"head": 2, "tail": 1, "type": "hasParticipant/hasPatient"},
        ],
    }
    ex = mod.convert([rec])[0]
    assert [(e.text, e.type) for e in ex.entities] == [
        ("air conditioner", "Component"), ("thermostat", "Sensor"), ("not working", "FailureMode"),
    ]  # fmt: skip
    # hasPart(Component, Sensor) is not Component-Component -> dropped; hasPatient on a Sensor too
    assert ex.relations == []
    rec["entities"][1]["type"] = "PhysicalObject/ControllingObject/Thermostat"
    ex = mod.convert([rec])[0]
    assert {(r.head, r.type, r.tail) for r in ex.relations} == {
        (1, "PART_OF", 0), (1, "HAS_FAILURE_MODE", 2),
    }  # fmt: skip


def test_pack_files_present() -> None:
    for rel in ["DATA.md", "demo_queries.cypher", "llm_hints.md", "llm_hints.ja.md",
                "eval/labelstudio/config.xml", "eval/labelstudio/tasks.ja.json"]:  # fmt: skip
        assert (PACK / rel).is_file(), rel
    sentences = (PACK / "eval" / "labelstudio" / "sentences.ja.txt").read_text(encoding="utf-8")
    assert len([s for s in sentences.splitlines() if s.strip()]) >= 100


def test_tps_concepts_have_ja_terms() -> None:
    from leankg.domain.loader import load_pack

    pack = load_pack("manufacturing")
    for cid, ja in [("MF:jidoka", "自働化"), ("MF:andon", "アンドン"), ("MF:poka_yoke", "ポカヨケ"),
                    ("MF:five_whys", "なぜなぜ分析"), ("MF:kaizen", "カイゼン"),
                    ("MF:jit", "ジャスト・イン・タイム")]:  # fmt: skip
        assert pack.concepts[cid].preferred("ja") == ja
    for rel in pack.ontology.relations.values():
        assert rel.labels.get("ja")


def test_demo_queries_use_cjk_index() -> None:
    text = (PACK / "demo_queries.cypher").read_text(encoding="utf-8")
    assert "entity_names" in text
    assert "chunk_embedding" in text
    assert "CAUSED_BY*1..5" in text


def test_ja_example_builds_triples_for_all_relation_families() -> None:
    from leankg.pipeline import Pipeline

    pipe = Pipeline.from_domain("manufacturing", llm="none", setup="A")
    pipe.build(
        Path(__file__).resolve().parents[1]
        / "examples"
        / "manufacturing"
        / "maintenance_log_ja.txt"
    )
    types = {t.type for t in pipe.graph.facts()}
    assert {"CAUSED_BY", "DETECTED_BY", "PREVENTS", "PART_OF"} <= types
