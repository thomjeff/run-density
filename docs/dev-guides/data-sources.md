# Canonical Data Sources

This document defines the canonical sources of truth for each type of data used in Runflow v2. This ensures consistency and prevents hardcoded assumptions.

**Version:** v2.0.6  
**Last Updated:** 2025-12-26

**Issue #512 + #553**: All data must come from these sources or fail with clear errors. No hardcoded defaults. All analysis inputs are configurable via API request.

---

## Table of Contents

1. [Data Flow Overview](#data-flow-overview)
   - [Test Coverage by Layer](#test-coverage-by-layer)
   - [Data Flow Examples](#data-flow-examples)
2. [Data Source Matrix](#data-source-matrix)
3. [Detailed Specifications](#detailed-specifications)
4. [UI → Data Lineage](#ui--data-lineage)
   - [Dashboard Page](#dashboard-page-dashboard)
   - [Segments Page](#segments-page-segments)
   - [Density Page](#density-page-density)
   - [Flow Page](#flow-page-flow)
   - [Locations Page](#locations-page-locations)
   - [Reports Page](#reports-page-reports)
   - [Health Page](#health-page-health)
   - [Analysis Page](#analysis-page-analysis)
   - [Create Files Page](#create-files-page-create_files)
5. [API Endpoints Reference](#api-endpoints-reference)
6. [Artifact Schemas](#artifact-schemas)
7. [Metric Dictionary](#metric-dictionary)
8. [Transform Rules](#transform-rules)
9. [Schema Tests](#schema-tests)
10. [Contract Tests](#contract-tests)
11. [E2E Tests](#e2e-tests)
12. [Quick Reference](#quick-reference)
13. [Related Issues](#related-issues)

---

## Data Flow Overview

The following diagram illustrates the data flow from artifacts through API endpoints to UI pages, and the test types that validate each layer:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Artifacts  │ ───→ │     API     │ ───→ │     UI      │
│  (JSON/     │      │  Endpoints  │      │   Pages     │
│  GeoJSON/   │      │             │      │             │
│  Parquet)   │      │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
      ↑                    ↑                    ↑
      │                    │                    │
      │                    │                    │
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Schema    │      │  Contract   │      │     E2E     │
│    Tests    │      │    Tests    │      │    Tests    │
│             │      │             │      │             │
│ (Validate   │      │ (Validate   │      │ (Validate   │
│  structure  │      │  parity:    │      │  rendering  │
│  & format)  │      │  artifacts  │      │  & user     │
│             │      │  = API      │      │  workflows) │
│             │      │  responses) │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
   ✅ Existing        ⏳ Issue #687        ✅ Existing
```

### Test Coverage by Layer

| Layer | Test Type | Status | Purpose | Examples |
|-------|-----------|--------|---------|----------|
| **Artifacts** | Schema Tests | ✅ Existing | Validate JSON/GeoJSON structure and required fields | `test_schema_resolver.py`, `test_ssot_failfast.py` |
| **Artifacts → API** | Contract Tests | ⏳ Issue #687 | Validate API responses match source artifacts | `test_contracts_dashboard.py`, `test_contracts_segments.py` |
| **API → UI** | E2E Tests | ✅ Existing | Validate UI rendering and user workflows | `tests/e2e.py` |

**Legend:**
- ✅ **Existing**: Tests currently implemented
- ⏳ **Planned**: Tests planned for Issue #687 (Contract Tests)

### Data Flow Examples

**Example 1: Dashboard Peak Density**
1. **Artifact:** `ui/metrics/segment_metrics.json` → Contains `peak_density` summary field and segment-level `peak_density` values
2. **API:** `GET /api/dashboard/summary` → Calculates peak from segment-level data, returns `peak_density` and `peak_density_los`
3. **UI:** Dashboard page → Displays peak density KPI tile with LOS badge
4. **Tests:**
   - Schema: Validate `segment_metrics.json` has required fields
   - Contract: Verify API `peak_density` matches calculated value from artifact
   - E2E: Verify UI displays correct value and LOS badge

**Example 2: Segments GeoJSON Enrichment**
1. **Artifacts:** 
   - `ui/geospatial/segments.geojson` → Segment geometries
   - `ui/metrics/segment_metrics.json` → Segment metrics
   - `ui/metrics/flags.json` → Flagged segments
2. **API:** `GET /api/segments/geojson` → Enriches GeoJSON features with metrics and flag status
3. **UI:** Segments page → Displays map with enriched segment features
4. **Tests:**
   - Schema: Validate GeoJSON structure, metrics JSON structure
   - Contract: Verify enriched properties match source artifacts
   - E2E: Verify map displays segments with correct colors/badges

**Example 3: Density Table**
1. **Artifacts:**
   - `ui/metrics/segment_metrics.json` → Segment-level density metrics
   - `ui/geospatial/segments.geojson` → Segment labels
   - `ui/metrics/flags.json` → Flagged segments
   - `ui/visualizations/captions.json` → Heatmap captions
2. **API:** `GET /api/density/segments` → Returns density table data for all segments
3. **UI:** Density page → Displays table with segment density metrics and heatmap links
4. **Tests:**
   - Schema: Validate segment_metrics.json structure
   - Contract: Verify table data matches segment_metrics.json values
   - E2E: Verify table displays correctly and heatmap links work

**Example 4: Flow Zones**
1. **Artifacts:**
   - `ui/metrics/flow_segments.json` → Flow metrics per segment-pair with zones
   - `ui/visualizations/zone_captions.json` → Zone visualization captions
2. **API:** `GET /api/flow/segments` → Returns flow data with worst zone and nested zones
3. **UI:** Flow page → Displays flow table with zone visualization
4. **Tests:**
   - Schema: Validate flow_segments.json structure (zones array)
   - Contract: Verify flow metrics match flow_segments.json
   - E2E: Verify zone visualization displays correctly

**Example 5: Locations Report**
1. **Artifacts:**
   - `reports/Locations.csv` → Location report data
   - `computation/locations_results.json` → Resources available
2. **API:** `GET /api/locations` → Returns locations report as JSON
3. **UI:** Locations page → Displays location table with resource counts
4. **Tests:**
   - Schema: Validate CSV structure and JSON resources
   - Contract: Verify API JSON matches CSV data
   - E2E: Verify locations table displays correctly

**Example 6: Reports Listing**
1. **Artifacts:**
   - `reports/` directory → Report files (Markdown, CSV, Parquet)
   - `analysis.json` → Data directory path
2. **API:** `GET /api/reports/list` → Returns list of report files with metadata
3. **UI:** Reports page → Displays report listing with download links
4. **Tests:**
   - Schema: Validate file metadata (mtime, size)
   - Contract: Verify file list matches directory contents
   - E2E: Verify download links work correctly

**Example 7: Health Status**
1. **Artifacts:**
   - `ui/metadata/health.json` → System health information
2. **API:** `GET /api/health/data` → Returns health data
3. **UI:** Health page → Displays system health status
4. **Tests:**
   - Schema: Validate health.json structure
   - Contract: Verify API response matches health.json
   - E2E: Verify health page displays correctly

**Example 8: Analysis Submission**
1. **Artifacts:**
   - Data directory → Input CSV/GPX files
   - `analysis.json` (generated) → Analysis configuration
2. **API:** `POST /runflow/v2/analyze` → Submits analysis request (background processing)
3. **UI:** Analysis page → Displays submission form and run_id
4. **Tests:**
   - Schema: Validate analysis.json structure after generation
   - Contract: Verify analysis.json matches request payload
   - E2E: Verify analysis submission workflow

**Example 9: Baseline File Generation**
1. **Artifacts:**
   - Data directory → Input runner CSV files
   - Generated files → Output runner CSV files with suffix
2. **API:** `POST /api/baseline/create-files` → Creates new runner files
3. **UI:** Create Files page → Displays baseline calculation and file generation
4. **Tests:**
   - Schema: Validate generated CSV structure
   - Contract: Verify generated files match control variables
   - E2E: Verify file generation workflow

**Note:** For detailed data flow examples for all UI pages, see [Data Flow Examples by Page](data-flow-examples-by-page.md) (separate document).

---

## Data Source Matrix

| Data Type | Canonical Source | Fallback | Validation | Notes |
|-----------|------------------|----------|------------|-------|
| **Start Time** | API request → `analysis.json` | **None** - fail if missing | Required in API request | Must be integer (300-1200 minutes after midnight) |
| **Event Duration** | API request → `analysis.json` | **None** - fail if missing | Required in API request | Must be integer (1-500 minutes) |
| **Event Names** | API request → `analysis.json` | **None** - fail if missing | Must match columns in `segments.csv` | All lowercase (e.g., `elite`, `open`) |
| **Event Ordering** | `flow.csv` (`event_a`, `event_b` columns) | Start time ordering (debugging only) | Log warning if fallback used | flow.csv defines intentional semantic ordering |
| **Segment Ranges** (Flow) | `flow.csv` (`from_km_a`, `to_km_a`, `from_km_b`, `to_km_b`) | **None** - fail if missing | Validate columns exist | flow.csv is authoritative for flow analysis |
| **Segment Ranges** (Density) | `segments.csv` (`{event}_from_km`, `{event}_to_km` columns) | **None** - fail if missing | Validate columns exist | segments.csv is authoritative for density analysis |
| **Flow Type** (parallel, counter) | `flow.csv` (`flow_type` column) | `segments.csv` (`flow_type` column) | Prefer flow.csv | flow.csv takes precedence |
| **Flow Metadata** | `flow.csv` (`notes`, `overtake_flag` columns) | **None** | Optional fields | Used for reporting context |
| **LOS Thresholds** | `density_rulebook.yml` | **None** - fail if missing | Validate file exists | Rulebook is single source of truth |
| **Runner Arrival Data** | `{event}_runners.csv` files | **None** - fail if missing | Validate file exists per event | Per-event runner files required |
| **Runner Counts** | Calculated from `{event}_runners.csv` | 0 (if calculation fails) | Never hardcoded | Must count actual runners |
| **Segment Metadata** | `segments.csv` (`seg_id`, `seg_label`, `width_m`, etc.) | **None** - fail if missing | Validate required columns | Base segment information |
| **Location Data** | `locations.csv` | **None** - fail if missing | Validate file exists | Location definitions |
| **GPX Course Data** | `{event}.gpx` files | **None** - fail if missing | Validate file exists and is parseable | Per-event GPX files required |

---

## Detailed Specifications

### Start Time

**Source**: API request → `analysis.json` (Issue #553)

**Request Format:**
```json
{
  "events": [
    {"name": "full", "day": "sun", "start_time": 420, "event_duration_minutes": 390},
    {"name": "10k", "day": "sun", "start_time": 440, "event_duration_minutes": 120}
  ]
}
```

**Access in Code:**
```python
from app.core.v2.analysis_config import get_start_time, load_analysis_json

analysis_config = load_analysis_json(run_path)
start_time = get_start_time('full', analysis_config)
```

**Validation**:
- Required field (no default)
- Must be integer between 300 and 1200 (5:00 AM - 8:00 PM)
- Validated in `app/core/v2/validation.py::validate_start_times()`

**Error Handling**: Returns 422 Unprocessable Entity if missing or invalid

**Related**: Issue #512 + #553 - No hardcoded start times allowed

---

### Event Ordering

**Source**: `flow.csv` columns `event_a` and `event_b`

**Format**:
```csv
seg_id,event_a,event_b,from_km_a,to_km_a,from_km_b,to_km_b,flow_type,notes
A1,full,10k,0.0,2.0,0.0,2.0,parallel,
```

**Ordering Semantics**:
- `event_a` and `event_b` in `flow.csv` reflect intentional semantic ordering
- Ordering may reflect:
  - Spatial position (who is ahead)
  - Direction of travel
  - Speed relationships
  - Race dynamics (who is being overtaken)

**Fallback**: Start time ordering (only when flow.csv doesn't contain the pair)
- Logs warning when fallback is used
- Should be rare - indicates missing flow.csv entry

**Validation**: 
- flow.csv must exist (404 if missing)
- Pairs in flow.csv are authoritative
- Fallback only for debugging/incomplete metadata

**Related**: Issue #512 - flow.csv is authoritative source

---

### Segment Ranges

**For Flow Analysis**: `flow.csv`
- Columns: `from_km_a`, `to_km_a`, `from_km_b`, `to_km_b`
- Defines event-specific distance ranges for each segment-pair combination
- Supports sub-segments (e.g., A1a, A1b, A1c) with different ranges

**For Density Analysis**: `segments.csv`
- Columns: `{event}_from_km`, `{event}_to_km` (e.g., `full_from_km`, `full_to_km`)
- Defines event-specific distance ranges for each segment
- One row per base segment (e.g., A1, not A1a)

**Validation**:
- Required columns must exist (422 if missing)
- Validated in `app/core/v2/validation.py::validate_segment_spans()`

**Error Handling**: Returns 422 Unprocessable Entity if columns missing

---

### Flow Type

**Source**: `flow.csv` column `flow_type` (preferred)
- Values: `parallel`, `counterflow`, `merge`, `none`, etc.

**Fallback**: `segments.csv` column `flow_type`
- Only used if flow.csv doesn't have the segment-pair

**Validation**: Optional field, no validation required

---

### LOS Thresholds

**Source**: `config/density_rulebook.yml` (or `data/density_rulebook.yml`)

**Structure**:
```yaml
globals:
  los_thresholds:
    density: [0.36, 0.54, 0.72, 1.08, 1.63]
schemas:
  on_course_narrow:
    los_thresholds:
      density: [0.36, 0.54, 0.72, 1.08, 1.63]
```

**Validation**:
- File must exist (fail if missing)
- Loaded in `app/rulebook.py::load_rulebook()`

**Error Handling**: Falls back to hardcoded defaults in `app/rulebook.py` (should be moved to constants)

**Related**: Issue #512 - Consolidate LOS threshold definitions

---

### Runner Arrival Data

**Source**: `{event}_runners.csv` files (e.g., `full_runners.csv`, `10k_runners.csv`)

**Format**:
```csv
runner_id,event,pace,distance,start_offset,day
12345,full,5.2,42.195,0,sun
```

**Required Columns**:
- `runner_id`: Unique identifier
- `event`: Event name (lowercase)
- `pace`: Minutes per km
- `distance`: Total distance in km
- `start_offset`: Seconds after event start_time
- `day`: Day identifier (fri, sat, sun, mon)

**Validation**:
- File must exist per event (404 if missing)
- Validated in `app/core/v2/validation.py::validate_file_existence()`
- No duplicate runner_ids across events
- Validated in `app/core/v2/validation.py::validate_runner_uniqueness()`

**Error Handling**: Returns 404 if file missing, 422 if invalid data

---

### Runner Counts

**Source**: Calculated from `{event}_runners.csv` files

**Calculation**:
1. Load `{event}_runners.csv` for each event
2. Filter by `day` column if present
3. Count unique `runner_id` values
4. Sum across all events for the day

**Fallback**: 0 (if calculation fails or file missing)

**Validation**: Never hardcoded - must be calculated

**Error Handling**: Use 0 if calculation fails, log warning

**Related**: Issue #512 - No hardcoded runner counts

---

### Segment Metadata

**Source**: `segments.csv`

**Required Columns**:
- `seg_id`: Segment identifier (e.g., "A1", "M1")
- `seg_label`: Human-readable label
- `width_m`: Segment width in meters
- `{event}_from_km`, `{event}_to_km`: Event-specific distance ranges

**Optional Columns**:
- `segment_type`: Schema type (start_corral, on_course_narrow, on_course_open)
- `flow_type`: Flow classification

**Validation**:
- Required columns must exist (422 if missing)
- Validated in `app/core/v2/validation.py::validate_segment_spans()`

---

### Location Data

**Source**: `locations.csv`

**Required Columns**:
- `loc_id`: Location identifier
- `loc_label`: Human-readable label
- `seg_id`: Associated segment ID
- `timing_source`: Source of timing data (e.g., "proxy:n")

**Validation**:
- File must exist (404 if missing)
- Validated in `app/core/v2/validation.py::validate_file_existence()`

---

### GPX Course Data

**Source**: `{event}.gpx` files (e.g., `full.gpx`, `10k.gpx`)

**Format**: Standard GPX XML format

**Validation**:
- File must exist per event (404 if missing)
- Must be valid XML/GPX format (422 if invalid)
- Validated in `app/core/v2/validation.py::validate_gpx_files()`

**Error Handling**: Returns 404 if file missing, 422 if invalid format

---

## Implementation Rules

1. **Always use canonical source** - Never hardcode values
2. **Fail early** - Return clear errors if source is missing
3. **Log warnings** - When fallback is used, log clearly
4. **Validate inputs** - Check all required fields exist
5. **No defaults** - If source is missing, fail (except documented fallbacks)

---

## Related Issues

- Issue #512: Audit: Hardcoded Values and Missing Constants
- Issue #494: Runflow v2 refactor
- Issue #515: Bug: Saturday Density.md Executive Summary shows incorrect bin and segment counts
- Issue #516: Review: Saturday Flow and Density computations for loop course

---

---

## UI → Data Lineage

This section maps each UI page to its API endpoints and underlying artifact sources. All paths are relative to `runflow/analysis/<run_id>/<day>/` unless otherwise noted.

### Dashboard Page (`/dashboard`)

**API Endpoints:**
- `GET /api/dashboard/summary` - Main dashboard data
- `GET /api/runs/list` - Run history table
- `GET /api/runs/{run_id}/summary` - Run detail view

**Artifact Sources:**
- `ui/metadata/meta.json` → `run_timestamp`, `environment`
- `ui/metrics/segment_metrics.json` → `segments_total`, `peak_density`, `peak_rate`, `segments_overtaking`, `segments_copresence`
- `ui/metrics/flags.json` → `bins_flagged`, `segments_flagged`
- `metadata.json` (day-level) → `events` (participants, start_time)

**UI Elements → Data Mapping:**
- **Total Runners** → Sum of `participants` from `metadata.json` events
- **Peak Density** → Calculated from `segment_metrics.json` segment-level data
- **Peak Density LOS** → `worst_los` from segment with peak density (SSOT)
- **Peak Rate** → Calculated from `segment_metrics.json` segment-level data
- **Segments Total** → Count of segment IDs in `segment_metrics.json`
- **Segments Flagged** → Count from `flags.json`
- **Bins Flagged** → Count from `flags.json`
- **Overtaking Segments** → `overtaking_segments` summary field in `segment_metrics.json`
- **Co-presence Segments** → `co_presence_segments` summary field in `segment_metrics.json`
- **Status** → Calculated: "action_required" if `peak_density_los` in ["E", "F"] OR `segments_flagged > 0`, else "normal"
- **Run History Table** → `index.json` (run-level) + `analysis.json` (description) + `metadata.json` (performance metrics)

### Segments Page (`/segments`)

**API Endpoints:**
- `GET /api/segments/geojson` - Enriched GeoJSON with metrics
- `GET /api/segments/summary` - Summary statistics
- `GET /api/dashboard/summary` - For day selector

**Artifact Sources:**
- `ui/geospatial/segments.geojson` → Segment geometries (converted from Web Mercator to WGS84)
- `ui/metrics/segment_metrics.json` → `worst_los`, `peak_density`, `peak_rate`, `active_window`
- `ui/metrics/flags.json` → Flagged segment IDs

**UI Elements → Data Mapping:**
- **Map Features** → `segments.geojson` features enriched with metrics
- **Segment Properties** → `seg_id`, `label`, `length_km`, `width_m`, `direction`, `events` from GeoJSON properties
- **Worst LOS** → `worst_los` from `segment_metrics.json[seg_id]`
- **Peak Density** → `peak_density` from `segment_metrics.json[seg_id]`
- **Peak Rate** → `peak_rate` from `segment_metrics.json[seg_id]`
- **Active Window** → `active_window` from `segment_metrics.json[seg_id]`
- **Is Flagged** → Boolean: `seg_id` in flagged segments from `flags.json`

### Density Page (`/density`)

**API Endpoints:**
- `GET /api/density/segments` - Density table data
- `GET /api/density/segment/{seg_id}` - Segment detail panel
- `GET /api/bins` - Bin-level data for detail view

**Artifact Sources:**
- `ui/metrics/segment_metrics.json` → Segment-level density metrics
- `ui/geospatial/segments.geojson` → Segment labels and metadata
- `ui/metrics/flags.json` → Flagged segments and bins
- `ui/visualizations/captions.json` → Heatmap captions
- `bins/bins.parquet` → Bin-level density data (for detail view)

**UI Elements → Data Mapping:**
- **Density Table** → Aggregated from `segment_metrics.json` + `segments.geojson` labels
- **Segment Detail Panel** → `segment_metrics.json[seg_id]` + `segments.geojson` feature
- **Heatmap URLs** → `/heatmaps/analysis/<run_id>/<day>/ui/visualizations/<seg_id>.png`
- **Heatmap Captions** → `captions.json[seg_id]`
- **Bin Detail Table** → `bins.parquet` filtered by `segment_id`
- **Flag Indicators** → `flags.json` filtered by `seg_id`

### Flow Page (`/flow`)

**API Endpoints:**
- `GET /api/flow/segments` - Flow table data with zones

**Artifact Sources:**
- `ui/metrics/flow_segments.json` → Flow metrics per segment-pair
- `ui/visualizations/zone_captions.json` → Zone visualization captions

**UI Elements → Data Mapping:**
- **Flow Table** → `flow_segments.json` (keyed by `seg_id_event_a_event_b`)
- **Worst Zone Metrics** → Top-level metrics in `flow_segments.json` entry
- **Nested Zones** → `zones` array in `flow_segments.json` entry
- **Zone Captions** → `zone_captions.json` (keyed by `seg_id_event_a_event_b_zone_index`)

### Locations Page (`/locations`)

**API Endpoints:**
- `GET /api/locations` - Locations report data

**Artifact Sources:**
- `reports/Locations.csv` → Location report data
- `computation/locations_results.json` → `resources_available` array

**UI Elements → Data Mapping:**
- **Locations Table** → `Locations.csv` converted to JSON
- **Resource Counts** → `resources_available` from `locations_results.json`
- **Flag Column** → Boolean from CSV (converted from string if needed)

### Reports Page (`/reports`)

**API Endpoints:**
- `GET /api/reports/list` - Report file listing
- `GET /api/reports/download` - File download

**Artifact Sources:**
- `reports/` directory → All report files (Markdown, CSV, Parquet)
- `analysis.json` → Data directory path for data files

**UI Elements → Data Mapping:**
- **Report List** → Files in `reports/` directory (filtered by day if specified)
- **Data Files** → CSV/GPX files from `data_dir` (from `analysis.json`)
- **File Metadata** → Filesystem `mtime` and `size`
- **Download Links** → `/api/reports/download?path=<relative_path>`

### Health Page (`/health`)

**API Endpoints:**
- `GET /api/health/data` - System health information
- `GET /api/health` - Simple health check

**Artifact Sources:**
- `ui/metadata/health.json` → System health data (environment, files, hashes, endpoints)

**UI Elements → Data Mapping:**
- **Health Status** → `health.json` content
- **Environment Info** → `environment` from `health.json`
- **File Checksums** → `files` array from `health.json`
- **Endpoint Status** → `endpoints` array from `health.json`

### Analysis Page (`/analysis`)

**API Endpoints:**
- `POST /runflow/v2/analyze` - Submit analysis request
- `GET /api/analysis/{run_id}/config` - Get analysis configuration
- `GET /api/data/files` - List available CSV/GPX files

**Artifact Sources:**
- `analysis.json` (run-level) → Analysis configuration
- Data directory (from request) → Input CSV/GPX files

**UI Elements → Data Mapping:**
- **File Dropdowns** → Files from `data_dir` (via `/api/data/files`)
- **Analysis Config** → `analysis.json` for existing runs
- **Run ID** → Returned from `/runflow/v2/analyze` POST

### Create Files Page (`/create_files`)

**API Endpoints:**
- `GET /api/data/files` - List available CSV files
- `POST /api/baseline/calculate` - Calculate baseline metrics
- `POST /api/baseline/generate` - Generate new baseline
- `POST /api/baseline/create-files` - Create new runner files
- `GET /api/baseline/download` - Download generated files

**Artifact Sources:**
- Data directory → Input runner CSV files
- Generated files → Output runner CSV files with suffix

**UI Elements → Data Mapping:**
- **File Selection** → CSV files from data directory
- **Baseline Metrics** → Calculated from selected files
- **Control Variables** → User input (participant counts, pace adjustments)
- **New Baseline Metrics** → Calculated from control variables
- **Generated Files** → New runner CSV files with suffix

---

## API Endpoints Reference

### v2 Analysis Endpoint

**`POST /runflow/v2/analyze`**
- **Purpose:** Submit analysis request (background processing)
- **Request Body:** V2AnalyzeRequest (events, files, data_dir, enableAudit)
- **Response:** V2AnalyzeResponse (run_id, status, days, output_paths)
- **Processing:** Asynchronous (Issue #554)
- **Artifacts Generated:** All day-scoped outputs in `runflow/analysis/<run_id>/<day>/`

### Dashboard Endpoints

**`GET /api/dashboard/summary`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** Dashboard KPIs (runners, segments, density, flags, flow metrics)
- **Artifacts Read:** `ui/metadata/meta.json`, `ui/metrics/segment_metrics.json`, `ui/metrics/flags.json`, `metadata.json`

**`GET /api/runs/list`**
- **Returns:** List of all runs with summary metrics
- **Artifacts Read:** `index.json`, `analysis.json`, `metadata.json` (run-level)

**`GET /api/runs/{run_id}/summary`**
- **Returns:** Detailed metrics per day for specific run
- **Artifacts Read:** `analysis.json`, `metadata.json` (run-level), day-level `ui/metrics/segment_metrics.json`, `ui/metrics/flags.json`

### Segments Endpoints

**`GET /api/segments/geojson`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** Enriched GeoJSON FeatureCollection
- **Artifacts Read:** `ui/geospatial/segments.geojson`, `ui/metrics/segment_metrics.json`, `ui/metrics/flags.json`
- **Transform:** Converts Web Mercator → WGS84 coordinates (Issue #477)

**`GET /api/segments/summary`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** Summary statistics (total segments, LOS counts, flagged count)
- **Artifacts Read:** `ui/geospatial/segments.geojson`, `ui/metrics/segment_metrics.json`, `ui/metrics/flags.json`

### Density Endpoints

**`GET /api/density/segments`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** Density table data for all segments
- **Artifacts Read:** `ui/metrics/segment_metrics.json`, `ui/geospatial/segments.geojson`, `ui/metrics/flags.json`, `ui/visualizations/captions.json`

**`GET /api/density/segment/{seg_id}`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** Detailed density data for single segment
- **Artifacts Read:** `ui/metrics/segment_metrics.json`, `ui/geospatial/segments.geojson`, `ui/metrics/flags.json`, `ui/visualizations/captions.json`

### Flow Endpoints

**`GET /api/flow/segments`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** Flow metrics per segment-pair with zones
- **Artifacts Read:** `ui/metrics/flow_segments.json`, `ui/visualizations/zone_captions.json`

### Bins Endpoints

**`GET /api/bins`**
- **Query Params:** `segment_id` (optional), `los_class` (optional), `limit` (default: 1000), `run_id` (optional), `day` (optional)
- **Returns:** Bin-level density and flow data
- **Artifacts Read:** `bins/bins.parquet`

### Reports Endpoints

**`GET /api/reports/list`**
- **Query Params:** `run_id` (optional), `day` (optional)
- **Returns:** List of report files with metadata
- **Artifacts Read:** `reports/` directory, `analysis.json` (for data files)

**`GET /api/reports/download`**
- **Query Params:** `path` (required)
- **Returns:** File download (Markdown, CSV, Parquet, GeoJSON)
- **Artifacts Read:** Files from `reports/` or data directory

### Locations Endpoints

**`GET /api/locations`**
- **Query Params:** `run_id` (optional), `day` (optional), `generate` (default: false)
- **Returns:** Locations report as JSON
- **Artifacts Read:** `reports/Locations.csv`, `computation/locations_results.json`

### Health Endpoints

**`GET /api/health/data`**
- **Returns:** System health information
- **Artifacts Read:** `ui/metadata/health.json`

**`GET /api/health`**
- **Returns:** Simple OK status (for load balancers)

### Baseline Endpoints

**`GET /api/data/files`**
- **Query Params:** `extension` (optional, e.g., "csv", "gpx")
- **Returns:** List of available data files

**`POST /api/baseline/calculate`**
- **Request Body:** Selected runner file names
- **Returns:** Baseline metrics for selected files

**`POST /api/baseline/generate`**
- **Request Body:** Control variables (participant counts, pace adjustments)
- **Returns:** New baseline metrics

**`POST /api/baseline/create-files`**
- **Request Body:** File suffix, new baseline metrics
- **Returns:** Created file information

**`GET /api/baseline/download`**
- **Query Params:** `run_id` (required)
- **Returns:** Download link for generated files

---

## Artifact Schemas

### Directory Structure

All artifacts are organized under `runflow/analysis/<run_id>/<day>/`:

```
<run_id>/
├── analysis.json (run-level config)
├── metadata.json (run-level metadata)
├── <day>/
│   ├── reports/ (Density.md, Flow.csv, Locations.csv, *.parquet)
│   ├── bins/ (bins.parquet)
│   ├── audit/ (audit_<day>.parquet) - if enabled
│   ├── computation/ (locations_results.json)
│   ├── metadata.json (day-level metadata)
│   └── ui/
│       ├── metadata/ (meta.json, schema_density.json, health.json)
│       ├── metrics/ (segment_metrics.json, flags.json, flow_segments.json)
│       ├── geospatial/ (segments.geojson, flow.json)
│       └── visualizations/ (captions.json, zone_captions.json, *.png)
```

### meta.json

**Path:** `ui/metadata/meta.json`

**Purpose:** Run metadata (timestamp, environment)

**Schema:**
```json
{
  "run_timestamp": "2025-01-15T10:30:00Z",
  "environment": "local"
}
```

### segment_metrics.json

**Path:** `ui/metrics/segment_metrics.json`

**Purpose:** Density and flow metrics per segment (SSOT for LOS)

**Schema:**
```json
{
  "peak_density": 1.23,
  "peak_rate": 45.6,
  "segments_with_flags": 3,
  "flagged_bins": 12,
  "overtaking_segments": 5,
  "co_presence_segments": 8,
  "<seg_id>": {
    "worst_los": "D",
    "peak_density": 1.23,
    "peak_rate": 45.6,
    "active_window": "08:00-09:30"
  }
}
```

**Notes:**
- Top-level keys are either summary fields or segment IDs
- `worst_los` is SSOT (Issue #640) - calculated from bins.parquet
- Summary fields: `peak_density`, `peak_rate`, `segments_with_flags`, `flagged_bins`, `overtaking_segments`, `co_presence_segments`

### flags.json

**Path:** `ui/metrics/flags.json`

**Purpose:** Operational flags (CRITICAL/CAUTION/WATCH/NONE)

**Schema (Array Format):**
```json
[
  {
    "seg_id": "A1",
    "bin_id": "A1_12345",
    "severity": "CRITICAL",
    "los_class": "E",
    "density": 1.5,
    "utilization_pctile": 98
  }
]
```

**Schema (Dict Format - Legacy):**
```json
{
  "flagged_segments": [
    {
      "seg_id": "A1",
      "bins": [...]
    }
  ]
}
```

**Notes:**
- Array format is preferred (current)
- Dict format supported for backward compatibility

### segments.geojson

**Path:** `ui/geospatial/segments.geojson`

**Purpose:** Segment geometries with metadata

**Schema:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[lon, lat], ...]  // WGS84 (EPSG:4326)
      },
      "properties": {
        "seg_id": "A1",
        "label": "Start Corral",
        "length_km": 0.5,
        "width_m": 3.0,
        "direction": "forward",
        "events": ["elite", "open"],
        "description": "Segment description"
      }
    }
  ]
}
```

**Notes:**
- Coordinates converted from Web Mercator (EPSG:3857) to WGS84 (EPSG:4326) before serving (Issue #477)
- GeoJSON standard requires WGS84

### flow_segments.json

**Path:** `ui/metrics/flow_segments.json`

**Purpose:** Flow metrics per segment-pair with zones (Issue #628)

**Schema:**
```json
{
  "<seg_id>_<event_a>_<event_b>": {
    "seg_id": "A1",
    "event_a": "elite",
    "event_b": "open",
    "worst_zone": {
      "zone_index": 0,
      "cp_km": 0.5,
      "overtaking_a": 10,
      "overtaking_b": 5,
      "copresence_a": 15,
      "copresence_b": 12
    },
    "zones": [
      {
        "zone_index": 0,
        "cp_km": 0.5,
        "overtaking_a": 10,
        "overtaking_b": 5,
        "copresence_a": 15,
        "copresence_b": 12
      }
    ]
  }
}
```

**Notes:**
- Key format: `{seg_id}_{event_a}_{event_b}`
- Multi-zone support (Issue #612, #629)
- `worst_zone` contains metrics from zone with highest overtaking/copresence

### zone_captions.json

**Path:** `ui/visualizations/zone_captions.json`

**Purpose:** Zone visualization captions

**Schema:**
```json
{
  "<seg_id>_<event_a>_<event_b>_<zone_index>": "Zone description"
}
```

### captions.json

**Path:** `ui/visualizations/captions.json`

**Purpose:** Heatmap captions per segment

**Schema:**
```json
{
  "<seg_id>": "Heatmap caption text"
}
```

### health.json

**Path:** `ui/metadata/health.json`

**Purpose:** System health information

**Schema:**
```json
{
  "environment": "local",
  "files": [
    {
      "path": "segments.csv",
      "hash": "abc123..."
    }
  ],
  "endpoints": [
    {
      "name": "/api/dashboard/summary",
      "status": "ok"
    }
  ]
}
```

### metadata.json (Day-Level)

**Path:** `<day>/metadata.json`

**Purpose:** Day-level metadata (events, participants)

**Schema:**
```json
{
  "events": {
    "<event_name>": {
      "participants": 1000,
      "start_time": 480
    }
  }
}
```

### metadata.json (Run-Level)

**Path:** `metadata.json` (run-level)

**Purpose:** Run-level metadata (performance, status)

**Schema:**
```json
{
  "performance": {
    "total_elapsed_seconds": 300,
    "total_elapsed_minutes": "05:00"
  },
  "status": "complete"
}
```

---

## Metric Dictionary

| Field | Meaning | Units | Source | Rules/Notes |
|-------|---------|-------|--------|-------------|
| `density` | Areal density | persons/m² | `bins.parquet` → `segment_metrics.json` | Peak density from bins |
| `rate` | Throughput | persons/second | `bins.parquet` → `segment_metrics.json` | Formula: `density × width × mean_speed` |
| `los_class` | Level of Service | A-F | `density_rulebook.yml` → `segment_metrics.json` | SSOT: `worst_los` from segment_metrics.json |
| `worst_los` | Worst LOS in segment | A-F | `segment_metrics.json[seg_id]` | SSOT (Issue #640) |
| `peak_density` | Maximum density | persons/m² | `segment_metrics.json` | Calculated from segment bins |
| `peak_rate` | Maximum throughput | persons/second | `segment_metrics.json` | Calculated from segment bins |
| `active_window` | Time window with activity | HH:MM-HH:MM | `segment_metrics.json` | Time range with non-zero density |
| `segments_total` | Total segments | count | `segment_metrics.json` | Count of segment IDs |
| `segments_flagged` | Segments with flags | count | `flags.json` | Count of unique `seg_id` |
| `bins_flagged` | Bins with flags | count | `flags.json` | Count of flag entries |
| `overtaking_a` | Runners from event_a overtaking | count | `flow_segments.json` | Real temporal overlaps only |
| `overtaking_b` | Runners from event_b overtaking | count | `flow_segments.json` | Real temporal overlaps only |
| `copresence_a` | Runners from event_a co-present | count | `flow_segments.json` | Co-presence in same segment |
| `copresence_b` | Runners from event_b co-present | count | `flow_segments.json` | Co-presence in same segment |
| `overtaking_segments` | Segments with overtaking | count | `segment_metrics.json` | Summary field |
| `co_presence_segments` | Segments with co-presence | count | `segment_metrics.json` | Summary field |
| `severity` | Flag severity | CRITICAL/CAUTION/WATCH/NONE | `flags.json` | From flagging logic |
| `zone_index` | Zone identifier | integer | `flow_segments.json` | Multi-zone support |
| `cp_km` | Convergence point | km | `flow_segments.json` | Distance where events converge |
| `participants` | Runner count per event | count | `metadata.json` | From `{event}_runners.csv` |
| `total_runners` | Total runners | count | `metadata.json` | Sum across events |
| `start_time` | Event start time | minutes from midnight | `analysis.json` | 300-1200 (5:00 AM - 8:00 PM) |
| `event_duration_minutes` | Event duration | minutes | `analysis.json` | 1-500 minutes |

---

## Transform Rules

### LOS Classification

**Source:** `density_rulebook.yml` (SSOT)

**Algorithm:**
1. Load thresholds from `density_rulebook.yml` (schema-specific if available)
2. Compare density value to thresholds
3. Assign LOS grade (A-F) based on threshold ranges
4. Store in `segment_metrics.json[seg_id].worst_los` (SSOT)

**Implementation:** `app/rulebook.py::load_rulebook()`

### Peak Metrics Calculation

**Source:** `segment_metrics.json` segment-level data

**Algorithm:**
1. Iterate through all segment IDs in `segment_metrics.json`
2. Find maximum `peak_density` across all segments
3. Find corresponding `peak_rate` for that segment
4. Return `(peak_density, peak_rate, peak_segment_id)`

**Implementation:** `app/routes/api_dashboard.py::_calculate_peak_metrics()`

### Flagging Logic

**Source:** `app/flagging.py` (SSOT)

**Algorithm:**
1. Load bins from `bins.parquet`
2. Apply flagging rules from `config/reporting.yml`:
   - `min_los_flag`: Flag bins with LOS >= threshold (default: "C")
   - `utilization_pctile`: Flag bins in top percentile (default: 95)
3. Assign severity:
   - **CRITICAL:** Both LOS >= C AND top 5% utilization
   - **CAUTION:** LOS >= C only
   - **WATCH:** Top 5% utilization only
   - **NONE:** Neither condition met
4. Store in `flags.json`

**Implementation:** `app/flagging.py`

### Zone Detection (Multi-Zone)

**Source:** Flow analysis with multi-zone support (Issue #612, #629)

**Algorithm:**
1. Analyze temporal flow for segment-pair
2. Detect convergence points (`cp_km`) where events interact
3. Create zones around each convergence point
4. Calculate metrics per zone (`overtaking_a`, `overtaking_b`, `copresence_a`, `copresence_b`)
5. Identify worst zone (highest overtaking/copresence)
6. Store in `flow_segments.json` with nested zones array

**Implementation:** Flow analysis pipeline

### Coordinate Conversion

**Source:** `segments.geojson` (Web Mercator) → API response (WGS84)

**Algorithm:**
1. Read `segments.geojson` (contains Web Mercator coordinates, EPSG:3857)
2. Transform each coordinate pair using `pyproj.Transformer`
3. Convert to WGS84 (EPSG:4326) for GeoJSON standard compliance
4. Return transformed GeoJSON

**Implementation:** `app/routes/api_segments.py::convert_geometry_to_wgs84()`

---

## Schema Tests

**Status:** ✅ Existing

**Purpose:** Validate artifact structure and format (JSON/GeoJSON schemas)

Schema tests validate that artifacts conform to expected structure and format. These tests validate the **Artifacts** layer in the data flow diagram above.

**Existing Tests:**
- `tests/unit/test_schema_resolver.py` - Schema resolution validation
- `tests/unit/test_ssot_failfast.py` - Rulebook schema validation
- `tests/unit/test_pipeline_integration.py` - Invalid schema fail-fast behavior

**Test Coverage:**
- JSON structure validation (required fields, types)
- GeoJSON format validation (FeatureCollection, coordinates)
- Schema-specific validation (rulebook schemas)
- Fail-fast behavior for invalid schemas

**Example:**
```python
def test_segment_metrics_schema():
    """Validate segment_metrics.json has required structure."""
    metrics = load_json("ui/metrics/segment_metrics.json")
    assert "peak_density" in metrics  # Summary field
    assert isinstance(metrics.get("A1"), dict)  # Segment-level data
    assert "worst_los" in metrics["A1"]  # Required field
```

---

## Contract Tests

**Status:** ⏳ Not Yet Implemented (Issue #687)

**Purpose:** Validate data parity from source artifacts → API responses

Contract tests ensure that API responses accurately reflect source artifacts. These tests validate the **Artifacts → API** layer in the data flow diagram above.

**Test Coverage:**

1. **Dashboard Parity:** All KPIs match source artifacts
2. **Segments GeoJSON Enrichment:** Metrics correctly joined to geometries
3. **Flow Table Parity:** Flow metrics match `flow_segments.json`
4. **Density Table Parity:** Density metrics match `segment_metrics.json`
5. **Health/Presence Tests:** Required artifacts exist and are readable

### Proposed Test Structure

**Directory:** `tests/contract/` (matches existing `tests/unit/` pattern)

**Test Files:**
- `tests/contract/test_dashboard.py` - Dashboard KPI parity
- `tests/contract/test_segments.py` - Segments GeoJSON enrichment
- `tests/contract/test_density.py` - Density table parity
- `tests/contract/test_flow.py` - Flow table parity
- `tests/contract/test_health.py` - Health/presence tests

**Directory Structure:**
```
tests/
├── conftest.py
├── e2e.py
├── unit/          # Unit tests (existing)
└── contract/      # Contract tests (new)
    ├── __init__.py
    ├── test_dashboard.py
    ├── test_segments.py
    ├── test_density.py
    ├── test_flow.py
    └── test_health.py
```

**Implementation Guidance:**
1. Load artifacts from test run
2. Call API endpoints
3. Compare API response values to artifact values
4. Assert exact matches (or acceptable tolerances for floating-point)
5. Test both latest run and specific run_id/day combinations

**Related Issues:**
- Issue #281 (this issue) - Documentation
- Issue #687 - Contract test implementation

**Note:** Contract tests focus on **Artifacts → API** parity. UI rendering validation is covered by E2E tests (`tests/e2e.py`).

---

## E2E Tests

**Status:** ✅ Existing

**Purpose:** Validate UI rendering and user workflows (API → UI layer)

E2E tests validate that UI pages correctly render data from API endpoints and that user workflows function correctly. These tests validate the **API → UI** layer in the data flow diagram above.

**Existing Tests:**
- `tests/e2e.py` - Comprehensive E2E test suite

**Test Coverage:**
- Analysis submission workflow
- Day selector functionality
- UI page rendering (Dashboard, Segments, Density, Flow, etc.)
- Report generation and download
- Golden file regression testing

**Note:** E2E tests focus on **API → UI** workflows. Artifact → API parity is validated by Contract Tests (Issue #687).

---

## Quick Reference

### Artifact Paths by Category

| Category | Path Pattern | Example Files |
|----------|--------------|---------------|
| **Metadata** | `<day>/ui/metadata/` | `meta.json`, `schema_density.json`, `health.json` |
| **Metrics** | `<day>/ui/metrics/` | `segment_metrics.json`, `flags.json`, `flow_segments.json` |
| **Geospatial** | `<day>/ui/geospatial/` | `segments.geojson`, `flow.json` |
| **Visualizations** | `<day>/ui/visualizations/` | `captions.json`, `zone_captions.json`, `*.png` |
| **Reports** | `<day>/reports/` | `Density.md`, `Flow.csv`, `Locations.csv`, `*.parquet` |
| **Bins** | `<day>/bins/` | `bins.parquet` |
| **Computation** | `<day>/computation/` | `locations_results.json` |

### API Endpoints by UI Page

| UI Page | Primary Endpoint | Additional Endpoints |
|---------|------------------|---------------------|
| **Dashboard** | `GET /api/dashboard/summary` | `GET /api/runs/list`, `GET /api/runs/{run_id}/summary` |
| **Segments** | `GET /api/segments/geojson` | `GET /api/segments/summary` |
| **Density** | `GET /api/density/segments` | `GET /api/density/segment/{seg_id}`, `GET /api/bins` |
| **Flow** | `GET /api/flow/segments` | - |
| **Locations** | `GET /api/locations` | - |
| **Reports** | `GET /api/reports/list` | `GET /api/reports/download` |
| **Health** | `GET /api/health/data` | `GET /api/health` |
| **Analysis** | `POST /runflow/v2/analyze` | `GET /api/analysis/{run_id}/config`, `GET /api/data/files` |
| **Create Files** | `POST /api/baseline/create-files` | `GET /api/data/files`, `POST /api/baseline/calculate`, `POST /api/baseline/generate` |

### Artifact → API → UI Mapping

| Artifact | API Endpoint | UI Element |
|----------|--------------|------------|
| `segment_metrics.json` | `GET /api/dashboard/summary` | Dashboard KPIs (peak density, segments total) |
| `segment_metrics.json` | `GET /api/segments/geojson` | Segments map (worst_los, peak_density) |
| `segment_metrics.json` | `GET /api/density/segments` | Density table |
| `flags.json` | `GET /api/dashboard/summary` | Dashboard (segments_flagged, bins_flagged) |
| `flags.json` | `GET /api/segments/geojson` | Segments map (is_flagged indicator) |
| `segments.geojson` | `GET /api/segments/geojson` | Segments map (geometries) |
| `flow_segments.json` | `GET /api/flow/segments` | Flow table (zones, metrics) |
| `bins.parquet` | `GET /api/bins` | Density detail view (bin-level data) |
| `Locations.csv` | `GET /api/locations` | Locations table |
| `health.json` | `GET /api/health/data` | Health status page |

### Common Query Parameters

All API endpoints support these optional query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `run_id` | string | latest | Run identifier (defaults to latest run) |
| `day` | string | first available | Day code: `fri`, `sat`, `sun`, `mon` |

**Example:**
```
GET /api/dashboard/summary?run_id=abc123&day=sat
```

### Metric Units Reference

| Metric | Unit | Source | Notes |
|--------|------|--------|-------|
| `density` | persons/m² | `segment_metrics.json` | Areal density |
| `rate` | persons/second | `segment_metrics.json` | Throughput (NOT "flow") |
| `los_class` | A-F | `segment_metrics.json` | Level of Service |
| `start_time` | minutes from midnight | `analysis.json` | Range: 300-1200 (5:00 AM - 8:00 PM) |
| `event_duration_minutes` | minutes | `analysis.json` | Range: 1-500 |
| `cp_km` | kilometers | `flow_segments.json` | Convergence point distance |
| `width_m` | meters | `segments.csv` | Segment width |
| `length_km` | kilometers | `segments.geojson` | Segment length |

### Test Type Quick Lookup

| What to Test | Test Type | Test File | Status |
|--------------|-----------|-----------|--------|
| Artifact JSON structure | Schema Tests | `test_schema_resolver.py` | ✅ Existing |
| Artifact GeoJSON format | Schema Tests | `test_ssot_failfast.py` | ✅ Existing |
| API response matches artifact | Contract Tests | `tests/contract/test_*.py` | ⏳ Issue #687 |
| UI renders correctly | E2E Tests | `tests/e2e.py` | ✅ Existing |

### Common Artifact Fields

| Field | Artifact | Type | Description |
|-------|----------|------|-------------|
| `worst_los` | `segment_metrics.json[seg_id]` | string (A-F) | SSOT for LOS (Issue #640) |
| `peak_density` | `segment_metrics.json` | float | Maximum density (persons/m²) |
| `peak_rate` | `segment_metrics.json` | float | Maximum throughput (persons/second) |
| `segments_total` | `segment_metrics.json` | integer | Count of segment IDs |
| `segments_flagged` | `flags.json` | integer | Count of unique `seg_id` |
| `bins_flagged` | `flags.json` | integer | Count of flag entries |
| `overtaking_segments` | `segment_metrics.json` | integer | Summary field |
| `co_presence_segments` | `segment_metrics.json` | integer | Summary field |
| `severity` | `flags.json` | string | CRITICAL/CAUTION/WATCH/NONE |
| `zone_index` | `flow_segments.json` | integer | Zone identifier (multi-zone) |

---

## Related Issues

- Issue #512: Audit: Hardcoded Values and Missing Constants
- Issue #494: Runflow v2 refactor
- Issue #553: API-driven configuration (no hardcoded values)
- Issue #554: Background analysis processing
- Issue #580: UI artifact organization (metadata/, metrics/, geospatial/, visualizations/)
- Issue #628: Flow segments JSON structure
- Issue #640: LOS SSOT from segment_metrics.json
- Issue #281: Data Source Map and Dictionary (this documentation)
- Issue #687: Contract Tests implementation

---

## Last Updated

2025-12-26 - Extended with UI data lineage, API endpoints reference, artifact schemas, metric dictionary, transform rules, contract tests section, data flow overview with visual diagram, expanded data flow examples for all 9 UI pages, schema tests section, E2E tests section, and quick reference tables (Issue #281)

