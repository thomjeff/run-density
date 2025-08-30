# -------- Configuration --------
PY ?= /opt/homebrew/opt/python@3.12/bin/python3.12
PORT ?= 8081
BASE ?= http://127.0.0.1:$(PORT)

# Prod BASE can be overridden per-run:
# make smoke-prod BASE=https://run-density-131075166528.us-central1.run.app

# -------- Phony targets --------
.PHONY: venv install run-local stop-local smoke-local smoke-prod clean-venv smoke-areal smoke-crowd

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

smoke-crowd:
	@echo ">> zoneMetric=crowd with custom cuts"
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	OVLS=$${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}; \
	BODY=$$(printf '{\n  "paceCsv": "%s",\n  "overlapsCsv": "%s",\n  "startTimes": {"Full":420,"Half":460,"10K":440},\n  "stepKm": 0.03,\n  "timeWindow": 60,\n  "depth_m": 3.0,\n  "zoneMetric": "crowd",\n  "zones": {"crowd":[1.0,2.0,4.0,8.0]}\n}\n' "$$PACE" "$$OVLS"); \
	echo "$$BODY" | curl -sS -X POST "$$BASE/api/density" -H 'Content-Type: application/json' --data @- \
	| jq -r '.segments | map(select(.peak.zone!="green")) | .[:8][] | "\(.seg_id)\tareal=\(.peak.areal_density)\tcrowd=\(.peak.crowd_density)\tzone=\(.peak.zone)"'

smoke-areal:
	@echo ">> zoneMetric=areal with custom cuts"
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	OVLS=$${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}; \
	printf '{\n  "paceCsv": "%s",\n  "overlapsCsv": "%s",\n  "startTimes": {"Full":420,"Half":460,"10K":440},\n  "stepKm": 0.03,\n  "timeWindow": 60,\n  "depth_m": 3.0,\n  "zoneMetric": "areal",\n  "zones": {"areal":[7.5,15,30,50]}\n}\n' "$$PACE" "$$OVLS" \
	| curl -sS -X POST "$$BASE/api/density" -H 'Content-Type: application/json' --data @- \
	| jq -r '.segments | map(select(.peak.zone!="green")) | .[:8][] | "\(.seg_id)\tareal=\(.peak.areal_density)\tcrowd=\(.peak.crowd_density)\tzone=\(.peak.zone)"'

smoke-short:
	@echo ">> tiny inline segment (optionally single_event)"
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	printf '{\n  "paceCsv": "%s",\n  "segments": [\n    {\n      "seg_id":"ZZ-short",\n      "segment_label":"Tiny 2cm test",\n      "eventA":"10K", "eventB":"10K",\n      "from_km_A":1.000, "to_km_A":1.001,\n      "from_km_B":1.000, "to_km_B":1.001,\n      "direction":"uni", "width_m":3.0,\n      "single_event": %s\n    }\n  ],\n  "startTimes":{"Full":420,"Half":460,"10K":440},\n  "stepKm":0.03, "timeWindow":60, "depth_m":3.0\n}\n' "$$PACE" "$${SINGLE_EVENT:-false}" \
	| curl -sS -X POST "$$BASE/api/density" -H 'Content-Type: application/json' --data @- \
	| jq '{seg: .segments[0].seg_id, A: .segments[0].peak.A, B: .segments[0].peak.B, combined: .segments[0].peak.combined, areal: .segments[0].peak.areal_density, crowd: .segments[0].peak.crowd_density, zone: .segments[0].peak.zone}'
		
clean-venv:
	@rm -rf .venv
	@echo "Removed .venv"

# Pretty print summary (areal)
smoke-summary-areal:
	@echo "== areal zones =="
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	OVLS=$${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}; \
	curl -s -X POST "$$BASE/api/density?zoneMetric=areal" -H 'Content-Type: application/json' \
	  -d "$$(printf '{"paceCsv":"%s","overlapsCsv":"%s","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0}' "$$PACE" "$$OVLS")" \
	| jq -r '.segments | map(select(.peak.zone!="green")) | .[:8][] | "\(.seg_id)\tareal=\(.peak.areal_density)\tzone=\(.peak.zone)"'

# Pretty print summary (crowd)
smoke-summary-crowd:
	@echo "== crowd zones =="
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	OVLS=$${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}; \
	curl -s -X POST "$$BASE/api/density?zoneMetric=crowd" -H 'Content-Type: application/json' \
	  -d "$$(printf '{"paceCsv":"%s","overlapsCsv":"%s","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0,"zones":{"crowd":[1,2,4,8]}}' "$$PACE" "$$OVLS")" \
	| jq -r '.segments | map(select(.peak.zone!="green")) | .[:8][] | "\(.seg_id)\tcrowd=\(.peak.crowd_density)\tzone=\(.peak.zone)"'


smoke-peaks-areal:
	@echo ">> peaks.csv (areal default cuts)"
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	OVLS=$${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}; \
	printf '{\n  "paceCsv": "%s",\n  "overlapsCsv": "%s",\n  "startTimes": {"Full":420,"Half":460,"10K":440},\n  "stepKm": 0.03,\n  "timeWindow": 60,\n  "depth_m": 3.0\n}\n' "$$PACE" "$$OVLS" \
	| curl -sS -X POST "$$BASE/api/peaks.csv" -H 'Content-Type: application/json' --data @- \
	| head -n 10

smoke-peaks-crowd:
	@echo ">> peaks.csv (crowd with custom cuts)"
	@BASE=$${BASE:-http://127.0.0.1:8081}; \
	PACE=$${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}; \
	OVLS=$${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}; \
	printf '{\n  "paceCsv": "%s",\n  "overlapsCsv": "%s",\n  "startTimes": {"Full":420,"Half":460,"10K":440},\n  "stepKm": 0.03,\n  "timeWindow": 60,\n  "depth_m": 3.0,\n  "zones": {"crowd":[1,2,4,8]}\n}\n' "$$PACE" "$$OVLS" \
	| curl -sS -X POST "$$BASE/api/peaks.csv?zoneMetric=crowd" -H 'Content-Type: application/json' --data @- \
	| head -n 10

	