# Quick Reference Guide

**Last Updated:** 2025-12-25  
**Version:** v2.0.2+  
**Purpose:** Fast lookups for variables, terminology, standards, and constants

This guide consolidates essential reference information for developers working with the run-density codebase.

**Note:** This guide reflects v2.0.2+ architecture (Issue #553 complete). All analysis inputs are configurable via API request.

---

## Table of Contents

1. [Variable Naming](#variable-naming)
2. [Terminology](#terminology)
3. [CSV Export Standards](#csv-export-standards)
4. [Constants Reference](#constants-reference)
5. [Schema Quick Reference](#schema-quick-reference)

---

## Variable Naming

### Critical Naming Rules

**Always use these exact field names to avoid bugs:**

| ✅ CORRECT | ❌ INCORRECT | Type | Source |
|-----------|-------------|------|--------|
| `seg_id` | `segment_id` | str | segments.csv |
| `seg_label` | `segment_label` | str | segments.csv |
| `from_km` | `start_km` | float | segments.csv |
| `to_km` | `end_km` | float | segments.csv |
| `width_m` | `width` | float | segments.csv |
| `flow_type` | `flowType` | str | flow analysis |

### Event Names (Lowercase Required)

**Issue #553:** All event names must be lowercase in API requests and data files.

| ✅ CORRECT | ❌ INCORRECT |
|-----------|-------------|
| `'full'` | `'Full'`, `'FULL'` |
| `'half'` | `'Half'`, `'HALF'` |
| `'10k'` | `'10K'`, `'tenk'` |
| `'elite'` | `'Elite'`, `'ELITE'` |
| `'open'` | `'Open'`, `'OPEN'` |

**File Naming:**
- Runners: `{event}_runners.csv` (e.g., `elite_runners.csv`)
- GPX: `{event}.gpx` (e.g., `elite.gpx`)

### Time Fields

**Issue #553:** Start times come from API request → `analysis.json`. Use helper functions from `app/core/v2/analysis_config.py`.

| Field | Units | Example | Source |
|-------|-------|---------|--------|
| `start_time` | minutes from midnight | `420` (7:00 AM), `480` (8:00 AM) | API request → `analysis.json` |
| `start_times` | dict | `{'elite': 480, 'open': 510}` | `analysis.json` → `get_all_start_times()` |
| `start_offset` | seconds | `30.0` | Runner data |
| `pace` | minutes per km | `5.5` | Runner data |
| `event_duration_minutes` | minutes | `45`, `120`, `390` | API request → `analysis.json` |

**Valid Range:** `start_time` must be 300-1200 (5:00 AM - 8:00 PM)

### Density/Flow Fields

| Field | Units | Description |
|-------|-------|-------------|
| `density` | persons/m² | Areal density |
| `rate` | persons/second | Bin throughput (NOT "flow") |
| `los_class` | A-F | Level of Service |
| `severity` | CRITICAL/CAUTION/WATCH/NONE | Flag severity |

---

## Terminology

### Flow vs Rate

**Critical Distinction:**

**"Flow"** (Capital F) = Event-level interaction analysis
- Co-presence between events
- Overtaking patterns
- Event convergence points
- Used in: `flow.csv`, Flow reports, temporal flow analysis

**"rate"** (lowercase) = Bin-level throughput
- Formula: `rate = density × width × mean_speed`
- Units: persons/second
- Physical meaning: throughput at a point
- Used in: `bins.csv`, density calculations

**Why This Matters:**
Using "flow" for bin throughput caused confusion. Always use "rate" for bin-level metrics.

### Overtake vs Overlap

**"Overtake"** = One runner passes another (temporal event)
- Requires actual time-based detection
- Must have real temporal overlap
- Used in flow analysis

**"Overlap"** = Two events share same segment (spatial)
- Co-presence on same path
- Can be simultaneous or sequential

### LOS (Level of Service)

Standard pedestrian density classification (A-F):
- **A**: 0.00-0.36 p/m² (Free Flow)
- **B**: 0.36-0.54 p/m² (Comfortable)
- **C**: 0.54-0.72 p/m² (Moderate)
- **D**: 0.72-1.08 p/m² (Dense)
- **E**: 1.08-1.63 p/m² (Very Dense)
- **F**: 1.63+ p/m² (Extremely Dense)

**Source of Truth:** `config/density_rulebook.yml` → `globals.los_thresholds`

---

## CSV Export Standards

### Decimal Precision

**All numeric CSV exports use 4 decimal places** for consistency and readability.

### Export Utility

**Module:** `app/csv_export_utils.py`

**Usage:**
```bash
# Export bins to CSV
python app/csv_export_utils.py reports/2025-10-15
```

**Programmatic:**
```python
from app.csv_export_utils import export_bins_to_csv, export_segment_windows_to_csv

csv_path = export_bins_to_csv("reports/2025-10-15/bins.parquet")
```

### Formatted Columns

**bins_readable.csv:**
- `start_km`: 4 decimals (e.g., 0.8000)
- `end_km`: 4 decimals (e.g., 1.0000)
- `density`: 4 decimals (e.g., 0.7490) - persons/m²
- `rate`: 4 decimals (e.g., 5.5284) - persons/second
- `bin_size_km`: 4 decimals (e.g., 0.2000)

**Why 4 decimals:**
- ✅ Sufficient precision for density/rate values
- ✅ Avoids misleading "0.00" for small values
- ✅ Consistent display in Excel/spreadsheets

---

## Constants Reference

### File Locations

**Configuration (YAML - Source of Truth):**
- `config/density_rulebook.yml` - LOS thresholds, operational rules
- `config/reporting.yml` - Colors, display settings
- `config/captioning.yml` - Caption thresholds

**Code Constants:**
- `app/utils/constants.py` - Application-level constants (NOT analysis parameters)

**Analysis Configuration (Issue #553):**
- `runflow/{run_id}/analysis.json` - Single source of truth for analysis parameters
- Generated from API request at start of analysis
- Use helper functions from `app/core/v2/analysis_config.py` to access

### Loading Configuration

```python
# YAML configuration
from app.common.config import load_rulebook, load_reporting, load_captioning

rulebook = load_rulebook()
los_thresholds = rulebook['globals']['los_thresholds']

# Analysis configuration (v2.0.2+)
from app.core.v2.analysis_config import (
    load_analysis_json,
    get_start_time,
    get_event_names,
    get_flow_file
)

analysis_config = load_analysis_json(run_path)
start_time = get_start_time('elite', analysis_config)
event_names = get_event_names(run_path)
```

### Removed Constants (Issue #553)

The following constants have been **removed** - values now come from API request:
- ❌ `EVENT_DAYS`
- ❌ `SATURDAY_EVENTS`
- ❌ `SUNDAY_EVENTS`
- ❌ `ALL_EVENTS`
- ❌ `EVENT_DURATION_MINUTES` (deprecated, kept for v1 API only)
- ❌ `DEFAULT_PACE_CSV`
- ❌ `DEFAULT_SEGMENTS_CSV`
- ❌ `DEFAULT_START_TIMES`

### Common Constants

**Time:**
- Default bin size: 60 seconds
- Coarsened bin size: 120 seconds
- Window format: ISO 8601
- Start time range: 300-1200 minutes (5:00 AM - 8:00 PM)
- Event duration range: 1-500 minutes

**Spatial:**
- Default segment width: varies by segment (see segments.csv)
- Minimum segment length: 50m

**Density:**
- LOS thresholds: See `config/density_rulebook.yml`
- Flag thresholds: See `config/density_rulebook.yml`

---

## Schema Quick Reference

### segments.csv

Core segment definition file.

**Key Fields:**
- `seg_id` - Unique ID (A1, B1, etc.)
- `seg_label` - Human name
- `width_m` - Segment width
- `direction` - uni/bi directional
- `full`, `half`, `10K` - Event participation (y/n)
- `*_from_km`, `*_to_km` - Event-specific ranges
- `flow_type` - overtake/merge/nan
- `description` - Segment description

### runners.csv

Runner data file.

**Key Fields:**
- `bib` - Runner number
- `event` - Full/Half/10K
- `pace` - Minutes per km
- `start_offset` - Seconds delay from event start

### flow_expected_results.csv

Flow analysis validation oracle.

**Key Fields:**
- `seg_id` - Segment ID
- `event_a`, `event_b` - Event pair
- `flow_type` - Expected flow type
- `overtaking_a`, `overtaking_b` - Expected overtake counts
- `copresence_a`, `copresence_b` - Expected co-presence counts

---

## API Quick Reference

### Core Endpoints

**Density:**
- `POST /api/density-report` - Generate density analysis
- `GET /api/density/segments` - Get segment density data

**Flow:**
- `POST /api/temporal-flow-report` - Generate flow analysis
- `GET /api/flow/segments` - Get flow interaction data

**Reports:**
- `GET /api/reports/list` - List available reports
- `GET /api/reports/download?path=...` - Download report

**Map:**
- `GET /api/map/manifest` - Map configuration
- `GET /api/map/bins?window_idx=N&bbox=...` - Bin-level map data

**Dashboard:**
- `GET /api/dashboard/summary` - Dashboard metrics

**Health:**
- `GET /health` - Basic health check
- `GET /ready` - Readiness check

---

## File Paths Reference

### Source Data
- `data/segments.csv` - Segment definitions
- `data/runners.csv` - Runner data
- `data/flow_expected_results.csv` - Flow validation oracle
- `data/*.gpx` - GPX course files

### Configuration
- `config/density_rulebook.yml` - LOS thresholds, rules
- `config/reporting.yml` - Display configuration
- `config/captioning.yml` - Caption thresholds

### Generated Outputs
- `reports/YYYY-MM-DD/*.md` - Markdown reports
- `reports/YYYY-MM-DD/*.csv` - CSV exports
- `reports/YYYY-MM-DD/*.parquet` - Binary data
- `artifacts/YYYY-MM-DD/*.json` - UI artifacts
- `artifacts/YYYY-MM-DD/heatmaps/*.png` - Heatmap images

---

## Common Gotchas

### 1. Variable Name Mismatches
❌ **Wrong:** `segment_id`  
✅ **Right:** `seg_id`

### 2. Event Name Casing
❌ **Wrong:** `'full'`, `'FULL'`  
✅ **Right:** `'Full'`

### 3. Flow vs Rate Confusion
❌ **Wrong:** "flow rate" for bin throughput  
✅ **Right:** "rate" (persons/second)

### 4. LOS Hardcoding
❌ **Wrong:** Hardcode thresholds in code  
✅ **Right:** Load from `config/density_rulebook.yml`

### 5. Path Assumptions
❌ **Wrong:** Assume `tests/` exists  
✅ **Right:** Use E2E testing via `make e2e` or `pytest tests/v2/e2e.py`

---

## Related Documentation

- **Architecture:** `docs/architecture/README.md`
- **Module Development:** `docs/architecture/adding-modules.md`
- **Testing:** `docs/ui-testing-checklist.md`
- **Operations:** `docs/dev-guides/OPERATIONS.md`
- **Docker Workflow:** `docs/dev-guides/docker-dev.md`
- **AI Developer Guide:** `docs/dev-guides/ai-developer-guide.md`

---

**For detailed technical architecture, see:**
- `docs/dev-guides/developer-guide-v2.md` - Complete v2 developer guide (includes Global Time Grid Architecture section)

