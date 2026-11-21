"""Load and validate a domain pack from disk, with ``file:line`` error messages."""

from __future__ import annotations

import csv
import json
import os
import re
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from leankg.domain.pack import (
    DepPattern,
    DomainPack,
    EntityPattern,
    ModelsConfig,
    Ontology,
    RelationPatterns,
    Term,
    TriggerRule,
)

DICT_COLUMNS = ("id", "type", "lang", "term", "synonyms", "source")
ENTRY_POINT_GROUP = "leankg.domains"


class PackValidationError(ValueError):
    """A pack file is invalid. ``errors`` holds one ``file:line: message`` per problem."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("invalid domain pack:\n  " + "\n  ".join(errors))


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _pydantic_errors(exc: ValidationError, where: str) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        out.append(f"{where}: {loc}: {err['msg']}" if loc else f"{where}: {err['msg']}")
    return out


def _yaml_line(text: str, key: str) -> int:
    m = re.search(rf"^\s*{re.escape(key)}\s*:", text, flags=re.MULTILINE)
    return text[: m.start()].count("\n") + 1 if m else 1


# ------------------------------------------------------------------ resolution
def bundled_domains_dirs() -> list[Path]:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "domains",
        here.parents[3] / "domains",  # editable install: <repo>/src/leankg/domain/loader.py
        here.parents[1] / "_domains",  # wheel install: leankg/_domains
    ]
    env = os.environ.get("LEANKG_DOMAINS_PATH")
    if env:
        candidates[:0] = [Path(p) for p in env.split(os.pathsep) if p]
    seen: list[Path] = []
    for c in candidates:
        if c.is_dir() and c.resolve() not in seen:
            seen.append(c.resolve())
    return seen


def resolve_pack_path(name_or_path: str | Path) -> Path:
    """Find a pack: explicit path → LEANKG_DOMAINS_PATH → ./domains → repo → bundled → plugins."""
    p = Path(name_or_path)
    if (p / "ontology.yaml").is_file():
        return p.resolve()
    name = str(name_or_path)
    for base in bundled_domains_dirs():
        if (base / name / "ontology.yaml").is_file():
            return (base / name).resolve()
    for ep in metadata.entry_points(group=ENTRY_POINT_GROUP):
        if ep.name != name:
            continue
        target: Any = ep.load()
        path = Path(target() if callable(target) else getattr(target, "__file__", target))
        path = path.parent if path.is_file() else path
        if (path / "ontology.yaml").is_file():
            return path.resolve()
    raise FileNotFoundError(
        f"domain pack {name!r} not found (looked in: "
        + ", ".join(str(b) for b in bundled_domains_dirs())
        + f", entry points '{ENTRY_POINT_GROUP}')"
    )


def available_packs() -> list[str]:
    names: set[str] = set()
    for base in bundled_domains_dirs():
        names.update(d.name for d in base.iterdir() if (d / "ontology.yaml").is_file())
    names.update(ep.name for ep in metadata.entry_points(group=ENTRY_POINT_GROUP))
    return sorted(names)


# --------------------------------------------------------------------- parts
def load_ontology(path: Path, root: Path, errors: list[str]) -> Ontology | None:
    where = _rel(path, root)
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{where}: {exc}")
        return None
    try:
        onto = Ontology.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            key = str(err["loc"][1]) if len(err["loc"]) > 1 else str(err["loc"][0])
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"{where}:{_yaml_line(text, key)}: {loc}: {err['msg']}")
        return None
    for problem in onto.check_references():
        key = problem.split()[1].rstrip(":")
        errors.append(f"{where}:{_yaml_line(text, key)}: {problem}")
    return onto


def load_dictionaries(
    folder: Path, root: Path, onto: Ontology | None, errors: list[str]
) -> list[Term]:
    terms: list[Term] = []
    if not folder.is_dir():
        return terms
    types_by_id: dict[str, tuple[str, str]] = {}
    for path in sorted(folder.glob("*.csv")):
        where = _rel(path, root)
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in DICT_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                errors.append(f"{where}:1: missing columns {missing} (need {list(DICT_COLUMNS)})")
                continue
            for row in reader:
                line = reader.line_num
                if not any((v or "").strip() for v in row.values()):
                    continue
                if (row.get("id") or "").startswith("#"):
                    continue
                values = {k: (row.get(k) or "").strip() for k in DICT_COLUMNS}
                problems = [f"empty '{c}'" for c in ("id", "type", "lang", "term") if not values[c]]
                if onto is not None and values["type"] and values["type"] not in onto.entities:
                    problems.append(f"unknown entity type {values['type']!r}")
                prior = types_by_id.get(values["id"])
                if prior and prior[0] != values["type"] and values["type"]:
                    problems.append(
                        f"id {values['id']!r} already has type {prior[0]!r} ({prior[1]})"
                    )
                if problems:
                    errors.extend(f"{where}:{line}: {p}" for p in problems)
                    continue
                types_by_id.setdefault(values["id"], (values["type"], f"{where}:{line}"))
                synonyms = [s.strip() for s in values["synonyms"].split("|") if s.strip()]
                terms.append(
                    Term(
                        id=values["id"],
                        type=values["type"],
                        lang=values["lang"],
                        term=values["term"],
                        synonyms=synonyms,
                        source=values["source"],
                        file=where,
                        line=line,
                    )
                )
    return terms


def load_entity_patterns(
    path: Path, root: Path, onto: Ontology | None, errors: list[str]
) -> list[EntityPattern]:
    patterns: list[EntityPattern] = []
    if not path.is_file():
        return patterns
    where = _rel(path, root)
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", "//")):
            continue
        try:
            pat = EntityPattern.model_validate(json.loads(line))
            _ = pat.regex
        except json.JSONDecodeError as exc:
            errors.append(f"{where}:{line_no}: invalid JSON: {exc.msg}")
            continue
        except ValidationError as exc:
            errors.extend(_pydantic_errors(exc, f"{where}:{line_no}"))
            continue
        except (re.error, KeyError) as exc:
            errors.append(f"{where}:{line_no}: invalid regex/flags: {exc}")
            continue
        if onto is not None and pat.type not in onto.entities:
            errors.append(f"{where}:{line_no}: unknown entity type {pat.type!r}")
            continue
        patterns.append(pat)
    return patterns


def load_relation_patterns(
    folder: Path, root: Path, onto: Ontology | None, errors: list[str]
) -> dict[str, RelationPatterns]:
    out: dict[str, RelationPatterns] = {}
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("relations.*.yaml")):
        lang = path.name.split(".")[1]
        where = _rel(path, root)
        try:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text) or {}
            rp = RelationPatterns.model_validate({"lang": lang, **data})
        except yaml.YAMLError as exc:
            errors.append(f"{where}: {exc}")
            continue
        except ValidationError as exc:
            errors.extend(_pydantic_errors(exc, where))
            continue
        if onto is not None:
            items: list[DepPattern | TriggerRule] = [*rp.dependency, *rp.triggers]
            for item in items:
                for choice in item.relations:
                    if choice.type not in onto.relations:
                        errors.append(
                            f"{where}:{_yaml_line(text, 'id')}: pattern {item.id}: "
                            f"unknown relation {choice.type!r}"
                        )
        out[lang] = rp
    return out


def load_models(path: Path, root: Path, errors: list[str]) -> ModelsConfig:
    if not path.is_file():
        return ModelsConfig()
    try:
        return ModelsConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    except (yaml.YAMLError, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            errors.extend(_pydantic_errors(exc, _rel(path, root)))
        else:
            errors.append(f"{_rel(path, root)}: {exc}")
        return ModelsConfig()


def load_hints(root: Path) -> dict[str, str]:
    hints: dict[str, str] = {}
    for path in sorted(root.glob("llm_hints*.md")):
        parts = path.name.split(".")
        lang = parts[1] if len(parts) == 3 else "en"
        hints[lang] = path.read_text(encoding="utf-8")
    return hints


# ---------------------------------------------------------------------- pack
def load_pack(name_or_path: str | Path) -> DomainPack:
    """Load and validate a pack. Raises :class:`PackValidationError` listing every problem."""
    root = resolve_pack_path(name_or_path)
    errors: list[str] = []
    onto = load_ontology(root / "ontology.yaml", root, errors)
    terms = load_dictionaries(root / "dictionaries", root, onto, errors)
    patterns = load_entity_patterns(root / "patterns" / "entities.jsonl", root, onto, errors)
    relations = load_relation_patterns(root / "patterns", root, onto, errors)
    models = load_models(root / "models.yaml", root, errors)
    if errors or onto is None:
        raise PackValidationError(errors or ["ontology.yaml: could not be loaded"])
    return DomainPack(
        name=onto.name or root.name,
        root=root,
        ontology=onto,
        terms=terms,
        entity_patterns=patterns,
        relation_patterns=relations,
        models=models,
        llm_hints=load_hints(root),
    )
