# -------- Configuration --------
PY ?= /opt/homebrew/opt/python@3.12/bin/python3.12
PORT ?= 8081
BASE ?= http://127.0.0.1:$(PORT)

# Prod BASE can be overridden per-run:
# make smoke-prod BASE=https://run-density-131075166528.us-central1.run.app

# -------- Phony targets --------
.PHONY: venv install run-local stop-local smoke-local smoke-prod clean-venv

venv:
	$(PY) -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

install: venv
	@echo "Dependencies installed."

run-local:
	@# Refuse to start if port is busy
	@if lsof -ti:$(PORT) >/dev/null 2>&1; then \
		echo "Port $(PORT) is already in use. Run 'make stop-local' or choose another PORT=..."; \
		exit 1; \
	fi
	. .venv/bin/activate && uvicorn app.main:app --reload --port $(PORT)

stop-local:
	@-lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || true
	@echo "Stopped anything on port $(PORT)."

smoke-local:
	@echo ">> Hitting $(BASE)"
	@curl -fsS "$(BASE)/health" | jq -e '.ok==true' >/dev/null && echo "health OK"
	@curl -fsS "$(BASE)/ready"  | jq -e '.ok==true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready  OK"
	@echo ">> tiny density call (from overlaps.csv)"
	@curl -fsS -X POST "$(BASE)/api/density" \
	  -H "Content-Type: application/json" -H "Accept: application/json" \
	  -d '{ \
	        "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv", \
	        "overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv", \
	        "startTimes":{"Full":420,"10K":440,"Half":460}, \
	        "stepKm":0.03,"timeWindow":60 \
	      }' \
	| jq -e '.engine=="density" and (.segments|length)>0' >/dev/null && echo "density OK" || (echo "density FAILED" && exit 1)
	@echo "✅ smoke-local passed"

smoke-prod:
ifndef BASE
	$(error Set BASE to your Cloud Run URL, e.g. make smoke-prod BASE=https://run-density-131075166528.us-central1.run.app)
endif
	@echo ">> Hitting $(BASE)"
	@curl -fsS "$(BASE)/health" | jq -e '.ok==true' >/dev/null && echo "health OK"
	@curl -fsS "$(BASE)/ready"  | jq -e '.ok==true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready  OK"
	@echo ">> tiny density call (from overlaps.csv)"
	@curl -fsS -X POST "$(BASE)/api/density" \
	  -H "Content-Type: application/json" -H "Accept: application/json" \
	  -d '{ \
	        "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv", \
	        "overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv", \
	        "startTimes":{"Full":420,"10K":440,"Half":460}, \
	        "stepKm":0.03,"timeWindow":60 \
	      }' \
	| jq -e '.engine=="density" and (.segments|length)>0' >/dev/null && echo "density OK" || (echo "density FAILED" && exit 1)
	@echo "✅ smoke-prod passed"

clean-venv:
	@rm -rf .venv
	@echo "Removed .venv"