# Architecture

## Overview

Incident Copilot is a supervisor/specialist Multi-Agent System built on a LangGraph `StateGraph`. It is a graph, not a chain: the supervisor re-routes after every specialist turn based on accumulated findings, and cycles are allowed but bounded by the circuit breaker.

```
 ┌─────────┐     ┌────────────────────────────────────────────────┐
 │   CLI   │────▶│                 Supervisor                     │
 └─────────┘     │  load scenario · consult memory · route · stop │
                 └───────┬───────────────┬───────────────┬────────┘
                         ▼               ▼               ▼
                  ┌────────────┐  ┌──────────────┐  ┌──────────────┐
                  │ Log        │  │ Metrics      │  │ Runbook      │
                  │ Analyst    │  │ Analyst      │  │ Executor     │
                  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘
                        │ MCP (stdio)    │ MCP (stdio)     │ MCP (stdio)
                        ▼                ▼                 ▼
                  ┌────────────┐  ┌──────────────┐  ┌──────────────┐
                  │ k8s_mock   │  │ prometheus_  │  │ runbook      │
                  │ server     │  │ mock server  │  │ tools        │
                  └────────────┘  └──────────────┘  └──────────────┘
                         │               │               │
                         └───────────────┴───────────────┘
                                         ▼
                              ┌────────────────────┐
                              │  Synthesis node    │
                              │ diagnosis + remedy │
                              └────────────────────┘
```

## Layers

| Layer | Modules | Rule |
|---|---|---|
| Presentation | `cli.py` | catches domain errors, renders with rich |
| Orchestration | `agents/` | owns the graph, state, routing |
| Cross-cutting | `guardrails/`, `context/` | wrap every loop and tool call |
| Infrastructure | `llm/`, `mcp_servers/`, `memory/` | only place touching SDKs, processes, SQLite |

Dependency direction is strictly downward. The Anthropic SDK is never imported outside `llm/`.

## Shared state

A typed state object flows through the graph and carries:

- the scenario under diagnosis,
- accumulated findings per agent,
- the full trajectory (every routing decision and tool call — also consumed by evals),
- token usage and iteration counters (consumed by the circuit breaker),
- the context window (managed by `context/`).

## Data flow for one diagnosis

1. CLI calls the supervisor with a scenario name.
2. Supervisor loads `scenarios/<name>.json`, queries `memory/` for similar past incidents.
3. Supervisor routes to a specialist; the specialist runs an LLM tool-use loop against its MCP server. Every tool call passes `tool_validator`; every iteration ticks `circuit_breaker`.
4. Findings return to the supervisor, context manager compacts history if needed, supervisor re-routes or proceeds to synthesis.
5. Synthesis node emits diagnosis + remediation; the incident is persisted to memory; trajectory is returned for display and evals.

## Why these choices

See PROJECT.md ADRs: LangGraph (ADR-1), provider abstraction (ADR-2), MCP servers over in-process tools (ADR-3), simulated incidents (ADR-4).
