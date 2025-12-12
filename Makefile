# ============================================================================
# Run-Density Makefile - Local-only Docker Development
# Issue #466 Step 4: Simplified to 3 core commands (dev, e2e-local, test)
# ============================================================================

# -------- Configuration --------
PORT ?= 8080

# -------- Phony targets --------
.PHONY: help usage --help dev e2e-local test stop build validate-output validate-all test-v2

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
	@echo "  test                Run smoke tests (health checks + API validation)"
	@echo "  test-v2             Test v2 analysis API (sat + sun events, no reload mode)"
	@echo "  e2e-local           Run full end-to-end test suite (generates all artifacts)"
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

e2e-local: ## Run end-to-end tests (local-only)
	@echo "🧪 Running E2E tests (local mode)..."
	@docker-compose down
	@echo "GCS_UPLOAD=false" > .env.override
	@docker-compose --env-file .env.override up -d
	@rm -f .env.override
	@echo "⏳ Waiting for container startup (5s)..."
	@sleep 5
	@echo "▶️  Running E2E test suite..."
	@docker exec run-density-dev python /app/e2e.py --local

test: ## Run smoke tests (health checks + API validation)
	@echo "🧪 Running smoke tests..."
	@curl -fsS "http://localhost:$(PORT)/health" | jq -e '.ok==true' >/dev/null && echo "✅ Health OK" || (echo "❌ Health FAILED" && exit 1)
	@curl -fsS "http://localhost:$(PORT)/ready"  | jq -e '.ok==true' >/dev/null && echo "✅ Ready OK" || (echo "❌ Ready FAILED" && exit 1)
	@curl -fsS "http://localhost:$(PORT)/api/dashboard/summary" | jq -e '.peak_density >= 0' >/dev/null && echo "✅ Dashboard OK" || (echo "❌ Dashboard FAILED" && exit 1)
	@curl -fsS "http://localhost:$(PORT)/api/density/segments" | jq -e 'length > 0' >/dev/null && echo "✅ Density API OK" || (echo "❌ Density API FAILED" && exit 1)
	@echo "🎉 All smoke tests passed"

test-v2: ## Test v2 analysis API (sat + sun events, no reload mode)
	@bash scripts/test_v2_analysis.sh

validate-output: ## Validate output integrity for latest run
	@echo "🔍 Validating output integrity..."
	@docker exec run-density-dev python -m app.tests.validate_output

validate-all: ## Validate all runs in index.json
	@echo "🔍 Validating all runs..."
	@docker exec run-density-dev python -m app.tests.validate_output --all
