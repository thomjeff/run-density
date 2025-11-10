# -------- Configuration --------
PORT ?= 8080
BASE ?= http://localhost:$(PORT)

# Issue #465: Cloud Run references disabled during Phase 0 (Disable Cloud CI)
# Cloud Run BASE can be overridden per-run:
# make smoke-docker BASE=https://run-density-ln4r3sfkha-uc.a.run.app

# -------- Phony targets --------
.PHONY: help dev-docker stop-docker build-docker smoke-docker e2e-docker e2e-local-docker

# Issue #447: Use same shell for all lines in e2e targets (required for environment variables)
.ONESHELL:

# -------- Help --------
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo ""
	@echo "🐳 Run-Density - Docker Development Makefile"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Configuration:"
	@echo "  PORT=$(PORT)  (Docker container port)"
	@echo "  BASE=$(BASE)"
	@echo ""
	@echo "Examples:"
	@echo "  make dev-docker              # Start development container"
	@echo "  make e2e-docker              # Run E2E test (default to local)"
	@echo "  make e2e-local-docker        # Run E2E test (local, filesystem)"
	@echo "  make smoke-docker            # Quick health check"
	@echo "  make stop-docker             # Stop container"
	@echo ""

# -------- Docker Development --------
dev-docker: ## Start Docker container for local development (hot reload enabled)
	@echo ">> Starting Docker container for local development"
	@echo ">> Container will run on http://localhost:8080"
	@docker-compose up --build

stop-docker: ## Stop and remove Docker container
	@echo ">> Stopping Docker container"
	@docker-compose down

build-docker: ## Build Docker image without starting container
	@echo ">> Building Docker image"
	@docker-compose build

smoke-docker: ## Run smoke tests (health, ready, API endpoints)
	@echo ">> Running smoke tests against Docker container"
	@echo ">> Hitting http://localhost:8080"
	@curl -fsS "http://localhost:8080/health" | jq -e '.ok==true' >/dev/null && echo "health OK" || (echo "health FAILED" && exit 1)
	@curl -fsS "http://localhost:8080/ready"  | jq -e '.ok==true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready  OK" || (echo "ready FAILED" && exit 1)
	@echo ">> Testing API endpoints"
	@curl -fsS "http://localhost:8080/api/segments" | jq -e '.segments | length > 0' >/dev/null && echo "segments OK" || (echo "segments FAILED" && exit 1)
	@curl -fsS "http://localhost:8080/api/density/segments" | jq -e 'length > 0' >/dev/null && echo "density/segments OK" || (echo "density/segments FAILED" && exit 1)
	@curl -fsS "http://localhost:8080/api/dashboard/summary" | jq -e '.segments_total >= 0' >/dev/null && echo "dashboard OK" || (echo "dashboard FAILED" && exit 1)
	@echo "✅ smoke-docker passed"

e2e-docker: ## Run e2e.py inside Docker container
	@echo ">> Running E2E tests inside Docker container (default to local)"
	@docker exec run-density-dev python /app/e2e.py --local

e2e-local-docker: ## Run e2e --local (local container, filesystem storage)
	@echo ">> Restarting container with local mode (filesystem storage)"
	docker-compose down
	echo "GCS_UPLOAD=false" > .env.override
	docker-compose --env-file .env.override up -d
	rm -f .env.override
	echo ">> Waiting for container to be ready (15s)..."
	sleep 15
	echo ">> Running E2E tests in local mode"
	docker exec run-density-dev python /app/e2e.py --local

# Issue #465: Cloud targets disabled during Phase 0 (Disable Cloud CI)
# Uncomment if GCS or Cloud Run testing is needed in the future
#
# e2e-staging-docker: ## Run e2e --local with GCS (local container, GCS storage)
# 	@echo ">> Restarting container with staging mode (GCS storage)"
# 	docker-compose down
# 	echo "GCS_UPLOAD=true" > .env.override
# 	echo "GOOGLE_CLOUD_PROJECT=run-density" >> .env.override
# 	echo "GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json" >> .env.override
# 	docker-compose --env-file dev.env --env-file .env.override up -d
# 	rm -f .env.override
# 	echo ">> Waiting for container to be ready (15s)..."
# 	sleep 15
# 	echo ">> Running E2E tests in staging mode (local code, GCS storage)"
# 	docker exec run-density-dev python /app/e2e.py --local
# 	echo ">> Note: Container is now in GCS mode. Run 'make e2e-local-docker' to restore filesystem mode."
#
# e2e-prod-gcp: ## Run e2e --cloud (tests Cloud Run production)
# 	@echo ">> Testing Cloud Run production (requires running container)"
# 	@docker exec run-density-dev python /app/e2e.py --cloud
