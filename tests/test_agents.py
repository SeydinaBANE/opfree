from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.specialists import (
    make_log_analyst_node,
    make_metrics_analyst_node,
    make_runbook_executor_node,
)
from incident_copilot.agents.state import Finding, GraphState, TrajectoryEntry
from incident_copilot.agents.supervisor import (
    _agents_consulted,
    _parse_routing,
    make_supervisor_node,
    route_supervisor,
)
from incident_copilot.agents.synthesis import make_synthesis_node
from incident_copilot.llm.base import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from incident_copilot.mcp_servers.client import MCPClient
from incident_copilot.scenarios import Scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _usage(inp: int = 10, out: int = 10) -> TokenUsage:
    return TokenUsage(input_tokens=inp, output_tokens=out)


def _text_response(text: str) -> LLMResponse:
    return LLMResponse(content=text, stop_reason="end_turn", usage=_usage())


def _tool_response(
    tool_name: str, tool_id: str = "tc_1", args: dict[str, object] | None = None
) -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id=tool_id, name=tool_name, input=args or {})],
        stop_reason="tool_use",
        usage=_usage(),
    )


class ScriptedLLM:
    """Returns pre-programmed LLMResponse objects in order."""

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


def _fake_mcp(tools: list[str], tool_result: str = "result") -> MCPClient:
    client = AsyncMock(spec=MCPClient)
    client.list_tools.return_value = [
        ToolDefinition(name=t, description=t, input_schema={}) for t in tools
    ]
    client.call_tool.return_value = tool_result
    return client


def _empty_state(scenario: Scenario) -> GraphState:
    return GraphState(
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


@pytest.fixture()
def crashloop() -> Scenario:
    return Scenario.load(SCENARIOS_DIR / "crashloop.json")


# ---------------------------------------------------------------------------
# Supervisor unit tests
# ---------------------------------------------------------------------------


def test_parse_routing_recognises_all_routes() -> None:
    assert _parse_routing("log_analyst") == "log_analyst"
    assert _parse_routing("metrics_analyst") == "metrics_analyst"
    assert _parse_routing("runbook_executor") == "runbook_executor"
    assert _parse_routing("synthesize") == "synthesize"


def test_parse_routing_defaults_to_synthesize_on_garbage() -> None:
    assert _parse_routing("unknown gibberish") == "synthesize"


def test_parse_routing_case_insensitive() -> None:
    assert _parse_routing("LOG_ANALYST") == "log_analyst"


def test_agents_consulted_empty_trajectory(crashloop: Scenario) -> None:
    state = _empty_state(crashloop)
    assert _agents_consulted(state) == set()


def test_agents_consulted_excludes_supervisor(crashloop: Scenario) -> None:
    state = _empty_state(crashloop)
    state["trajectory"] = [
        TrajectoryEntry(step=0, agent="supervisor", action="route", detail="→ log_analyst"),
        TrajectoryEntry(step=1, agent="log_analyst", action="tool_call", detail="list_pods"),
    ]
    assert _agents_consulted(state) == {"log_analyst"}


def test_supervisor_node_routes_to_log_analyst(crashloop: Scenario) -> None:
    llm = ScriptedLLM([_text_response("log_analyst")])
    node = make_supervisor_node(llm)
    state = _empty_state(crashloop)

    result = node(state)

    assert result["next_agent"] == "log_analyst"
    trajectory = result["trajectory"]
    assert isinstance(trajectory, list) and len(trajectory) == 1
    assert trajectory[0]["agent"] == "supervisor"


def test_supervisor_node_routes_to_synthesize(crashloop: Scenario) -> None:
    llm = ScriptedLLM([_text_response("synthesize")])
    node = make_supervisor_node(llm)
    state = _empty_state(crashloop)

    result = node(state)

    assert result["next_agent"] == "synthesize"


def test_route_supervisor_returns_next_agent(crashloop: Scenario) -> None:
    state = _empty_state(crashloop)
    state["next_agent"] = "metrics_analyst"
    assert route_supervisor(state) == "metrics_analyst"


# ---------------------------------------------------------------------------
# Specialist unit tests
# ---------------------------------------------------------------------------


async def test_log_analyst_calls_tools_and_returns_finding(crashloop: Scenario) -> None:
    llm = ScriptedLLM(
        [
            _tool_response("list_pods", args={}),
            _text_response("Payment service is crash-looping due to DB connection refusal."),
        ]
    )
    mcp = _fake_mcp(["list_pods", "get_pod_logs"])
    node = make_log_analyst_node(llm, mcp_client=mcp)

    result = await node(_empty_state(crashloop))

    findings: list[Finding] = result["findings"]  # type: ignore[assignment]
    assert len(findings) == 1
    assert findings[0]["agent"] == "log_analyst"
    assert "crash" in findings[0]["observation"].lower()

    trajectory: list[TrajectoryEntry] = result["trajectory"]  # type: ignore[assignment]
    assert any(e["action"] == "tool_call" for e in trajectory)
    mcp.call_tool.assert_awaited_once()


async def test_log_analyst_no_tool_calls_yields_finding_from_text(
    crashloop: Scenario,
) -> None:
    llm = ScriptedLLM([_text_response("No issues found in logs.")])
    mcp = _fake_mcp(["list_pods"])
    node = make_log_analyst_node(llm, mcp_client=mcp)

    result = await node(_empty_state(crashloop))

    assert len(result["findings"]) == 1  # type: ignore[arg-type]
    assert result["trajectory"] == []  # type: ignore[comparison-overlap]


async def test_metrics_analyst_calls_tools_and_returns_finding(crashloop: Scenario) -> None:
    llm = ScriptedLLM(
        [
            _tool_response("get_alerts", args={}),
            _text_response("KubePodCrashLooping alert is firing."),
        ]
    )
    mcp = _fake_mcp(["get_alerts", "query_range"])
    node = make_metrics_analyst_node(llm, mcp_client=mcp)

    result = await node(_empty_state(crashloop))

    findings: list[Finding] = result["findings"]  # type: ignore[assignment]
    assert findings[0]["agent"] == "metrics_analyst"


async def test_runbook_executor_calls_tools_and_returns_finding(crashloop: Scenario) -> None:
    llm = ScriptedLLM(
        [
            _tool_response("get_runbook", args={"trigger": "KubePodCrashLooping"}),
            _text_response("Run: check DB connectivity then restart the pod."),
        ]
    )
    mcp = _fake_mcp(["get_runbook", "list_runbook_steps"])
    node = make_runbook_executor_node(llm, mcp_client=mcp)

    result = await node(_empty_state(crashloop))

    findings: list[Finding] = result["findings"]  # type: ignore[assignment]
    assert findings[0]["agent"] == "runbook_executor"


async def test_specialist_accumulates_token_counts(crashloop: Scenario) -> None:
    llm = ScriptedLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="t1", name="list_pods", input={})],
                stop_reason="tool_use",
                usage=TokenUsage(input_tokens=100, output_tokens=50),
            ),
            LLMResponse(
                content="All good.",
                tool_calls=[],
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=200, output_tokens=30),
            ),
        ]
    )
    mcp = _fake_mcp(["list_pods"])
    node = make_log_analyst_node(llm, mcp_client=mcp)

    result = await node(_empty_state(crashloop))

    assert result["input_tokens"] == 300
    assert result["output_tokens"] == 80


# ---------------------------------------------------------------------------
# Synthesis unit tests
# ---------------------------------------------------------------------------


def test_synthesis_produces_diagnosis(crashloop: Scenario) -> None:
    llm = ScriptedLLM([_text_response("ROOT CAUSE: DB unreachable. REMEDIATION: Restart pod.")])
    node = make_synthesis_node(llm)
    state = _empty_state(crashloop)
    state["findings"] = [
        Finding(
            agent="log_analyst",
            source="log_analyst",
            observation="connection refused to postgres",
            severity="high",
            supports_hypothesis=True,
        )
    ]

    result = node(state)

    assert "ROOT CAUSE" in (result["diagnosis"] or "")


def test_synthesis_empty_findings(crashloop: Scenario) -> None:
    llm = ScriptedLLM([_text_response("No findings available.")])

    result = make_synthesis_node(llm)(_empty_state(crashloop))

    assert result["diagnosis"] is not None


# ---------------------------------------------------------------------------
# Full graph integration test
# ---------------------------------------------------------------------------


async def test_full_graph_crashloop(crashloop: Scenario) -> None:
    # Script: supervisor → log_analyst → supervisor → metrics_analyst →
    #         supervisor → synthesize
    llm = ScriptedLLM(
        [
            # supervisor call 1: route to log_analyst
            _text_response("log_analyst"),
            # log_analyst: one tool call + final answer
            _tool_response("list_pods"),
            _text_response("Payment service is crash-looping: DB connection refused."),
            # supervisor call 2: route to metrics_analyst
            _text_response("metrics_analyst"),
            # metrics_analyst: one tool call + final answer
            _tool_response("get_alerts"),
            _text_response("KubePodCrashLooping alert firing since 10:00."),
            # supervisor call 3: enough evidence → synthesize
            _text_response("synthesize"),
            # synthesis
            _text_response(
                "ROOT CAUSE: DB unreachable.\n"
                "EVIDENCE: connection refused in logs + crash alert.\n"
                "REMEDIATION: verify DB service, check NetworkPolicy, restart pod.\n"
                "CONFIDENCE: high"
            ),
        ]
    )

    k8s_mcp = _fake_mcp(["list_pods", "get_pod_logs"])
    prom_mcp = _fake_mcp(["get_alerts", "query_range"])
    runbook_mcp = _fake_mcp(["get_runbook", "list_runbook_steps"])

    graph = build_graph(
        llm,
        k8s_client=k8s_mcp,
        prom_client=prom_mcp,
        runbook_client=runbook_mcp,
    )

    thread_id = str(uuid.uuid4())
    initial: GraphState = _empty_state(crashloop)

    result: dict[str, Any] = await graph.ainvoke(
        initial, config={"configurable": {"thread_id": thread_id}}
    )

    assert result["diagnosis"] is not None
    assert "ROOT CAUSE" in result["diagnosis"]
    assert len(result["findings"]) == 2
    assert result["input_tokens"] > 0

    agents_in_trajectory = {e["agent"] for e in result["trajectory"]}
    assert "log_analyst" in agents_in_trajectory
    assert "metrics_analyst" in agents_in_trajectory
