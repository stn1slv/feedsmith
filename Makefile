.DEFAULT_GOAL := help
.PHONY: help setup test lint format build run clean upgrade-deps

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies
	uv sync

test: ## Run unit tests
	uv run pytest

lint: ## Run linters and static analysis
	uv run ruff check src tests
	uv run mypy src

format: ## Auto-format code
	uv run ruff format src tests
	uv run ruff check --fix src tests

build: ## Build the package
	uv build

run: ## Run the CLI (pass ARGS="generate boomi")
	uv run feedsmith $(ARGS)

clean: ## Remove build and cache artifacts
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

upgrade-deps: ## Upgrade all dependencies to latest versions
	uv lock --upgrade
