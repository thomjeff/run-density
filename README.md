# Run Density

A microservice to calculate runner density and overlap for road races.  
Exposes a REST API for health checks, density simulations, and overlap reporting.  

## Requirements

- Python **3.12.5** (`.python-version` included for [pyenv](https://github.com/pyenv/pyenv))
- [pip](https://pip.pypa.io/) for installing dependencies
- [Docker](https://www.docker.com/) (optional for container builds)
- [Google Cloud SDK](https://cloud.google.com/sdk) (for deploys)

## Installation

Clone the repo:

```bash
git clone https://github.com/thomjeff/run-density.git
cd run-density
```

Set up a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Alternatively, use the `Makefile` to bootstrap everything:

```bash
make setup
```

## Running Locally

```bash
make run
```

Or directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Health check:

```bash
curl -s http://localhost:8080/health | jq .
```

## Smoke Tests

Quick prod test:

```bash
BASE="https://run-density-ln4r3sfkha-uc.a.run.app"
curl -fsS "$BASE/health" | jq -e '.ok == true' >/dev/null
curl -fsS "$BASE/ready"  | jq -e '.ok == true and .density_loaded and .overlap_loaded' >/dev/null
echo "✅ prod smoke OK"
```

Local test:

```bash
curl -s http://localhost:8080/health | jq .
curl -s http://localhost:8080/ready  | jq .
```

For a sample density run:

```bash
curl -s -X POST http://localhost:8080/api/density   -H "Content-Type: application/json" -H "Accept: application/json"   -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
    "startTimes":{"10K":440,"Half":460},
    "segments":[{"eventA":"10K","eventB":"Half","from":0.00,"to":2.74,"width":3.0,"direction":"uni"}],
    "stepKm":0.03,"timeWindow":60
  }' | jq '.engine, .segments[0].peak'
```

## Deployment

Deploy to Google Cloud Run using the included manifest:

```bash
gcloud run deploy run-density   --source .   --region us-central1   --project <your-project-id>   --quiet
```

Or apply the explicit Cloud Run YAML:

```bash
gcloud run services replace deploy-cloud-run.yml
```

### Deployment Flow
See **[docs/DEPLOYMENT_FLOW.md](docs/DEPLOYMENT_FLOW.md)** for:
- GitHub Actions → Workload Identity Federation → Cloud Build → Artifact Registry → Cloud Run
- Required GitHub Secrets and IAM roles
- Useful commands (tail logs, fetch URL, smoke tests)
- Troubleshooting (403 Cloud Build, 404 `generateAccessToken`, startup probe)

## Repo Layout

- `app/` — main FastAPI app
- `schemas/` — JSON schema for API responses
- `scripts/` — utility scripts (e.g., `smoke.sh`)
- `tests/` — pytest suite
- `deploy-cloud-run.yml` — Cloud Run service definition
- `Makefile` — helper commands for setup, run, test, deploy
