# Guardrails

Production safety measures wrapping every agent loop and tool call. Design goal: an agent can be wrong, slow, or stuck — the system never is.

## Circuit breaker (`guardrails/circuit_breaker.py`)

Bounds every form of runaway:

| Limit | Setting | Default |
|---|---|---|
| Graph iterations | `MAX_AGENT_ITERATIONS` | 15 |
| Total tokens | `MAX_TOTAL_TOKENS` | 200 000 |
| Wall-clock time | `AGENT_TIMEOUT_SECONDS` | 300 |

On trip: the graph short-circuits to synthesis with whatever evidence exists, the trajectory records the trip reason, and the CLI reports a degraded (but honest) diagnosis. A trip is never an exception that loses state.

Loop detection: if the supervisor issues the same routing decision with identical findings hash N times in a row, the breaker trips early (`repeated_route` reason) — this is the classic "agent stuck in an infinite loop" scar the offer mentions.

## Tool-call validator (`guardrails/tool_validator.py`)

Every tool call an agent emits is checked **against the live MCP server schemas** before execution:

1. Tool name must exist on the connected server — otherwise it is a *hallucinated tool*.
2. Arguments must validate against the tool's JSON schema — otherwise *hallucinated arguments*.

Rejected calls are not silently dropped: the validator returns a structured error message into the agent's tool-result slot ("tool `get_pod` does not exist; available: …") so the model can self-correct on the next turn. Repeated hallucinations count toward the circuit breaker.

## Output sanitizer (`guardrails/sanitizer.py`)

Applied to specialist findings and the final synthesis:

- strips anything matching secret patterns (keys, tokens, connection strings) coming back from logs,
- neutralizes prompt-injection echoes found in scenario data (instructions embedded in log lines are rendered inert),
- enforces the structured output contract — non-conforming output is rejected and retried once, then surfaced as a guardrail failure.

## Observability

Every guardrail decision (validation failure, breaker tick, trip, sanitization hit) is logged via structlog with the incident id, and recorded in the trajectory so the eval harness can score guardrail behavior, not just happy paths.
