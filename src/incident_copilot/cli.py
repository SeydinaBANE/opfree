from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import cast

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import GraphState, TrajectoryEntry
from incident_copilot.config import Settings
from incident_copilot.evals.harness import run_all
from incident_copilot.evals.report import write
from incident_copilot.llm.factory import make_provider
from incident_copilot.scenarios import Scenario

app = typer.Typer(help="Multi-agent SRE incident diagnosis copilot.", no_args_is_help=True)

_console = Console()
_DETAIL_TRUNCATE_AT = 90


async def _run_diagnose(scenario_name: str, settings: Settings) -> GraphState:
    scenario_path = Path("scenarios") / f"{scenario_name}.json"
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")
    scenario = Scenario.load(scenario_path)
    llm = make_provider(settings)
    graph = build_graph(llm, settings=settings)
    initial = GraphState(
        scenario=scenario,
        findings=[],
        trajectory=[],
        input_tokens=0,
        output_tokens=0,
        iteration_count=0,
        next_agent="",
        diagnosis=None,
        start_time=time.monotonic(),
    )
    # LangGraph return type erased; cast to GraphState is safe at runtime.
    raw = await graph.ainvoke(
        initial,
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )
    return cast(GraphState, raw)


def _build_trajectory_table(trajectory: list[TrajectoryEntry]) -> Table:
    table = Table(title="Trajectory", box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("Step", style="dim", width=5, no_wrap=True)
    table.add_column("Agent", style="cyan", width=20, no_wrap=True)
    table.add_column("Action", style="magenta", width=18, no_wrap=True)
    table.add_column("Detail", style="white")
    for entry in trajectory:
        table.add_row(
            str(entry["step"]),
            entry["agent"],
            entry["action"],
            entry["detail"][:_DETAIL_TRUNCATE_AT],
        )
    return table


def _build_diagnosis_panel(diagnosis: str | None, scenario_name: str) -> Panel:
    title = f"Diagnosis — {scenario_name}"
    if diagnosis is None:
        return Panel(
            "[yellow]No diagnosis produced (circuit breaker may have fired).[/yellow]",
            title=title,
            border_style="yellow",
        )
    return Panel(diagnosis, title=f"[bold green]{title}[/bold green]", border_style="green")


@app.command()
def diagnose(scenario: str = typer.Option(..., help="Incident scenario name.")) -> None:
    settings = Settings()
    with _console.status(
        f"[bold cyan]Diagnosing scenario '{scenario}'…[/bold cyan]", spinner="dots"
    ):
        try:
            state = asyncio.run(_run_diagnose(scenario, settings))
        except FileNotFoundError as exc:
            _console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

    _console.print(_build_trajectory_table(state["trajectory"]))
    _console.print()
    _console.print(_build_diagnosis_panel(state["diagnosis"], scenario))


@app.command()
def evals(
    all_scenarios: bool = typer.Option(False, "--all", help="Evaluate every scenario."),
    n_runs: int = typer.Option(1, "--runs", help="Number of replays per scenario."),
) -> None:
    settings = Settings()
    scenarios_dir = Path("scenarios")

    if not scenarios_dir.exists():
        _console.print("[red]scenarios/ directory not found[/red]")
        raise typer.Exit(1)

    paths = sorted(scenarios_dir.glob("*.json"))
    if not paths:
        _console.print("[red]No scenario files found in scenarios/[/red]")
        raise typer.Exit(1)

    scenarios = [Scenario.load(p) for p in paths]
    if not all_scenarios:
        scenarios = scenarios[:1]

    llm = make_provider(settings)
    _console.print(f"Running evals: {len(scenarios)} scenario(s) x {n_runs} run(s)...")

    results = asyncio.run(run_all(scenarios, llm, settings, n_runs=n_runs))
    md_path, json_path = write(results)
    _console.print(f"[green]Reports written:[/green] {md_path}  {json_path}")
