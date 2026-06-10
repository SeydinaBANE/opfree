# Incident Copilot

[![CI](https://github.com/SeydinaBANE/opfree/actions/workflows/ci.yml/badge.svg)](https://github.com/SeydinaBANE/opfree/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Coverage ≥ 85%](https://img.shields.io/badge/coverage-85%25-4CAF50)](https://github.com/SeydinaBANE/opfree/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Production-grade **multi-agent SRE incident diagnosis copilot**. A LangGraph supervisor orchestrates three specialist agents — Log Analyst, Metrics Analyst, Runbook Executor — that investigate simulated cloud incidents through **MCP servers**, protected by production guardrails and measured by an **agentic evaluation harness**.

## Architecture

```
                        ┌──────────────────────────────┐
                        │   Supervisor (LangGraph)      │
                        │  routing · memory · guardrails│
                        └─────┬──────┬──────┬───────────┘
                              │      │      │
                 ┌────────────┘      │      └────────────┐
                 ▼                   ▼                   ▼
         ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
         │ Log Analyst  │   │ Metrics       │   │ Runbook        │
         │              │   │ Analyst       │   │ Executor       │
         └──────┬───────┘   └──────┬────────┘   └──────┬─────────┘
                │ MCP (stdio)      │ MCP (stdio)        │ MCP (stdio)
                ▼                  ▼                    ▼
         ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
         │  k8s_mock    │   │ prometheus_   │   │ runbook_mock   │
         │  server      │   │ mock server   │   │ server         │
         └──────────────┘   └───────────────┘   └────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │    Synthesis node     │
                        │ ROOT CAUSE · EVIDENCE │
                        │ REMEDIATION · CONFID. │
                        └───────────┬───────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │    Persist node       │
                        │  SQLite memory store  │
                        └───────────────────────┘
```

**Cross-cutting layers:** circuit-breaker guardrail · tool-call validator · output sanitizer · sliding-window context pruning · semantic summarization · past-incident memory retrieval.

Full details in [docs/architecture.md](docs/architecture.md).

## Quickstart

```bash
# 1 — install
make install
cp .env.example .env      # add ANTHROPIC_API_KEY

# 2 — diagnose a simulated incident (real LLM calls)
make run SCENARIO=crashloop

# 3 — run the agentic evaluation harness
make evals
```

Quality gates:

```bash
make check      # lint (ruff) + typecheck (mypy strict) + tests (pytest)
make coverage   # coverage report — fails below 85%
```

Docker:

```bash
make docker-build
make docker-run   # runs: incident-copilot diagnose --scenario crashloop
```

## Key features

| Feature | Implementation |
|---|---|
| Multi-agent supervisor routing | `agents/supervisor.py` — single LLM call, routes to log/metrics/runbook/synthesis |
| Typed shared state (LangGraph) | `agents/state.py` — `GraphState` TypedDict with reducer annotations |
| MCP tool servers | `mcp_servers/` — three FastMCP servers (k8s, Prometheus, runbooks) |
| Circuit breaker | `guardrails/circuit_breaker.py` — max iterations, token budget, timeout, repeated-route detection |
| Tool-call validator | `guardrails/tool_validator.py` — hallucinated-tool and missing-arg rejection with LLM feedback loop |
| Output sanitizer | `guardrails/sanitizer.py` — secret redaction, prompt-injection neutralisation, synthesis contract check |
| Context management | `context/` — sliding window eviction + LLM-based semantic summarization |
| Incident memory | `memory/store.py` — SQLite store; supervisor reads past incidents at diagnosis start |
| Agentic eval harness | `evals/` — N-run replay, tool-call F1 vs gold trajectory, consistency, reasoning correctness |
| Multi-provider LLM | `llm/` — Anthropic (working), Bedrock + Vertex stubs; swap via `LLM_PROVIDER` env var |

## Eval results

Run `make evals` to generate a timestamped report under `reports/`. Report format:

| Scenario | Runs | Precision | Recall | F1 | Consistency | Correct | Loops | Val Errs | Trips | Avg Tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| crashloop | 3 | 1.000 | 1.000 | 1.000 | 1.000 | yes | 0 | 0 | 0 | — |
| oom | 3 | — | — | — | — | — | — | — | — | — |
| latency_spike | 3 | — | — | — | — | — | — | — | — | — |

> Actual numbers depend on model version and temperature. Run `make evals` with your `ANTHROPIC_API_KEY` to populate.

## Scenarios

Three built-in simulated incidents in `scenarios/`:

| Scenario | Root cause |
|---|---|
| `crashloop` | Service cannot reach its dependent database (connection refused) |
| `oom` | Container exceeded its memory limit due to unbounded cache growth |
| `latency_spike` | Missing database index causing full table scans |

## Configuration

All settings via `.env` (see `.env.example`):

| Variable | Default | Effect |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` / `bedrock` / `vertex` |
| `LLM_MODEL` | `claude-sonnet-4-6` | Model ID passed to the provider |
| `MAX_AGENT_ITERATIONS` | `15` | Circuit breaker iteration cap |
| `MAX_TOTAL_TOKENS` | `200000` | Circuit breaker token budget |
| `AGENT_TIMEOUT_SECONDS` | `300` | Circuit breaker wall-clock timeout |
| `LOG_LEVEL` | `INFO` | structlog level |

## Project docs

| Document | Content |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Layer diagram, data flow, design decisions |
| [docs/agents.md](docs/agents.md) | State schema, graph topology, supervisor/specialist/synthesis detail |
| [docs/guardrails.md](docs/guardrails.md) | Circuit breaker, tool validator, sanitizer — all trigger conditions |
| [docs/evals.md](docs/evals.md) | Metrics definitions, harness design, regression policy |
| [docs/runbook.md](docs/runbook.md) | Setup, everyday commands, debugging guide |
