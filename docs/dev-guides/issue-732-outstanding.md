# Issue 732 – Outstanding Work Summary

*Use this after restarting to continue work.*

---

## Completed (committed)

- **Course Mapping UI** (commit `dedff26`): Edit mode, labels, button styling (Street/Satellite style), Snap-to-Road as button, Delete Course styling, description auto-resize textarea, Export/Delete/Edit layout
- **Segments UI** (earlier commits): Table with Seg ID (S1, S2, …), From pin, To pin, Segment label, Width, From/To/Length km
- **Course storage** (earlier commits): New course, Save, Load, table/list UI, Leaflet map, draw line, snap-to-road, segment pins, locations

---

## Outstanding (uncommitted)

### 1. Commit backend changes

These files have uncommitted changes that support the UI already built:

| File | Changes |
|------|---------|
| `app/core/course/export.py` | `_segment_display_id()` returns S1, S2, S3, … for segments.csv and flow.csv; `loc_description` added to locations.csv |
| `app/core/course/storage.py` | `list_courses()` returns `distance_km`, `segments_count`, `locations_count`, `description`; `delete_course()`; `segment_break_descriptions`, `segment_break_ids` in default course |
| `app/routes/api_course.py` | `delete_course` route; export `to_folder` query param (write files to course folder instead of download) |

**Action:** `git add` those three files and commit with a message like:  
`Issue #732: Export S1/S2 seg_id, locations loc_description, delete course, list enrichment, export to_folder`

### 2. Add dev docs (optional)

- `docs/dev-guides/issue-732-segments-ui-csv-alignment.md` — proposal doc (all checklist items done)
- Consider adding `docs/dev-guides/issue-731-course-mapping-decisions.md` and `issue-731-original-prompt-vs-prd.md` if they should be in version control

### 3. Verify export flow

- Confirm Export writes segments.csv, flow.csv, locations.csv, GPX to course folder when `to_folder=1`
- Confirm downstream pipeline accepts S1, S2, … as `seg_id` (doc says it does)

---

## Reference

- Spec: `docs/dev-guides/issue-732-segments-ui-csv-alignment.md`
- Frontend: `frontend/templates/pages/course_mapping.html`, `frontend/static/js/map/course_mapping.js`
- Backend: `app/core/course/export.py`, `app/core/course/storage.py`, `app/routes/api_course.py`
