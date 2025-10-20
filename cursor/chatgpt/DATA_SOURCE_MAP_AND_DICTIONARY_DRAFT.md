# DATA_SOURCE_MAP_AND_DICTIONARY

**Draft from ChatGPT (Technical Architect)**  
**Date**: 2025-10-19  
**For Issue**: #281  
**Parent Issue**: #279 (RF-FE-002)

---

## Scope

Single source of truth (SSOT) for where each UI element gets its data, what each metric means, and how to validate parity from source → artifacts → API → UI.

**Baseline**: RF-FE-002 (Steps 1–8), artifacts from `artifacts/<run_id>/ui/` (QA-fixed 2025-10-19), v1.6.42 analytics.

**Environments**:
- **Local**: artifacts under repo `./artifacts/…`
- **Cloud Run**: artifacts under GCS bucket/prefix (via Storage adapter)

---

## 0) Directory & Config Map

```
/artifacts/latest.json                  → {"run_id": "YYYY-MM-DD", "ts": "<ISO-8601 UTC>"}
└── /artifacts/<run_id>/ui/
    ├── meta.json
    ├── segment_metrics.json
    ├── flags.json
    ├── flow.json
    └── segments.geojson

/reports/<run_id>/                      → Density.md, Flow.md/csv, bins.parquet, segment_windows_from_bins.parquet
/config/                                → density_rulebook.yml, reporting.yml
/data/                                  → runners.csv, segments.csv, <*.gpx>
```

**SSOT loaders**: `app/common/config.py`
- `load_rulebook()` → `density_rulebook.yml` (LOS thresholds)
- `load_reporting()` → `reporting.yml` (LOS colors, presentation config)

**Storage adapter**: `app/storage.py` (uses `artifacts/latest.json` → `<run_id>`)

---

## 1) API Endpoints (Implemented)

| Category | Endpoint | Purpose | Backing Files (artifacts/<run_id>/ui) |
|----------|----------|---------|---------------------------------------|
| **Dashboard** | `GET /api/dashboard/summary` | KPI tiles & banner (status, counts, peaks, cohorts) | `meta.json`, `segment_metrics.json`, `flags.json`, `flow.json`; also `/reports/<run_id>/bins.parquet` for `bins_flagged` |
| **Segments** | `GET /api/segments/geojson` | Map + table (joined geometry + metrics + flags) | `segments.geojson`, `segment_metrics.json`, `flags.json` |
| **Segments** | `GET /api/segments/summary` | Optional compact summary for dashboard | `segment_metrics.json`, `flags.json` |
| **Density** | `GET /api/density/segments` | Density table (per-segment density metrics) | `segment_metrics.json`, `flags.json` |
| **Density** | `GET /api/density/segment/{seg_id}` | Details for one segment | `segment_metrics.json`, `flags.json` |
| **Flow** | `GET /api/flow/segments` | Flow table (per-segment co-presence / overtaking) | `flow.json` |
| **Reports** | `GET /api/reports/list` | Report listing & links | `/reports/<run_id>/*` |
| **Reports** | `GET /api/reports/download` | File download | `/reports/<run_id>/*` |
| **Health** | `GET /api/health/data` | Data file presence and mtimes | checks artifacts + reports |

**Note**: `/api/density/heatmap` does not exist (future enhancement).  
**Note**: There is no `/api/flow/summary`; we use `/api/flow/segments`.

---

## 2) UI → Data Lineage (by page & element)

### A) Password
- No data binding.

### B) Dashboard (Landing)

**Endpoint**: `GET /api/dashboard/summary`

**Source lineage**:

| Tile / Field | Derived From | Transform |
|--------------|--------------|-----------|
| `total_runners` | `/data/runners.csv` | Count of rows; grouped by event for cohorts. |
| `cohorts ({event: {start, count}})` | `/data/runners.csv` | Group by event; start times from configured input (persisted with artifacts via meta.json if available). |
| `segments_total` | `segment_metrics.json` | Count of keys/records. |
| `segments_flagged` | `flags.json` | Count of unique `seg_id` flagged. |
| `bins_flagged` | `/reports/<run_id>/bins.parquet` | Count rows where `flag_severity != 'none'`. |
| `peak_density` | `segment_metrics.json` | `max(m.peak_density)` across segments. |
| `peak_density_los` | `density_rulebook.yml` | LOS classification for `peak_density` (rulebook thresholds). |
| `peak_rate` | `segment_metrics.json` | `max(m.peak_rate)` across segments. |
| `segments_overtaking` | `flow.json` | Count segments where `overtaking_a > 0 OR overtaking_b > 0`. |
| `segments_copresence` | `flow.json` | Count segments where `copresence_a > 0 OR copresence_b > 0`. |
| `status` | summary of above | `action_required` if any LOS E/F OR any flagged segment; else `normal`. |
| `warnings[]` | storage checks | List missing/invalid artifacts. |
| `provenance` | `meta.json` | timestamp, environment, run hash (if present). |

### C) Segments (Map + Table)

**Endpoint**: `GET /api/segments/geojson`

**Source lineage**:
- **Base geometry**: `segments.geojson` (FeatureCollection; properties: `seg_id`, `label`, `length_km`, `width_m`, `direction`, `events[]`)
- **Metrics join**: `segment_metrics.json` keyed by `seg_id` → adds `worst_los`, `peak_density`, `peak_rate`, `active_window` (e.g., "07:40–08:06")
- **Flags mark**: `flags.json` (array) → `is_flagged: true/false` per segment.

### D) Density

**Endpoint**:
- **Table**: `GET /api/density/segments`
- **Detail drawer**: `GET /api/density/segment/{seg_id}`

**Source lineage**: `segment_metrics.json` + `flags.json`

**Fields include**: `seg_id`, `label`, `schema`, `active_window`, `peak_density`, `los`, `peak_rate`, `utilization` (if provided), `flag_type`, `worst_bin` (if provided), `watch/mitigation` (if provided).

### E) Flow

**Endpoint**: `GET /api/flow/segments`

**Source lineage**: `flow.json` (already aggregated from Flow.csv by exporter)

**Fields**: `seg_id`, `event_a`, `event_b`, `flow_type`, `overtaking_a`, `overtaking_b`, `copresence_a`, `copresence_b`.

### F) Reports

**Endpoints**: `GET /api/reports/list`, `GET /api/reports/download`

**Source lineage**: `/reports/<run_id>/*`

### G) Health Check

**Endpoint**: `GET /api/health/data`

**Source lineage**: `Storage.exists()/mtime()` over both artifacts and reports paths.

---

## 3) Artifact Schemas (JSON/GeoJSON)

All artifacts live at: `/artifacts/<run_id>/ui/`

### 3.1 meta.json

```json
{
  "run_id": "2025-10-19",
  "run_timestamp": "2025-10-19T21:09:00Z",
  "environment": "local",
  "rulebook_hash": "…",              // optional
  "dataset_version": "…",            // optional (git SHA or tag)
  "notes": "optional"
}
```

- **Type**: object
- **Constraints**: `run_timestamp` must be ISO-8601 UTC (Z).

### 3.2 segments.geojson

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type":"Feature",
      "id":"A1",
      "properties":{
        "seg_id":"A1",
        "label":"Start to Queen/Regent",
        "length_km":0.9,
        "width_m":5.0,
        "direction":"uni",
        "events":["Full","10K","Half"]
      },
      "geometry": { "type":"LineString", "coordinates":[[lng,lat], ...] }
    }
  ]
}
```

- **Type**: GeoJSON FeatureCollection
- **Constraints**: `seg_id` unique; coordinates non-empty.

### 3.3 segment_metrics.json

```json
{
  "A1": {
    "seg_id": "A1",
    "schema": "start_corral",
    "active_window": "07:00–07:44",
    "peak_density": 0.755,
    "los": "D",
    "peak_rate": 2.26,
    "utilization": 0.23,
    "worst_bin": { "km": "0.2–0.4", "t": "07:42" }
  },
  "A2": { ... }
}
```

- **Type**: object keyed by `seg_id`
- **Constraints**: `los` in [A..F]; non-negative numbers.

### 3.4 flags.json

```json
[
  { "seg_id":"A1", "type":"density", "severity":"E", "reason":"utilization", "at":"07:42" },
  { "seg_id":"B2", "type":"density", "severity":"B", "reason":"peak_density" }
]
```

- **Type**: array
- **Constraints**: `severity` in [A..F]; `seg_id` present in metrics.

### 3.5 flow.json

```json
{
  "A1": { "seg_id":"A1", "overtaking_a": 14, "overtaking_b": 22, "copresence_a": 128, "copresence_b": 92 },
  "B2": { "...": "..." }
}
```

- **Type**: object keyed by `seg_id`
- **Semantics**: Aggregated from CSV (sum across event pairs per `seg_id`).

---

## 4) Metric Dictionary (definitions, units, rules)

| Field | Meaning | Units | Source | Rules / Notes |
|-------|---------|-------|--------|---------------|
| `total_runners` | Count of participants in analysis | persons | `/data/runners.csv` | Groupable by event; excludes DNS. |
| `cohorts[event].start` | Scheduled start time per event | HH:MM | `/data/runners.csv` / `meta.json` | Must match run config used for analysis. |
| `segments_total` | Count of segments with metrics | count | `segment_metrics.json` | Keys length. |
| `segments_flagged` | Segments with any flag | count | `flags.json` | Count distinct `seg_id`. |
| `bins_flagged` | Flagged bin count | count | `/reports/<run_id>/bins.parquet` | `flag_severity != 'none'`. |
| `peak_density` | Max density across all segments | persons / m² | `segment_metrics.json` | `max(peak_density)`; non-negative float. |
| `peak_density_los` | LOS at `peak_density` | A–F | `density_rulebook.yml` | Apply rulebook thresholds. |
| `peak_rate` | Max person flow rate | persons / sec | `segment_metrics.json` | `max(peak_rate)`; non-negative float. |
| `overtaking_a/b` | Overtakes between cohorts | events | `flow.json` | Aggregated sum per segment. |
| `copresence_a/b` | Co-presence magnitude | events | `flow.json` | Definition per analytics (count, not %). |
| `worst_los` | Worst LOS per segment | A–F | `segment_metrics.json` | Derived from bin analysis. |
| `active_window` | Time window segment is active | HH:MM–HH:MM | `segment_metrics.json` | Derived from bins coverage. |
| `utilization` | Time in LOS≥X (policy) | fraction (0–1) | `segment_metrics.json` | Calculation defined in analytics. |

**LOS thresholds**: `config/density_rulebook.yml`  
**LOS colors (UI)**: `config/reporting.yml`

---

## 5) Transform Rules (concise)

### LOS classification
Given a density `d`, find the band in `rulebook.globals.los_thresholds` where `min ≤ d < max` → return label A..F.

### Segments flagged
From `flags.json` array, `len(set(f.seg_id for f in flags))`.

### Bins flagged
From `bins.parquet`, count rows where `flag_severity != 'none'`.

### Peak metrics
- `peak_density = max(m.peak_density)` across `segment_metrics.json` values
- `peak_rate = max(m.peak_rate)` across `segment_metrics.json` values

### Overtaking / Co-presence segment counts
Count segments where `overtaking_a > 0 or overtaking_b > 0` (resp. `copresence_* > 0`) in `flow.json`.

### Segments geo join
For each feature by `seg_id`: merge `segment_metrics[seg_id]` + `is_flagged = seg_id in flags[].seg_id`.

---

## 6) Contract Tests (Cursor/QA)

These are data-path tests that compare API output (what the UI consumes) to the artifact source of truth (what analytics exported).

### 6.1 Dashboard parity

**Fetch**: `GET /api/dashboard/summary`

**Assert**:
- `total_runners == count rows in /data/runners.csv`
- `segments_total == len(keys in segment_metrics.json)`
- `segments_flagged == len(distinct seg_id in flags.json)`
- `bins_flagged == count from /reports/<run_id>/bins.parquet (flagged rows)`
- `peak_density == max(peak_density) from segment_metrics.json ± small epsilon`
- `peak_rate == max(peak_rate) from segment_metrics.json ± epsilon`
- `segments_overtaking == count segs in flow.json with any overtaking_* > 0`
- `segments_copresence == count segs in flow.json with any copresence_* > 0`
- `peak_density_los` matches rulebook classification of `peak_density`.

### 6.2 Segments geojson enrichment

**Fetch**: `GET /api/segments/geojson`

**Assert** per feature:
- `properties.seg_id` exists in `segment_metrics.json` keys
- `properties.worst_los`, `peak_density`, `peak_rate`, `active_window` equal the metric source
- `properties.is_flagged` equals (`seg_id` in `flags[].seg_id`)
- Count parity: `features` length == features in `segments.geojson`.

### 6.3 Flow table parity

**Fetch**: `GET /api/flow/segments`

**Assert**: For each `seg_id`: values in API equal `flow.json[seg_id]`.

### 6.4 Health / presence

**Fetch**: `GET /api/health/data`

**Assert**: required files exist for the current `run_id`. No false "missing" when files present.

**Implementation**: Cursor can implement these as `tests/test_contracts_*.py` and run in CI. These tests must not re-compute analytics; they only compare API output with artifact inputs.

---

## 7) Known Gaps / Future

- **No `/api/density/heatmap`**. Heatmaps currently pre-generated (PNG) or shown as placeholders; endpoint could stream image or return a URL reference.
- **No `/api/flow/summary`**. If needed, add it as an aggregate over `flow.json`.
- **`peak_rate` zeros** will remain if exporter/analytics doesn't compute them (fix upstream in analytics if required).
- **Schema versioning**: consider `meta.schema_version` to guard forward changes.

---

## 8) Acceptance Criteria (Data Parity)

A page is considered data-correct when:

1. **API == Artifact parity** holds for all fields listed in sections 2–5.
2. **No hardcoded values** for thresholds/colors; all from YAML SSOT.
3. **`warnings[]`** only includes true missing files.
4. **Local == Cloud parity** (same results for same artifact set).

---

## Appendix A — Minimal JSON Schemas (informal)

### segment_metrics.json (object keyed by seg_id)
**Required keys per entry**: `seg_id`, `peak_density` (>=0), `los` (A..F), `peak_rate` (>=0)

### flags.json (array)
**Each item**: `seg_id` (string), `type` (string), `severity` (A..F)

### flow.json (object keyed by seg_id)
**Each value**: `overtaking_a` (>=0), `overtaking_b` (>=0), `copresence_a` (>=0), `copresence_b` (>=0)

---

## Metadata

**Owner**: Technical Architect (ChatGPT)  
**Contributors**: Product (Jeff), Developer (Cursor)  
**Last Updated**: 2025-10-19

---

## Optional: Starter Contract Test

ChatGPT can also generate a starter `tests/test_contracts_dashboard.py` that implements the parity checks above using your active endpoints and the storage adapter paths.

