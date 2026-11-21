from pathlib import Path

import pytest

from leankg.domain.loader import PackValidationError, available_packs, load_pack


@pytest.mark.parametrize("name", ["health_stress", "manufacturing"])
def test_shipped_packs_load(name: str) -> None:
    pack = load_pack(name)
    assert pack.name == name
    assert pack.entity_types
    assert pack.relation_types
    assert pack.terms_for("en")
    assert pack.terms_for("ja")
    for t in pack.ontology.entities.values():
        assert t.labels.get("en")
        assert t.labels.get("ja")


def test_available_packs() -> None:
    assert {"health_stress", "manufacturing"} <= set(available_packs())


def test_concepts_merge_languages() -> None:
    pack = load_pack("health_stress")
    stress = pack.concepts["HS:stress"]
    assert stress.preferred("en") == "stress"
    assert stress.preferred("ja") == "ストレス"


def test_relation_schema_checks() -> None:
    pack = load_pack("health_stress")
    assert pack.relation_allowed("REDUCES", "Intervention", "Symptom")
    assert not pack.relation_allowed("REDUCES", "Symptom", "Intervention")
    assert "TREATS" in pack.allowed_relations("Intervention", "Condition")
    # symmetric wildcard relation
    assert pack.relation_allowed("ASSOCIATED_WITH", "Biomarker", "Outcome")


def _write_pack(
    root: Path, dictionary: str, patterns: str = "", ontology: str | None = None
) -> Path:
    (root / "dictionaries").mkdir(parents=True)
    (root / "patterns").mkdir()
    (root / "ontology.yaml").write_text(
        ontology
        or "version: 1\nname: tiny\nentities:\n  Thing: {labels: {en: Thing, ja: 物}}\n"
        "relations:\n  RELATES: {from: [Thing], to: [Thing]}\n",
        encoding="utf-8",
    )
    (root / "dictionaries" / "d.csv").write_text(dictionary, encoding="utf-8")
    (root / "patterns" / "entities.jsonl").write_text(patterns, encoding="utf-8")
    return root


def test_dictionary_errors_have_file_and_line(tmp_path: Path) -> None:
    root = _write_pack(
        tmp_path / "tiny",
        "id,type,lang,term,synonyms,source\nT:1,Thing,en,widget,,x\nT:2,Nope,en,gadget,,x\n"
        "T:3,Thing,en,,,x\n",
    )
    with pytest.raises(PackValidationError) as exc:
        load_pack(root)
    msgs = "\n".join(exc.value.errors)
    assert "dictionaries/d.csv:3: unknown entity type 'Nope'" in msgs
    assert "dictionaries/d.csv:4: empty 'term'" in msgs


def test_pattern_errors_have_line(tmp_path: Path) -> None:
    root = _write_pack(
        tmp_path / "tiny",
        "id,type,lang,term,synonyms,source\nT:1,Thing,en,widget,,x\n",
        patterns='// comment\n{"id": "p1", "type": "Thing", "pattern": "("}\nnot json\n',
    )
    with pytest.raises(PackValidationError) as exc:
        load_pack(root)
    msgs = "\n".join(exc.value.errors)
    assert "patterns/entities.jsonl:2: invalid regex" in msgs
    assert "patterns/entities.jsonl:3: invalid JSON" in msgs


def test_ontology_reference_errors(tmp_path: Path) -> None:
    root = _write_pack(
        tmp_path / "tiny",
        "id,type,lang,term,synonyms,source\n",
        ontology="version: 1\nentities:\n  Thing: {}\nrelations:\n"
        "  BAD: {from: [Thing], to: [Missing]}\n",
    )
    with pytest.raises(PackValidationError) as exc:
        load_pack(root)
    assert any("ontology.yaml:5" in e and "Missing" in e for e in exc.value.errors)


def test_missing_pack() -> None:
    with pytest.raises(FileNotFoundError):
        load_pack("no_such_pack_xyz")
