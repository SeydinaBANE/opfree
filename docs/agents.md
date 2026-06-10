# Agents

All agents share the `LLMProvider` interface and the typed graph state. Each specialist is an LLM tool-use loop over one MCP server, with its own system prompt and a strict output contract (structured findings, never free prose into the state).

## Supervisor

- Role: cognitive architecture root — loads the scenario, consults memory, decides which specialist to engage next, decides when evidence is sufficient to synthesize.
- Tools: none directly; it routes.
- Output contract: a routing decision (`log_analyst` | `metrics_analyst` | `runbook_executor` | `synthesize`) plus a short rationale recorded in the trajectory.
- Stop conditions: confidence threshold reached, circuit breaker trip, or no specialist can add evidence.

## Log Analyst

- Role: investigate pod/container logs and Kubernetes events.
- MCP server: `k8s_mock` (`list_pods`, `describe_pod`, `get_pod_logs`, `get_events`).
- Output contract: list of findings `{source, observation, severity, supports_hypothesis}`.

## Metrics Analyst

- Role: investigate time-series and alerts (CPU, memory, latency, restarts).
- MCP server: `prometheus_mock` (`query_range`, `get_alerts`, `get_targets`).
- Output contract: same findings structure, with metric evidence (series name, window, anomaly).

## Runbook Executor

- Role: match findings against known runbooks and propose (simulated) remediation steps.
- MCP server: runbook tools (lookup, step listing). Execution is simulated — it never mutates anything real.
- Output contract: ordered remediation plan with per-step risk notes.

## Synthesis node

Not an agent loop — a single structured-output LLM call that merges findings into the final diagnosis: root cause, evidence chain, remediation proposal, confidence.

## Prompting rules

- System prompts live next to each agent module as module-level constants.
- Prompts must instruct the model to only use tools that exist (the validator enforces it anyway) and to emit the structured output contract.
- Any prompt change requires re-running `make evals` and noting the delta in the PR/commit message.
