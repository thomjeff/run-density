# Race Configuration User Guide (Leg-Based Workflow)

**Audience:** Race organizers, course mappers, and operational staff
**Last updated:** 2026-06

This guide covers the **Race Configuration** page — the recommended way to build analysis-ready config packages from reusable GPX **legs**. For the legacy draw-the-line workflow, see [Course Mapping](course-mapping.md).

---

## Overview

Instead of drawing one long course line, you build a course from **legs**: short GPX sections (e.g. "Bridge at Mill → Half Turn") stored in your **organization leg library**. Each event (Full, Half, 10K) gets a **recipe** — an ordered list of legs. Applying recipes builds the combined course and generates **segments.csv**, **flow.csv**, **locations.csv**, and per-event **GPX** automatically. No hand-editing of CSVs.

**Key benefits:**

- Legs are reusable across years and packages — fix a leg once, every package that uses it benefits.
- Out-and-back sections become two explicit directional legs, so flow analysis can model opposing traffic correctly (see [Corridor pairing](#corridor-pairing)).
- Locations (water stops, officials, aid) live **on legs**, so they come along automatically when a leg is used.

---

## Where to find it

Open **Race Configuration** from the main menu and select (or create) a config package. The workspace has three tabs:

| Tab | Purpose |
|-----|---------|
| **Legs** | Manage the organization leg library, edit leg metadata, place locations on legs |
| **Course** | Event recipes, combined course preview, segments and locations tables, apply + export |
| **Runners** | Install actual race-result runner files; baseline scenario generation |

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

## The Legs tab

### Leg map

Pan and zoom to filter the legs table below the map. Select a leg in the table to highlight its route (purple line). Toolbar actions:

| Action | What it does |
|--------|--------------|
| **Trim route** | Drag the start or end of the selected leg along its route |
| **Reshape route** | Simplify the route, then drag yellow anchors to nudge it |
| **Add Locations** | Click the map to place location pins on the selected leg |

### Organization leg library

Legs live in the **organization library** (`runflow/org/legs/`), outside any single package, so they are shared across packages.

| Button | What it does |
|--------|--------------|
| **Import legs…** | Import third-party GPX files (e.g. from a route planner) as new legs |
| **Leg library…** | Browse all org legs, including ones not used by this package |
| **Export legs…** | Download all legs (GPX + metadata + locations per leg) |

The legs table shows each leg's ID, label, endpoints, length, width, schema, direction, flow type, **Pair** (corridor pairing partner), and location count. Use the **edit** action to open the leg editor.

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

The simple rules:

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

When recipes are applied, the flow generator emits **opposing-pass flow rows** (`counterflow`, `bi`) for every event combination that crosses the paired corridor — including **same-event** pairs (e.g. Full outbound km 25.1–27.7 vs Full return km 33.8–36.4). These restore the high-value overlap insight that previously required hand-crafted flow rows (out/back corridors, late chase overlaps).

Same-direction `overtake` rows on each individual leg are still generated as usual; pairing **adds** the cross-corridor rows, it doesn't replace anything.

### Self-pairing (automatic)

If the **same leg appears twice in one recipe** (e.g. a single bidirectional connector used out and back), the system treats the two occurrences as an implicit corridor pair — no configuration needed.

### Pairing validation

When recipes are applied, the system warns (without blocking) if:

- a leg's pair references a leg that doesn't exist (**dangling**),
- pairing isn't symmetric (e.g. edited by hand),
- a paired leg is not used in any recipe (the pair is inert),
- the two legs' geometries don't look like reversed passes of the same corridor.

---

## Locations on legs

Place pins on the **Legs tab** with **Add Locations** (select a leg first). Location types:

| Type | Snaps to route? | Typical use |
|------|------------------|-------------|
| **course** | Yes | Timed checkpoints |
| **water** | Yes | Water stops |
| **official** | Yes | Turnarounds, officials |
| **aid** | No | Aid stations beside the course |
| **traffic** | No | Traffic control points |
| **extract** | No | Extraction points |

**The Legs tab owns pin positions.** Dragging a pin on the Legs tab is saved immediately and synced into the package course automatically — no re-apply needed. Operational details (zones, resources, notes, proxy timing) are edited at the **course level** (Locations table → **Edit operations…**) and survive re-applies.

**Proxy locations:** off-course locations can take their timing from an on-course **proxy** location. The proxy dropdown only offers locations that have their own timing (you cannot chain a proxy to another proxied location).

---

## The Course tab

1. **Edit event recipes** — set the ordered list of legs per event. The same leg can appear in multiple recipes (shared segments) and twice in one recipe (out-and-back over the same leg).
2. **Apply recipes** — builds the combined course: segments with per-event `from_km`/`to_km`, locations (synced from legs), and generated flow pairs. Review any stitch or pairing warnings shown after apply.
3. Review the **Segments** and **Locations (combined course)** tables. Location **ID** is the stable crew-facing `loc_id`; **Key** keeps identity across re-applies.
4. **Export package** — writes `segments.csv`, `flow.csv`, `locations.csv`, and per-event GPX to the package folder, ready for analysis.

> **Note:** per-event segment kilometres are **server-owned** once recipes are applied. They are recomputed from recipes on each apply and protected against accidental overwrites from stale browser tabs.

---

## What gets exported

| File | Contents |
|------|----------|
| **segments.csv** | One row per leg occurrence with event flags and per-event `from_km`/`to_km` |
| **flow.csv** | Cross-event `overtake` rows on shared legs + `counterflow` rows for corridor pairs |
| **locations.csv** | All locations with per-event flags, `seg_id`, zones, resources, proxy timing |
| **`{event}.gpx`** | Per-event course geometry stitched from that event's recipe |

---

## Common issues

**"I see two pins for the same location."**
Course-level pin copies are hidden on the Legs tab; if you still see duplicates after editing, refresh the page. Pin positions are owned by the leg — the course copy follows automatically.

**"Should an out-and-back leg be counterflow/bi?"**
No — keep each directional leg `overtake`/`uni` (or as its same-direction interaction warrants) and **pair** the two legs. The system generates the counterflow rows from the pairing.

**"My paired legs produce no counterflow rows."**
Both legs must appear in at least one recipe of events being analyzed, and the events' passes must overlap in time. Check the apply warnings for inert pairings.

**"A location at a turnaround gets odd first/last runner times."**
Turn-point pins sit at segment boundaries and can be affected by small distance bookkeeping differences (see issue #786). Keep the pin physically accurate; do not nudge it to compensate.
