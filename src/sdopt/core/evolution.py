from __future__ import annotations

import logging
import random
from typing import Sequence

from .evaluation import Evaluator
from .llm import LLMClient
from .models import (
    EvolutionConfig,
    EvolutionStrategy,
    GenerationRecord,
    ModelConfig,
    PromptEvaluation,
    PromptVariant,
    RunConfig,
    TestCase,
)
from .simulator import AgentSimulator

logger = logging.getLogger(__name__)

INIT_PROMPT = """You are a prompt engineer. Generate a variation of the given system prompt.
Keep the core instruction but rephrase, restructure, or add detail to improve clarity and effectiveness.
Return ONLY the new prompt text, no explanations."""

CROSSOVER_PROMPT = """You are a prompt engineer. Merge the following two system prompts into ONE improved prompt.
Combine the strengths of both. The result should be better than either parent.
Return ONLY the new prompt text."""

TARGETED_PROMPT = """You are a prompt engineer. The following system prompt failed on specific test scenarios.
Generate an improved version that handles these cases correctly while keeping what works.
Return ONLY the new prompt text."""

BASELINE_PROMPT = """You are a prompt engineer. Rephrase the following system prompt.
Keep the same meaning and instructions but use different wording.
Return ONLY the new prompt text."""


class PromptGenerator:
    def __init__(self, llm: LLMClient, model_cfg: ModelConfig, scenario: str):
        self._llm = llm
        self._model_cfg = model_cfg
        self._scenario = scenario

    async def initialize(self, basic_prompt: str, count: int) -> list[PromptVariant]:
        variants: list[PromptVariant] = [
            PromptVariant(
                system_prompt=basic_prompt,
                generation=0,
                strategy="baseline",
            )
        ]
        for i in range(count - 1):
            raw = await self._llm.generate(
                system_prompt=INIT_PROMPT,
                user_prompt=f"Original prompt:\n{basic_prompt}",
                model_cfg=self._model_cfg,
            )
            variants.append(
                PromptVariant(
                    system_prompt=raw.strip(),
                    parent_id=variants[0].id,
                    generation=0,
                    strategy="init",
                )
            )
        return variants

    async def crossover(
        self, parent_a: PromptVariant, parent_b: PromptVariant, generation: int
    ) -> PromptVariant:
        raw = await self._llm.generate(
            system_prompt=CROSSOVER_PROMPT,
            user_prompt=f"--- Prompt A ---\n{parent_a.system_prompt}\n\n--- Prompt B ---\n{parent_b.system_prompt}",
            model_cfg=self._model_cfg,
        )
        return PromptVariant(
            system_prompt=raw.strip(),
            parent_id=f"{parent_a.id}+{parent_b.id}",
            generation=generation,
            strategy="crossover",
        )

    async def targeted_mutate(
        self,
        prompt: PromptVariant,
        failures: Sequence[str],
        generation: int,
    ) -> PromptVariant:
        failures_block = "\n".join(f"- {f}" for f in failures)
        raw = await self._llm.generate(
            system_prompt=TARGETED_PROMPT,
            user_prompt=f"--- Prompt ---\n{prompt.system_prompt}\n\n--- Failing scenarios ---\n{failures_block}",
            model_cfg=self._model_cfg,
        )
        return PromptVariant(
            system_prompt=raw.strip(),
            parent_id=prompt.id,
            generation=generation,
            strategy="targeted",
        )

    async def baseline_mutate(
        self, basic_prompt: str, generation: int
    ) -> PromptVariant:
        raw = await self._llm.generate(
            system_prompt=BASELINE_PROMPT,
            user_prompt=basic_prompt,
            model_cfg=self._model_cfg,
        )
        return PromptVariant(
            system_prompt=raw.strip(),
            generation=generation,
            strategy="baseline",
        )


class ConvergenceDetector:
    def __init__(self, cfg: EvolutionConfig):
        self._cfg = cfg
        self._best_scores: list[float] = []

    def check(self, best_score: float) -> bool:
        self._best_scores.append(best_score)
        if best_score >= self._cfg.convergence_threshold:
            logger.info(
                "Converged: score %.4f >= threshold %.2f",
                best_score,
                self._cfg.convergence_threshold,
            )
            return True
        if len(self._best_scores) > self._cfg.patience:
            recent = self._best_scores[-self._cfg.patience :]
            if max(recent) == min(recent):
                logger.info(
                    "Converged: no improvement for %d generations (%.4f)",
                    self._cfg.patience,
                    recent[-1],
                )
                return True
        return False


class EvolutionEngine:
    def __init__(
        self,
        cfg: RunConfig,
        llm: LLMClient,
        sim_model: ModelConfig,
        eval_model: ModelConfig,
        gen_model: ModelConfig,
    ):
        self._cfg = cfg
        self._generator = PromptGenerator(llm, gen_model, cfg.scenario)
        self._simulator = AgentSimulator(
            llm, sim_model, cfg.tools, cfg.fake_tools
        )
        self._evaluator = Evaluator(llm, eval_model, cfg.weights)
        self._detector = ConvergenceDetector(cfg.evolution)
        self._evolve_cfg = cfg.evolution
        self._test_cases = cfg.test_cases

    async def run(self) -> GenerationRecord:
        population = await self._generator.initialize(
            self._cfg.basic_prompt, self._evolve_cfg.population_size
        )
        best_overall: PromptEvaluation | None = None

        for gen in range(self._evolve_cfg.max_generations):
            logger.info("=== Generation %d (%d prompts) ===", gen, len(population))

            evaluated = await self._evaluate_population(population)
            evaluated.sort(key=lambda p: p.aggregate_score, reverse=True)

            best = evaluated[0]
            if best_overall is None or best.aggregate_score > best_overall.aggregate_score:
                best_overall = best

            logger.info(
                "Best: %.4f (prompt %s)",
                best.aggregate_score,
                best.prompt_id,
            )

            record = GenerationRecord(
                generation=gen,
                prompts=evaluated,
                best_score=best.aggregate_score,
                best_prompt_id=best.prompt_id,
            )

            if self._detector.check(best.aggregate_score):
                logger.info("Stopping at generation %d", gen)
                return record

            population = await self._next_generation(evaluated, gen + 1)

        return GenerationRecord(
            generation=self._evolve_cfg.max_generations - 1,
            prompts=[],
            best_score=(best_overall.aggregate_score if best_overall else 0.0),
            best_prompt_id=(best_overall.prompt_id if best_overall else ""),
        )

    async def _evaluate_population(
        self, population: list[PromptVariant]
    ) -> list[PromptEvaluation]:
        results: list[PromptEvaluation] = []
        for pv in population:
            test_results = []
            for tc in self._test_cases:
                tr = await self._simulator.simulate(pv.system_prompt, tc)
                tr.prompt_id = pv.id
                test_results.append(tr)
            pe = await self._evaluator.evaluate_prompt(
                pv.id, pv.system_prompt, test_results
            )
            results.append(pe)
        return results

    async def _next_generation(
        self,
        evaluated: list[PromptEvaluation],
        next_gen: int,
    ) -> list[PromptVariant]:
        top_k = self._evolve_cfg.selection_top_k
        elite = evaluated[:top_k]
        new_population: list[PromptVariant] = [
            PromptVariant(
                system_prompt=e.system_prompt,
                parent_id=e.prompt_id,
                generation=next_gen,
                strategy="elite",
            )
            for e in elite
        ]

        remaining = self._evolve_cfg.population_size - len(new_population)
        if remaining <= 0:
            return new_population[: self._evolve_cfg.population_size]

        elite_variants = [
            PromptVariant(system_prompt=e.system_prompt, id=e.prompt_id)
            for e in elite
        ]

        for _ in range(remaining):
            variant = await self._pick_strategy_and_generate(
                elite_variants, evaluated, next_gen
            )
            if variant:
                new_population.append(variant)

        random.shuffle(new_population)
        return new_population

    async def _pick_strategy_and_generate(
        self,
        elite: list[PromptVariant],
        evaluated: list[PromptEvaluation],
        generation: int,
    ) -> PromptVariant | None:
        strategy = self._evolve_cfg.strategy

        if strategy == EvolutionStrategy.all_strategies:
            available: list[str] = []
            if len(elite) >= 2:
                available.append("crossover")
            if evaluated:
                available.append("targeted")
            available.append("baseline")
            strategy_name = random.choice(available)
        else:
            strategy_name = strategy.value

        if strategy_name == "crossover" and len(elite) >= 2:
            a, b = random.sample(elite, 2)
            return await self._generator.crossover(a, b, generation)

        if strategy_name == "targeted" and evaluated:
            parent = random.choice(elite)
            parent_eval = next(
                (e for e in evaluated if e.prompt_id == parent.id), None
            )
            failures = self._find_failures(parent_eval)
            if failures:
                return await self._generator.targeted_mutate(
                    parent, failures, generation
                )

        return await self._generator.baseline_mutate(
            self._cfg.basic_prompt, generation
        )

    def _find_failures(self, pe: PromptEvaluation | None) -> list[str]:
        if not pe:
            return []
        failures = []
        for etr in pe.test_results:
            if etr.scores.aggregate < 0.5:
                tc = etr.test_result.test_case
                failures.append(tc.input[:120])
        return failures[:3]
