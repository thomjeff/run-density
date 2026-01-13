# Refactored Makefile

## Complete Refactored Makefile

```makefile
# ============================================================================
# Run-Density Makefile - Local-only Docker Development
# Issue #466 Step 4: Simplified to 3 core commands (dev, e2e-local, test)
# ============================================================================

# -------- Configuration --------
PORT ?= 8080
ENABLE_AUDIT ?= n  # Default to "n" (matches e2e.py default), override with ENABLE_AUDIT=y
CONTAINER_NAME := run-density-dev
BASE_URL := http://localhost:8080
PYTEST_ARGS := -v --base-url $(BASE_URL)

# -------- Phony targets --------
.PHONY: help usage --help dev e2e e2e-full e2e-sat e2e-sun e2e-coverage-lite stop build validate-output validate-all prune-runs clean-containers start-services

# -------- Use same shell for multi-line targets --------
.ONESHELL:

# -------- Help --------
.DEFAULT_GOAL := help

help usage --help: ## Show this help message
	@echo ""
	@echo "🐳 Run-Density - Local Docker Development"
	@echo ""
	@echo "Core Commands (Post-Phase 2 Architecture):"
	@echo ""
	@echo "  help                Show this help message"
	@echo "  dev                 Start local development server (hot reload enabled)"
	@echo "  stop                Stop Docker container"
	@echo "  build               Build Docker image"
	@echo "  e2e                 Run sat+sun E2E test (single run_id with both days)"
	@echo "  e2e-full            Run full E2E test suite (all scenarios)"
	@echo "  e2e-sat              Run Saturday-only E2E test (~2 min)"
	@echo "  e2e-sun              Run Sunday-only E2E test (~2 min)"
	@echo "  e2e-coverage-lite   Run E2E with coverage (DAY=sat|sun|both), save to runflow/<run_id>/coverage"
	@echo "  validate-output     Validate output integrity for latest run"
	@echo "  validate-all        Validate output for all runs in index.json"
	@echo "  prune-runs          Prune old run_ids, keeping last N (KEEP=n, --dry-run for preview)"
	@echo ""
	@echo "Configuration:"
	@echo "  PORT=$(PORT)  (Docker container port)"
	@echo "  ENABLE_AUDIT=$(ENABLE_AUDIT)  (Default: n, set ENABLE_AUDIT=y to enable audit)"
	@echo ""
	@echo "Note: E2E tests support ENABLE_AUDIT flag to control audit generation."
	@echo "      To disable audit (faster runs, default): make e2e"
	@echo "      To enable audit:                        make e2e ENABLE_AUDIT=y"
	@echo "      Applies to: e2e, e2e-sat"
	@echo ""

# ============================================================================
# Helper Targets (Internal)
# ============================================================================

clean-containers: ## Clean up existing containers (internal helper)
	@echo "🛑 Stopping existing containers (if any)..."
	@docker-compose down 2>/dev/null || true
	@echo "🛑 Stopping any containers using port $(PORT)..."
	@for container in $$(docker ps --filter "publish=$(PORT)" --format "{{.Names}}" 2>/dev/null); do \
		docker stop $$container 2>/dev/null || true; \
	done
	@for container in $$(docker ps -a --filter "name=$(CONTAINER_NAME)" --format "{{.Names}}" 2>/dev/null); do \
		docker rm -f $$container 2>/dev/null || true; \
	done

start-services: clean-containers ## Start docker-compose services (internal helper)
	@echo "📦 Starting docker-compose services..."
	@docker-compose up -d --build
	@echo "⏳ Waiting for server to be ready (10s)..."
	@sleep 10

# ============================================================================
# Core Commands
# ============================================================================

dev: ## Start local development server (hot reload enabled)
	@echo "🚀 Starting local development server..."
	@echo "📍 http://localhost:$(PORT)"
	@docker-compose up --build

stop: ## Stop Docker container
	@echo "🛑 Stopping container..."
	@docker-compose down

build: ## Build Docker image
	@echo "🔨 Building Docker image..."
	@docker-compose build

e2e: ## Run sat+sun E2E test (single run_id with both days). Usage: make e2e ENABLE_AUDIT=y
	@echo "🧪 Running sat+sun E2E test (enableAudit=$(ENABLE_AUDIT))..."
	@$(MAKE) start-services
	@echo "▶️  Running pytest test_sat_sun..."
	@docker exec $(CONTAINER_NAME) python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sat_sun $(PYTEST_ARGS) --enable-audit $(ENABLE_AUDIT) || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-full: ## Run full E2E test suite (all scenarios)
	@echo "🧪 Running v2 E2E tests..."
	@$(MAKE) start-services
	@echo "▶️  Running pytest tests/v2/e2e.py..."
	@docker exec $(CONTAINER_NAME) python -m pytest tests/v2/e2e.py $(PYTEST_ARGS) || (echo "❌ E2E tests failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E tests completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-sat: ## Run Saturday-only E2E test. Usage: make e2e-sat ENABLE_AUDIT=y
	@echo "🧪 Running Saturday-only E2E test (enableAudit=$(ENABLE_AUDIT))..."
	@$(MAKE) start-services
	@echo "▶️  Running pytest test_sat..."
	@docker exec $(CONTAINER_NAME) python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sat $(PYTEST_ARGS) --enable-audit $(ENABLE_AUDIT) || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-sun: ## Run Sunday-only E2E test
	@echo "🧪 Running Sunday-only E2E test..."
	@$(MAKE) start-services
	@echo "▶️  Running pytest test_sun..."
	@docker exec $(CONTAINER_NAME) python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sun $(PYTEST_ARGS) || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-coverage-lite: ## Run E2E with coverage (DAY=sat|sun|both) and save reports under runflow/<run_id>/coverage
	@echo "🧪 Running coverage-instrumented sat+sun E2E (lite)..."
	@$(MAKE) start-services
	@echo "📦 Ensuring coverage is available in container..."
	@docker exec $(CONTAINER_NAME) python -m pip install --quiet coverage || (echo "⚠️ Container not ready, waiting..." && sleep 5 && docker exec $(CONTAINER_NAME) python -m pip install --quiet coverage)
	@echo "🔄 Restarting container to launch server under coverage..."
	@docker-compose restart app || true
	@echo "⏳ Waiting for server to be ready (20s)..."
	@sleep 20
	@echo "🔍 Verifying container is running and server is responding..."
	@for i in $$(seq 1 10); do \
		if docker exec $(CONTAINER_NAME) curl -s http://localhost:8080/health >/dev/null 2>&1; then \
			echo "✅ Server is responding"; \
			break; \
		else \
			echo "⏳ Waiting for server to respond (attempt $$i/10)..."; \
			sleep 2; \
		fi; \
	done
	@if ! docker exec $(CONTAINER_NAME) curl -s http://localhost:8080/health >/dev/null 2>&1; then \
		echo "❌ Server not responding after 20s"; \
		docker logs $(CONTAINER_NAME) --tail 50; \
		docker-compose down; \
		exit 1; \
	fi
	@echo "▶️  Selecting scenario based on DAY (sat|sun|both)..."
	@scenario=$$( \
		if [ "$${DAY}" = "sat" ]; then \
			echo "tests/v2/e2e.py::TestV2E2EScenarios::test_sat"; \
		elif [ "$${DAY}" = "sun" ]; then \
			echo "tests/v2/e2e.py::TestV2E2EScenarios::test_sun"; \
		else \
			echo "tests/v2/e2e.py::TestV2E2EScenarios::test_sat_sun"; \
		fi \
	); \
	echo "▶️  Running pytest $$scenario under coverage..."; \
	docker exec $(CONTAINER_NAME) env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage run -m pytest $$scenario $(PYTEST_ARGS) || (echo "❌ Coverage run failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "🧮 Combining coverage data..."
	@docker exec $(CONTAINER_NAME) env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage combine || echo "⚠️  No parallel coverage files to combine (using existing .coverage)"
	@run_id=$$(docker exec $(CONTAINER_NAME) python -c "import json, pathlib; latest=pathlib.Path('/app/runflow/analysis/latest.json'); data=json.loads(latest.read_text()) if latest.exists() else {}; print(data.get('run_id','latest'))"); \
	echo "📂 Using run_id=$$run_id for coverage outputs"; \
	docker exec $(CONTAINER_NAME) mkdir -p /app/runflow/analysis/$$run_id/coverage ;\
	docker exec $(CONTAINER_NAME) env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage json -o /app/runflow/analysis/$$run_id/coverage/e2e-coverage.json ;\
	docker exec $(CONTAINER_NAME) env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage html -d /app/runflow/analysis/$$run_id/coverage/html ;\
	docker exec $(CONTAINER_NAME) env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage report -m --skip-empty || true ;\
	echo "✅ Coverage artifacts written to runflow/analysis/$$run_id/coverage"; \
	echo "💡 Container still running. Use 'make stop' to stop it."

validate-output: ## Validate output integrity for latest run
	@echo "🔍 Validating output integrity..."
	@docker exec $(CONTAINER_NAME) python -m app.tests.validate_output

validate-all: ## Validate all runs in index.json
	@echo "🔍 Validating all runs..."
	@docker exec $(CONTAINER_NAME) python -m app.tests.validate_output --all

prune-runs: ## Prune old run_ids, keeping last N (KEEP=n required, --dry-run for preview)
	@if [ -z "$(KEEP)" ]; then \
		echo "❌ Error: KEEP parameter required (e.g., make prune-runs KEEP=10)"; \
		exit 1; \
	fi
	@docker-compose exec app python -m app.utils.prune_runs --keep $(KEEP) $(if $(DRY_RUN),--dry-run,) $(if $(CONFIRM),--confirm,)
```
