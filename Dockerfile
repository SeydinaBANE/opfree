FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY scenarios ./scenarios
COPY README.md ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --from=builder --chown=app:app /app/src ./src
COPY --from=builder --chown=app:app /app/scenarios ./scenarios

ENV PATH="/app/.venv/bin:$PATH"
USER app

ENTRYPOINT ["incident-copilot"]
CMD ["--help"]
