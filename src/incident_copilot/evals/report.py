from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

from incident_copilot.evals.metrics import ScenarioEvalResult


def write(
    results: list[ScenarioEvalResult],
    *,
    reports_dir: Path = Path("reports"),
) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    md_path = reports_dir / f"eval_{timestamp}.md"
    json_path = reports_dir / f"eval_{timestamp}.json"
    md_path.write_text(_render_markdown(results, timestamp))
    json_path.write_text(_render_json(results))
    return md_path, json_path


def _render_markdown(results: list[ScenarioEvalResult], timestamp: str) -> str:
    lines: list[str] = [
        "# Agentic Evaluation Report",
        "",
        f"Generated: {timestamp}  "
        f"Scenarios: {len(results)}  "
        f"Total runs: {sum(r.n_runs for r in results)}",
        "",
        "## Summary",
        "",
        "| Scenario | Runs | Precision | Recall | F1 | Consistency | Correct | "
        "Loops | Val Errs | Trips | Avg Tokens |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        m = r.metrics
        correct = "yes" if m.reasoning_correct else "no"
        lines.append(
            f"| {r.scenario_name} | {r.n_runs} "
            f"| {m.tool_precision:.3f} | {m.tool_recall:.3f} | {m.tool_f1:.3f} "
            f"| {m.trajectory_consistency:.3f} | {correct} "
            f"| {m.loop_count} | {m.validation_errors} | {m.breaker_trips} "
            f"| {m.avg_tokens:,} |"
        )
    lines.append("")
    for r in results:
        lines.extend(_scenario_section(r))
    return "\n".join(lines) + "\n"


def _scenario_section(result: ScenarioEvalResult) -> list[str]:
    m = result.metrics
    lines: list[str] = [
        f"## {result.scenario_name}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Tool precision | {m.tool_precision:.3f} |",
        f"| Tool recall | {m.tool_recall:.3f} |",
        f"| Tool F1 | {m.tool_f1:.3f} |",
        f"| Trajectory consistency | {m.trajectory_consistency:.3f} |",
        f"| Reasoning correct | {'yes' if m.reasoning_correct else 'no'} |",
        f"| Redundant calls | {m.redundant_calls} |",
        f"| Loop count | {m.loop_count} |",
        f"| Validation errors | {m.validation_errors} |",
        f"| Breaker trips | {m.breaker_trips} |",
        f"| Avg tokens | {m.avg_tokens:,} |",
        f"| Avg duration (s) | {m.avg_duration_seconds:.2f} |",
        "",
    ]
    for idx, run in enumerate(result.runs, start=1):
        lines.append(f"### Diagnosis (run {idx})")
        lines.append("")
        lines.append(run.diagnosis if run.diagnosis else "_No diagnosis produced._")
        lines.append("")
    return lines


def _render_json(results: list[ScenarioEvalResult]) -> str:
    data = [dataclasses.asdict(r) for r in results]
    return json.dumps(data, indent=2)
