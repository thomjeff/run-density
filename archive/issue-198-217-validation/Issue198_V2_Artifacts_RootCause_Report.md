# Issue #198 – V2 Artifact Triage & Root-Cause Report

**Generated:** 2025-09-17T22:27:33

## What I inspected

- `/mnt/data/Issue-198-ChatGPT-Review-Package-v2-Performance-Plan.zip` → extracted to `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package-v2-Performance-Plan`
- `/mnt/data/Issue-198-ChatGPT-Review-Package 2.zip` → extracted to `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2`

## Artifact checks (GeoJSON)

- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package-v2-Performance-Plan/latest-bin-dataset.geojson` → features: **2104**, zero_density: **2104**, nonzero_density: **0**
  - Missing/NA props: bin_id_missing_or_na:2104, t_start_missing_or_na:2104, t_end_missing_or_na:2104, flow_missing_or_na:2104, los_class_missing_or_na:2104
  - Sample properties: `{"segment_id": "A1", "segment_label": "Start to Queen/Regent", "bin_index": 0, "start_km": 0.0, "end_km": 0.1, "density": 0.0, "density_level": "A", "overtakes": {"Full_vs_Half": 1, "Half_vs_Full": 1}...`
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package-v2-Performance-Plan/bin-dataset-sample.geojson` → **ERROR**: Failed to parse JSON: Expecting ',' delimiter: line 1 column 3001 (char 3000)
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/Issue-198-ChatGPT-Review-Package/samples/sample-bin-dataset-excerpt.geojson` → **ERROR**: Failed to parse JSON: Invalid control character at: line 1 column 5070 (char 5069)
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/Issue-198-ChatGPT-Review-Package/reports/2025-09-17-1352-BinDataset.geojson` → features: **2104**, zero_density: **2104**, nonzero_density: **0**
  - Sample properties: `{"segment_id": "A1", "segment_label": "Start to Queen/Regent", "bin_index": 0, "start_km": 0.0, "end_km": 0.1, "density": 0.0, "density_level": "A", "overtakes": {"Full_vs_Half": 1, "Half_vs_Full": 1}...`
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/Issue-198-ChatGPT-Review-Package/reports/2025-09-17-1348-BinDataset.geojson` → features: **2104**, zero_density: **2104**, nonzero_density: **0**
  - Sample properties: `{"segment_id": "A1", "segment_label": "Start to Queen/Regent", "bin_index": 0, "start_km": 0.0, "end_km": 0.1, "density": 0.0, "density_level": "A", "overtakes": {"Full_vs_Half": 1, "Half_vs_Full": 1}...`
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/__MACOSX/Issue-198-ChatGPT-Review-Package/reports/._2025-09-17-1352-BinDataset.geojson` → **ERROR**: Failed to parse JSON: Expecting value: line 1 column 1 (char 0)
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/__MACOSX/Issue-198-ChatGPT-Review-Package/reports/._2025-09-17-1348-BinDataset.geojson` → **ERROR**: Failed to parse JSON: Expecting value: line 1 column 1 (char 0)

**Conclusion:** In **all valid GeoJSONs**, `density` is `0.0` for every feature. Expected fields (`bin_id`, `t_start`, `flow`, `los_class`) are **missing or NA** in v2 as well.

## Artifact checks (Parquet)

- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package-v2-Performance-Plan/latest-bin-dataset.parquet` → **UNREADABLE HERE** (no Parquet engine in this environment).
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/Issue-198-ChatGPT-Review-Package/samples/sample-bin-dataset.parquet` → **UNREADABLE HERE** (no Parquet engine in this environment).
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/Issue-198-ChatGPT-Review-Package/reports/2025-09-17-1348-BinDataset.parquet` → **UNREADABLE HERE** (no Parquet engine in this environment).
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/Issue-198-ChatGPT-Review-Package/reports/2025-09-17-1352-BinDataset.parquet` → **UNREADABLE HERE** (no Parquet engine in this environment).
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/__MACOSX/Issue-198-ChatGPT-Review-Package/reports/._2025-09-17-1348-BinDataset.parquet` → **UNREADABLE HERE** (no Parquet engine in this environment).
- `/mnt/data/extracted_Issue-198-ChatGPT-Review-Package 2/__MACOSX/Issue-198-ChatGPT-Review-Package/reports/._2025-09-17-1352-BinDataset.parquet` → **UNREADABLE HERE** (no Parquet engine in this environment).

> Note: I couldn’t read Parquet in this environment due to missing engines, but the GeoJSON already proves the **all-zero density** condition.

## Code path review (density_report.py)

- `generate_bin_dataset(...)` calls `bin_analysis.get_all_segment_bins(...)` then wraps with `generate_bins_geojson_with_temporal_windows(...)`.
- `generate_bins_geojson_with_temporal_windows(...)` **does not compute density**; it **expects** each feature to already have a meaningful `density` (and optionally `width_m`). It then derives `t_start/t_end` and `flow = density * width_m * speed_mps`.

### Likely root cause

`get_all_segment_bins(...)` (or whatever populates `all_bins`) is returning **structure-only bins** with zero occupancy; hence `density==0` everywhere. The enhancer then keeps `density=0` and produces `flow=0`. If enhancer is skipped/fails, you also lose `bin_id/t_start/los_class`.

### Evidence

- v2 GeoJSON shows domain props like `overtakes`, `co_presence`, `rsi_score` (from base generator), but still **density=0**.

## High-confidence fixes (in priority order)

1. **Populate bin occupancy before GeoJSON:** In the bin assembly step that precedes `generate_bins_geojson`, aggregate per time window and spatial bin:
   - `count` = number of runner presences in `[t_start,t_end)` intersecting the bin
   - `width_m` = segment width (constant per segment or per-bin)
   - `density` = `count / (bin_length_m * width_m)`
   - **Use vectorized `numpy` accumulation** (see prior guidance) to avoid perf cliffs.

2. **Verify inputs are non-empty:** Ensure the `AnalysisContext` feeds the same **runners** and **segments** used by the segment-level analysis. If `pace_csv`/`segments_csv` resolve to empty frames, you’ll produce zeros.

3. **Unit test the join:** Add a test that creates a tiny synthetic segment (length 300m, width 5m), two 60s windows, and 10 synthetic runners with fixed speeds. Assert that at least one bin/window pair yields `density>0` and that segment totals reconcile (±2%).

4. **Guard against enhancer bypass:** Ensure `generate_bins_geojson_with_temporal_windows(...)` always runs; log a warning if the base generator returns features missing `bin_id` etc., and fill them.

5. **Expose counters in metadata:** `bins.metadata` should include `occupied_bins`, `nonzero_density_bins`, and `avg_density` to catch this early.

## Minimal instrumentation to add now

Add these counters right after occupancy aggregation and again after GeoJSON serialization:
- `runners_input_count`
- `segments_input_count`
- `projected_feature_count`
- `occupied_bins` (density>0)
- `nonzero_density_bins` (density>0)
- `max_bin_density`

If `occupied_bins==0`, **short-circuit** with an ERROR log including sample rows from runners/segments.

## Why your artifacts showed 2,104 or 1,059 features but no data

- The base generator is emitting geometric bins and a few structural props, but **no occupancy math** is wired to those props. Hence, every bin has `density=0`. The enhancer can’t invent density; it only refines timing and flow **based on** density.

## Next-step debugging checklist (fast)

- [ ] Print `len(runners)`, `len(segments)`, and a sample of runner positions at one analysis window during binning.
- [ ] For one segment, one window, print the first 10 `pos_m`, derived `bin_idx`, and the resulting `counts` vector.
- [ ] Confirm `width_m` is non-zero and `bin_length_m = bin_size_km*1000`.
- [ ] Confirm `dt_seconds` matches the time slicing used elsewhere (e.g., 60s).
- [ ] Verify that `start_times` are in **minutes** if that’s what `get_all_segment_bins` expects.
