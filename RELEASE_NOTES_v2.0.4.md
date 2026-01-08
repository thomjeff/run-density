# Release Notes: v2.0.4

**Release Date:** January 8, 2026  
**Previous Version:** v2.0.2 (December 25, 2025)

## Overview

This release delivers major enhancements to the Flow UI with zone-level drilldown functionality, significant improvements to flow analysis with multi-convergence point support, and comprehensive UI improvements across Locations and Flow interfaces. The release also includes critical bug fixes for data integrity and performance optimizations.

## Major Features

### 🎯 Flow UI Zone-Level Enhancements (Issue #628)

The Flow UI now provides detailed zone-level analysis with an intuitive drilldown interface:

- **Zone Drilldown**: Click any segment row to expand and view all zones within that segment
- **Worst Zone Display**: Main table shows the worst zone index per segment (determined by overtaking + co-presence metrics)
- **Comprehensive Zone Table**: Sortable table displaying:
  - Zone index and distance (km)
  - Overtaking (A/B format)
  - Overtaken (A/B format)
  - Co-presence (A/B format)
  - Unique encounters, participants involved, multi-category runners
- **Narrative Captions**: Each zone includes a human-readable summary describing:
  - Co-presence percentages per event
  - Overtaking ratios (e.g., "2:1")
  - Total participants involved
  - Interaction characterization (limited/moderate/significant/peak congestion)

**Technical Implementation:**
- New UI artifacts: `metrics/flow_segments.json` and `visualizations/zone_captions.json`
- API endpoint `/api/flow/segments` now reads from JSON artifacts
- Captions generated dynamically based on zone metrics

### 🔄 Flow Analysis Restructuring (Issue #629)

Flow.csv has been restructured to zone-level format:
- **Before**: One row per segment+event-pair with aggregated metrics
- **After**: One row per zone within each segment+event-pair
- **Benefits**: Better granularity, zone-specific analysis, alignment with UI drilldown

### 🎯 Multi-Convergence Point Support (Issue #612)

Segments can now have multiple convergence points:
- Each convergence point generates separate zones
- Proper zone indexing (0-based)
- Zone-specific metrics and analysis
- Improved dataclass serialization for JSON export

### ⚡ Performance Optimization (Issue #613)

Flow zone metric calculations optimized using vectorized operations:
- **3-5x performance improvement** for zone metric calculations
- Implemented `SegmentFlowCache` for efficient data access
- Vectorized overlap calculations using numpy/pandas operations

## UI Improvements

### Locations UI Enhancements
- **Resource Filtering** (Issue #591): Dropdown filter to filter locations by resource type
- **Simplified Layout** (Issue #592): Combined columns, improved tooltips with resource counts
- **Enhanced Report** (Issue #589): New fields and resource calculations in locations.csv

### Flow UI Corrections
- Zero values now display as "0" instead of "--"
- Removed color styling from worst zone column
- Column heading changes: "CP (km)" → "Distance"
- Removed "Type" column from zone table
- Merged columns into A/B format for consistency

## Data Integrity & Bug Fixes

### Critical Fixes
- **Overtaking Count Logic** (Issue #552): Corrected calculation to match temporal flow analysis
- **Participants Involved** (Commit 4198c36): Fixed to include overtaken runners
- **Duplicate bins.parquet** (Issues #519, #542): Removed duplicate files from reports directory
- **Metadata Verification** (PR #601): Fixed discrepancies in metadata and density reports

### Data Exports
- **Overtaken Metrics** (Issue #620): Added `overtaken_a` and `overtaken_b` to `flow_zones.parquet`
- **Multi-category Runners** (Issue #622): Added field for participants_involved validation
- **fz_runners.parquet** (Issue #627): Fixed export to include all segments
- **Audit Refactoring** (Issue #607): Refactored to use Parquet format instead of CSV

## Infrastructure Improvements

### Pipeline Enhancements
- **Organized UI Artifacts** (Issues #574, #579, #580): Restructured into subdirectories:
  - `metadata/`: meta.json, schema_density.json, health.json
  - `metrics/`: segment_metrics.json, flags.json, flow_segments.json
  - `geospatial/`: segments.geojson, flow.json
  - `visualizations/`: heatmaps/*.png, captions.json, zone_captions.json
- **Enhanced Logging** (Issue #581): Improved pipeline phase logging for better visibility
- **Persisted JSON Artifacts** (Issue #600): Reports use persisted JSON as single source of truth

### API & Integration
- **Postman Collections** (Issue #576): Added `event_group` field
- **Field Deduplication** (Issue #549): Removed overlapping fields from flow.csv and segments.csv

## Breaking Changes

### Flow.csv Structure
- **Format Change**: Now zone-level (one row per zone) instead of segment-level
- **New Fields**: `zone_index`, `cp_km`, `cp_type`, `zone_source`, zone-specific metrics
- **Migration**: Existing scripts reading Flow.csv will need updates

### API Changes
- **Flow API**: `/api/flow/segments` now reads from JSON artifacts instead of CSV
- **Response Structure**: Includes nested zones array and captions per zone

## Migration Guide

### For Flow.csv Consumers
1. Update parsing logic to handle zone-level rows
2. Group by `(seg_id, event_a, event_b, zone_index)` for zone-specific analysis
3. Use `zone_index` to identify zones within segments

### For API Consumers
1. Flow API now returns nested zones structure
2. Access zone captions via `zone.caption.summary` field
3. Worst zone metrics available at segment level in `worst_zone` object

### For UI Developers
1. New UI artifacts in organized subdirectories
2. Flow UI uses accordion pattern for zone drilldown
3. Captions generated dynamically (Issue #632 proposes YAML rulebook)

## Known Issues

- **Issue #632**: Flow zone captions currently generated in code (enhancement created to move to YAML rulebook)
- **D1 (full/full) segment**: Debug logging added to investigate missing segment in flow_segments.json (may be timing/serialization issue)

## Contributors

This release includes contributions from multiple development sessions addressing Issues #612, #613, #620, #622, #627, #628, #629, and various UI improvements.

## Next Steps

- Issue #632: Move Flow captions to YAML rulebook (aligned with Density pattern)
- Continue investigation of D1 (full/full) segment discrepancy
- Consider unified UI rulebook for Density and Flow (research note in Issue #632)

---

**Full Changelog**: See [CHANGELOG.md](CHANGELOG.md) for complete details.
