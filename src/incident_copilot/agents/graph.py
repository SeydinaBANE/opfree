from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.specialists import (
    make_log_analyst_node,
    make_metrics_analyst_node,
    make_runbook_executor_node,
)
from incident_copilot.agents.state import GraphState
from incident_copilot.agents.supervisor import make_supervisor_node, route_supervisor
from incident_copilot.agents.synthesis import make_synthesis_node
from incident_copilot.config import Settings
from incident_copilot.llm.base import LLMProvider
from incident_copilot.mcp_servers.client import MCPClient


def build_graph(
    llm: LLMProvider,
    *,
    settings: Settings | None = None,
    k8s_client: MCPClient | None = None,
    prom_client: MCPClient | None = None,
    runbook_client: MCPClient | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    builder: StateGraph[GraphState, None, GraphState, GraphState] = StateGraph(GraphState)

    # LangGraph overloads don't resolve dict[str, object] node returns; runtime is correct.
    builder.add_node("supervisor", make_supervisor_node(llm, settings))  # type: ignore[call-overload]
    builder.add_node("log_analyst", make_log_analyst_node(llm, k8s_client))  # type: ignore[call-overload]
    builder.add_node("metrics_analyst", make_metrics_analyst_node(llm, prom_client))  # type: ignore[call-overload]
    builder.add_node("runbook_executor", make_runbook_executor_node(llm, runbook_client))  # type: ignore[call-overload]
    builder.add_node("synthesis", make_synthesis_node(llm))  # type: ignore[call-overload]

    builder.set_entry_point("supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "log_analyst": "log_analyst",
            "metrics_analyst": "metrics_analyst",
            "runbook_executor": "runbook_executor",
            "synthesize": "synthesis",
        },
    )
    builder.add_edge("log_analyst", "supervisor")
    builder.add_edge("metrics_analyst", "supervisor")
    builder.add_edge("runbook_executor", "supervisor")
    builder.add_edge("synthesis", END)

    return builder.compile(checkpointer=MemorySaver())
