# Issue #574: Pipeline Sequencing and Data Persistence Research Session

**Date**: December 30, 2025  
**Issue**: #574 - Investigate pipeline sequencing and data persistence patterns  
**Status**: Research Complete - Comprehensive proposal documented  
**Branch**: N/A (research only, no implementation)

## Session Objective

Conduct research-only investigation of the current pipeline sequencing to propose a comprehensive solution that splits computation from report generation. The goal is to persist all computation results in JSON artifacts that serve as the source of truth, with reports being pure templating/formatting operations.

## Background

Issue #573 (RES implementation) revealed a sequencing dependency problem:
- Reports are generated before RES calculation
- RES calculation requires `segment_metrics.json` from UI artifacts phase
- Reports must be regenerated to include RES data
- This creates duplication and scalability issues

The user requested investigation into:
1. Current pipeline sequencing of all calculation and report generation steps
2. Which calculations are performed during report generation vs. stored in JSON artifacts
3. Whether reports should be pure templating/formatting of pre-calculated JSON data
4. Opportunities to persist calculations in JSON files as source of truth
5. Whether reports (markdown/PDF) should be generated from these JSON artifacts in a future phase

## User Requirements

1. **Don't limit to RES**: Proposal should be comprehensive, covering all computation phases
2. **Locations JSON**: Locations should also have a `.json` file like density and flow
3. **UI Artifacts Organization**: Current UI artifacts structure needs better organization
4. **Performance Target**: Maintain 3-minute duration for sat+sun 5-event analysis
5. **Freedom to Propose**: Don't feel constrained by current constructs

## Research Process

### 1. Current Pipeline Analysis

Examined `app/core/v2/pipeline.py` to understand current sequencing:

**Current Flow**:
1. Pre-Analysis & Data Loading (lines 484-546)
2. Density Analysis → `density_results` (in-memory, lines 549-566)
3. Flow Analysis → `flow_results` (in-memory, lines 568-584)
4. Bin Generation → `bins.parquet`, `bins.json.gz`, `bins.json` (persisted, lines 586-663)
5. Report Generation → `Density.md`, `Flow.md`, `Flow.csv`, `Locations.csv` (lines 683-712)
6. Map Data Generation → `map_data.json` (persisted, lines 714-747)
7. UI Artifacts Generation → Multiple JSON files (persisted, lines 749-772)
8. Metadata Creation → `metadata.json` (persisted, lines 774-1023)
9. RES Calculation → Stores in `metadata.json`, requires report regeneration (lines 897-1018)

**Key Findings**:
- `density_results` and `flow_results` are NOT persisted (only in-memory dicts)
- `locations_df` is loaded but not persisted as JSON
- Only bins, UI artifacts, and metadata are persisted
- Reports must be regenerated after RES calculation (lines 977-1009)

### 2. UI Artifacts Structure Analysis

Examined actual UI artifacts from recent run:
- `/Users/jthompson/Documents/runflow/YREtByZhLnG6GjCmUxMSkd/sun/ui`

**Current Structure** (flat):
- `meta.json` (203B)
- `segment_metrics.json` (5.3KB)
- `flags.json` (4.5KB)
- `flow.json` (2.7MB - large!)
- `segments.geojson` (unknown size)
- `health.json` (1.5KB)
- `schema_density.json` (1.6KB)
- `captions.json` (16KB)
- `heatmaps/` directory (17 PNG files)

**Issues Identified**:
- Flat structure with no organization
- Large files (`flow.json` 2.7MB) mixed with small metadata
- No clear categorization by purpose
- Heatmaps in subdirectory but other visual assets not organized

### 3. Locations Processing Analysis

Examined how locations are currently handled:
- Loaded as DataFrame from `locations.csv`
- Filtered by day segments
- Used in `generate_locations_report_v2()` to create `Locations.csv`
- No JSON persistence, no computed metrics storage

## Proposed Solution

### Comprehensive 8-Phase Pipeline Architecture

**Design Principles**:
1. Computation First, Presentation Second
2. JSON as Source of Truth
3. Pure Templating for Reports
4. Maintain 3-Minute Performance Target
5. Incremental Generation (derived metrics don't require base computation regeneration)

**Proposed Sequence**:

```
Phase 1: Pre-Analysis & Validation
  → Validate request, check data files, load analysis.json

Phase 2: Data Loading
  → Load all CSV/GPX files into DataFrames

Phase 3: Core Computation Analysis
  → 3.1 Density Analysis → density_results (in-memory)
  → 3.2 Flow Analysis → flow_results (in-memory)
  → 3.3 Locations Processing → locations_results (in-memory)

Phase 4: Persist Core Computation Results
  → Write density_results.json
  → Write flow_results.json
  → Write locations_results.json
  → Generate bins (bins.parquet, bins.json.gz, bins.json)

Phase 5: Generate Aggregated Metrics & UI Artifacts
  → Generate segment_metrics.json, flags.json (from persisted results)
  → Generate segments.geojson, flow.json
  → Generate heatmaps, captions.json
  → Generate meta.json, health.json, schema_density.json
  → Organized in subdirectories: ui/metadata/, ui/metrics/, ui/geospatial/, ui/visualizations/

Phase 6: Calculate Derived Metrics
  → Calculate RES (from segment_metrics.json + segments.csv + analysis.json)
  → Calculate operational status
  → Store in metadata.json under derived_metrics section

Phase 7: Report Generation (Pure Templating)
  → Load all JSON artifacts (density, flow, locations, metrics, metadata)
  → Generate reports (Density.md, Flow.md, Flow.csv, Locations.csv)
  → No inline calculations, pure formatting/templating

Phase 8: Finalize & Cleanup
  → Create run-level metadata.json
  → Update pointer files
  → Performance summary
```

### New JSON Artifacts

1. **`computation/density_results.json`**
   - Location: `runflow/{run_id}/{day}/computation/density_results.json`
   - Structure: `{schema_version, day, events, computed_at, segments: {...}, summary: {...}}`
   - Contains: Peak density, LOS, density windows, computed metrics per segment

2. **`computation/flow_results.json`**
   - Location: `runflow/{run_id}/{day}/computation/flow_results.json`
   - Structure: `{schema_version, day, events, computed_at, segments: {...}, summary: {...}}`
   - Contains: Overtaking, co-presence, convergence points per segment

3. **`computation/locations_results.json`**
   - Location: `runflow/{run_id}/{day}/computation/locations_results.json`
   - Structure: `{schema_version, day, events, computed_at, locations: [...], summary: {...}}`
   - Contains: Location data with computed metrics (peak density, service times, etc.)

### UI Artifacts Reorganization

**Proposed Structure**:
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
│   └── flow.json (large file - 2.7MB)
└── visualizations/
    ├── heatmaps/*.png
    └── captions.json
```

**Benefits**:
- Clear organization by purpose
- Large files separated from small metadata
- Performance: can load only needed categories
- Easier maintenance and navigation

### Derived Metrics Structure

All derived metrics stored in `metadata.json`:
```json
{
  "derived_metrics": {
    "res": {
      "event_groups": {
        "sun-all": {
          "events": ["full", "10k", "half"],
          "res": 5.0
        }
      }
    },
    "operational_status": {
      "status": "Stable",
      "worst_los": "D",
      "peak_density": 0.7550
    },
    "aggregates": {
      "total_participants": 1234,
      "total_segments": 22,
      "flagged_segments": 3
    }
  }
}
```

## Performance Analysis

**Current Performance**: ~3-4 minutes for sat+sun 5-event analysis

**Estimated Overhead**:
- Writing 3 JSON files (density, flow, locations): ~1-2 seconds
- Reading JSON in report generation: ~0.5-1 second (faster than recomputing)
- **Net Impact**: ~0.5-1 second overhead, well within 3-minute target

**Optimizations**:
- Parallel JSON writing where possible
- Streaming JSON writer for large files
- Lazy loading in reports (load only needed data)
- Cache computation results during pipeline

## Implementation Strategy

### Phase 1: Add JSON Persistence (Incremental)
1. Add `locations_results.json` persistence
2. Add `density_results.json` persistence
3. Add `flow_results.json` persistence
4. Maintain in-memory copies for backward compatibility

### Phase 2: Refactor Report Generation
1. Update report generators to load from JSON
2. Add fallback: try JSON first, fall back to in-memory if not available
3. Remove inline calculations from report generation

### Phase 3: Reorganize UI Artifacts
1. Create subdirectory structure
2. Move existing files to appropriate subdirectories
3. Update UI artifact generation
4. Update frontend code to load from new paths

### Phase 4: Move Derived Metrics
1. Calculate all derived metrics before reports (Phase 6)
2. Move RES calculation to Phase 6
3. Move operational status calculation to Phase 6
4. Store in metadata.json
5. Remove report regeneration

## Deliverables

1. **Research Document**: `cursor/research_issue_574.md` (710 lines)
   - Comprehensive analysis of current pipeline
   - Detailed 8-phase proposed architecture
   - JSON structure specifications
   - Performance considerations
   - Implementation strategy
   - UI artifacts reorganization proposal

2. **Issue #574 Updated**: GitHub issue updated with research findings and proposal

3. **Session Document**: This document (for future Cursor sessions)

## Key Files Examined

- `app/core/v2/pipeline.py` - Current pipeline sequencing
- `app/core/v2/reports.py` - Report generation logic
- `app/core/v2/ui_artifacts.py` - UI artifact generation
- `app/core/v2/density.py` - Density analysis
- `app/core/v2/flow.py` - Flow analysis (referenced)
- `/Users/jthompson/Documents/runflow/YREtByZhLnG6GjCmUxMSkd/sun/ui/` - Actual UI artifacts structure

## Next Steps for Implementation

A future Cursor session should:

1. **Review Research Document**: Read `cursor/research_issue_574.md` for complete specifications
2. **Start with Phase 1**: Add JSON persistence for density, flow, and locations results
3. **Maintain Backward Compatibility**: Keep in-memory copies during transition
4. **Test Performance**: Verify 3-minute target maintained after each phase
5. **Incremental Implementation**: Follow the 4-phase implementation strategy
6. **Update UI Code**: Ensure frontend loads from new UI artifact structure

## Important Notes

- **No Implementation Done**: This was research-only, no code changes made
- **Performance Critical**: Must maintain ~3-minute target for sat+sun 5-event analysis
- **Backward Compatibility**: Initial implementation should support both JSON and in-memory data
- **Comprehensive Solution**: This proposal extends beyond RES to all computed metrics
- **UI Artifacts**: Reorganization is important for maintainability and performance

## Related Issues

- Issue #573: RES implementation (revealed the sequencing problem)
- Issue #574: This issue (pipeline sequencing investigation)

## Research Document Reference

Complete detailed specifications, JSON structures, and implementation details are in:
**`cursor/research_issue_574.md`**

This document should be the primary reference for implementation work.
