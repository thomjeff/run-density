# Cloud Run Runbook — Issue #198/#217 Bin Dataset Fix (Cursor-ready)

**Purpose:** End-to-end instructions for Cursor to build, deploy, verify, and operate the bin dataset feature on **Cloud Run**, with safe rollback and clear acceptance gates.

> This runbook assumes you already merged the fixes: `bins_accumulator.py` (vectorized binning), hotspot preservation, temporal-first coarsening, and defensive `save_bin_artifacts` saver. Feature flag: `ENABLE_BIN_DATASET` (default **false**).

---

## 0) Prereqs

- **GCP project:** `PROJECT_ID` (Viewer/Editor on Logs; Storage Object Admin if writing to GCS)
- **Artifact Registry** (or GCR) repo: `REGION-docker.pkg.dev/PROJECT_ID/run-density/run-density`
- **Cloud Run** API enabled; `gcloud` v>= 462.0 installed & authenticated
- **Service account:** `run-density-sa@PROJECT_ID.iam.gserviceaccount.com` with:
  - `roles/run.invoker`
  - `roles/storage.objectAdmin` (for artifact bucket, if used)
  - `roles/logging.logWriter`
  - Optional cache store (Redis/Firestore) perms if implemented

- **Env:** `REGION` (e.g., `us-central1`), `SERVICE=run-density`, `IMAGE_TAG=$(date +%Y%m%d-%H%M%S)`
- **Artifacts bucket (optional):** `gs://run-density-artifacts-<env>` (ensure bucket exists)

```bash
export PROJECT_ID="<your-project-id>"
export REGION="us-central1"
export SERVICE="run-density"
export REPO="run-density"
export IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
gcloud config set project "$PROJECT_ID"
```

---

## 1) Build & Push Image (Artifact Registry)

> If you already have CI building images, you can skip to §2.

```bash
# Create repo once (idempotent)
gcloud artifacts repositories create "$REPO"   --repository-format=docker   --location="$REGION"   --description="Run-density images" || true

# Build
gcloud builds submit --tag   "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:$IMAGE_TAG"
```

---

## 2) Staging Deploy (feature flag OFF)

```bash
# Common env vars
BIN_ENV="ENABLE_BIN_DATASET=false,BIN_MAX_FEATURES=10000,BIN_MAX_GEOJSON_MB=15,DEFAULT_BIN_TIME_WINDOW_SECONDS=60,MAX_BIN_GENERATION_TIME_SECONDS=120,BIN_SCHEMA_VERSION=1.0.0,HOTSPOT_SEGMENTS=bridge_w,bridge_e,greenwood_e,greenwood_w,bridge_mill,royal_rd_cross,station_barker,queen_square"

gcloud run deploy "$SERVICE-staging"   --image="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:$IMAGE_TAG"   --region="$REGION"   --platform=managed   --service-account="run-density-sa@$PROJECT_ID.iam.gserviceaccount.com"   --memory=3Gi   --cpu=2   --concurrency=1   --timeout=300   --max-instances=3   --set-env-vars="$BIN_ENV"   --allow-unauthenticated
```

> Rationale: single-threaded long requests; 3Gi RAM for headroom; 300s hard cap; flag OFF by default.

---

## 3) Canary: Enable Bins (feature flag ON for staging)

```bash
gcloud run services update "$SERVICE-staging"   --region="$REGION"   --set-env-vars="ENABLE_BIN_DATASET=true,$BIN_ENV"
```

Trigger your standard manifests (3 scenarios) against staging:

```bash
STAGING_URL="$(gcloud run services describe "$SERVICE-staging" --region="$REGION" --format='value(status.url)')"

# Example; adjust path/body to your API
curl -sS -X POST "$STAGING_URL/reports/density"   -H "Content-Type: application/json"   -d @scenario_full.json | jq .status

curl -sS -X POST "$STAGING_URL/reports/density"   -H "Content-Type: application/json"   -d @scenario_half.json | jq .status

curl -sS -X POST "$STAGING_URL/reports/density"   -H "Content-Type: application/json"   -d @scenario_10k.json | jq .status
```

---

## 4) Telemetry Validation (Logs)

Query the last 200 log lines for staging and **confirm these fields**:

```bash
gcloud logging read  'resource.type="cloud_run_revision" AND resource.labels.service_name="'$SERVICE'-staging"'  --limit=200 --format="value(textPayload)"
```

**Expected fields per run:**

- `analysis_hash`
- `bin_generation_ms`
- `effective_bin_m`, `effective_window_s`
- `nb_features` (<= **10,000**), `geojson_bytes_gz` (<= **15 MB**)
- `occupied_bins`, `nonzero_density_bins` (> 0)
- `cache_hit=true|false`, `memory_peak_mb`
- `bins.status=ok|partial|empty|timeout` (expect `ok`)

**Acceptance thresholds:**

- **Performance:** `bin_generation_ms` P95 ≤ **120,000** (temp ceiling); target ≤ **90,000**
- **Size:** `nb_features` ≤ **10k** (hard cap 12k), `geojson_bytes_gz` ≤ **15 MB**
- **Correctness:** occupied/nonzero > 0; reconciliation (see §6)
- **Stability:** on failure, service still returns segment report; `bins.status` set

---

## 5) Artifact Check (GCS or local)

If writing to GCS, list and sample:

```bash
# Example, adapt to your bucket/path
gsutil ls gs://run-density-artifacts-staging/bins_*.geojson.gz | tail -n 1 | xargs -I {} gsutil cp {} ./latest.geojson.gz
gzip -cd latest.geojson.gz | head -c 1000

gsutil ls gs://run-density-artifacts-staging/bins_*.parquet | tail -n 1 | xargs -I {} gsutil cp {} ./latest.parquet
python - << 'PY'
import pyarrow.parquet as pq
t = pq.read_table('latest.parquet')
print(t.num_rows, t.schema)
print(t.to_pandas().head())
PY
```

Check presence of props: `bin_id, segment_id, start_km, end_km, t_start, t_end, density, flow, los_class, bin_size_km`.

---

## 6) Reconciliation Gate (±2% / ±5%)

Run one API with an option to emit reconciliation, or download both **segment** and **bin** aggregates and compare:

- Per (segment, window):
  - `weighted_mean_bin_density = sum(bin_density * bin_len) / segment_len`
  - Compare to segment density → **±2%**
  - `sum(bin_flow) ≈ segment_flow` → **±5%**

If outside thresholds → **FAIL**, investigate runner mapping, width, or time-window alignment.

---

## 7) Production Deploy (flag OFF)

```bash
gcloud run deploy "$SERVICE"   --image="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:$IMAGE_TAG"   --region="$REGION"   --platform=managed   --service-account="run-density-sa@$PROJECT_ID.iam.gserviceaccount.com"   --memory=3Gi   --cpu=2   --concurrency=1   --timeout=300   --max-instances=5   --set-env-vars="$BIN_ENV"   --allow-unauthenticated
```

### Enable per-scenario (canary)
```bash
gcloud run services update "$SERVICE"   --region="$REGION"   --set-env-vars="ENABLE_BIN_DATASET=true,$BIN_ENV"
```

Run the same three scenarios; watch logs as in §4.

---

## 8) Rollback & Safety Nets

- **Immediate rollback:** `gcloud run services update "$SERVICE" --region="$REGION" --set-env-vars="ENABLE_BIN_DATASET=false,$BIN_ENV"`
- **Previous image:** redeploy with prior `$IMAGE_TAG`
- **Auto-coarsen:** code should react to soft timeout by widening time windows (non-hotspots) and then spatial coarsening
- **Empty bins:** saver writes artifacts but logs `occupied_bins=0`/`nonzero=0` as **ERROR**; UI banner shows `bins.status="empty"`

---

## 9) Troubleshooting

**Symptom:** `AttributeError: 'NoneType' object has no attribute 'get'` in saver  
**Fix:** Ensure you pass **GeoJSON FeatureCollection** or **BinBuildResult** to `save_bin_artifacts`. The defensive saver (`app/save_bins.py`) already handles `None` props/geometry.

**Symptom:** `occupied_bins=0` in metadata  
- Verify runner→segment/window mapping produces arrays
- Check `width_m` and `bin_len_m` > 0
- Confirm time windows cover the analysis duration

**Symptom:** 5xx / timeouts on Cloud Run  
- Reduce concurrency to 1; ensure single worker
- Confirm coarsening policy is active (temporal-first, then spatial for non-hotspots)
- Watch memory peak; if >1.5 GB, raise to 3Gi or reduce feature budget

**Symptom:** Map stutter  
- Ensure `nb_features` ≤ 10k; gz ≤ 15 MB; filter properties to essentials

---

## 10) CI Hooks (optional but recommended)

- **Unit:** schema validation; empty-occupancy guard; saver writes artifacts on empty & logs
- **Perf smoke:** run one medium scenario; assert `nb_features ≤ 10k`; `bin_generation_ms < 120s`
- **Recon:** ±2%/±5% checks on sample windows
- **Artifact audit:** Parquet row count == GeoJSON features

---

## 11) Ops Validation (first live exercise)

- Police/Traffic: verify reopening decisions align with **bin LOS decay** at crossings and ramps
- Ski Patrol/SJA: verify patrol staging near bins with peak density/flow
- Last Runner Biker: compare **occupied bins trailing edge** with expected last-runner progression

---

### One-liner to export logs as CSV for the AAR
```bash
gcloud logging read  'resource.type="cloud_run_revision" AND resource.labels.service_name="'$SERVICE'" AND textPayload:"bin_generation_ms"'  --limit=1000 --format=json | jq -r '.[] | .textPayload' > bin_runs.log
```

---

**Done.** This runbook is Cursor-ready to execute the full Cloud Run validation and production rollout with safe guards and objective acceptance gates.
