# ============================================================================
# Run-Density Makefile - Local-only Docker Development
# Issue #466 Step 4: Simplified to 3 core commands (dev, e2e-local, test)
# ============================================================================

# -------- Configuration --------
PORT ?= 8080

# -------- Phony targets --------
.PHONY: help usage --help dev e2e e2e-full e2e-sat e2e-sun e2e-coverage-lite stop build validate-output validate-all prune-runs

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
	@echo "  e2e-sat             Run Saturday-only E2E test (~2 min)"
	@echo "  e2e-sun             Run Sunday-only E2E test (~2 min)"
	@echo "  e2e-coverage-lite   Run E2E with coverage (DAY=sat|sun|both), save to runflow/<run_id>/coverage"
	@echo "  validate-output     Validate output integrity for latest run"
	@echo "  validate-all        Validate output for all runs in index.json"
	@echo "  prune-runs          Prune old run_ids, keeping last N (KEEP=n, --dry-run for preview)"
	@echo ""
	@echo "Configuration:"
	@echo "  PORT=$(PORT)  (Docker container port)"
	@echo ""

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

e2e: ## Run sat+sun E2E test (single run_id with both days)
	@echo "🧪 Running sat+sun E2E test..."
	@echo "🛑 Stopping existing containers (if any)..."
	@docker-compose down 2>/dev/null || true
	@echo "🛑 Stopping any containers using port 8080..."
	@for container in $$(docker ps --filter "publish=8080" --format "{{.Names}}" 2>/dev/null); do \
		docker stop $$container 2>/dev/null || true; \
	done
	@for container in $$(docker ps -a --filter "name=run-density" --format "{{.Names}}" 2>/dev/null); do \
		docker rm -f $$container 2>/dev/null || true; \
	done
	@echo "📦 Starting docker-compose services..."
	@docker-compose up -d --build
	@echo "⏳ Waiting for server to be ready (10s)..."
	@sleep 10
	@echo "▶️  Running pytest test_sat_sun_scenario..."
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sat_sun_scenario -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-full: ## Run full E2E test suite (all scenarios)
	@echo "🧪 Running v2 E2E tests..."
	@echo "🛑 Stopping existing containers (if any)..."
	@docker-compose down 2>/dev/null || true
	@echo "🛑 Stopping any containers using port 8080..."
	@for container in $$(docker ps --filter "publish=8080" --format "{{.Names}}" 2>/dev/null); do \
		docker stop $$container 2>/dev/null || true; \
	done
	@for container in $$(docker ps -a --filter "name=run-density" --format "{{.Names}}" 2>/dev/null); do \
		docker rm -f $$container 2>/dev/null || true; \
	done
	@echo "📦 Starting docker-compose services..."
	@docker-compose up -d --build
	@echo "⏳ Waiting for server to be ready (10s)..."
	@sleep 10
	@echo "▶️  Running pytest tests/v2/e2e.py..."
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py -v --base-url http://localhost:8080 || (echo "❌ E2E tests failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E tests completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-sat: ## Run Saturday-only E2E test
	@echo "🧪 Running Saturday-only E2E test..."
	@echo "🛑 Stopping existing containers (if any)..."
	@docker-compose down 2>/dev/null || true
	@echo "🛑 Stopping any containers using port 8080..."
	@for container in $$(docker ps --filter "publish=8080" --format "{{.Names}}" 2>/dev/null); do \
		docker stop $$container 2>/dev/null || true; \
	done
	@for container in $$(docker ps -a --filter "name=run-density" --format "{{.Names}}" 2>/dev/null); do \
		docker rm -f $$container 2>/dev/null || true; \
	done
	@echo "📦 Starting docker-compose services..."
	@docker-compose up -d --build
	@echo "⏳ Waiting for server to be ready (10s)..."
	@sleep 10
	@echo "▶️  Running pytest test_saturday_only_scenario..."
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_saturday_only_scenario -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-sun: ## Run Sunday-only E2E test
	@echo "🧪 Running Sunday-only E2E test..."
	@echo "🛑 Stopping existing containers (if any)..."
	@docker-compose down 2>/dev/null || true
	@echo "🛑 Stopping any containers using port 8080..."
	@for container in $$(docker ps --filter "publish=8080" --format "{{.Names}}" 2>/dev/null); do \
		docker stop $$container 2>/dev/null || true; \
	done
	@for container in $$(docker ps -a --filter "name=run-density" --format "{{.Names}}" 2>/dev/null); do \
		docker rm -f $$container 2>/dev/null || true; \
	done
	@echo "📦 Starting docker-compose services..."
	@docker-compose up -d --build
	@echo "⏳ Waiting for server to be ready (10s)..."
	@sleep 10
	@echo "▶️  Running pytest test_sunday_only_scenario..."
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sunday_only_scenario -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-coverage-lite: ## Run E2E with coverage (DAY=sat|sun|both) and save reports under runflow/<run_id>/coverage
	@echo "🧪 Running coverage-instrumented sat+sun E2E (lite)..."
	@echo "🛑 Stopping existing containers (if any)..."
	@docker-compose down 2>/dev/null || true
	@echo "🛑 Stopping any containers using port 8080..."
	@for container in $$(docker ps --filter "publish=8080" --format "{{.Names}}" 2>/dev/null); do \
		docker stop $$container 2>/dev/null || true; \
	done
	@for container in $$(docker ps -a --filter "name=run-density" --format "{{.Names}}" 2>/dev/null); do \
		docker rm -f $$container 2>/dev/null || true; \
	done
	@echo "📦 Starting docker-compose services..."
	@docker-compose up -d --build
	@echo "⏳ Waiting for server to be ready (10s)..."
	@sleep 10
	@echo "📦 Ensuring coverage is available in container..."
	@docker exec run-density-dev python -m pip install --quiet coverage || (echo "⚠️ Container not ready, waiting..." && sleep 5 && docker exec run-density-dev python -m pip install --quiet coverage)
	@echo "🔄 Restarting container to launch server under coverage..."
	@docker-compose restart app || true
	@echo "⏳ Waiting for server to be ready (20s)..."
	@sleep 20
	@echo "🔍 Verifying container is running and server is responding..."
	@for i in $$(seq 1 10); do \
		if docker exec run-density-dev curl -s http://localhost:8080/health >/dev/null 2>&1; then \
			echo "✅ Server is responding"; \
			break; \
		else \
			echo "⏳ Waiting for server to respond (attempt $$i/10)..."; \
			sleep 2; \
		fi; \
	done
	@if ! docker exec run-density-dev curl -s http://localhost:8080/health >/dev/null 2>&1; then \
		echo "❌ Server not responding after 20s"; \
		docker logs run-density-dev --tail 50; \
		docker-compose down; \
		exit 1; \
	fi
	@echo "▶️  Selecting scenario based on DAY (sat|sun|both)..."
	@scenario=$$( \
		if [ "$${DAY}" = "sat" ]; then \
			echo "tests/v2/e2e.py::TestV2E2EScenarios::test_saturday_only_scenario"; \
		elif [ "$${DAY}" = "sun" ]; then \
			echo "tests/v2/e2e.py::TestV2E2EScenarios::test_sunday_only_scenario"; \
		else \
			echo "tests/v2/e2e.py::TestV2E2EScenarios::test_sat_sun_scenario"; \
		fi \
	); \
	echo "▶️  Running pytest $$scenario under coverage..."; \
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage run -m pytest $$scenario -v --base-url http://localhost:8080 || (echo "❌ Coverage run failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "🧮 Combining coverage data..."
	@docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage combine || echo "⚠️  No parallel coverage files to combine (using existing .coverage)"
	@run_id=$$(docker exec run-density-dev python -c "import json, pathlib; latest=pathlib.Path('/app/runflow/latest.json'); data=json.loads(latest.read_text()) if latest.exists() else {}; print(data.get('run_id','latest'))"); \
	echo "📂 Using run_id=$$run_id for coverage outputs"; \
	docker exec run-density-dev mkdir -p /app/runflow/$$run_id/coverage ;\
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage json -o /app/runflow/$$run_id/coverage/e2e-coverage.json ;\
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage html -d /app/runflow/$$run_id/coverage/html ;\
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage report -m --skip-empty || true ;\
	echo "✅ Coverage artifacts written to runflow/$$run_id/coverage"; \
	echo "💡 Container still running. Use 'make stop' to stop it."

validate-output: ## Validate output integrity for latest run
	@echo "🔍 Validating output integrity..."
	@docker exec run-density-dev python -m app.tests.validate_output

validate-all: ## Validate all runs in index.json
	@echo "🔍 Validating all runs..."
	@docker exec run-density-dev python -m app.tests.validate_output --all

prune-runs: ## Prune old run_ids, keeping last N (KEEP=n required, --dry-run for preview)
	@if [ -z "$(KEEP)" ]; then \
		echo "❌ Error: KEEP parameter required (e.g., make prune-runs KEEP=10)"; \
		exit 1; \
	fi
	@docker-compose exec app python -m app.utils.prune_runs --keep $(KEEP) $(if $(DRY_RUN),--dry-run,) $(if $(CONFIRM),--confirm,)
