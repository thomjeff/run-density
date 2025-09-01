# Test Runner (LEGACY - No longer used)

> **⚠️ DEPRECATED**: This test runner has been replaced by the consolidated GitHub Actions workflow `.github/workflows/deploy-and-test.yml` which automatically runs smoke tests after deployment.

This runner posts prepared JSON cases to your Cloud Run service, validates `/health` and `/ready`, and prints a CLI-style human-readable segment report via `/api/report`.

## Files

> **⚠️ DEPRECATED**: All test runner files have been removed. Testing is now handled automatically by the GitHub Actions workflow.

## Usage

```bash
# ⚠️ DEPRECATED: This test runner has been removed
# Testing is now handled automatically by the GitHub Actions workflow
# which runs smoke tests after every deployment
```

## Case format

These cases are designed for the `/api/report` endpoint (human-readable output). They mirror the fields you’ve used manually in prior cURL payloads.

If you need to hit `/api/density` for raw engine output, set `"report": false` in the JSON. The runner will route accordingly.

### Example (A.json)

```json
{
  "eventA": "10K",
  "eventB": "Half",
  "from": 0.00,
  "to": 2.74,
  "segment_name": "A",
  "segment_label": "Start to Friel",
  "direction": "uni",
  "width_m": 3.0,
  "startTimes": {"10K": 1200, "Half": 2400},
  "startTimesClock": {"10K": "07:20:00", "Half": "07:40:00"},
  "runnersA": 618,
  "runnersB": 368,
  "overlap_from_km": 2.55,
  "overlap_to_km": 2.74,
  "first_overlap_clock": "07:48:15",
  "first_overlap_km": 2.55,
  "first_overlap_bibA": "1617",
  "first_overlap_bibB": "1681",
  "peak": {"km": 1.80, "A": 260, "B": 140, "combined": 400, "areal_density": 2.20},
  "report": true
}
```

## Notes

- **⚠️ DEPRECATED**: This test runner has been completely removed.
- Testing is now handled automatically by the consolidated GitHub Actions workflow.
- For manual testing, use the endpoints directly: `/api/density`, `/api/overlap.narrative.text`, etc.
