# Course Mapping User Guide

**Audience:** Race organizers, course mappers, and operational staff  
**Last updated:** 2026-02

---

## Overview

Course Mapping lets you define a single course geometry (route) that supports **multiple events** (e.g. Full Marathon, Half, 10K) with **shared segments** and clear **splits** at intersections. You draw the route, place pins at key points, and assign which events use which legs. The system then exports **segments.csv**, **flow.csv**, **locations.csv**, and **GPX** for use in density and flow analysis.

**You will:**
- Draw or edit the course line (with optional snap-to-road).
- Add **segment pins** at Start, Finish, and every place where the route splits or changes (e.g. Friel, 10K Turn, Station at Barker).
- Use **Flow control** at pins where the route splits to say which events take which outgoing leg.
- Optionally edit segment labels and events in the **Segments** table.
- **Save** the course and **Export** for the analysis pipeline.

---

## Where to find it

Open **Course Mapping** from the app navigation (e.g. **Course Mapping** under the main menu). Select a course from the table or create a **New course**. Use **Edit** to switch from view-only to editing (draw line, add pins, flow control).

---

## Key concepts

| Concept | What it means |
|--------|----------------|
| **Course line** | One ordered path (the green dashed line on the map). It can include out-and-backs and forks by drawing in a specific order and using **Extend from here** and **Same Route Back**. |
| **Segment pins** | Boundaries between segments. They mark “segment from previous pin to this pin.” Add pins at Start, Finish, and every **intersection** (e.g. Friel, 10K Turn, Station at Barker). |
| **Segments** | Automatically derived from pins: Segment 1 = Start → first pin, Segment 2 = first pin → second pin, etc. Each segment has **events** (Full, Half, 10K) that indicate which events run that stretch. |
| **Flow control** | At a pin where the route **splits**, you define which event(s) take which **outgoing leg**. That sets which events use each segment so export and analysis are correct. |
| **Extend from here** | From a pin, draw a **new leg** (e.g. Half-only to Station at Barker). The main line continues from that pin; you are adding a fork. |
| **Same Route Back** | After drawing an outbound leg, adds a **return leg** that retraces back to a **rejoin point**. You choose the rejoin point (e.g. “Friel”) so the path returns to the correct place before continuing. |

---

## Basic workflow

### 1. Draw the path (order matters)

1. **New course** or **Edit** an existing one. Turn on **Draw Line** and **Snap to Road** if desired.
2. Draw the **first shared part** (e.g. Start → Friel). Add a **segment pin** at Friel: **Add Segment Pin** → click on the green line at Friel → set label (e.g. “Friel”).
3. **Fork for Full/10K:** Click the **Friel** pin → **Extend from here** → draw to **10K Turn**. Add a segment pin at the 10K turn (e.g. “10K Turn”).
4. **10K return:** Click **Same Route Back** → set **Rejoin at:** to “Friel” → **Confirm**. You now have Start → Friel → 10K Turn → back to Friel.
5. **Continue to finish:** From the same Friel point, draw the next leg: Friel → Station at Barker → … → Finish. Add segment pins where needed (e.g. “Station at Barker”, “Finish”).
6. Add any segment pins you missed and label them clearly.

**Important:** To get “Friel → 10K Turn” and “10K Turn → Friel” as **separate segments**, you need **segment pins in three places**: (1) the first Friel (where the path leaves toward 10K Turn), (2) the 10K Turn (apex), and (3) the return Friel (where the path continues to finish). Without a pin at the first Friel and at 10K Turn, the out-and-back is hidden inside one segment.

### 2. Assign who goes where (Flow control)

At every pin where the route **splits**:

1. Click that **pin** on the map.
2. Click **Flow control**.
3. For each “Leg to: &lt;label&gt;”, **check only the events** that take that leg (e.g. “Leg to: 10K Turn” → Full, 10K; “Leg to: Station at Barker” → Half).
4. Click **Save**.

Repeat for every split pin.

### 3. Per-segment events (if needed)

- **Flow control** at a pin sets events for the segments that **start** at that pin.
- For segments that do **not** start at a flow-control pin (e.g. the first segment Start → Friel), set events in the **Segments** table (e.g. Full, Half, 10K).

### 4. Save and export

Click **Save** to persist the course. Use **Export** (e.g. “to folder”) to generate **segments.csv**, **flow.csv**, **locations.csv**, and **course.gpx** for the pipeline.

---

## Segments table and Segment pins table

- **Segments table:** Lists each segment with ID, From pin, To pin, Segment label, Events, and **per-event distances** (Full, Half, 10K, Elite, Open). Each event column shows the distance range (e.g. 0.00–2.72 or 0 if that event does not use the segment). **Click a row** to zoom the map to that segment. You can edit a segment (label, events, etc.) by clicking its **ID**.
- **Segment pins table:** Lists all pins (Index, Label). Use **Show on map** (eye icon) to pan to a pin.

Use the **Action** column in the Segments table to **Show on map** (eye) for a segment or **Add pin on segment** (pin icon) to add a new boundary on that leg. Segment boundaries are determined by the **next** pin along the path—to have a segment end at a specific place (e.g. 10K Turn on the return leg), use **Add pin on segment** on that leg and click on the line at that spot, then label the new pin.

---

## Quick reference

| You want to… | Where |
|--------------|--------|
| Draw the line | **Edit** → **Draw Line** → click map to add points. |
| Add a segment boundary | **Add Segment Pin** → click on the line at that point → set label. |
| Start a fork from a point | Click the **pin** → **Extend from here** → draw new points. |
| Add a U-turn (return same path) | After drawing outbound: **Same Route Back** → set **Rejoin at:** (dropdown or red marker) → **Confirm**. |
| Add a new leg (e.g. to Finish) | From the current end pin: **Extend from here** → draw along the route. Do **not** use Same Route Back for this. |
| Define who goes which way at a split | Click the **pin** → **Flow control** → check events per “Leg to: …” → **Save**. |
| Set events for a segment (no flow control) | **Segments** table → click segment **ID** → edit events. |
| Zoom the map to a segment | **Segments** table → click anywhere on that segment’s row. |
| Save the course | **Save** (top). |
| Export for the pipeline | **Export** (e.g. “to folder”). |

---

## Common issues

**“I don’t see ‘Friel to 10K Turn’ and ‘10K Turn back to Friel’ in segments.”**  
Segments exist only **between consecutive segment pins**. Add pins at the first Friel (where the path goes out to 10K Turn) and at the 10K Turn. Then you should see four segments: Start→Friel, Friel→10K Turn, 10K Turn→Friel, Friel→Finish.

**“Red marker won’t go where I need it.”**  
Use the **Rejoin at:** dropdown and pick the pin by name (e.g. “Friel”). You can also drag the red marker; it snaps to segment pins when close.

**“I can’t click a segment pin (e.g. it’s behind the green F).”**  
Click the **green F** marker—if that point has a segment pin, the pin popup opens. Or use the **Segments** table: click the **From** or **To** pin label for a segment that ends at that point to open the pin popup.

**“Same place, two pins (e.g. Friel before 10K leg and Friel before Station at Barker).”**  
The line has two points at the same location, so you get two pins. Use **Flow control** at **each** if both are split points.

**“I only see one leg in Flow control.”**  
You may be missing a **segment pin at the first vertex** at that location (e.g. the first Friel where the 10K leg starts). Add a segment pin there so both legs appear in Flow control.

**“Segment events are wrong after I set flow control.”**  
Flow control only affects segments that **start** at that pin. If you have two pins at the same place, the UI shows all legs from any pin at that location in one dialog; set the correct events per leg.

**“I drew the whole course first, then tried Same Route Back.”**  
Same Route Back adds return from the **last point** to the **rejoin point**. If you drew Start → Finish in one go, the “last point” is Finish and the result is wrong. Prefer: draw up to the rejoin point, use Same Route Back to that point, then continue drawing to Finish.

**“Green line looks doubled and total distance is too long.”**  
The course may have an **extra leg** after the intended finish (e.g. a return leg counted twice). Click the **segment pin where the course should end** → **End course here** to truncate the course at that pin. Alternatively, use the truncate script (see dev docs) with a backup of your course file.

**“I moved a segment pin and see multiple green tracks.”**  
Dragging a pin or U-turn only **moves that point** on the single course line; it does not add new geometry. What you may see is each segment drawn as its own polyline (several short segments can look like parallel dashes). If you truly have duplicate geometry, use **Undo** or **Clear line** and redraw. To remove a U-turn marker entirely, click it → **Remove this U-turn**.

**“When I delete a segment pin, the green lines stay (or don’t update).”**  
Deleting a pin only **removes a segment boundary** (it merges two segments into one). It does **not** remove any of the course path. The green line still covers the same route but is redrawn as fewer segments. To **remove a leg** from the map you must remove its points (e.g. **Undo** or **Clear line** and redraw).

**“After deleting a segment pin, the Finish marker (green F) moved.”**  
The **Finish marker is always** at the **last point** of the course (end of the green line). Deleting a segment pin never shortens the course—it only merges two segments. If you want the course to end somewhere else, **Extend from here** from the correct pin so the line reaches that point; the F will be there.

**“Split at one place (e.g. Station/Barker): Half one way, Full/10K another.”**  
You need **two points at that location** (same place, two pins) so the course has two distinct legs. Draw to that place and add a pin; **Extend from here** to draw the first leg (e.g. Full/10K to Finish); then click the same pin again → **Extend from here** and draw the second leg (e.g. Half to Gibson/McGloin). Use **Flow control** at that pin to set which events take “Leg to …” for each direction.

---

## What gets exported

- **segments.csv:** One row per segment with event-specific distance columns (e.g. `full_from_km`, `half_from_km`, `10k_from_km`). Distances are cumulative along only the segments that include that event.
- **flow.csv:** Segment-level flow metadata for the pipeline.
- **locations.csv:** Checkpoint and aid station locations (if you added location pins).
- **course.gpx** / **course.json:** Full course geometry and metadata.

Flow control and segment events together determine which events are listed per segment and how event-specific distances are computed for export and analysis.
