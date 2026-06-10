# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Multi-agent SRE incident diagnosis copilot. A LangGraph supervisor orchestrates three specialist agents (Log Analyst, Metrics Analyst, Runbook Executor) that investigate simulated cloud incidents through MCP mock servers, protected by production guardrails. Read PROJECT.md for the vision and TODO.md for the phased backlog (steps are ordered — do not skip ahead).

## Workflow

1. Open TODO.md and pick the first unchecked step.
2. Read the relevant docs/ page before coding (architecture.md, agents.md, guardrails.md, evals.md).
3. Implement in small increments: code + tests together, never code without tests.
4. Run `make check` — it must be fully green before the step is considered done.
5. Tick the step in TODO.md and add new sub-tasks discovered along the way.
6. Commit with a conventional message (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`). Never push unless explicitly asked.

## Commands

| Command | Purpose |
|---|---|
| `make install` | uv sync + pre-commit hooks |
| `make check` | lint + typecheck + tests (the definition of done) |
| `make lint` / `make format` | ruff check / auto-fix |
| `make typecheck` | mypy strict |
| `make test` / `make coverage` | pytest / coverage (fails under 85%) |
| `make run SCENARIO=<name>` | run a diagnosis end-to-end (needs ANTHROPIC_API_KEY) |
| `make evals` | run the evaluation harness |

Run a single test: `uv run pytest tests/test_<module>.py::test_function_name -v`

Run a mock MCP server standalone (useful for debugging): `uv run python -m incident_copilot.mcp_servers.k8s_mock --scenario crashloop`

First-time setup: `cp .env.example .env` and add `ANTHROPIC_API_KEY`.

Always run Python through `uv run` — never the system interpreter.

## Code conventions

- Python 3.12, src layout, package `incident_copilot`. Ruff line-length is **100** (not 88).
- Strict typing everywhere: all parameters and return values annotated; no `Any`, no bare `dict`/`list`, no `# type: ignore` without a documented reason.
- No comments in code — code must be self-documenting. Docstrings only where they add real information.
- One function = one responsibility, max ~30 lines.
- Logging via `structlog` only — never `print`.
- Configuration only through `incident_copilot.config.Settings` (pydantic-settings, loaded from `.env`). No hardcoded secrets, paths, or model names.
- Domain errors are raised in the domain layer (agents, guardrails) and caught at the CLI boundary.
- Dependencies: check pyproject.toml before adding anything; additions require a real justification.

## Testing conventions

- pytest with `asyncio_mode = "auto"` — tests may be `async def` without extra decoration.
- Files mirror `src/` layout (`tests/test_<module>.py`). Names: `test_<function>_<case>`.
- Minimum per feature: one nominal test + one error/edge case.
- No network in tests: the LLM provider and MCP clients are always mocked or faked. Scenario JSON files are the test fixtures.
- Coverage gate: 85% (enforced by `make coverage` and CI).

## Module layout (src/incident_copilot/)

| Module | Status | Purpose |
|---|---|---|
| `config.py` | done | `Settings` via pydantic-settings; all env vars |
| `log.py` | done | structlog bootstrap called once at startup |
| `cli.py` | done | Typer entry point; catches domain errors, renders with rich |
| `scenarios.py` | done | Pydantic schema for scenario JSON; `Scenario.load(path)` |
| `llm/base.py` | done | `LLMProvider` protocol, typed `Message`, `LLMResponse`, `ToolDefinition` |
| `llm/anthropic_provider.py` | done | Working Anthropic SDK impl with retries and token accounting |
| `llm/bedrock_provider.py` | stub | Documented stub — raises `NotImplementedError` |
| `llm/vertex_provider.py` | stub | Documented stub — raises `NotImplementedError` |
| `llm/factory.py` | done | Selects provider from `Settings.llm_provider` |
| `mcp_servers/k8s_mock.py` | done | FastMCP server: `list_pods`, `describe_pod`, `get_pod_logs`, `get_events` |
| `mcp_servers/prometheus_mock.py` | done | FastMCP server: `query_range`, `get_alerts`, `get_targets` |
| `mcp_servers/runbook_mock.py` | done | FastMCP server: runbook retrieval and execution steps |
| `mcp_servers/client.py` | done | `MCPClient` wrapper + `connect_to_server` async context manager |
| `agents/state.py` | done | `GraphState`, `Finding`, `TrajectoryEntry` TypedDicts; reducer annotations |
| `agents/supervisor.py` | done | `make_supervisor_node` + `route_supervisor` conditional edge function |
| `agents/specialists.py` | done | `make_log_analyst_node`, `make_metrics_analyst_node`, `make_runbook_executor_node` |
| `agents/synthesis.py` | done | `make_synthesis_node` — aggregates findings into ROOT CAUSE / REMEDIATION / CONFIDENCE |
| `agents/graph.py` | done | `build_graph` — wires the LangGraph `StateGraph` with `MemorySaver` checkpointing |
| `guardrails/circuit_breaker.py` | done | `check` + `BreakerTrip`; max iterations / token budget / timeout / repeated-route detection |
| `guardrails/tool_validator.py` | done | `validate`; hallucinated-tool and missing-arg rejection with LLM-readable error feedback |
| `guardrails/sanitizer.py` | done | `sanitize_text` (secrets + injection); `validate_synthesis` (output contract check) |
| `context/` | planned | Sliding window, semantic summarizer, token-efficient pruning |
| `memory/` | planned | SQLite store for resolved incidents and user preferences |
| `evals/` | planned | Replay harness, trajectory metrics, markdown/JSON report |

Scenario JSON files live in `scenarios/` (three built-in: `crashloop`, `oom`, `latency_spike`).

## Architecture rules

- Layers: `cli` → `agents` (orchestration) → `llm` / `mcp_servers` / `memory` (infrastructure). Never call the Anthropic SDK outside `llm/`. Never touch SQLite outside `memory/`.
- All LLM access goes through the `LLMProvider` interface so Bedrock/Vertex can be swapped in via `LLM_PROVIDER`.
- Every agent tool call must pass through `guardrails.tool_validator`; every graph loop is bounded by `guardrails.circuit_breaker`.
- Scenario data lives in `scenarios/` and is the single source of truth for both MCP mock servers and eval gold trajectories.

## Documentation duties

When a step changes behavior or architecture, update the matching docs/ page and README in the same commit. TODO.md must always reflect reality.
