from __future__ import annotations

import re
from dataclasses import dataclass

from incident_copilot.agents.state import TrajectoryEntry
from incident_copilot.scenarios import Scenario


@dataclass(frozen=True)
class RunResult:
    scenario_name: str
    trajectory: list[TrajectoryEntry]
    diagnosis: str | None
    input_tokens: int
    output_tokens: int
    duration_seconds: float


@dataclass(frozen=True)
class ScenarioMetrics:
    tool_precision: float
    tool_recall: float
    tool_f1: float
    trajectory_consistency: float
    reasoning_correct: bool
    redundant_calls: int
    loop_count: int
    validation_errors: int
    breaker_trips: int
    avg_tokens: int
    avg_duration_seconds: float


@dataclass(frozen=True)
class ScenarioEvalResult:
    scenario_name: str
    n_runs: int
    runs: list[RunResult]
    metrics: ScenarioMetrics


def tool_call_accuracy(actual_tools: list[str], gold_tools: list[str]) -> dict[str, float]:
    actual_set = set(actual_tools)
    gold_set = set(gold_tools)
    if not actual_set and not gold_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(actual_set & gold_set)
    precision = tp / len(actual_set) if actual_set else 0.0
    recall = tp / len(gold_set) if gold_set else 0.0
    denom = precision + recall
    f1 = (2 * precision * recall / denom) if denom > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def trajectory_consistency(tool_sequences: list[list[str]]) -> float:
    if len(tool_sequences) <= 1:
        return 1.0
    scores: list[float] = []
    for i in range(len(tool_sequences)):
        for j in range(i + 1, len(tool_sequences)):
            sa, sb = set(tool_sequences[i]), set(tool_sequences[j])
            union = sa | sb
            scores.append(len(sa & sb) / len(union) if union else 1.0)
    return sum(scores) / len(scores)


_MIN_KEYWORD_LEN = 5
_MIN_KEYWORD_MATCHES = 2
_MAJORITY_THRESHOLD = 0.5


def reasoning_correctness(diagnosis: str | None, scenario: Scenario) -> bool:
    if diagnosis is None:
        return False
    root_cause_text = " ".join(rb.root_cause for rb in scenario.runbooks)
    keywords = {
        w.lower() for w in re.findall(r"\w+", root_cause_text) if len(w) >= _MIN_KEYWORD_LEN
    }
    diag_lower = diagnosis.lower()
    return sum(1 for kw in keywords if kw in diag_lower) >= _MIN_KEYWORD_MATCHES


def loop_waste(trajectory: list[TrajectoryEntry], gold_tools: list[str]) -> dict[str, int]:
    gold_set = set(gold_tools)
    actual_tools = _extract_tools(trajectory)
    redundant = sum(1 for t in actual_tools if t not in gold_set)
    loops = sum(1 for e in trajectory if e["agent"] == "circuit_breaker" and e["action"] == "trip")
    return {"redundant_calls": redundant, "loop_count": loops}


def guardrail_engagement(trajectory: list[TrajectoryEntry]) -> dict[str, int]:
    val_errors = sum(1 for e in trajectory if e["action"] == "validation_error")
    trips = sum(1 for e in trajectory if e["agent"] == "circuit_breaker" and e["action"] == "trip")
    return {"validation_errors": val_errors, "breaker_trips": trips}


def compute(runs: list[RunResult], scenario: Scenario) -> ScenarioMetrics:
    gold_tools = [step.tool for step in scenario.gold_trajectory]
    tool_seqs = [_extract_tools(r.trajectory) for r in runs]
    n = len(runs)

    acc_scores = [tool_call_accuracy(seq, gold_tools) for seq in tool_seqs]
    avg_precision = sum(s["precision"] for s in acc_scores) / n
    avg_recall = sum(s["recall"] for s in acc_scores) / n
    avg_f1 = sum(s["f1"] for s in acc_scores) / n

    consistency = trajectory_consistency(tool_seqs)

    correct_count = sum(1 for r in runs if reasoning_correctness(r.diagnosis, scenario))
    is_correct = correct_count / n >= _MAJORITY_THRESHOLD

    waste_data = [loop_waste(r.trajectory, gold_tools) for r in runs]
    guard_data = [guardrail_engagement(r.trajectory) for r in runs]

    avg_tokens = int(sum(r.input_tokens + r.output_tokens for r in runs) / n)
    avg_duration = sum(r.duration_seconds for r in runs) / n

    return ScenarioMetrics(
        tool_precision=round(avg_precision, 3),
        tool_recall=round(avg_recall, 3),
        tool_f1=round(avg_f1, 3),
        trajectory_consistency=round(consistency, 3),
        reasoning_correct=is_correct,
        redundant_calls=sum(w["redundant_calls"] for w in waste_data),
        loop_count=sum(w["loop_count"] for w in waste_data),
        validation_errors=sum(g["validation_errors"] for g in guard_data),
        breaker_trips=sum(g["breaker_trips"] for g in guard_data),
        avg_tokens=avg_tokens,
        avg_duration_seconds=round(avg_duration, 2),
    )


def _extract_tools(trajectory: list[TrajectoryEntry]) -> list[str]:
    return [e["detail"].split("(")[0] for e in trajectory if e["action"] == "tool_call"]
