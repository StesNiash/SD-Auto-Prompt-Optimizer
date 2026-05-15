from __future__ import annotations

import logging

from .generators import FakeToolsGenerator, TestCasesGenerator
from .llm import LLMClient
from .models import RunConfig

logger = logging.getLogger(__name__)


class SetupPipeline:
    MIN_TEST_CASES = 5

    def __init__(self, llm: LLMClient, cfg: RunConfig):
        self._llm = llm
        self._cfg = cfg

    async def run(self) -> RunConfig:
        cfg = self._cfg

        if cfg.tools:
            logger.info("Generating FakeTools from %d tools ...", len(cfg.tools))
            gen = FakeToolsGenerator(
                self._llm, cfg.models.get("generation", cfg.models["simulation"])
            )
            cfg.fake_tools = await gen.generate(cfg.tools, cfg.scenario)
            logger.info("Generated %d fake tools", len(cfg.fake_tools))
            self._assign_tool_scenarios(cfg)

        if len(cfg.test_cases) < self.MIN_TEST_CASES:
            needed = self.MIN_TEST_CASES - len(cfg.test_cases)
            logger.info(
                "Only %d test cases, generating %d more ...",
                len(cfg.test_cases),
                needed,
            )
            gen = TestCasesGenerator(
                self._llm, cfg.models.get("generation", cfg.models["simulation"])
            )
            extra = await gen.generate(
                scenario=cfg.scenario,
                tools=cfg.tools,
                existing_cases=cfg.test_cases,
                target_count=needed,
            )
            cfg.test_cases.extend(extra)
            logger.info("Now have %d test cases", len(cfg.test_cases))

        return cfg

    @staticmethod
    def _assign_tool_scenarios(cfg: RunConfig) -> None:
        ft_by_name = {ft.tool_name: ft for ft in cfg.fake_tools}
        for tc in cfg.test_cases:
            if not tc.expected_behavior or not tc.expected_behavior.tool_calls:
                continue
            mapping: dict[str, str] = {}
            for tool_name in tc.expected_behavior.tool_calls:
                ft = ft_by_name.get(tool_name)
                if not ft or not ft.responses:
                    continue
                if "error" in (tc.tags or []):
                    match = next(
                        (r for r in ft.responses if "error" in r.scenario_match.lower()),
                        None,
                    )
                    if match:
                        mapping[tool_name] = match.scenario_match
                        continue
                mapping[tool_name] = ft.responses[0].scenario_match
            tc.tool_scenarios = mapping if mapping else None
