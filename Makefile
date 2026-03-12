.PHONY: install test test-unit test-integration lint format check clean run

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev,all-providers]"

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# ── Testes ─────────────────────────────────────────────────────────────────────
test: test-unit

test-unit:
	pytest tests/unit/ -v --tb=short -m "not integration"

test-integration:
	pytest tests/integration/ -v --tb=short -m "integration" --no-cov

test-all:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/unit/ \
		--cov=aiadapter \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		-m "not integration"
	@echo "Relatório HTML em: htmlcov/index.html"

# ── Qualidade de código ────────────────────────────────────────────────────────
lint:
	ruff check aiadapter/ tests/

lint-fix:
	ruff check aiadapter/ tests/ --fix

format:
	black aiadapter/ tests/

format-check:
	black --check --diff aiadapter/ tests/

check: lint format-check
	@echo "Verificação concluída!"

# ── Servidor ───────────────────────────────────────────────────────────────────
run:
	python main.py

run-dev:
	uvicorn aiadapter.api.main:app --reload --host 0.0.0.0 --port 8000

# ── Limpeza ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "coverage.xml" -delete 2>/dev/null || true
	@echo "Limpeza concluída!"
