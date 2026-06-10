# Incident Copilot

Production-grade **multi-agent SRE incident diagnosis copilot**. A LangGraph supervisor orchestrates specialist agents (logs, metrics, runbooks) that investigate simulated cloud incidents through **MCP servers**, protected by production guardrails (circuit breakers, tool-call validation, output sanitization) and measured by an **agentic evaluation harness**.

Built as a portfolio project demonstrating the skills required for production agentic systems (see [offre.md](offre.md)).

## Architecture

```
                        ┌──────────────────────────┐
                        │   Supervisor (LangGraph)  │
                        │  routing · shared state   │
                        └─────┬──────┬──────┬───────┘
                              │      │      │
                 ┌────────────┘      │      └────────────┐
                 ▼                   ▼                   ▼
         ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
         │ Log Analyst  │   │ Metrics       │   │ Runbook        │
         │              │   │ Analyst       │   │ Executor       │
         └──────┬───────┘   └──────┬────────┘   └──────┬─────────┘
                │ MCP              │ MCP               │ MCP
                ▼                  ▼                   ▼
         ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
         │ k8s_mock     │   │ prometheus_   │   │ runbook tools  │
         │ server       │   │ mock server   │   │                │
         └──────────────┘   └───────────────┘   └────────────────┘

   Cross-cutting: guardrails (circuit breaker, tool validation, sanitizer),
   context management (sliding window, semantic summarization),
   memory (past incidents, user preferences), eval harness.
```

Full details in [docs/architecture.md](docs/architecture.md).

## Quickstart

```bash
make install                 # uv sync + pre-commit hooks
cp .env.example .env         # add your ANTHROPIC_API_KEY
make run SCENARIO=crashloop  # diagnose a simulated incident
make evals                   # run the agentic evaluation harness
```

Quality gates:

```bash
make check      # lint + typecheck + tests
make coverage   # coverage report (fails under 85%)
```

Docker:

```bash
make docker-build
make docker-run
```

## Job requirements → modules

| Requirement (offre.md) | Where it lives |
|---|---|
| Multi-Agent Systems beyond basic RAG | `src/incident_copilot/agents/` (LangGraph supervisor + specialists) |
| Context orchestration (sliding window, semantic summarization, pruning) | `src/incident_copilot/context/` |
| Tool-use & MCP interfaces | `src/incident_copilot/mcp_servers/` + agent MCP clients |
| LangGraph state-handling for long-running tasks | `src/incident_copilot/agents/supervisor.py` |
| Safety: sanitization, hallucination triggers, circuit breakers | `src/incident_copilot/guardrails/` |
| Memory & personalization | `src/incident_copilot/memory/` |
| Agentic evaluation (trajectories, tool-call accuracy) | `src/incident_copilot/evals/` |
| Bedrock / Vertex enterprise deployment | `src/incident_copilot/llm/` provider abstraction |
| Modular architecture & clean Python | src layout, mypy strict, ruff, 85%+ coverage, CI |

## Project docs

- [PROJECT.md](PROJECT.md) — vision, scope, architecture decisions
- [TODO.md](TODO.md) — phased backlog
- [CLAUDE.md](CLAUDE.md) — working agreement for AI-assisted development
- [docs/](docs/) — architecture, agents, guardrails, evals, runbook

## Status

Work in progress — foundations and documentation are in place; agent implementation follows the backlog in [TODO.md](TODO.md).
