# Cloud Run Timeout 503s — Fix Plan (Infra First, Then Code Hygiene)

**Context**  
`/api/temporal-flow`, `/api/temporal-flow-report`, and `/api/density-report` return 503s on Cloud Run. Logs show Gunicorn worker timeouts and SIGABRT. Locally, tests pass.

---

## 1) Cloud Run / Gunicorn Changes (No Code)

Your log shows a classic mismatch:

**Problem signal**
- `[CRITICAL] WORKER TIMEOUT (pid:3)` followed by `SIGABRT` → Gunicorn default timeout (~30s) kills the worker before Cloud Run’s 300s request timeout, surfacing as 503.

That’s Gunicorn killing the worker (default --timeout is 30s) long before Cloud Run’s request timeout (you’ve confirmed 300s). Cloud Run then surfaces this as a 503.

**Immediate changes**
- **Gunicorn runtime:**
  - Recommended CMD (adjust workers/threads with CPU size):
    ```bash
    gunicorn app.main:app       -k uvicorn.workers.UvicornWorker       -b 0.0.0.0:${PORT:-8080}       --timeout 360       --graceful-timeout 60       --keep-alive 75       --workers 1       --threads 4
    ```
  - Alternatively set `GUNICORN_CMD_ARGS="--timeout 360 --graceful-timeout 60 --keep-alive 75 --workers 1 --threads 4"`.

- **Cloud Run service settings:**
  - Timeout: **300s** (keep).
  - CPU/Memory: start with **2 vCPU / 2–4 GiB**.
  - Concurrency: **1** (CPU-bound work; prevents request dogpiles).
  - Min instances: **1** (optional; reduces cold starts).
  - Example deploy flags:
    ```bash
    gcloud run deploy run-density       --image gcr.io/PROJECT/IMAGE:TAG       --region us-central1       --cpu=2 --memory=2Gi       --concurrency=1       --timeout=300       --min-instances=1
    ```

Make sure the container PORT is respected (you already do with :${PORT:-8080}—good).

If these three are the only problems, your 503s should disappear without touching code.
---

## 2) Repo Review: Cloud Run Pitfalls

### A) Writes to a non-writable path
- Current default: `reports/analysis`.
- Cloud Run only allows writes to `/tmp`.  
- Fix: `OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp/analysis")`.

Update any writer to use that (and os.makedirs(OUTPUT_DIR, exist_ok=True)).
**Long-term:** write to GCS (Cloud Storage) and return a signed URL instead of pushing huge JSON/CSV through the response.

### B) Heavy CPU work in request handlers
The endpoints you called out—/api/temporal-flow, /api/temporal-flow-report, /api/density-report—all route into pandas/numpy-heavy analysis modules (density.py, flow.py, report.py, temporal_flow_report.py, density_report.py). These are fine locally, but in Cloud Run under the default 30s Gunicorn timeout they’ll get killed mid-flight (what you’re seeing). Even after you raise timeouts, large inputs may still exceed 300s in worst case.

- Pandas/numpy-heavy code runs synchronously.
- Fix: raise Gunicorn timeout, limit concurrency, or offload to Cloud Run Jobs / Tasks.

### C) Large responses
*I don't believe we are returning any large responses*
If the report endpoints return very large JSON/CSV inline, you’ll be paying for serialization time and network time in the same 300s window. That’s risky under load.
- Returning massive JSON/CSV inline eats the 300s budget.  
- Fix: Write to GCS + return signed URL.

### D) Algorithmic hot spots
I can’t see every inner loop (some files show elisions), but temporal flow / overtake detection is often O(N²) on pairwise comparisons. That’s fine locally with small inputs but can explode with real race data. Possible mitigations:
* Pre-bucket by segment/time windows to reduce pairwise comparisons.
* Use vectorized joins on time bins instead of naive double loops.
* Profile locally with the same dataset that times out in Cloud Run.

- Temporal flow logic may be O(N²).  
- Fix: bucket/join by time or pre-segment data.

### E) Threading/async mismatch
FastAPI async functions don’t make CPU work faster; if the handlers are async but call CPU-bound pandas operations, the event loop is still blocked. UvicornWorker handles sync endpoints just fine, but consider:
* Offload CPU-bound calls with run_in_executor or to a job queue (Cloud Tasks).
* Keep workers=1 and add --threads (Gunicorn) to avoid process churn while still letting Uvicorn handle I/O.

- Async endpoints with CPU-bound pandas still block.  
- Fix: `run_in_executor` or job queues.

---

## 3) Concrete Code Hygiene Fixes
Minimum viable code edits (Cloud-Run-friendly without re-architecting):
1.	Writable path
* Introduce OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp/analysis").
* Replace any "reports/analysis" usage with OUTPUT_DIR.
* Ensure os.makedirs(OUTPUT_DIR, exist_ok=True) before writes.

2.	Return URLs, not bulk payloads
* Where you currently generate a report file, write to GCS:
* Add a small storage util (using google-cloud-storage).
* Bucket via env var REPORTS_BUCKET.
* Return a signed URL + metadata in the API response.
This dramatically reduces request body sizes and latency.

3.	Guardrails around long work
* Wrap the heavy call with timing logs; return 202 Accepted + job id if you detect inputs that will exceed a threshold (optional, but nice).
* Or provide a ?async=true flag that kicks off a Cloud Run Job/Cloud Task and returns a handle.

4.	Gunicorn baked-in
* Even if you bump it at deploy time, commit the safer defaults into the Docker CMD (Section 1) so anyone running your image gets sane behavior.

Summary:
- [ ] Switch all writes to `/tmp` or GCS.
- [ ] Add env var: `OUTPUT_DIR` + `REPORTS_BUCKET`.
- [ ] Use signed GCS URLs for large outputs.
- [ ] Wrap heavy jobs with timing + consider async/offload for >300s inputs.
- [ ] Commit safe Gunicorn defaults into Dockerfile.

---

## 4) Trail Plan (Experimental Endpoint)
We will *only consider making fundamental code changes* if the Cloud/Infra and Cloud code hygiene fixes don't work. 
Your idea is solid: clone one endpoint/module to trial Cloud-Run-specific patterns while keeping the 3 current ones unchanged for local validity. Best practice I’d suggest:
* Pick the smallest surface but representative workload—usually /api/density-report (it exercises pandas, I/O, and report formatting without all the temporal complexity).
* Create /api/density-report-v2 backed by a copied module (e.g., density_report_v2.py) that:
	1.	Writes outputs to OUTPUT_DIR (default /tmp/analysis).
	2.	(Option A) Returns the result as a signed GCS URL.
	3.	(Option B) If you want to keep it simple for now, still return JSON but add metrics to validate runtime and size.

* Deploy with the Gunicorn/Cloud Run settings above.
* Once that succeeds end-to-end in Cloud, port the same pattern to /api/temporal-flow-report and /api/temporal-flow.

This yields a safe A/B:
* Local: keep the original 3 as-is for your existing e2e tests.
* Cloud: exercise the v2 endpoint and iterate on infra + code patterns.
* When stable, refactor the original three to the v2 approach or cut over routes.

- Copy `/api/density-report` → `/api/density-report-v2`.
- New module uses `/tmp` or GCS, safer response pattern.
- Keep originals for local e2e validation.
- Use v2 in Cloud Run to test infra + code hygiene approach.

We will *only consider making fundamental code changes* if the Cloud/Infra and Cloud code hygiene fixes don't work. 

---

## 5) Checklist for Cursor

**Cloud Run / Infra**
- [ ] Gunicorn: `--timeout 360 --graceful-timeout 60 --keep-alive 75`.
- [ ] Workers/threads tuned for CPU.
- [ ] Cloud Run: `concurrency=1`, `cpu=2`, `memory=2Gi`, `timeout=300`, `min-instances=1`.

**Code hygiene**
- [ ] Replace `reports/analysis` with `OUTPUT_DIR=/tmp/analysis`.
- [ ] Optionally add GCS + signed URL pattern.
- [ ] Log runtimes; offload if >300s.

**Trial**
We will *only consider making fundamental code changes* if the Cloud/Infra and Cloud code hygiene fixes don't work. 
- [ ] Duplicate density-report → density-report-v2.
- [ ] Validate in Cloud Run, keep old endpoints for local.
- [ ] Roll out refactor once stable.

---

## Updated Next Steps (Two-Phase Approach)

**Phase 1 – Cloud Run / Infra**
1. Update Gunicorn config and Cloud Run service settings.
2. Redeploy and rerun failing endpoints.
3. Confirm if requests succeed.

**Phase 2 – Code Hygiene for Cloud Run**
1. Switch writes to `/tmp` or GCS.
2. Add OUTPUT_DIR + REPORTS_BUCKET env vars.
3. Return signed URLs for large reports.
4. Add timing + structured logging.
5. Evaluate async/offload for >300s cases.

**Decision Point**: If stable after Phase 1+2 → keep pattern. If not, apply Trail Plan with `/api/density-report-v2` as experimental module.

## Cloud Run Service YAML
Here’s a Cloud Run Service YAML you can drop into Cursor. It keeps resources at 1 vCPU / 1GiB, sets concurrency=1, and pushes all the runtime knobs (Gunicorn timeouts, writable path) without changing the CPU/RAM.

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: run-density
  namespace: run-density
  annotations:
    # Optional: cap autoscaling while you test
    autoscaling.knative.dev/minScale: "0"
    autoscaling.knative.dev/maxScale: "4"
spec:
  template:
    metadata:
      annotations:
        # Concurrency per instance — keep at 1 for CPU-heavy work
        autoscaling.knative.dev/target: "1"
        # Optional: small startup boost; doesn't change your steady-state CPU
        run.googleapis.com/startup-cpu-boost: "true"
    spec:
      containerConcurrency: 1
      timeoutSeconds: 300
      containers:
        - image: gcr.io/PROJECT_ID/IMAGE:TAG
          # If your Dockerfile already sets CMD, keep it.
          # We pass Gunicorn settings via env so you don't edit Dockerfile right now.
          env:
            - name: GUNICORN_CMD_ARGS
              value: "--timeout 360 --graceful-timeout 60 --keep-alive 75 --workers 1 --threads 4"
            - name: OUTPUT_DIR
              value: "/tmp/analysis"
            # Uncomment if/when you push large outputs to Cloud Storage
            # - name: REPORTS_BUCKET
            #   value: "your-gcs-bucket-name"
            # - name: GOOGLE_CLOUD_PROJECT
            #   value: "run-density"
          ports:
            - name: http1
              containerPort: 8080
          resources:
            limits:
              cpu: "1"      # stays at 1 vCPU as requested
              memory: "1Gi" # stays at 1GiB as requested
```

Does ChatGPT agree that 1 vCPU / 1GiB is tight? Yes—for pandas/numpy-heavy “temporal flow” analysis, 1 core and 1 GiB is lean. That said, if you’d rather not bump resources yet, the YAML above plus these practices usually stabilizes things:
* Set containerConcurrency: 1 so requests don’t compete for the single core.
* Increase Gunicorn timeouts (done in YAML) so the worker isn’t killed at ~30s.
* Write only to /tmp (done via OUTPUT_DIR) to avoid filesystem hiccups.
* Keep responses small (or switch to GCS URLs later) to reduce memory/serialization time.
* Avoid spawning extra processes; use --workers 1 --threads 4 to keep within 1 core and prevent thrash.

If you still see 503s after this, that’s a signal the work per request is exceeding what 1 vCPU can comfortably handle within 300s, and we should either (a) push outputs to GCS + return quickly, (b) split work (Cloud Tasks/Run Jobs), or (c) lightly raise CPU/RAM.

Next steps (aligned to your “Infra first, then hygiene” plan)

Phase 1 – Cloud Run / Infra (no resource increase)
1.	Deploy the YAML above (swap PROJECT_ID/IMAGE:TAG).

2.	Re-run the failing tests for:
* /api/temporal-flow
* /api/temporal-flow-report
* /api/density-report

3.	Confirm:
* No [CRITICAL] WORKER TIMEOUT in logs.
* p95 latency and memory stay within limits.

Phase 2 – Code hygiene (still at 1 vCPU / 1GiB)
1.	Ensure all writes use OUTPUT_DIR=/tmp/analysis.

2.	Cap response sizes (optionally switch to GCS signed URLs for large reports).

3.	Add simple timing logs around the heavy sections; if any cross ~120–180s, consider:
* a flag for async job mode (Cloud Run Jobs / Cloud Tasks) returning a job id, or
* minor algorithmic trims (bucketing, fewer pairwise joins).
