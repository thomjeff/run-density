# SSOT Compliance Analysis: Report Generation

## Summary

Analysis of whether Density, Flow, and Locations reports follow Single Source of Truth (SSOT) principles established in Issue #574.

---

## 1. Density Report ❌ **VIOLATES SSOT**

**Current State:**
- Function: `generate_new_density_report()` in `app/new_density_report.py`
- Data Source: Recalculates from `bins.parquet`
- Violates SSOT: Yes

**Expected SSOT:**
- Should use: `{day}/ui/metrics/segment_metrics.json` (generated in Phase 4.1)

**Issue:** #600 (created)

**Details:**
- Phase 4.1 generates `segment_metrics.json` with all segment metrics
- Phase 5 (report generation) ignores this and recalculates from bins.parquet
- This duplicates calculation logic and creates inconsistency risk

---

## 2. Flow Report ⚠️ **PARTIALLY COMPLIANT** (Needs Clarification)

**Current State:**
- Function: `generate_flow_report_v2()` in `app/core/v2/reports.py`
- Data Source: Uses `flow_results` parameter (in-memory from Phase 3.1)
- Uses Persisted JSON: No (but flow_results.json exists in computation/)

**Expected SSOT:**
- Option A: `flow_results.json` from `{day}/computation/flow_results.json` (Phase 3.2)
- Option B: `flow.json` from `{day}/ui/geospatial/flow.json` (Phase 4.1)

**Current Implementation:**
```python
# Phase 3.1: Compute flow
flow_results = analyze_temporal_flow_segments_v2(...)

# Phase 3.2: Persist to JSON (but not used by reports)
flow_results.json → computation/flow_results.json

# Phase 4.1: Generate UI artifact (but not used by reports)
flow.json → ui/geospatial/flow.json

# Phase 5: Report generation
generate_flow_report_v2(flow_results=flow_results[day])  # Uses in-memory
```

**Analysis:**
- Flow report uses in-memory computation results, not persisted artifacts
- Pipeline code (line 1343) has comment: "Still using in-memory for now (JSON structure ready)"
- Flow.json in ui/geospatial/ is a UI-facing artifact with different schema
- flow_results.json in computation/ matches the computation output structure

**Potential Issue:**
- If Issue #574 goal is "pure templating, no inline calculations", reports should load from persisted JSON
- Currently uses in-memory data, which works but doesn't align with "reports load from JSON artifacts"

---

## 3. Locations Report ⚠️ **PARTIALLY COMPLIANT** (Needs Clarification)

**Current State:**
- Function: `generate_locations_report_v2()` in `app/core/v2/reports.py`
- Data Source: Uses `locations_df` parameter (in-memory from Phase 2)
- Uses Persisted JSON: Partially (locations_results.json exists, used as fallback)

**Expected SSOT:**
- Should use: `locations_results.json` from `{day}/computation/locations_results.json` (Phase 3.2)

**Current Implementation:**
```python
# Phase 2: Load locations
locations_df = load_locations(...)

# Phase 3.2: Persist to JSON
locations_results.json → computation/locations_results.json

# Phase 5: Report generation
locations_df_from_json = load_from_json() if exists else locations_df
generate_locations_report_v2(locations_df=locations_df_from_json or locations_df)
```

**Analysis:**
- Pipeline (line 1347) uses JSON if available, falls back to in-memory
- This is closer to SSOT compliance than flow report
- However, the primary data source is still in-memory DataFrame
- No UI artifacts for locations (unlike density/flow)

**Status:**
- Better than Flow Report (attempts to use JSON)
- But still prefers in-memory over persisted artifacts

---

## Comparison Matrix

| Report Type | Uses In-Memory | Uses Persisted JSON | Uses UI Artifacts | SSOT Compliance |
|-------------|---------------|---------------------|-------------------|-----------------|
| **Density** | ❌ No (recalculates) | ❌ No | ❌ No | ❌ **VIOLATES** |
| **Flow** | ✅ Yes (primary) | ❌ No | ❌ No | ⚠️ **PARTIAL** |
| **Locations** | ✅ Yes (primary) | ⚠️ Fallback only | N/A | ⚠️ **PARTIAL** |

---

## Recommendations

### High Priority
1. **Density Report** (#600): Refactor to use `segment_metrics.json` as SSOT

### Medium Priority
2. **Flow Report**: Consider loading from `flow_results.json` instead of in-memory
   - Pipeline comment indicates "JSON structure ready" but not implemented
   - Aligns with Issue #574 goal of "reports load from JSON artifacts"

3. **Locations Report**: Make JSON the primary source, not fallback
   - Currently loads JSON but prefers in-memory
   - Should prioritize persisted artifacts

---

## Key Findings

1. **Density Report** clearly violates SSOT by recalculating instead of using segment_metrics.json
2. **Flow Report** uses in-memory data; persisted JSON exists but not used by reports
3. **Locations Report** has JSON loading but prioritizes in-memory data
4. Pipeline code (pipeline.py:1335-1337) acknowledges this with TODO comment:
   > "TODO: Full refactor to load from JSON only (remove in-memory fallback in future)"

All three reports have room for improvement to fully align with Issue #574's SSOT principle.
