from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import structlog

from incident_copilot.agents.state import Finding, GraphState, TrajectoryEntry
from incident_copilot.llm.base import (
    AssistantMessage,
    LLMProvider,
    Message,
    ToolResultMessage,
    UserMessage,
)
from incident_copilot.mcp_servers.client import MCPClient, connect_to_server

log = structlog.get_logger()

_NodeFn = Callable[[GraphState], Coroutine[Any, Any, dict[str, object]]]

LOG_ANALYST_SYSTEM = """\
You are a Log Analyst for an SRE incident diagnosis system.
Investigate the incident using the available Kubernetes tools.
Use list_pods to find affected pods, describe_pod for details, get_pod_logs for crash
evidence, and get_events for cluster events. After gathering evidence, respond with a
concise summary of your findings focused on error messages and crash patterns.\
"""

METRICS_ANALYST_SYSTEM = """\
You are a Metrics Analyst for an SRE incident diagnosis system.
Investigate using Prometheus tools. Use get_alerts to see firing alerts, query_range to
inspect suspicious metrics over time, and get_targets to check endpoint health.
After gathering evidence, respond with a concise summary focused on anomalies and
threshold breaches.\
"""

RUNBOOK_EXECUTOR_SYSTEM = """\
You are a Runbook Executor for an SRE incident diagnosis system.
Based on the incident description and findings, find and retrieve the relevant runbook.
Use list_runbooks to see what is available, get_runbook to retrieve by alert trigger,
and list_runbook_steps for the remediation steps.
After gathering evidence, respond with the recommended remediation steps.\
"""


async def _run_tool_loop(
    state: GraphState,
    llm: LLMProvider,
    client: MCPClient,
    agent_name: str,
    system_prompt: str,
) -> dict[str, object]:
    tools = await client.list_tools()
    messages: list[Message] = [
        UserMessage(content=f"Investigate this incident:\n{state['scenario'].description}")
    ]
    total_input = 0
    total_output = 0
    trajectory: list[TrajectoryEntry] = []
    base_step = len(state["trajectory"])
    last_response_content: str | None = None

    while True:
        response = llm.tool_use(messages=messages, system=system_prompt, tools=tools)
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens
        last_response_content = response.content

        if not response.has_tool_calls:
            break

        messages.append(AssistantMessage(content=response.content, tool_calls=response.tool_calls))
        tool_results: list[Message] = []
        for tc in response.tool_calls:
            trajectory.append(
                TrajectoryEntry(
                    step=base_step + len(trajectory),
                    agent=agent_name,
                    action="tool_call",
                    detail=f"{tc.name}({json.dumps(tc.input)})",
                )
            )
            log.debug("tool_call", agent=agent_name, tool=tc.name, args=tc.input)
            result = await client.call_tool(tc.name, tc.input)
            tool_results.append(ToolResultMessage(tool_call_id=tc.id, content=result))
        messages.extend(tool_results)

    findings: list[Finding] = []
    if last_response_content:
        findings.append(
            Finding(
                agent=agent_name,
                source=agent_name,
                observation=last_response_content,
                severity="medium",
                supports_hypothesis=True,
            )
        )

    return {
        "findings": findings,
        "trajectory": trajectory,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "iteration_count": 1,
    }


def _scenario_path(name: str) -> str:
    return str(Path("scenarios") / f"{name}.json")


def make_log_analyst_node(
    llm: LLMProvider,
    mcp_client: MCPClient | None = None,
) -> _NodeFn:
    async def node(state: GraphState) -> dict[str, object]:
        if mcp_client is not None:
            return await _run_tool_loop(state, llm, mcp_client, "log_analyst", LOG_ANALYST_SYSTEM)
        path = _scenario_path(state["scenario"].name)
        async with connect_to_server(
            "uv",
            ["run", "python", "-m", "incident_copilot.mcp_servers.k8s_mock", "--scenario", path],
        ) as client:
            return await _run_tool_loop(state, llm, client, "log_analyst", LOG_ANALYST_SYSTEM)

    return node


def make_metrics_analyst_node(
    llm: LLMProvider,
    mcp_client: MCPClient | None = None,
) -> _NodeFn:
    async def node(state: GraphState) -> dict[str, object]:
        if mcp_client is not None:
            return await _run_tool_loop(
                state, llm, mcp_client, "metrics_analyst", METRICS_ANALYST_SYSTEM
            )
        path = _scenario_path(state["scenario"].name)
        async with connect_to_server(
            "uv",
            [
                "run",
                "python",
                "-m",
                "incident_copilot.mcp_servers.prometheus_mock",
                "--scenario",
                path,
            ],
        ) as client:
            return await _run_tool_loop(
                state, llm, client, "metrics_analyst", METRICS_ANALYST_SYSTEM
            )

    return node


def make_runbook_executor_node(
    llm: LLMProvider,
    mcp_client: MCPClient | None = None,
) -> _NodeFn:
    async def node(state: GraphState) -> dict[str, object]:
        if mcp_client is not None:
            return await _run_tool_loop(
                state, llm, mcp_client, "runbook_executor", RUNBOOK_EXECUTOR_SYSTEM
            )
        path = _scenario_path(state["scenario"].name)
        async with connect_to_server(
            "uv",
            [
                "run",
                "python",
                "-m",
                "incident_copilot.mcp_servers.runbook_mock",
                "--scenario",
                path,
            ],
        ) as client:
            return await _run_tool_loop(
                state, llm, client, "runbook_executor", RUNBOOK_EXECUTOR_SYSTEM
            )

    return node
