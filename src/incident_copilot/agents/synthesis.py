from __future__ import annotations

from collections.abc import Callable

from incident_copilot.agents.state import GraphState
from incident_copilot.llm.base import LLMProvider, UserMessage

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
        return {
            "diagnosis": response.content,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    return node
