# Flow vs Rate: Terminology Clarification

## Overview

The run-density system uses two distinct but related metrics. This document clarifies the difference to prevent confusion.

## Terminology

### 🔄 **Flow** (Capital F - Event-Level)

**What it measures**: Event interaction and convergence
**Where it's used**: `flow.csv`, `flow_report.py`, Flow analysis modules
**Scope**: Event-to-event relationships (e.g., Half overtaking 10K)

**Key metrics**:
- Co-presence detection
- Overtaking analysis
- Event convergence points
- Temporal interaction patterns

**Example questions Flow answers**:
- "Where do Half and 10K runners meet?"
- "How many overtaking events occur in segment F1?"
- "What's the co-presence window for different events?"

### 📊 **rate** (lowercase - Bin-Level)

**What it measures**: Instantaneous throughput rate
**Where it's used**: `bins.csv`, `bins_readable.csv`, density calculations
**Scope**: Spatial-temporal bins (e.g., A1:0.000-0.200 at 07:20)

**Formula**: `rate = density × width × mean_speed`
- **density**: persons/m² (areal crowding)
- **width**: segment width in meters
- **mean_speed**: average runner speed in m/s
- **rate**: persons/second (throughput)

**Physical meaning**: Number of people crossing a virtual line per second

**Example questions rate answers**:
- "How many runners per second pass through A1 at 07:20?"
- "What's the throughput rate during peak congestion?"
- "How fast are runners moving through this bin?"

## Why the Rename?

### Previous Problem (Before Rename):
```python
# CONFUSING: Same word, different concepts
flow.csv          # Event-level convergence analysis
bins['flow']      # Bin-level throughput rate
```

This caused ambiguity when discussing "flow" - which metric?

### Current Solution (After Rename):
```python
# CLEAR: Distinct terminology
Flow analysis     # Event-level (flow.csv, flow_report.py)
rate              # Bin-level (bins.csv, density calculations)
```

Now "Flow" exclusively means event interaction, and "rate" exclusively means bin throughput.

## Comparison Table

| Aspect | Flow (Event-Level) | rate (Bin-Level) |
|--------|-------------------|------------------|
| **Scope** | Event-to-event | Bin-to-bin |
| **Units** | Various (co-presence count, overlap %) | persons/second |
| **Purpose** | Detect convergence, overtaking | Measure throughput intensity |
| **Files** | flow.csv, Flow.md | bins.parquet, bins_readable.csv |
| **Modules** | flow.py, flow_report.py | bins_accumulator.py, density_report.py |
| **Time Scale** | Event duration | 60-120 second windows |
| **Example Value** | "126 co-presence events" | "5.528 p/s" |

## Implementation Examples

### Flow Analysis (Event-Level):
```python
from app.flow import analyze_convergence

# Analyzes when/where events meet
flow_results = analyze_convergence(
    event_a='Half',
    event_b='10K',
    segment='F1'
)
# Returns: co-presence count, overlap times, convergence point
```

### Rate Calculation (Bin-Level):
```python
from app.bins_accumulator import build_bin_features

# Calculates instantaneous throughput
bins = build_bin_features(
    segments=segments,
    time_windows=windows,
    runners_by_window=mapping
)
# Each bin has: density (p/m²), rate (p/s), los_class
```

## Schema Fields

### flow.csv columns:
- `segment_id`
- `event_a`, `event_b`
- `co_presence_count`
- `overlap_time_sec`
- `convergence_point_km`

### bins_readable.csv columns:
- `segment_id`
- `start_km`, `end_km`
- `t_start`, `t_end`
- **`density`** (p/m²)
- **`rate`** (p/s) ← Renamed from 'flow'
- `los_class`

## Migration Notes

### For Developers:
- **Before**: `flow` in bins meant throughput
- **After**: `rate` in bins means throughput
- **Breaking change**: CSV column renamed `flow` → `rate`
- **Code change**: `BinFeature.flow` → `BinFeature.rate`

### For Users:
- Old CSV files have `flow` column
- New CSV files have `rate` column
- **Same calculation, just clearer naming**

### Backward Compatibility:
If you need to support old files:
```python
# Handle both old and new column names
rate = df.get('rate') if 'rate' in df.columns else df.get('flow')
```

## Best Practices

1. **When discussing event convergence** → Use "Flow analysis" or "Flow metrics"
2. **When discussing bin throughput** → Use "rate" or "throughput rate"
3. **In variable names** → `flow_analysis`, `flow_results` vs `rate_pers_s`, `throughput_rate`
4. **In documentation** → "Flow" (capital) for events, "rate" (lowercase) for bins

## Related Documents

- `docs/Application Fundamentals.md` - Core concepts
- `docs/CSV_EXPORT_STANDARDS.md` - Data formats
- `docs/GLOBAL_TIME_GRID_ARCHITECTURE.md` - Time window design
- `app/flow.py` - Flow analysis implementation
- `app/bins_accumulator.py` - Rate calculation implementation

