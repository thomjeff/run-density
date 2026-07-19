# Race Configuration User Guide (Legs → Courses → Packages)

**Audience:** Race organizers, course mappers, and operational staff
**Last updated:** 2026-07

This guide covers the **Race Configuration** hub — the recommended way to build analysis-ready race packages from reusable GPX **legs** and named **courses**. For the legacy draw-the-line workflow, see [Course Mapping](course-mapping.md).

---

## Overview

```text
GLOBAL
├── Legs     → edit routes & locations only here
└── Courses  → named frozen snapshots per distance

RACE CONFIGURATION (package)
├── Assign one global course per distance (full / half / 10k)
├── Runners
└── Build race exports → package-root multi-distance CSVs/GPX for v2 analyze
```

- **Legs** are short GPX sections (e.g. "Bridge at Mill → Half Turn") in `runflow/org/legs/`. They are shared across all race configurations.
- **Courses** are named frozen snapshots for one distance (e.g. **10K University**, **10K River Trail**) in `runflow/org/courses/{id}/`. Saving a course copies the legs used at that moment; later org leg edits do not change already-saved courses.
- **Race configurations (packages)** assign one course per distance and build multi-distance exports at `runflow/config/{config_id}/` for analysis.

**Key benefits:**

- Legs are reusable across years and packages — fix a leg once, then save a new course snapshot when you want packages to pick up the change.
- Multiple variants of the same distance (two different 10Ks) are first-class courses, not package overrides.
- Out-and-back sections become two explicit directional legs, so flow analysis can model opposing traffic correctly (see [Corridor pairing](#corridor-pairing)).
- Locations (water stops, officials, aid) live **on legs**, so they come along when a course snapshots those legs.

---

## Where to find it

Open **Race Configuration** from the main menu. The hub has three top-level views:

| View | Purpose |
|------|---------|
| **Packages** | Create/open race packages; assign courses and runners |
| **Legs** | Organization leg library — import/draw routes, edit metadata, place locations |
| **Courses** | Create and manage named frozen courses by distance (**New course**) |

Inside a package, the workspace has two tabs:

| Tab | Purpose |
|-----|---------|
| **Courses** | Assign one global course per distance; **Build race exports** |
| **Runners** | Install actual race-result runner files; baseline scenario generation |

---

## Recommended workflow (two 10Ks + multi-distance)

1. **Legs** — Import or draw shared route pieces; place locations.
2. **Courses** → **Save course…** — Compose **10K University** (order legs 1…n for the University route). Save again as **10K River Trail** with a different leg order.
3. Save **Full** and **Half** courses the same way (each distance can have many named courses).
4. Open a **race configuration** → **Courses** tab — assign Full / Half / 10K (pick University or River Trail for 10K).
5. **Build race exports** — writes combined `segments.csv`, `flow.csv`, `locations.csv`, and `{event}.gpx` at the package root.
6. Analyze with `data_dir` pointing at `runflow/config/{config_id}` (all distances together), or at a single course folder for one-distance runs.

---

## Legs (global)

### Leg map

Pan and zoom to filter the legs table below the map. Select a leg in the table to highlight its route (purple line). Toolbar actions:

| Action | What it does |
|--------|--------------|
| **Trim route** | Drag the start or end of the selected leg along its route to **shorten** it |
| **Extend route** | Click the map to **lengthen** the leg at the start or end (snap to roads/trails) |
| **Reshape route** | Simplify the route, drag yellow anchors to nudge it, and click the purple line between pins to add more anchors |
| **Add Locations** | Click the map to place location pins on the selected leg |

### Organization leg library

Legs live in `runflow/org/legs/`, outside any single package.

| Button | What it does |
|--------|--------------|
| **Import legs…** | Import third-party GPX files (e.g. from a route planner) as new legs |
| **Draw leg on map** | Click along roads/trails to create a new leg |
| **Export legs…** | (Package context) Download all legs (GPX + metadata + locations) |

The legs table shows each leg's ID, label, endpoints, length, width, schema, direction, flow type, **Pair** (corridor pairing partner), and location count. Use the **edit** action to open the leg editor.

### Package resources

Each config package defines which **resource types** can be scheduled at locations (default: FPF, YSSR, AWP, VOL). Add custom types such as **Officials (`ofc`)** when creating or editing a configuration, or via **Manage resources** on the package Locations card after you open a package.

### Leg editor fields

| Field | Meaning |
|-------|---------|
| **Label / Start / End** | Names used in segment labels and endpoint matching |
| **Width (m)** | Usable course width for density (e.g. 1.5 for a trail lane, 3.0 for a full trail) |
| **Schema** | Density LOS schema for the leg |
| **Direction** | `uni` (one direction of travel) or `bi` (two-way traffic on the leg itself) |
| **Flow type** | Default interaction type: `overtake`, `counterflow`, `merge`, or `none` |
| **Paired leg** | The leg covering the **same physical corridor in the opposite direction** (see below) |

### Choosing direction and flow type

- **direction** answers: do the streams on this leg move the same way or opposite ways?
- **flow type** answers: what kind of interaction risk is this?

| Situation | flow type | direction |
|-----------|-----------|-----------|
| Events share the leg moving the **same way** (catching/passing) | `overtake` | `uni` |
| Streams physically **meet head-on** on this one leg | `counterflow` | `bi` |
| One stream **joins** another | `merge` | `uni` |
| Keep the leg but don't analyze interaction risk | `none` | per geometry |

> **Out-and-back corridors:** do *not* mark a single directional leg `bi` just because the trail carries traffic both ways at different km. Instead split it into two directional legs and **pair** them.

---

## Corridor pairing

When a course goes out and back along the same physical trail, you have two legs — e.g. leg 03 "Bridge at Mill → Half Turn" and leg 10 "Half Turn → Bridge at Mill". Each is one direction of travel, but runners on both occupy the **same physical space** at the same time. Corridor pairing tells the system about that relationship.

### How to pair

1. Open the **leg editor** for either leg.
2. Set **Paired leg (same corridor, opposite direction)** to the partner leg.
3. Save. Pairing is **symmetric** — the partner leg is updated automatically, and the **Pair** column shows the link on both rows.

To unpair, clear the dropdown on either leg.

### What pairing generates

When a course is saved (or race exports are built), the flow generator emits **opposing-pass flow rows** (`counterflow`, `bi`) for every event combination that crosses the paired corridor — including **same-event** pairs. Same-direction `overtake` rows on each individual leg are still generated as usual; pairing **adds** the cross-corridor rows.

### Self-pairing (automatic)

If the **same leg appears twice in one recipe** (e.g. a single bidirectional connector used out and back), the system treats the two occurrences as an implicit corridor pair — no configuration needed.

---

## Locations on legs

Place pins on **Legs** with **Add Locations** (select a leg first). Location types:

| Type | Snaps to route? | Typical use |
|------|------------------|-------------|
| **course** | Yes | Timed checkpoints |
| **water** | Yes | Water stops |
| **official** | Yes | Turnarounds, officials |
| **aid** | No | Aid stations beside the course |
| **traffic** | No | Traffic control points |
| **extract** | No | Extraction points |

**Legs own pin positions.** Dragging a pin on Legs is saved on the org leg. When you save a Course, locations on those legs are snapshotted into the course folder.

---

## Courses (global)

Open the hub **Courses** view → **Save course…**

1. Enter a **name** (e.g. 10K University) and **distance** (full / half / 10k).
2. Set **order numbers** (1, 2, 3…) for legs in that course. The same leg can appear more than once (comma-separated slots).
3. **Save course snapshot** — writes under `runflow/org/courses/{course_id}/`:
   - `leg_library/` (frozen GPX copies)
   - `segments.csv`, `flow.csv`, `locations.csv`, `{distance}.gpx`
   - `saved_course.json` metadata

Run single-distance v2 analysis with `data_dir` pointing at that folder, for example:

```json
{
  "data_dir": "runflow/org/courses/10k-university",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [{
    "name": "10k",
    "runners_file": "10k_runners.csv",
    "gpx_file": "10k.gpx"
  }]
}
```

Copy or symlink runner CSVs into the course folder (or use a package build for multi-distance analysis with runners already installed on the package).

---

## Package: Assign courses + Build race exports

1. Open a race configuration → **Courses** tab.
2. For each package event (Full / Half / 10K), select one global course.
3. **Save assignments**, then **Build race exports**.

That merges the assigned course leg snapshots and recipes into package-root files ready for multi-distance analysis:

| File | Contents |
|------|----------|
| **segments.csv** | One row per leg occurrence with event flags and per-event `from_km`/`to_km` |
| **flow.csv** | Cross-event `overtake` rows on shared legs + `counterflow` rows for corridor pairs |
| **locations.csv** | All locations with per-event flags, `seg_id`, zones, resources, proxy timing |
| **`{event}.gpx`** | Per-event course geometry stitched from that event's recipe |

Analyze with `data_dir`: `runflow/config/{config_id}`.

> **Legacy:** **Edit event recipes** remains available for advanced overrides; prefer Assign courses + Build race exports for the normal path.

---

## Runners tab — actual race results

After a race, import **chip-timed** finisher data as `{event}_runners.csv` files for analysis (post-race review, calibration, etc.). This is separate from **Calculate Baseline → Create New Files**, which generates synthetic scenario files.

### Recommended workflow

1. Export results from Race Roster as an Excel workbook (one sheet per event).
2. Run the conversion script (once per results file). From the repo root, either use a local Python env with `requirements.txt` installed, or the dev container (`make dev`):

   ```bash
   python scripts/build_raceroster_runner_csvs.py \
     --xlsx "/path/to/FM2026 Results.xlsx" \
     --out-dir /tmp/fm2026-runners \
     --events 10k,half,full
   ```

   ```bash
   docker exec run-density-dev python scripts/build_raceroster_runner_csvs.py \
     --xlsx "/app/cursor/FM2026 Results.xlsx" \
     --out-dir /app/cursor \
     --events 10k,half,full
   ```

   Omit `--events` to export all default sheets (5K Elite, 5K Open, 10K, Half, Full). Use `--list-sheets` to see mappings.

3. Open **Race Configuration** for your package → **Runners** tab → **Install runner files** → **Upload CSV files**. Select the generated `*_runners.csv` files.

### Chip-only rule

Only finishers with both **Gun Time** and **Chip Time** are included. Rows with no chip time are skipped (pace and start_offset cannot be computed from gun time alone).

| Output column | Source |
|---------------|--------|
| `runner_id` | Bib number (`No.`) |
| `pace` | Chip finish time ÷ distance (min/km) |
| `start_offset` | Gun time − chip time (seconds), minimum 0 |
| `distance` | Fixed per event (5, 10, 21.1, or 42.2 km) |

Requires `openpyxl` (`pip install openpyxl` or use the project `requirements.txt`).

---

## Common issues

**"Editing a leg changed my race analysis."**
Org leg edits affect the live library. Already-saved Courses keep their snapshotted legs until you save a new course (or rebuild after re-assigning an updated course).

**"I need two different 10K routes."**
Save two courses with distance `10k` and different names/recipes. Assign the one you want on the package Courses tab.

**"Should an out-and-back leg be counterflow/bi?"**
No — keep each directional leg `overtake`/`uni` (or as its same-direction interaction warrants) and **pair** the two legs. The system generates the counterflow rows from the pairing.

**"My paired legs produce no counterflow rows."**
Both legs must appear in at least one recipe of events being analyzed, and the events' passes must overlap in time.

**"A location at a turnaround gets odd first/last runner times."**
Turn-point pins sit at segment boundaries and can be affected by small distance bookkeeping differences (see issue #786). Keep the pin physically accurate; do not nudge it to compensate.
