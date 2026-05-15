from __future__ import annotations

import json
import logging
import re
from typing import Sequence

from .llm import LLMClient
from .models import (
    FakeTool,
    ModelConfig,
    TestCase,
    Tool,
)

FAKETOOL_SYSTEM_PROMPT = """You are a test data generator for AI agent testing.
Given tool descriptions and examples, generate deterministic mock responses covering ALL possible outcomes.

For each tool, generate FakeToolResponse entries for:
1. Success case (based on the success example)
2. Each error case from the examples
3. Edge cases that make sense for this tool (timeout, partial success, validation errors, etc.)

Each response must have:
- scenario_match: short description of when this response is used
- output: the exact JSON string the tool returns"""

TESTCASE_SYSTEM_PROMPT = """You are a test case designer for AI agent evaluation.
Given a scenario description and a list of available tools, generate diverse test cases.

Return a JSON array. Each item must follow this exact schema:
{
  "input": "user message to the agent",
  "expected_behavior": {
    "tool_calls": ["tool_name1", "tool_name2"],
    "constraints": ["must not ask for confirmation twice"]
  },
  "expected_output": {
    "text_contains": ["expected substring"],
    "text_not_contains": ["forbidden substring"],
    "format": "text | json | markdown"
  },
  "tags": ["happy_path"]
}

RULES:
- Omit fields entirely (not null, not empty object) when not applicable
- expected_behavior.tool_calls: list of tool names or omit
- expected_behavior.constraints: list of strings or omit
- expected_output.text_contains / text_not_contains: list of strings or omit
- expected_output.format: one of text/json/markdown or omit
- tags: one or more of happy_path, error_case, edge_case, ambiguous, multi_tool

Cover: happy paths, error scenarios, edge cases, ambiguous requests. Make inputs realistic."""


logger = logging.getLogger(__name__)


def _drop_empty(obj, fields):
    for f in fields:
        val = obj.get(f)
        if val == {} or val == [] or val is None:
            obj.pop(f, None)
    return obj


def _coerce_test_case(item: dict) -> dict:
    _drop_empty(item, ("expected_behavior", "expected_output"))
    for key in ("expected_behavior", "expected_output"):
        sub = item.get(key)
        if isinstance(sub, dict):
            sub.pop("constraints", None) if sub.get("constraints") == {} else None
            sub.pop("tool_calls", None) if sub.get("tool_calls") == [] else None
            sub.pop("text_contains", None) if sub.get("text_contains") == [] else None
            sub.pop("text_not_contains", None) if sub.get("text_not_contains") == [] else None
    return item


def _parse_json_list(text: str):
    text = text.strip()
    code_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if code_match:
        text = code_match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON list: %s\nRaw: %s", e, text[:300])
        return []


class FakeToolsGenerator:
    def __init__(self, llm: LLMClient, model_cfg: ModelConfig):
        self._llm = llm
        self._model_cfg = model_cfg

    async def generate(self, tools: Sequence[Tool], scenario: str) -> list[FakeTool]:
        if not tools:
            return []

        tools_block = "\n\n".join(
            _format_tool(t) for t in tools
        )
        user_prompt = f"""Scenario: {scenario}

Tools to generate fake responses for:
{tools_block}

Return a JSON array of FakeTool objects (tool_name + responses list)."""

        raw = await self._llm.generate(
            system_prompt=FAKETOOL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_cfg=self._model_cfg,
        )

        data = _parse_json_list(raw)
        result: list[FakeTool] = []
        for item in data:
            try:
                result.append(FakeTool(**item))
            except Exception as e:
                logger.warning("Skipping bad fake tool: %s\nData: %s", e, str(item)[:200])
        return result


class TestCasesGenerator:
    def __init__(self, llm: LLMClient, model_cfg: ModelConfig):
        self._llm = llm
        self._model_cfg = model_cfg

    async def generate(
        self,
        scenario: str,
        tools: Sequence[Tool],
        existing_cases: list[TestCase],
        target_count: int,
    ) -> list[TestCase]:
        tools_block = "\n".join(
            f"- {t.name}: {t.description}" for t in tools
        ) if tools else "No tools available"

        existing_block = "\n".join(
            f"- input: {c.input[:120]}" for c in existing_cases
        ) if existing_cases else "None"

        user_prompt = f"""Scenario: {scenario}

Available tools:
{tools_block}

Existing test cases ({len(existing_cases)}):
{existing_block}

Generate {target_count} new test cases that are DIFFERENT from existing ones.
Return a JSON array of test cases."""

        raw = await self._llm.generate(
            system_prompt=TESTCASE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_cfg=self._model_cfg,
        )

        data = _parse_json_list(raw)
        result: list[TestCase] = []
        for item in data:
            try:
                result.append(TestCase(**_coerce_test_case(item)))
            except Exception as e:
                logger.warning("Skipping bad test case: %s\nData: %s", e, str(item)[:200])
        return result


def _format_tool(t: Tool) -> str:
    examples = "\n".join(
        f"  Input: {e.input}\n  Output: {e.output}" for e in t.examples
    )
    return f"Tool: {t.name}\nDescription: {t.description}\nExamples:\n{examples}"
