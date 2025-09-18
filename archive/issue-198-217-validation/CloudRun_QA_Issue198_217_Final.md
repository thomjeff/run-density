# Cloud Run QA Review — Issue #198 / #217 Final Validation
**Date:** September 17, 2025  
**Environment:** Google Cloud Run (2 vCPU / 2–3 GB RAM, request timeout 300s)  
**Feature Flag:** `ENABLE_BIN_DATASET` (default **false**; enabled per-scenario during tests)

---

## Executive Summary
Local results indicate the bin dataset is producing **real operational data** with **excellent performance** (≈ **250 ms** total for generation + serialization) and correct artifacts. This Cloud Run QA focuses on validating those results **in production-like conditions**: cold starts, real logging, I/O, gzip, and CPU scheduling. We also verify **coarsening policy**, **hotspot preservation**, **schema/reconciliation**, and **fallback safety**.

**Verdict:** _Conditional GO_. Enable on Cloud Run behind the feature flag and run the canary plan below. Ship widely once the gates in §1 and §7 are green.

---

## 1) Go/No‑Go Gates (Cloud Run)
All **must** pass for a full enablement:
- **Correctness**
  - [ ] Every feature has: `bin_id, segment_id, start_km, end_km, t_start, t_end, density, flow, los_class, bin_size_km`.
  - [ ] Reconciliation: per segment & window, **weighted mean(bin_density)** ≈ segment density (±2%).  
        Sum of bin flows ≈ segment flow (±5%).
  - [ ] Metadata counters present: `total_features, occupied_bins (>0), nonzero_density_bins (>0)`.
- **Performance**
  - [ ] Bin step P95 ≤ **120 s** (target ≤ 90 s).  
        Note: local shows **~0.25 s**; Cloud Run likely higher but still well under threshold.
  - [ ] Feature budget ≤ **10k** (hard cap 12k); `geojson_gz_mb` ≤ **15 MB** (warn at 12 MB).
  - [ ] Memory peak ≤ **1.5 GB** during bin step.
- **Stability / Safety Nets**
  - [ ] **Auto‑coarsen** reacts to soft‑timeout: temporal-first (60→120→180 s), then spatial for **non‑hotspots** only.
  - [ ] **Hotspot preservation** remains at **0.1 km / 60 s**.
  - [ ] **Feature flag** default **false**. Non-bin path verified.
  - [ ] **Empty/partial UX** banner logic wired (`bins.status`: ok|partial|empty|timeout).
- **Caching**
  - [ ] Content-addressable cache key; cache hit verified on repeated manifest.

---

## 2) Instrumentation to Confirm (must log per run)
Recommended structured fields (JSON logs):
```
analysis_hash
bin_generation_ms
geojson_serialization_ms
parquet_serialization_ms
effective_bin_m
effective_window_s
nb_features
geojson_bytes_gz
parquet_bytes
occupied_bins
nonzero_density_bins
cache_hit
memory_peak_mb
bins_status        // ok|partial|empty|timeout|disabled
notes
```
**Note on local 250 ms:** In Cloud Run, measure from **accumulation start → parquet write → gzip done**. If timings remain sub‑second, great; otherwise ensure they stay well under thresholds in §1.

---

## 3) Canary Plan (Cloud Run)
1. **Deploy revision** with `ENABLE_BIN_DATASET=false` (default). Verify segment-only flow.
2. **Enable flag for canary runs only** (per environment variable override or per-route switch).
3. Run the **three standard scenarios** (Full/Half/10K). For each:
   - Capture telemetry in §2.
   - Download artifacts and validate schema + reconciliation (§4).
4. **Repeat each run once** without input changes to confirm **cache_hit=true** and near‑zero bin compute time.
5. **Examine logs** for coarsening notes and hotspot preservation.

---

## 4) Artifact & Data QA (Cloud Run)
For each canary:
- **Artifacts present:** `bins.parquet`, `bins.geojson.gz` (non-empty).
- **Sizes:** `geojson_gz_mb` ≤ 15; `parquet_bytes` reasonable (tens of KB at current scale).
- **Data spot‑checks:** Sample 5 bins across hotspots:
  - **Non-zero** `density` (e.g., 0.0003–0.005 p/m²) and `flow`.
  - `los_class` sensible (A–D where density peaks).
  - Continuity across adjacent bins at peak minute (shape makes sense near pinch points).
- **Reconciliation (±2% / ±5%)**: For 3 segments (short/med/long) and one minute:
  - `sum(density[i] * bin_len_m[i]) / seg_len_m ≈ segment_density`
  - `sum(flow[i]) ≈ segment_flow`

---

## 5) Config & Runtime Shape (Cloud Run)
- **Gunicorn**: `--workers 1 --threads 1` (long synchronous analysis).
- **Request timeout**: 300 s; **soft budget** for bins: **120 s**.
- **CPU / Memory**: 2 vCPU, 2–3 GB RAM (3 GB if GC churn observed).
- **Concurrency**: ≤ 2 during canary.
- **Env vars (example):**
```
ENABLE_BIN_DATASET=false
BIN_MAX_FEATURES=10000
BIN_MAX_GEOJSON_MB=15
DEFAULT_BIN_TIME_WINDOW_SECONDS=60
MAX_BIN_GENERATION_TIME_SECONDS=120
HOTSPOT_SEGMENTS=F1,H1,J1,J4,J5,K1,L1
BIN_SCHEMA_VERSION=1.0.0
```

---

## 6) Auto‑Coarsen & Hotspot Policy Verification
- Confirm logs show **temporal-first** coarsening applied **only** to non‑hotspots (e.g., `window_s=120`).
- Confirm **spatial coarsening** (e.g., `bin_m=200`) never applied to hotspots unless absolutely necessary.
- Telemetry example (expected when limits exceeded):
```
{ "action": "coarsen", "phase": "temporal", "from_window_s": 60, "to_window_s": 120, "scope": "non_hotspots" }
{ "action": "coarsen", "phase": "spatial", "from_bin_m": 100, "to_bin_m": 200, "scope": "non_hotspots" }
```

---

## 7) Alert Thresholds (Cloud Monitoring)
Create alerts:
- `bin_generation_ms` P95 > **120,000** WARN; > **180,000** PAGE.
- `nb_features` > **12,000** or `geojson_bytes_gz` > **15e6** ERROR → next run should coarsen.
- `occupied_bins == 0` or `nonzero_density_bins == 0` ERROR (regression to Issue #198).
- Container OOM / 5xx spikes → PAGE.

---

## 8) Failure Modes & What You Should See
- **Empty occupancy**: `bins.status="empty"`, ERROR logs with counters; artifacts still written for debug.
- **Soft timeout**: `bins.status="partial"` with message “temporal coarsening applied”; next run should adapt.
- **Saver input mismatch** (previous bug): New saver tolerates GeoJSON/dataclass and logs what’s missing, no `.get()` on `None`.
- **Cache hits**: Second run with identical inputs should show `cache_hit=true` and tiny `bin_generation_ms`.

---

## 9) Post‑Deploy Ops Validation (with Safety & Traffic)
Have FPF / YSSR / SJA validate bins at key pinch points match expectations:
- **Westmorland bridge approaches / ramps (F1/H1)** — 100 m / 60 s preserved.
- **Greenwood crossings (J4/J5)** — visible temporal peaks around crossing pressure.
- **Bridge @ Mill (K1) & Queen Square (L1)** — decay aligns with reopening triggers.

This is where the bin layer materially improves decisions for **reopen timing**, **resource targeting**, and **Last Runner Biker** confirmation.

---

## 10) Known Good Results to Benchmark
From local (reference):
- **Total features**: ~8,800 (after coarsening 35,200 → 8,800).
- **Occupied bins**: ~3,468 (non-zero density).
- **Density range**: 0.0–0.005 p/m²; average ~0.0005 p/m².
- **Runtime**: ~250 ms (gen+serialize).  
**Cloud Run expectation:** higher than local due to I/O and container scheduling, but still **orders of magnitude under the 120 s ceiling**.

---

## 11) Final Decision Logic
- If §§1–4 and §7 are green → **Enable feature flag more broadly**.
- If only performance lags but remains <120s → **still GO**; keep coarsening policy and watch telemetry.
- If any correctness gate fails (schema, reconciliation, or occupancy counters) → **HOLD** and fix before enabling.

---

## Appendix — Quick Checks

### Artifact sanity
- Download `bins.geojson.gz`, check `metadata.saved_at`, counts, and a few features.
- Open `bins.parquet`; confirm types: timestamps, floats, short strings.

### Reconciliation snippet (ad hoc)
- For a chosen segment/window, compute:
  - `sum(density[i] * bin_len_m[i]) / seg_len_m` vs. `segment_density`
  - `sum(flow[i])` vs. `segment_flow`

---

**Bottom line:** Cloud Run should comfortably handle the bin generation with the vectorized pipeline, coarsening policy, and hotspot preservation. Use this runbook to validate under real service conditions, then broaden enablement via the feature flag.
