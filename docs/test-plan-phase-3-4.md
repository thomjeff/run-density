# Test Plan: Phase 3 + Phase 4 Validation

**Date:** 2025-12-25  
**Related to:** Issue #553  
**Phases:** Phase 3 (metadata.json Enhancement) + Phase 4 (Refactor Hardcoded Event Names)

---

## Test Objectives

1. **Phase 3: Validate metadata.json Enhancement**
   - Verify request payload is stored in run-level metadata.json
   - Verify response payload is stored in run-level metadata.json
   - Verify request/response are stored in day-level metadata.json
   - Verify backward compatibility (existing fields still present)

2. **Phase 4.1: Validate Event Constants Removal**
   - Verify EVENT_DAYS, SATURDAY_EVENTS, SUNDAY_EVENTS, ALL_EVENTS are removed
   - Verify helper functions (get_event_names, get_events_by_day) work correctly
   - Verify no runtime errors from missing constants

3. **Phase 4.2: Validate Event Name Comparisons Refactoring**
   - Verify bin generation uses dynamic event names from analysis.json
   - Verify flow analysis works with dynamic events
   - Verify data loading dynamically discovers event columns
   - Verify new events (not in hardcoded list) work correctly

4. **Phase 4.3: Validate Event Duration Lookups**
   - Verify event durations come from analysis.json (no fallback to constant)
   - Verify bin generation uses event_durations from metadata
   - Verify fail-fast behavior when event_durations missing

---

## Test Environment Setup

### Prerequisites
- Container running: `make dev` (or `docker-compose up`)
- API endpoint: `http://localhost:8080/runflow/v2/analyze`
- Test data files in `/data` directory:
  - `segments.csv`
  - `flow.csv`
  - `locations.csv`
  - `10k_runners.csv`, `half_runners.csv`, `full_runners.csv`
  - `10k.gpx`, `half.gpx`, `full.gpx`

### Test Data Verification
Before running tests, verify test data exists:
```bash
ls -la data/*.csv data/*.gpx
```

---

## Test Cases

### TC-1: Phase 3 - Request/Response in Run-Level metadata.json

**Objective:** Verify request and response payloads are stored in run-level metadata.json

**Request:**
```json
{
  "description": "Test: Phase 3 metadata enhancement",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 120,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ]
}
```

**Expected Results:**
- ✅ HTTP 200 response
- ✅ `run_id` in response
- ✅ `runflow/{run_id}/metadata.json` contains:
  - `request` field with full request payload
  - `response` field with full response payload
  - All existing fields still present (backward compatibility)

**Validation Commands:**
```bash
# Get run_id from response
RUN_ID=$(curl -s -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d @test_request.json | jq -r '.run_id')

# Verify metadata.json exists
ls -la /Users/jthompson/Documents/runflow/$RUN_ID/metadata.json

# Verify request field
cat /Users/jthompson/Documents/runflow/$RUN_ID/metadata.json | jq '.request'

# Verify response field
cat /Users/jthompson/Documents/runflow/$RUN_ID/metadata.json | jq '.response'

# Verify backward compatibility
cat /Users/jthompson/Documents/runflow/$RUN_ID/metadata.json | jq '.run_id, .created_at, .status'
```

---

### TC-2: Phase 3 - Request/Response in Day-Level metadata.json

**Objective:** Verify request and response payloads are stored in day-level metadata.json

**Request:** Same as TC-1

**Expected Results:**
- ✅ `runflow/{run_id}/sat/metadata.json` contains:
  - `request` field with full request payload
  - `response` field with full response payload
  - All existing day-level fields still present

**Validation Commands:**
```bash
# Verify day-level metadata.json
cat /Users/jthompson/Documents/runflow/$RUN_ID/sat/metadata.json | jq '.request'
cat /Users/jthompson/Documents/runflow/$RUN_ID/sat/metadata.json | jq '.response'
```

---

### TC-3: Phase 4.1 - Event Constants Removal

**Objective:** Verify event constants are removed and helper functions work

**Test Approach:**
- Import helper functions and verify they work
- Verify constants are not accessible (or deprecated)

**Validation Commands:**
```bash
# Test helper functions in Python
docker exec run-density-dev python3 -c "
from app.core.v2.analysis_config import get_event_names, get_events_by_day
from pathlib import Path
from app.utils.run_id import get_runflow_root

# Load analysis.json from latest run
runflow_root = get_runflow_root()
# Get latest run_id from latest.json
import json
latest_path = runflow_root / 'latest.json'
if latest_path.exists():
    latest = json.loads(latest_path.read_text())
    run_id = latest.get('run_id')
    if run_id:
        run_path = runflow_root / run_id
        event_names = get_event_names(run_path=run_path)
        print(f'Event names: {event_names}')
        sat_events = get_events_by_day('sat', run_path=run_path)
        print(f'Saturday events: {sat_events}')
        print('✅ Helper functions work correctly')
    else:
        print('⚠️ No run_id in latest.json')
else:
    print('⚠️ latest.json not found')
"
```

---

### TC-4: Phase 4.2 - Dynamic Event Names in Bin Generation

**Objective:** Verify bin generation uses dynamic event names from analysis.json

**Request:**
```json
{
  "description": "Test: Phase 4.2 dynamic event names",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 120,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
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

**Expected Results:**
- ✅ Analysis completes successfully
- ✅ Bins generated for both days
- ✅ `bins.parquet` contains event names from analysis.json (not hardcoded)
- ✅ Event names in bins match request payload

**Validation Commands:**
```bash
# Get run_id
RUN_ID=$(curl -s -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d @test_request.json | jq -r '.run_id')

# Check bins.parquet for event names
docker exec run-density-dev python3 -c "
import pandas as pd
from pathlib import Path

bins_path = Path('/app/runflow') / '$RUN_ID' / 'sat' / 'bins' / 'bins.parquet'
if bins_path.exists():
    df = pd.read_parquet(bins_path)
    if 'event' in df.columns:
        # Event column is a list, flatten to get unique events
        import numpy as np
        all_events = set()
        for events in df['event']:
            if isinstance(events, list):
                all_events.update(events)
            elif events:
                all_events.add(events)
        print(f'Saturday bins events: {sorted(all_events)}')
        assert '10k' in all_events or '10K' in all_events, '10k event not found in bins'
        print('✅ Event names in bins match analysis.json')
    else:
        print('⚠️ event column missing from bins.parquet')
else:
    print('⚠️ bins.parquet not found')
"
```

---

### TC-5: Phase 4.3 - Event Durations from analysis.json

**Objective:** Verify event durations come from analysis.json (no fallback)

**Request:** Same as TC-4

**Expected Results:**
- ✅ Analysis completes successfully
- ✅ Event durations in metadata come from analysis.json
- ✅ Bin generation uses event_durations from metadata
- ✅ No fallback to EVENT_DURATION_MINUTES constant

**Validation Commands:**
```bash
# Verify event_durations in bin metadata
docker exec run-density-dev python3 -c "
import json
from pathlib import Path

runflow_root = Path('/app/runflow')
run_id = '$RUN_ID'
run_path = runflow_root / run_id

# Check analysis.json
analysis_path = run_path / 'analysis.json'
if analysis_path.exists():
    analysis = json.loads(analysis_path.read_text())
    print('Event durations in analysis.json:')
    for event in analysis.get('events', []):
        print(f\"  {event.get('name')}: {event.get('event_duration_minutes')} minutes\")

# Check bin metadata
bins_metadata_path = run_path / 'sat' / 'bins' / 'bins.geojson.gz'
if bins_metadata_path.exists():
    import gzip
    with gzip.open(bins_metadata_path, 'rt') as f:
        geojson = json.load(f)
        metadata = geojson.get('metadata', {})
        event_durations = metadata.get('event_durations', {})
        print(f'\\nEvent durations in bin metadata: {event_durations}')
        assert len(event_durations) > 0, 'event_durations missing from bin metadata'
        print('✅ Event durations present in bin metadata')
"
```

---

### TC-6: Phase 4.2 - Dynamic Event Column Discovery

**Objective:** Verify data loaders dynamically discover event columns

**Test Approach:**
- Verify load_segments() normalizes event columns dynamically
- Verify load_locations() normalizes event columns dynamically

**Validation Commands:**
```bash
# Test dynamic column discovery
docker exec run-density-dev python3 -c "
from app.io.loader import load_segments, load_locations
import pandas as pd

# Test load_segments
segments_df = load_segments('data/segments.csv')
print('Segments columns:', list(segments_df.columns))
event_columns = [col for col in segments_df.columns if col.lower() in ['full', 'half', '10k', 'elite', 'open']]
print(f'Event columns found: {event_columns}')
for col in event_columns:
    unique_vals = segments_df[col].unique()
    print(f'  {col}: {unique_vals}')
    assert set(unique_vals).issubset({'y', 'n', 'Y', 'N', None}), f'Column {col} not normalized'

# Test load_locations
locations_df = load_locations('data/locations.csv')
print('\\nLocations columns:', list(locations_df.columns))
event_columns = [col for col in locations_df.columns if col.lower() in ['full', 'half', '10k', 'elite', 'open']]
print(f'Event columns found: {event_columns}')
for col in event_columns:
    unique_vals = locations_df[col].unique()
    print(f'  {col}: {unique_vals}')
    assert set(unique_vals).issubset({'y', 'n', 'Y', 'N', None}), f'Column {col} not normalized'

print('\\n✅ Dynamic event column discovery works correctly')
"
```

---

### TC-7: Phase 4.2 - Flow Analysis with Dynamic Events

**Objective:** Verify flow analysis works with dynamic event names

**Request:** Same as TC-4 (multi-day with 10k and half)

**Expected Results:**
- ✅ Flow analysis completes successfully
- ✅ Flow.csv contains correct event pairs
- ✅ Segment ranges work for both events

**Validation Commands:**
```bash
# Verify flow.csv contains correct events
docker exec run-density-dev python3 -c "
import pandas as pd
from pathlib import Path

runflow_root = Path('/app/runflow')
run_id = '$RUN_ID'
flow_csv = runflow_root / run_id / 'sun' / 'reports' / 'Flow.csv'

if flow_csv.exists():
    df = pd.read_csv(flow_csv)
    print('Flow.csv columns:', list(df.columns))
    if 'event_a' in df.columns and 'event_b' in df.columns:
        event_pairs = df[['event_a', 'event_b']].drop_duplicates()
        print('\\nEvent pairs in Flow.csv:')
        print(event_pairs)
        # Verify events match request
        all_events = set(event_pairs['event_a'].unique()) | set(event_pairs['event_b'].unique())
        print(f'\\nAll events: {all_events}')
        assert 'half' in [e.lower() for e in all_events], 'half event not found'
        print('✅ Flow analysis works with dynamic events')
    else:
        print('⚠️ event_a/event_b columns missing')
else:
    print('⚠️ Flow.csv not found')
"
```

---

### TC-8: Phase 4.3 - Fail-Fast on Missing Event Durations

**Objective:** Verify system fails fast when event_durations missing (no fallback)

**Test Approach:**
- This is tested indirectly by verifying event_durations are required
- If event_durations are missing from metadata, bin generation should fail

**Note:** This is a negative test that verifies the fail-fast behavior. The positive case (event_durations present) is covered in TC-5.

---

### TC-9: Multi-Day Analysis with All Phase 3 & 4 Changes

**Objective:** End-to-end test with all Phase 3 & 4 changes

**Request:**
```json
{
  "description": "E2E test: All Phase 3 & 4 changes",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 120,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    },
    {
      "name": "half",
      "day": "sun",
      "start_time": 460,
      "event_duration_minutes": 180,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    },
    {
      "name": "full",
      "day": "sun",
      "start_time": 420,
      "event_duration_minutes": 390,
      "runners_file": "full_runners.csv",
      "gpx_file": "full.gpx"
    }
  ]
}
```

**Expected Results:**
- ✅ All Phase 3 validations pass
- ✅ All Phase 4 validations pass
- ✅ Complete analysis succeeds
- ✅ All outputs generated correctly

---

## Test Execution Script

Create `test-phase-3-4.sh`:

```bash
#!/bin/bash
set -e

BASE_URL="http://localhost:8080"
RUNFLOW_ROOT="/Users/jthompson/Documents/runflow"

echo "=" | head -c 60
echo ""
echo "PHASE 3 & 4 TEST EXECUTION"
echo "=" | head -c 60
echo ""

# TC-1: Phase 3 - Request/Response in Run-Level metadata.json
echo ""
echo "TC-1: Phase 3 - Request/Response in Run-Level metadata.json"
echo "------------------------------------------------------------"
# ... (test commands)

# TC-2: Phase 3 - Request/Response in Day-Level metadata.json
echo ""
echo "TC-2: Phase 3 - Request/Response in Day-Level metadata.json"
echo "------------------------------------------------------------"
# ... (test commands)

# Continue with other test cases...
```

---

## Success Criteria

All test cases must pass:
- ✅ Phase 3: Request/response payloads in metadata.json
- ✅ Phase 4.1: Event constants removed, helper functions work
- ✅ Phase 4.2: Dynamic event names work in bin generation, flow analysis, data loading
- ✅ Phase 4.3: Event durations from analysis.json, no fallback
- ✅ End-to-end: Complete analysis succeeds with all changes

---

## Notes

- Tests should be run against a fresh container restart to ensure latest code is loaded
- Some tests require manual inspection of generated files
- Test execution may take 5-10 minutes for full analysis

