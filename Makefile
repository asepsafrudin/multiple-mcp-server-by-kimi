.PHONY: install dev test lint format clean start stop backup docs

ROOT := $(shell pwd)
VENV := $(ROOT)/.venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3.12 -m venv $(VENV) || true
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

dev:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(VENV)/bin/ruff check shared servers tests scripts
	$(VENV)/bin/ruff format --check shared servers tests scripts

format:
	$(VENV)/bin/ruff check --fix shared servers tests scripts
	$(VENV)/bin/ruff format shared servers tests scripts

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true

start:
	bash $(ROOT)/scripts/start-all.sh

stop:
	bash $(ROOT)/scripts/stop-all.sh

backup:
	bash $(ROOT)/scripts/backup.sh

docs:
	@echo "Documentation is in README.md, ARCHITECTURE.md, MEMORY.md, KNOWLEDGE.md,"
	@echo "SKILLS.md, SECURITY.md, DEPLOYMENT.md, ROADMAP.md and TASKS.md."
