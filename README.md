# Run Density

[![Deploy and Test](https://github.com/thomjeff/run-density/actions/workflows/deploy-and-test.yml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/deploy-and-test.yml)
[![Deploy](https://github.com/thomjeff/run-density/actions/workflows/deploy-and-test.yml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/deploy-and-test.yml)

## Overview
This service models runner density on shared course segments using a density engine and temporal flow analysis.  
It provides comprehensive reporting capabilities with both Markdown and CSV outputs, and is containerized and deployed to Google Cloud Run.

**Current Version: v1.6.12** - Negative convergence points algorithm fix and enhanced accuracy

## Key Features
- **Density Analysis**: Spatial concentration analysis with areal and crowd density calculations
- **Temporal Flow Analysis**: Convergence and overtaking analysis between different race events
- **Comprehensive Reporting**: Auto-generated Markdown and CSV reports with detailed analytics
- **RESTful API**: Full FastAPI integration with configurable parameters
- **CLI Tools**: Command-line scripts for report generation and analysis

## Quick Start (Local Development)

Create and activate a Python virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Run locally:
```bash
make run-local
```

Health checks:
```bash
curl -fsS http://localhost:8080/health | jq .
curl -fsS http://localhost:8080/ready | jq .
```

Smoke test locally:
```bash
make smoke-local
```

## Report Generation

### CLI Tools
Generate comprehensive reports using command-line tools:

> **Note**: Legacy CLI scripts have been moved to `archive/` directory. The examples below use the modern module-based approach.

**Temporal Flow Report** (Markdown + CSV):
```bash
python3 -c "
from app.temporal_flow_report import generate_temporal_flow_report
result = generate_temporal_flow_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Report generated: {result[\"md_file\"]}')
"
```

**Density Report** (Markdown):
```bash
python3 -c "
from app.density_report import generate_density_report
result = generate_density_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Report generated: {result[\"md_file\"]}')
"
```

### API Endpoints
Generate reports via REST API:

**Temporal Flow Report**:
```bash
curl -X POST "http://localhost:8080/api/temporal-flow-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/your_pace_data.csv",
    "segmentsCsv": "data/segments.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "outputDir": "reports/analysis"
  }'
```

**Density Report**:
```bash
curl -X POST "http://localhost:8080/api/density-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/your_pace_data.csv",
    "densityCsv": "data/density.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "outputDir": "reports/analysis"
  }'
```

---

## Makefile Shortcuts
- `make bootstrap` – install runtime dependencies  
- `make run-local` – start service on `http://localhost:8080`  
- `make smoke-local` – hit `/health`, `/ready`, and a small `/api/density` payload  
- `make smoke-prod` – run the same tests against the deployed Cloud Run service  

---

## Deployment (CI/CD)

Deployment is automated with **GitHub Actions** (`.github/workflows/deploy-and-test.yml`).

### Deployment Flow
1. Build Docker image locally inside GitHub Actions runner  
2. Push to **Artifact Registry**  
3. Deploy to **Cloud Run**  

⚠️ **Important**:  
- **Do NOT use Google Cloud Build** for this project.  
  - Past attempts caused IAM/permissions errors.  
  - Always use **Docker → Artifact Registry → Cloud Run**.  

### CI/CD Notes

**1. Smoke Tests**
- After deployment, the smoke test job dynamically fetches the Cloud Run service URL:
  ```bash
  gcloud run services describe $SERVICE     --project $PROJECT_ID --region $REGION     --format='value(status.url)'
  ```
- Do **not** attempt to pass `BASE_URL` between jobs.  
- If you see `ERROR: BASE_URL is empty`, the fix is already included (the smoke step re-fetches the URL).

**2. Artifact Registry Repo**
- If `GCP_AR_REPO` is not set in repo secrets, the workflow defaults to `run`.

**3. Cloud Run Config**
- Memory: `1Gi`  
- CPU: `1`  
- Min instances: `0`  
- Max instances: `3`

---

## ChatGPT Reminder Prompt

When opening new chats with ChatGPT for this repo, paste the following at the top:

```
Reminder:
- Never suggest using Google Cloud Build for this repo. Always use Docker → Artifact Registry → Cloud Run.
- Smoke tests must resolve the Cloud Run URL dynamically (never pass BASE_URL between jobs).
- Keep Makefile targets venv-aware to avoid pip/uvicorn “command not found” issues.
```

---

## License
MIT
