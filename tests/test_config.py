from pathlib import Path

import pytest

from leankg.config import load_config, parse_dotenv


def test_defaults_without_files(isolated_env: Path) -> None:
    cfg = load_config()
    assert cfg.llm.provider == "none"
    assert cfg.llm.model == ""  # no model ID hardcoded in code
    assert cfg.llm.api_key is None


def test_toml_then_env_override(isolated_env: Path) -> None:
    (isolated_env / "leankg.toml").write_text(
        '[llm]\nprovider = "groq"\nmodel = "m-from-toml"\nbudget_calls = 10\n', encoding="utf-8"
    )
    cfg = load_config(env={"LEANKG_LLM_MODEL": "m-from-env", "LEANKG_LLM_BUDGET_CALLS": "7"})
    assert cfg.llm.provider == "groq"
    assert cfg.llm.model == "m-from-env"
    assert cfg.llm.budget_calls == 7


def test_dotenv_secrets_and_precedence(isolated_env: Path) -> None:
    (isolated_env / ".env").write_text(
        "# comment\nGROQ_API_KEY='gsk_test'\nLEANKG_LLM_MODEL=from-dotenv\nNEO4J_PASSWORD=pw\n",
        encoding="utf-8",
    )
    cfg = load_config(env={"LEANKG_LLM_MODEL": "from-env"})
    assert cfg.llm.api_key is not None
    assert cfg.llm.api_key.get_secret_value() == "gsk_test"
    assert cfg.llm.model == "from-env"  # real env beats .env
    assert cfg.neo4j.password is not None
    assert "gsk_test" not in cfg.model_dump_json()  # secrets never dumped


def test_bool_and_float_coercion(isolated_env: Path) -> None:
    cfg = load_config(
        env={"LEANKG_LLM_USE_CACHE": "false", "LEANKG_SCORING_ACCEPT_THRESHOLD": "0.7"}
    )
    assert cfg.llm.use_cache is False
    assert cfg.scoring.accept_threshold == 0.7


def test_overrides_argument(isolated_env: Path) -> None:
    cfg = load_config(env={}, overrides={"llm.provider": "fake", "linking.use_embeddings": False})
    assert cfg.llm.provider == "fake"
    assert cfg.linking.use_embeddings is False


def test_unknown_toml_key_is_an_error(isolated_env: Path) -> None:
    (isolated_env / "leankg.toml").write_text("[llm]\nmodle = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="modle"):
        load_config(env={})


def test_parse_dotenv_inline_comment(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text("A=1 # note\nexport B=two\n", encoding="utf-8")
    assert parse_dotenv(p) == {"A": "1", "B": "two"}


def test_repo_config_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "leankg.toml", env={}, dotenv=None)
    assert cfg.llm.model  # model ID lives in config, not code
    assert cfg.chunking.target_for("ja") == 400
    assert cfg.chunking.target_for("xx") == 800
