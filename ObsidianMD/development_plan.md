# Development Plan

## Phase 0: Project Setup
- [x] Initialize Python project with `pyproject.toml` (Poetry or UV)
- [x] Set up project structure (core/, cli/, web/, tests/)
- [x] Configure dependencies: LiteLLM, Pydantic, SQLite (SQLAlchemy), Rich (CLI logging)
- [x] Set up pre-commit / ruff / mypy

## Phase 1: Core Data Models
- [x] Define Pydantic models:
  - `Scenario` — контекст задачи
  - `Tool` / `ToolExample` — описание и примеры вызовов
  - `FakeTool` / `FakeToolResponse` — детерминированные моки
  - `TestCase` — input, expected_behavior, expected_output, tags
  - `PromptVariant` — system prompt + metadata
  - `TestResult` — результат прогона одного теста
  - `EvaluationScore` — 4 критерия + aggregate
  - `GenerationRecord` — вся история поколения
- [x] Config model: LLM providers, strategy, convergence params

## Phase 2: Data Loader & Setup
- [x] Implement YAML/JSON config loader
- [x] Implement FakeToolsGenerator — LLM генерирует моки из Tool spec
- [x] Implement TestCasesGenerator — LLM генерирует доп. кейсы на основе сценария
- [x] Implement StrategySelector — обработка выбора мутации, моделей

## Phase 3: Simulation Engine
- [x] Implement LLM client abstraction (через LiteLLM)
- [x] Implement `AgentSimulator` — запускает system prompt + user input, поддерживает tool calls
- [x] Implement `FakeToolExecutor` — по сценарию тест-кейса возвращает нужный мок-ответ
- [x] Результат: финальный ответ + последовательность tool calls

## Phase 4: Evaluation Engine
- [ ] Implement `Judge` — LLM-as-a-judge по 4 критериям
- [ ] Implement scoring: weighted_sum → aggregate per prompt
- [ ] Сохранение всей истории оценок в SQLite

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
