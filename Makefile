# ============================================================================
# Runflow Makefile — local Create (Build + Plan) and Execute
# ============================================================================

# -------- Configuration --------
CREATE_PORT ?= 8080
EXECUTE_PORT ?= 8081
RUNFLOW_ROOT ?= ./runflow

# -------- Phony targets --------
.PHONY: help usage --help create execute stop-create stop-execute prune-runs ai-prompt

# -------- Use same shell for multi-line targets --------
.ONESHELL:

# -------- Help --------
.DEFAULT_GOAL := help

help usage --help: ## Show this help message
	@echo ""
	@echo "Runflow — local Docker environments"
	@echo ""
	@echo "Create is Build + Plan (author a race). Execute is race day."
	@echo "Both can run at once. They do not share a filesystem;"
	@echo "the Day Plan ZIP is the handoff from Create to Execute."
	@echo ""
	@echo "  create         Start Create on http://localhost:$(CREATE_PORT) (hot reload)"
	@echo "  execute        Start Execute + Postgres on http://localhost:$(EXECUTE_PORT)"
	@echo "  stop-create    Stop Create only"
	@echo "  stop-execute   Stop Execute and Postgres only"
	@echo "  prune-runs     Prune old run_ids (KEEP=n, CONFIRM=1, DRY_RUN=1)"
	@echo "  ai-prompt      Generate AI prompt for a run_id (RUN_ID=...)"
	@echo ""
	@echo "Execute copies code at image build time. Restart with"
	@echo "'make execute' after Execute backend or frontend changes."
	@echo ""

# ============================================================================
# Local environments
# ============================================================================

create: ## Start Create (Build + Plan) on :8080
	@echo "Starting Create (Build + Plan) on http://localhost:$(CREATE_PORT)"
	@docker compose up -d --build create

execute: ## Start Execute + Postgres on :8081
	@echo "Starting Execute on http://localhost:$(EXECUTE_PORT)"
	@docker compose up -d --build execute-db execute

stop-create: ## Stop Create only
	@echo "Stopping Create..."
	@docker compose stop create
	@docker compose rm -f create

stop-execute: ## Stop Execute and Postgres only
	@echo "Stopping Execute..."
	@docker compose stop execute execute-db
	@docker compose rm -f execute execute-db

ai-prompt: ## Generate AI prompt for a run_id (manual mode)
	@if [ -z "$(RUN_ID)" ]; then \
		echo "Error: RUN_ID parameter required (e.g., make ai-prompt RUN_ID=4VwzQWum7DpFCj7r6aZi4s)"; \
		exit 1; \
	fi
	@echo "Generating AI prompt for run_id=$(RUN_ID)..."
	@docker exec runflow-create python -m app.utils.ai_analysis prompt --run-id $(RUN_ID) || (echo "Create is not running. Start with 'make create' first." && exit 1)

prune-runs: ## Prune old run_ids, keeping last N (KEEP=n required)
	@if [ -z "$(KEEP)" ]; then \
		echo "Error: KEEP parameter required (e.g., make prune-runs KEEP=10)"; \
		exit 1; \
	fi
	@docker compose exec create python -m app.utils.prune_runs --keep $(KEEP) $(if $(DRY_RUN),--dry-run,) $(if $(CONFIRM),--confirm,)
