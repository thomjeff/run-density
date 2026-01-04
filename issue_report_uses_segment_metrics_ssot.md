# Reports Should Use Persisted JSON Artifacts as Single Source of Truth

**Type:** Enhancement  
**Related Issue:** #574  
**Priority:** High (affects data consistency and DRY principle)

## Current State

All three report types (Density, Flow, Locations) currently use in-memory data or recalculate metrics instead of consuming persisted JSON artifacts, violating the Single Source of Truth (SSOT) principle established in Issue #574.

---

## 1. Density Report ❌ **VIOLATES SSOT**

### Current Flow (Violates SSOT):
1. **Phase 4.1**: UI Artifacts Generation
   - Calculates segment metrics from bins
   - Writes to `{day}/ui/metrics/segment_metrics.json`
   
2. **Phase 4.2**: Derived Metrics Calculation  
   - ✅ **Correctly uses** `segment_metrics.json` for RES and operational status
   
3. **Phase 5**: Report Generation
   - ❌ **VIOLATES SSOT** - Recalculates metrics from bins:
     - Reads `bins.parquet`
     - Re-applies flagging logic (`apply_new_flagging`)
     - Re-calculates segment summaries (`summarize_segment_flags_new`)
     - Re-computes statistics (`get_flagging_summary_for_report`)
     - Does NOT use `segment_metrics.json`

### Code Location:
- **Violation**: `app/new_density_report.py::generate_new_density_report()` (lines 209-227)
- **Pipeline comment**: `app/core/v2/pipeline.py` line 1265 states "Reports load from JSON artifacts (pure templating, no inline calculations)" but this is not implemented

### Impact:
- Metrics calculated in Phase 4.1 vs Phase 5 may differ
- Duplicate calculation logic creates maintenance burden
- Inconsistency risk (e.g., peak_rate conversion issue that was fixed)
- Violates DRY principle

---

## 2. Flow Report ⚠️ **PARTIALLY COMPLIANT**

### Current Flow:
1. **Phase 3.1**: Core Computation
   - Computes flow analysis: `flow_results = analyze_temporal_flow_segments_v2(...)`
   - Results stored in-memory

2. **Phase 3.2**: Computation Persistence
   - Persists to `{day}/computation/flow_results.json`
   - ✅ JSON structure created

3. **Phase 4.1**: UI Artifacts Generation
   - Generates `{day}/ui/geospatial/flow.json` (UI-facing artifact)

4. **Phase 5**: Report Generation
   - ❌ **Uses in-memory data** instead of persisted JSON:
     - `generate_flow_report_v2(flow_results=flow_results[day])` uses in-memory dict
     - Does NOT load from `computation/flow_results.json`
     - Pipeline comment (line 1343): "Still using in-memory for now (JSON structure ready)"

### Code Location:
- **Violation**: `app/core/v2/reports.py::generate_flow_report_v2()` (line 377)
- **Pipeline**: `app/core/v2/pipeline.py` line 1343 passes in-memory `flow_results`

### Impact:
- Works correctly but doesn't align with Issue #574 goal of "reports load from JSON artifacts"
- Inconsistent with SSOT principle (reports should consume persisted artifacts)
- JSON structure exists but is unused by reports

---

## 3. Locations Report ⚠️ **PARTIALLY COMPLIANT**

### Current Flow:
1. **Phase 2**: Data Loading
   - Loads locations: `locations_df = load_locations(...)`
   - Stored in-memory

2. **Phase 3.2**: Computation Persistence
   - Persists to `{day}/computation/locations_results.json`
   - ✅ JSON structure created

3. **Phase 5**: Report Generation
   - ⚠️ **Uses in-memory as primary, JSON as fallback**:
     - Pipeline loads JSON: `locations_df_from_json = load_from_json()` (line 1316)
     - But passes: `locations_df_from_json if locations_df_from_json is not None else locations_df` (line 1347)
     - Prioritizes in-memory DataFrame over persisted JSON

### Code Location:
- **Violation**: `app/core/v2/reports.py::generate_locations_report_v2()` (line 511)
- **Pipeline**: `app/core/v2/pipeline.py` line 1347 uses JSON as fallback only

### Impact:
- JSON loading exists but is treated as fallback
- Should prioritize persisted artifacts over in-memory data
- Not fully aligned with SSOT principle

---

## Deviation from Issue #574

Issue #574 established a single source of truth architecture where:
- Metrics/data are computed/persisted **once** in earlier phases
- All downstream consumers (UI artifacts, derived metrics, reports) use the same persisted values
- This ensures consistency and follows DRY (Don't Repeat Yourself) principle
- Reports should load from JSON artifacts (pure templating, no inline calculations)

**Current deviations:**
1. **Density Report**: Duplicates calculation logic instead of consuming from `segment_metrics.json`
2. **Flow Report**: Uses in-memory computation results instead of persisted `flow_results.json`
3. **Locations Report**: Prioritizes in-memory data over persisted `locations_results.json`

All three violate the architectural principle established in Issue #574.

---

## Impact

### Data Consistency Risk
- Metrics/data calculated in different phases may differ
- Potential bugs in one path but not the other
- Conversion/formula differences (e.g., peak_rate conversion issue that was fixed for density)

### Maintenance Burden
- Calculation/logic exists in multiple places:
  - UI artifacts generation
  - Report generation (density recalculates, flow/locations use in-memory)
  - Changes must be made in multiple locations to maintain consistency

### Performance
- Unnecessary recalculation (density) or data duplication (flow/locations)
- In-memory data requires keeping objects alive between phases

### Architectural Violation
- Contradicts the single source of truth principle established in Issue #574
- Pipeline comment (lines 1335-1337) acknowledges this: "TODO: Full refactor to load from JSON only (remove in-memory fallback in future)"

---

## Proposed Fix

### Option 1: Load from Persisted JSON Artifacts (Recommended)

Modify report generation functions to:

1. **Density Report**: Load `segment_metrics.json` from `{day}/ui/metrics/segment_metrics.json`
2. **Flow Report**: Load `flow_results.json` from `{day}/computation/flow_results.json`
3. **Locations Report**: Load `locations_results.json` from `{day}/computation/locations_results.json`

### Implementation Steps:

#### For Density Report:
1. Add function to load and convert `segment_metrics.json` to segment_summary DataFrame format
2. Modify `generate_new_density_report()` to:
   - Accept optional `segment_metrics_path` parameter
   - Load segment_metrics.json if available
   - Convert to segment_summary DataFrame
   - Fall back to current calculation if segment_metrics.json not found (backward compatibility)
3. Update `generate_density_report_v2()` in `app/core/v2/reports.py` to pass segment_metrics.json path
4. Ensure template engine can work with metrics from either source (JSON or recalculated)

#### For Flow Report:
1. Modify `generate_flow_report_v2()` to:
   - Accept optional `flow_results_path` parameter
   - Load flow_results.json if available
   - Fall back to in-memory flow_results parameter if JSON not found
2. Update pipeline to pass JSON path instead of (or in addition to) in-memory data
3. Remove in-memory dependency once JSON loading is verified

#### For Locations Report:
1. Modify `generate_locations_report_v2()` to:
   - Accept optional `locations_results_path` parameter
   - Prioritize loading from JSON over in-memory DataFrame
   - Fall back to in-memory only if JSON not available
2. Update pipeline to pass JSON path and prioritize JSON over in-memory

### Benefits:

- ✅ Single source of truth for all report data
- ✅ Eliminates calculation duplication (density)
- ✅ Removes in-memory dependencies (flow, locations)
- ✅ Ensures UI and Report use identical values (density)
- ✅ Aligns with Issue #574 architecture
- ✅ Maintains backward compatibility (fallback if JSON missing)
- ✅ Supports future "re-run reports from artifacts" functionality

### Considerations:

- Template engines may need adjustments to handle data from JSON vs in-memory
- Some report sections may still need bins.parquet for detailed bin-level data (density)
- Need to ensure all required fields are present in JSON artifacts
- Flow report uses flow_results.json (computation) vs flow.json (UI artifact) - need to decide which is SSOT

---

## Acceptance Criteria

- [ ] **Density Report**: Uses `segment_metrics.json` as primary data source
- [ ] **Flow Report**: Uses `flow_results.json` as primary data source (or in-memory fallback removed)
- [ ] **Locations Report**: Uses `locations_results.json` as primary data source (not fallback)
- [ ] Metrics in Density.md report match UI metrics (from segment_metrics.json)
- [ ] No duplicate calculation logic in report generation
- [ ] No in-memory data dependencies for report generation
- [ ] Backward compatibility maintained (fallback if JSON missing)
- [ ] All existing tests pass
- [ ] E2E tests verify UI and Report data/metrics match
- [ ] Pipeline TODO comment (line 1337) can be removed

---

## Related Files

### Density Report:
- `app/new_density_report.py` - Report generation (needs modification)
- `app/core/v2/reports.py` - Report generation orchestration (needs modification)
- `app/core/v2/pipeline.py` - Pipeline orchestration (comment at line 1265 needs to be implemented)

### Flow Report:
- `app/core/v2/reports.py::generate_flow_report_v2()` - Report generation (needs modification)
- `app/core/v2/pipeline.py` - Pipeline orchestration (line 1343 needs to load from JSON)

### Locations Report:
- `app/core/v2/reports.py::generate_locations_report_v2()` - Report generation (needs modification)
- `app/core/v2/pipeline.py` - Pipeline orchestration (line 1347 needs to prioritize JSON)

### Common:
- `app/core/v2/ui_artifacts.py` - UI artifacts generation (already generates segment_metrics.json)
- `app/core/v2/pipeline.py` - Pipeline orchestration (TODO at line 1337 needs to be implemented)

---

## Comparison Matrix

| Report Type | Current Data Source | Expected SSOT | Status |
|-------------|-------------------|---------------|--------|
| **Density** | Recalculates from bins.parquet | segment_metrics.json (ui/metrics/) | ❌ VIOLATES |
| **Flow** | In-memory flow_results dict | flow_results.json (computation/) | ⚠️ PARTIAL |
| **Locations** | In-memory DataFrame (JSON fallback) | locations_results.json (computation/) | ⚠️ PARTIAL |

---

## Notes

- This issue was discovered while investigating peak_rate discrepancy between UI and Density Report
- The peak_rate conversion bug fix (commit a862918) was a workaround; this issue addresses the root cause
- Issue #574 comment at line 1265 in pipeline.py promises "pure templating, no inline calculations" but this is not currently implemented
- Pipeline code (pipeline.py:1335-1337) has explicit TODO: "Full refactor to load from JSON only (remove in-memory fallback in future)"
- All three reports need refactoring to fully align with Issue #574's SSOT architecture