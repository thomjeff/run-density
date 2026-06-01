# Segment library & event recipes (2027 planning)

**Status:** Prototype in `app/core/course/segment_library.py`  
**Reference data:** `cursor/plotaroute/` (PlotARoute chunks + combined `00_*.gpx`)  
**Epic:** #755 · Related: #767 (planner), #759 (flow review)

---

## Goal

Use a **map/GPX workflow** to produce analysis-ready config **without hand-editing** `segments.csv`, `flow.csv`, or `locations.csv` for each new year (e.g. 2027).

| Output | Role in analysis |
|--------|------------------|
| **segments.csv** | **Multi-event rows** — one row per *shared* course chunk; `full`/`half`/`10k` flags; per-event `*_from_km` / `*_to_km` for density |
| **flow.csv** | **Event pairs** on shared chunks; uses *each event’s* km on that chunk (can differ on same `seg_id` in advanced cases) |
| **locations.csv** | Points with **per-event** flags and km; first/last runner times pool arrivals across all flagged events |
| **`{event}.gpx`** | Per-event geometry for GPX projection and location distance |

---

## Model (PlotARoute-aligned)

### 1. Segment library

- Each file `01_start_friel.gpx`, `02_friel_10kturn.gpx`, … is one **chunk**.
- Chunks stitch end-to-end (endpoint tolerance ~80 m).
- Metadata in `cursor/plotaroute/manifest.yaml`: `seg_id`, `seg_label`, width, schema, direction.

### 2. Event recipes

Ordered list of chunk ids per event:

```yaml
recipes:
  10k: [01, 02, 04, 05, 06, 12]
  half: [01, 05, 08, 10, 11, 12]
  full: [01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12]
```

- **Combine** = concatenate chunk GPX (same idea as PlotARoute “Combine Route”).
- Verify `recipe_lengths_km` against `00_{event}.gpx` after edits.

### 3. Export `segments.csv` (multi-event — required)

**One row per chunk**, not per event:

| Column | Source |
|--------|--------|
| `seg_id`, `seg_label`, … | Chunk metadata |
| `full`, `half`, `10k`, … | `y` if chunk appears in that event’s recipe |
| `full_from_km`, `full_to_km`, … | Cumulative distance along **that event’s recipe only** |
| `0` / `n` | Events that skip the chunk |

This matches **2026_final** (e.g. A1 used by Full+Half+10K with aligned early km; B1 Full+10K only with `half` = n).

Density (`get_shared_segments`, bins) uses these flags — **shared segments must stay on one row**.

### 4. Export `flow.csv` (re-planned)

**Generator:** `build_flow_csv_from_segments()` in `segment_library.py`.

For each segment row where **2+ events** are active:

- Emit rows for event pairs `(A, B)` (and same-event pairs where needed, e.g. 10k/10k on B3-style legs).
- `from_km_a` / `to_km_a` = segment’s `{event_a}_from_km` / `{event_a}_to_km`.
- `from_km_b` / `to_km_b` = same for event B.
- Default `flow_type`: `overtake`; overrides in manifest `flow_overrides` or future UI.

**Not** the old stub in `build_flow_csv()` (one row per segment, same event A/B).

**Pipeline:** `app/core/v2/flow.py` — `flow.csv` is authoritative; pairs must exist for requested events or analysis fails (#553).

**Follow-up (#759):** Review grid for exceptions (e.g. 2026 `B1a` — same `seg_label`, different km windows for late overlaps). Auto-generate baseline; human adds override rows.

### 5. Locations (re-planned)

Locations are **like segments + flow**: multi-event, analysis uses **all** eligible events at a point.

**Current analysis** (`app/location_report.py`):

1. Read `locations.csv` flags (`full`, `half`, `10k`, …).
2. For each eligible event, compute arrival times from:
   - Listed `seg_id`(s) on the location, **or**
   - Nearest segment + GPX projection using `{event}.gpx`.
3. Uses `{event}_from_km` / distance on segment for `pace × distance + start`.
4. **`first_runner` / `last_runner`** = min/max over **combined** arrival list across events (cross-event staffing window).

**Planned authoring (no hand km):**

| Step | Action |
|------|--------|
| 1 | Place location on map (or import lat/lon). |
| 2 | System projects point onto each **recipe-built** `{event}.gpx` → event km at location. |
| 3 | Set event flags from segment membership (suggest API exists: `suggest_location_events`). |
| 4 | Export `locations.csv` with `full_from_km`, `half_from_km`, `10k_from_km`, … |

**Dependency:** Per-event GPX from recipes must exist before location export (same as analysis).

**Not** tied to single `course.json` LineString.

---

## What’s implemented now

```bash
# In repo root (Docker or venv with app deps):
python3 -c "
from pathlib import Path
from app.core.course.segment_library import export_library_to_course, write_package_exports
b = export_library_to_course(Path('cursor/plotaroute'))
print('10k km', b['recipe_lengths_km'])
print('flow rows', b['flow_csv'].count(chr(10)))
write_package_exports(Path('/tmp/fm_plotaroute_test'), Path('cursor/plotaroute'))
"
```

```bash
pytest tests/unit/test_segment_library.py -q
```

Files:

- `cursor/plotaroute/manifest.yaml` — chunks + recipes (edit recipes here)
- `app/core/course/segment_library.py` — load, stitch, segments, flow, package write
- `tests/unit/test_segment_library.py`

---

## UI roadmap (after library API stable)

| Tab | Purpose |
|-----|---------|
| **Library** | Import GPX chunks; endpoint validation |
| **Recipes** | Order chunks per event; length vs `00_*` check |
| **Segments & flow** | Preview tables; export |
| **Locations** | Pins + auto km + event flags |
| **Publish** | Write package + `analyze_ready` |

Deprecate single-line-only planner as **primary** 2027 path; keep for simple races.

---

## Open issues

1. **Full recipe tuning** — manifest `full` recipe ~40–44 km; validate against `00_full.gpx` (41.76 km).
2. **Flow exceptions** — `B1a`-style rows need override UI or manifest entries.
3. **Package API** — `POST /api/config/packages/{id}/import-library` (not wired yet).
4. **#767** — Align waypoint planner with chunk ids instead of vertex indices.

---

## Related code

| Module | Use |
|--------|-----|
| `app/core/course/export.py` | `build_segments_csv`, `_event_cumulative_distances` |
| `app/core/v2/flow.py` | Consumes `flow.csv` + `segments.csv` |
| `app/location_report.py` | Consumes `locations.csv` + GPX + segments |
| `app/core/config_package/storage.py` | `package_readiness` needs all three CSVs |
