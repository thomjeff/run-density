# QA Report – Issue #198 / #217 Bin Dataset Fix & Integration
**Date:** 2025-09-17  
**Reviewer:** Marathon Policy Writer (ChatGPT)  
**Scope:** Review of `Issue-217-ChatGPT-Analysis-Package.zip` (design + results), with emphasis on
- correctness of the **vectorized occupancy fix** (`bins_accumulator.py`)
- integration with existing `density_report.py`
- backward compatibility and operational value
- performance viability for Cloud Run

---

## 1) Executive Summary

**Verdict:** The root cause (structural bins without occupancy) is correctly addressed by the NumPy-based accumulation. The sample outputs (e.g., `density ≈ 0.0020 p/m²`, `flow ≈ 0.0300 p/s`) indicate non-zero, plausible values. With proper integration into `density_report.py`, feature-flag gating, and a small set of guardrails (temporal-first coarsening + hotspot preservation), this is ready for **staging enablement** and then **controlled production**.

**Key conditions for Go-Live:**  
- Wire the accumulator using the **actual** runner/segment/time-window sources from your analysis pipeline.  
- Enforce **bin/time budgets** and **auto-coarsen** on soft timeout.  
- Emit and assert **metadata counters** (`occupied_bins`, `nonzero_density_bins`) and **schema** on CI.  
- Keep **100 m** bins in hotspots; widen time windows for non-hotspots if over budget.

---

## 2) What I Reviewed (based on your package contents)

- `bins_accumulator.py` – vectorized per-window accumulation design (counts, mean speed, density, flow, LOS, metadata).  
- `density_report_current.py` – target for wiring; verifies where bin generation hooks belong.  
- `constants.py` – limits, thresholds, feature-flag names.  
- `Issue198_V2_Artifacts_RootCause_Report.md` – prior diagnosis (zero densities).  
- `test_results.md` – sample values demonstrating non-zero density/flow.  
- `integration_requirements.md` – data mapping and backward compatibility notes.  
- `README.md` – package overview and success criteria.

> I did not run your code here; QA is based on your supplied details and earlier guidance we provided that your patch implements.

---

## 3) Correctness Review – `bins_accumulator.py`

### 3.1 Strengths
- **Vectorized accumulation** using `np.add.at` over bin indices eliminates per-feature loops.  
- **Density** computed as `count / (bin_len_m * width_m)` (p/m²).  
- **Flow** computed as `density * width_m * mean_speed_mps` (p/s), consistent with segment method.  
- **Validation guards:** positive/finite `width_m`, `length_m`, and `bin_len_m`.  
- **Metadata counters:** `occupied_bins`, `nonzero_density_bins`, `total_features`; logs **ERROR** when zero.  
- **Time windows** provided via helper; timestamps carried through to features.  
- **LOS classification** via threshold table (extensible).

### 3.2 Gaps / Risks (minor, fixable)
- **Geometry placeholder:** `geometry=None` in GeoJSON conversion; rely on your existing slicer to fill linestrings per bin. _Action:_ confirm integration calls slicer.  
- **Width source of truth:** If `width_m` comes from segment metadata, ensure **non-trail** vs **trail** segments get realistic widths (e.g., 3–4 m trail, 5–7 m road lane or combined). _Action:_ centralize width lookup.  
- **Timestamp policy:** Uses fixed windows; ensure this matches your segment model’s cadence (60 s baseline).  
- **LOS thresholds:** Ensure alignment with segment LOS thresholds to pass ±2% reconciliation.

**Conclusion:** The accumulator is sound; the above are integration details rather than conceptual issues.

---

## 4) Integration with `density_report.py` – precise wiring

Below is a **drop-in** example of how to integrate, assuming your `results` object exposes:
- `results.segments` iterable with `id`, `length_m`, `width_m` (or derivable), and polyline `coords`
- `results.t0_utc: datetime` and `results.duration_s: int`
- `results.runners` with accessors to determine which segment a runner occupies at a given time and their longitudinal position and speed

> Where your pipeline differs, adjust the mapping adapter only.

```python
# In density_report.py
from app.bins_accumulator import (
    SegmentInfo, build_bin_features, make_time_windows, to_geojson_features
)

def generate_bin_dataset(results, *, bin_size_km=0.1, dt_seconds=60, logger=None):
    # 1) Segment catalog
    segments = {}
    for seg in results.segments:
        seg_id = seg.id
        length_m = float(seg.length_m)
        # preferred: seg.width_m from course metadata; otherwise fallback by type
        width_m = float(getattr(seg, "width_m", 3.0))
        coords = getattr(seg, "coords", None)
        segments[seg_id] = SegmentInfo(seg_id, length_m, width_m, coords)

    # 2) Time windows
    t0_utc = results.t0_utc
    total_duration_s = int(results.duration_s)
    time_windows = make_time_windows(t0=t0_utc, duration_s=total_duration_s, dt_seconds=dt_seconds)

    # 3) Runner→segment/window mapping (adapter to your model)
    runners_by_segment_and_window = build_runner_window_mapping(results, time_windows)

    # 4) Accumulate
    bin_build = build_bin_features(
        segments=segments,
        time_windows=time_windows,
        runners_by_segment_and_window=runners_by_segment_and_window,
        bin_size_km=bin_size_km,
        los_thresholds=None,
        logger=logger,
    )

    # 5) Build geometries + GeoJSON
    geojson_features = to_geojson_features(bin_build.features)
    for f in geojson_features:
        seg_id = f["properties"]["segment_id"]
        start_km = f["properties"]["start_km"]
        end_km   = f["properties"]["end_km"]
        # f["geometry"] = build_linestring_for_bin(segments[seg_id].coords, start_km, end_km)
        # ^ call your existing geometry slicer here

    geojson = {"type": "FeatureCollection", "features": geojson_features, "metadata": bin_build.metadata}

    # 6) Safety checks
    md = geojson.get("metadata", {})
    occ = int(md.get("occupied_bins", 0))
    ndz = int(md.get("nonzero_density_bins", 0))
    if occ == 0 or ndz == 0:
        if logger:
            logger.error("🛑 Empty bin dataset: occupied_bins=%s nonzero_density_bins=%s", occ, ndz)
        # Optionally mark status for UI telemetry
        geojson.setdefault("metadata", {})["status"] = "empty"

    return geojson
```

**Mapping adapter (example):**
```python
def build_runner_window_mapping(results, time_windows):
    import numpy as np
    mapping = {seg.id: {} for seg in results.segments}

    for (t_start, t_end, w_idx) in time_windows:
        tm = t_start + (t_end - t_start)/2  # midpoint sampling
        for runner in results.runners:
            seg_id = runner.segment_at(tm)
            if seg_id is None:
                continue
            pos_m = runner.position_m_along(seg_id, tm)  # meters
            speed = runner.speed_mps_at(seg_id, tm)      # m/s
            bucket = mapping[seg_id].setdefault(w_idx, {"pos_m": [], "speed_mps": []})
            bucket["pos_m"].append(pos_m)
            bucket["speed_mps"].append(speed)

    # convert to arrays
    for seg_id, windows in mapping.items():
        for w_idx, d in windows.items():
            d["pos_m"]   = np.asarray(d["pos_m"],   dtype=np.float64)
            d["speed_mps"] = np.asarray(d["speed_mps"], dtype=np.float64)
    return mapping
```

**Backfill of geometry:** use your **existing** linestring slicer; the accumulator intentionally leaves geometry as `None`.

---

## 5) Backward Compatibility

- **Feature flag:** keep `ENABLE_BIN_DATASET=false` by default.  
- **No regression path:** if bins fail validation (`occupied_bins==0 or nonzero_density_bins==0`), continue with segment-only outputs and set `bins.status="empty"` in manifest for UI messaging.  
- **Schema versioning:** set/keep `BIN_SCHEMA_VERSION = "1.0.0"`. If you alter LOS thresholds or add columns, bump minor/patch.  
- **Dual artifacts:** keep writing **GeoJSON + Parquet**; unchanged consumers continue to function.

---

## 6) Performance for Cloud Run

**Baseline expectations with vectorization (rule-of-thumb):**
- Typical FM scenarios (≈ 36 segments, 60 s windows, 0.1 km bins) should stay **≤120 s** for the bin step on 2 vCPU if the mapping adapter is efficient and serialization is streamed.  
- If over budget, apply **temporal-first coarsening** (120 s windows) for non-hotspots, then **spatial** coarsening (0.2–0.3 km) outside hotspots.

**Add these guardrails (minimal change):**
- **Projected feature budget:** cap at **10k**; estimate before compute and coarsen non-hotspots.  
- **Soft timeout reaction:** if `elapsed > MAX_BIN_GENERATION_TIME_SECONDS`, first **double dt_seconds** (≤180), then **coarsen non-hotspot bins** to 0.2 km, else mark `status="partial"`.  
- **Hotspot preservation:** keep 0.1 km & 60 s on bridge ramps, crossings, downtown; coarsen elsewhere.

---

## 7) Validation & QA Checklist (CI/E2E)

### 7.1 Schema & metadata
- [ ] GeoJSON has `bin_id, segment_id, start_km, end_km, t_start, t_end, density, flow, los_class, bin_size_km`.  
- [ ] Parquet mirrors the above (plus `schema_version`, `analysis_hash`).  
- [ ] Metadata includes `occupied_bins`, `nonzero_density_bins`, `total_features`, `generated_at`, `schema_version`.

### 7.2 Consistency
- [ ] For each (segment, window): `mean_bin_density_weighted_by_length ≈ segment_density_mean (±2%)`.  
- [ ] Sum of bin flows over segment/window ≈ segment flow (±5%).

### 7.3 Performance
- [ ] Bin step P95 ≤ 120 s (temporary ceiling ≤ 150 s OK with auto-coarsen).  
- [ ] GeoJSON gz ≤ 15 MB; features ≤ 10k.  
- [ ] Peak RSS ≤ 1.5 GB.

### 7.4 Correctness smoke
- [ ] `occupied_bins > 0` and `nonzero_density_bins > 0` in staging scenarios.  
- [ ] LOS class transitions visible at known pinch points.

### 7.5 Failure paths
- [ ] Empty mapping → ERROR log + `bins.status="empty"`, report proceeds.  
- [ ] Soft-timeout → coarsen and continue, not fail.

---

## 8) Risks / Pitfalls & Mitigations

- **Empty occupancy due to adapter:** If `segment_at(tm)` or `position_m_along` return `None/NaN`, you’ll see zeros. _Mitigation:_ assert counts by (segment, window); log top-3 with sample runner IDs.  
- **Width misconfiguration:** Too small/large `width_m` skews density. _Mitigation:_ central width catalog + unit tests.  
- **Serialization hotspots:** Python dict construction can be slow. _Mitigation:_ write **Parquet first**; generate GeoJSON lazily and gzip.  
- **Hotspot definitions drift:** Keep a static list in config; optionally mark segments with dynamic `peak_los>=D` as hotspots post-pass.

---

## 9) Recommended Action Plan (short, actionable)

1. **Integrate** `bins_accumulator.py` as above; wire geometry slicing.  
2. **Implement temporal-first coarsening** + **hotspot preservation** (non-hotspots only).  
3. **Add CI tests** for (a) schema, (b) reconciliation ±2%, (c) metadata counters, (d) performance smoke.  
4. **Stage deploy** with `ENABLE_BIN_DATASET=true` on controlled scenarios; capture timings & sizes.  
5. **Prod deploy** with feature flag default **false**, then enable per-scenario as needed until telemetry is green.

---

## 10) Ready-to-merge snippets (copy/paste)

**Soft-timeout reaction & budgets (in `density_report.py` around the bin step):**
```python
start = time.monotonic()
gj = generate_bin_dataset(results, bin_size_km=bin_size_km, dt_seconds=dt_seconds, logger=logger)
elapsed = time.monotonic() - start

md = gj.get("metadata", {})
features = int(md.get("total_features", 0))

if elapsed > MAX_BIN_GENERATION_TIME_SECONDS or features > BIN_MAX_FEATURES:
    # temporal-first coarsening for non-hotspots
    dt_seconds = min(max(dt_seconds, 120), 180)
    # optional: spatial coarsen non-hotspots only
    if features > BIN_MAX_FEATURES and bin_size_km < 0.2:
        bin_size_km = 0.2
    logger.warning("Coarsening bins due to budget: dt=%ss, bin=%skm", dt_seconds, bin_size_km)
    gj = generate_bin_dataset(results, bin_size_km=bin_size_km, dt_seconds=dt_seconds, logger=logger)
```

**Empty-occupancy ERROR & manifest flag:**
```python
md = gj.get("metadata", {})
occ = int(md.get("occupied_bins", 0))
ndz = int(md.get("nonzero_density_bins", 0))
if occ == 0 or ndz == 0:
    logger.error("🛑 Empty bin dataset post-accumulation: %s", md)
    gj.setdefault("metadata", {})["status"] = "empty"
```

---

## 11) Conclusion

- The implemented **vectorized fix** solves the fundamental problem (zero densities).  
- Integration is straightforward: **map runners to (segment, window) → positions/speeds**, call the accumulator, add geometry, enforce budgets.  
- With minor coarsening controls and hotspot preservation, Cloud Run performance will be within an acceptable envelope **without sacrificing operational intelligence** (Last Runner Biker & reopening calls).

**Recommendation:** Proceed to **staging enablement**, capture telemetry, and then conditional production roll-out under the feature flag.
