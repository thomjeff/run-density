# Bug #287 — Flow: flow.json empty; UI shows 15 segments; CSV shows ~29

## Problem Recap

**Actual**: Flow page renders ~15 segments (derived from other sources).  
**Expected**: ~29 segments (per the run's flow CSV / bins).  
**Root cause**: `artifacts/.../ui/flow.json` was not written, so FE fell back to whatever it could infer (flags/geojson subset).

---

## Implementation Plan

### 1) Backend — write authoritative flow.json

**Goal**: Emit a complete per-segment time series of rate (p/s) for the entire active window, using canonical names.

#### Source of Truth
- Read from authoritative bins (same that drive the report): each bin has `segment_id`, `t_start`, `t_end`, `rate` (p/s).
- Do not derive from flags or tooltips.

#### Aggregation Shape
- One record per segment × bin with rate (p/s), no gaps (if a segment is inactive for a bin, omit the row).
- Include optional helpers for the FE (peak/avg/precomputed sparkline), but do not downsample without a flag.

#### File Path

```
artifacts/<run-date>/ui/flow.json
```

#### Schema (canonical)

```json
{
  "schema_version": "1.0.0",
  "units": { "rate": "persons_per_second", "time": "ISO8601" },
  "rows": [
    {
      "segment_id": "A1",
      "t_start": "2025-10-20T07:00:00Z",
      "t_end":   "2025-10-20T07:02:00Z",
      "rate": 2.26
    }
  ],
  "summaries": [
    {
      "segment_id": "A1",
      "bins": 400,
      "peak_rate": 2.26,
      "avg_rate": 0.48,
      "active_start": "2025-10-20T07:00:00Z",
      "active_end":   "2025-10-20T10:00:00Z"
    }
  ]
}
```

**Notes**:
- **Units**: use p/s (persons_per_second). If you also carry `rate_per_m_per_min` internally, do not emit it here (or emit under `_compat` for one release only).
- **Timestamps**: ISO 8601 with timezone (consistent with report).

#### Exporter Outline (Python)

```python
def export_flow_json(bins_df, out_path):
    # bins_df columns: segment_id, t_start, t_end, rate (p/s)  [authoritative]
    rows = [
        dict(segment_id=r.segment_id,
             t_start=r.t_start, t_end=r.t_end,
             rate=float(r.rate))
        for r in bins_df.itertuples(index=False)
        if r.rate is not None
    ]
    # summaries
    grp = bins_df.groupby("segment_id")
    summaries = []
    for seg, g in grp:
        if g.empty: continue
        summaries.append(dict(
            segment_id=seg,
            bins=int(len(g)),
            peak_rate=float(g["rate"].max()),
            avg_rate=float(g["rate"].mean()),
            active_start=str(g["t_start"].min()),
            active_end=str(g["t_end"].max()),
        ))
    payload = dict(
        schema_version="1.0.0",
        units=dict(rate="persons_per_second", time="ISO8601"),
        rows=rows,
        summaries=summaries,
    )
    out_path.write_text(json.dumps(payload, indent=2))
```

---

### 2) Frontend — deterministic behavior

- **Primary source**: load `flow.json`. Render:
  - segment list from `summaries.segment_id` (or `rows` unique ids);
  - charts/sparklines from `rows` filtered by `segment_id`.
- **Empty state**: if `flow.json` is missing or `rows=[]`, show:
  ```
  "No flow data available for this run."
  ```
  Do not infer from flags/geojson—avoid partial/incorrect lists.
- **Units**: label charts as p/s. (If later you add specific flow, label p/(m·s) distinctly.)

---

### 3) CI / contract checks

Add to your CI parity script or a companion check:

#### Presence & shape
- `artifacts/ui/flow.json` exists.
- `schema_version` present; `units.rate == "persons_per_second"`.

#### Coverage
- `rows` contains ≥ expected minimum (e.g., bins × segments > 0).
- `summaries` unique segment count ≥ 29 for this dataset (make threshold configurable).

#### Consistency (optional but recommended)
- If `segments.geojson` present: every `summaries.segment_id` exists in `features[].properties.segment_id`. (Don't require the reverse; some map segments may be non-flow.)
- If `Density.md` lists active window per segment, ensure `active_start`/`active_end` bracket the bin times.

#### Python snippet

```python
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]) / "artifacts" / "ui" / "flow.json"
j = json.loads(p.read_text(encoding="utf-8"))

assert j["units"]["rate"] == "persons_per_second", "Flow units must be p/s"
rows = j.get("rows", [])
summ = j.get("summaries", [])
assert isinstance(rows, list), "flow.json rows must be list"
assert isinstance(summ, list), "flow.json summaries must be list"
assert len(summ) >= 20, f"Unexpected low segment coverage: {len(summ)}"  # tune threshold
print(f"flow.json OK: segments={len({r['segment_id'] for r in summ})}, rows={len(rows)}")
```

---

## Acceptance Criteria (QA will verify)

- ✅ `flow.json` is populated with `rows` and `summaries`; no empty file.
- ✅ Segment coverage on Flow page ≈ 29 (matches the run's source).
- ✅ Charts render from `rows` (no gaps for active segments).
- ✅ Units displayed as p/s.
- ✅ Empty-state behavior shows a clear message when `flow.json` is absent (for legacy runs), and no inferred/partial lists appear.

---

## Test Plan

### Backend
- Golden fixture with 3 segments × 6 bins → `flow.json` `rows=18`; `summaries=3` with correct peaks/averages.
- Unit test validates JSON schema, units, and counts.

### Frontend
- Mock `flow.json` → assert segment list length equals `summaries.length`.
- Chart renders correct number of points for a chosen segment.
- Empty-state snapshot when `rows=[]`.

---

## Pitfalls to Avoid

- ❌ Re-deriving flow from flags (wrong source).
- ❌ Mixing units (p/min vs p/s).
- ❌ Downsampling without disclosure—if you downsample for charts, add `downsampled=true` and keep full `rows` in the file, or produce a separate `flow_downsampled.json`.

---

## Files to Modify

### Backend
- **Exporter**: `analytics/export_frontend_artifacts.py` (or equivalent) — add `write_flow_json(...)`.

### Frontend
- **Flow page**: selectors/components to read only from `flow.json` and implement the empty-state.

### CI
- Extend parity/contract script with the checks above.

---

## Definition of Done

- ✅ `flow.json` produced and non-empty for E2E runs.
- ✅ FE Flow page lists ~29 segments (matches dataset).
- ✅ Charts use p/s and look consistent with report timings.
- ✅ CI passes new flow checks.
- ✅ Empty-state message displays when `flow.json` is missing or empty.
- ✅ No inference from flags/geojson (deterministic behavior).

---

## Technical Notes

### Current State
- `flow.json` is not being generated by the artifact exporter
- Frontend falls back to inferring segments from other sources (flags.json, segments.geojson)
- This results in incomplete segment coverage (15 vs 29 expected)

### Proposed Architecture
- **Single Source of Truth**: `bins.parquet` (same source used for reports)
- **Canonical Format**: `flow.json` with `rows` (bin-level time series) and `summaries` (segment aggregates)
- **Units**: Standardized to persons per second (p/s)
- **Frontend**: Reads exclusively from `flow.json`, no fallback inference

### Data Flow
```
bins.parquet → export_flow_json() → flow.json → Frontend (Flow page)
```

