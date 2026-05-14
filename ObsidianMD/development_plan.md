# Development Plan

## Phase 0: Project Setup
- [x] Initialize Python project with `pyproject.toml`
- [x] Set up project structure (core/, cli/, web/, tests/)
- [x] Configure dependencies: LiteLLM, Pydantic, Rich, SQLAlchemy
- [x] Ruff / mypy config in pyproject.toml

## Phase 1: Core Data Models
- [x] Pydantic models: Scenario, Tool, FakeTool, TestCase, PromptVariant
- [x] Evaluation models: 4-criteria scoring
- [x] Config: RunConfig, EvolutionConfig, WeightsConfig, ModelConfig
- [x] Settings: API keys via pydantic-settings (SDOPT_ prefix)

## Phase 2: Data Loader & Setup
- [x] YAML config loader
- [x] FakeToolsGenerator — LLM генерирует моки из Tool spec
- [x] TestCasesGenerator — LLM генерирует доп. кейсы
- [x] SetupPipeline — оркестратор setup-фазы

## Phase 3: Simulation Engine
- [x] LLMClient — complete() + generate() через LiteLLM
- [x] AgentSimulator — system prompt → tool calls → response
- [x] FakeToolExecutor — детерминированные мок-ответы

## Phase 4: Evaluation Engine
- [x] Judge — LLM-as-a-judge (4 критерия)
- [x] Evaluator — скоринг и агрегация

## Phase 5: Evolutionary Loop
- [ ] Implement `PromptGenerator`:
  - Crossover strategy
  - Targeted mutation strategy (анализ провалов → фикс)
  - Baseline keeper
- [ ] Implement `EvolutionEngine` — orchestrator:
  - Управление популяцией
  - Запуск тестирования
  - Запуск оценки
  - Селекция + мутация
  - Проверка сходимости
- [ ] Implement convergence detection (threshold / patience)

## Phase 6: CLI Interface
- [ ] CLI с использованием Rich:
  - `sdopt run config.yaml` — запуск оптимизации
  - `sdopt view <run-id>` — просмотр результатов
  - `sdopt compare <run-id-1> <run-id-2>` — сравнение
- [ ] Live progress bar в терминале

## Phase 7: Persistence & Logging
- [ ] SQLite schema (SQLAlchemy):
  - runs, generations, prompts, test_results, evaluations
- [ ] Экспорт результатов: JSON / YAML / Markdown report
- [ ] Seed-based reproducibility

## Phase 8: UI (Web)
- [ ] React + TypeScript + Vite setup
- [ ] React Flow для evolution tree
- [ ] API endpoints (FastAPI) для данных
- [ ] Drill-down: prompt → test results
- [ ] Copy-to-clipboard
- [ ] WebSocket для live progress

## Phase 9: Testing & Polish
- [ ] Unit tests: models, simulator, evaluator
- [ ] Integration tests: полный пайплайн на синтетических данных
- [ ] Пример конфига в `examples/`
- [ ] README с quick start
