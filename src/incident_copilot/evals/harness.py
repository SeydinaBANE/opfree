from __future__ import annotations

import time
import uuid
from typing import cast

import structlog

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import GraphState
from incident_copilot.config import Settings
from incident_copilot.evals.metrics import (
    RunResult,
    ScenarioEvalResult,
    compute,
)
from incident_copilot.llm.base import LLMProvider
from incident_copilot.mcp_servers.client import MCPClient
from incident_copilot.scenarios import Scenario

log = structlog.get_logger()


async def run_scenario(
    scenario: Scenario,
    llm: LLMProvider,
    settings: Settings,
    *,
    n_runs: int = 1,
    k8s_client: MCPClient | None = None,
    prom_client: MCPClient | None = None,
    runbook_client: MCPClient | None = None,
) -> list[RunResult]:
    results: list[RunResult] = []
    for run_idx in range(n_runs):
        log.info("eval_run_start", scenario=scenario.name, run=run_idx + 1, total=n_runs)
        result = await _single_run(scenario, llm, settings, k8s_client, prom_client, runbook_client)
        results.append(result)
        log.info(
            "eval_run_done",
            scenario=scenario.name,
            run=run_idx + 1,
            duration=result.duration_seconds,
        )
    return results


async def run_all(
    scenarios: list[Scenario],
    llm: LLMProvider,
    settings: Settings,
    *,
    n_runs: int = 1,
) -> list[ScenarioEvalResult]:
    eval_results: list[ScenarioEvalResult] = []
    for scenario in scenarios:
        runs = await run_scenario(scenario, llm, settings, n_runs=n_runs)
        metrics = compute(runs, scenario)
        eval_results.append(
            ScenarioEvalResult(
                scenario_name=scenario.name,
                n_runs=n_runs,
                runs=runs,
                metrics=metrics,
            )
        )
    return eval_results


async def _single_run(
    scenario: Scenario,
    llm: LLMProvider,
    settings: Settings,
    k8s_client: MCPClient | None,
    prom_client: MCPClient | None,
    runbook_client: MCPClient | None,
) -> RunResult:
    graph = build_graph(
        llm,
        settings=settings,
        k8s_client=k8s_client,
        prom_client=prom_client,
        runbook_client=runbook_client,
    )
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
    start = time.monotonic()
    # LangGraph return type erased via type: ignore[type-arg] on CompiledStateGraph; cast is safe.
    raw = await graph.ainvoke(
        initial,
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )
    duration = time.monotonic() - start
    state = cast(GraphState, raw)
    return RunResult(
        scenario_name=scenario.name,
        trajectory=list(state["trajectory"]),
        diagnosis=state["diagnosis"],
        input_tokens=state["input_tokens"],
        output_tokens=state["output_tokens"],
        duration_seconds=round(duration, 2),
    )
