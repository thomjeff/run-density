# Canonical Data Sources

This document defines the canonical sources of truth for each type of data used in Runflow v2. This ensures consistency and prevents hardcoded assumptions.

**Version:** v2.0.2+ (Issue #553 complete)  
**Last Updated:** 2025-12-25

**Issue #512 + #553**: All data must come from these sources or fail with clear errors. No hardcoded defaults. All analysis inputs are configurable via API request.

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

## Last Updated

2025-12-12 - Created as part of Issue #512 implementation

