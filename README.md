# SD Auto Prompt Optimizer

Evolutionary system prompt optimizer — uses LLM-as-a-judge and genetic algorithms to automatically improve system prompts for LLM agents with tool-calling capabilities.

## How it works

1. **Setup phase**: LLM generates fake tool implementations (mocks) and additional test cases from your config
2. **Evolution loop** (multi-generation):
   - **Generate** prompt variants via crossover, targeted mutation, and baseline strategies
   - **Simulate** each variant against test cases using fake tools
   - **Evaluate** performance via LLM-as-a-judge (correctness, efficiency, helpfulness, robustness)
   - **Select** top variants, **mutate** and repeat
3. **Output**: Best-performing system prompt with detailed scores

## Quick start

```bash
# 1. Install
pip install sdopt
# or from source:
pip install -e .

# 2. Install web UI dependencies (optional)
cd ui && npm install && cd ..

# 3. Set up API keys
cp .env.example .env
# Edit .env with your keys (SDOPT_OPENAI_API_KEY, SDOPT_OPENROUTER_API_KEY, etc.)

# 4. Run optimization
sdopt run examples/config.yaml
```

## CLI commands

### `sdopt run <config>`

Run the full optimization pipeline.

```bash
sdopt run examples/config.yaml
```

Takes a YAML config with scenario, tools, test cases, evolution parameters, and model settings.

### `sdopt list` / `sdopt ls`

List all previous runs.

```bash
sdopt list
```

### `sdopt view <run_id>`

View details of a specific run.

```bash
sdopt view abc123
sdopt view abc123 --format json
sdopt view abc123 --format md
```

### `sdopt export <run_id>`

Export run results to JSON or Markdown.

```bash
sdopt export abc123 --format json --output results.json
sdopt export abc123 --format md --output results.md
```

### `sdopt compare <run_a> <run_b>`

Compare two runs side by side.

```bash
sdopt compare abc123 def456
```

### `sdopt serve`

Start the web UI (requires FastAPI + uvicorn).

```bash
# Install web dependencies
pip install 'sdopt[web]'

# Build frontend (first time or after changes)
cd ui && npm install && npm run build && cd ..

# Start server
sdopt serve
sdopt serve --host 0.0.0.0 --port 8512
```

The UI auto-serves the built frontend from `ui/dist/`. For frontend development:

```bash
cd ui
npm run dev     # Vite dev server on :5173 (proxies API to :8512)
```

## Web UI

The frontend is built with React + TypeScript + React Flow (@xyflow/react) and includes:

- **Run list** — all previous runs with scores and status
- **Evolution tree** — interactive React Flow DAG showing generations with colored nodes by score
- **Prompt detail** — full system prompt, test results per test case, and copy-to-clipboard

API endpoints (FastAPI, port 8512):

| Endpoint | Description |
|---|---|
| `GET /api/runs` | List all runs |
| `GET /api/runs/{id}` | Run summary |
| `GET /api/runs/{id}/tree` | Evolution tree (nodes + edges) |
| `GET /api/runs/{id}/prompts/{promptId}` | Prompt detail with test results |

## Configuration

Example config (`examples/config.yaml`):

```yaml
scenario: |
  You are a customer support agent for a bank.
  Help clients with transactions, account issues, and fraud reports.

basic_prompt: |
  You are a helpful assistant.

tools:
  - name: check_balance
    description: Check account balance
    examples:
      - input: '{"account_id": "123"}'
        output: '{"balance": 1500.00}'

test_cases:
  - input: "What's my balance?"
    expected_behavior:
      tool_calls: [check_balance]
    expected_output:
      text_contains: ["balance", "$"]

evolution:
  strategy: targeted   # crossover | targeted | baseline | all
  population_size: 4
  selection_top_k: 3
  max_generations: 5
  convergence_threshold: 0.95
  patience: 3

models:
  generation:
    provider: openrouter
    model: openai/gpt-4o-mini
    temperature: 0.8
    api_base: https://openrouter.ai/api/v1
  evaluation:
    provider: openrouter
    model: openai/gpt-4o-mini
    temperature: 0.0
  simulation:
    provider: openrouter
    model: openai/gpt-4o-mini
    temperature: 0.0
```

### Supported providers

- `openai` — requires `SDOPT_OPENAI_API_KEY`
- `anthropic` — requires `SDOPT_ANTHROPIC_API_KEY`
- `google` — requires `SDOPT_GOOGLE_API_KEY`
- `openrouter` — requires `SDOPT_OPENROUTER_API_KEY`, supports `api_base`

## Project structure

```
├── src/sdopt/
│   ├── core/           # Backend logic
│   │   ├── models.py       # Pydantic models
│   │   ├── config.py       # Settings + YAML config loader
│   │   ├── llm.py          # LLM client (LiteLLM)
│   │   ├── generators.py   # FakeTools + TestCases generators
│   │   ├── setup.py        # Setup pipeline
│   │   ├── simulator.py    # Agent simulator
│   │   ├── evaluation.py   # Judge + Evaluator
│   │   ├── evolution.py    # Evolution engine
│   │   └── persistence.py  # SQLite database
│   ├── cli/            # CLI interface
│   │   └── main.py
│   └── web/            # FastAPI server
│       └── server.py
├── ui/                 # React + TypeScript frontend
│   └── src/
│       ├── components/
│       │   ├── RunList.tsx
│       │   ├── RunDetail.tsx
│       │   └── PromptDetail.tsx
│       └── App.tsx
├── examples/
│   └── config.yaml     # Example bank scenario
└── ObsidianMD/         # Dev plan & architecture
```

## Persistence

Runs are stored in `~/.sdopt/runs.db` (SQLite). All CLI commands read from this database.
