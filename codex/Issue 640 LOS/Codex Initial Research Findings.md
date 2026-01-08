# Codex Initial Research Findings
**GitHub Issue 640**

## 1. LOS Source Mapping (by component/file)

| Component / File                                          | LOS source (los vs los_class)                                            | Evidence / notes                                                                                                                                                                                                                                        |
| --------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/bins_accumulator.py`                                 | **writes `los_class`** using `DEFAULT_LOS_THRESHOLDS` (local, hardcoded) | `DEFAULT_LOS_THRESHOLDS` is defined in this module and `build_bin_features()` uses it when `los_thresholds=None`, so raw bin features start with a hardcoded LOS band set.:codex-file-citation                                                          |
| `app/density_report.py`                                   | **overwrites `los_class`** using rulebook evaluation                     | `_apply_flagging_to_bin_features()` runs rulebook flagging and updates `props["los_class"] = result.los_class` (schema-aware). Then `_build_parquet_row_from_feature()` writes `los_class` into `bins.parquet`.:codex-file-citation:codex-file-citation |
| `app/new_flagging.py`                                     | **writes `los`** (not `los_class`) from rulebook                         | Rulebook evaluation sets `los` from `result.los_class` and then writes it into the DataFrame; thresholds also appear hardcoded in `get_los_thresholds()` (0.36/0.54/0.72/1.08/1.63).:codex-file-citation                                                |
| `app/save_bins.py`                                        | **propagates `los`** into features if present                            | When flagging succeeds, `los` is used to update features (fallback to `los_class`).:codex-file-citation                                                                                                                                                 |
| `app/core/artifacts/frontend.py` (`segment_metrics.json`) | **prefers `los_class`, then `los`, else reclassify**                     | `generate_segment_metrics_json()` uses the *worst bin* and sets `worst_los` from `los_class` (preferred), `los`, or a rulebook fallback if neither is present (Issue #603 change).:codex-file-citation                                                  |
| `/api/segments/geojson`                                   | **uses `segment_metrics.json` worst_los**                                | Enrichment uses `worst_los` from segment metrics and attaches it to GeoJSON features for the map UI.:codex-file-citation                                                                                                                                |
| `/api/density/segments`                                   | **uses `segment_metrics.json` worst_los**                                | Density table in UI is driven by `segment_metrics.json` and uses `worst_los` there for display/badging.:codex-file-citation:codex-file-citation                                                                                                         |
| UI map (`frontend/static/js/map/segments.js`)             | **consumes `worst_los`**                                                 | Segment styling and tooltip colors are based on `feature.properties.worst_los`.:codex-file-citation                                                                                                                                                     |
| UI bin table (`frontend/templates/pages/density.html`)    | **consumes `los_class` from `/api/bins`**                                | Bin filters and row display use `bin.los_class`.:codex-file-citation                                                                                                                                                                                    |
| `/api/bins`                                               | **maps `bin_summary.json`’s `los` → `los_class`**                        | API builds `los_class` from `bin_data.get("los")`, so it relies on a legacy field name in bin summary artifacts.:codex-file-citation                                                                                                                    |
| `/map/bins`                                               | **uses `los_class` from `bins.parquet`**                                 | Map bin features include `los_class` from the parquet row.:codex-file-citation                                                                                                                                                                          |
| `app/heatmap_generator.py`                                | **no LOS column, density-only**                                          | Heatmap uses density matrix with PowerNorm (`gamma=0.5`) and hardcoded `vmin=0`, `vmax=2.0`. Colors come from reporting config, not from LOS bands.:codex-file-citation                                                                                 |
| `app/core/artifacts/heatmaps.py`                          | **no LOS column, density-only**                                          | Same PowerNorm and `vmax=2.0`; captions compute LOS from *global* rulebook thresholds (not schema-specific).:codex-file-citation:codex-file-citation                                                                                                    |
| `app/new_density_template_engine.py`                      | **recomputes LOS from density**                                          | Flagged-segments table recalculates LOS from worst-bin density using rulebook thresholds, defaulting to `segment_type='on_course_open'` if absent, which can diverge from schema-based bins LOS.:codex-file-citation                                    |


## 2. Threshold Comparison (Hardcoded vs Rulebook)

### Rulebook SSOT (expected)
- **Global LOS bands** are 0.36/0.54/0.72/1.08/1.63, and **A1 binds** to start_corral with more tolerant thresholds (B up to 0.8).

### Other conflicting definitions
- `app/bins_accumulator.py` uses (0.20, 0.40, 0.70, 1.20, 2.00) hardcoded bands.
- `app/new_flagging.py` exposes 0.36/0.54/0.72/1.08/1.63 in get_los_thresholds() (close to rulebook globals, but not schema-specific).
- `app/los.py` uses 0.5/1.0/1.5/2.0/3.0 defaults (legacy Fruin bands).
- `config/reporting.yml` also has 0.5/1.0/1.5/2.0/3.0 thresholds, a separate definition from rulebook. 

### build_bin_features() threshold path
- `build_bin_features()` is called with `los_thresholds=None`, so it falls back to the bins_accumulator defaults unless overridden later; rulebook LOS only gets applied if downstream flagging updates los_class.

## 3. Heatmap Scaling Check
- Both `app/heatmap_generator.py` and `app/core/artifacts/heatmaps.py` **hardcode** PowerNorm(gamma=0.5, vmin=0, vmax=2.0) and map density values directly to color (no explicit LOS buckets).
- This means the heatmap’s orange/red appearance is **continuous** and **nonlinear** relative to LOS thresholds. It is not aligned to the rulebook bands and could make a `start_corral` “B” appear visually orange if density ≈0.75. (Scaling is based purely on density range and PowerNorm, not LOS.)

## 4. UI LOS Trace
- **Segments map + table** are driven by segment_metrics.json → worst_los, and color/badges are applied from that field in the frontend JS/HTML.
- **Bin detail table** uses los_class from /api/bins, which in turn maps bin_summary.json’s los field to los_class (legacy naming).

## 5. A1 Cross‑Check (Pre vs Post Issue #603)

### Pre‑Issue #603 run: THoqXc4d7Q7z8kVXSrBQ2X
- `segment_metrics.json` shows **A1 worst_los = D**, with a long **active_window 07:00–09:40**, consistent with pre-#603 “full window” logic rather than worst-bin extraction.{line_range_start=8 line_range_end=15 path=codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/ui/metrics/segment_metrics.json git_url="https://github.com/thomjeff/run-density/blob/main/codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/ui/metrics/segment_metrics.json#L8-L15"}
- `Density.md` flagged segments table also lists **LOS D** for A1 at density 0.7550.{line_range_start=78 line_range_end=83 path=codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/reports/Density.md git_url="https://github.com/thomjeff/run-density/blob/main/codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/reports/Density.md#L78-L83"}

### Post‑Issue #603 run: SxdpZwRw6PTtpPNEkbGDdd
- `segment_metrics.json` shows **A1 worst_los = B** and a **short active window (07:42–07:44)**, consistent with the “worst bin” logic introduced by #603.{line_range_start=8 line_range_end=14 path=codex/Issue 640 LOS/SxdpZwRw6PTtpPNEkbGDdd/sun/ui/metrics/segment_metrics.json git_url="https://github.com/thomjeff/run-density/blob/main/codex/Issue 640 LOS/SxdpZwRw6PTtpPNEkbGDdd/sun/ui/metrics/segment_metrics.json#L8-L14"}
- `Density.md` still shows **LOS D** for A1 at the same 0.7550 density, suggesting it is recomputing LOS using global/on_course_open thresholds rather than the start_corral schema thresholds.{line_range_start=78 line_range_end=83 path=codex/Issue 640 LOS/SxdpZwRw6PTtpPNEkbGDdd/sun/reports/Density.md git_url="https://github.com/thomjeff/run-density/blob/main/codex/Issue 640 LOS/SxdpZwRw6PTtpPNEkbGDdd/sun/reports/Density.md#L78-L83"}

## Root Cause Analysis (A1 discrepancy)

### Primary mismatch:
A1 is bound to the start_corral schema in the rulebook (B up to 0.8). That makes 0.755 → LOS B under rulebook schema thresholds. However, the density report’s flagged-segments table recomputes LOS from the worst bin density using segment_type → defaults to on_course_open if missing; this uses the global rulebook thresholds (D ≥ 0.72), so 0.755 becomes LOS D in Density.md.

### Why pre‑#603 matched and post‑#603 diverged:
- Pre‑#603 segment_metrics.json already shows worst_los D, likely from legacy logic or density‑based classification rather than the worst bin’s stored los_class. It also shows a full active window, indicating pre‑#603 behavior (not “worst bin” extraction).{line_range_start=8 line_range_end=15 path=codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/ui/metrics/segment_metrics.json git_url="https://github.com/thomjeff/run-density/blob/main/codex/Issue 640 LOS/THoqXc4d7Q7z8kVXSrBQ2X/sun/ui/metrics/segment_metrics.json#L8-L15"}
- Post‑#603 segment_metrics.json now uses los_class from the worst bin (Issue #603 logic), so UI renders B for A1, while the report (and heatmap, which is density‑scaled) still reflect D, producing the discrepancy.{line_range_start=8 line_range_end=14 path=codex/Issue 640 LOS/SxdpZwRw6PTtpPNEkbGDdd/sun/ui/metrics/segment_metrics.json git_url="https://github.com/thomjeff/run-density/blob/main/codex/Issue 640 LOS/SxdpZwRw6PTtpPNEkbGDdd/sun/ui/metrics/segment_metrics.json#L8-L14"}

### Secondary contributors:
- Multiple LOS thresholds in code/config (bins_accumulator defaults, app/los.py, config/reporting.yml, etc.) drift from rulebook SSOT, increasing the risk of mismatches.
- Heatmaps are continuous density maps with a nonlinear PowerNorm scale and hardcoded vmax, which do not align to LOS buckets and can visually imply a different LOS band than the UI table or report.

## Recommendations (SSOT + UX alignment)
### 1. Enforce rulebook SSOT everywhere
- Use `rulebook.get_thresholds(schema_key)` and `classify_los()` for all LOS output (report, UI, captions, any fallback classification).
- Eliminate or deprecate `DEFAULT_LOS_THRESHOLDS` in `bins_accumulator.py`, `app/los.py`, and `config/reporting.yml` as LOS sources (keep only colors in reporting.yml if needed).
- **Why**: Current report recomputation defaults to global thresholds and ignores schema-based rules, causing A1’s LOS D vs B mismatch. 

### 2. Propagate schema context into report tables
- Ensure `segment_type` or `schema_key` travels into the segment summary (used by new_density_template_engine).
- Right now, `summarize_segment_flags_new()` does not include segment_type, so LOS recomputation falls back to on_course_open. 

### 3. Heatmap scaling alignment
- Replace `PowerNorm(vmin=0, vmax=2.0)` with LOS band boundaries (e.g., BoundaryNorm using rulebook thresholds, possibly schema‑specific or global per segment).
- Add colorbar tick labels (A–F) to make the mapping explicit and avoid interpretive drift.
- **Why**: current nonlinear scaling with fixed vmax does not map to LOS buckets and can visually imply “D/E” even when LOS B is correct for start_corral. 

### 4. Column cleanup / naming
- Pick a single column (los_class) as SSOT and migrate UI/API (especially `/api/bins`’s `bin_summary.json` mapping) to consistently use it.
- Reduce fallback logic that reclassifies LOS (which is a source of divergence). 

## Expected Outputs (Delivered)
✅ Table mapping components to LOS source (see Section 1)
✅ Hardcoded vs dynamic threshold comparison (Section 2)
✅ Heatmap scaling review (Section 3)
✅ UI LOS trace (Section 4)
✅ A1 discrepancy analysis with pre/post artifacts (Section 5 + root cause)
✅ Recommendations for SSOT + heatmap alignment (Recommendations section)