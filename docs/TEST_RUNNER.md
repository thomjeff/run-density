# Test Runner (human-readable reports)

This runner posts prepared JSON cases to your Cloud Run service, validates `/health` and `/ready`, and prints a CLI-style human-readable segment report via `/api/report`.

## Files

- `ci/test_runner.sh` — main runner
- `ci/cases/A.json` — Segment A (Start → Friel), pre-filled
- `ci/cases/TEMPLATE.json` — copy/edit for B, C, …

## Usage

```bash
# Make it executable once
chmod +x ci/test_runner.sh

# Run against production (replace with your URL)
BASE="https://run-density-XXXXXXXX.a.run.app" ./ci/test_runner.sh

# Or pass URL as arg
./ci/test_runner.sh https://run-density-XXXXXXXX.a.run.app
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

- This bundle supersedes older single-case files like `density_case.json` and `overlap_case.json` — use `ci/cases/*.json` instead.
- For engine-level testing (not human-readable), see earlier payload shapes you used for `/api/density` and `/api/overlap`.
