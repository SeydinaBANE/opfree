from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from incident_copilot.agents.state import TrajectoryEntry
from incident_copilot.config import Settings
from incident_copilot.evals.harness import run_scenario
from incident_copilot.evals.metrics import (
    RunResult,
    ScenarioEvalResult,
    ScenarioMetrics,
    compute,
    guardrail_engagement,
    loop_waste,
    reasoning_correctness,
    tool_call_accuracy,
    trajectory_consistency,
)
from incident_copilot.evals.report import write
from incident_copilot.llm.base import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolDefinition,
)
from incident_copilot.mcp_servers.client import MCPClient
from incident_copilot.scenarios import Scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

_USAGE = TokenUsage(input_tokens=10, output_tokens=10)


def _traj_tool(name: str, step: int = 0, agent: str = "log_analyst") -> TrajectoryEntry:
    return TrajectoryEntry(step=step, agent=agent, action="tool_call", detail=f"{name}({{}})")


def _traj_error(name: str, step: int = 0, agent: str = "log_analyst") -> TrajectoryEntry:
    return TrajectoryEntry(step=step, agent=agent, action="validation_error", detail=name)


def _traj_trip(step: int = 0) -> TrajectoryEntry:
    return TrajectoryEntry(
        step=step, agent="circuit_breaker", action="trip", detail="max_iterations"
    )


_DEFAULT_DIAGNOSIS = (
    "ROOT CAUSE: database connection refused.\n"
    "EVIDENCE: pod logs show connection refused.\n"
    "REMEDIATION: restart deployment.\nCONFIDENCE: high"
)


def _run(
    trajectory: list[TrajectoryEntry],
    diagnosis: str | None = _DEFAULT_DIAGNOSIS,
    tokens: int = 100,
) -> RunResult:
    return RunResult(
        scenario_name="crashloop",
        trajectory=trajectory,
        diagnosis=diagnosis,
        input_tokens=tokens,
        output_tokens=tokens,
        duration_seconds=1.0,
    )


# ---------------------------------------------------------------------------
# tool_call_accuracy
# ---------------------------------------------------------------------------


def test_tool_call_accuracy_perfect() -> None:
    acc = tool_call_accuracy(["list_pods", "get_logs"], ["list_pods", "get_logs"])
    assert acc["precision"] == 1.0
    assert acc["recall"] == 1.0
    assert acc["f1"] == 1.0


def test_tool_call_accuracy_partial() -> None:
    acc = tool_call_accuracy(["list_pods", "get_logs"], ["list_pods", "describe_pod"])
    assert acc["precision"] == pytest.approx(0.5)
    assert acc["recall"] == pytest.approx(0.5)


def test_tool_call_accuracy_empty_both() -> None:
    acc = tool_call_accuracy([], [])
    assert acc["f1"] == 1.0


def test_tool_call_accuracy_empty_actual() -> None:
    acc = tool_call_accuracy([], ["list_pods"])
    assert acc["precision"] == 0.0
    assert acc["recall"] == 0.0
    assert acc["f1"] == 0.0


def test_tool_call_accuracy_empty_gold() -> None:
    acc = tool_call_accuracy(["list_pods"], [])
    assert acc["precision"] == 0.0
    assert acc["recall"] == 0.0


# ---------------------------------------------------------------------------
# trajectory_consistency
# ---------------------------------------------------------------------------


def test_trajectory_consistency_single_run() -> None:
    assert trajectory_consistency([["list_pods", "get_logs"]]) == 1.0


def test_trajectory_consistency_identical_runs() -> None:
    seqs = [["list_pods", "get_logs"], ["list_pods", "get_logs"]]
    assert trajectory_consistency(seqs) == pytest.approx(1.0)


def test_trajectory_consistency_disjoint_runs() -> None:
    seqs = [["list_pods"], ["get_logs"]]
    assert trajectory_consistency(seqs) == pytest.approx(0.0)


def test_trajectory_consistency_partial_overlap() -> None:
    seqs = [["list_pods", "get_logs"], ["list_pods", "describe_pod"]]
    score = trajectory_consistency(seqs)
    assert 0.0 < score < 1.0


def test_trajectory_consistency_empty_sequences() -> None:
    assert trajectory_consistency([[], []]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# reasoning_correctness
# ---------------------------------------------------------------------------


def test_reasoning_correct_matching_keywords() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    diagnosis = (
        "ROOT CAUSE: database connection refused.\n"
        "EVIDENCE: logs show refused.\nREMEDIATION: restart.\nCONFIDENCE: high"
    )
    assert reasoning_correctness(diagnosis, scenario) is True


def test_reasoning_correct_none_diagnosis() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    assert reasoning_correctness(None, scenario) is False


def test_reasoning_correct_irrelevant_diagnosis() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    assert reasoning_correctness("The sky is blue and birds sing.", scenario) is False


# ---------------------------------------------------------------------------
# loop_waste
# ---------------------------------------------------------------------------


def test_loop_waste_clean_run() -> None:
    traj = [_traj_tool("list_pods"), _traj_tool("get_pod_logs")]
    waste = loop_waste(traj, ["list_pods", "get_pod_logs"])
    assert waste["redundant_calls"] == 0
    assert waste["loop_count"] == 0


def test_loop_waste_redundant_tool() -> None:
    traj = [_traj_tool("list_pods"), _traj_tool("unknown_tool")]
    waste = loop_waste(traj, ["list_pods"])
    assert waste["redundant_calls"] == 1


def test_loop_waste_with_breaker_trip() -> None:
    traj = [_traj_tool("list_pods"), _traj_trip()]
    waste = loop_waste(traj, ["list_pods"])
    assert waste["loop_count"] == 1


# ---------------------------------------------------------------------------
# guardrail_engagement
# ---------------------------------------------------------------------------


def test_guardrail_engagement_clean() -> None:
    traj = [_traj_tool("list_pods")]
    g = guardrail_engagement(traj)
    assert g["validation_errors"] == 0
    assert g["breaker_trips"] == 0


def test_guardrail_engagement_with_errors() -> None:
    traj = [_traj_tool("list_pods"), _traj_error("bad_tool"), _traj_trip()]
    g = guardrail_engagement(traj)
    assert g["validation_errors"] == 1
    assert g["breaker_trips"] == 1


# ---------------------------------------------------------------------------
# compute (aggregate)
# ---------------------------------------------------------------------------


def test_compute_produces_scenario_metrics() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    gold = [step.tool for step in scenario.gold_trajectory]
    traj = [_traj_tool(t) for t in gold]
    runs = [_run(traj)]
    metrics = compute(runs, scenario)
    assert isinstance(metrics, ScenarioMetrics)
    assert metrics.tool_f1 == pytest.approx(1.0)
    assert metrics.reasoning_correct is True


def test_compute_multi_run_averages() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    gold = [step.tool for step in scenario.gold_trajectory]
    traj_perfect = [_traj_tool(t) for t in gold]
    traj_empty: list[TrajectoryEntry] = []
    runs = [_run(traj_perfect, tokens=200), _run(traj_empty, diagnosis=None, tokens=100)]
    metrics = compute(runs, scenario)
    assert 0.0 < metrics.tool_f1 < 1.0
    assert metrics.avg_tokens == 300


# ---------------------------------------------------------------------------
# report.write
# ---------------------------------------------------------------------------


def test_report_creates_both_files(tmp_path: Path) -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    traj = [_traj_tool("list_pods")]
    runs = [_run(traj)]
    metrics = compute(runs, scenario)
    result = ScenarioEvalResult(scenario_name="crashloop", n_runs=1, runs=runs, metrics=metrics)
    md, js = write([result], reports_dir=tmp_path)
    assert md.exists()
    assert js.exists()
    assert md.suffix == ".md"
    assert js.suffix == ".json"


def test_report_markdown_contains_scenario(tmp_path: Path) -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    traj = [_traj_tool("list_pods")]
    runs = [_run(traj)]
    metrics = compute(runs, scenario)
    result = ScenarioEvalResult(scenario_name="crashloop", n_runs=1, runs=runs, metrics=metrics)
    md, _ = write([result], reports_dir=tmp_path)
    content = md.read_text()
    assert "crashloop" in content
    assert "## Summary" in content
    assert "Tool F1" in content


def test_report_json_is_valid_and_structured(tmp_path: Path) -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    traj = [_traj_tool("list_pods")]
    runs = [_run(traj)]
    metrics = compute(runs, scenario)
    result = ScenarioEvalResult(scenario_name="crashloop", n_runs=1, runs=runs, metrics=metrics)
    _, js = write([result], reports_dir=tmp_path)
    data = json.loads(js.read_text())
    assert isinstance(data, list)
    assert data[0]["scenario_name"] == "crashloop"
    assert "metrics" in data[0]
    assert "runs" in data[0]


# ---------------------------------------------------------------------------
# harness integration (scripted LLM + fake MCP)
# ---------------------------------------------------------------------------


class _ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._iter = iter(responses)

    @property
    def model(self) -> str:
        return "scripted"

    def complete(
        self,
        *,
        messages: list[Message],  # noqa: ARG002
        system: str,  # noqa: ARG002
        max_tokens: int = 1024,  # noqa: ARG002
    ) -> LLMResponse:
        return next(self._iter)

    def tool_use(
        self,
        *,
        messages: list[Message],  # noqa: ARG002
        system: str,  # noqa: ARG002
        tools: list[ToolDefinition],  # noqa: ARG002
        max_tokens: int = 4096,  # noqa: ARG002
    ) -> LLMResponse:
        return next(self._iter)


async def test_harness_run_scenario_returns_run_results() -> None:
    llm = _ScriptedLLM(
        [
            LLMResponse(content="log_analyst", stop_reason="end_turn", usage=_USAGE),
            LLMResponse(content="No tool calls needed.", stop_reason="end_turn", usage=_USAGE),
            LLMResponse(content="synthesize", stop_reason="end_turn", usage=_USAGE),
            LLMResponse(
                content=(
                    "ROOT CAUSE: DB unreachable.\n"
                    "EVIDENCE: connection refused.\n"
                    "REMEDIATION: restart pod.\n"
                    "CONFIDENCE: high"
                ),
                stop_reason="end_turn",
                usage=_USAGE,
            ),
        ]
    )

    k8s_mcp = AsyncMock(spec=MCPClient)
    k8s_mcp.list_tools.return_value = []
    prom_mcp = AsyncMock(spec=MCPClient)
    prom_mcp.list_tools.return_value = []
    runbook_mcp = AsyncMock(spec=MCPClient)
    runbook_mcp.list_tools.return_value = []

    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    settings = Settings()

    results = await run_scenario(
        scenario,
        llm,
        settings,
        n_runs=1,
        k8s_client=k8s_mcp,
        prom_client=prom_mcp,
        runbook_client=runbook_mcp,
    )

    assert len(results) == 1
    result = results[0]
    assert result.scenario_name == "crashloop"
    assert result.diagnosis is not None
    assert "ROOT CAUSE" in result.diagnosis
    assert result.duration_seconds >= 0
