from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from incident_copilot.scenarios import Scenario


class Finding(TypedDict):
    agent: str
    source: str
    observation: str
    severity: str
    supports_hypothesis: bool


class TrajectoryEntry(TypedDict):
    step: int
    agent: str
    action: str
    detail: str


class GraphState(TypedDict):
    scenario: Scenario
    findings: Annotated[list[Finding], operator.add]
    trajectory: Annotated[list[TrajectoryEntry], operator.add]
    input_tokens: Annotated[int, operator.add]
    output_tokens: Annotated[int, operator.add]
    iteration_count: Annotated[int, operator.add]
    next_agent: str
    diagnosis: str | None
