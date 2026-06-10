# TODO.md — Phased backlog

Rules: steps are ordered, finish one before starting the next. A step is done only when `make check` is green, tests cover the new code, the matching docs/ page is updated, and the work is committed. See CLAUDE.md.

## Step 1 — Production foundations
- [x] git init, uv project, Python 3.12 pinned
- [x] pyproject: deps, ruff (strict ruleset), mypy strict, pytest + coverage ≥ 85%
- [x] Makefile (install, lint, format, typecheck, test, coverage, check, run, evals, docker-*)
- [x] pre-commit config (ruff, ruff-format, mypy, hygiene hooks)
- [x] GitHub Actions CI (lint → typecheck → tests+coverage → docker build)
- [x] Dockerfile multi-stage non-root + docker-compose
- [x] Minimal package + CLI skeleton + sanity tests

## Step 2 — Documentation & steering files
- [x] README (pitch, architecture, quickstart, requirements→modules table)
- [x] CLAUDE.md, PROJECT.md (ADRs), TODO.md
- [x] docs/: architecture.md, agents.md, guardrails.md, evals.md, runbook.md

## Step 3 — Config + LLM provider abstraction
- [x] `config.py`: `Settings` (pydantic-settings) — provider, model, budgets, log level
- [x] `llm/base.py`: `LLMProvider` protocol (complete + tool-use methods, typed messages)
- [x] `llm/anthropic_provider.py`: working implementation (SDK, retries, token accounting)
- [x] `llm/bedrock_provider.py` + `llm/vertex_provider.py`: documented stubs
- [x] `llm/factory.py`: provider selection from Settings
- [x] structlog setup module (`log.py`)
- [x] Tests: settings parsing, factory selection, Anthropic provider with mocked SDK

## Step 4 — Scenarios + MCP mock servers
- [x] Scenario schema (pydantic): pods, logs, metrics, alerts, runbooks, gold trajectory
- [x] `scenarios/crashloop.json`, `scenarios/oom.json`, `scenarios/latency_spike.json`
- [x] `mcp_servers/k8s_mock.py`: list_pods, describe_pod, get_pod_logs, get_events
- [x] `mcp_servers/prometheus_mock.py`: query_range, get_alerts, get_targets
- [x] `mcp_servers/runbook_mock.py`: get_runbook, list_runbooks, list_runbook_steps
- [x] MCP client helper for agents (connect, list tools, call tool)
- [x] Tests: tool outputs per scenario, schema validation, unknown-tool errors

## Step 5 — Multi-agent LangGraph
- [x] Typed shared state (findings, trajectory, token usage, iteration count)
- [x] Supervisor node: routing logic (which specialist next, or synthesize)
- [x] Specialist agents: log_analyst, metrics_analyst, runbook_executor (MCP tool loops)
- [x] Synthesis node: diagnosis + remediation proposal
- [x] Checkpointing for long-running tasks
- [x] Tests: routing decisions, each agent with mocked LLM + fake MCP, full graph run on crashloop with scripted LLM

## Step 6 — Guardrails
- [x] `circuit_breaker.py`: max iterations, token budget, wall-clock timeout, trip reporting
- [x] `tool_validator.py`: validate calls against live MCP schemas, reject + feed back hallucinated tools/args
- [x] `sanitizer.py`: output sanitization (secrets, prompt-injection echoes)
- [x] Wire into the graph (every agent loop, every tool call)
- [x] Tests: breaker trips, hallucinated tool rejected then corrected, sanitizer cases

## Step 7 — Context management + memory
- [x] `context/window.py`: sliding window over graph history
- [x] `context/summarizer.py`: semantic summarization of evicted turns
- [x] `context/pruning.py`: token-efficient pruning
- [x] `memory/store.py`: SQLite store — resolved incidents, user preferences
- [x] Supervisor consults memory at diagnosis start; writes back on resolution
- [x] Tests: window eviction, summarizer with mocked LLM, store round-trips

## Step 8 — Agentic evaluation harness
- [ ] `evals/harness.py`: replay scenarios N times, capture trajectories
- [ ] `evals/metrics.py`: tool-call accuracy vs gold, trajectory consistency, loop detection
- [ ] `evals/report.py`: markdown + JSON report
- [ ] `evals` CLI command wired (`make evals`)
- [ ] Tests: metrics on synthetic trajectories, report rendering

## Step 9 — Polish & release
- [ ] `diagnose` CLI: rich live trajectory display, final diagnosis panel
- [ ] Verify `make docker-build && make docker-run` end-to-end
- [ ] Complete docs/ pages with final diagrams and real examples
- [ ] README: add eval results table + demo GIF/asciinema
- [ ] Manual checks: circuit breaker on a trap scenario, eval report quality
