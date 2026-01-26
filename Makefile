# ============================================================================
# Run-Density Makefile - Local-only Docker Development
# ============================================================================

# -------- Configuration --------
PORT ?= 8080

# Cloud (skinny UI) configuration
CLOUD_PROJECT_ID ?= runflow-485519
CLOUD_REGION ?= us-central1
CLOUD_AR_REPO ?= runflow-cloud
CLOUD_IMAGE_NAME ?= runflow-cloud
CLOUD_SERVICE_PREFIX ?= runflow-cloud
RUNFLOW_ROOT ?= /Users/jthompson/Documents/runflow
CLOUD_BUILD_CONTEXT ?= .cloud-build
CLOUD_ENV_FILE ?= cloud.env
CLOUD_BUILD_PLATFORM ?= linux/amd64
CLOUD_PASSWORD ?= $(shell awk -F= '/^DASHBOARD_PASSWORD=/{print $$2; exit}' $(CLOUD_ENV_FILE) 2>/dev/null)
CLOUD_MAX_INSTANCES ?= 1
CLOUD_CPU ?= 1
CLOUD_MEMORY ?= 2Gi

RESOLVED_RUN_ID ?= $(if $(RUN_ID),$(RUN_ID),$(shell python3 -c "import json, pathlib; p=pathlib.Path('$(RUNFLOW_ROOT)/analysis/latest.json'); print(json.loads(p.read_text()).get('run_id','') if p.exists() else '')"))
CLOUD_IMAGE ?= $(CLOUD_REGION)-docker.pkg.dev/$(CLOUD_PROJECT_ID)/$(CLOUD_AR_REPO)/$(CLOUD_IMAGE_NAME):$(RESOLVED_RUN_ID)
CLOUD_SERVICE ?= $(CLOUD_SERVICE_PREFIX)
CLOUD_RUN_PATH ?= $(RUNFLOW_ROOT)/analysis/$(RUN_ID)

# -------- Phony targets --------
.PHONY: help usage --help dev e2e e2e-sat e2e-sun e2e-coverage-lite stop build validate-output validate-all prune-runs ai-prompt cloud-build cloud-run cloud-stop cloud-push cloud-deploy cloud-clean

# -------- Use same shell for multi-line targets --------
.ONESHELL:

# -------- Help --------
.DEFAULT_GOAL := help

help usage --help: ## Show this help message
	@echo ""
	@echo "🐳 Run-Density - Local Docker Development"
	@echo ""
	@echo "Core Commands:"
	@echo ""
	@echo "  help                Show this help message"
	@echo "  dev                 Start Docker container (hot reload enabled)"
	@echo "  stop                Stop Docker container"
	@echo "  build               Build Docker image"
	@echo "  e2e                 Run sat+sun test"
	@echo "  e2e-sat             Run sat test"
	@echo "  e2e-sun             Run sun test"
	@echo "  e2e-coverage-lite   Runs e2e with code coverage metrics"
	@echo "  validate-output     Validate output integrity for latest run"
	@echo "  validate-all        Validate output for all runs in index.json"
	@echo "  prune-runs          Prune old run_ids, keeping last N (KEEP=n, --dry-run for preview)"
	@echo "  ai-prompt           Generate AI prompt for a run_id (RUN_ID=...)"
	@echo ""
	@echo "Configuration:"
	@echo "	PORT=$(PORT)  (Docker container port)"
	@echo "	ENABLE_AUDIT: (Flag to control audit generation.)"
	@echo "	To disable audit (faster runs, default): make e2e"
	@echo "	To enable audit: make e2e ENABLE_AUDIT=y"
	@echo "	Applies to: e2e, e2e-sat, e2e-sun"
	@echo ""
	@echo "Cloud (skinny UI) Commands:"
	@echo ""
	@echo "  cloud-build        Build cloud UI image (RUN_ID=...)"
	@echo "  cloud-run          Run cloud UI locally (HOST_PORT=8081)"
	@echo "  cloud-stop         Stop local cloud UI container"
	@echo "  cloud-push         Push cloud UI image"
	@echo "  cloud-deploy       Deploy to Cloud Run"
	@echo "  cloud-clean        Delete Cloud Run service"
	@echo ""
	@echo "Cloud Defaults:"
	@echo "	CLOUD_PROJECT_ID=$(CLOUD_PROJECT_ID)"
	@echo "	CLOUD_REGION=$(CLOUD_REGION)"
	@echo "	CLOUD_AR_REPO=$(CLOUD_AR_REPO)"
	@echo "	CLOUD_IMAGE_NAME=$(CLOUD_IMAGE_NAME)"
	@echo "	CLOUD_SERVICE_PREFIX=$(CLOUD_SERVICE_PREFIX)"
	@echo "	RUNFLOW_ROOT=$(RUNFLOW_ROOT)"
	@echo "	RESOLVED_RUN_ID=$(RESOLVED_RUN_ID)"
	@echo "	CLOUD_BUILD_CONTEXT=$(CLOUD_BUILD_CONTEXT)"
	@echo "	CLOUD_BUILD_PLATFORM=$(CLOUD_BUILD_PLATFORM)"
	@echo "	CLOUD_ENV_FILE=$(CLOUD_ENV_FILE)"
	@echo "	CLOUD_PASSWORD=$(if $(CLOUD_PASSWORD),***,)"
	@echo "	CLOUD_MAX_INSTANCES=$(CLOUD_MAX_INSTANCES)"
	@echo "	CLOUD_CPU=$(CLOUD_CPU)"
	@echo "	CLOUD_MEMORY=$(CLOUD_MEMORY)"
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

e2e: ENABLE_AUDIT ?= n
e2e: ## Run sat+sun E2E test (single run_id with both days). Usage: make e2e ENABLE_AUDIT=y
	@echo "🧪 Running sat+sun E2E test (enableAudit=$(ENABLE_AUDIT))..."
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
	@echo "▶️  Running pytest test_sat_sun..."
	@docker exec run-density-dev python -m pytest tests/e2e.py::TestV2E2EScenarios::test_sat_sun -v --base-url http://localhost:8080 --enable-audit $(ENABLE_AUDIT) || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "✅ E2E test completed"
	@echo "💡 Container still running. Use 'make stop' to stop it."

e2e-sat: ENABLE_AUDIT ?= n
e2e-sat: ## Run Saturday-only E2E test. Usage: make e2e-sat ENABLE_AUDIT=y
	@echo "🧪 Running Saturday-only E2E test (enableAudit=$(ENABLE_AUDIT))..."
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
	@echo "▶️  Running pytest test_sat..."
	@docker exec run-density-dev python -m pytest tests/e2e.py::TestV2E2EScenarios::test_sat -v --base-url http://localhost:8080 --enable-audit $(ENABLE_AUDIT) || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
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
	@echo "▶️  Running pytest test_sun..."
	@docker exec run-density-dev python -m pytest tests/e2e.py::TestV2E2EScenarios::test_sun -v --base-url http://localhost:8080 || (echo "❌ E2E test failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
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
			echo "tests/e2e.py::TestV2E2EScenarios::test_sat"; \
		elif [ "$${DAY}" = "sun" ]; then \
			echo "tests/e2e.py::TestV2E2EScenarios::test_sun"; \
		else \
			echo "tests/e2e.py::TestV2E2EScenarios::test_sat_sun"; \
		fi \
	); \
	echo "▶️  Running pytest $$scenario under coverage..."; \
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage run -m pytest $$scenario -v --base-url http://localhost:8080 || (echo "❌ Coverage run failed" && echo "💡 Container still running for debugging. Use 'make stop' to stop it." && exit 1)
	@echo "🧮 Combining coverage data..."
	@docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage combine || echo "⚠️  No parallel coverage files to combine (using existing .coverage)"
	@run_id=$$(docker exec run-density-dev python -c "import json, pathlib; latest=pathlib.Path('/app/runflow/analysis/latest.json'); data=json.loads(latest.read_text()) if latest.exists() else {}; print(data.get('run_id','latest'))"); \
	echo "📂 Using run_id=$$run_id for coverage outputs"; \
	docker exec run-density-dev mkdir -p /app/runflow/analysis/$$run_id/coverage ;\
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage json -o /app/runflow/analysis/$$run_id/coverage/e2e-coverage.json ;\
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage html -d /app/runflow/analysis/$$run_id/coverage/html ;\
	docker exec run-density-dev env COVERAGE_RCFILE=/app/coverage.rc COVERAGE_PROCESS_START=/app/coverage.rc COVERAGE_FILE=/app/runflow/.coverage python -m coverage report -m --skip-empty || true ;\
	echo "✅ Coverage artifacts written to runflow/analysis/$$run_id/coverage"; \
	echo "💡 Container still running. Use 'make stop' to stop it."

validate-output: ## Validate output integrity for latest run
	@echo "🔍 Validating output integrity..."
	@docker exec run-density-dev python -m app.tests.validate_output

validate-all: ## Validate all runs in index.json
	@echo "🔍 Validating all runs..."
	@docker exec run-density-dev python -m app.tests.validate_output --all

ai-prompt: ## Generate AI prompt for a run_id (manual mode)
	@if [ -z "$(RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID parameter required (e.g., make ai-prompt RUN_ID=4VwzQWum7DpFCj7r6aZi4s)"; \
		exit 1; \
	fi
	@echo "🧠 Generating AI prompt for run_id=$(RUN_ID)..."
	@docker exec run-density-dev python -m app.utils.ai_analysis prompt --run-id $(RUN_ID) || (echo "❌ Container not running. Start with 'make dev' first." && exit 1)

prune-runs: ## Prune old run_ids, keeping last N (KEEP=n required, --dry-run for preview)
	@if [ -z "$(KEEP)" ]; then \
		echo "❌ Error: KEEP parameter required (e.g., make prune-runs KEEP=10)"; \
		exit 1; \
	fi
	@docker-compose exec app python -m app.utils.prune_runs --keep $(KEEP) $(if $(DRY_RUN),--dry-run,) $(if $(CONFIRM),--confirm,)

# ============================================================================
# Cloud (Skinny UI) Commands
# ============================================================================

cloud-build: ## Build skinny cloud UI image (RUN_ID=...)
	@if [ -z "$(RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID parameter required (e.g., make cloud-build RUN_ID=abc123)"; \
		exit 1; \
	fi
	@if [ ! -d "$(CLOUD_RUN_PATH)" ]; then \
		echo "❌ Error: $(CLOUD_RUN_PATH) not found"; \
		exit 1; \
	fi
	@echo "🐳 Building cloud UI image for RUN_ID=$(RUN_ID)..."
	@rm -rf "$(CLOUD_BUILD_CONTEXT)"
	@mkdir -p "$(CLOUD_BUILD_CONTEXT)/runflow/analysis"
	@cp -R app "$(CLOUD_BUILD_CONTEXT)/"
	@cp -R frontend "$(CLOUD_BUILD_CONTEXT)/"
	@cp Dockerfile.cloud requirements-cloud.txt "$(CLOUD_BUILD_CONTEXT)/"
	@cp -R "$(CLOUD_RUN_PATH)" "$(CLOUD_BUILD_CONTEXT)/runflow/analysis/"
	@docker buildx build --platform $(CLOUD_BUILD_PLATFORM) --load \
		-f "$(CLOUD_BUILD_CONTEXT)/Dockerfile.cloud" \
		--build-arg RUN_ID=$(RUN_ID) \
		-t $(CLOUD_IMAGE) \
		"$(CLOUD_BUILD_CONTEXT)"

cloud-run: HOST_PORT ?= 8081
cloud-run: ## Run cloud UI locally (uses cloud.env, HOST_PORT=8081)
	@if [ -z "$(RESOLVED_RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID not set and latest.json missing (build first)"; \
		exit 1; \
	fi
	@if [ -z "$(CLOUD_PASSWORD)" ]; then \
		echo "❌ Error: DASHBOARD_PASSWORD missing in $(CLOUD_ENV_FILE)"; \
		exit 1; \
	fi
	@echo "🚀 Running cloud UI locally on port $(HOST_PORT)..."
	@docker run --rm -p $(HOST_PORT):8080 --env-file $(CLOUD_ENV_FILE) $(CLOUD_IMAGE)

cloud-stop: ## Stop local cloud UI container
	@if [ -z "$(RESOLVED_RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID not set and latest.json missing (build first)"; \
		exit 1; \
	fi
	@echo "🛑 Stopping cloud UI container for RUN_ID=$(RESOLVED_RUN_ID)..."
	@container_id=$$(docker ps --filter "ancestor=$(CLOUD_IMAGE)" --format "{{.ID}}"); \
	if [ -n "$$container_id" ]; then \
		docker stop $$container_id; \
	else \
		echo "ℹ️  No running container found for image $(CLOUD_IMAGE)"; \
	fi

cloud-push: ## Push skinny cloud UI image (RUN_ID=...)
	@if [ -z "$(RESOLVED_RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID not set and latest.json missing (build first)"; \
		exit 1; \
	fi
	@echo "📦 Pushing cloud UI image: $(CLOUD_IMAGE)"
	@docker push $(CLOUD_IMAGE)

cloud-deploy: ## Deploy skinny cloud UI to Cloud Run (uses cloud.env)
	@if [ -z "$(RESOLVED_RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID not set and latest.json missing (build first)"; \
		exit 1; \
	fi
	@if [ -z "$(CLOUD_PASSWORD)" ]; then \
		echo "❌ Error: DASHBOARD_PASSWORD missing in $(CLOUD_ENV_FILE)"; \
		exit 1; \
	fi
	@echo "🚀 Deploying Cloud Run service: $(CLOUD_SERVICE)"
	@gcloud run deploy $(CLOUD_SERVICE) \
		--image $(CLOUD_IMAGE) \
		--region $(CLOUD_REGION) \
		--project $(CLOUD_PROJECT_ID) \
		--platform managed \
		--max-instances $(CLOUD_MAX_INSTANCES) \
		--cpu $(CLOUD_CPU) \
		--memory $(CLOUD_MEMORY) \
		--allow-unauthenticated \
		--set-env-vars CLOUD_MODE=true,CLOUD_RUN_ID=$(RESOLVED_RUN_ID),DASHBOARD_PASSWORD=$(CLOUD_PASSWORD)

cloud-clean: ## Delete Cloud Run service
	@if [ -z "$(RESOLVED_RUN_ID)" ]; then \
		echo "❌ Error: RUN_ID not set and latest.json missing (build first)"; \
		exit 1; \
	fi
	@echo "🧹 Deleting Cloud Run service: $(CLOUD_SERVICE)"
	@gcloud run services delete $(CLOUD_SERVICE) --region $(CLOUD_REGION) --project $(CLOUD_PROJECT_ID) --quiet || \
		echo "ℹ️  Service $(CLOUD_SERVICE) not found (already deleted)"
