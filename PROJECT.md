# PROJECT.md — Vision & decisions

## Why this project exists

Portfolio project targeting the Opsfleet AI Engineer role ([offre.md](offre.md)). The offer asks for production-grade agentic systems: Multi-Agent Systems, MCP, LangGraph state-handling, context orchestration, safety guardrails, memory, and agentic evaluation. This repo demonstrates each requirement with working, tested code in a domain that matches Opsfleet's business (SRE / cloud operations).

## What it does

`incident-copilot diagnose --scenario crashloop` runs a multi-agent diagnosis of a simulated cloud incident:

1. The **supervisor** (LangGraph StateGraph) loads the scenario, consults memory for similar past incidents, and routes work to specialists.
2. **Log Analyst**, **Metrics Analyst**, and **Runbook Executor** agents investigate through MCP tools served by mock Kubernetes and Prometheus servers fed from scenario JSON.
3. Guardrails bound every loop (circuit breaker), validate every tool call against real MCP schemas (hallucination detection), and sanitize outputs.
4. A synthesis node produces the final diagnosis and remediation proposal; the resolved incident is written to memory.
5. The **eval harness** replays scenarios against gold trajectories and scores tool-call accuracy, trajectory consistency, and loop behavior.

## Architecture decisions (ADR)

### ADR-1: LangGraph for orchestration
Supervisor/specialist pattern as an explicit StateGraph: typed shared state, bounded cycles, checkpointing for long-running tasks. A graph (not a linear chain) because routing depends on intermediate findings.

### ADR-2: LLM provider abstraction instead of direct Bedrock/Vertex
Development runs on the Anthropic API (no cloud account needed). All model access goes through an `LLMProvider` interface with `AnthropicProvider` implemented and `BedrockProvider`/`VertexProvider` as documented stubs, selected by `LLM_PROVIDER` config. This shows enterprise portability without blocking local work.

### ADR-3: MCP servers over in-process tools
Tools are exposed by real stdio MCP servers (`k8s_mock`, `prometheus_mock`) rather than plain Python functions, to demonstrate the MCP communication standard the offer requires. Agents are MCP clients; tool schemas come from the servers and double as validation source for the hallucination detector.

### ADR-4: Simulated incidents, no real infra
Scenarios are JSON files (`scenarios/`) containing pods, logs, metrics, alerts, and a gold trajectory. The same files feed the MCP mock servers and the eval harness, keeping the system deterministic and testable offline.

### ADR-5: Quality gates as product
mypy strict, ruff, 85% coverage, pre-commit, CI, Docker non-root multi-stage. The engineering rigor is part of what this portfolio demonstrates.

## Scope

In scope: 3 incident scenarios (crashloop, oom, latency_spike), 3 specialist agents, sliding-window + summarization context management, SQLite memory, eval harness with markdown/JSON reports, CLI demo, Docker.

Out of scope: real cluster access, web UI, A2A cross-process agent federation (mentioned in README as future work), fine-tuning.

## Key references

- Backlog: [TODO.md](TODO.md)
- Working agreement: [CLAUDE.md](CLAUDE.md)
- Deep dives: [docs/architecture.md](docs/architecture.md), [docs/agents.md](docs/agents.md), [docs/guardrails.md](docs/guardrails.md), [docs/evals.md](docs/evals.md), [docs/runbook.md](docs/runbook.md)
