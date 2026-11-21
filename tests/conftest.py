from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ROOT / "domains"


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


requires_en_model = pytest.mark.skipif(
    not has_module("en_core_web_sm"), reason="en_core_web_sm not installed"
)
requires_ginza = pytest.mark.skipif(
    not (has_module("ginza") and has_module("ja_ginza")), reason="[ja] extra not installed"
)


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in an empty folder with no LEANKG_*/GROQ/NEO4J env vars."""
    for key in list(os.environ):
        if key.startswith(("LEANKG_", "GROQ_", "NEO4J_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path
