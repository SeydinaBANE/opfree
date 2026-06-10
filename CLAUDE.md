# CLAUDE.md — Working agreement for AI-assisted development

This file tells Claude Code how to work in this repo autonomously. Read PROJECT.md for the vision and TODO.md for what to build next.

## Workflow

1. Open TODO.md and pick the first unchecked step (steps are ordered; do not skip ahead).
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

## Architecture rules

- Layers: `cli` → `agents` (orchestration) → `llm` / `mcp_servers` / `memory` (infrastructure). Never call the Anthropic SDK outside `llm/`. Never touch SQLite outside `memory/`.
- All LLM access goes through the `LLMProvider` interface so Bedrock/Vertex can be swapped in via `LLM_PROVIDER`.
- Every agent tool call must pass through `guardrails.tool_validator`; every graph loop is bounded by `guardrails.circuit_breaker`.
- Scenario data lives in `scenarios/` and is the single source of truth for both MCP mock servers and eval gold trajectories.

## Documentation duties

When a step changes behavior or architecture, update the matching docs/ page and README in the same commit. TODO.md must always reflect reality.
