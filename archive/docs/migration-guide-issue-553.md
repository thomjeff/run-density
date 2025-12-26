# Migration Guide: Issue #553

**Issue:** #553 - Analysis Request/Response via API  
**Version:** v2.0.1 → v2.0.2+  
**Type:** Breaking Changes

---

## Overview

Issue #553 makes all analysis inputs configurable via API request payload, eliminating hardcoded event names, start times, and file paths. This is a **breaking change** that requires updating all API requests.

---

## Breaking Changes Summary

### 1. Required Request Fields

The following fields are now **required** (no defaults provided):

- `segments_file` - Name of segments CSV file (e.g., `"segments.csv"`)
- `flow_file` - Name of flow CSV file (e.g., `"flow.csv"`)
- `locations_file` - Name of locations CSV file (e.g., `"locations.csv"`)
- `event_duration_minutes` - Duration of each event in minutes (per event)
- `runners_file` - Name of runners CSV file for each event (e.g., `"full_runners.csv"`)
- `gpx_file` - Name of GPX file for each event (e.g., `"full.gpx"`)

### 2. Removed Constants

The following constants have been **removed** from `app/utils/constants.py`:

- `EVENT_DAYS`
- `SATURDAY_EVENTS`
- `SUNDAY_EVENTS`
- `ALL_EVENTS`
- `EVENT_DURATION_MINUTES` (deprecated, kept for v1 API only)
- `DEFAULT_PACE_CSV`
- `DEFAULT_SEGMENTS_CSV`
- `DEFAULT_START_TIMES` (already removed in Issue #512)

### 3. Fail-Fast Behavior

**Flow Analysis:**
- ❌ **No fallback** - If `flow.csv` is missing, unreadable, or missing required pairs, the request **fails immediately**
- ❌ **No auto-generation** - Event pairs must be defined in `flow.csv`
- ✅ **Clear error messages** - All failures include detailed error messages

---

## Migration Steps

### Step 1: Update API Request Payload

**Before (v2.0.0):**
```json
{
  "events": [
    {
      "name": "full",
      "day": "sun",
      "start_time": 420
    },
    {
      "name": "half",
      "day": "sun",
      "start_time": 460
    }
  ]
}
```

**After (v2.0.1+):**
```json
{
  "description": "Optional description of this analysis",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "full",
      "day": "sun",
      "start_time": 420,
      "event_duration_minutes": 390,
      "runners_file": "full_runners.csv",
      "gpx_file": "full.gpx"
    },
    {
      "name": "half",
      "day": "sun",
      "start_time": 460,
      "event_duration_minutes": 180,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    }
  ]
}
```

### Step 2: Ensure flow.csv Contains All Required Pairs

**Critical:** `flow.csv` must contain pairs for **all requested events**, including same-event pairs.

**Example for Saturday events (`elite`, `open`):**
```csv
seg_id,event_a,event_b,...
N1,elite,elite,...
N2a,elite,elite,...
O1,open,open,...
O2a,open,open,...
```

**If `flow.csv` is missing pairs:**
- ❌ Request will **fail** with clear error message
- ❌ No fallback or auto-generation
- ✅ Error message will indicate which events are missing pairs

### Step 3: Update Code Using Deprecated Constants

**Before:**
```python
from app.utils.constants import EVENT_DAYS, SATURDAY_EVENTS, EVENT_DURATION_MINUTES

events = SATURDAY_EVENTS
duration = EVENT_DURATION_MINUTES
```

**After:**
```python
from app.core.v2.analysis_config import load_analysis_json, get_event_names, get_event_duration_minutes
from pathlib import Path

run_path = Path(f"/app/runflow/{run_id}")
analysis_config = load_analysis_json(run_path)
events = get_event_names(run_path)
duration = get_event_duration_minutes(run_path, "elite")
```

### Step 4: Handle Fail-Fast Errors

**Before (silent fallback):**
```python
# Flow analysis would silently use fallback if flow.csv missing
flow_results = analyze_temporal_flow_segments_v2(...)
```

**After (explicit error handling):**
```python
try:
    flow_results = analyze_temporal_flow_segments_v2(...)
except FileNotFoundError as e:
    # flow.csv not found - request fails
    logger.error(f"Flow analysis failed: {e}")
    return {"error": str(e)}
except ValueError as e:
    # flow.csv missing required pairs - request fails
    logger.error(f"Flow analysis failed: {e}")
    return {"error": str(e)}
```

---

## Common Migration Scenarios

### Scenario 1: Adding New Event

**Before:** Update `constants.py` with new event name, add to `SATURDAY_EVENTS` or `SUNDAY_EVENTS`

**After:** 
1. Add event to API request payload
2. Ensure `flow.csv` contains pairs for new event (including same-event pairs)
3. Ensure `segments.csv` contains columns for new event (`{event}_from_km`, `{event}_to_km`, `{event}_length`)
4. Ensure `locations.csv` contains locations for new event
5. No code changes required

### Scenario 2: Changing Event Duration

**Before:** Update `EVENT_DURATION_MINUTES` constant in `constants.py`

**After:** Update `event_duration_minutes` in API request payload (per event)

### Scenario 3: Using Different File Names

**Before:** Hardcoded file paths in `constants.py` or code

**After:** Specify file names in API request payload (`segments_file`, `flow_file`, `locations_file`, `runners_file`, `gpx_file`)

---

## Error Messages

### File Not Found
```
flow.csv file not found at data/flow.csv. 
flow.csv is required for flow analysis and must be provided in the request. 
No fallback or auto-generation of event pairs is allowed per Issue #553.
```

**Solution:** Ensure `flow_file` in request matches actual file name in `/data` directory.

### Missing Event Pairs
```
Requested events ['elite', 'open'] have no pairs defined in flow.csv. 
flow.csv contains pairs for: ['full', 'half', '10k']. 
All requested events must have at least one pair (including same-event pairs) in flow.csv. 
No fallback or auto-generation of event pairs is allowed per Issue #553.
```

**Solution:** Add required pairs to `flow.csv` (including same-event pairs like `elite-elite`, `open-open`).

### Missing Required Field
```
Field required: segments_file
```

**Solution:** Add `segments_file` to request payload.

---

## Testing Your Migration

### 1. Test with Saturday-Only Events
```bash
curl -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Saturday test",
    "segments_file": "segments.csv",
    "flow_file": "flow.csv",
    "locations_file": "locations.csv",
    "events": [
      {
        "name": "elite",
        "day": "sat",
        "start_time": 480,
        "event_duration_minutes": 45,
        "runners_file": "elite_runners.csv",
        "gpx_file": "elite.gpx"
      }
    ]
  }'
```

### 2. Verify Outputs
- Check that `analysis.json` is created in `runflow/{run_id}/`
- Verify `Flow.csv` is generated (if `flow.csv` contains pairs for requested events)
- Check `metadata.json` includes request/response payloads

### 3. Test Fail-Fast Behavior
- Try request with missing `flow_file` → Should fail with clear error
- Try request with event not in `flow.csv` → Should fail with clear error

---

## Rollback Plan

If you need to rollback to v2.0.0:

1. **Git:** Checkout tag `v2.0.1` (created before Issue #553)
2. **API Requests:** Revert to old payload format (without required fields)
3. **Code:** Restore deprecated constants if needed

**Note:** v2.0.0 endpoints remain available for backward compatibility, but v2.0.1+ endpoints require new payload format.

---

## Questions?

- See `docs/issue-553-completion-summary.md` for detailed implementation summary
- See `docs/implementation-plan-issue-553.md` for full implementation plan
- Check E2E tests in `tests/v2/e2e.py` for example payloads

---

**Migration Status:** ✅ Complete  
**Version:** v2.0.2+  
**Date:** 2025-12-25

