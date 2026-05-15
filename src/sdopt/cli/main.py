from __future__ import annotations

import argparse
import asyncio
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


async def _run_optimization(cfg: RunConfig) -> None:
    settings = Settings()
    llm = LLMClient(settings)

    sim_model = cfg.models["simulation"]
    eval_model = cfg.models["evaluation"]
    gen_model = cfg.models.get("generation", sim_model)

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

    if not result.prompts:
        best_pe = None
    else:
        result.prompts.sort(key=lambda p: p.aggregate_score, reverse=True)
        best_pe = result.prompts[0]

    console.print()
    panel = Panel(
        Text(f"Evolution complete — {result.generation + 1} generations", style="bold green"),
        box=box.ROUNDED,
    )
    console.print(panel)

    if best_pe:
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
    else:
        console.print("[yellow]No results from evolution[/yellow]")


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
    asyncio.run(_run_optimization(cfg))


def cmd_view(args: argparse.Namespace) -> None:
    console.print("[yellow]view: not yet implemented (Phase 7 — persistence)[/yellow]")


def cmd_compare(args: argparse.Namespace) -> None:
    console.print("[yellow]compare: not yet implemented (Phase 7 — persistence)[/yellow]")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sdopt",
        description="SD Auto Prompt Optimizer — evolutionary system prompt optimizer",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run optimization pipeline")
    run_p.add_argument("config", type=str, help="Path to config YAML")
    run_p.set_defaults(func=cmd_run)

    view_p = sub.add_parser("view", help="View run results")
    view_p.add_argument("run_id", type=str, help="Run ID")
    view_p.set_defaults(func=cmd_view)

    cmp_p = sub.add_parser("compare", help="Compare two runs")
    cmp_p.add_argument("run_a", type=str)
    cmp_p.add_argument("run_b", type=str)
    cmp_p.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
