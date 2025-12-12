# Phase 4: Density Pipeline Test Plan

## Overview
This test plan validates that Phase 4 density analysis works correctly with real data, ensuring:
- Segments are not skipped unnecessarily
- Runner mapping works correctly
- Density calculations match v1 expectations
- Output structure is correct

## Prerequisites
- Docker container running
- Data files present: `segments.csv`, `full_runners.csv`, `half_runners.csv`, `10k_runners.csv`
- API endpoint accessible at `http://localhost:8000/runflow/v2/analyze`

## Test Execution

### Option 1: Automated Test Script
```bash
./test_phase4_density.sh
```

This script will:
1. Send POST request to API with Sunday events (full, half, 10k)
2. Extract run_id from response
3. Check container logs for density analysis
4. Verify output directory structure
5. Validate density results in metadata.json

### Option 2: Manual API Test

#### Step 1: Send API Request
```bash
curl -X POST "http://localhost:8000/runflow/v2/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "name": "full",
        "day": "sun",
        "start_time": 420,
        "runners_file": "full_runners.csv",
        "gpx_file": "full.gpx"
      },
      {
        "name": "half",
        "day": "sun",
        "start_time": 440,
        "runners_file": "half_runners.csv",
        "gpx_file": "half.gpx"
      },
      {
        "name": "10k",
        "day": "sun",
        "start_time": 460,
        "runners_file": "10k_runners.csv",
        "gpx_file": "10k.gpx"
      }
    ],
    "segments_file": "segments.csv",
    "locations_file": "locations.csv",
    "flow_file": "flow.csv"
  }'
```

#### Step 2: Extract Run ID
From the response, extract the `run_id` field.

#### Step 3: Check Container Logs
```bash
docker-compose logs app --tail=100 | grep -i "density\|segment\|runner"
```

**Expected Log Messages:**
- `"Loaded X segments from ..."`
- `"Loaded X total runners from Y events"`
- `"Analyzing density for day sun with X events"`
- `"Density analysis complete. Processed X segments, Skipped Y segments"`

**Red Flags:**
- `"No segments found for requested events"`
- `"No runners found for day ..."`
- `"Density analysis failed"`
- Excessive "skipped segments" warnings

#### Step 4: Verify Output Structure
```bash
# Check directory structure
docker-compose exec app ls -la /app/runflow/{RUN_ID}/sun/

# Check metadata.json
docker-compose exec app cat /app/runflow/{RUN_ID}/sun/metadata.json | python3 -m json.tool
```

**Expected Structure:**
```
runflow/{RUN_ID}/
  sun/
    reports/
    bins/
    maps/
    ui/
    metadata.json
```

**Expected metadata.json fields:**
- `density.processed_segments` > 0
- `density.skipped_segments` should be minimal
- `density.total_segments` should match expected segment count
- `density.has_error` should be false

#### Step 5: Validate Density Results
```bash
# Check density summary
docker-compose exec app python3 -c "
import json
with open('/app/runflow/{RUN_ID}/sun/metadata.json') as f:
    data = json.load(f)
    density = data.get('density', {})
    print(f\"Processed: {density.get('processed_segments', 0)}\")
    print(f\"Skipped: {density.get('skipped_segments', 0)}\")
    print(f\"Total: {density.get('total_segments', 0)}\")
"
```

## Validation Checklist

### ✅ Segment Coverage
- [ ] All expected segments are processed (A1, A2, B1, B2, F1, etc.)
- [ ] No segments are skipped unless they have zero-length spans
- [ ] Logs show segment filtering working correctly

### ✅ Runner Mapping
- [ ] Runners loaded from event-specific files (`full_runners.csv`, etc.)
- [ ] Event names mapped correctly (full → Full, half → Half, 10k → 10K)
- [ ] No "missing runners" warnings in logs
- [ ] Runner count matches expected values

### ✅ Density Calculations
- [ ] Density analysis completes without errors
- [ ] Results structure matches v1 format
- [ ] Day-scoped results are correct (no cross-day contamination)
- [ ] Start times converted correctly (minutes → datetime)

### ✅ Output Structure
- [ ] Day-partitioned directories created correctly
- [ ] Metadata.json includes density summary
- [ ] File counts are tracked
- [ ] Pointer files (latest.json, index.json) updated

## Success Criteria

Phase 4 is considered successful if:

1. **API Response**: Returns 200 OK with valid run_id
2. **Logs**: Show density analysis completing with processed_segments > 0
3. **Metadata**: Contains density summary with processed_segments > skipped_segments
4. **No Errors**: No exceptions or validation failures in logs
5. **Segment Coverage**: Expected segments (A1, A2, F1, etc.) are processed

## Known Limitations (Phase 4 Only)

- **No bins.parquet generation**: This will be added in Phase 6
- **No reports**: Density.md, Flow.md, etc. will be generated in Phase 6
- **No flow analysis**: Flow pipeline will be rebuilt in Phase 5

## Next Steps After Validation

Once Phase 4 is validated:

1. ✅ Document any issues found
2. ✅ Proceed to Phase 5: Flow Pipeline rebuild
3. ✅ Use same constraints: preserve v1 logic, use get_shared_segments(), etc.

## Troubleshooting

### Issue: "No segments found for requested events"
**Cause**: Segments.csv not loaded or event flags don't match
**Fix**: Check segments.csv has correct event flag columns (full, half, 10k)

### Issue: "No runners found for day"
**Cause**: Runner files missing or event names don't match
**Fix**: Verify `{event}_runners.csv` files exist and have correct format

### Issue: "Density analysis failed"
**Cause**: Error in v1 density function or data format mismatch
**Fix**: Check logs for specific error, verify start_times format

### Issue: All segments skipped
**Cause**: Segment spans invalid or zero-length
**Fix**: Check segments.csv has valid `{event}_from_km` and `{event}_to_km` values

