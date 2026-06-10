import typer

app = typer.Typer(help="Multi-agent SRE incident diagnosis copilot.", no_args_is_help=True)


@app.command()
def diagnose(scenario: str = typer.Option(..., help="Incident scenario to diagnose.")) -> None:
    raise NotImplementedError(f"Diagnosis of '{scenario}' lands with TODO.md step 5.")


@app.command()
def evals(
    all_scenarios: bool = typer.Option(False, "--all", help="Evaluate every scenario."),
) -> None:
    raise NotImplementedError(f"Eval harness (all={all_scenarios}) lands with TODO.md step 8.")
