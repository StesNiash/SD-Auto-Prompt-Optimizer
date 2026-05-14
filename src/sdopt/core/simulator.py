from __future__ import annotations

import json
import logging
from typing import Sequence

import litellm

from .llm import LLMClient
from .models import (
    FakeTool,
    ModelConfig,
    TestCase,
    TestResult,
    Tool,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)


def _tool_to_openai_func(tool: Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": {
                    tool.name: {
                        "type": "object",
                        "description": f"Input parameters for {tool.name}",
                        "additionalProperties": True,
                    }
                },
                "required": [tool.name],
            },
        },
    }


class FakeToolExecutor:
    def __init__(
        self,
        fake_tools: Sequence[FakeTool],
        tool_scenarios: dict[str, str] | None = None,
    ):
        self._by_name = {ft.tool_name: ft for ft in fake_tools}
        self._scenarios = tool_scenarios or {}

    def execute(self, tool_name: str, tool_input: str) -> ToolCallRecord:
        ft = self._by_name.get(tool_name)
        if not ft:
            logger.warning("Fake tool '%s' not found, returning error", tool_name)
            return ToolCallRecord(
                tool_name=tool_name,
                input=tool_input,
                output=json.dumps({"error": f"unknown_tool: {tool_name}"}),
            )

        scenario = self._scenarios.get(tool_name)
        if scenario:
            match = next(
                (r for r in ft.responses if r.scenario_match == scenario), None
            )
            if match:
                return ToolCallRecord(
                    tool_name=tool_name, input=tool_input, output=match.output
                )

        default = ft.responses[0] if ft.responses else None
        if default:
            return ToolCallRecord(
                tool_name=tool_name, input=tool_input, output=default.output
            )

        return ToolCallRecord(
            tool_name=tool_name,
            input=tool_input,
            output=json.dumps({"error": "no_response_defined"}),
        )


class AgentSimulator:
    def __init__(
        self,
        llm: LLMClient,
        model_cfg: ModelConfig,
        tools: Sequence[Tool],
        fake_tools: Sequence[FakeTool],
    ):
        self._llm = llm
        self._model_cfg = model_cfg
        self._tools = list(tools)
        self._fake_tools = list(fake_tools)

    async def simulate(self, system_prompt: str, test_case: TestCase) -> TestResult:
        executor = FakeToolExecutor(self._fake_tools, test_case.tool_scenarios)

        openai_tools = [_tool_to_openai_func(t) for t in self._tools]

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": test_case.input},
        ]

        calls: list[ToolCallRecord] = []

        for _ in range(10):
            response = await litellm.acompletion(
                model=f"{self._model_cfg.provider}/{self._model_cfg.model}",
                messages=messages,
                tools=openai_tools or None,
                temperature=self._model_cfg.temperature,
                max_tokens=self._model_cfg.max_tokens or 4096,
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = tc.function.arguments
                    rec = executor.execute(fn_name, fn_args)
                    calls.append(rec)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": rec.output,
                    })
                if msg.content:
                    messages.append({"role": "assistant", "content": msg.content})
                continue

            final = msg.content or ""
            return TestResult(
                prompt_id="",
                test_case=test_case,
                response=final,
                tool_calls=calls,
            )

        logger.warning("Simulator reached max iterations, returning last response")
        return TestResult(
            prompt_id="",
            test_case=test_case,
            response="",
            tool_calls=calls,
        )
