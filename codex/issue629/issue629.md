# Enhance `flow.csv` to Align with Updated Architecture and Zone-Level Reporting
_This is part of Flow enhancements for the end-user via UI (#628) and CSV this issue #629._
https://github.com/thomjeff/run-density/issues/629

## Files for Codex:
- Are located in /codex/7iHmDgGFMZdpjLmZRVgYWY
- Flow.csv (sunday): /codex/7iHmDgGFMZdpjLmZRVgYWY/sun/reports
- fz.parquet (zone level flow details): /codex/7iHmDgGFMZdpjLmZRVgYWY/sun/reports

## Overview

The current `flow.csv` (example for sunday: [flow.csv](https://github.com/user-attachments/files/24479560/Flow.csv) )contains legacy and redundant metadata fields that are now tracked elsewhere (`analysis.json`, `metadata.json`, and parquet files such as `fz.parquet`, `fz_runners.parquet`, and `audit.parquet`). This issue proposes a cleanup and structural improvement of `flow.csv` for clarity, maintainability, and future usability.

## Tasks

### 1. **Remove the following deprecated fields:**
These fields are now part of `analysis.json` or `metadata.json`, and do not belong in the analysis report:
- `analysis_timestamp`
- `app_version`
- `environment`
- `data_source`
- `start_times`
- `min_overlap_duration`
- `conflict_length_m`
- `sample_a` (see note below)
- `sample_b` (see note below)

> These are no longer needed as runner-level details can be queried from `fz.parquet`, `fz_runners.parquet`, and `audit.parquet`.
> Any back-end to calculate `sample_a` and `sample_b` can be removed from code.

---

### 2. **Investigate removal of these internal debug flags:**
These are likely redundant or unused. If not actively consumed in downstream reports/UI, they should be removed:
- `spatial_zone_exists`
- `temporal_overlap_exists`
- `true_pass_exists`
- `has_convergence_policy`
- `has_convergence`
- `no pass reason`

> If any of these are still needed for debugging or quality assurance, consider moving them to an internal `.debug` export.

---

### 3. **Investigate and document `overtaking_load_a/b` and `max_overtaking_load_a/b`**
These fields are currently unclear. Questions:
- What is the unit and formula behind these metrics?
- Are they derived from runner density during overtaking events?
- Should they be added to `fz.parquet` or `fz_runners.parquet`?

**Action:**
- Audit how these are calculated in the codebase
- If useful and interpretable, document and potentially export to `fz` or `fz_runners` for richer analytics
- Are they accurate?

---

### 4. **Update structure: shift to zone-level reporting**
Currently, `flow.csv` is one row per segment. Instead, update it to be:
- One row per **`seg_id` / `zone_index`**
- Ordered by `seg_id`, then `zone_index`
- Includes zone-level metrics per row (copresence, overtaken, overtaking, multi-category, participants involved, etc.)

**Column changes:**

| Current         | Replace With       |
|----------------|--------------------|
| from_km_a      | zone_start_a       |
| to_km_a        | zone_end_a         |
| from_km_b      | zone_start_b       |
| to_km_b        | zone_end_b         |

> Zone start/end values are already available in `fz.parquet`. You can infer full segment `from_km` / `to_km` as the first and last zone.

---

## Current/Final Fields (with keep, remove, research delta)
Those with research will need to be researched first to arrive at a keep or remove determination. Fields are to be presented in the following order:

| field	 |action	 |note |
| ------- | --------| -----|
| seg_id	 |keep	 |-  |
| segment_label |	keep	 |- |
| event_a	 |keep	 |- |
| event_b	 |keep	 |- |
| total_a	 |keep	 |- |
| total_b	 |keep	 |- |
| flow_type	 |keep	 |-
| from_km_a	 |replace	 |zone_start_a |
| to_km_a	 |replace	 |zone_end_a |
| from_km_b	 |replace	 |zone_start_b |
| to_km_b	 |replace	 |zone_end_b |
| width_m	 |keep	 | - |
| overtaking_a	 |update  | value for the zone_index |
| overtaking_b	 |update  | value for the zone_index |
| sample_a	 |remove	 |- |
| sample_b	 |remove	 |- |
| pct_a	 |keep	 |- |
| pct_b	 |keep |	- |
| copresence_a	 |update	 |value for the zone_index |
| copresence_b	 |update	 |value for the zone_index |
| unique_encounters	 |update	 |value for the zone_index |
| participants_involved	 |update |	value for the zone_index |
| overtaking_load_a	 |research |	- |
| overtaking_load_b	 |research	 |- |
| max_overtaking_load_a	 |research |	- |
| max_overtaking_load_b	 |research	 |- |
| spatial_zone_exists	 |research |	- |
| temporal_overlap_exists	 |research	 |- |
| true_pass_exists	 |research	 |- |
| has_convergence_policy	 |research	 |- |
| has_convergence	 |research	 |- |
| convergence_zone_start	 |remove	 |replaced by zone_start_* |
| convergence_zone_end	 |remove	 |replaced by zone_end_* |
| no_pass_reason_code	 |research	 |- |
| conflict_length_m	 |remove	 |- |
| worst_zone_index	 |remove	 |- |
| convergence_points_json	 |remove	 |- |
| analysis_timestamp	 |remove	 |- |
| app_version	 |remove	 |- |
| environment	 |remove	 |- |
| data_source	 |remove	 |- |
| start_times	 |remove	 |- |
| min_overlap_duration	 |remove	 |- |
| conflict_length_m	 |remove |	- |


---

## Notes
- There are **296 zones across 27 segments**
- With zone-level output, `flow.csv` can support more detailed trend analyses and UI features (e.g. flow tables similar to density breakdowns).
- This format matches the zone indexing already used in `fz.parquet`.

---

## Deliverables

- [ ] Cleaned and lean `flow.csv` output (one row per segment/zone)
- [ ] Updated exporter logic in backend
- [ ] Documentation updates to `flow.md` and `fz_runners.md` as needed
- [ ] Decision on `overtaking_load_*` fields