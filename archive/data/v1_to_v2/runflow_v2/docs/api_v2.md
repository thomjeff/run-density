
# Runflow v2 API Specification
This document defines the API contract for triggering a Runflow v2 analysis. The architecture supports multi-day, multi-event analysis with clear segmentation of input data, configuration, and error handling.

## API Endpoint

**Input Files**
All input files must be placed in the `/data` directory prior to invocation.

| File | Description |
|------|-------------|
| `segments.csv` | Segment definitions, with event-specific distance spans (e.g., `5K_from_km`, `5K_to_km`) |
| `locations.csv` | Named geographic points used for labeling or map output |
| `flow.csv` | Flow rule definitions used in flow analysis |
| `<event_name>_runners.csv` | One file per event, e.g., `full_runners.csv`, `10k_runners.csv`, etc. |
| `<event_name>.gpx` | One GPX file per event, matching the event's route |

**Example API Request**
A request to run an analysis will be made via: 
`POST /runflow/v2/analyze`

that triggers a v2 analysis pipeline using provided inputs and event metadata. Below is a sample request body showing 5 events across two days and includes:
- `segments`: segments.csv file name
- `locations`: locations.csv file name
- `flow`: flow.csv file name
- `name`: Lowercase event name (`full`, `half`, `10k`, `elite`, `open`)
- `day`: One of `["fri", "sat", "sun"]`
- `start_time`: Integer minutes after midnight (e.g., `420` = 7:00 AM)
- `runners_file`: File containing runners for this event
- `gpx_file`: File defining this event's course path

The following is a sample request:
```json
{
  "segments_file": "segments.csv",
  "locations_file": "locations.csv",
  "flow_file": "flow.csv",
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
      "start_time": 460,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    },
    {
      "name": "10k",
      "day": "sun",
      "start_time": 440,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    },
    {
      "name": "elite",
      "day": "sat",
      "start_time": 480,
      "runners_file": "elite_runners.csv",
      "gpx_file": "elite.gpx"
    },
    {
      "name": "open",
      "day": "sat",
      "start_time": 510,
      "runners_file": "open_runners.csv",
      "gpx_file": "open.gpx"
    }
  ]
}
```

## Validation Rules

| Check | Rule |
|-------|------|
| File existence | All files named in the payload must exist in `/data` |
| Unique event names | No duplicate `name` values |
| Unique runner IDs | No duplicate `runner_id` across all `runners_file`s |
| Segment spans | `segments.csv` must include `*_from_km` and `*_to_km` for each event |
| Time normalization | `start_time` must be an integer between 0 and 1440 |
| GPX validation | Each `gpx_file` must be parseable and aligned to event segment distances |
| Day codes | Must match short-code vocabulary: `["fri", "sat", "sun"]` |


## File Expectations
All filenames are relative to /data and files must exist and be readable.
- segments file: required columns: seg_id, start_distance, end_distance, and event-specific distance ranges (<event>_from_km, <event>_to_km)
- locations: tequired columns: loc_id, lat, lon, segment_id
- flow: must define valid flow segment connections (pairings used for flow metrics)
- Each runner file: tequired columns: runner_id, offset (in seconds)
- Each gpx_file: must contain valid GPX XML with distance-aligned trackpoints


## Input Validation Rules

### General:
- run_id must be a non-empty alphanumeric string (used in output paths).
- All files must exist at /data/<filename>
- All file extensions must be appropriate (.csv, .gpx)

### Events:
Each event must have:
- Unique name (lowercase, no spaces) where no two events may share the same name
- Valid day from the set ["fri", "sat", "sun", "mon"], where multiple events may share the same day
- Integer start_time (0–1439, representing minutes after midnight)
- runners files and gpx files must exist and be valid

### Runners:
  • Each event must have a matching runners_file
  • Each runner must have:
  • A unique runner_id
  • A valid offset (0 or positive integer in seconds)

### Segments:
  • Must contain distance columns for each event defined in events[]
  • All distances must be numeric and non-negative

### Locations:
  • Each location must reference a valid seg_id
  • Latitude/longitude must be valid float coordinates

### Flow:
  • All segment IDs used in flow pairings must exist in segments_file


## Error Responses

| HTTP | Code Reason |
| 400 | Missing required field |
| 400 | Invalid file format/extension |
| 400 | Unknown event day (must be fri/sat/…) |
| 400 | Duplicate event names |
| 404 | Referenced file not found |
| 422 | Malformed runners/segments CSV |
| 500 | Internal processing error |

All errors include a message and a code field in the response JSON.

## Output Location
All run outputs are organized under a single `runflow/` directory with UUID-based subdirectories for each analysis run. See `output_v2.md` document for a complete summary of the outputs.


## 📈 Future Additions
- `wave_offset` per runner (optional)
- `scenario_id` to group event permutations

