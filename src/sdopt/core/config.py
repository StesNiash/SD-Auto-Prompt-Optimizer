from __future__ import annotations

from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import RunConfig


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
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    if settings.google_api_key:
        os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
    if settings.openrouter_api_key:
        os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)


def load_config(path: str | Path) -> RunConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RunConfig(**raw)
