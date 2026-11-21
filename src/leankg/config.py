"""Configuration: ``leankg.toml`` + ``.env`` + ``LEANKG_*`` environment overrides.

Precedence (highest first): explicit overrides passed in code → environment variables →
``.env`` file (does not override real env vars) → ``leankg.toml`` → built-in defaults.

Model IDs and prices have no meaningful built-in defaults on purpose: they live in
``leankg.toml`` or env, because hosted providers retire models often.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

CONFIG_FILENAME = "leankg.toml"
ENV_PREFIX = "LEANKG_"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMConfig(_Section):
    provider: Literal["none", "groq", "ollama", "fake"] = "none"
    model: str = ""
    escalation_model: str = ""
    escalation_floor: float = 0.5
    price_in_per_mtok: float = 0.0
    price_out_per_mtok: float = 0.0
    budget_calls: int = 500
    budget_tokens: int = 400_000
    batch_size: int = 20
    temperature: float = 0.0
    max_concurrency: int = 2
    max_retries: int = 6
    reasoning_effort: str = "low"  # "" = don't send
    include_reasoning: bool | None = False  # None = don't send
    max_completion_tokens: int = 4096
    cache_path: str = ".leankg/cache.sqlite"
    use_cache: bool = True
    dedupe_threshold: float = 95.0
    verify_model: bool = True
    ollama_host: str = "http://localhost:11434"
    fake_fixture: str = ""
    log_path: str = ".leankg/llm_log.jsonl"
    api_key: SecretStr | None = Field(default=None, exclude=True)


class ChunkingConfig(_Section):
    target_chars: dict[str, int] = Field(
        default_factory=lambda: {"en": 800, "ja": 400, "default": 800}
    )

    def target_for(self, lang: str) -> int:
        return self.target_chars.get(lang, self.target_chars.get("default", 800))


class DetectConfig(_Section):
    cjk_threshold: float = 0.2


class ScoringConfig(_Section):
    accept_threshold: float = 0.6
    hedge_penalty: float = 0.7
    complex_penalty: float = 0.5
    flip_penalty: float = 0.8
    method_prior: dict[str, float] = Field(
        default_factory=lambda: {
            "dict": 0.95,
            "regex": 0.9,
            "ner": 0.75,
            "gliner": 0.7,
            "dep": 0.9,
            "trigger": 0.72,
            "cooc": 0.35,
            "llm": 0.85,
        }
    )

    def prior(self, method: str) -> float:
        return self.method_prior.get(method, 0.5)


class LinkingConfig(_Section):
    fuzzy_threshold: float = 88.0
    fuzzy_margin: float = 2.0
    use_embeddings: bool = True
    embed_threshold: float = 0.85
    embed_margin: float = 0.02
    cache_dir: str = ".leankg/embeddings"


class GlinerConfig(_Section):
    threshold: float = 0.5
    min_entities_before: int = 2
    batch_size: int = 8


class Neo4jConfig(_Section):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    database: str = "neo4j"
    batch_size: int = 1000
    password: SecretStr | None = Field(default=None, exclude=True)


class Config(_Section):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    detect: DetectConfig = Field(default_factory=DetectConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    linking: LinkingConfig = Field(default_factory=LinkingConfig)
    gliner: GlinerConfig = Field(default_factory=GlinerConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    write_unverified: bool = False


def parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal ``.env`` parser: KEY=VALUE lines, ``#`` comments, optional quotes."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


def _coerce(value: str, current: Any) -> Any:
    if isinstance(current, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    return value


def _apply_env(data: dict[str, Any], env: Mapping[str, str], defaults: Config) -> None:
    """Apply ``LEANKG_<SECTION>_<KEY>`` overrides onto raw config data."""
    sections = {name for name, f in Config.model_fields.items() if f.annotation is not bool}
    for key, value in env.items():
        if not key.startswith(ENV_PREFIX) or value == "":
            continue
        rest = key[len(ENV_PREFIX) :].lower()
        for section in sorted(sections, key=len, reverse=True):
            if not rest.startswith(section + "_"):
                continue
            field = rest[len(section) + 1 :]
            section_default = getattr(defaults, section)
            if field not in type(section_default).model_fields:
                break
            current = getattr(section_default, field)
            sec = data.setdefault(section, {})
            if isinstance(current, dict):
                break  # dict-valued settings are toml-only
            sec[field] = _coerce(value, current)
            break
        else:
            if rest == "write_unverified":
                data["write_unverified"] = _coerce(value, False)


def find_config_file(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        candidate = folder / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    dotenv: str | Path | None = ".env",
    overrides: Mapping[str, Any] | None = None,
) -> Config:
    """Load configuration. ``path=None`` searches for ``leankg.toml`` upwards from cwd."""
    data: dict[str, Any] = {}
    cfg_path = Path(path) if path is not None else find_config_file()
    if cfg_path is not None:
        if not cfg_path.is_file():
            raise FileNotFoundError(f"config file not found: {cfg_path}")
        with cfg_path.open("rb") as fh:
            data = tomllib.load(fh)

    merged_env: dict[str, str] = {}
    if dotenv is not None:
        dotenv_path = Path(dotenv)
        if not dotenv_path.is_absolute() and cfg_path is not None and not dotenv_path.exists():
            dotenv_path = cfg_path.parent / dotenv_path
        merged_env.update(parse_dotenv(dotenv_path))
    merged_env.update(os.environ if env is None else env)

    defaults = Config()
    _apply_env(data, merged_env, defaults)
    for dotted, value in (overrides or {}).items():
        target = data
        *parents, leaf = dotted.split(".")
        for part in parents:
            target = target.setdefault(part, {})
        target[leaf] = value

    cfg = Config.model_validate(data)
    if merged_env.get("GROQ_API_KEY"):
        cfg.llm.api_key = SecretStr(merged_env["GROQ_API_KEY"])
    if merged_env.get("NEO4J_PASSWORD"):
        cfg.neo4j.password = SecretStr(merged_env["NEO4J_PASSWORD"])
    if merged_env.get("NEO4J_URI"):
        cfg.neo4j.uri = merged_env["NEO4J_URI"]
    if merged_env.get("NEO4J_USER"):
        cfg.neo4j.user = merged_env["NEO4J_USER"]
    return cfg
