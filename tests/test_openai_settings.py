"""Tests for shared OpenAI configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.config.openai_settings import (
    OpenAIConfigurationError,
    configure_openai_environment,
    load_openai_api_key,
)


def test_load_openai_api_key_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    assert load_openai_api_key() == "env-key"


def test_load_openai_api_key_falls_back_to_secrets_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('[openai]\napi_key = "secret-key"\nmodel = "gpt-5-mini"\n', encoding="utf-8")
    assert load_openai_api_key(secrets_path=secrets) == "secret-key"


def test_configure_openai_environment_raises_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    missing = tmp_path / "missing.toml"
    with pytest.raises(OpenAIConfigurationError):
        configure_openai_environment(secrets_path=missing)
