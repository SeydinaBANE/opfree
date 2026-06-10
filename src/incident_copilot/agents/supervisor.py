from __future__ import annotations

from collections.abc import Callable

from incident_copilot.agents.state import GraphState, TrajectoryEntry
from incident_copilot.llm.base import LLMProvider, UserMessage

SUPERVISOR_SYSTEM = """\
You are the supervisor of a multi-agent SRE incident diagnosis system.
Your role is to decide which specialist to engage next based on current findings.

Specialists:
- log_analyst: investigates pod/container logs and Kubernetes events
- metrics_analyst: investigates time-series metrics and alerts
- runbook_executor: retrieves matching runbooks and remediation steps

Rules:
1. Route to each specialist at most once.
2. Once at least 2 specialists have reported, you may route to "synthesize".
3. If all 3 have reported, always route to "synthesize".

Respond with ONLY one word: log_analyst, metrics_analyst, runbook_executor, or synthesize.\
"""

_VALID_ROUTES = frozenset({"log_analyst", "metrics_analyst", "runbook_executor", "synthesize"})


def _agents_consulted(state: GraphState) -> set[str]:
    return {e["agent"] for e in state["trajectory"] if e["agent"] != "supervisor"}


def _parse_routing(text: str) -> str:
    lower = text.lower()
    for route in ("log_analyst", "metrics_analyst", "runbook_executor", "synthesize"):
        if route in lower:
            return route
    return "synthesize"


def _build_prompt(state: GraphState) -> str:
    consulted = _agents_consulted(state)
    lines = [f"Incident: {state['scenario'].description}"]
    if consulted:
        lines.append(f"Already consulted: {', '.join(sorted(consulted))}")
        lines.append(f"Findings collected: {len(state['findings'])}")
    else:
        lines.append("No specialists consulted yet.")
    lines.append("Which specialist should investigate next?")
    return "\n".join(lines)


def make_supervisor_node(llm: LLMProvider) -> Callable[[GraphState], dict[str, object]]:
    def node(state: GraphState) -> dict[str, object]:
        response = llm.complete(
            messages=[UserMessage(content=_build_prompt(state))],
            system=SUPERVISOR_SYSTEM,
            max_tokens=64,
        )
        next_agent = _parse_routing(response.content or "")
        step = len(state["trajectory"])
        return {
            "next_agent": next_agent,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "trajectory": [
                TrajectoryEntry(
                    step=step,
                    agent="supervisor",
                    action="route",
                    detail=f"→ {next_agent}",
                )
            ],
        }

    return node


def route_supervisor(state: GraphState) -> str:
    return state["next_agent"]
