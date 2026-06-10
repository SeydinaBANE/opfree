from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import structlog

from incident_copilot.agents.state import GraphState, TrajectoryEntry
from incident_copilot.config import Settings

log = structlog.get_logger()

TripReason = Literal["max_iterations", "token_budget", "timeout", "repeated_route"]

_REPEATED_ROUTE_WINDOW = 3


@dataclass(frozen=True)
class BreakerTrip:
    reason: TripReason
    detail: str


def check(state: GraphState, settings: Settings) -> BreakerTrip | None:
    if state["iteration_count"] >= settings.max_agent_iterations:
        return BreakerTrip(
            reason="max_iterations",
            detail=(
                f"iteration_count={state['iteration_count']} >= {settings.max_agent_iterations}"
            ),
        )

    total_tokens = state["input_tokens"] + state["output_tokens"]
    if total_tokens >= settings.max_total_tokens:
        return BreakerTrip(
            reason="token_budget",
            detail=f"total_tokens={total_tokens} >= {settings.max_total_tokens}",
        )

    elapsed = time.monotonic() - state["start_time"]
    if elapsed >= settings.agent_timeout_seconds:
        return BreakerTrip(
            reason="timeout",
            detail=f"elapsed={elapsed:.1f}s >= {settings.agent_timeout_seconds}s",
        )

    if _repeated_route(state):
        return BreakerTrip(
            reason="repeated_route",
            detail=f"same route issued {_REPEATED_ROUTE_WINDOW} times consecutively",
        )

    return None


def _repeated_route(state: GraphState) -> bool:
    routes = [
        e["detail"]
        for e in state["trajectory"]
        if e["agent"] == "supervisor" and e["action"] == "route"
    ]
    if len(routes) < _REPEATED_ROUTE_WINDOW:
        return False
    return len(set(routes[-_REPEATED_ROUTE_WINDOW:])) == 1


def make_trip_entry(step: int, trip: BreakerTrip) -> TrajectoryEntry:
    return TrajectoryEntry(
        step=step,
        agent="circuit_breaker",
        action="trip",
        detail=f"{trip.reason}: {trip.detail}",
    )
