# SD Auto Prompt Optimizer — Architecture Plan

## Overview
Эволюционный оптимизатор системных промптов. На вход — сценарий, инструменты (опционально), тест-кейсы и базовый промпт. На выходе — оптимизированный системный промпт.

---

## 1. Input Data

### 1.1 Scenario (контекст)
Описание общей задачи и роли ассистента. Например: "Ты - ИИ Ассистент в банке, помогаешь клиентам с транзакциями."

### 1.2 Basic Prompt
Стартовый system prompt, от которого начинаем оптимизацию.

### 1.3 Tools (опционально)
Список инструментов с:
- Описанием (что делает)
- Примерами вызова
- Примерами ответов (success, error, edge cases)

### 1.4 Fake Tools (генерируются всегда при наличии Tools)
На основе описаний и примеров инструментов LLM генерирует детерминированные моки:
- Каждый fake tool — это функция, которая возвращает предопределённый ответ в зависимости от сценария тест-кейса
- Для каждого инструмента создаются варианты: success, error, timeout, partial success, etc.
- Fake tools НЕ заменяют real API — они симулируют все возможные исходы для тестирования промпта

Если же сценарий НЕ подразумевает использования инструментов — Fake Tools не нужны.

### 1.5 Test Cases
Расширенная структура:

```yaml
test_case:
  input: str                          # Что говорит пользователь
  expected_behavior:                  # Что агент ДОЛЖЕН сделать
    tool_calls: [ToolCall, ...]       # Опционально: ожидаемые вызовы инструментов
    constraints: [str, ...]           # Пример: "не запрашивать подтверждение дважды"
  expected_output:                    # Каким должен быть финальный ответ
    text_contains: [str, ...]         # Подстроки, которые должны быть в ответе
    text_not_contains: [str, ...]     # Подстроки, которых быть не должно
    format: json | text | markdown    # Ожидаемый формат
  tags: [str, ...]                    # Для фильтрации/анализа (например: "error_case", "happy_path")
```

### 1.6 Usage Cases (опционально)
Если пользователь предоставил всего 2-3 тест-кейса, LLM генерирует дополнительные на основе сценария и инструментов.

---

## 2. Pipeline

### Фаза 1: Setup
1. Проверить входные данные
2. Если предоставлены tools — сгенерировать Fake Tools (моки со всеми исходами)
3. Если usage cases太少 — сгенерировать дополнительные
4. Сгенерировать evaluation prompt (инструкция для judge-модели)

### Фаза 2: Эволюционный цикл (N поколений)

```
                    ┌──────────────────────┐
                    │   Population: M       │
                    │   prompt variants     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Test all prompts     │
                    │  on all test cases    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Evaluate each        │
                    │  prompt-response      │
                    │  pair                 │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Rating (aggregate    │
                    │  score per prompt)    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Select best K        │
                    │  prompts + mutate     │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
            Converged?            Next generation
            → Output              → Repeat
```

### 2.1 Generate Prompt Variants

Стратегии (выбирается пользователем):

**A. Crossover**
- Берём топ-K промптов
- Скрещиваем: берём часть system prompt от одного, часть от другого
- Добавляем случайную мутацию (замена фразы, переформулировка)

**B. Targeted Mutation** (рекомендуемая)
- Анализируем на каких тест-кейсах промпт провалился
- Генерируем новый промпт с инструкцией: "исправь проблему X"
- Пример: "Prompt fails when user asks about refunds. Generate a version that handles refund requests correctly."

**C. Keep Baseline**
- Базовый промпт всегда остаётся в популяции
- Остальные мутируют от него случайно или целенаправленно

**D. All (пользователь хочет все три)**
На каждой итерации:
- Часть потомков от crossover
- Часть от targeted mutation
- Baseline всегда в популяции

### 2.2 Testing

Каждый вариант промпта прогоняется через ВСЕ test cases.

Для каждого test case:
1. Запускаем симуляцию: system prompt + user input → агент
2. Агент может вызывать fake tools (которые возвращают предопределённые ответы)
3. Сохраняем: финальный ответ + последовательность tool calls

### 2.3 Evaluation (LLM-as-a-judge)

4 критерия, каждый оценивается от 0 до 1:

| Критерий | Описание |
|-----------|----------|
| **Correctness** | Агент выполнил expected behavior? Вызвал правильные инструменты? |
| **Efficiency** | Минимальное количество лишних tool calls? Нет лишних действий? |
| **Helpfulness** | Ответ полезен пользователю? Решает его проблему? |
| **Robustness** | Не сломался на краевых случаях? Корректно обработал ошибки? |

Финальный score = weighted_sum(correctness * w1 + efficiency * w2 + helpfulness * w3 + robustness * w4)

Score per prompt = average(score across all test cases)

### 2.4 Selection & Mutation

- Отбираем топ-K промптов (по aggregate score)
- Применяем выбранную стратегию мутации
- Создаём M новых вариантов (размер популяции константен)

### 2.5 Convergence

Цикл останавливается, когда:
- Достигнут порог качества (например, average score > 0.95)
- ИЛИ score не улучшался последние N поколений (patience)

---

## 3. Multi-Model Support

```yaml
config:
  generation:
    provider: openai
    model: gpt-4o-mini    # Дешёвая модель для генерации вариантов
    temperature: 0.8
  evaluation:
    provider: openai
    model: gpt-4o         # Дорогая модель для оценки
    temperature: 0.0
  simulation:
    provider: openai
    model: gpt-4o-mini    # Модель, которая играет роль агента
    temperature: 0.0
```

Пользователь может выбрать любую комбинацию провайдеров (OpenAI, Anthropic, Google, локальные модели).

---

## 4. Observability (UI)

### Требования к UI:
1. **Evolution Tree** — дерево поколений: каждая нода = промпт с его score
2. **История** — видно какие промпты перешли в следующее поколение, какие отсеялись
3. **Drill-down** — нажал на промпт → видишь все его тесты и результаты каждого
4. **Copy** — кнопка копирования любого промпта
5. **Live progress** — текущее поколение, estimated time, логи

### Tech stack для UI:
- React + TypeScript
- Dagre или React Flow для дерева
- WebSocket или SSE для live updates
- Electron (desktop app) или просто web-интерфейс

---

## 5. Tech Stack (предложение)

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11+ (FastAPI или просто CLI with asyncio) |
| LLM calls | LiteLLM (единый интерфейс для всех провайдеров) |
| Serialization | Pydantic + YAML для конфигов |
| UI | React + TypeScript + Vite |
| Граф | React Flow |
| Хранилище | SQLite (через SQLAlchemy) для логов/результатов |

---

## 6. Future Ideas

- Автоматическая генерация test cases из истории реальных чатов
- A/B тестирование лучших промптов в production
- Fine-tuning evaluation criteria под специфику бизнеса
- Поддержка multi-turn диалогов (сейчас — только single-turn)
