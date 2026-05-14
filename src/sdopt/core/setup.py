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
