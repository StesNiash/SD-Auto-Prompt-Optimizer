from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from sdopt.core import (
    EvolutionEngine,
    LLMClient,
    RunConfig,
    RunDatabase,
    Settings,
    SetupPipeline,
    load_config,
)

console = Console()


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )


async def _run_optimization(cfg: RunConfig, run_id: str) -> None:
    settings = Settings()
    llm = LLMClient(settings)
    db = RunDatabase()

    sim_model = cfg.models["simulation"]
    eval_model = cfg.models["evaluation"]
    gen_model = cfg.models.get("generation", sim_model)

    try:
        with _make_progress() as progress:
            task = progress.add_task("Setting up...", total=None)
            setup = SetupPipeline(llm, cfg)
            cfg = await setup.run()
            progress.remove_task(task)

            gen_task = progress.add_task("Running evolution...", total=cfg.evolution.max_generations)

            def _on_progress(event: str, data: dict) -> None:
                if event == "generation_start":
                    gen = data["gen"]
                    max_gen = data["max_gen"]
                    progress.update(gen_task, description=f"Gen {gen}/{max_gen} — simulating...")
                elif event == "generation_end":
                    gen = data["gen"]
                    scores = data["scores"]
                    best = data["best_score"]
                    progress.update(gen_task, advance=1)
                    progress.update(
                        gen_task,
                        description=f"Gen {gen} done — best {best:.3f} | scores: {[f'{s:.2f}' for s in scores[:3]]}...",
                    )
                    console.log(f"[cyan]Gen {gen}[/] best [green]{best:.4f}[/] | top-3: {[f'{s:.3f}' for s in scores[:3]]}")

            engine = EvolutionEngine(cfg, llm, sim_model, eval_model, gen_model, on_event=_on_progress)

            logging.getLogger("sdopt.core.evolution").setLevel(logging.WARNING)
            result = await engine.run()

            progress.update(gen_task, completed=result.generation + 1)

        db.finish_run(run_id, result)

        if not result.prompts:
            console.print("[yellow]No results from evolution[/yellow]")
            return

        result.prompts.sort(key=lambda p: p.aggregate_score, reverse=True)
        best_pe = result.prompts[0]

        console.print()
        panel = Panel(
            Text(f"Evolution complete — {result.generation + 1} generations", style="bold green"),
            box=box.ROUNDED,
        )
        console.print(panel)

        table = Table(box=box.SIMPLE_HEAD, title="Best prompt results")
        table.add_column("Criterion", style="cyan")
        table.add_column("Score", justify="right")

        avg_scores = _average_scores(best_pe.test_results)
        for k, v in avg_scores.items():
            color = "green" if v >= 0.7 else "yellow" if v >= 0.4 else "red"
            table.add_row(k, f"[{color}]{v:.4f}[/]")

        console.print(table)
        console.print()

        console.print("[bold]Best prompt:[/bold]")
        console.print(Panel(
            best_pe.system_prompt,
            box=box.SQUARE,
            border_style="blue",
        ))

        details = Table(box=box.SIMPLE)
        details.add_column("Test case", style="cyan")
        details.add_column("Score", justify="right")
        details.add_column("Result")
        for etr in best_pe.test_results:
            inp = etr.test_result.test_case.input[:60]
            score = etr.scores.aggregate
            color = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "red"
            tools = f" ({len(etr.test_result.tool_calls)} calls)" if etr.test_result.tool_calls else ""
            details.add_row(inp, f"[{color}]{score:.4f}[/]", f"OK{tools}" if score >= 0.5 else "FAIL")
        console.print(details)

        console.print(f"\nRun saved: [bold]{run_id}[/]")

    except Exception:
        logger = logging.getLogger("sdopt")
        logger.exception("Run failed")
        db.fail_run(run_id, "See logs for details")
        raise


def _average_scores(results):
    if not results:
        return {}
    keys = ["correctness", "efficiency", "helpfulness", "robustness", "aggregate"]
    return {
        k: sum(getattr(r.scores, k) for r in results) / len(results)
        for k in keys
    }


def cmd_run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    db = RunDatabase()
    run_id = db.create_run(cfg)
    console.log(f"Run [bold]{run_id}[/] started")
    asyncio.run(_run_optimization(cfg, run_id))


def cmd_list(args: argparse.Namespace) -> None:
    db = RunDatabase()
    runs = db.list_runs()
    if not runs:
        console.print("[yellow]No runs found[/yellow]")
        return
    table = Table(box=box.SIMPLE_HEAD, title="Runs")
    table.add_column("ID", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Status")
    table.add_column("Best score")
    table.add_column("Model")
    table.add_column("Scenario")
    for r in runs:
        score = f"{r['best_score']:.4f}" if r.get("best_score") is not None else "-"
        table.add_row(
            r["id"],
            r["created_at"][:19],
            r["status"],
            score,
            r.get("model", "?"),
            r.get("scenario", "?")[:50],
        )
    console.print(table)


def cmd_view(args: argparse.Namespace) -> None:
    db = RunDatabase()
    row = db.get_run(args.run_id)
    if row is None:
        console.print(f"[red]Run '{args.run_id}' not found[/red]")
        return

    raw = db.export_run(args.run_id, fmt=args.format or "json")
    if raw is None:
        return

    if args.format in ("md", "markdown"):
        console.print(raw)
        return

    data = json.loads(raw)
    status_color = "green" if data["status"] == "completed" else "red"
    console.print(f"Run [bold]{data['id']}[/] — [{status_color}]{data['status']}[/]")
    console.print(f"Created: {data['created_at']}")

    if data.get("result_json"):
        result = json.loads(data["result_json"])
        console.print(f"Best score: [bold]{result.get('best_score', '?')}[/]")
        console.print(f"Generations: {result.get('generation', '?')}")
        prompts = result.get("prompts", [])
        if prompts:
            prompts.sort(key=lambda p: p["aggregate_score"], reverse=True)
            best = prompts[0]
            console.print()
            console.print("[bold]Best prompt:[/bold]")
            console.print(Panel(best["system_prompt"], box=box.SQUARE, border_style="blue"))


def cmd_export(args: argparse.Namespace) -> None:
    db = RunDatabase()
    raw = db.export_run(args.run_id, fmt=args.format)
    if raw is None:
        console.print(f"[red]Run '{args.run_id}' not found[/red]")
        return
    if args.output:
        Path(args.output).write_text(raw, encoding="utf-8")
        console.log(f"Exported to {args.output}")
    else:
        console.print(raw)


def cmd_compare(args: argparse.Namespace) -> None:
    db = RunDatabase()
    a = db.get_run(args.run_a)
    b = db.get_run(args.run_b)
    if a is None or b is None:
        console.print("[red]One or both runs not found[/red]")
        return
    ra = json.loads(a.get("result_json") or "{}")
    rb = json.loads(b.get("result_json") or "{}")
    table = Table(box=box.SIMPLE_HEAD, title="Comparison")
    table.add_column("", style="cyan")
    table.add_column(f"Run {args.run_a[:8]}", justify="right")
    table.add_column(f"Run {args.run_b[:8]}", justify="right")
    table.add_row("Best score", f"{ra.get('best_score', '?'):.4f}" if ra.get('best_score') else "?", f"{rb.get('best_score', '?'):.4f}" if rb.get('best_score') else "?")
    table.add_row("Generations", str(ra.get('generation', '?')), str(rb.get('generation', '?')))
    pa = (ra.get("prompts") or [{}])[0].get("system_prompt", "?")[:80]
    pb = (rb.get("prompts") or [{}])[0].get("system_prompt", "?")[:80]
    table.add_row("Best prompt", pa, pb)
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sdopt",
        description="SD Auto Prompt Optimizer — evolutionary system prompt optimizer",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run optimization pipeline")
    run_p.add_argument("config", type=str, help="Path to config YAML")
    run_p.set_defaults(func=cmd_run)

    list_p = sub.add_parser("list", aliases=["ls"], help="List runs")
    list_p.set_defaults(func=cmd_list)

    view_p = sub.add_parser("view", help="View run results")
    view_p.add_argument("run_id", type=str)
    view_p.add_argument("--format", "-f", choices=["json", "md", "markdown"], default="json")
    view_p.set_defaults(func=cmd_view)

    export_p = sub.add_parser("export", help="Export run results")
    export_p.add_argument("run_id", type=str)
    export_p.add_argument("--format", "-f", choices=["json", "md", "markdown"], default="json")
    export_p.add_argument("--output", "-o", type=str, help="Output file path")
    export_p.set_defaults(func=cmd_export)

    cmp_p = sub.add_parser("compare", help="Compare two runs")
    cmp_p.add_argument("run_a", type=str)
    cmp_p.add_argument("run_b", type=str)
    cmp_p.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
