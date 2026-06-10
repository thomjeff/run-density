# Leg library, event recipes & corridor pairing (developer guide)

**Status:** Implemented (org-primary since #780/#783; corridor pairing since #785)
**Last updated:** 2026-06
**Epics/issues:** #755 (library), #780 (org-primary), #785 (corridor pairing), #786 (km drift — open)
**User guide:** [Race Configuration](../user-guide/race-configuration.md)

---

## Goal

Use a **map/GPX workflow** to produce analysis-ready config **without hand-editing** `segments.csv`, `flow.csv`, or `locations.csv` for each new year.

| Output | Role in analysis |
|--------|------------------|
| **segments.csv** | Multi-event rows — one row per leg occurrence; `full`/`half`/`10k` flags; per-event `*_from_km` / `*_to_km` for density |
| **flow.csv** | Event pairs on shared legs + corridor opposing-pass rows; uses *each event's* km windows |
| **locations.csv** | Points with per-event flags, `seg_id`, zones, resources, proxy timing |
| **`{event}.gpx`** | Per-event geometry stitched from recipe order |

---

## Data model

### Org leg library (primary)

- Legs live in `runflow/org/legs/` — one GPX per leg + `manifest.yaml` (id, file, `seg_label`, `start_label`/`end_label`, `width_m`, `schema`, `direction`, `flow_type`, `flow_notes`, `paired_with`, `locations[]`).
- New packages default to `leg_source: org` (`effective_leg_source` in `leg_library_resolver.py`); legacy packages with local legs stay package-scoped.
- Package manifests (`{package}/segment_library/manifest.yaml`) hold **recipes** and `flow_overrides`; legs come from the org manifest via `resolve_leg_library()` / `combined_manifest_for_apply()`.

### Event recipes

Ordered list of leg ids per event, stored in the **package** manifest:

```yaml
recipes:
  10k: ["01", "02", "04", "05", "06", "12"]
  half: ["01", "05", "08", "10", "11", "12"]
  full: ["01", "02", ..., "12"]
```

- The same leg may appear in multiple recipes (shared segments) and **multiple times in one recipe** (out-and-back over one leg → distinct `seg_id` per occurrence).
- Apply = stitch leg GPX in recipe order (endpoint tolerance `STITCH_TOLERANCE_M`), compute per-event cumulative kms, build `course.json` segments + locations, generate flow.

### Corridor pairing (#785)

`paired_with` on a leg declares that another leg covers the **same physical corridor in the opposite direction**.

- **Symmetric by construction:** `apply_leg_pairing()` (`app/core/config_package/legs.py`) sets/clears both sides and clears stale reciprocals. Wired into `update_package_leg` and `update_org_leg` when `paired_with` is in the update fields.
- **Self-pairing is implicit:** the same leg appearing twice in one recipe is treated as a corridor pair between the two occurrences (`leg_occurrence` in `flow_csv.py`).
- **Validation:** `validate_corridor_pairings()` (`app/core/course/segment_library.py`) emits warnings (dangling, asymmetric, unused-in-recipes, geometry-not-reversed) appended to stitch warnings at apply time.

---

## Flow generation

**Generator:** `build_flow_csv_from_segments()` in `app/core/course/flow_csv.py`.

1. **Cross-event pairs** on each shared segment (2+ events active): `overtake` rows with each event's own km window; unique `flow_id` per row.
2. **Corridor pairs** (`_corridor_pairs()`): for explicitly paired legs and self-paired occurrences, emit `counterflow,bi` rows for **all** event combinations across the two passes — including same-event (e.g. full outbound vs full return). Events not present on a pass are skipped.
3. Same-event rows with identical A/B km windows are never auto-generated; `flow_overrides` in the manifest still supported for exceptions.

**Pipeline:** `app/core/v2/flow.py` — `flow.csv` is authoritative; pairs must exist for requested events or analysis fails (#553).

---

## Leg ↔ course synchronization

Two copies of leg data exist: the leg manifest (authoring) and the package `course.json` (combined course, feeds exports). Sync rules:

| Direction | Mechanism | Triggers |
|-----------|-----------|----------|
| Leg → course | `merge_leg_locations_into_course()` + `sync_leg_metadata_into_course()` (`legs.py`) | Apply recipes; any package-leg update; **any org-leg update** fans out via `sync_org_leg_changes_into_packages()` (`org_leg_library.py`) to every org-sourced package with applied recipes |
| Course → leg | `sync_leg_location_metadata_from_course()` | Locations grid (operations editor) saves |

**Field ownership** during leg → course merge:

- **Leg-owned:** `lat`, `lon`, `placement` (`_LEG_OWNED_PLACEMENT_FIELDS`) — pin moves on the Legs tab always win; stale course copies never override them.
- **Course-owned (preserved):** crew-facing `id` (`loc_id`), resources, zone, notes, buffer, interval, contact, proxy settings, etc. (`_LEG_LOC_PRESERVE_FIELDS` minus placement). Identity is matched by `location_key` / `leg_loc_key`.

**Server-owned recipe kms:** `_preserve_recipe_segment_kms()` (`storage.py::save_config_course`) prevents stale client saves from overwriting recipe-applied per-event `from_km`/`to_km` and the `segment_library_applied` flag.

**UI note:** the Legs and Course tabs share one Leaflet map. Course-level location pins are removed while the Legs tab is active (`removeLocationPins` in `course_mapping.js`, called from `onLegsTabShown`) to avoid duplicate-pin confusion.

---

## Location projection tolerances

`app/utils/constants.py`:

| Constant | Default | Use |
|----------|---------|-----|
| `LOCATION_SNAP_THRESHOLD_M` | 50 | Max pin → segment-centerline distance for projection and for `find_nearest_segment` discovery |
| `LOCATION_SEGMENT_CLAMP_M` | 50 | Boundary pins projecting metres past a segment end are clamped into bounds instead of falling back to midpoint |

Known limitation: recipe-bookkept kms vs stitched-GPX traced distance drift up to ~110 m mid-course, which can still fail projection for pins at turn points — see **#786** for the planned reconciliation (record traced kms at export).

---

## Key modules

| Module | Use |
|--------|-----|
| `app/core/course/segment_library.py` | Load/stitch legs, build segments, corridor pairing validation, package export |
| `app/core/course/flow_csv.py` | Flow generation incl. corridor opposing-pass rows |
| `app/core/course/export.py` | `build_segments_csv`, per-event cumulative kms (uses stored recipe kms) |
| `app/core/config_package/legs.py` | Package leg CRUD, pairing, leg↔course sync, location merge |
| `app/core/config_package/org_leg_library.py` | Org leg CRUD, import/export, package fan-out sync |
| `app/core/config_package/leg_library_resolver.py` | Org vs package leg source resolution |
| `app/core/config_package/segment_recipes.py` | Recipe persistence, apply |
| `app/routes/api_config_packages.py` | REST endpoints (`/api/org/legs/*`, `/api/config/packages/{id}/segment-library/*`) |
| `frontend/static/js/map/segment_recipes.js` | Legs tab UI (leg editor, pairing dropdown, locations) |
| `frontend/static/js/map/course_mapping.js` | Course tab UI (recipes, segments/locations tables, pins) |

## Tests

```bash
pytest tests/unit/test_segment_library.py tests/unit/test_corridor_pairing.py \
       tests/unit/test_flow_csv.py tests/unit/test_leg_library_resolver.py \
       tests/unit/test_package_legs.py tests/unit/test_org_leg_library.py -q
```

Notable regression coverage:

- `test_corridor_pairing.py` — symmetric pairing, validation warnings
- `test_flow_csv.py` — paired/self-paired opposing-pass rows; unpaired output unchanged
- `test_leg_library_resolver.py` — org-primary resolution; org leg edits sync into applied packages without re-apply
- `test_config_package_course.py` — recipe kms protected from stale client saves
