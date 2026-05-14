from __future__ import annotations

import os

import litellm

from .config import Settings
from .models import ModelConfig


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_cfg: ModelConfig,
    ) -> str:
        response = await litellm.acompletion(
            model=f"{model_cfg.provider}/{model_cfg.model}",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=model_cfg.temperature,
            max_tokens=model_cfg.max_tokens or 4096,
        )
        return response.choices[0].message.content
