from __future__ import annotations

import json
import logging
import re
from typing import Sequence

from .llm import LLMClient
from .models import (
    EvaluationScore,
    EvaluatedTestResult,
    ModelConfig,
    PromptEvaluation,
    TestResult,
    WeightsConfig,
)

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator of AI agent responses.
Score the agent's performance on each criterion from 0.0 to 1.0.

Criteria:
- correctness: Did the agent follow the expected behavior? Call the right tools?
- efficiency: Minimal necessary tool calls? No unnecessary steps?
- helpfulness: Is the response clear, accurate, and useful to the user?
- robustness: Did it handle edge cases, errors, or unexpected input properly?

Return ONLY a JSON object:
{
  "correctness": 0.0-1.0,
  "correctness_reason": "...",
  "efficiency": 0.0-1.0,
  "efficiency_reason": "...",
  "helpfulness": 0.0-1.0,
  "helpfulness_reason": "...",
  "robustness": 0.0-1.0,
  "robustness_reason": "..."
}"""


DEFAULT_SCORE = 0.5


def _parse_score_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse judge JSON: %s\nRaw: %s", e, text[:300])
        return {}


class Judge:
    def __init__(self, llm: LLMClient, model_cfg: ModelConfig):
        self._llm = llm
        self._model_cfg = model_cfg

    async def evaluate(
        self, test_result: TestResult, weights: WeightsConfig | None = None
    ) -> EvaluationScore:
        w = weights or WeightsConfig()
        tc = test_result.test_case
        calls_summary = "\n".join(
            f"  → {c.tool_name}({c.input}) = {c.output}" for c in test_result.tool_calls
        ) or "  (none)"

        user_prompt = f"""--- Expected Behavior ---
Tool calls expected: {tc.expected_behavior.tool_calls if tc.expected_behavior else "not specified"}
Constraints: {tc.expected_behavior.constraints if tc.expected_behavior else "none"}

--- Expected Output ---
Text should contain: {tc.expected_output.text_contains if tc.expected_output else "not specified"}
Text should NOT contain: {tc.expected_output.text_not_contains if tc.expected_output else "none"}
Format: {tc.expected_output.format if tc.expected_output else "any"}

--- Actual Behavior ---
Tool calls made:
{calls_summary}

--- Actual Response ---
{test_result.response}"""

        raw = await self._llm.generate(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_cfg=self._model_cfg,
        )

        data = _parse_score_json(raw)

        raw_scores = {
            k: data.get(k, 0.5)
            for k in ("correctness", "efficiency", "helpfulness", "robustness")
        }
        aggregate = (
            raw_scores["correctness"] * w.correctness
            + raw_scores["efficiency"] * w.efficiency
            + raw_scores["helpfulness"] * w.helpfulness
            + raw_scores["robustness"] * w.robustness
        )

        return EvaluationScore(
            correctness=raw_scores["correctness"],
            efficiency=raw_scores["efficiency"],
            helpfulness=raw_scores["helpfulness"],
            robustness=raw_scores["robustness"],
            aggregate=round(aggregate, 4),
        )


class Evaluator:
    def __init__(self, llm: LLMClient, model_cfg: ModelConfig, weights: WeightsConfig):
        self._judge = Judge(llm, model_cfg)
        self._weights = weights

    async def evaluate_prompt(
        self, prompt_id: str, system_prompt: str, results: Sequence[TestResult]
    ) -> PromptEvaluation:
        evaluated: list[EvaluatedTestResult] = []
        for r in results:
            scores = await self._judge.evaluate(r, self._weights)
            evaluated.append(EvaluatedTestResult(test_result=r, scores=scores))

        aggregate = (
            sum(e.scores.aggregate for e in evaluated) / len(evaluated)
            if evaluated
            else 0.0
        )

        return PromptEvaluation(
            prompt_id=prompt_id,
            system_prompt=system_prompt,
            test_results=evaluated,
            aggregate_score=round(aggregate, 4),
        )
