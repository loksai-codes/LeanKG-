from pathlib import Path

from leankg.config import Config
from leankg.models import Document
from leankg.stages.base import StageContext
from leankg.stages.ingest import IngestStage, LoaderOptions, load_documents
from leankg.stages.ingest.chunker import clean_text

from .conftest import ROOT

EXAMPLES = ROOT / "examples"


def _ingest(text: str, **chunk_cfg: int) -> Document:
    cfg = Config()
    if chunk_cfg:
        cfg.chunking.target_chars.update(chunk_cfg)
    return IngestStage(StageContext(config=cfg)).process(Document(id="d", text=text))


def test_clean_text() -> None:
    assert clean_text("a \t b\r\n\r\n\r\n\r\nc　d  ") == "a b\n\nc d"


def test_language_per_document_and_chunk() -> None:
    doc = _ingest(
        "Stress causes insomnia in many adults.\n\nストレスは不眠を引き起こす。\n\n"
        "Exercise helps a lot of people sleep better."
    )
    assert doc.lang == "en"
    assert [c.lang for c in doc.chunks] == ["en", "ja", "en"]


def test_chunk_offsets_and_sentences_are_consistent() -> None:
    text = " ".join(f"Sentence number {i} is here." for i in range(40))
    doc = _ingest(text, en=200)
    assert len(doc.chunks) > 1
    for c in doc.chunks:
        assert doc.text[c.start : c.end] == c.text
        assert len(c.text) <= 200 or len(c.sentences) == 1
        for s in c.sentences:
            assert c.text[s.start : s.end] == s.text
            assert s.lang == c.lang


def test_ja_chunk_target_is_smaller() -> None:
    text = "".join(f"これは{i}番目の文です。" for i in range(60))
    doc = _ingest(text)
    assert doc.lang == "ja"
    assert all(len(c.text) <= 400 for c in doc.chunks)
    assert sum(len(c.sentences) for c in doc.chunks) == 60


def test_ingest_is_idempotent() -> None:
    doc = _ingest("One. Two.")
    stage = IngestStage(StageContext(config=Config()))
    assert stage.process(doc).chunks == doc.chunks


def test_load_examples_folder() -> None:
    docs = load_documents(EXAMPLES / "health_stress")
    ids = {d.id for d in docs}
    assert {"stress_and_sleep_en.txt", "stress_and_sleep_ja.txt", "workplace_mixed.html"} <= ids
    html = next(d for d in docs if d.id.endswith(".html"))
    assert "Job stress" in html.text
    assert "<p>" not in html.text


def test_load_csv_with_text_column(tmp_path: Path) -> None:
    docs = load_documents(
        EXAMPLES / "manufacturing" / "complaints.csv",
        LoaderOptions(csv_text_column="summary", csv_id_column="complaint_id"),
    )
    assert [d.id for d in docs] == [
        "complaints.csv#S-001",
        "complaints.csv#S-002",
        "complaints.csv#S-003",
    ]
    assert docs[0].metadata["component"] == "ENGINE"


def test_load_cp932_text(tmp_path: Path) -> None:
    p = tmp_path / "sjis.txt"
    p.write_bytes("油圧ポンプの漏れ".encode("cp932"))
    assert load_documents(p)[0].text == "油圧ポンプの漏れ"


def test_load_pdf(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    p = tmp_path / "blank.pdf"
    w = PdfWriter()
    w.add_blank_page(width=100, height=100)
    with p.open("wb") as fh:
        w.write(fh)
    docs = load_documents(p)
    assert docs[0].metadata["pages"] == 1


def test_load_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "docs.jsonl"
    p.write_text(
        '{"id": "a", "text": "Stress.", "lang_hint": "en"}\n\n{"text": "x"}\n', encoding="utf-8"
    )
    docs = load_documents(p)
    assert docs[0].id == "a"
    assert docs[0].metadata == {"lang_hint": "en"}
    assert docs[1].id == "docs.jsonl#2"
