# Issue #574 Research: Pipeline Sequencing and Data Persistence

## Executive Summary

This research investigates the current pipeline sequencing and proposes a comprehensive separation of computation from report generation. The goal is to persist all computation results in JSON artifacts that serve as the source of truth, with reports being pure templating/formatting operations that consume these pre-calculated artifacts. This proposal extends beyond RES to all computed metrics and maintains the 3-minute performance target for sat+sun 5-event analysis.

## Current Pipeline Sequencing (from `app/core/v2/pipeline.py`)

### Current Flow:

1. **Pre-Analysis & Data Loading** (Lines 484-546)
   - Load `analysis.json` (if exists)
   - Generate day timelines
   - Load segments DataFrame
   - Load all runners for events

2. **Density Analysis** (Lines 549-566)
   - `analyze_density_segments_v2()` → Returns `density_results` (in-memory dict)
   - Results stored in memory, not persisted to JSON

3. **Flow Analysis** (Lines 568-584)
   - `analyze_temporal_flow_segments_v2()` → Returns `flow_results` (in-memory dict)
   - Results stored in memory, not persisted to JSON

4. **Bin Generation** (Lines 586-663)
   - `generate_bins_v2()` → Creates `bins.parquet`, `bins.json.gz`, `bins.json`
   - **PERSISTED** to disk as Parquet and JSON

5. **Report Generation** (Lines 683-712)
   - `generate_reports_per_day()` → Generates:
     - `Density.md` (markdown report)
     - `Flow.md` (markdown report)
     - `Flow.csv` (CSV export)
     - `Locations.csv` (CSV export)
   - **Problem**: Report generation may perform inline calculations rather than consuming pre-calculated data

6. **Map Data Generation** (Lines 714-747)
   - Generates `map_data.json` from density results
   - **PERSISTED** to disk

7. **UI Artifacts Generation** (Lines 749-772)
   - `generate_ui_artifacts_per_day()` → Generates:
     - `segment_metrics.json` (segment-level density and flow metrics)
     - `segments.geojson` (geospatial data)
     - `meta.json` (metadata)
     - Other UI-specific JSON files
   - **PERSISTED** to disk

8. **Metadata Creation** (Lines 774-1023)
   - Creates day-level `metadata.json` with density/flow summaries
   - **PERSISTED** to disk

9. **RES Calculation** (Lines 897-1018)
   - Calculates RES scores per event group
   - Requires `segment_metrics.json` (from UI artifacts phase)
   - Stores RES in `metadata.json`
   - **Problem**: Reports were already generated, so Density.md must be regenerated to include RES

## Key Findings

### What IS Persisted:

1. **Bins** (`bins.parquet`, `bins.json.gz`, `bins.json`)
   - Density and flow metrics per bin
   - Fully persisted and queryable

2. **UI Artifacts** (`segment_metrics.json`, `segments.geojson`, etc.)
   - Segment-level aggregated metrics
   - Peak density, peak rate, flagged segments
   - Used by dashboard UI

3. **Metadata** (`metadata.json`)
   - Run-level and day-level summaries
   - Event information, participant counts
   - Now includes RES scores

4. **Map Data** (`map_data.json`)
   - Geospatial visualization data

### What is NOT Persisted (Computed On-the-Fly):

1. **Density Results** (`density_results`)
   - Returned from `analyze_density_segments_v2()`
   - In-memory dictionary
   - Contains per-segment density calculations
   - Used by report generation

2. **Flow Results** (`flow_results`)
   - Returned from `analyze_temporal_flow_segments_v2()`
   - In-memory dictionary
   - Contains per-segment flow calculations
   - Used by report generation

3. **Report Calculations**
   - Some calculations may be performed inline during report generation
   - Report templates may compute aggregations from `density_results`/`flow_results`

## Current Problem (from Issue #573 Implementation)

The RES calculation revealed a sequencing dependency:

1. Reports are generated (lines 698-712) using `density_results` and `flow_results`
2. RES calculation happens later (lines 897-1018) and requires `segment_metrics.json` (from UI artifacts)
3. RES is stored in `metadata.json`
4. Reports must be **regenerated** (lines 977-1009) to include RES data in Density.md

This creates:
- **Duplication**: Reports generated twice
- **Dependency Issues**: Reports depend on computation that happens after they're generated
- **Scalability Problems**: Adding new calculated metrics (like RES) requires report regeneration

## Proposed Pipeline Architecture

### Phase 1: Pre-Analysis & Validation
- Validate API request
- Ensure all data files exist and are properly formatted
- Load configuration from `analysis.json`

### Phase 2: Data Loading
- Load all input data files:
  - `*_runners.csv` files per event
  - `*.gpx` files per event
  - `segments.csv`
  - `flow.csv`
  - `locations.csv`

### Phase 3: Computation Analysis
**Sequencing Question (per user): Is current order optimal?**
Current order:
1. Density analysis
2. Flow analysis
3. Locations (loaded but not computed - used in reports)

**Computations to Run:**
- Density analysis → `density_results` (in-memory)
- Flow analysis → `flow_results` (in-memory)
- Locations (currently just loaded, not computed)

### Phase 4: Persist Computation Results
**Current State:**
- Bins are persisted (`bins.parquet`, `bins.json.gz`, `bins.json`)
- UI artifacts are persisted (`segment_metrics.json`, etc.)
- Metadata is persisted (`metadata.json`)

**Missing:**
- `density_results` are NOT persisted as JSON
- `flow_results` are NOT persisted as JSON
- Only available as in-memory dictionaries

**Proposed Artifacts:**
- `density_results.json` - Full density computation results per segment
- `flow_results.json` - Full flow computation results per segment
- These would be the **source of truth** for all density/flow metrics

### Phase 5: Calculate Derived Metrics
**Current:**
- RES calculation happens here (requires segment_metrics.json)
- Operational status calculation
- Other derived metrics

**After Persistence:**
- All derived metrics calculated from persisted JSON artifacts
- Stored in `metadata.json` or separate `derived_metrics.json`

### Phase 6: Report Generation (Pure Templating)
**Current:**
- Report generation may perform calculations inline
- Consumes in-memory `density_results` and `flow_results`

**Proposed:**
- Reports consume pre-calculated JSON artifacts:
  - `density_results.json`
  - `flow_results.json`
  - `bins.parquet` / `bins.json`
  - `segment_metrics.json`
  - `metadata.json` (for RES, operational status, etc.)
- Reports become **pure templating/formatting** operations
- No inline calculations during report generation

## Detailed Analysis

### Current Report Generation Flow

From `app/core/v2/reports.py`:

1. `generate_reports_per_day()` calls:
   - `generate_density_report_v2()` → `Density.md`
   - `generate_flow_report_v2()` → `Flow.md`, `Flow.csv`
   - `generate_locations_report_v2()` → `Locations.csv`

2. These functions receive:
   - `density_results` (in-memory dict)
   - `flow_results` (in-memory dict)
   - DataFrames (segments_df, all_runners_df, locations_df)

3. Report generation likely:
   - Processes `density_results` and `flow_results` to extract metrics
   - Performs aggregations (peak density, peak rate, etc.)
   - Formats data for markdown/CSV output

### What Should Be Persisted

Based on the proposed architecture, we need:

1. **`density_results.json`**
   - Per-segment density calculations
   - Peak density values
   - Density timestamps
   - LOS classifications
   - All metrics currently in `density_results` dict

2. **`flow_results.json`**
   - Per-segment flow calculations
   - Overtaking counts
   - Co-presence counts
   - Convergence points
   - All metrics currently in `flow_results` dict

3. **`segment_metrics.json`** (already exists from UI artifacts)
   - Aggregated segment-level metrics
   - Peak density, peak rate
   - Flagged segments/bins
   - Used by both UI and reports

4. **`metadata.json`** (already exists)
   - Run-level summaries
   - Event information
   - RES scores (after Phase 5)
   - Operational status

### Proposed New Pipeline Sequence

```
1. Pre-Analysis & Validation
   └─> Validate request, check data files exist

2. Data Loading
   └─> Load all CSV/GPX files into DataFrames

3. Computation Analysis
   ├─> Density Analysis → density_results (in-memory)
   ├─> Flow Analysis → flow_results (in-memory)
   └─> Locations (loaded)

4. Persist Computation Results
   ├─> Write density_results.json
   ├─> Write flow_results.json
   ├─> Generate bins (bins.parquet, bins.json.gz, bins.json)
   ├─> Generate UI artifacts (segment_metrics.json, segments.geojson, etc.)
   └─> Create initial metadata.json (without RES/derived metrics)

5. Calculate Derived Metrics
   ├─> Calculate RES (from segment_metrics.json + segments.csv)
   ├─> Calculate operational status
   └─> Update metadata.json with derived metrics

6. Report Generation (Pure Templating)
   ├─> Load density_results.json
   ├─> Load flow_results.json
   ├─> Load segment_metrics.json
   ├─> Load metadata.json (for RES, operational status)
   └─> Generate reports (Density.md, Flow.md, Flow.csv, Locations.csv)
       - No inline calculations
       - Pure formatting/templating
       - All data from persisted JSON artifacts

7. Finalize Artifacts
   └─> Create run-level metadata.json
   └─> Update pointer files (latest.json, index.json)
```

## Benefits of Proposed Architecture

1. **Separation of Concerns**
   - Computation is separate from presentation
   - Reports are reproducible from persisted data

2. **No Duplication**
   - Reports generated once, after all computations complete
   - No need to regenerate reports when new metrics added

3. **Scalability**
   - Adding new metrics (like RES) doesn't require report regeneration
   - Metrics calculated once, stored in JSON, consumed by reports

4. **Debuggability**
   - All computation results available as JSON artifacts
   - Can inspect intermediate results
   - Reports can be regenerated from artifacts without re-running computation

5. **Flexibility**
   - Reports can be regenerated with different templates
   - New report formats (PDF) can consume same JSON artifacts
   - UI and reports consume same source of truth

## Implementation Considerations

### Data Structure Design

**`density_results.json`** should mirror current `density_results` structure:
```json
{
  "sat": {
    "segments": {
      "A1": {
        "peak_density": 0.75,
        "peak_density_timestamp": "2024-01-01T07:15:00",
        "los": "D",
        "density_windows": [...],
        ...
      },
      ...
    },
    "summary": {
      "processed_segments": 22,
      "skipped_segments": 0,
      "total_segments": 22
    }
  },
  ...
}
```

**`flow_results.json`** should mirror current `flow_results` structure:
```json
{
  "sat": {
    "segments": {
      "A1": {
        "overtaking": [...],
        "co_presence": [...],
        "convergence_points": [...],
        ...
      },
      ...
    },
    "summary": {
      "total_segments": 22,
      "segments_with_convergence": 5
    }
  },
  ...
}
```

### Backward Compatibility

- Current code expects `density_results` and `flow_results` as in-memory dicts
- Can load from JSON files if they exist, fall back to computation if not
- Gradual migration path

### Performance

- Persisting JSON files adds minimal overhead (already persisting bins, UI artifacts)
- Report generation becomes faster (reading JSON vs. re-computing)
- Can cache JSON artifacts if needed

## Open Questions

1. **Computation Sequencing**: User asked if current order (density → flow → locations) is optimal. Should investigate if there are dependencies or if order matters.

2. **Locations Computation**: Currently locations are just loaded, not computed. Is there computation needed for locations, or is it just pass-through data?

3. **Data Redundancy**: 
   - `segment_metrics.json` (from UI artifacts) contains aggregated metrics
   - `density_results.json` would contain detailed per-segment data
   - `bins.parquet` contains bin-level data
   - Need to ensure clear separation: what goes where?

4. **Report Dependencies**: 
   - Which reports need which data?
   - Density.md needs density_results.json + metadata.json (for RES)
   - Flow.md needs flow_results.json
   - Flow.csv needs flow_results.json
   - Locations.csv needs locations DataFrame (not computed, just formatted)

5. **Incremental Updates**:
   - If we add new metrics later (beyond RES), how do we handle updates?
   - Should derived metrics be in separate file or in metadata.json?

## Recommendations

1. **Immediate Action**: Create `density_results.json` and `flow_results.json` persistence after computation phases
2. **Refactor Report Generation**: Make reports consume JSON artifacts instead of in-memory dicts
3. **Move RES Calculation**: Calculate RES after all computation is persisted, before report generation
4. **Document Artifacts**: Create clear documentation on what each JSON artifact contains
5. **Test Regeneration**: Ensure reports can be regenerated from JSON artifacts without re-running computation
