# Required Fields and Fallbacks (Issue 712)

This note summarizes the required fields and known fallbacks for the three CSV
inputs used by the v2 pipeline. It is intended to support editing the
`*_712.csv` working files while testing which columns are actually required.

## flow.csv

Required (validated):
- `seg_id`
- `event_a`
- `event_b`
- `from_km_a`
- `to_km_a`
- `from_km_b`
- `to_km_b`
- `direction`

Required (structural):
- At least one data row (empty file is rejected).

Fallbacks:
- `flow_type`: if missing/unknown, terminology defaults to "overtake". This
  changes labels in reports/UI but not the underlying flow calculations.
- `seg_label`: if missing, becomes an empty label (display only).

## segments.csv

Required (validated):
- `seg_id`
- `seg_label`
- `schema`
- `width_m` (must be numeric and > 0)
- `direction` (must be non-empty)
- For each event in the run config:
  - `{event}_from_km`
  - `{event}_to_km`

Fallbacks:
- `seg_label`: if missing in some lookups, the label falls back to `seg_id`.
  This affects display only.
- Event spans: if `{event}_from_km`/`{event}_to_km` are missing and validation is
  bypassed, the flow conversion falls back to `(0, 0)`, which effectively
  removes that event's usage in flow calculations and changes results.

## locations.csv

Required (validated):
- File existence only (no column validation in v2).

Required for meaningful results (runtime behavior):
- `lat`, `lon`: missing coordinates skip the location.
- Event flags (`full`, `half`, `10k`, `elite`, `open`): if none are `y`, the
  location is skipped.

Fallbacks:
- `seg_id`: if missing, the system projects onto the course and then finds the
  nearest segment. This can change arrival times, especially for multi-crossing
  locations.
- `buffer`: missing/NaN defaults to `0` minutes (affects `loc_end` and duration).
- `interval`: missing/NaN defaults to `5` minutes (affects `loc_end` rounding).
- `loc_direction`: missing defaults to empty string (display only).
- `timing_source`: missing defaults to `"modeled"`. If set to `proxy:n`, timing
  values are copied from another location, which changes results for that row.
