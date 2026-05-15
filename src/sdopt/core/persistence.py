from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import GenerationRecord, RunConfig

DEFAULT_DB_DIR = Path.home() / ".sdopt"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "runs.db"


def _serialize(obj: Any) -> Any:
    if isinstance(obj, (Path, datetime)):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


class RunDatabase:
    def __init__(self, db_path: str | Path | None = None):
        self._path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        import sqlite3
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                config_json TEXT NOT NULL,
                result_json TEXT
            )
        """)
        conn.commit()
        conn.close()

    def create_run(self, cfg: RunConfig) -> str:
        run_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        conn.execute(
            "INSERT INTO runs (id, created_at, updated_at, status, config_json) VALUES (?, ?, ?, 'running', ?)",
            (run_id, now, now, cfg.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return run_id

    def finish_run(self, run_id: str, result: GenerationRecord) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        conn.execute(
            "UPDATE runs SET status = 'completed', updated_at = ?, result_json = ? WHERE id = ?",
            (now, result.model_dump_json(), run_id),
        )
        conn.commit()
        conn.close()

    def fail_run(self, run_id: str, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        conn.execute(
            "UPDATE runs SET status = 'failed', updated_at = ?, result_json = ? WHERE id = ?",
            (now, json.dumps({"error": error}), run_id),
        )
        conn.commit()
        conn.close()

    def get_run(self, run_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def list_runs(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, created_at, status, config_json, result_json FROM runs ORDER BY created_at DESC"
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    cfg = json.loads(d.pop("config_json"))
                    d["scenario"] = cfg.get("scenario", "")[:80]
                    d["model"] = cfg.get("models", {}).get("simulation", {}).get("model", "?")
                except Exception:
                    d["scenario"] = "?"
                    d["model"] = "?"
                try:
                    res = json.loads(d.get("result_json") or "{}")
                    d["best_score"] = res.get("best_score")
                except Exception:
                    d["best_score"] = None
                result.append(d)
            return result
        finally:
            conn.close()

    def export_run(self, run_id: str, fmt: str = "json") -> str | None:
        row = self.get_run(run_id)
        if row is None:
            return None
        if fmt == "json":
            return json.dumps(row, indent=2, default=_serialize)
        if fmt in ("md", "markdown"):
            return self._to_markdown(row)
        return json.dumps(row, indent=2, default=_serialize)

    def _to_markdown(self, row: dict) -> str:
        cfg = json.loads(row.get("config_json", "{}"))
        result = json.loads(row.get("result_json", "{}"))

        lines = [
            f"# Run {row['id']}",
            f"",
            f"- **Status:** {row['status']}",
            f"- **Created:** {row['created_at']}",
            f"",
            f"## Config",
            f"",
            f"- Scenario: {cfg.get('scenario', '?')[:200]}",
            f"- Model: {cfg.get('models', {}).get('simulation', {}).get('model', '?')}",
            f"- Population: {cfg.get('evolution', {}).get('population_size', '?')}",
            f"- Max generations: {cfg.get('evolution', {}).get('max_generations', '?')}",
            f"",
        ]

        if result:
            lines += [
                f"## Results",
                f"",
                f"- **Best score:** {result.get('best_score', '?')}",
                f"- **Best prompt ID:** {result.get('best_prompt_id', '?')}",
                f"- **Generations:** {result.get('generation', '?')}",
                f"",
            ]
            prompts = result.get("prompts", [])
            if prompts:
                prompts.sort(key=lambda p: p["aggregate_score"], reverse=True)
                best = prompts[0]
                lines += [
                    f"### Best prompt",
                    f"",
                    f"```",
                    f"{best['system_prompt']}",
                    f"```",
                    f"",
                    f"**Scores:** correctness={best['aggregate_score']}",
                    f"",
                ]

        return "\n".join(lines)

    def close(self) -> None:
        pass
