from __future__ import annotations

from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import RunConfig


UNPREFIXED_KEYS = {
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "google_api_key": "GEMINI_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SDOPT_",
        extra="ignore",
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""


def apply_settings(settings: Settings) -> None:
    import os
    for field, env_name in UNPREFIXED_KEYS.items():
        val = getattr(settings, field, "") or os.environ.get(env_name, "")
        if val:
            os.environ[env_name] = val


def load_config(path: str | Path) -> RunConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RunConfig(**raw)
