"""Document loaders: TXT/MD, HTML, PDF, CSV and JSONL → :class:`Document`."""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from leankg.models import Document

log = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md", ".text"}
HTML_SUFFIXES = {".html", ".htm"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | HTML_SUFFIXES | {".pdf", ".csv", ".jsonl"}
_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "euc-jp", "latin-1")


@dataclass
class LoaderOptions:
    csv_text_column: str = "text"
    csv_id_column: str | None = None
    csv_title_column: str | None = None
    recursive: bool = True


def read_text_file(path: Path) -> str:
    """Read text trying UTF-8 first, then common Japanese encodings."""
    raw = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")  # pragma: no cover - latin-1 always decodes


def _doc_id(path: Path, root: Path, suffix: str = "") -> str:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.name
    return rel + suffix


def load_text(path: Path, root: Path) -> list[Document]:
    text = read_text_file(path)
    title = next((ln.strip("# ").strip() for ln in text.splitlines() if ln.strip()), path.stem)
    return [Document(id=_doc_id(path, root), source=str(path), title=title[:200], text=text)]


_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def html_to_text(html: str) -> tuple[str, dict[str, Any]]:
    """Main text + metadata via trafilatura; crude tag stripping as fallback."""
    meta: dict[str, Any] = {}
    text: str | None = None
    try:
        import trafilatura

        text = trafilatura.extract(html, include_comments=False, include_tables=True)
        md = trafilatura.extract_metadata(html)
        if md is not None:
            meta = {k: getattr(md, k, None) for k in ("title", "date", "url", "sitename")}
    except Exception as exc:  # pragma: no cover - trafilatura is a core dep
        log.debug("trafilatura failed: %s", exc)
    if not text:
        text = _TAG.sub(" ", _SCRIPT.sub(" ", html))
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m and not meta.get("title"):
            meta["title"] = m.group(1).strip()
    return text, {k: v for k, v in meta.items() if v}


def load_html(path: Path, root: Path) -> list[Document]:
    text, meta = html_to_text(read_text_file(path))
    return [
        Document(
            id=_doc_id(path, root),
            source=str(path),
            title=str(meta.get("title") or path.stem),
            url=meta.get("url"),
            date=str(meta["date"]) if meta.get("date") else None,
            text=text,
            metadata={k: v for k, v in meta.items() if k not in {"title", "url", "date"}},
        )
    ]


def load_pdf(path: Path, root: Path) -> list[Document]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    info = reader.metadata
    title = str(info.title) if info is not None and info.title else path.stem
    return [
        Document(
            id=_doc_id(path, root),
            source=str(path),
            title=title,
            text="\n\n".join(pages),
            metadata={"pages": len(pages)},
        )
    ]


def load_csv(path: Path, root: Path, opts: LoaderOptions) -> list[Document]:
    docs: list[Document] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if opts.csv_text_column not in (reader.fieldnames or []):
            raise ValueError(
                f"{path}: text column {opts.csv_text_column!r} not found "
                f"(columns: {reader.fieldnames}); use --csv-text-column"
            )
        for i, row in enumerate(reader):
            text = (row.get(opts.csv_text_column) or "").strip()
            if not text:
                continue
            rid = row.get(opts.csv_id_column) if opts.csv_id_column else None
            meta = {k: v for k, v in row.items() if k != opts.csv_text_column and v}
            docs.append(
                Document(
                    id=_doc_id(path, root, f"#{rid or i}"),
                    source=str(path),
                    title=str(row.get(opts.csv_title_column or "", "") or f"{path.stem} #{i}"),
                    text=text,
                    metadata=meta,
                )
            )
    return docs


def load_jsonl(path: Path, root: Path) -> list[Document]:
    docs: list[Document] = []
    for i, line in enumerate(read_text_file(path).splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        text = str(row.get("text", ""))
        if not text.strip():
            continue
        docs.append(
            Document(
                id=str(row.get("id") or _doc_id(path, root, f"#{i}")),
                source=str(path),
                title=str(row.get("title", "")),
                url=row.get("url"),
                date=row.get("date"),
                text=text,
                metadata={
                    k: v for k, v in row.items() if k not in {"id", "text", "title", "url", "date"}
                },
            )
        )
    return docs


def load_file(
    path: Path, root: Path | None = None, opts: LoaderOptions | None = None
) -> list[Document]:
    opts = opts or LoaderOptions()
    root = root or path.parent
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return load_text(path, root)
    if suffix in HTML_SUFFIXES:
        return load_html(path, root)
    if suffix == ".pdf":
        return load_pdf(path, root)
    if suffix == ".csv":
        return load_csv(path, root, opts)
    if suffix == ".jsonl":
        return load_jsonl(path, root)
    raise ValueError(f"unsupported file type: {path}")


def iter_files(path: Path, recursive: bool = True) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    pattern = "**/*" if recursive else "*"
    for p in sorted(path.glob(pattern)):
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES and not p.name.startswith("."):
            yield p


def load_documents(path: str | Path, opts: LoaderOptions | None = None) -> list[Document]:
    """Load every supported file under ``path`` (a file or folder)."""
    opts = opts or LoaderOptions()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    root = p if p.is_dir() else p.parent
    docs: list[Document] = []
    for f in iter_files(p, opts.recursive):
        try:
            docs.extend(load_file(f, root, opts))
        except ValueError:
            raise  # bad CSV column / malformed JSONL: fail loudly
        except Exception as exc:
            log.warning("skipping %s: %s", f, exc)
    return docs
