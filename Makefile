# Development commands. Every target runs without credentials or dataset access.
.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help install test lint format schemas check check-policy serve demo

help: ## List the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install the locked dependencies
	$(UV) sync --locked

test: ## Run the test suite
	$(UV) run pytest

lint: ## Check lint and formatting
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Apply formatting and safe lint fixes
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

schemas: ## Export the JSON Schema of the boundary models to docs/schemas
	$(UV) run python -m scripts.export_schemas

check: lint test check-policy ## Run every check that CI runs
	$(UV) run python -m scripts.export_schemas --check
	$(UV) run python scripts/check_publication.py

check-policy: ## Check the executable policy; set VERA_MASTER_POLICY to compare it with the master policy
	$(UV) run python -m scripts.check_policy

serve: ## Run the API locally with reload, mock adapter and rules interpreter
	$(UV) run uvicorn api.main:app --reload --port 8000

demo: ## Build and start the containers of the local demo (no credentials)
	docker compose up --build
