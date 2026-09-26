.PHONY: install dev test lint format clean sweep start stop backup docs

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

sweep:
	@echo "Menyapu Sandbox: Menghapus script eksperimen (lebih dari 7 hari) di operasional/sandbox/..."
	find $(ROOT)/operasional/sandbox/ -type f -mtime +7 -exec rm -f {} + 2>/dev/null || true
	@echo "Menyapu Logs: Menghapus log (lebih dari 30 hari) di output/logs/..."
	find $(ROOT)/output/logs/ -type f -name "*.log" -mtime +30 -exec rm -f {} + 2>/dev/null || true
	@echo "Pemeliharaan rutin struktur MCP selesai!"

start:
	bash $(ROOT)/scripts/start-all.sh

stop:
	bash $(ROOT)/scripts/stop-all.sh

backup:
	bash $(ROOT)/scripts/backup.sh

docs:
	@echo "Documentation is in README.md, ARCHITECTURE.md, MEMORY.md, KNOWLEDGE.md,"
	@echo "SKILLS.md, SECURITY.md, DEPLOYMENT.md, ROADMAP.md and TASKS.md."
