# Implementation Plan: 5K Course Support with Elite and Open Events

**Goal:** Add 5K course and two events (5K Elite, 5K Open) to the run-density application  
**Status:** Planning Phase  
**Target Sprint:** Next Sprint

---

## Overview

Currently, the application supports three courses (Full, Half, 10K) with start times. This plan outlines adding:
- **5K Course**: 5K course file (`data/5K.gpx`) will be duplicated for each event below.
- **Elite Event**: 5K distance, faster participants (2 laps, 5km total)
- **Open Event**: 5K distance, same route as Elite but different start time/participants

**Key Clarifications:**
- Event names are **'Elite'** and **'Open'** (capitalized to match "Full", "Half", "10K" pattern)
- Data files (runners.csv, segments.csv, flow.csv) have been updated to use these names
- Only one distance (5K) has both elite and open variants
- **GPX Files**: Use separate files `data/5KElite.gpx` and `data/5KOpen.gpx` for consistency with existing pattern (10K.gpx, Half.gpx, Full.gpx)
- Both files will have identical content (same physical route), but separate files maintain consistency with codebase pattern
- **Temporal Separation**: 5K events (Elite, Open) are on **Saturday**, Other events (Full, Half, 10K) are on **Sunday** - no overlap, separate analysis

The segments.csv already has the structure in place with:
- Segments N1-N3 for Elite (Lap 1, Lap 2, Finish)
- Segments O1-O3 for Open (Lap 1, Lap 2, Finish)
- Columns: `elite`, `open`, `5K_from_km`, `5K_to_km` and `5K_length`

---

## UI Considerations

The UI needs to support event-based filtering since 5K events (Elite and Open) are separate from Full, Half, and 10K events

### Dashboard Page (`/dashboard`)
- **Model Inputs**: Add two new tiles for '5K Elite', '5K Open' that show start time and count of participants, and a third new tile for the number of 5K segments (this only needs to be the count of one of Elite or Open)
- **Model Outputs**: Show three groups of metric tiles (Elite, Open, and Full/Half/10K (current behavior)
- **Backend**: Update `/api/dashboard/summary` to accept day event filter parameter (elite, open, full, half, 10K) and all

### Segments Page (`/segments`)
- **Add Drop-down Event Selector**: "5K Elite", "5K Open" and "Full/Half/10K"
- **Filter Map**: Only display segments for the selected event
- **Filter Segment Table**: Only show segment metadata for selected event
- **Backend**: Update `/api/segments` to accept event filter parameter (elite, open, full, half, 10K) and all

### Density Page (`/density`)
- **Add Drop-down Event Selector**: "5K Elite", "5K Open" and "Full/Half/10K"
- **Filter Segment Table**: Only show density segments for selected event
- **Backend**: Update `/api/density/segments` to accept event filter parameter (elite, open, full, half, 10K) and all

### Flow Page (`/flow`)
- **Add Drop-down Selector**: "5K" vs "Full/Half/10K"
- **Filter Flow Table**: Only show flow pairs for selected event
- **5K Selected**: Show only Elite/Open pair
- **Full/Half/10K Selected**: Show Full/Half, Full/10K, Half/10K pairs
- **Backend**: Update `/api/flow/segments` to accept event filter parameter (elite, open, full, half, 10K) and all

### Reports Page (`/reports`)
- **No UI Changes**: Keep same structure
- **Backend**: Include 5K events (Elite, Open) in existing flow/density reports

---

## Areas Requiring Changes

### 1. GPX Processing (`app/core/gpx/processor.py`)

**Current State:**
- Only loads: `10K.gpx`, `Half.gpx`, `Full.gpx`
- Event priority: `["10K", "half", "full"]`

**Required Changes:**
1. **Add 5KElite.gpx and 5KOpen.gpx to course loading** (`load_all_courses()` function)
   - Add `"Elite": os.path.join(gpx_dir, "5KElite.gpx")` to `gpx_files` dictionary
   - Add `"Open": os.path.join(gpx_dir, "5KOpen.gpx")` to `gpx_files` dictionary
   - **Note**: Files will have identical content (same route) but separate files maintain consistency
   - **Note**: Use capitalized "Elite" and "Open" to match "Full", "Half", "10K" naming pattern
   
2. **Update event priority in `generate_segment_coordinates()`**
   - Current: `["10K", "half", "full"]`
   - New: Add `"Elite"` and `"Open"` to event detection list (line 289)
   - Event name maps directly to GPX file (consistent with existing pattern)

3. **Update course key lookup**
   - Current: Uses title case conversion for "10K", "half", "full"
   - New: Handle "Elite" and "Open" - both map directly to their respective GPX files
   - No special case handling needed - follows same pattern as other events

**Files to Modify:**
- `app/core/gpx/processor.py`: 
  - Line 392-396: Add "Elite" and "Open" to gpx_files dictionary
  - Line 289-296: Add "Elite" and "Open" to event priority list
  - Line 299-300: Update course key lookup to handle "Elite" and "Open"

---

### 2. Density Analysis (`app/core/density/compute.py`)

**Current State:**
- Only recognizes: `["Full", "Half", "10K"]`
- Event interval extraction: `full_from_km`, `half_from_km`, `tenk_from_km`

**Required Changes:**
1. **Update `get_event_intervals()` function** (lines 31-60)
   - Add support for "Elite" and "Open" events
   - Both use `5K_from_km` and `5K_to_km` from segments.csv
   - Check event name to determine which to use (both use same km columns)

2. **Update event validation** (line 55)
   - Current: `if event not in ["Full", "Half", "10K"]:`
   - New: Add `"Elite"` and `"Open"` → `["Full", "Half", "10K", "Elite", "Open"]`

3. **Update event column mapping** (line 247)
   - Current: `("Full", "full"), ("Half", "half"), ("10K", "10K")`
   - New: Add `("Elite", "elite")` and `("Open", "open")` - capitalized event name, lowercase CSV column

**Event Names:** Use capitalized `"Elite"` and `"Open"` to match "Full", "Half", "10K" pattern for consistency

**Files to Modify:**
- `app/core/density/compute.py`: 
  - Lines 31-60: Update `get_event_intervals()` to handle "elite" and "open" (use 5K_from_km/5K_to_km)
  - Line 55: Add "elite" and "open" to validation list
  - Line 247: Add ("elite", "elite") and ("open", "open") to column mapping

---

### 3. Flow Analysis (`app/core/flow/flow.py`)

**Current State:**
- Analyzes temporal flow between events (Full, Half, 10K)

**Required Changes:**
1. **Update event handling for Elite/Open**
   - Need to recognize "Elite" and "Open" as valid events
   - **NO flow analysis between Elite/Open and other events** (Full, Half, 10K)
   - Rationale: 5K events are on **Saturday**, other events are on **Sunday** - separate days, no overlap
   - Flow analysis between Elite and Open ONLY (for bad data detection)

2. **Event pair generation**
   - Current combinations: Full/Half, Full/10K, Half/10K (3 pairs) - Sunday events only
   - New: Add Elite/Open pair (1 pair) - Saturday events only
   - **Total combinations: 4 pairs** (not 10 - events are separated by day)
   - New pairs: Elite/Open (only)
   - **No pairs between**: Full/Elite, Full/Open, Half/Elite, Half/Open, 10K/Elite, 10K/Open

**Important Constraints:**
- 5K events (Elite, Open) are on **Saturday**
- Other events (Full, Half, 10K) are on **Sunday**
- No temporal overlap, so no flow analysis between day groups
- Elite/Open pair kept for bad data detection scenarios

**Future Consideration:**
- Question: Should we introduce a "day" field along with time to explicitly separate Saturday vs Sunday events?
- For now: No separate analysis mode needed (future feature)

**Files to Modify:**
- `app/core/flow/flow.py`: 
  - Event recognition to accept "Elite" and "Open" (capitalized)
  - Event pair generation: Add Elite/Open pair ONLY (no pairs with other events)
  - Ensure no cross-day pairs are generated (Saturday vs Sunday separation)

---

### 4. Constants and Defaults (`app/utils/constants.py`)

**Current State:**
- `DEFAULT_START_TIMES = {"Full": 420, "10K": 440, "Half": 460}`

**Required Changes:**
1. **Add Elite and Open start times**
   - Default start times: Elite=480, Open=510 (minutes from midnight)
   - Format: `{"Full": 420, "10K": 440, "Half": 460, "Elite": 480, "Open": 510}`
   - Note: Event names are capitalized "Elite" and "Open" to match "Full", "Half", "10K" pattern

**Files to Modify:**
- `app/utils/constants.py`: 
  - Line 83: Update DEFAULT_START_TIMES to include `"Elite": 480, "Open": 510`

---

### 5. Event Detection Utilities

**Critical Issue:** Multiple event detection functions need updates to recognize Elite and Open events.

#### 5a. `app/conversion_audit.py` - `get_segment_events()`

**Current State:**
- Only checks: `full`, `half`, `10K` columns
- Returns: `['Full', 'Half', '10K']`

**Required Changes:**
1. **Update `get_segment_events()` function** (lines 13-30)
   - Add checks for `elite` and `open` columns (lowercase in CSV)
   - Return `"Elite"` or `"Open"` (capitalized) based on which column is 'y'
   - Can return both if both columns are 'y'
   - CSV columns are lowercase (`elite`, `open`), but return capitalized event names to match pattern

**Files to Modify:**
- `app/conversion_audit.py`: 
  - Lines 13-30: Update `get_segment_events()` to check `elite` and `open` columns, return "Elite" and "Open" event names

#### 5b. `app/core/flow/flow.py` - `_get_segment_events()`

**Current State:**
- Only checks: `full`, `half`, `10K` columns (lines 74-79)
- Returns: `['Full', 'Half', '10K']`

**Required Changes:**
1. **Update `_get_segment_events()` function** (lines 63-80)
   - Add checks for `elite` and `open` columns (lowercase in CSV)
   - Return `"Elite"` or `"Open"` (capitalized) based on which column is 'y'
   - Used by flow analysis for segment-to-event mapping

**Files to Modify:**
- `app/core/flow/flow.py`:
  - Lines 63-80: Update `_get_segment_events()` to check `elite` and `open` columns, return "Elite" and "Open" event names

---

### 6. API Endpoints and Request Models

**Current State:**
- API endpoints accept `startTimes: Dict[str, int]` with Full, Half, 10K

**Required Changes:**
1. **Update request models** (if needed)
   - Most endpoints accept flexible `startTimes` dict, so should work as-is
   - Verify all endpoints can handle "Elite" and "Open" keys (capitalized)

2. **Update validation** (if any)
   - Check if any endpoint validates event names explicitly
   - Update validation to accept "Elite" and "Open" events

**Files to Review:**
- `app/main.py`: All request models
- `app/api/density.py`: Event validation
- `app/api/flow.py`: Event validation

---

### 7. E2E Testing (`e2e.py`)

**Current State:**
- Uses default start times for Full, Half, 10K

**Required Changes:**
1. **Add Elite and Open to E2E test data**
   - Update start times in E2E configuration (Elite=480, Open=510)
   - Ensure runners.csv has test data for Elite and Open events (already updated per user)
   - Verify segments.csv and flow.csv have elite/open data (already updated per user)
   - Note: CSV columns are lowercase, but event names in code should be capitalized

**Files to Modify:**
- `e2e.py`: Start times configuration

---

### 8. UI Components (New Requirements)

**Current State:**
- Dashboard shows metrics for Full, Half, 10K (Sunday events)
- Segments, Density, and Flow pages show all segments/analysis
- No day-based filtering

**Required Changes:**

1. **Dashboard (`/dashboard` or templates/pages/dashboard.html)**
   - Add drop-down selector: **"5K (Saturday)"** vs **"Full/Half/10K (Sunday)"**
   - When 5K selected: Show two sets of metric tiles (Elite and Open)
   - When Full/Half/10K selected: Show current behavior (Full, Half, 10K metrics)
   - Update summary API to filter by selected day

2. **Segments Page (`/segments` or templates/pages/segments.html)**
   - Add drop-down selector: **"5K"** vs **"Full/Half/10K"**
   - Filter map display: Only show segments for selected day
   - Filter segment metadata table: Only show segments for selected day
   - Update segments API to accept day filter parameter

3. **Density Page (`/density` or templates/pages/density.html)**
   - Add drop-down selector: **"5K"** vs **"Full/Half/10K"**
   - Filter segment table: Only show segments for selected day
   - Update density API to accept day filter parameter

4. **Flow Page (`/flow` or templates/pages/flow.html)**
   - Add drop-down selector: **"5K"** vs **"Full/Half/10K"**
   - Filter flow table: Only show flow pairs for selected day
   - Update flow API to accept day filter parameter
   - Note: 5K selection shows only Elite/Open pair, Sunday selection shows Full/Half/10K pairs

5. **Reports Page (`/reports`)**
   - Keep same structure
   - Add 5K events (Elite, Open) to existing flow/density reports
   - Reports include all events but can be filtered by day if needed

**Implementation Notes:**
- Day filtering can be query parameter: `?day=5K` or `?day=Sunday` or similar
- Backend APIs need to support day filter parameter
- Frontend needs selector component/UI element
- Consider storing selected day in session/localStorage for consistency across page navigation

**Files to Review/Modify:**
- `templates/pages/dashboard.html` - Add day selector, conditional rendering
- `templates/pages/segments.html` - Add day selector, filter map/table
- `templates/pages/density.html` - Add day selector, filter table
- `templates/pages/flow.html` - Add day selector, filter table
- `app/routes/api_dashboard.py` - Add day filter parameter
- `app/routes/api_segments.py` - Add day filter parameter
- `app/routes/api_density.py` - Add day filter parameter
- `app/routes/api_flow.py` - Add day filter parameter
- Frontend JavaScript (if any) - Day selector logic

---

### 9. Artifact Generation Pipeline

**Critical Issue:** UI artifacts (segments.geojson, segment_metrics.json, meta.json) must include Elite and Open events.

#### 9a. Segments GeoJSON Generation ⚠️ **CRITICAL GAP IDENTIFIED**

**Current State:**
- `segments.geojson` is generated during E2E runs and stored in `runflow/<uuid>/ui/`
- Properties include `events: []` array populated from segments.csv
- Generated by artifact export process (likely in `app/core/artifacts/frontend.py` - filtered from view)
- **PROBLEM:** Current logic may hardcode event lists and selectively build output per known segment/event mapping

**Critical Issue Found:**
- `app/density_report.py` lines 2534-2548: Hardcoded conversion only includes Full, Half, 10K
- Missing `elite` and `open` columns in segments_list conversion
- This affects segment coordinate generation for Elite/Open segments

**Required Changes:**
1. **Fix `app/density_report.py` `_add_geometries_to_bin_features()` function**
   - **Lines 2534-2548:** Add `elite` and `open` columns to segments_list dict:
   ```python
   segments_list.append({
       "seg_id": segment['seg_id'],
       "segment_label": segment.get('seg_label', segment['seg_id']),
       "10K": segment.get('10K', 'n'),
       "half": segment.get('half', 'n'),
       "full": segment.get('full', 'n'),
       "elite": segment.get('elite', 'n'),  # ADD THIS
       "open": segment.get('open', 'n'),    # ADD THIS
       # ... rest of fields
   })
   ```

2. **Ensure segments.geojson includes Elite/Open in events property**
   - Artifact generator must read `elite` and `open` columns from segments.csv
   - Populate `events: ["Elite"]` or `events: ["Open"]` or `events: ["Elite", "Open"]` in GeoJSON features
   - **CRITICAL:** UI filtering depends on events array - segments without events won't render
   - Verify segments N1-N3 (Elite) and O1-O3 (Open) have correct events array

3. **Event Detection in Artifact Generation**
   - All code paths that generate segments.geojson must use updated event detection
   - Check: `app/core/artifacts/frontend.py` (if accessible) - artifact export module
   - Check: `app/density_report.py` - segment GeoJSON generation
   - Check: `app/geo_utils.py` - `generate_segments_geojson()` may need events property from source
   - **Implementation Pattern:**
     ```python
     events = []
     if segment.get('full') == 'y':
         events.append('Full')
     if segment.get('half') == 'y':
         events.append('Half')
     if segment.get('10K') == 'y':
         events.append('10K')
     if segment.get('elite') == 'y':  # ADD THIS
         events.append('Elite')        # ADD THIS
     if segment.get('open') == 'y':   # ADD THIS
         events.append('Open')         # ADD THIS
     properties["events"] = events
     ```

**Files to Review/Modify:**
- `app/density_report.py` - **CRITICAL:** Fix lines 2534-2548 (add elite/open columns)
- `app/core/artifacts/frontend.py` - Artifact export module (check event detection logic)
- `app/geo_utils.py` - GeoJSON generation functions
- Any module that reads segments.csv and generates GeoJSON

#### 9b. Segment Metrics JSON Generation

**Current State:**
- `segment_metrics.json` contains per-segment metrics and summary statistics
- Includes summary fields: `peak_density`, `peak_rate`, `segments_with_flags`, etc.

**Required Changes:**
1. **Ensure Elite/Open segments included in metrics**
   - Metrics should be calculated for all segments including N1-N3, O1-O3
   - No filtering by event type that excludes Elite/Open
   - Verify summary statistics include Elite/Open segments

**Files to Review:**
- `app/core/artifacts/frontend.py` - Segment metrics export
- `app/routes/api_density.py` - Metrics normalization logic

#### 9c. Meta.json Generation

**Current State:**
- `meta.json` contains run metadata (timestamp, environment, file counts)

**Required Changes:**
1. **Verify no event whitelist filtering**
   - Ensure metadata includes all segments regardless of event type
   - No hardcoded event lists that would exclude Elite/Open

### 10. Health & Safety Flags

**Critical Issue:** Health indicators must work with Elite and Open events.

#### 10a. Health.json Generation

**Current State:**
- `health.json` contains system health information (environment, files, hashes, endpoints)
- Loaded by `/api/health/data` endpoint (`app/routes/api_health.py`)

**Required Changes:**
1. **Verify health checks scale with new events**
   - Ensure health.json generation doesn't filter by event type
   - Verify file count checks include Elite/Open segments

**Files to Review:**
- `app/routes/api_health.py` - Health data endpoint (should be OK, reads from artifact)
- Health generation logic (likely in artifact export)

#### 10b. Safety Flagging System

**Current State:**
- `flags.json` contains flagged segments for safety concerns
- Generated during analysis based on density/flow thresholds

**Required Changes:**
1. **Ensure flagging rules work for Elite/Open**
   - Smaller participant sets (Elite) may have lower densities → verify thresholds appropriate
   - Avoid false negatives due to low participant counts
   - Verify flagging logic doesn't hardcode event types

**Files to Review:**
- `app/flagging.py` - Flag generation logic
- Flagging thresholds in `config/reporting.yml` or rulebook

### 11. Report Generation and Comparison Views

**Critical Issue:** Reports must adapt to 5 events instead of 3. **May assume 3-event overlay (Full, Half, 10K) and not auto-handle 2-event structures like Elite/Open.**

#### 11a. Density Reports

**Required Changes:**
1. **Charts and tables must adapt dynamically**
   - Event-specific tables should include Elite and Open
   - Comparison views should handle 5 events gracefully
   - **Graphs/plots adaptation:** Ensure charts can display:
     - 5 individual event lines (instead of 3)
     - Saturday events (Elite, Open) vs Sunday events (Full, Half, 10K)
     - Separate comparison views if needed
   - Ensure no assumptions about exactly 3 events break

**Specific Concerns:**
- Event overlay visualizations may need separate Saturday vs Sunday views
- Metrics tables must accommodate 5 events
- Comparison logic may need day-based grouping

**Files to Review:**
- `app/density_report.py` - Report generation, chart generation logic
- Any hardcoded event lists or loops assuming 3 events
- Graph/plot generation functions

#### 11b. Flow Reports

**Required Changes:**
1. **Flow comparison logic**
   - Must handle 4 pairs (not 3)
   - Ensure no assumptions about pair count
   - Day-based separation in reports (Saturday vs Sunday)
   - **Overtake visualizations:** May need separate Saturday vs Sunday views
   - **2-event structure handling:** Elite/Open pair may need different visualization than 3-event structure

**Specific Concerns:**
- Overtake comparison charts must handle 4 pairs
- May need separate visualization sections for Saturday vs Sunday
- Ensure comparison logic doesn't break with 2-event structures

**Files to Review:**
- `app/flow_report.py` - Flow report generation, pair comparison logic
- Overtake visualization functions

#### 11c. Heatmaps

**Current State:**
- Segment heatmap PNGs generated and stored in `heatmaps/` folder
- May not be regenerated unless explicitly triggered

**Required Changes:**
1. **Verify heatmaps generated for Elite/Open segments**
   - Segments N1-N3, O1-O3 should have heatmaps
   - No event filtering that excludes 5K segments
   - Check heatmap generation trigger logic
   - **Document refresh workflow:** How/when heatmaps are regenerated

**Files to Review:**
- `app/heatmap_generator.py` - Heatmap generation
- Heatmap generation triggers in analysis pipeline
- Document refresh workflow for heatmaps

### 11d. Parquet & JSON Outputs

**Critical Issue:** Artifacts like `segments.parquet` and `segment_metrics.json` are used in load-time analytics and must include Elite/Open data.

#### Segments Parquet

**Required Changes:**
1. **Verify segments.parquet includes Elite/Open segments**
   - Ensure no event filtering excludes N1-N3, O1-O3 segments
   - Document in development workflow whether parquet files are updated automatically
   - Check downstream consumers (e.g., `flow-analysis.py`, `run_health.py`) are event-aware beyond original 3

#### Segment Metrics JSON

**Required Changes:**
1. **Verify segment_metrics.json includes Elite/Open metrics**
   - All segments including N1-N3, O1-O3 must have metrics calculated
   - Summary statistics must include Elite/Open segments
   - Used by UI dashboards - must be complete

**Files to Review:**
- Parquet generation logic (wherever segments.parquet is created)
- `segment_metrics.json` generation in artifact export
- Downstream consumers that read parquet/JSON files

### 11e. UI Segment Filtering Logic

**Critical Issue:** Segments map filters by `events[]` in segments.geojson. If events property is missing or incorrect, segments won't render.

**Required Changes:**
1. **Verify Leaflet mapping filters correctly**
   - Check `static/js/map/segments.js` for event filtering logic
   - Ensure day-based filtering works with events array
   - Segments with `events: ["Elite"]` or `events: ["Open"]` must be filterable
   - Not dynamic unless explicitly patched - verify filtering logic

**Files to Review:**
- `static/js/map/segments.js` - Leaflet map filtering logic
- UI JavaScript that filters segments by events array

### 11f. Deployment Trigger & Artifact Refresh

**Required Changes:**
1. **Document artifact regeneration workflow**
   - Who/what regenerates artifacts after code changes?
   - Should there be a `make run-5k` build target or documented artifact-refresh step?
   - Document when artifacts are regenerated:
     - During E2E runs (`make e2e-local`)
     - Manual artifact export triggers
     - Automatic regeneration on data changes

**Files to Document:**
- `Makefile` - Consider adding `make artifacts-refresh` or `make run-5k` target
- `e2e.py` - Document artifact generation triggers
- Developer workflow documentation

### 12. Documentation Updates

**Required Changes:**
1. **Update README.md**
   - Add Elite and Open (5K events) to feature list
   - Update API examples if needed
   - Note: 5K events are on Saturday, other events on Sunday

2. **Update Reference Documentation**
   - `docs/reference/QUICK_REFERENCE.md`: Add Elite and Open events (5K distance)
   - Update event lists throughout docs to include Elite and Open
   - Note: Event names are capitalized (Elite, Open) to match Full, Half, 10K pattern

**Files to Modify:**
- `README.md`
- `docs/reference/QUICK_REFERENCE.md`
- Other relevant docs

---

## Implementation Sequence

### Phase 1: Core Infrastructure (Foundation)
1. ✅ Create `5KElite.gpx` and `5KOpen.gpx` files (copy from 5K.gpx - identical content)
2. ✅ Update GPX processor to load 5KElite.gpx and 5KOpen.gpx
3. ✅ Add Elite and Open to constants (start times: Elite=480, Open=510)
4. ✅ Update event recognition in density analysis (use "Elite" and "Open" event names - capitalized)

### Phase 2: Analysis Engine Updates
4. ✅ Update density analysis event handling (Elite/Open recognition, interval extraction)
5. ✅ Update flow analysis event handling (add Elite/Open pair only, no pairs with other events)
6. ✅ Update conversion audit utilities (event detection for Elite/Open)

### Phase 3: Integration and Testing
7. ✅ Update E2E test configuration
8. ✅ Verify API endpoints work with new events
9. ✅ Test with sample data
10. ✅ Verify flow pairs are correct (4 pairs total, no cross-day pairs)

### Phase 4: UI Updates
11. ✅ Add day selector to Dashboard (5K vs Full/Half/10K)
12. ✅ Add day selector to Segments page (filter map and segments)
13. ✅ Add day selector to Density page (filter segments)
14. ✅ Add day selector to Flow page (filter flow analysis)
15. ✅ Update Reports page (add 5K events to existing reports)
16. ✅ Update backend APIs to support day filter parameter

### Phase 5: Documentation
17. ✅ Update documentation
18. ✅ Update examples and references

---

## Additional Considerations

### Separate Elite/Open Analysis Mode
**Status:** ✅ **Future Feature** - Not required for this sprint

**Rationale:**
- Operationally, Elite finishes before Open starts
- However, bad data could show elites still on course during open start
- Separate analysis could help identify data quality issues

**For This Sprint:**
- Analyze Elite and Open together (Elite/Open pair only)
- Flow analysis between Elite/Open kept for bad data detection
- No separate analysis mode flag needed now

**Future Enhancement:**
- Consider separate analysis mode if data quality issues are identified
- Auto-detect overlap and warn if Elite/Open overlap temporally

---

## Key Design Decisions ✅ **ALL DECIDED**

### Decision 1: Event Naming Convention ✅ **DECIDED - UPDATED**
**Answer:** Event names are **'Elite'** and **'Open'** (capitalized)
- Matches existing pattern: "Full", "Half", "10K" (capitalized)
- Data files (runners.csv, segments.csv, flow.csv) use lowercase columns (`elite`, `open`)
- Internal code should use: `"Elite"` and `"Open"` as event names (capitalized)
- CSV column mapping: lowercase CSV columns → capitalized event names
- Consistency: Don't add to existing inconsistencies (e.g., "tenk") - use proper capitalization

### Decision 2: Segments.csv Column Mapping ✅ **DECIDED - UPDATED**
**Answer:** 
- `elite` column (lowercase in CSV): If `elite == 'y'` → Event is **"Elite"** (capitalized)
- `open` column (lowercase in CSV): If `open == 'y'` → Event is **"Open"** (capitalized)
- Both can be 'y' for segments used by both (like segments N1-N3, O1-O3)
- Both use same `5K_from_km`/`5K_to_km` columns for distance intervals
- Mapping: CSV columns are lowercase, but internal event names are capitalized for consistency

### Decision 3: Default Start Times ✅ **DECIDED**
**Answer:** 
- **Elite**: 08:00 = **480 minutes** from midnight
- **Open**: 08:30 = **510 minutes** from midnight
- Current defaults: Full=420, 10K=440, Half=460 (minutes from midnight)

**Important Operational Note:**
- Elite finishes well before Open starts (due to fast pace + operational planning)
- Race directors ensure Open doesn't start until last Elite has finished
- **Separate Days:** 5K events (Elite, Open) are on **Saturday**, Other events (Full, Half, 10K) are on **Sunday**
- **No Temporal Overlap:** Events are on different days, so no flow analysis between day groups
- Elite/Open pair analysis kept for bad data detection only

### Decision 4: GPX Course Mapping ✅ **DECIDED**
**Answer:**
- Use separate GPX files: **`5KElite.gpx`** and **`5KOpen.gpx`** for consistency with existing pattern
- Files will have identical content (same physical route) but maintains 1:1 event-to-file pattern
- Event name maps directly to GPX file: `"Elite"` → `5KElite.gpx`, `"Open"` → `5KOpen.gpx`
- Simpler code implementation - no special case handling needed
- Consistent with how 10K.gpx, Half.gpx, and Full.gpx are handled

### Decision 5: Temporal Separation ✅ **DECIDED**
**Answer:**
- 5K events (Elite, Open) are on **Saturday**
- Other events (Full, Half, 10K) are on **Sunday**
- **No flow analysis between Saturday and Sunday events** - they don't overlap
- Only flow analysis: Elite/Open pair (Saturday events only)
- **Future Consideration:** Should we introduce a "day" field along with time to explicitly separate events?

---

## Testing Strategy

### Unit Tests
1. Test GPX processor loads 5KElite.gpx and 5KOpen.gpx correctly
2. Test event interval extraction for Elite/Open (use 5K_from_km/5K_to_km)
3. Test density analysis with Elite and Open events
4. Test flow analysis generates only Elite/Open pair (no cross-day pairs)
5. Test `get_segment_events()` in `conversion_audit.py` returns Elite/Open
6. Test `_get_segment_events()` in `flow.py` returns Elite/Open
7. Test event detection in artifact generation includes Elite/Open

### Integration Tests
1. End-to-end test with all 5 events (Full, Half, 10K, Elite, Open)
2. Verify segments N1-N3 (Elite) and O1-O3 (Open) are processed correctly
3. Verify flow analysis generates correct pairs:
   - Sunday events: Full/Half, Full/10K, Half/10K (3 pairs)
   - Saturday events: Elite/Open (1 pair)
   - Total: 4 pairs (not 10 - no cross-day pairs)
4. Test UI day selector functionality (5K vs Full/Half/10K)
5. Verify day filtering works on Dashboard, Segments, Density, Flow pages
6. **Verify segments.geojson includes Elite/Open in events property**
7. **Verify segment_metrics.json includes metrics for Elite/Open segments**
8. **Verify health.json generation works with 5 events**
9. **Verify flags.json includes flags for Elite/Open segments if thresholds exceeded**

### Manual Testing

#### API Response Testing
1. **Test `/api/segments/geojson` response**
   - Verify segments N1-N3 have `events: ["Elite"]` or similar
   - Verify segments O1-O3 have `events: ["Open"]` or similar
   - Verify events property is populated correctly

2. **Test `/api/dashboard/summary` with day filter**
   - Test `?day=5K` parameter returns Elite/Open metrics
   - Test `?day=Sunday` parameter returns Full/Half/10K metrics
   - Verify response shape and values

3. **Test `/api/flow/segments` with day filter**
   - Verify `?day=5K` returns only Elite/Open pair
   - Verify `?day=Sunday` returns only Full/Half/10K pairs (3 pairs)
   - Verify no cross-day pairs appear

4. **Test `/api/health/data`**
   - Verify health.json loads correctly
   - Verify no errors with 5 events

#### UI Testing
1. Generate density report with Elite and Open events included
2. Generate flow report with Elite/Open pair (and verify no cross-day pairs)
3. Verify maps show 5K route correctly (5KElite.gpx and 5KOpen.gpx)
4. Verify UI displays 5K segments correctly
5. Test Dashboard day selector (switch between 5K and Full/Half/10K)
6. Test Segments page day selector and map filtering
7. Test Density page day selector and table filtering
8. Test Flow page day selector and table filtering (verify only correct pairs shown)
9. **Verify segment coloring/visibility based on day selection**
10. **Verify heatmaps display for Elite/Open segments (N1-N3, O1-O3)**

#### Report Testing
1. **Verify density reports include Elite and Open sections**
2. **Verify flow reports show Elite/Open pair correctly**
3. **Verify comparison views handle 5 events gracefully**
4. **Verify no hardcoded "3 events" assumptions break reports**

---

## Files Requiring Changes (Summary)

### Core Modules (High Priority)
- `app/core/gpx/processor.py` - Load 5KElite.gpx and 5KOpen.gpx, update event detection
- `app/core/density/compute.py` - Event recognition, interval extraction
- `app/core/flow/flow.py` - Event handling, pair generation, `_get_segment_events()` function
- `app/conversion_audit.py` - `get_segment_events()` function (event detection)

### Utilities (Medium Priority)
- `app/utils/constants.py` - Add default start times
- **Artifact Generation** (High Priority - Critical)
  - `app/core/artifacts/frontend.py` - Ensure segments.geojson includes Elite/Open in events property
  - Any module generating segments.geojson must read elite/open columns from segments.csv
- **Report Generation** (Medium Priority)
  - `app/density_report.py` - Verify no hardcoded event lists, adapt to 5 events
  - `app/flow_report.py` - Verify handles 4 pairs correctly
  - `app/heatmap_generator.py` - Verify heatmaps generated for Elite/Open segments
- **Health & Safety** (Medium Priority)
  - `app/flagging.py` - Verify flagging works with smaller participant sets
  - Verify health.json generation doesn't filter by event type

### UI Components (High Priority - New)
- `templates/pages/dashboard.html` - Add day selector
- `templates/pages/segments.html` - Add day selector, filter map/segments
- `templates/pages/density.html` - Add day selector, filter segments
- `templates/pages/flow.html` - Add day selector, filter flow pairs
- `app/routes/api_dashboard.py` - Add day filter parameter
- `app/routes/api_segments.py` - Add day filter parameter
- `app/routes/api_density.py` - Add day filter parameter
- `app/routes/api_flow.py` - Add day filter parameter

### Configuration (Low Priority)
- `e2e.py` - Add test data
- `README.md` - Update documentation
- `docs/reference/QUICK_REFERENCE.md` - Update event lists

### Review Required (May need changes)
- `app/main.py` - Request model validation
- `app/api/density.py` - Event validation
- `app/api/flow.py` - Event validation
- All API endpoint handlers

---

## Risk Assessment

### Low Risk
- GPX file already exists (`5K.gpx`)
- Segments.csv already has structure (columns and segments)
- API endpoints use flexible `startTimes` dict

### Medium Risk
- Flow analysis complexity increases (4 event pairs vs 3) - **UPDATED**: Only 4 pairs total, not 10
- Need to ensure Elite/Open differentiation works correctly
- Testing coverage for new event combinations
- **Artifact generation must include Elite/Open** - segments.geojson, segment_metrics.json
- **Event detection functions in multiple modules** - easy to miss one
- **Day-based filtering in UI** - new functionality with potential edge cases

### High Risk
- Breaking existing functionality while adding new events
- Event naming inconsistencies across modules
- Missing validation for edge cases
- **Hardcoded event lists in artifact generation** - segments.geojson may not include Elite/Open events
- **Report generation assumptions** - charts/tables assuming exactly 3 events may break
- **Small participant sets (Elite)** - flagging thresholds may trigger false positives/negatives

---

## Success Criteria

✅ All 5 events (Full, Half, 10K, Elite, Open) are recognized  
✅ GPX processor loads 5KElite.gpx and 5KOpen.gpx successfully  
✅ Consistent file naming pattern maintained (1 event = 1 GPX file)  
✅ Consistent event naming (capitalized: Elite, Open match Full, Half, 10K pattern)  
✅ Density analysis works for Elite and Open segments  
✅ Flow analysis generates correct pairs: 4 total (3 Sunday pairs + 1 Saturday pair)  
✅ No flow analysis between Saturday (5K) and Sunday (Other) events  
✅ UI supports day-based filtering (5K vs Full/Half/10K)  
✅ E2E tests pass with all 5 events  
✅ Documentation updated  

---

## Implementation Checklist

**Based on ChatGPT Review - Comprehensive Action Items**

### Phase 1: Core Infrastructure ✅ Foundation
- [ ] Create `5KElite.gpx` and `5KOpen.gpx` files (copy from 5K.gpx - identical content)
- [ ] Update `app/core/gpx/processor.py` - Add Elite/Open to GPX file loading
- [ ] Update `app/utils/constants.py` - Add `"Elite": 480, "Open": 510` to DEFAULT_START_TIMES
- [ ] Update `app/core/gpx/processor.py` - Add Elite/Open to event priority in `generate_segment_coordinates()`

### Phase 2: Event Detection (CRITICAL - Multiple Modules) ✅ Recognition
- [ ] Update `app/conversion_audit.py` - `get_segment_events()` to check elite/open columns, return "Elite"/"Open"
- [ ] Update `app/core/flow/flow.py` - `_get_segment_events()` to check elite/open columns, return "Elite"/"Open"
- [ ] Update `app/core/density/compute.py` - Event validation list to include "Elite" and "Open"
- [ ] Update `app/core/density/compute.py` - Event column mapping to include ("Elite", "elite") and ("Open", "open")
- [ ] Update `app/core/density/compute.py` - `get_event_intervals()` to handle Elite/Open (use 5K_from_km/5K_to_km)

### Phase 3: Analysis Engines ✅ Processing
- [ ] Update `app/core/flow/flow.py` - Event pair generation: Add Elite/Open pair ONLY (no cross-day pairs)
- [ ] Verify flow pairs = 4 total (3 Sunday + 1 Saturday) - no cross-day pairs
- [ ] Test density analysis with Elite and Open events
- [ ] Test flow analysis generates only correct pairs

### Phase 4: Artifact Generation (CRITICAL) ✅ Output Files
- [ ] Review `app/core/artifacts/frontend.py` - Verify segments.geojson includes Elite/Open in events property
- [ ] Test segments.geojson generation - Verify N1-N3 have `events: ["Elite"]` and O1-O3 have `events: ["Open"]`
- [ ] Verify segment_metrics.json includes metrics for Elite/Open segments
- [ ] Verify meta.json generation doesn't filter by event type
- [ ] Test health.json generation with 5 events
- [ ] Verify flags.json includes flags for Elite/Open segments if thresholds exceeded

### Phase 5: Report Generation ✅ Documentation Output
- [ ] Review `app/density_report.py` - Verify no hardcoded 3-event assumptions
- [ ] Review `app/flow_report.py` - Verify handles 4 pairs correctly
- [ ] Review `app/heatmap_generator.py` - Verify heatmaps generated for Elite/Open segments (N1-N3, O1-O3)
- [ ] Test density reports include Elite and Open sections
- [ ] Test flow reports show Elite/Open pair correctly

### Phase 6: API Endpoints ✅ Backend
- [ ] Update `app/routes/api_dashboard.py` - Add `day` filter parameter
- [ ] Update `app/routes/api_segments.py` - Add `day` filter parameter
- [ ] Update `app/routes/api_density.py` - Add `day` filter parameter
- [ ] Update `app/routes/api_flow.py` - Add `day` filter parameter
- [ ] Test `/api/dashboard/summary?day=5K` and `?day=Sunday`
- [ ] Test `/api/flow/segments?day=5K` returns only Elite/Open pair
- [ ] Test `/api/flow/segments?day=Sunday` returns only 3 Sunday pairs

### Phase 7: UI Components ✅ Frontend
- [ ] Update `templates/pages/dashboard.html` - Add day selector dropdown
- [ ] Update `templates/pages/segments.html` - Add day selector, filter map/segments
- [ ] Update `templates/pages/density.html` - Add day selector, filter segments
- [ ] Update `templates/pages/flow.html` - Add day selector, filter flow pairs
- [ ] Test Dashboard day selector (switch between 5K and Full/Half/10K)
- [ ] Test Segments page day selector and map filtering
- [ ] Test Density page day selector and table filtering
- [ ] Test Flow page day selector and table filtering

### Phase 8: Testing & Validation ✅ Quality Assurance
- [ ] Run E2E tests with all 5 events
- [ ] Verify API response shapes for Elite/Open
- [ ] Verify segments.geojson events property populated correctly
- [ ] Verify flow pairs = 4 total (no cross-day pairs)
- [ ] Verify UI day filtering works on all pages
- [ ] Verify reports generate correctly with 5 events
- [ ] Verify heatmaps display for Elite/Open segments

### Phase 9: Documentation ✅ User/Developer Docs
- [ ] Update `README.md` - Add Elite/Open to feature list
- [ ] Update `docs/reference/QUICK_REFERENCE.md` - Add Elite and Open events
- [ ] Update event lists throughout documentation

---

## Next Steps

1. ✅ **All design decisions confirmed** - Ready for implementation
2. ✅ **ChatGPT review incorporated** - Critical gaps addressed
3. **Create feature branch** - `feature/5k-course-support`
4. **Follow Implementation Checklist above** - Systematic phase-by-phase approach
5. **Test thoroughly** - Especially artifact generation and event detection functions

---

**Plan Created:** 2025-11-23  
**Last Updated:** 2025-11-23 (Updated based on ChatGPT review)  
**Status:** ✅ All Design Decisions Confirmed - Ready for Implementation  

---

## ChatGPT Review Summary (2025-11-23)

**Review Status:** ✅ **Plan Enhanced** - Critical gaps identified and addressed

### Key Strengths Confirmed ✅
- Clear event differentiation with capitalized names
- GPX file duplication strategy (5KElite.gpx, 5KOpen.gpx) maintains consistency
- Segment infrastructure (N1-N3, O1-O3) already in place
- Day-based separation (Saturday vs Sunday) supports clean filtering

### Critical Gaps Identified & Addressed 🚨

1. **Data Loading Pipeline** - ✅ **ADDED Section 5b, 9a**
   - **Issue:** Event detection functions (`_get_segment_events()`, `get_segment_events()`) only check Full/Half/10K
   - **Action:** Updated plan includes both `app/conversion_audit.py` and `app/core/flow/flow.py` event detection fixes

2. **Segment-to-Event Registration** - ✅ **ADDED Section 9a**
   - **Issue:** `segments.geojson` must include Elite/Open in `events` property
   - **Action:** Added comprehensive artifact generation pipeline review requirements

3. **Artifact Generation** - ✅ **ADDED Section 9**
   - **Issue:** All artifact generators must recognize Elite/Open
   - **Action:** Added sections for segments.geojson, segment_metrics.json, meta.json generation verification

4. **Health & Safety Flags** - ✅ **ADDED Section 10**
   - **Issue:** Health indicators and flagging must work with Elite/Open
   - **Action:** Added verification requirements for health.json and flagging thresholds

5. **Report Generation** - ✅ **ADDED Section 11**
   - **Issue:** Reports may assume 3-event structure
   - **Action:** Added requirements for dynamic adaptation to 5 events

6. **Testing/QA Plan** - ✅ **ENHANCED Section "Testing Strategy"**
   - **Issue:** Missing comprehensive test coverage
   - **Action:** Expanded testing section with API response testing, UI testing, and report verification

### Implementation Checklist Added ✅
See **Section "Implementation Checklist"** below for step-by-step action items.

---

**Confirmed Details:**
- ✅ Event names: "Elite" and "Open" (capitalized to match Full, Half, 10K pattern)
- ✅ Start times: Elite=480 (08:00), Open=510 (08:30)
- ✅ GPX files: Separate files `5KElite.gpx` and `5KOpen.gpx` (for consistency with existing pattern)
- ✅ Data files: Already updated (runners.csv, segments.csv, flow.csv) - CSV columns are lowercase, event names capitalized
- ✅ Temporal separation: 5K events (Saturday) vs Other events (Sunday) - no flow analysis between days
- ✅ Flow pairs: 4 total (3 Sunday: Full/Half, Full/10K, Half/10K + 1 Saturday: Elite/Open)

**Next Action:** Begin Phase 1 implementation

---

## 📋 Detailed File-by-File Edit Checklist

**See:** `docs/5k-file-edit-checklist.md` for comprehensive file-by-file implementation checklist with:
- Exact code changes required
- Line numbers where applicable
- Priority levels (Critical/High/Medium/Low)
- Code snippets for each change

This checklist addresses the final technical review gaps:
1. Artifact generation scripts (events property population)
2. Parquet & JSON outputs (segments.parquet, segment_metrics.json)
3. UI segment filtering logic (events array in segments.geojson)
4. Report generation adaptation (5 events vs 3 events)
5. Deployment triggers and workflow documentation
