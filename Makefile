.PHONY: help install install-dev test chat web clean lint format setup hygiene audit

help:  ## Show this help message
	@echo "MaSoVa Agent - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	python3 -m pip install -r requirements.txt

install-dev:  ## Install development dependencies
	python3 -m pip install -r requirements.txt
	python3 -m pip install -e ".[dev]"

test:  ## Run all tests
	./scripts/run-tests.sh

chat:  ## Start interactive chat
	./scripts/start-chat.sh

web:  ## Start web UI
	./scripts/start-web.sh

clean:  ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ 2>/dev/null || true

lint:  ## Format, flake8, and mypy (CI gates)
	black --check src tests
	flake8 src tests --show-source --statistics
	mypy src

format:  ## Format code with black
	black src/ tests/

hygiene:  ## Fail if secrets or local-only files are tracked
	bash scripts/check-hygiene.sh

audit:  ## Dependency vulnerability scan
	pip-audit -r requirements.txt --progress-spinner off

setup:  ## First-time setup
	@echo "Setting up MaSoVa Agent..."
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -r requirements.txt
	. .venv/bin/activate && pip install -e . --no-deps
	@if [ ! -f .env ]; then cp config/env.example .env; echo "Created .env from config/env.example"; fi
	@echo "Setup complete. Edit .env with real keys. Run: source .venv/bin/activate && make test"
