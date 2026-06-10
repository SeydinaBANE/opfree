# Agentic evaluation

The eval harness treats the agent system as a unit under test: it replays scenarios, captures full trajectories, and scores them against gold references. Run with `make evals`.

## Gold trajectories

Each scenario JSON embeds a `gold_trajectory`: the expected sequence of routing decisions and tool calls (with acceptable variations) plus the expected root cause. Gold trajectories are the contract for "the agent reasons correctly", not just "the answer string matches".

## Metrics (`evals/metrics.py`)

| Metric | Question it answers |
|---|---|
| Tool-call accuracy | Did the agent call the right tools with valid, relevant arguments? (precision/recall vs gold tool set) |
| Trajectory consistency | Across N replays of the same scenario, how stable is the routing path? (normalized edit distance between trajectories) |
| Reasoning correctness | Does the final root cause match the scenario's ground truth? |
| Loop & waste score | Redundant tool calls, repeated routes, tokens spent past the point of sufficient evidence |
| Guardrail engagement | Hallucinated tool calls emitted, breaker trips (should be 0 on nominal scenarios) |

## Harness (`evals/harness.py`)

- Replays each scenario N times (default 3) with the real provider, or with a scripted provider for deterministic CI runs.
- Captures the trajectory recorded in the graph state — the same data structure the guardrails write to.
- Aggregates per-scenario and global scores.

## Report (`evals/report.py`)

Outputs `reports/evals-<timestamp>.md` (human review) and `.json` (machine baseline). The markdown report includes per-scenario score tables and the worst trajectory diff for inspection.

## Regression policy

A change that drops tool-call accuracy or reasoning correctness below the last committed baseline must not be merged. Prompt changes always require a fresh eval run (see docs/agents.md).
