# Makefile for run-density project
# Use tabs (not spaces) for indentation

.PHONY: run smoke test deploy

run:
	uvicorn app.main:app --reload --port 8080

smoke:
	curl -fsS http://localhost:8080/health | jq -e '.ok == true' >/dev/null
	curl -fsS http://localhost:8080/ready | jq -e '.ok == true and .density_loaded and .overlap_loaded' >/dev/null
	@echo "✅ local smoke OK"

test:
	pytest -q --disable-warnings

deploy:
	gcloud builds submit --config deploy-cloud-run.yml .
