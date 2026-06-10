from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from incident_copilot.config import Settings
from incident_copilot.evals.harness import run_all
from incident_copilot.evals.report import write
from incident_copilot.llm.factory import make_provider
from incident_copilot.scenarios import Scenario

app = typer.Typer(help="Multi-agent SRE incident diagnosis copilot.", no_args_is_help=True)

_console = Console()


@app.command()
def diagnose(scenario: str = typer.Option(..., help="Incident scenario to diagnose.")) -> None:
    raise NotImplementedError(f"Diagnosis of '{scenario}' lands with TODO.md step 9.")


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
