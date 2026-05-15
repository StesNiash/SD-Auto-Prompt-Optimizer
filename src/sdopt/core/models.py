from __future__ import annotations

import uuid
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ToolExample(BaseModel):
    input: str
    output: str


class Tool(BaseModel):
    name: str
    description: str
    examples: list[ToolExample]


class FakeToolResponse(BaseModel):
    scenario_match: str
    output: str


class FakeTool(BaseModel):
    tool_name: str
    responses: list[FakeToolResponse]


class FakeToolResponseRef(BaseModel):
    tool_name: str
    scenario_match: str


class ExpectedBehavior(BaseModel):
    tool_calls: list[str] | None = None
    constraints: list[str] | None = None


class ExpectedOutput(BaseModel):
    text_contains: list[str] | None = None
    text_not_contains: list[str] | None = None
    format: Literal["text", "json", "markdown"] | None = None


class TestCase(BaseModel):
    input: str
    expected_behavior: ExpectedBehavior | None = None
    expected_output: ExpectedOutput | None = None
    tool_scenarios: dict[str, str] | None = None
    tags: list[str] = Field(default_factory=list)


class PromptVariant(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    system_prompt: str
    parent_id: str | None = None
    generation: int = 0
    strategy: str | None = None


class ToolCallRecord(BaseModel):
    tool_name: str
    input: str
    output: str


class TestResult(BaseModel):
    prompt_id: str
    test_case: TestCase
    response: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class EvaluationScore(BaseModel):
    correctness: float = Field(ge=0.0, le=1.0)
    efficiency: float = Field(ge=0.0, le=1.0)
    helpfulness: float = Field(ge=0.0, le=1.0)
    robustness: float = Field(ge=0.0, le=1.0)
    aggregate: float = Field(ge=0.0, le=1.0)


class EvaluatedTestResult(BaseModel):
    test_result: TestResult
    scores: EvaluationScore


class PromptEvaluation(BaseModel):
    prompt_id: str
    system_prompt: str
    test_results: list[EvaluatedTestResult]
    aggregate_score: float = Field(ge=0.0, le=1.0)


class GenerationRecord(BaseModel):
    generation: int
    prompts: list[PromptEvaluation]
    best_score: float = Field(ge=0.0, le=1.0)
    best_prompt_id: str


class EvolutionStrategy(str, Enum):
    crossover = "crossover"
    targeted = "targeted"
    baseline = "baseline"
    all_strategies = "all"


class EvolutionConfig(BaseModel):
    strategy: EvolutionStrategy = EvolutionStrategy.all_strategies
    population_size: int = Field(default=8, ge=2, le=100)
    selection_top_k: int = Field(default=3, ge=1, le=100)
    max_generations: int = Field(default=10, ge=1, le=1000)
    convergence_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    patience: int = Field(default=3, ge=1, le=100)


class WeightsConfig(BaseModel):
    correctness: float = Field(default=0.4, ge=0.0, le=1.0)
    efficiency: float = Field(default=0.2, ge=0.0, le=1.0)
    helpfulness: float = Field(default=0.2, ge=0.0, le=1.0)
    robustness: float = Field(default=0.2, ge=0.0, le=1.0)


class ModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int | None = None
    api_base: str | None = None


class RunConfig(BaseModel):
    scenario: str
    basic_prompt: str
    tools: list[Tool] = Field(default_factory=list)
    fake_tools: list[FakeTool] = Field(default_factory=list)
    test_cases: list[TestCase]
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    models: dict[str, ModelConfig]
