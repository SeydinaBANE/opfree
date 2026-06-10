from __future__ import annotations

from collections.abc import Callable

import structlog

from incident_copilot.agents.state import GraphState, TrajectoryEntry
from incident_copilot.guardrails import sanitizer
from incident_copilot.llm.base import LLMProvider, UserMessage

log = structlog.get_logger()

SYNTHESIS_SYSTEM = """\
You are a Synthesis Engine for an SRE incident diagnosis system.
You receive findings from specialist agents and produce a final diagnosis.

Structure your response as:
ROOT CAUSE: <one sentence>
EVIDENCE: <key observations that confirm the root cause>
REMEDIATION: <ordered steps to resolve the incident>
CONFIDENCE: <high | medium | low>\
"""


def make_synthesis_node(llm: LLMProvider) -> Callable[[GraphState], dict[str, object]]:
    def node(state: GraphState) -> dict[str, object]:
        findings_text = "\n".join(f"[{f['agent']}] {f['observation']}" for f in state["findings"])
        response = llm.complete(
            messages=[
                UserMessage(
                    content=(
                        f"Incident: {state['scenario'].description}\n\nFindings:\n{findings_text}"
                    )
                )
            ],
            system=SYNTHESIS_SYSTEM,
            max_tokens=512,
        )
        raw = response.content or ""
        sanitized, hits = sanitizer.sanitize_text(raw)
        missing_fields = sanitizer.validate_synthesis(sanitized)

        extra_trajectory: list[TrajectoryEntry] = []
        step = len(state["trajectory"])
        if hits:
            extra_trajectory.append(
                TrajectoryEntry(
                    step=step,
                    agent="sanitizer",
                    action="sanitized",
                    detail=f"hits={hits}",
                )
            )
        if missing_fields:
            log.warning("synthesis_incomplete", missing=missing_fields)
            extra_trajectory.append(
                TrajectoryEntry(
                    step=step + len(extra_trajectory),
                    agent="sanitizer",
                    action="incomplete_synthesis",
                    detail=f"missing={missing_fields}",
                )
            )

        result: dict[str, object] = {
            "diagnosis": sanitized,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        if extra_trajectory:
            result["trajectory"] = extra_trajectory
        return result

    return node
