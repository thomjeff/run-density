# Segment UI & CSV Alignment Proposal

**Context:** The Course Mapping segments table and `segments.csv` currently mix segment identity (route from pin A to pin B) with pin identity (boundary markers). This proposal cleans up the model and aligns the UI with the CSV.

---

## Current State

### Conceptual Mix
- **Segment** = the route between two boundaries (e.g. Start → Block 1, Block 1 → Block 2, Block 3 → Finish)
- **Segment pin** = a boundary marker placed by the user (Block 1, Block 2, Block 3)
- **Current confusion:** `seg_id` uses pin IDs (1, 2, 3) and "F" for the finish segment, so segment identity is conflated with pin identity

### UI Table (current)
| ID | Segment label | From (km) | To (km) | Length (km) |
|----|---------------|-----------|---------|-------------|
| 1  | Block 1       | 0         | 0.14    | 0.14        |
| 2  | Block 2       | 0.14      | 0.26    | 0.12        |
| 3  | Block 3       | 0.26      | 0.39    | 0.13        |
| F  | Block 4       | 0.39      | 0.51    | 0.12        |

- **ID** = end pin ID or "F" (finish) — mixes pin with segment
- **Segment label** = user label (often the end pin name)
- Missing: explicit pin boundaries (From pin / To pin), width, schema, direction

### segments.csv (current)
| seg_id | seg_label | pin_start_label | pin_end_label | width_m | schema | ... |
|--------|-----------|-----------------|---------------|---------|--------|-----|
| 1      | Block 1   | Start           | Block 1       | 3       | ...    |     |
| 2      | Block 2   | Block 1         | Block 2       | 3       | ...    |     |
| 3      | Block 3   | Block 2         | Block 3       | 3       | ...    |     |
| F      | Block 4   | Block 3         | Finish        | 3       | ...    |     |

- **seg_id** = pin ID or F — should identify the segment, not the end pin
- **pin_start_label** / **pin_end_label** correctly describe the route

---

## Proposed Model

### Semantics
- **Segment ID (S1, S2, S3, …)** = unique ID for each segment (route between two pins). Sequential, stable.
- **Pin** = boundary; has label (e.g. Block 1) and optional ID for reference. Start and Finish are virtual pins.
- **Segment** = route from pin A to pin B; has segment label, width, schema, direction, from_km, to_km, length.

### Seg ID Format
Use `S1`, `S2`, `S3`, `S4` (segment index) instead of pin IDs or "F". This:
- Clearly distinguishes segments from pins
- Avoids confusion with pin IDs (1, 2, 3)
- Works with the pipeline (seg_id is a string identifier)

---

## Proposed Changes

### 1. segments.csv
- **seg_id:** Use `S1`, `S2`, `S3`, … instead of `1`, `2`, `3`, `F`
- Keep: `seg_label`, `pin_start_label`, `pin_end_label`, `width_m`, `schema`, `direction`, event columns, from/to/km, length, description

### 2. UI Segments Table
Align columns with segments.csv:

| Seg ID | From pin | To pin | Segment label | Width (m) | From (km) | To (km) | Length (km) |
|--------|----------|--------|---------------|-----------|-----------|---------|-------------|
| S1     | Start    | Block 1| Block 1       | 3         | 0         | 0.14    | 0.14        |
| S2     | Block 1  | Block 2| Block 2       | 3         | 0.14      | 0.26    | 0.12        |
| S3     | Block 2  | Block 3| Block 3       | 3         | 0.26      | 0.39    | 0.13        |
| S4     | Block 3  | Finish | Block 4       | 3         | 0.39      | 0.51    | 0.12        |

- **Seg ID** = S1, S2, … (segment identity)
- **From pin / To pin** = boundary labels (same as `pin_start_label`, `pin_end_label` in CSV)
- **Segment label** = user-defined label for the segment
- **Width (m)** = from segment annotation
- **From/To/Length (km)** = route distance

### 3. Empty State / Help Text
- Update copy from "segment pins (A1, A2, ...)" to: "Segment pins split the course into segments. Each segment is the route between two pins (e.g. Start → Block 1)."

### 4. Implementation Checklist
- [x] `app/core/course/export.py`: Change `_segment_display_id()` to return `S1`, `S2`, … (1-based segment index)
- [x] `frontend/static/js/map/course_mapping.js`: Add `getPinLabelForIndex()`; update `renderSegmentsList()` to show Seg ID (S1…), From pin, To pin, Width; update segment annotation popup and info icon to show Seg ID
- [x] `frontend/templates/pages/course_mapping.html`: Update table header and empty state text
- [x] `flow.csv` uses same `_segment_display_id()` — accepts `S1`, `S2`, … as seg_id

---

## Notes
- Pin IDs (1, 2, 3) remain internal for segment_break_ids; they are no longer used as segment identifiers.
- The segment annotation popup (width, schema, direction, etc.) continues to edit segment properties; the table displays them.
- Schema/direction could be added as optional columns if useful; width is the most commonly needed.
