from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer.testing import CliRunner

from incident_copilot import __version__
from incident_copilot.agents.state import TrajectoryEntry
from incident_copilot.cli import (
    _build_diagnosis_panel,
    _build_trajectory_table,
    _run_diagnose,
    app,
)
from incident_copilot.config import Settings
from incident_copilot.scenarios import Scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
_runner = CliRunner()


def _traj(step: int, agent: str, action: str, detail: str) -> TrajectoryEntry:
    return TrajectoryEntry(step=step, agent=agent, action=action, detail=detail)


def _fake_state(scenario: Scenario, diagnosis: str | None = None) -> dict[str, object]:
    return {
        "scenario": scenario,
        "findings": [],
        "trajectory": [
            _traj(0, "supervisor", "route", "log_analyst"),
            _traj(1, "log_analyst", "tool_call", "list_pods({})"),
        ],
        "input_tokens": 10,
        "output_tokens": 10,
        "iteration_count": 1,
        "next_agent": "synthesize",
        "diagnosis": diagnosis,
        "start_time": 0.0,
    }


# ---------------------------------------------------------------------------
# Existing smoke tests
# ---------------------------------------------------------------------------


def test_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_lists_commands() -> None:
    result = _runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "diagnose" in result.output
    assert "evals" in result.output


# ---------------------------------------------------------------------------
# _run_diagnose
# ---------------------------------------------------------------------------


async def test_run_diagnose_missing_scenario_raises() -> None:
    settings = Settings()
    with pytest.raises(FileNotFoundError, match="Scenario not found"):
        await _run_diagnose("nonexistent_xyz", settings)


async def test_run_diagnose_returns_state_with_diagnosis() -> None:
    settings = Settings()
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    diagnosis = (
        "ROOT CAUSE: database connection refused.\n"
        "EVIDENCE: pod logs show connection refused.\n"
        "REMEDIATION: restart pod.\nCONFIDENCE: high"
    )
    fake = _fake_state(scenario, diagnosis=diagnosis)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=fake)

    with patch("incident_copilot.cli.build_graph", return_value=mock_graph):
        state = await _run_diagnose("crashloop", settings)

    assert state["diagnosis"] == diagnosis


async def test_run_diagnose_calls_build_graph_once() -> None:
    settings = Settings()
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    fake = _fake_state(scenario)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=fake)

    with patch("incident_copilot.cli.build_graph", return_value=mock_graph) as mock_build:
        await _run_diagnose("crashloop", settings)

    mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# _build_trajectory_table
# ---------------------------------------------------------------------------


def test_build_trajectory_table_empty() -> None:
    table = _build_trajectory_table([])
    assert isinstance(table, Table)
    assert table.row_count == 0


def test_build_trajectory_table_with_entries() -> None:
    entries = [
        _traj(0, "supervisor", "route", "log_analyst"),
        _traj(1, "log_analyst", "tool_call", "list_pods({})"),
    ]
    table = _build_trajectory_table(entries)
    assert isinstance(table, Table)
    assert table.row_count == 2


def test_build_trajectory_table_truncates_long_detail() -> None:
    long_detail = "x" * 200
    entries = [_traj(0, "log_analyst", "tool_call", long_detail)]
    table = _build_trajectory_table(entries)
    console = Console(file=io.StringIO())
    console.print(table)
    output = console.file.getvalue()
    assert "x" * 200 not in output


# ---------------------------------------------------------------------------
# _build_diagnosis_panel
# ---------------------------------------------------------------------------


def test_build_diagnosis_panel_with_text() -> None:
    diagnosis = (
        "ROOT CAUSE: database connection refused.\n"
        "EVIDENCE: logs.\nREMEDIATION: restart.\nCONFIDENCE: high"
    )
    panel = _build_diagnosis_panel(diagnosis, "crashloop")
    assert isinstance(panel, Panel)
    console = Console(file=io.StringIO())
    console.print(panel)
    output = console.file.getvalue()
    assert "ROOT CAUSE" in output


def test_build_diagnosis_panel_none_shows_fallback() -> None:
    panel = _build_diagnosis_panel(None, "crashloop")
    assert isinstance(panel, Panel)
    console = Console(file=io.StringIO())
    console.print(panel)
    output = console.file.getvalue()
    assert "No diagnosis" in output
