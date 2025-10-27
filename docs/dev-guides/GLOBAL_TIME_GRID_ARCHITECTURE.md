# Global Time Grid Architecture

## Overview

The run-density application uses a **single global clock-time grid** for all events to enable cross-event comparisons, overlays, and accurate temporal analysis.

## Critical Design Principle

**All events (Full, 10K, Half) share the same time axis**, anchored to the earliest event start time. This ensures:
- ✅ Each event appears at its correct clock time
- ✅ Cross-event comparisons are possible (same time axis)
- ✅ Flow analysis can detect co-presence and overtaking
- ✅ Visualizations show all events on a unified timeline

## Implementation Details

### 1. Global Time Window Creation

Time windows are created from the earliest event start:

```python
# Example: Full starts at 420 mins (07:00), 10K at 440 mins (07:20), Half at 460 mins (07:40)
earliest_start_min = min(start_times.values())  # 420 (Full)
t0 = race_day + timedelta(minutes=earliest_start_min)

# Create global windows
WINDOW_SECONDS = 60  # or 120 after coarsening
windows = [(t0 + i*Δ, t0 + (i+1)*Δ, i) for i in range(K)]

# Window indices:
# 0:   07:00-07:01 (Full starts here)
# 20:  07:20-07:21 (10K starts here)
# 40:  07:40-07:41 (Half starts here)
```

### 2. Per-Event Window Index Mapping

Each event maps to its appropriate starting index in the global grid:

```python
for event in ['Full', '10K', 'Half']:
    event_min = start_times[event]  # e.g., 440 for 10K
    
    # Calculate global start index for this event
    start_idx = int(((event_min - earliest_start_min) * 60) // WINDOW_SECONDS)
    # For 10K: start_idx = ((440 - 420) * 60) // 60 = 20
    
    # Process only windows >= start_idx for this event
    for global_w_idx in range(start_idx, len(windows)):
        # Map runners to this global window
        ...
```

### 3. Runner Time Anchoring

**Critical**: Runner start times must be anchored to their event's start time, **not** the global 07:00:

```python
# CORRECT: Anchor to event start
event_start_sec = event_min * 60.0  # e.g., 26400 sec for 10K
runner_start_time = event_start_sec + runner.start_offset_sec

# INCORRECT: Would anchor all runners to global 07:00
# runner_start_time = earliest_start_min * 60.0 + runner.start_offset_sec
```

### 4. Coarsening Window Re-Mapping (Issue #243 Fix)

When coarsening windows (e.g., 60s → 120s), the window indices change. **Runners must be re-mapped** to the new indices:

```python
# Original: 60s windows
# Index 19: 07:18-07:19 (has some Full runners)
# Index 20: 07:20-07:21 (has 333 10K runners)

# After coarsening to 120s windows
# New Index 9:  07:18-07:20 (MUST aggregate runners from old indices 19 + 20)

coarsening_factor = new_dt_seconds // old_dt_seconds  # e.g., 120 // 60 = 2

for seg_id, old_windows in runners_by_segment.items():
    re_mapped[seg_id] = {}
    
    for new_w_idx in range(len(new_windows)):
        # Determine which old windows map to this new window
        old_start = new_w_idx * coarsening_factor
        old_end = old_start + coarsening_factor
        
        # Aggregate runners from all old windows
        all_runners = []
        for old_idx in range(old_start, old_end):
            if old_idx in old_windows:
                all_runners.append(old_windows[old_idx])
        
        re_mapped[seg_id][new_w_idx] = concatenate(all_runners)
```

**Without this re-mapping**, the coarsened bins will use wrong indices and show zero density for correctly-timed events.

## Historical Context: Issue #243

### Problem
10K runners were missing from bins at their correct start time (07:20). They appeared ~50 minutes late due to incorrect window index mapping.

### Root Causes
1. **Per-Event Anchoring**: Original code looped through windows first, then events. This caused incorrect index calculations for events that didn't start at 07:00.

2. **Coarsening Index Mismatch**: When coarsening from 60s to 120s windows, the runner mapping kept old indices but bins used new indices, causing lookups to fail.

### Solution
1. **Loop through events FIRST** (Approach B from ChatGPT)
2. **Calculate correct start_idx** for each event
3. **Anchor runner times to event start** (not global 07:00)
4. **Re-map runners during coarsening** to match new indices

### Verification
The fix ensures:
- ✅ Full Marathon: First A1 density at 07:00
- ✅ 10K Marathon: First A1 density at 07:20 (was missing)
- ✅ Half Marathon: First A1 density at 07:40
- ✅ No phantom late blocks
- ✅ Natural density attenuation downstream

## QA Regression Testing

Run the regression test to verify the global time grid remains correct:

```bash
python tests/qa_regression_baseline.py
```

Expected output:
```
✅ Full Marathon starts at correct time: 07:00
✅ 10K Marathon starts at correct time: 07:20 (density=0.7490)
✅ Half Marathon starts at correct time: 07:40 (density=0.7490)
✅ No phantom late blocks (08:12-08:26 density=0.0000)
✅ Density attenuates naturally: A1=0.755 → A2=0.469 → A3=0.291
```

Any deviation from this baseline indicates a regression in event anchoring or window mapping.

## References

- **Issue #243**: Bug: 10K runners missing from bins at start time (07:20)
- **Implementation**: `app/density_report.py` - `build_runner_window_mapping()` and `generate_bin_features_with_coarsening()`
- **QA Baseline**: `tests/qa_regression_baseline.py`
- **ChatGPT Analysis**: Confirmed fix with segment-by-segment timeline verification

