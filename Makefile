# ---- run-density Makefile (venv-aware & self-bootstrapping) ----
# Usage:
#   make bootstrap        # create .venv and install deps
#   make run-local        # start uvicorn on http://localhost:8080
#   make smoke-local      # health/ready + tiny density POST against localhost
#   make smoke-prod       # same smoke against Cloud Run (override BASE=...)

SHELL := /bin/bash
BASE  ?= https://run-density-ln4r3sfkha-uc.a.run.app

# venv binaries (no need to "activate")
PY       := .venv/bin/python
PIP      := .venv/bin/pip
UVICORN  := .venv/bin/uvicorn
CURL     := curl
JQ       := jq

.PHONY: bootstrap run-local smoke-local smoke-prod _smoke deps check jq-check

bootstrap: .venv/bin/python deps ## Create venv and install deps

.venv/bin/python:
	@echo ">> creating venv (.venv) with python3.12"
	@/opt/homebrew/bin/python3.12 -m venv .venv || python3 -m venv .venv

deps:
	@echo ">> installing runtime requirements"
	@$(PY) -m pip install -U pip
	@$(PIP) install -r requirements.txt

jq-check:
	@command -v $(JQ) >/dev/null || { echo "ERROR: 'jq' not found. brew install jq"; exit 1; }

run-local: bootstrap
	@echo ">> starting uvicorn on http://localhost:8080 ..."
	@$(UVICORN) app.main:app --reload --port 8080

smoke-local: jq-check
	@$(MAKE) _smoke BASE=http://localhost:8080

smoke-prod: jq-check
	@$(MAKE) _smoke BASE=$(BASE)

_smoke:
	@set -euo pipefail; \
	echo ">> Hitting $$BASE"; \
	$(CURL) -fsS "$$BASE/health" | $(JQ) -e '.ok == true' >/dev/null && echo "health OK"; \
	$(CURL) -fsS "$$BASE/ready"  | $(JQ) -e '.ok == true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready OK"; \
	printf '%s\n' '{ \
	  "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv", \
	  "startTimes":{"10K":440,"Half":460}, \
	  "segments":[{"eventA":"10K","eventB":"Half","from":0.00,"to":2.74,"width":3.0,"direction":"uni"}], \
	  "stepKm":0.03,"timeWindow":60 \
	}' \
	| $(CURL) -fsS -X POST "$$BASE/api/density" -H "Content-Type: application/json" -H "Accept: application/json" \
	  --data-binary @- | $(JQ) -e '.engine=="density" and (.segments[0].peak|has("km"))' >/dev/null \
	&& echo "density OK"; \
	echo "✅ Smoke passed for $$BASE"