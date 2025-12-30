# Issue #574 Research: Pipeline Sequencing and Data Persistence (Comprehensive Proposal)

## Executive Summary

This research investigates the current pipeline sequencing and proposes a comprehensive separation of computation from report generation. The goal is to persist all computation results in JSON artifacts that serve as the source of truth, with reports being pure templating/formatting operations that consume these pre-calculated artifacts. This proposal extends beyond RES to all computed metrics, includes locations persistence, proposes UI artifact reorganization, and maintains the 3-minute performance target for sat+sun 5-event analysis.

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
     - `flags.json` (flagged segments)
     - `flow.json` (2.7MB - large file)
     - `health.json` (health status)
     - `schema_density.json` (schema definition)
     - `captions.json` (heatmap captions)
     - `heatmaps/` directory (PNG images)
   - **PERSISTED** to disk, but structure could be better organized

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
   - **Current Structure Issues**: 
     - 8 JSON files in flat structure
     - Large `flow.json` (2.7MB) mixed with small metadata files
     - No clear organization by purpose/type
     - Heatmaps in subdirectory but other visual assets not organized

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

3. **Locations Data**
   - Currently loaded as DataFrame
   - Only persisted as `Locations.csv` (formatted for reports)
   - No JSON artifact for computation results
   - Locations may have computed metrics (not just pass-through)

4. **Report Calculations**
   - Some calculations may be performed inline during report generation
   - Report templates may compute aggregations from `density_results`/`flow_results`

## Current UI Artifacts Structure Analysis

**Current Structure** (`runflow/{run_id}/{day}/ui/`):
```
ui/
├── meta.json (203B)
├── segment_metrics.json (5.3KB)
├── flags.json (4.5KB)
├── flow.json (2.7MB - large!)
├── segments.geojson (unknown size)
├── health.json (1.5KB)
├── schema_density.json (1.6KB)
├── captions.json (16KB)
└── heatmaps/
    └── *.png (multiple heatmap images)
```

**Issues:**
1. **Flat structure**: All JSON files at same level, no organization
2. **Large files mixed with small**: `flow.json` (2.7MB) alongside small metadata files
3. **No clear categorization**: Metrics, schemas, visual assets all mixed together
4. **No versioning**: Schema files not clearly versioned or organized

**Proposed Structure:**
```
ui/
├── metadata/
│   ├── meta.json
│   ├── health.json
│   └── schema_density.json
├── metrics/
│   ├── segment_metrics.json
│   └── flags.json
├── geospatial/
│   ├── segments.geojson
│   └── flow.json (large file - could be split or compressed)
└── visualizations/
    ├── heatmaps/
    │   └── *.png
    └── captions.json
```

**Benefits:**
- Clear organization by purpose
- Large files separated from small metadata
- Easier navigation and maintenance
- Better performance (can load only needed categories)

## Proposed Comprehensive Pipeline Architecture

### Design Principles

1. **Computation First, Presentation Second**: All computations persist results before any presentation layer (reports, UI artifacts)
2. **JSON as Source of Truth**: All computation results stored in JSON artifacts
3. **Pure Templating**: Reports consume JSON artifacts, perform no calculations
4. **Performance Target**: Maintain ~3 minutes for sat+sun 5-event analysis
5. **Incremental Generation**: Derived metrics can be added without regenerating base computations

### Proposed Pipeline Sequence

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Pre-Analysis & Validation                          │
│ - Validate API request                                       │
│ - Check all data files exist and are formatted correctly    │
│ - Load analysis.json (single source of truth)               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Data Loading                                        │
│ - Load segments.csv → segments_df                            │
│ - Load *_runners.csv files → all_runners_df                  │
│ - Load *.gpx files (for geospatial data)                     │
│ - Load flow.csv → flow_df                                    │
│ - Load locations.csv → locations_df                          │
│                                                               │
│ Output: All input DataFrames loaded and validated            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Core Computation Analysis                           │
│                                                               │
│ 3.1 Density Analysis                                         │
│   → analyze_density_segments_v2()                            │
│   → density_results (in-memory dict)                         │
│                                                               │
│ 3.2 Flow Analysis                                            │
│   → analyze_temporal_flow_segments_v2()                      │
│   → flow_results (in-memory dict)                            │
│                                                               │
│ 3.3 Locations Processing                                     │
│   → Process locations_df (if computation needed)             │
│   → locations_results (in-memory dict)                       │
│                                                               │
│ Note: Sequencing - Density → Flow (flow may depend on        │
│ density for segment filtering). Locations is independent.    │
│                                                               │
│ Output: All computation results in memory                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Persist Core Computation Results                    │
│                                                               │
│ 4.1 Persist Density Results                                  │
│   → Write density_results.json                               │
│   → Structure: {day: {segments: {...}, summary: {...}}}     │
│                                                               │
│ 4.2 Persist Flow Results                                     │
│   → Write flow_results.json                                  │
│   → Structure: {day: {segments: {...}, summary: {...}}}     │
│                                                               │
│ 4.3 Persist Locations Results                                │
│   → Write locations_results.json                             │
│   → Structure: {day: {locations: [...], summary: {...}}}    │
│   → Includes any computed metrics for locations              │
│                                                               │
│ 4.4 Generate Bins                                            │
│   → generate_bins_v2() (consumes density_results)            │
│   → Write bins.parquet, bins.json.gz, bins.json              │
│                                                               │
│ Output: All core computations persisted as JSON artifacts    │
│         (density_results.json, flow_results.json,            │
│          locations_results.json, bins.*)                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 5: Generate Aggregated Metrics & UI Artifacts          │
│                                                               │
│ 5.1 Generate UI Metrics (from persisted computation results) │
│   → Load density_results.json                                │
│   → Load flow_results.json                                   │
│   → Generate segment_metrics.json (aggregated metrics)       │
│   → Generate flags.json (flagged segments)                   │
│                                                               │
│ 5.2 Generate Geospatial Artifacts                            │
│   → Generate segments.geojson (from segments_df + density)   │
│   → Generate flow.json (from flow_results.json)              │
│                                                               │
│ 5.3 Generate Visualizations                                  │
│   → Generate heatmaps (PNG images)                           │
│   → Generate captions.json                                   │
│                                                               │
│ 5.4 Generate Metadata Artifacts                              │
│   → Generate meta.json                                       │
│   → Generate health.json                                     │
│   → Generate schema_density.json                             │
│                                                               │
│ Output: Organized UI artifacts in subdirectories             │
│         ui/metadata/, ui/metrics/, ui/geospatial/,           │
│         ui/visualizations/                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 6: Calculate Derived Metrics                           │
│                                                               │
│ 6.1 Load Required Data                                       │
│   → Load segment_metrics.json                                │
│   → Load segments.csv (for distance weighting)               │
│   → Load analysis.json (for event_group config)              │
│                                                               │
│ 6.2 Calculate RES Scores                                     │
│   → calculate_res_per_event_group()                          │
│   → Store in metadata.derived_metrics.res                    │
│                                                               │
│ 6.3 Calculate Other Derived Metrics                          │
│   → Operational status (from peak density + flow)            │
│   → Aggregate statistics                                     │
│   → Store in metadata.derived_metrics.*                      │
│                                                               │
│ 6.4 Create/Update Metadata                                   │
│   → Create metadata.json with:                               │
│     - Run/day information                                    │
│     - Event information                                      │
│     - Computation summaries                                  │
│     - Derived metrics (RES, operational status, etc.)        │
│                                                               │
│ Output: metadata.json with all derived metrics               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 7: Report Generation (Pure Templating)                 │
│                                                               │
│ 7.1 Load All Required Data                                   │
│   → Load density_results.json                                │
│   → Load flow_results.json                                   │
│   → Load locations_results.json                              │
│   → Load segment_metrics.json                                │
│   → Load metadata.json (for RES, operational status)         │
│   → Load bins.parquet (if needed for detailed bin data)      │
│                                                               │
│ 7.2 Generate Reports                                         │
│   → Density.md: Pure templating from density_results.json +  │
│                metadata.json (for RES, operational status)    │
│   → Flow.md: Pure templating from flow_results.json          │
│   → Flow.csv: Export flow_results.json to CSV format         │
│   → Locations.csv: Export locations_results.json to CSV      │
│                                                               │
│ Output: All reports generated once, no regeneration needed   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 8: Finalize & Cleanup                                  │
│                                                               │
│ 8.1 Create Run-Level Metadata                                │
│   → Aggregate day-level metadata.json                        │
│   → Create run-level metadata.json                           │
│                                                               │
│ 8.2 Update Pointer Files                                     │
│   → Update latest.json                                       │
│   → Update index.json                                        │
│                                                               │
│ 8.3 Performance Summary                                      │
│   → Log performance metrics                                  │
│   → Verify 3-minute target met                              │
│                                                               │
│ Output: Complete run with all artifacts persisted            │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Component Specifications

### 4.1 Density Results JSON Structure

**File**: `runflow/{run_id}/{day}/computation/density_results.json`

```json
{
  "schema_version": "1.0.0",
  "day": "sun",
  "events": ["full", "10k", "half"],
  "computed_at": "2025-12-30T00:56:29Z",
  "segments": {
    "A1": {
      "seg_id": "A1",
      "seg_label": "Bridge Approach",
      "length_m": 900.0,
      "width_m": 5.0,
      "peak_density": 0.7550,
      "peak_density_timestamp": "2025-01-01T07:15:00Z",
      "peak_density_km": 0.5,
      "los": "D",
      "density_windows": [
        {
          "window_start": "2025-01-01T07:00:00Z",
          "window_end": "2025-01-01T07:30:00Z",
          "peak_density": 0.7550,
          "avg_density": 0.6234
        }
      ],
      "events_included": ["full", "10k", "half"],
      "computed_metrics": {
        "total_windows": 180,
        "active_windows": 120,
        "peak_concurrency": 45
      }
    },
    ...
  },
  "summary": {
    "total_segments": 22,
    "processed_segments": 22,
    "skipped_segments": 0,
    "peak_density_overall": 0.7550,
    "peak_density_segment": "A1",
    "segments_by_los": {
      "A": 5,
      "B": 8,
      "C": 4,
      "D": 3,
      "E": 1,
      "F": 1
    }
  }
}
```

### 4.2 Flow Results JSON Structure

**File**: `runflow/{run_id}/{day}/computation/flow_results.json`

```json
{
  "schema_version": "1.0.0",
  "day": "sun",
  "events": ["full", "10k", "half"],
  "computed_at": "2025-12-30T00:56:29Z",
  "segments": {
    "A1": {
      "seg_id": "A1",
      "event_pairs": [
        {
          "event_a": "full",
          "event_b": "10k",
          "overtaking_a": 12,
          "overtaking_b": 8,
          "co_presence_a": 45,
          "co_presence_b": 32,
          "has_convergence": true,
          "convergence_km": 0.75,
          "convergence_timestamp": "2025-01-01T07:20:00Z"
        },
        ...
      ],
      "summary": {
        "total_overtakes": 20,
        "total_co_presence": 77,
        "has_convergence": true
      }
    },
    ...
  },
  "summary": {
    "total_segments": 22,
    "segments_with_convergence": 5,
    "total_event_pairs": 66,
    "total_overtakes": 234,
    "total_co_presence": 1234
  }
}
```

### 4.3 Locations Results JSON Structure

**File**: `runflow/{run_id}/{day}/computation/locations_results.json`

```json
{
  "schema_version": "1.0.0",
  "day": "sun",
  "events": ["full", "10k", "half"],
  "computed_at": "2025-12-30T00:56:29Z",
  "locations": [
    {
      "location_id": "AS1",
      "location_name": "Aid Station 1",
      "km": 5.0,
      "lat": 40.123456,
      "lon": -105.123456,
      "events": ["full", "10k", "half"],
      "computed_metrics": {
        "peak_density": 0.45,
        "peak_timestamp": "2025-01-01T07:30:00Z",
        "total_served": 1234,
        "avg_service_time": 15.5
      },
      "associated_segments": ["A1", "A2"]
    },
    ...
  ],
  "summary": {
    "total_locations": 12,
    "locations_by_event": {
      "full": 12,
      "10k": 8,
      "half": 10
    }
  }
}
```

### 5. UI Artifacts Reorganization

**Proposed Structure**: `runflow/{run_id}/{day}/ui/`

```
ui/
├── metadata/
│   ├── meta.json                    # Run metadata (run_id, timestamp, day, environment)
│   ├── health.json                  # Health status
│   └── schema_density.json          # Schema definitions
│
├── metrics/
│   ├── segment_metrics.json         # Aggregated segment-level metrics
│   └── flags.json                   # Flagged segments and bins
│
├── geospatial/
│   ├── segments.geojson             # Segment geometries
│   └── flow.json                    # Flow data (large file - 2.7MB)
│
└── visualizations/
    ├── heatmaps/
    │   ├── A1.png
    │   ├── A2.png
    │   └── ...
    └── captions.json                # Heatmap captions
```

**Benefits:**
1. **Clear organization**: Files grouped by purpose (metadata, metrics, geospatial, visualizations)
2. **Performance**: Can load only needed categories (e.g., UI loads metrics/ first, then geospatial/ on demand)
3. **Maintainability**: Easier to find and update related files
4. **Scalability**: New artifact types can be added to appropriate category

### 6. Derived Metrics Structure

**File**: `runflow/{run_id}/{day}/metadata.json`

```json
{
  "run_id": "YREtByZhLnG6GjCmUxMSkd",
  "day": "sun",
  "events": ["full", "10k", "half"],
  "computed_at": "2025-12-30T00:56:29Z",
  
  "computation": {
    "density": {
      "results_file": "computation/density_results.json",
      "summary": {
        "processed_segments": 22,
        "peak_density": 0.7550
      }
    },
    "flow": {
      "results_file": "computation/flow_results.json",
      "summary": {
        "segments_with_convergence": 5
      }
    },
    "locations": {
      "results_file": "computation/locations_results.json",
      "summary": {
        "total_locations": 12
      }
    }
  },
  
  "derived_metrics": {
    "res": {
      "event_groups": {
        "sun-all": {
          "events": ["full", "10k", "half"],
          "res": 5.0,
          "computed_at": "2025-12-30T00:56:35Z"
        }
      }
    },
    "operational_status": {
      "status": "Stable",
      "worst_los": "D",
      "peak_density": 0.7550,
      "computed_at": "2025-12-30T00:56:35Z"
    },
    "aggregates": {
      "total_participants": 1234,
      "total_segments": 22,
      "flagged_segments": 3
    }
  },
  
  "artifacts": {
    "ui": "ui/",
    "reports": "reports/",
    "bins": "bins/"
  }
}
```

## Performance Considerations

### Maintaining 3-Minute Target

**Current Performance**: ~3-4 minutes for sat+sun 5-event analysis

**Optimizations to Maintain Performance**:

1. **Parallel JSON Writing**: Write density_results.json, flow_results.json, locations_results.json in parallel (where possible)
2. **Streaming for Large Files**: Use streaming JSON writer for large flow_results.json (2.7MB+)
3. **Lazy Loading in Reports**: Reports load only needed data from JSON artifacts
4. **Cache Computation Results**: Keep density_results and flow_results in memory during pipeline (don't reload immediately after writing)
5. **Incremental UI Artifacts**: Generate UI artifacts incrementally, not all at once
6. **Optimize JSON Structure**: Use efficient JSON structure (arrays vs objects) based on access patterns

**Estimated Overhead**:
- Writing 3 JSON files (density, flow, locations): ~1-2 seconds
- Reading JSON in report generation: ~0.5-1 second (faster than recomputing)
- **Net Impact**: ~0.5-1 second overhead, well within 3-minute target

## Implementation Strategy

### Phase 1: Add JSON Persistence (Incremental)

1. **Add `locations_results.json` persistence**
   - After locations_df loaded, write to JSON
   - Structure similar to density/flow results

2. **Add `density_results.json` persistence**
   - After density analysis, write results to JSON
   - Maintain in-memory copy for current pipeline

3. **Add `flow_results.json` persistence**
   - After flow analysis, write results to JSON
   - Maintain in-memory copy for current pipeline

### Phase 2: Refactor Report Generation

1. **Update report generators to load from JSON**
   - Add fallback: try JSON first, fall back to in-memory if not available
   - Gradually migrate to JSON-only

2. **Remove inline calculations**
   - Identify calculations in report generation
   - Move to computation phases
   - Store results in JSON artifacts

### Phase 3: Reorganize UI Artifacts

1. **Create subdirectory structure**
   - Create metadata/, metrics/, geospatial/, visualizations/
   - Move existing files to appropriate subdirectories

2. **Update UI artifact generation**
   - Generate files in new structure
   - Update paths in metadata.json

3. **Update UI code**
   - Update frontend to load from new paths
   - Test all UI functionality

### Phase 4: Move Derived Metrics

1. **Calculate all derived metrics before reports**
   - Move RES calculation to Phase 6 (before reports)
   - Move operational status calculation to Phase 6
   - Store in metadata.json

2. **Remove report regeneration**
   - Reports generated once, after all metrics calculated
   - No regeneration needed

## Benefits of Comprehensive Architecture

1. **Separation of Concerns**
   - Computation separate from presentation
   - Reports are reproducible from persisted data
   - UI artifacts organized by purpose

2. **No Duplication**
   - Reports generated once, after all computations complete
   - No need to regenerate reports when new metrics added
   - Single source of truth for all computed data

3. **Scalability**
   - Adding new metrics (beyond RES) doesn't require report regeneration
   - Metrics calculated once, stored in JSON, consumed by reports/UI
   - UI artifacts organized for efficient loading

4. **Performance**
   - Maintains 3-minute target
   - JSON reading faster than recomputing
   - Lazy loading of UI artifacts by category

5. **Debuggability**
   - All computation results available as JSON artifacts
   - Can inspect intermediate results
   - Reports can be regenerated from artifacts without re-running computation
   - Clear artifact organization

6. **Flexibility**
   - Reports can be regenerated with different templates
   - New report formats (PDF) can consume same JSON artifacts
   - UI and reports consume same source of truth
   - Easy to add new artifact types

## Open Questions & Recommendations

### Questions

1. **Locations Computation**: What metrics need to be computed for locations? Or is it just pass-through data formatting?

2. **Flow.json Size**: 2.7MB is large. Should it be:
   - Compressed (flow.json.gz)?
   - Split into multiple files?
   - Optimized structure?

3. **Backward Compatibility**: How to handle existing runs that don't have JSON artifacts?
   - Fallback to in-memory computation
   - Migration script to generate JSON from existing data

4. **Schema Versioning**: Should we version the JSON schemas?
   - Include schema_version in each JSON file
   - Migration path for schema updates

### Recommendations

1. **Start with JSON Persistence**: Add density_results.json, flow_results.json, locations_results.json persistence first (maintains backward compatibility)

2. **Reorganize UI Artifacts**: Create subdirectory structure early to establish pattern

3. **Move Derived Metrics**: Calculate RES and other metrics before report generation

4. **Performance Testing**: Verify 3-minute target maintained after each phase

5. **Documentation**: Create clear documentation of:
   - JSON artifact structures
   - Pipeline sequence
   - UI artifact organization
   - How to add new metrics
