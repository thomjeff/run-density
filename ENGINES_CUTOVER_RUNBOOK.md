# Engines Cutover Runbook — Cloud Run (Zero-Downtime)

**Service:** `run-density`  
**Environment:** Cloud Run (Region: `us-central1`)  
**Objective:** Swap stub engines with the real implementations of `density` and `overlap` **without breaking prod**.

---

## Phase 0 — Preconditions (you already passed these)
```bash
BASE="https://run-density-131075166528.us-central1.run.app"
curl -s "$BASE/health" | jq .
curl -s "$BASE/ready"  | jq .
# Expect ok:true; stub shows density_loaded/overlap_loaded true when modules import.
```

---

## Phase 1 — Create a working branch
```bash
cd /Users/jthompson/Documents/GitHub/run-density
git checkout -b engines-cutover
```

---

## Phase 2 — Wire in the real engines

**Contract (do not change these function signatures):**

```python
# app/density.py
def run_density(
    pace_csv: str,
    start_times: dict,
    segments: list[dict],
    step_km: float,
    time_window_s: float,
) -> dict:
    """Return JSON-serializable dict with computed metrics/results."""
    ...

# app/overlap.py
def analyze_overlaps(
    pace_csv: str,
    overlaps_csv: str | None,
    start_times: dict,
    step_km: float,
    time_window_s: float,
    eventA: str,
    eventB: str | None,
    from_km: float,
    to_km: float,
) -> dict:
    """Return JSON-serializable dict with computed metrics/results."""
    ...
```

**Action:** Replace the current placeholder content in `app/density.py` and `app/overlap.py` with your **real logic** (the same computation path that matched the CLI).

> Tip: Keep I/O (HTTP) out of these files; return Python dicts only. `app/main.py` handles request parsing and headers (`X-Compute-Seconds`).

Commit:
```bash
git add app/density.py app/overlap.py
git commit -m "Engines: wire real density & overlap implementations"
```

---

## Phase 3 — Local validation (fast fail if anything is off)

**Run locally:**
```bash
# 1) Python deps
pip install -r requirements.txt

# 2) Start API locally
uvicorn app.main:app --reload --port 8080

# 3) In a second terminal, smoke-test:
curl -s http://localhost:8080/health | jq .
curl -s http://localhost:8080/ready  | jq .

# 4) Density minimal
curl -s -X POST http://localhost:8080/api/density   -H "Content-Type: application/json" -H "Accept: application/json"   -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
    "startTimes":{"10K":440,"Half":460},
    "segments":[
      "10K,Half,0.00,2.74,3.0,uni",
      "10K,,2.74,5.80,1.5,bi",
      {"eventA":"10K","eventB":"Half","from":5.81,"to":8.10,"width":3.0,"direction":"uni"}
    ],
    "stepKm":0.03,
    "timeWindow":60
  }' | jq .

# 5) Overlap minimal
curl -s -X POST http://localhost:8080/api/overlap   -H "Content-Type: application/json" -H "Accept: application/json"   -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
    "startTimes":{"10K":440,"Half":460},
    "eventA":"10K",
    "eventB":"Half",
    "from":0.00,
    "to":2.74,
    "stepKm":0.03,
    "timeWindow":60
  }' | jq .
```

**Optional container parity check:**
```bash
docker build -t run-density:engines .
docker run -e PORT=8080 -p 8080:8080 run-density:engines
curl -s http://localhost:8080/health | jq .
```

---

## Phase 4 — Safe deploy as **no-traffic canary**

Deploy a new revision WITHOUT sending user traffic, and attach a **tag** so you get a unique URL:

```bash
gcloud run deploy run-density   --source .   --region us-central1   --allow-unauthenticated   --memory=1Gi --cpu=1   --min-instances=0 --max-instances=3   --timeout=300   --no-traffic   --tag=canary
```

Get the per-tag URL:
```bash
gcloud run services describe run-density --region us-central1 --format='json(status.traffic)' | jq '.status.traffic[] | {tag:.tag,percent:.percent,url:.url}'
# Look for the object where "tag":"canary" and copy its "url"
```

Smoke-test **the canary URL** (it looks like `https://canary---run-density-XXXX-uc.a.run.app`):
```bash
CANARY_URL="<paste_url_here>"
curl -s "$CANARY_URL/health" | jq .
curl -s "$CANARY_URL/ready"  | jq .

# Same payloads as Phase 3, but point at CANARY_URL
curl -s -X POST "$CANARY_URL/api/density" -H "Content-Type: application/json" -H "Accept: application/json" -d '{ ... }' | jq .
curl -s -X POST "$CANARY_URL/api/overlap" -H "Content-Type: application/json" -H "Accept: application/json" -d '{ ... }' | jq .
```

Tail logs during verification:
```bash
gcloud beta run services logs tail run-density --region us-central1
```

---

## Phase 5 — Gradual traffic shift (optional but recommended)

Send a small slice of prod traffic to the new revision:
```bash
# Show revisions to get the latest name
gcloud run revisions list --service run-density --region us-central1

# Shift 5% to the latest
gcloud run services update-traffic run-density   --region us-central1   --to-latest=5
```

Observe logs/metrics for a few minutes. If clean, promote to 100%:
```bash
gcloud run services update-traffic run-density   --region us-central1   --to-latest
```

---

## Phase 6 — Rollback plan (instant)

If anything misbehaves:
```bash
# List revisions (note the previous-good REV name)
gcloud run revisions list --service run-density --region us-central1

# Route 100% back to the previous good revision
gcloud run services update-traffic run-density   --region us-central1   --to-revisions <PREVIOUS_REV>=100
```

---

## Phase 7 — Operational guardrails

- **Timeouts:** We’re at `--timeout=300`. If the engines need more, bump to 600 once.
- **Scale caps:** `--max-instances=3` initially. Raise gradually as needed.
- **Observability:**  
  ```bash
  gcloud beta run services logs tail run-density --region us-central1
  ```
- **Costs:** Cloud Run bills only while serving requests. Idle = $0.

---

## Quick checklist (print and keep handy)

- [ ] Branch created: `engines-cutover`
- [ ] Real `app/density.py` and `app/overlap.py` in place
- [ ] Local `uvicorn` smoke tests pass
- [ ] Canary revision deployed with `--no-traffic --tag=canary`
- [ ] Canary URL returns expected metrics
- [ ] Traffic shift 5% → 100%
- [ ] Rollback command ready (previous revision noted)

---

## Appendix — example `segments` payload

String and object forms are both accepted; these are equivalent:
```json
"segments": [
  "10K,Half,0.00,2.74,3.0,uni",
  {"eventA":"10K","eventB":"Half","from":5.81,"to":8.10,"width":3.0,"direction":"uni"}
]
```
