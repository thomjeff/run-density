# ============================================================================
# Run-Density Makefile - Local-only Docker Development
# Issue #466 Step 4: Simplified to 3 core commands (dev, e2e-local, test)
# ============================================================================

# -------- Configuration --------
PORT ?= 8080

# -------- Phony targets --------
.PHONY: help usage --help dev e2e e2e-full e2e-sat e2e-sun stop build validate-output validate-all

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
	@echo "  validate-output     Validate output integrity for latest run"
	@echo "  validate-all        Validate output for all runs in index.json"
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
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sat_sun_scenario -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && docker-compose down && exit 1)
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
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py -v --base-url http://localhost:8080 || (echo "❌ E2E tests failed" && docker-compose down && exit 1)
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
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_saturday_only_scenario -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && docker-compose down && exit 1)
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
	@docker exec run-density-dev python -m pytest tests/v2/e2e.py::TestV2E2EScenarios::test_sunday_only_scenario -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && docker-compose down && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

validate-output: ## Validate output integrity for latest run
	@echo "🔍 Validating output integrity..."
	@docker exec run-density-dev python -m app.tests.validate_output

validate-all: ## Validate all runs in index.json
	@echo "🔍 Validating all runs..."
	@docker exec run-density-dev python -m app.tests.validate_output --all
