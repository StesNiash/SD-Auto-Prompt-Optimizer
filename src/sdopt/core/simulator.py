from __future__ import annotations

import json
import logging
from typing import Sequence

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
                    "input": {
                        "type": "string",
                        "description": f"Input data for {tool.name} as JSON string",
                    }
                },
                "required": ["input"],
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
        openai_tools = [_tool_to_openai_func(t) for t in self._tools] or None

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": test_case.input},
        ]

        calls: list[ToolCallRecord] = []
        seen_calls: set[tuple[str, str]] = set()

        for _ in range(5):
            resp = await self._llm.complete(
                messages=messages,
                model_cfg=self._model_cfg,
                tools=openai_tools,
            )

            if resp.tool_calls:
                for tc in resp.tool_calls:
                    key = (tc.name, tc.arguments)
                    if key in seen_calls:
                        logger.warning("Duplicate tool call detected: %s", tc.name)
                        return TestResult(
                            prompt_id="",
                            test_case=test_case,
                            response=resp.content or "",
                            tool_calls=calls,
                        )
                    seen_calls.add(key)

                assistant_msg = {"role": "assistant", "content": resp.content}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in resp.tool_calls
                ]
                messages.append(assistant_msg)
                for tc in resp.tool_calls:
                    rec = executor.execute(tc.name, tc.arguments)
                    calls.append(rec)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": rec.output,
                    })
                continue

            return TestResult(
                prompt_id="",
                test_case=test_case,
                response=resp.content or "",
                tool_calls=calls,
            )

        logger.warning("Simulator reached max iterations (5)")
        return TestResult(
            prompt_id="",
            test_case=test_case,
            response="",
            tool_calls=calls,
        )
