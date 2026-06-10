# Agents

All agents share the `LLMProvider` interface and the typed `GraphState`. Each specialist is an LLM tool-use loop over one MCP server, with its own system prompt and a strict output contract (structured `Finding` entries written to state, never free prose).

## Shared state (`agents/state.py`)

`GraphState` is a `TypedDict` with LangGraph reducer annotations:

| Field | Type | Reducer |
|---|---|---|
| `scenario` | `Scenario` | replace |
| `findings` | `list[Finding]` | `operator.add` (append) |
| `trajectory` | `list[TrajectoryEntry]` | `operator.add` (append) |
| `input_tokens` | `int` | `operator.add` (sum) |
| `output_tokens` | `int` | `operator.add` (sum) |
| `iteration_count` | `int` | `operator.add` (sum) |
| `next_agent` | `str` | replace |
| `diagnosis` | `str \| None` | replace |

`Finding` captures `{agent, source, observation, severity, supports_hypothesis}`. `TrajectoryEntry` captures `{step, agent, action, detail}`.

## Graph topology (`agents/graph.py`)

```
supervisor
    ├── log_analyst      → supervisor
    ├── metrics_analyst  → supervisor
    ├── runbook_executor → supervisor
    └── synthesize       → END
```

Built with `StateGraph(GraphState)` compiled with `MemorySaver` checkpointing. `build_graph(llm, *, k8s_client, prom_client, runbook_client)` accepts optional pre-built `MCPClient` instances for tests; when `None`, each specialist spawns its MCP server as a subprocess.

## Supervisor (`agents/supervisor.py`)

Single `llm.complete()` call (max 64 tokens) with the current incident description and list of already-consulted agents. Responds with one word: `log_analyst`, `metrics_analyst`, `runbook_executor`, or `synthesize`. `_parse_routing` does case-insensitive substring matching and defaults to `synthesize` on unrecognised output.

Rules encoded in the system prompt: each specialist consulted at most once; synthesize after ≥2 specialists report; always synthesize after all 3.

## Specialists (`agents/specialists.py`)

All three specialists share `_run_tool_loop`:

1. `client.list_tools()` to get available `ToolDefinition` list.
2. `llm.tool_use()` with the tool list.
3. If the response has tool calls: append `AssistantMessage` + `ToolResultMessage` per call, log each to trajectory, loop.
4. On `end_turn`: emit one `Finding` from the final response content.

Token counts accumulate across the loop and are returned as partial state updates.

| Node | MCP server | Key tools |
|---|---|---|
| `log_analyst` | `k8s_mock` | `list_pods`, `describe_pod`, `get_pod_logs`, `get_events` |
| `metrics_analyst` | `prometheus_mock` | `query_range`, `get_alerts`, `get_targets` |
| `runbook_executor` | `runbook_mock` | `list_runbooks`, `get_runbook`, `list_runbook_steps` |

## Synthesis node (`agents/synthesis.py`)

Not a tool-use loop — a single `llm.complete()` call (max 512 tokens) that merges all findings into a structured response:

```
ROOT CAUSE: <one sentence>
EVIDENCE: <key observations>
REMEDIATION: <ordered steps>
CONFIDENCE: high | medium | low
```

## Prompting rules

- System prompts live as module-level constants in each agent module.
- Any prompt change requires re-running `make evals` and noting the delta in the commit message.
