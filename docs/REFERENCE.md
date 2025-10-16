# Quick Reference Guide

Fast lookups for variable names, schemas, terminology, and standards.

## Table of Contents
1. [Variable Naming](#variable-naming)
2. [Terminology](#terminology)
3. [CSV Export Standards](#csv-export-standards)
4. [Schema Definitions](#schema-definitions)
5. [Constants Reference](#constants-reference)

---

## Variable Naming

### Segment Fields

| ✅ CORRECT | ❌ INCORRECT | Type | Notes |
|-----------|-------------|------|-------|
| `seg_id` | `segment_id` | str | Unique segment identifier (A1, F1, etc.) |
| `seg_label` | `segment_label` | str | Human-readable segment name |
| `from_km` | `10K_from_km` | float | Event-specific start position |
| `to_km` | `10K_to_km` | float | Event-specific end position |
| `full_from_km` | `Full_from_km` | float | Full marathon start position |
| `half_from_km` | `Half_from_km` | float | Half marathon start position |
| `10K_from_km` | `tenk_from_km` | float | 10K start position |
| `width_m` | `width` | float | Segment width in meters |
| `flow_type` | `flowType` | str | overtake, merge, or nan |

### Event Names

| ✅ CORRECT | ❌ INCORRECT | Notes |
|-----------|-------------|-------|
| `'Full'` | `'full'`, `'FULL'` | Capital F |
| `'Half'` | `'half'`, `'HALF'` | Capital H |
| `'10K'` | `'tenk'`, `'10k'` | Uppercase K |

### Time Fields

| Field | Units | Format | Example |
|-------|-------|--------|---------|
| `start_times` | minutes from midnight | dict | `{'Full': 420, '10K': 440, 'Half': 460}` |
| `start_offset` | seconds | float | `30.0` |
| `pace` | minutes per km | float | `5.5` |
| `t_start` | ISO datetime | str | `2025-10-15T07:20:00Z` |

### Density/Flow Fields

| Field | Units | Notes |
|-------|-------|-------|
| `density` | persons/m² | Areal density |
| `rate` | persons/second | Bin throughput (renamed from 'flow') |
| `los_class` | A-F | Level of Service |
| `severity` | CRITICAL/CAUTION/WATCH/NONE | Operational intelligence flag |

---

## Terminology

### Flow vs rate

**CRITICAL**: These are different metrics - don't confuse them!

| Term | Scope | Units | Purpose | Files |
|------|-------|-------|---------|-------|
| **Flow** (capital F) | Event-level | Various | Event convergence, overtaking, co-presence | flow.csv, flow_report.py, flow.py |
| **rate** (lowercase) | Bin-level | persons/second | Spatial throughput intensity | bins.parquet, density_report.py |

**Flow Metrics:**
- Co-presence count
- Overtaking count  
- Convergence point (km)
- Overlap duration (seconds)

**rate Formula:**
```python
rate = density × width_m × mean_speed_mps
# density = persons/m²
# width_m = segment width in meters
# mean_speed_mps = average speed in m/s
# rate = persons/second (actual throughput)
```

**Example:**
- Density: 0.353 p/m²
- Width: 5.0 m
- Speed: 3.13 m/s
- **rate**: 5.528 p/s ✅

See `docs/FLOW_VS_RATE_TERMINOLOGY.md` for complete guide.

### Density Metrics

| Metric | Symbol | Units | Definition |
|--------|--------|-------|------------|
| Areal Density | ρ | persons/m² | Crowd density in 2D space |
| Linear Density | λ | persons/m | Runners per meter of width |
| Mean Density | ρ̄ | persons/m² | Average across bins in window |
| Peak Density | ρ_max | persons/m² | Maximum density in window |

### LOS (Level of Service)

| LOS | Density (p/m²) | Description | Color |
|-----|---------------|-------------|-------|
| A | 0.00 - 0.50 | Free flow | #4CAF50 (Green) |
| B | 0.50 - 1.00 | Comfortable | #8BC34A (Light Green) |
| C | 1.00 - 1.50 | Moderate | #FFC107 (Amber) |
| D | 1.50 - 2.00 | Dense | #FF9800 (Orange) |
| E | 2.00 - 3.00 | Very dense | #FF5722 (Red-Orange) |
| F | 3.00+ | Extremely dense | #F44336 (Red) |

**Note**: Thresholds configurable per segment schema in `config/density_rulebook.yml`

### Severity Levels (Operational Intelligence)

| Severity | Criteria | Badge | Action |
|----------|----------|-------|--------|
| **CRITICAL** | LOS ≥ C AND top 5% utilization | 🚨 | Immediate attention |
| **CAUTION** | LOS ≥ C only | ⚡ | Monitor closely |
| **WATCH** | Top 5% utilization only | 👁️ | Review if needed |
| **NONE** | Normal operations | - | No action |

---

## CSV Export Standards

All CSV exports use **4 decimal places** for consistency.

### bins_readable.csv Columns

| Column | Decimals | Units | Example |
|--------|----------|-------|---------|
| `bin_id` | - | - | A1:0.000-0.200 |
| `segment_id` | - | - | A1 |
| `start_km` | 4 | km | 0.8000 |
| `end_km` | 4 | km | 1.0000 |
| `t_start` | - | ISO datetime | 2025-10-15T07:20:00Z |
| `t_end` | - | ISO datetime | 2025-10-15T07:22:00Z |
| `density` | 4 | persons/m² | 0.7490 |
| `rate` | 4 | persons/second | 5.5284 |
| `los_class` | - | A-F | B |
| `bin_size_km` | 4 | km | 0.2000 |

### Export Utility

```bash
# Export parquet to CSV with formatting
python app/csv_export_utils.py reports/2025-10-16

# Programmatic usage
from app.csv_export_utils import export_bins_to_csv
csv_path = export_bins_to_csv("reports/2025-10-16/bins.parquet")
```

See `docs/CSV_EXPORT_STANDARDS.md` for details.

---

## Schema Definitions

### bins.parquet Schema

```
bin_id: string                  # A1:0.000-0.200
segment_id: string              # A1
start_km: double                # 0.0
end_km: double                  # 0.2
t_start: string                 # 2025-10-15T07:20:00Z
t_end: string                   # 2025-10-15T07:22:00Z  
density: double                 # 0.7490 (persons/m²)
rate: double                    # 5.5284 (persons/second)
los_class: string               # A-F
bin_size_km: double             # 0.2
schema_version: string          # 1.0.0
analysis_hash: string           # (optional)
geometry: binary                # WKB linestring
```

### segment_windows_from_bins.parquet Schema

```
segment_id: string              # A1
t_start: timestamp              # 2025-10-15 07:20:00+00:00
t_end: timestamp                # 2025-10-15 07:22:00+00:00
density_mean: double            # 0.1900
density_peak: double            # 0.7490
n_bins: int64                   # 5
```

### tooltips.json Schema

```json
{
  "tooltips": [
    {
      "segment_id": "A1",
      "start_km": 0.0,
      "end_km": 0.2,
      "t_start": "07:20:00",
      "t_end": "07:22:00",
      "density_peak": 0.749,
      "los": "B",
      "los_description": "Comfortable",
      "los_color": "#8BC34A",
      "severity": "WATCH",
      "flag_reason": "UTILIZATION_HIGH"
    }
  ],
  "metadata": {
    "generated": "2025-10-15T18:05:00Z",
    "schema_version": "1.0",
    "total_bins": 441
  }
}
```

---

## Constants Reference

### From `app/constants.py`

```python
# Event start times (NEVER hardcode these!)
DEFAULT_START_TIMES = {'Full': 420, '10K': 440, 'Half': 460}

# Analysis parameters
DEFAULT_BIN_SIZE_KM = 0.1
DEFAULT_BIN_TIME_WINDOW_SECONDS = 60
DISTANCE_BIN_SIZE_KM = 0.03

# Performance limits
MAX_BIN_GENERATION_TIME_SECONDS = 90
BIN_MAX_FEATURES = 12000

# Hotspot segments (preserved during coarsening)
HOTSPOT_SEGMENTS = ['A1', 'F1']

# Operational intelligence
LOS_HIGH_THRESHOLD = 'C'
UTILIZATION_PERCENTILE = 95

# URLs (for e2e.py)
CLOUD_RUN_URL = "https://run-density-ln4r3sfkha-uc.a.run.app"
LOCAL_RUN_URL = "http://localhost:8080"
```

### Analysis Tolerances

```python
DEFAULT_MIN_OVERLAP_DURATION = 5.0        # seconds
DEFAULT_CONFLICT_LENGTH_METERS = 100.0    # meters
DEFAULT_STEP_KM = 0.03                    # km
DEFAULT_TIME_WINDOW_SECONDS = 300         # seconds
```

### Dynamic Conflict Lengths

| Segment Length | Conflict Zone |
|----------------|---------------|
| ≤ 1.0 km | 100 m |
| 1.0 - 2.0 km | 150 m |
| > 2.0 km | 200 m |

---

## Common Lookups

### Convert Minutes to Time

```python
minutes = 440  # 10K start
hours = minutes // 60        # 7
mins = minutes % 60          # 20
time_str = f"{hours:02d}:{mins:02d}"  # "07:20"
```

### Convert Pace to Speed

```python
pace_min_per_km = 5.5  # min/km
pace_sec_per_km = pace_min_per_km * 60.0
speed_mps = 1000.0 / pace_sec_per_km  # m/s
speed_kmh = speed_mps * 3.6  # km/h
```

### Check if Runner in Segment

```python
# Runner position at time t
runner_km = (t - runner_start_time) / pace_sec_per_km

# Check bounds
if from_km <= runner_km <= to_km:
    # Runner is in segment
    relative_pos_m = (runner_km - from_km) * 1000.0
```

---

**This reference should be your first stop for quick lookups!** For comprehensive explanations, see the specialized documentation files.

