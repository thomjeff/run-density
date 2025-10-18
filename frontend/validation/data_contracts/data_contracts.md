# Runflow Data Contracts (Front-End Inputs)

## segments.geojson
- **type:** FeatureCollection of LineString features
- **properties:**
  - `segment_id: str`
  - `label: str`
  - `length_m: float > 0`
  - `events: ["Full"|"Half"|"10K"][]`
- **geometry:** LineString with `[lon,lat]` coords

## segment_metrics.json
- `items[]` of:
  - `segment_id: str`
  - `worst_los: "A".."F"`
  - `peak_density_window: "HH:MM–HH:MM"`
  - `co_presence_pct: 0..100`
  - `overtaking_pct: 0..100`
  - `utilization_pct: 0..100`

## flags.json
- `items[]` of:
  - `segment_id: str`
  - `flag_type: "co_presence"|"overtaking"`
  - `severity: "info"|"warn"|"critical"`
  - `window: "HH:MM–HH:MM"`
  - `note?: str`

## meta.json
- `run_timestamp: ISO8601`
- `environment: "local"|"cloud"`
- `rulebook_hash: str`
- `dataset_version: str`
- `run_hash?: str` (computed)
- `validated?: bool` (computed)
