# Guardrails

Production safety measures wrapping every agent loop and tool call. Design goal: an agent can be wrong, slow, or stuck — the system never is.

## Circuit breaker (`guardrails/circuit_breaker.py`)

Bounds every form of runaway. Checked in the supervisor node **before** every routing decision; trips short-circuit to synthesis with whatever evidence exists.

| Limit | Setting | Default |
|---|---|---|
| Graph iterations | `MAX_AGENT_ITERATIONS` | 15 |
| Total tokens | `MAX_TOTAL_TOKENS` | 200 000 |
| Wall-clock time | `AGENT_TIMEOUT_SECONDS` | 300 |

`check(state, settings) -> BreakerTrip | None` — evaluates all four conditions in priority order:

1. **max_iterations** — `iteration_count >= max_agent_iterations`
2. **token_budget** — `input_tokens + output_tokens >= max_total_tokens`
3. **timeout** — `time.monotonic() - state["start_time"] >= agent_timeout_seconds`
4. **repeated_route** — last 3 supervisor routing decisions are identical (stuck loop)

On trip: the supervisor node returns `next_agent="synthesize"` plus a `circuit_breaker / trip` trajectory entry; the LLM is never called. The wall-clock start time is stored in `GraphState.start_time` (set once when the initial state is constructed).

`make_trip_entry(step, trip) -> TrajectoryEntry` formats the trip reason and detail for the eval harness.

## Tool-call validator (`guardrails/tool_validator.py`)

`validate(tool_call, available_tools) -> str | None` — called for every tool call inside `_run_tool_loop` **before** `client.call_tool()`:

1. **Hallucinated tool** — name not in the available tool list → returns an error string listing available tools.
2. **Missing required args** — arguments don't satisfy the tool schema's `required` array → returns an error string listing missing fields.

Rejected calls are not silently dropped: the error string is injected as the `ToolResultMessage` so the model can self-correct on the next turn. The trajectory records a `validation_error` action for the eval harness.

## Output sanitizer (`guardrails/sanitizer.py`)

Applied to the final synthesis output by `make_synthesis_node`.

`sanitize_text(text) -> tuple[str, list[str]]`:
- Strips secret patterns: AWS access keys (`AKIA…`), `sk-*` API keys, connection strings (`postgresql://…`, etc.), auth headers, password values.
- Neutralises prompt-injection echoes: "ignore previous instructions", role-change directives (`you are now a…`), role tags (`<system>`, `<user>`, `<assistant>`).
- Returns (sanitised text, list of hit labels) for logging and trajectory recording.

`validate_synthesis(text) -> list[str]`:
- Checks the structured output contract: `ROOT CAUSE:`, `EVIDENCE:`, `REMEDIATION:`, `CONFIDENCE:` must all be present.
- Returns list of missing field names. Logged as `incomplete_synthesis` trajectory entry.

## Observability

Every guardrail decision is logged via structlog and recorded as a trajectory entry:

| Entry agent | Entry action | Trigger |
|---|---|---|
| `circuit_breaker` | `trip` | Breaker fires; includes reason and detail |
| `<specialist>` | `validation_error` | Tool call rejected; detail = tool name |
| `sanitizer` | `sanitized` | Secret or injection hit; detail = hit labels |
| `sanitizer` | `incomplete_synthesis` | Missing synthesis fields; detail = field list |
