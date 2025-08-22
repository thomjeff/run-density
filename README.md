# Run Density

[![Smoke Tests](https://github.com/thomjeff/run-density/actions/workflows/smoke-report.yml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/smoke-report.yml)
[![Deploy](https://github.com/thomjeff/run-density/actions/workflows/deploy-cloud-run.yml/badge.svg)](https://github.com/thomjeff/run-density/actions/workflows/deploy-cloud-run.yml)

## Overview
This service models runner density on shared course segments using a density engine and overlap analysis.  
It is containerized and deployed to Google Cloud Run.

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

---

## Makefile Shortcuts
- `make bootstrap` – install runtime dependencies  
- `make run-local` – start service on `http://localhost:8080`  
- `make smoke-local` – hit `/health`, `/ready`, and a small `/api/density` payload  
- `make smoke-prod` – run the same tests against the deployed Cloud Run service  

---

## Deployment (CI/CD)

Deployment is automated with **GitHub Actions** (`.github/workflows/deploy-cloud-run.yml`).

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
