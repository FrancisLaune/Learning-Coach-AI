"""Shared OpenAI configuration for scripts and assessors."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"


class OpenAIConfigurationError(RuntimeError):
    """Raised when OpenAI credentials or model configuration is unavailable."""


def _read_secrets(path: Path = DEFAULT_SECRETS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _secret_api_key(*, secrets_path: Path | None = None) -> str | None:
    data = _read_secrets(secrets_path or DEFAULT_SECRETS_PATH)
    section = data.get("openai", {})
    key = section.get("api_key") or data.get("OPENAI_API_KEY")
    return str(key).strip() if key else None


def load_openai_api_key(*, secrets_path: Path | None = None) -> str | None:
    """Resolve API key: OPENAI_API_KEY env, then `.streamlit/secrets.toml`."""
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key
    return _secret_api_key(secrets_path=secrets_path)


def load_openai_model(*, secrets_path: Path | None = None) -> str | None:
    env_model = os.getenv("OPENAI_REVIEW_MODEL") or os.getenv("OPENAI_CONTENT_MODEL")
    if env_model:
        return str(env_model).strip()
    data = _read_secrets(secrets_path or DEFAULT_SECRETS_PATH)
    section = data.get("openai", {})
    model = section.get("review_model") or section.get("model") or data.get("OPENAI_CONTENT_MODEL")
    return str(model).strip() if model else None


def configure_openai_environment(*, secrets_path: Path | None = None) -> dict[str, str]:
    """Ensure process env contains a resolved OpenAI key and return metadata."""
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    secret_key = _secret_api_key(secrets_path=secrets_path)
    if env_key:
        key = env_key
        source = "environment"
    elif secret_key:
        key = secret_key
        source = "streamlit_secrets"
    else:
        raise OpenAIConfigurationError(
            "OpenAI API key not found. Set OPENAI_API_KEY or configure `.streamlit/secrets.toml`."
        )
    os.environ["OPENAI_API_KEY"] = key
    model = load_openai_model(secrets_path=secrets_path) or "gpt-5.6"
    return {
        "api_key_source": source,
        "model": model,
        "env_key_present": bool(env_key),
        "secret_key_present": bool(secret_key),
    }


def is_permanent_openai_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    permanent_markers = (
        "401",
        "403",
        "invalid_api_key",
        "incorrect api key",
        "authentication",
        "permission",
        "api key not found",
    )
    return any(marker in message for marker in permanent_markers)


def _minimal_openai_call(model: str) -> None:
    from openai import OpenAI

    OpenAI().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with OK."}],
        max_completion_tokens=3,
    )


def verify_openai_pedagogical_assessor(*, secrets_path: Path | None = None) -> dict[str, str]:
    """Perform one minimal authenticated OpenAI call."""
    config = configure_openai_environment(secrets_path=secrets_path)
    try:
        _minimal_openai_call(config["model"])
        return {"status": "AVAILABLE", "model": config["model"], "api_key_source": config["api_key_source"]}
    except Exception as exc:
        if not is_permanent_openai_error(exc):
            raise
        env_key = os.getenv("OPENAI_API_KEY", "").strip()
        secret_key = _secret_api_key(secrets_path=secrets_path)
        if config["api_key_source"] == "environment" and secret_key and secret_key != env_key:
            os.environ["OPENAI_API_KEY"] = secret_key
            _minimal_openai_call(config["model"])
            return {
                "status": "AVAILABLE",
                "model": config["model"],
                "api_key_source": "streamlit_secrets_fallback",
                "note": "Environment OPENAI_API_KEY was invalid; Streamlit secret used instead.",
            }
        raise OpenAIConfigurationError(
            "OpenAI authentication failed. Verify OPENAI_API_KEY or `.streamlit/secrets.toml`."
        ) from exc