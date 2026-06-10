.DEFAULT_GOAL := help
SCENARIO ?= crashloop

.PHONY: help install lint format typecheck test coverage check run evals docker-build docker-run clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and pre-commit hooks
	uv sync
	uv run pre-commit install

lint: ## Run ruff linter and format check
	uv run ruff check src tests
	uv run ruff format --check src tests

format: ## Auto-format and fix lint issues
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck: ## Run mypy strict type checking
	uv run mypy

test: ## Run the test suite
	uv run pytest

coverage: ## Run tests with coverage report (fails under 85%)
	uv run pytest --cov --cov-report=term-missing

check: lint typecheck test ## Run all quality gates

run: ## Diagnose a scenario (make run SCENARIO=crashloop)
	uv run incident-copilot diagnose --scenario $(SCENARIO)

evals: ## Run the agentic evaluation harness on all scenarios
	uv run incident-copilot evals --all

docker-build: ## Build the Docker image
	docker build -t incident-copilot:latest .

docker-run: ## Run the demo inside Docker
	docker compose run --rm app

clean: ## Remove caches and build artifacts
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
