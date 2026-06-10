# Runbook — operating the project

## Prerequisites

- [uv](https://docs.astral.sh/uv/) ≥ 0.5 (manages Python 3.12 automatically)
- Docker (optional, for the containerized demo)
- An Anthropic API key

## Setup

```bash
make install
cp .env.example .env   # fill in ANTHROPIC_API_KEY
```

## Everyday commands

```bash
make check                    # lint + typecheck + tests — must be green before any commit
make run SCENARIO=crashloop   # end-to-end diagnosis (real LLM calls)
make evals                    # evaluation harness, writes reports/
make docker-build && make docker-run
```

## Configuration

All settings come from `.env` (see `.env.example`). Key variables:

| Variable | Effect |
|---|---|
| `LLM_PROVIDER` | `anthropic` (default), `bedrock`, `vertex` |
| `LLM_MODEL` | model id passed to the provider |
| `MAX_AGENT_ITERATIONS` / `MAX_TOTAL_TOKENS` / `AGENT_TIMEOUT_SECONDS` | circuit breaker budgets |
| `LOG_LEVEL` | structlog level |

## Debugging

- Set `LOG_LEVEL=DEBUG` to get full structlog output including every routing decision, tool call, validation result, and breaker tick.
- Trajectories are part of the diagnosis output; `make evals` reports include the worst trajectory diff.
- MCP servers can be exercised standalone: `uv run python -m incident_copilot.mcp_servers.k8s_mock` and speak stdio MCP to it (e.g. with the MCP inspector).

## Known failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `NotImplementedError` from CLI | feature not yet built | check TODO.md — steps land in order |
| Diagnosis ends with `circuit_breaker: repeated_route` | model stuck re-routing | inspect trajectory; usually a prompt or scenario-data issue |
| `hallucinated tool` entries in logs | model invented a tool | expected occasionally; validator feeds back and the model self-corrects. Frequent occurrences → check prompts list the right server |
| Tests touching the network | a provider/MCP mock is missing | tests must never hit the network; fix the fixture |

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs lint → typecheck → tests+coverage → docker build on every push/PR to main. Coverage below 85% fails the build.
