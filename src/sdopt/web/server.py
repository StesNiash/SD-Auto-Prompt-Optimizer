from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sdopt.core.persistence import RunDatabase

logger = logging.getLogger(__name__)

app = FastAPI(title="SD Auto Prompt Optimizer UI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = RunDatabase()


@app.get("/api/runs")
def list_runs():
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    row = db.get_run(run_id)
    if row is None:
        raise HTTPException(404, "Run not found")
    result = json.loads(row.get("result_json") or "{}") if row.get("result_json") else {}
    prompts = result.get("prompts", [])
    if prompts:
        prompts.sort(key=lambda p: p["aggregate_score"], reverse=True)
    return {
        "id": row["id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "best_score": result.get("best_score"),
        "generations": result.get("generation", 0) + 1 if prompts else 0,
        "total_prompts": len(prompts),
    }


@app.get("/api/runs/{run_id}/tree")
def get_tree(run_id: str):
    row = db.get_run(run_id)
    if row is None:
        raise HTTPException(404, "Run not found")
    result = json.loads(row.get("result_json") or "{}") if row.get("result_json") else {}
    prompts = result.get("prompts", [])

    nodes = []
    edges = []
    gen_groups: dict[int, list[dict]] = {}

    for p in prompts:
        gen = p.get("generation", 0)
        gen_groups.setdefault(gen, []).append(p)

    max_gen = max(gen_groups.keys()) if gen_groups else 0
    node_width = 220
    node_height = 70
    h_gap = 30
    v_gap = 80

    for gen in sorted(gen_groups.keys()):
        items = sorted(gen_groups[gen], key=lambda p: p["aggregate_score"], reverse=True)
        total_w = len(items) * node_width + (len(items) - 1) * h_gap
        start_x = -total_w / 2

        for i, p in enumerate(items):
            pid = p["prompt_id"]
            score = p["aggregate_score"]
            label = f"Gen {gen}\n{score:.3f}"
            color = _score_color(score)

            nodes.append({
                "id": pid,
                "type": "promptNode",
                "position": {"x": start_x + i * (node_width + h_gap), "y": gen * (node_height + v_gap)},
                "data": {
                    "label": label,
                    "prompt_id": pid,
                    "system_prompt": p.get("system_prompt", "")[:120],
                    "score": score,
                    "generation": gen,
                    "color": color,
                },
                "style": {"width": node_width, "height": node_height},
            })

            parent = p.get("parent_id")
            if parent:
                edges.append({
                    "id": f"{parent}→{pid}",
                    "source": parent,
                    "target": pid,
                    "animated": True,
                    "style": {"stroke": "#666"},
                })

    return {"nodes": nodes, "edges": edges, "max_generation": max_gen}


@app.get("/api/runs/{run_id}/prompts/{prompt_id}")
def get_prompt_detail(run_id: str, prompt_id: str):
    row = db.get_run(run_id)
    if row is None:
        raise HTTPException(404, "Run not found")
    result = json.loads(row.get("result_json") or "{}") if row.get("result_json") else {}
    prompts = result.get("prompts", [])

    match = next((p for p in prompts if p["prompt_id"] == prompt_id), None)
    if match is None:
        raise HTTPException(404, "Prompt not found")

    test_results = match.get("test_results", [])
    details = []
    for tr in test_results:
        tc = tr.get("test_result", {}).get("test_case", {})
        details.append({
            "input": tc.get("input", ""),
            "expected_tool_calls": (tc.get("expected_behavior") or {}).get("tool_calls"),
            "response": tr.get("test_result", {}).get("response", ""),
            "tool_calls": tr.get("test_result", {}).get("tool_calls", []),
            "scores": tr.get("scores", {}),
        })

    return {
        "prompt_id": match["prompt_id"],
        "system_prompt": match.get("system_prompt", ""),
        "aggregate_score": match.get("aggregate_score", 0),
        "generation": match.get("generation", 0),
        "strategy": match.get("strategy"),
        "parent_id": match.get("parent_id"),
        "test_results": details,
    }


def _score_color(s: float) -> str:
    if s >= 0.8:
        return "#22c55e"
    if s >= 0.5:
        return "#eab308"
    return "#ef4444"


def serve(host: str = "127.0.0.1", port: int = 8512) -> None:
    import uvicorn

    static_dir = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="ui")

    uvicorn.run(app, host=host, port=port, log_level="info")
