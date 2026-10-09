"""Tests for environment configuration helpers (nazbeen_forex_ai.config)."""

from __future__ import annotations

import pytest

from nazbeen_forex_ai.config import env_bool, env_int, env_list, env_str, load_dotenv


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    """Ensure variables under test never leak between tests."""
    for key in ("TEST_STR", "TEST_BOOL", "TEST_INT", "TEST_LIST"):
        monkeypatch.delenv(key, raising=False)


def test_env_str_returns_default_when_unset() -> None:
    assert env_str("TEST_STR", "fallback") == "fallback"


def test_env_str_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_STR", "value")
    assert env_str("TEST_STR", "fallback") == "value"


def test_env_bool_parses_true_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("TEST_BOOL", raw)
        assert env_bool("TEST_BOOL") is True


def test_env_bool_parses_false_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("0", "false", "no", "off"):
        monkeypatch.setenv("TEST_BOOL", raw)
        assert env_bool("TEST_BOOL") is False


def test_env_bool_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert env_bool("TEST_BOOL", default=True) is True


def test_env_bool_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_BOOL", "maybe")
    with pytest.raises(ValueError):
        env_bool("TEST_BOOL")


def test_env_int_parses_and_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_INT", "42")
    assert env_int("TEST_INT", 7) == 42
    monkeypatch.setenv("TEST_INT", "not-a-number")
    with pytest.raises(ValueError):
        env_int("TEST_INT", 7)


def test_env_list_splits_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_LIST", " a.example , b.example ,,c.example ")
    assert env_list("TEST_LIST") == ["a.example", "b.example", "c.example"]


def test_env_list_default_when_unset() -> None:
    assert env_list("TEST_LIST", "x, y") == ["x", "y"]


def test_load_dotenv_does_not_override_existing_env(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_STR", "from-environment")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "TEST_STR=from-file\n"
        "TEST_LIST=one,two\n"
        'QUOTED="quoted value"\n'
        "export EXPORTED=yes\n"
        "MALFORMED_LINE\n",
        encoding="utf-8",
    )

    load_dotenv(env_file)

    import os

    assert os.environ["TEST_STR"] == "from-environment"  # not overridden
    assert os.environ["TEST_LIST"] == "one,two"
    assert os.environ["QUOTED"] == "quoted value"
    assert os.environ["EXPORTED"] == "yes"
    assert "MALFORMED_LINE" not in os.environ

    # Cleanup values set from the file so other tests are unaffected.
    for key in ("TEST_LIST", "QUOTED", "EXPORTED"):
        monkeypatch.delenv(key, raising=False)
