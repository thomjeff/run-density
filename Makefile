# ============================================================================
# Run-Density Makefile - Local-only Docker Development
# Issue #466 Step 4: Simplified to 3 core commands (dev, e2e-local, test)
# ============================================================================

# -------- Configuration --------
PORT ?= 8080

# -------- Phony targets --------
.PHONY: help dev e2e-local test stop-docker build-docker

# -------- Use same shell for multi-line targets --------
.ONESHELL:

# -------- Help --------
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo ""
	@echo "🐳 Run-Density - Local Docker Development"
	@echo ""
	@echo "Core Commands (Issue #466 Step 4):"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
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
	@echo "⏳ Waiting for container startup (15s)..."
	@sleep 15
	@echo "▶️  Running E2E test suite..."
	@docker exec run-density-dev python /app/e2e.py --local

test: ## Run smoke tests (health checks + API validation)
	@echo "🧪 Running smoke tests..."
	@curl -fsS "http://localhost:$(PORT)/health" | jq -e '.ok==true' >/dev/null && echo "✅ Health OK" || (echo "❌ Health FAILED" && exit 1)
	@curl -fsS "http://localhost:$(PORT)/ready"  | jq -e '.ok==true' >/dev/null && echo "✅ Ready OK" || (echo "❌ Ready FAILED" && exit 1)
	@curl -fsS "http://localhost:$(PORT)/api/dashboard/summary" | jq -e '.peak_density >= 0' >/dev/null && echo "✅ Dashboard OK" || (echo "❌ Dashboard FAILED" && exit 1)
	@curl -fsS "http://localhost:$(PORT)/api/density/segments" | jq -e 'length > 0' >/dev/null && echo "✅ Density API OK" || (echo "❌ Density API FAILED" && exit 1)
	@echo "🎉 All smoke tests passed"

# ============================================================================
# Legacy Aliases (Issue #466 Step 4: Maintained for backwards compatibility)
# ============================================================================

dev-docker: dev  ## Alias for 'make dev'
stop-docker: stop  ## Alias for 'make stop'
build-docker: build  ## Alias for 'make build'
e2e-local-docker: e2e-local  ## Alias for 'make e2e-local'
smoke-docker: test  ## Alias for 'make test'
e2e-docker: e2e-local  ## Alias for 'make e2e-local'
