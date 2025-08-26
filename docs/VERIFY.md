# VERIFY.md — Manual & Scripted Verification

This document gives you **fast, deterministic checks** you can run locally and against **GCP Cloud Run** to confirm the service is healthy after changes.

---

## 0) Make the smoke script executable (one-time per clone)

```bash
chmod +x ci/smoke-report.sh
```

> If `ci/smoke-report.sh` doesn’t exist, pull `main` or your feature branch.

---

## 1) Manual spot-checks (copy/paste)

First, fetch the **service URL** from Cloud Run (Console → Cloud Run → your service). It looks like:

```
https://run-density-XXXXXXXXXX.us-central1.run.app
```

Export and run:

```bash
BASE="https://run-density-XXXXXXXXXX.us-central1.run.app"

curl -fsS "$BASE/health" | jq .
curl -fsS "$BASE/ready"  | jq .

curl -fsS -X POST "$BASE/api/density"   -H "Content-Type: application/json"   -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
    "startTimes":{"10K":440,"Half":460},
    "segments":[{"eventA":"10K","eventB":"Half","from":0.00,"to":2.74,"width":3.0,"direction":"uni"}],
    "stepKm":0.03,
    "timeWindow":60
  }' | jq '.engine, .segments[0].peak'
```

Expected:
- `/health` → `{ "ok": true, ... }`
- `/ready`  → `{ "ok": true, "density_loaded": true, "overlap_loaded": true }`
- `/api/density` → `"density"` and a valid `.segments[0].peak` object.

---

## 2) Scripted smoke test (recommended)

Run with positional argument:

```bash
./ci/smoke-report.sh https://run-density-XXXXXXXXXX.us-central1.run.app
```

Or export an environment variable and run without args:

```bash
export BASE_URL="https://run-density-XXXXXXXXXX.us-central1.run.app"
./ci/smoke-report.sh
```

The script will:
- Validate `/health` and `/ready` JSON shapes
- POST a tiny `/api/density` payload and assert the response contract
- Exit non‑zero if anything fails

Common errors:
- `./smoke-report.sh: line 4: $1: unbound variable` → You didn’t pass a URL and `BASE_URL` isn’t set. Use one of the invocations above.
- `permission denied` → You forgot to `chmod +x ci/smoke-report.sh`.

---

## 3) Local checks (uvicorn)

In the project root:

```bash
make run-local   # starts uvicorn on http://localhost:8080
# In a separate shell:
make smoke-local # hits http://localhost:8080
```

If port `8080` is busy, stop the previous server or kill the process using it.

---

## 4) CI parity (GitHub Actions)

The workflow **Contract Tests (live)** and the **Deploy + Smoke** job run logic equivalent to this doc. If CI is green, these manual steps should also pass. If they diverge, prefer CI outputs and logs, then reproduce locally using this document.
