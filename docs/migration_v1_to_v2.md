# Migration Guide: Runflow v1 to v2

**Version:** 1.0  
**Date:** 2025-12-14  
**Target:** Runflow v2.0.0+

This guide helps developers and AI assistants understand the key differences between v1 and v2, and how to migrate code, data, and workflows.

---

## Overview

Runflow v2 introduces **multi-day, multi-event support** with day-scoped outputs. The architecture has been refactored to support:
- Multiple days (Saturday, Sunday) in a single run
- Dynamic event configuration (events defined in API payload)
- Day-scoped artifact organization
- Per-event runner files

---

## Key Architectural Changes

### 1. Output Structure

**v1 Structure:**
```
reports/{run_id}/
  bins.parquet
  Flow.csv
  Density.md
  Locations.csv
```

**v2 Structure:**
```
runflow/{run_id}/
  /sat/
    /bins/bins.parquet
    /reports/Flow.csv
    /reports/Density.md
    /reports/Locations.csv
    /ui/segments.geojson
    /ui/heatmaps/*.png
  /sun/
    /bins/bins.parquet
    /reports/Flow.csv
    /reports/Density.md
    /reports/Locations.csv
    /ui/segments.geojson
    /ui/heatmaps/*.png
```

### 2. Runner Files

**v1:**
- Single file: `data/runners.csv`
- All events in one file
- Event name in `event` column

**v2:**
- Per-event files: `data/{event}_runners.csv`
- Examples: `full_runners.csv`, `10k_runners.csv`, `half_runners.csv`, `elite_runners.csv`, `open_runners.csv`
- Event name determined by filename

### 3. Event Configuration

**v1:**
- Hardcoded event lists: `['full', 'half', '10k']`
- Constants: `SATURDAY_EVENTS`, `SUNDAY_EVENTS`, `ALL_EVENTS`
- Start times in constants: `START_TIMES`

**v2:**
- Events defined in API request payload
- Each event has: `name` (lowercase), `day` (sat/sun), `start_time` (minutes after midnight)
- No hardcoded event lists
- Start times come from API request

### 4. Column Naming

**v1:**
- Mixed usage: `segment_id` and `seg_id`
- Backward compatibility for both

**v2:**
- Standardized: `seg_id` only (no `segment_id`)
- Standardized: `loc_id` only (no `location_id`)
- No backward compatibility

### 5. API Endpoints

**v1 Analysis Endpoints (REMOVED):**
- `POST /api/temporal-flow`
- `POST /api/temporal-flow-single`
- `POST /api/density-report`
- `POST /api/temporal-flow-report`
- `POST /api/flow-audit`
- `POST /api/pdf-report`
- `GET /data/runners.csv`
- `GET /data/segments.csv`

**v2 Analysis Endpoint:**
- `POST /runflow/v2/analyze` – Single endpoint for all analysis

**v2 UI-Serving Endpoints (KEPT):**
- `/api/dashboard/*` – Dashboard data
- `/api/segments/*` – Segment data
- `/api/density/*` – Density data
- `/api/flow/*` – Flow data
- `/api/locations/*` – Location data
- `/api/bins/*` – Bin data
- `/api/reports/*` – Report files
- `/api/heatmaps/*` – Heatmap generation

---

## Data File Changes

### Runner Files

**Migration:**
1. Split `data/runners.csv` into per-event files
2. Filter by event name: `full_runners.csv`, `10k_runners.csv`, `half_runners.csv`
3. Ensure event names are lowercase
4. Keep all columns (bib, pace, etc.)

**Example:**
```python
# v1
df = pd.read_csv("data/runners.csv")
full_runners = df[df['event'] == 'Full']

# v2
full_runners = pd.read_csv("data/full_runners.csv")
```

### Segments File

**Changes:**
- Added event-specific distance columns: `{event}_from_km`, `{event}_to_km`
- Examples: `full_from_km`, `full_to_km`, `10k_from_km`, `10k_to_km`
- Each event can have different distance ranges for the same segment

**Example:**
```csv
seg_id,full_from_km,full_to_km,10k_from_km,10k_to_km,half_from_km,half_to_km
A1,0.00,0.90,0.00,0.90,0.00,0.90
B1,2.70,4.25,2.70,4.25,14.80,16.35
```

---

## Code Migration Examples

### Loading Runners

**v1:**
```python
from app.utils.constants import DEFAULT_PACE_CSV
runners_df = pd.read_csv(DEFAULT_PACE_CSV)  # data/runners.csv
full_runners = runners_df[runners_df['event'] == 'Full']
```

**v2:**
```python
# Events come from API payload
events = [Event(name='full', day=Day.SUN, start_time=420), ...]
runners_df = combine_runners_for_events(
    events=[e.name for e in events],
    day='sun',
    source_dir='data'
)
```

### Reading Outputs

**v1:**
```python
bins_df = pd.read_parquet(f"reports/{run_id}/bins.parquet")
flow_df = pd.read_csv(f"reports/{run_id}/Flow.csv")
```

**v2:**
```python
from app.utils.run_id import get_run_directory
run_dir = get_run_directory(run_id)
day_dir = run_dir / 'sun'
bins_df = pd.read_parquet(day_dir / 'bins' / 'bins.parquet')
flow_df = pd.read_csv(day_dir / 'reports' / 'Flow.csv')
```

### Column References

**v1:**
```python
# Backward compatibility
if 'seg_id' in df.columns:
    seg_col = 'seg_id'
elif 'segment_id' in df.columns:
    seg_col = 'segment_id'
```

**v2:**
```python
# Standardized
assert 'seg_id' in df.columns, "seg_id column required"
seg_col = 'seg_id'
```

---

## Testing Changes

### E2E Tests

**v1:**
- Manual E2E script: `e2e.py`
- Tests against `/data` inputs

**v2:**
- Automated E2E suite: `tests/v2/e2e.py`
- Golden file regression testing
- Day isolation validation
- Run: `make e2e-v2`

### Test Data

**v1:**
- Single test scenario
- All events in one run

**v2:**
- Multiple test scenarios:
  - `sunday_only` – Sunday events
  - `saturday_only` – Saturday events
  - `both_days` – Multi-day analysis

---

## Constants Changes

### Removed Constants

**v1:**
```python
EVENT_DAYS = {'full': 'sun', 'half': 'sun', '10k': 'sun'}
SATURDAY_EVENTS = ['elite', 'open']
SUNDAY_EVENTS = ['full', 'half', '10k']
ALL_EVENTS = ['full', 'half', '10k', 'elite', 'open']
DEFAULT_PACE_CSV = "data/runners.csv"
```

**v2:**
- All removed
- Events come from API payload
- Day assignment from `Event.day` property

---

## UI Changes

### Day Selector

**v2 Feature:**
- Global day selector in navigation bar
- Filters all pages (Dashboard, Segments, Density, Flow, Locations, Reports)
- Health page excluded

### Event Tiles

**v2 Feature:**
- Dynamic event tiles on Dashboard
- Show event name, start time, participant count
- Change based on selected day

---

## Migration Checklist

- [ ] Update runner files: Split `runners.csv` into per-event files
- [ ] Update segments.csv: Add event-specific distance columns
- [ ] Update code: Replace `segment_id` with `seg_id`
- [ ] Update code: Remove hardcoded event lists
- [ ] Update code: Read start times from API payload
- [ ] Update paths: Change `reports/{run_id}` to `runflow/{run_id}/{day}`
- [ ] Update tests: Migrate to `tests/v2/e2e.py`
- [ ] Update documentation: Reference v2 structure

---

## Reference

- `docs/GUARDRAILS.md` – v2 guardrails
- `docs/deprecated.md` – Removed v1 endpoints
- `archive/v1/docs/GUARDRAILS_v1.md` – v1 guardrails (reference)
- `ISSUE_504_BUCKETIZATION_PLAN.md` – Detailed deprecation plan

---

**Note:** v1 code is preserved in Git history. Tag `v1-maintenance` marks the last known-good v1 state. For reference, see `archive/v1/` (if archived) or checkout the `v1-maintenance` tag.

