from __future__ import annotations

import logging

import litellm
from pydantic import BaseModel

from .config import Settings, apply_settings
from .models import ModelConfig

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        apply_settings(self.settings)

    async def complete(
        self,
        messages: list[dict],
        model_cfg: ModelConfig,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        model = f"{model_cfg.provider}/{model_cfg.model}"

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                tools=tools or None,
                temperature=model_cfg.temperature,
                max_tokens=model_cfg.max_tokens or 4096,
            )
        except Exception:
            logger.exception("LLM call failed: %s", model)
            return LLMResponse(content="")

        msg = response.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
                for tc in msg.tool_calls
            ]

        return LLMResponse(content=msg.content or "", tool_calls=tool_calls)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_cfg: ModelConfig,
    ) -> str:
        resp = await self.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model_cfg=model_cfg,
        )
        return resp.content or ""
