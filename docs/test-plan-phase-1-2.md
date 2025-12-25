# Test Plan: Phase 1 + Phase 2 Validation

**Date:** 2025-12-24  
**Related to:** Issue #553  
**Phases:** Phase 1 (API Enhancement) + Phase 2 (analysis.json Creation)

---

## Test Objectives

1. **Validate Request Model:** Verify all new fields (description, event_duration_minutes) are accepted and validated correctly
2. **Validate Error Handling:** Verify fail-fast validation with proper error responses
3. **Validate analysis.json Creation:** Verify analysis.json is created correctly for single-day and multi-day events
4. **Validate Runner Counts:** Verify runner counts are calculated and stored correctly
5. **Validate Negative Cases:** Verify errors prevent analysis.json creation

---

## Test Environment Setup

### Prerequisites
- Container running: `make dev` (or `docker-compose up`)
- API endpoint: `http://localhost:8080/runflow/v2/analyze`
- Test data files in `/data` directory:
  - `segments.csv`
  - `flow.csv`
  - `locations.csv`
  - `10k_runners.csv` (for 10k event)
  - `half_runners.csv` (for half event)
  - `elite_runners.csv` (for elite event)
  - `open_runners.csv` (for open event)
  - `full_runners.csv` (for full event)
  - `10k.gpx`, `half.gpx`, `elite.gpx`, `open.gpx`, `full.gpx`

### Test Data Verification
Before running tests, verify test data exists:
```bash
ls -la data/*.csv data/*.gpx
```

---

## Test Cases

### TC-1: Single-Day Event (10k on Saturday)

**Objective:** Verify single-day event creates correct analysis.json

**Request:**
```json
{
  "description": "Test: Single-day 10k event",
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
- ✅ `analysis.json` created at `runflow/{run_id}/analysis.json`
- ✅ `analysis.json` contains:
  - `description`: "Test: Single-day 10k event"
  - `event_days`: `["sat"]`
  - `event_names`: `["10k"]`
  - `start_times`: `{"10k": 510}`
  - `events[0].runners`: Count from `10k_runners.csv`
  - `runners`: Total count (same as `events[0].runners` for single event)
  - `data_files.segments`: `"data/segments.csv"`
  - `data_files.runners.10k`: `"data/10k_runners.csv"`

**Validation Commands:**
```bash
# Get run_id from response
RUN_ID=$(curl -s -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d @test_request.json | jq -r '.run_id')

# Verify analysis.json exists
ls -la /Users/jthompson/Documents/runflow/$RUN_ID/analysis.json

# Verify structure
cat /Users/jthompson/Documents/runflow/$RUN_ID/analysis.json | jq '.'
```

---

### TC-2: Multi-Day Events (10k on Saturday, Half on Sunday)

**Objective:** Verify multi-day events create correct analysis.json with proper day separation

**Request:**
```json
{
  "description": "Test: Multi-day events (10k Sat, Half Sun)",
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
      "start_time": 540,
      "event_duration_minutes": 180,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    }
  ]
}
```

**Expected Results:**
- ✅ HTTP 200 response
- ✅ `run_id` in response
- ✅ `analysis.json` created
- ✅ `analysis.json` contains:
  - `event_days`: `["sat", "sun"]` (sorted)
  - `event_names`: `["10k", "half"]`
  - `start_times`: `{"10k": 510, "half": 540}`
  - `events[0].runners`: Count from `10k_runners.csv`
  - `events[1].runners`: Count from `half_runners.csv`
  - `runners`: Sum of both event runner counts
  - `data_files.runners.10k`: `"data/10k_runners.csv"`
  - `data_files.runners.half`: `"data/half_runners.csv"`

**Validation:**
```bash
# Verify event_days contains both days
cat /Users/jthompson/Documents/runflow/$RUN_ID/analysis.json | jq '.event_days'
# Expected: ["sat", "sun"]

# Verify total runners = sum of event runners
cat /Users/jthompson/Documents/runflow/$RUN_ID/analysis.json | jq '.runners'
cat /Users/jthompson/Documents/runflow/$RUN_ID/analysis.json | jq '[.events[].runners] | add'
# Should match
```

---

### TC-3: Multiple Events on Same Day (Elite + Open on Saturday)

**Objective:** Verify multiple events on the same day are handled correctly

**Request:**
```json
{
  "description": "Test: Multiple events same day",
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
    },
    {
      "name": "open",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 75,
      "runners_file": "open_runners.csv",
      "gpx_file": "open.gpx"
    }
  ]
}
```

**Expected Results:**
- ✅ HTTP 200 response
- ✅ `event_days`: `["sat"]` (single day, but two events)
- ✅ `event_names`: `["elite", "open"]`
- ✅ `start_times`: `{"elite": 480, "open": 510}`
- ✅ `runners`: Sum of elite + open runner counts

---

### TC-4: Missing Required Field (Negative Test)

**Objective:** Verify fail-fast validation prevents analysis.json creation

**Request (Missing event_duration_minutes):**
```json
{
  "description": "Test: Missing required field",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ]
}
```

**Expected Results:**
- ❌ HTTP 422 (Validation Error) or 400
- ❌ Error response format:
  ```json
  {
    "status": "ERROR",
    "code": 400,
    "error": "Missing required field 'event_duration_minutes' for event '10k'"
  }
  ```
- ❌ No `analysis.json` created (no run_id generated)
- ❌ No run directory created

**Validation:**
```bash
# Verify error response
curl -s -X POST http://localhost:8080/runflow/v2/analyze \
  -H "Content-Type: application/json" \
  -d @test_request.json | jq '.'

# Verify no run directory created (check latest run_id hasn't changed)
```

---

### TC-5: Invalid Start Time Range (Negative Test)

**Objective:** Verify start_time validation (300-1200 range)

**Request (start_time = 200, below minimum):**
```json
{
  "description": "Test: Invalid start_time",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 200,
      "event_duration_minutes": 120,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ]
}
```

**Expected Results:**
- ❌ HTTP 400
- ❌ Error: `"start_time 200 for event '10k' must be between 300 and 1200 (5:00 AM to 8:00 PM)"`
- ❌ No `analysis.json` created

---

### TC-6: Invalid Event Duration Range (Negative Test)

**Objective:** Verify event_duration_minutes validation (1-500 range)

**Request (event_duration_minutes = 600, above maximum):**
```json
{
  "description": "Test: Invalid event_duration_minutes",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 600,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ]
}
```

**Expected Results:**
- ❌ HTTP 400
- ❌ Error: `"event_duration_minutes 600 for event '10k' must be between 1 and 500 (inclusive)"`
- ❌ No `analysis.json` created

---

### TC-7: Description Too Long (Negative Test)

**Objective:** Verify description length validation (max 254 chars)

**Request (description = 255 chars):**
```json
{
  "description": "A" * 255,
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [...]
}
```

**Expected Results:**
- ❌ HTTP 400
- ❌ Error: `"description exceeds 254 characters (got 255 characters)"`
- ❌ No `analysis.json` created

---

### TC-8: Missing File (Negative Test)

**Objective:** Verify file existence validation

**Request (runners_file doesn't exist):**
```json
{
  "description": "Test: Missing file",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 120,
      "runners_file": "nonexistent_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ]
}
```

**Expected Results:**
- ❌ HTTP 404
- ❌ Error: `"runners_file 'nonexistent_runners.csv' for event '10k' not found in data/ directory"`
- ❌ No `analysis.json` created

---

### TC-9: Default Description Generation

**Objective:** Verify default description is generated when not provided

**Request (no description field):**
```json
{
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [...]
}
```

**Expected Results:**
- ✅ HTTP 200 response
- ✅ `analysis.json` contains `description` field
- ✅ `description` format: `"Analysis run on {YYYY-MM-DDTHH:MMZ}"`
- ✅ Timestamp is recent (within last minute)

---

### TC-10: Runner Count Accuracy

**Objective:** Verify runner counts match actual CSV file row counts

**Request:** Use TC-1 or TC-2

**Validation:**
```bash
# Get actual runner count from CSV
ACTUAL_COUNT=$(wc -l < data/10k_runners.csv | awk '{print $1-1}')  # Subtract header

# Get count from analysis.json
JSON_COUNT=$(cat /Users/jthompson/Documents/runflow/$RUN_ID/analysis.json | jq '.events[0].runners')

# Compare
echo "CSV count: $ACTUAL_COUNT"
echo "JSON count: $JSON_COUNT"
# Should match
```

---

## Test Execution Script

Create `test_phase_1_2.sh`:

```bash
#!/bin/bash
set -e

BASE_URL="http://localhost:8080"
ENDPOINT="$BASE_URL/runflow/v2/analyze"
RUNFLOW_ROOT="/Users/jthompson/Documents/runflow"

echo "🧪 Phase 1 + 2 Test Suite"
echo "=========================="

# TC-1: Single-day event
echo ""
echo "TC-1: Single-day event"
cat > /tmp/tc1.json <<EOF
{
  "description": "Test: Single-day 10k event",
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
EOF

RESPONSE=$(curl -s -X POST "$ENDPOINT" -H "Content-Type: application/json" -d @/tmp/tc1.json)
RUN_ID=$(echo "$RESPONSE" | jq -r '.run_id // empty')

if [ -z "$RUN_ID" ]; then
  echo "❌ FAIL: No run_id in response"
  echo "$RESPONSE" | jq '.'
  exit 1
fi

echo "✅ PASS: run_id = $RUN_ID"

# Verify analysis.json exists
if [ ! -f "$RUNFLOW_ROOT/$RUN_ID/analysis.json" ]; then
  echo "❌ FAIL: analysis.json not found"
  exit 1
fi

echo "✅ PASS: analysis.json created"

# Verify structure
EVENT_DAYS=$(cat "$RUNFLOW_ROOT/$RUN_ID/analysis.json" | jq -r '.event_days[]')
if [ "$EVENT_DAYS" != "sat" ]; then
  echo "❌ FAIL: event_days incorrect (expected: [\"sat\"], got: $EVENT_DAYS)"
  exit 1
fi

echo "✅ PASS: event_days correct"

# TC-2: Multi-day events
echo ""
echo "TC-2: Multi-day events"
cat > /tmp/tc2.json <<EOF
{
  "description": "Test: Multi-day events",
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
      "start_time": 540,
      "event_duration_minutes": 180,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    }
  ]
}
EOF

RESPONSE=$(curl -s -X POST "$ENDPOINT" -H "Content-Type: application/json" -d @/tmp/tc2.json)
RUN_ID=$(echo "$RESPONSE" | jq -r '.run_id // empty')

if [ -z "$RUN_ID" ]; then
  echo "❌ FAIL: No run_id in response"
  exit 1
fi

EVENT_DAYS=$(cat "$RUNFLOW_ROOT/$RUN_ID/analysis.json" | jq -r '.event_days | sort | .[]')
EXPECTED_DAYS="sat
sun"

if [ "$EVENT_DAYS" != "$EXPECTED_DAYS" ]; then
  echo "❌ FAIL: event_days incorrect"
  exit 1
fi

echo "✅ PASS: Multi-day events handled correctly"

# TC-4: Missing required field (negative test)
echo ""
echo "TC-4: Missing required field (negative test)"
cat > /tmp/tc4.json <<EOF
{
  "description": "Test: Missing event_duration_minutes",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {
      "name": "10k",
      "day": "sat",
      "start_time": 510,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    }
  ]
}
EOF

RESPONSE=$(curl -s -X POST "$ENDPOINT" -H "Content-Type: application/json" -d @/tmp/tc4.json)
STATUS=$(echo "$RESPONSE" | jq -r '.status // empty')

if [ "$STATUS" != "ERROR" ]; then
  echo "❌ FAIL: Expected ERROR status"
  echo "$RESPONSE" | jq '.'
  exit 1
fi

echo "✅ PASS: Error handling works correctly"

echo ""
echo "🎉 All tests passed!"
```

---

## Test Results Template

| Test Case | Status | Run ID | Notes |
|-----------|--------|--------|-------|
| TC-1: Single-day event | ⏳ | - | - |
| TC-2: Multi-day events | ⏳ | - | - |
| TC-3: Multiple events same day | ⏳ | - | - |
| TC-4: Missing required field | ⏳ | - | - |
| TC-5: Invalid start_time | ⏳ | - | - |
| TC-6: Invalid event_duration_minutes | ⏳ | - | - |
| TC-7: Description too long | ⏳ | - | - |
| TC-8: Missing file | ⏳ | - | - |
| TC-9: Default description | ⏳ | - | - |
| TC-10: Runner count accuracy | ⏳ | - | - |

---

## Next Steps After Testing

1. **Fix any issues** found during testing
2. **Document test results** in this file
3. **Proceed to Phase 3** (metadata.json enhancement) after Phase 1+2 validation passes

