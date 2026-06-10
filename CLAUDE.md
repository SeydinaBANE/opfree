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

First-time setup: `cp .env.example .env` and add `ANTHROPIC_API_KEY`.

Always run Python through `uv run` — never the system interpreter.

## Code conventions

- Python 3.12, src layout, package `incident_copilot`.
- Strict typing everywhere: all parameters and return values annotated; no `Any`, no bare `dict`/`list`, no `# type: ignore` without a documented reason.
- No comments in code — code must be self-documenting. Docstrings only where they add real information.
- One function = one responsibility, max ~30 lines.
- Logging via `structlog` only — never `print`.
- Configuration only through `incident_copilot.config.Settings` (pydantic-settings, loaded from `.env`). No hardcoded secrets, paths, or model names.
- Domain errors are raised in the domain layer (agents, guardrails) and caught at the CLI boundary.
- Dependencies: check pyproject.toml before adding anything; additions require a real justification.

## Testing conventions

- pytest, files mirror `src/` layout (`tests/test_<module>.py`).
- Names: `test_<function>_<case>`.
- Minimum per feature: one nominal test + one error/edge case.
- No network in tests: the LLM provider and MCP clients are always mocked or faked. Scenario JSON files are the test fixtures.
- Coverage gate: 85% (enforced by `make coverage` and CI).

## Planned module layout (src/incident_copilot/)

| Module | Purpose |
|---|---|
| `config.py` | `Settings` via pydantic-settings; all env vars |
| `cli.py` | Typer entry point; catches domain errors, renders with rich |
| `agents/` | LangGraph graph, supervisor, specialist nodes, shared state |
| `llm/` | `LLMProvider` protocol + Anthropic/Bedrock/Vertex impls + factory |
| `mcp_servers/` | `k8s_mock.py`, `prometheus_mock.py`, runbook tools; MCP client helper |
| `guardrails/` | `circuit_breaker.py`, `tool_validator.py`, `sanitizer.py` |
| `context/` | Sliding window, semantic summarizer, token-efficient pruning |
| `memory/` | SQLite store for resolved incidents and user preferences |
| `evals/` | Replay harness, trajectory metrics, markdown/JSON report |
| `scenarios/` | JSON scenario files — single source of truth for MCP data and eval gold |

## Architecture rules

- Layers: `cli` → `agents` (orchestration) → `llm` / `mcp_servers` / `memory` (infrastructure). Never call the Anthropic SDK outside `llm/`. Never touch SQLite outside `memory/`.
- All LLM access goes through the `LLMProvider` interface so Bedrock/Vertex can be swapped in via `LLM_PROVIDER`.
- Every agent tool call must pass through `guardrails.tool_validator`; every graph loop is bounded by `guardrails.circuit_breaker`.
- Scenario data lives in `scenarios/` and is the single source of truth for both MCP mock servers and eval gold trajectories.

## Documentation duties

When a step changes behavior or architecture, update the matching docs/ page and README in the same commit. TODO.md must always reflect reality.
