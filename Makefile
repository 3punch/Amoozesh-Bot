# ==============================================================================
# Amoozesh-Bot — Makefile برای developرها
# ==============================================================================

.PHONY: install test lint type-check sec format clean run verify

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e ".[dev]"

test:
	pytest tests -v --cov=src --cov-report=term-missing

lint:
	ruff check src tests
	ruff format --check src tests

type-check:
	mypy src

sec:
	bandit -r src -q

format:
	ruff check --fix src tests
	ruff format src tests

verify:
	python scripts/verify_imports.py

clean:
	rm -rf __pycache__ src/**/__pycache__ tests/**/__pycache__ .pytest_cache .ruff_cache htmlcov .coverage

run:
	python EntekhabVahedBot.py

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'