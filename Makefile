# Developer commands for Amoozesh-Bot.

.PHONY: install test lint type-check sec format clean run verify

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

test:
	pytest tests -v --cov-fail-under=70

lint:
	ruff check *.py src tests scripts
	ruff format --check *.py src tests scripts

type-check:
	mypy src

sec:
	bandit -r src -q

format:
	ruff check --fix src tests scripts
	ruff format src tests scripts

verify:
	python scripts/verify_imports.py

clean:
	rm -rf __pycache__ src/**/__pycache__ tests/**/__pycache__ .pytest_cache .ruff_cache htmlcov .coverage

run:
	python EntekhabVahedBot.py
