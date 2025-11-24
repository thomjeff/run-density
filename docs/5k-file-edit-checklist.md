# 5K Support - File-by-File Edit Checklist

**Based on Final Technical Review**  
**Date:** 2025-11-23  
**Status:** Comprehensive Implementation Checklist

---

## 🚨 CRITICAL FIXES (Must Do First)

### 1. Event Detection Functions (Multiple Files)

#### `app/conversion_audit.py` ⚠️ **ARCHIVED - NO ACTION NEEDED**

**Status:** ✅ **File moved to archive/** - Not used in runtime

**Analysis:**
- No runtime imports found in codebase
- Legacy audit utility for `segments_new.csv` (file no longer exists)
- Standalone CLI tool, not part of application runtime
- **Action:** File archived - removed from Phase 1 critical fixes

#### `app/core/flow/flow.py`
- **Function:** `_get_segment_events()` (lines 63-80)
- **Current:** Only checks `full`, `half`, `10K` columns
- **Fix:** Add checks for `elite` and `open` columns
- **Code Change:**
  ```python
  if segment.get('elite') == 'y':
      events.append('Elite')
  if segment.get('open') == 'y':
      events.append('Open')
  ```
- **Priority:** 🔴 **CRITICAL** - Used by flow analysis

---

### 2. Segments CSV to GeoJSON Conversion

#### `app/density_report.py`
- **Function:** `_add_geometries_to_bin_features()` (lines 2534-2548)
- **Current:** Hardcoded conversion only includes Full, Half, 10K:
  ```python
  segments_list.append({
      "seg_id": segment['seg_id'],
      "segment_label": segment.get('seg_label', segment['seg_id']),
      "10K": segment.get('10K', 'n'),
      "half": segment.get('half', 'n'),
      "full": segment.get('full', 'n'),
      "10K_from_km": segment.get('10K_from_km'),
      "10K_to_km": segment.get('10K_to_km'),
      "half_from_km": segment.get('half_from_km'),
      "half_to_km": segment.get('half_to_km'),
      "full_from_km": segment.get('full_from_km'),
      "full_to_km": segment.get('full_to_km')
      # MISSING: elite, open columns + 5K_from_km, 5K_to_km!
  })
  ```
- **Fix:** Add `elite`, `open` columns AND `5K_from_km`, `5K_to_km` fields
- **Code Change:**
  ```python
  segments_list.append({
      "seg_id": segment['seg_id'],
      "segment_label": segment.get('seg_label', segment['seg_id']),
      "10K": segment.get('10K', 'n'),
      "half": segment.get('half', 'n'),
      "full": segment.get('full', 'n'),
      "elite": segment.get('elite', 'n'),      # ADD THIS
      "open": segment.get('open', 'n'),        # ADD THIS
      "10K_from_km": segment.get('10K_from_km'),
      "10K_to_km": segment.get('10K_to_km'),
      "half_from_km": segment.get('half_from_km'),
      "half_to_km": segment.get('half_to_km'),
      "full_from_km": segment.get('full_from_km'),
      "full_to_km": segment.get('full_to_km'),
      "5K_from_km": segment.get('5K_from_km'),  # ADD THIS
      "5K_to_km": segment.get('5K_to_km'),     # ADD THIS
  })
  ```
- **Priority:** 🔴 **CRITICAL** - Affects segment coordinate generation

---

### 3. Artifact Generation - Events Property Population ✅ **LOCATION CONFIRMED**

**CRITICAL GAP:** segments.geojson must include `events: ["Elite"]` or `events: ["Open"]` per segment.

#### ✅ CONFIRMED: Artifact Export Module Location
- **File:** `app/core/artifacts/frontend.py` (exists, filtered by .cursorignore)
- **Function:** `export_ui_artifacts()` → `generate_segments_geojson()` → `_create_segment_feature()` / `_build_segment_feature_properties()`
- **Runtime:** Called during E2E test execution (see logs: "5️⃣ Generating segments.geojson...")

#### Fix Required: TWO Locations in frontend.py

**Location 1: `_create_segment_feature()` function (Line 510)**
- **Current Code:**
  ```python
  "events": [event for event in ["Full", "Half", "10K"] 
             if dims.get(event.lower() if event != "10K" else "10K", "") == "y"],
  ```
- **Fix:** Add `"Elite"` and `"Open"` to list:
  ```python
  "events": [event for event in ["Full", "Half", "10K", "Elite", "Open"] 
             if dims.get(event.lower() if event != "10K" else "10K", "") == "y"],
  ```
- **Note:** Logic already handles lowercase CSV columns (`elite`, `open`) correctly

**Location 2: `_build_segment_feature_properties()` function (Line 547)**
- **Current Code:** Same as Location 1
- **Fix:** Same change as Location 1

**Additional Fix: length_km Calculation (Lines 509 and 546)**
- **Current Code:**
  ```python
  "length_km": float(dims.get("full_length", dims.get("half_length", dims.get("10K_length", 0.0)))),
  ```
- **Fix:** Add `5K_length` fallback:
  ```python
  "length_km": float(dims.get("full_length", dims.get("half_length", dims.get("10K_length", dims.get("5K_length", 0.0))))),
  ```
- **Apply to:** Both `_create_segment_feature()` (line 509) and `_build_segment_feature_properties()` (line 546)

- **Priority:** 🔴 **CRITICAL** - UI filtering depends on events array

---

## 📋 Core Infrastructure Changes

### 4. GPX Processor

#### `app/core/gpx/processor.py`
- **Function:** `load_all_courses()` (around lines 392-396)
- **Change:** Add Elite and Open to GPX file dictionary:
  ```python
  gpx_files = {
      "10K": os.path.join(gpx_dir, "10K.gpx"),
      "Half": os.path.join(gpx_dir, "Half.gpx"),
      "Full": os.path.join(gpx_dir, "Full.gpx"),
      "Elite": os.path.join(gpx_dir, "5KElite.gpx"),  # ADD THIS
      "Open": os.path.join(gpx_dir, "5KOpen.gpx"),    # ADD THIS
  }
  ```

- **Function:** `generate_segment_coordinates()` (around line 289)
- **Change:** Add Elite and Open to event priority list:
  ```python
  # Current: ["10K", "half", "full"]
  # New: ["10K", "half", "full", "Elite", "Open"]
  for event in ["10K", "half", "full", "Elite", "Open"]:
      # ... rest of logic
  ```
- **Priority:** 🟡 **HIGH** - Required for 5K course loading

---

### 5. Density Analysis

#### `app/core/density/compute.py`
- **Function:** `get_event_intervals()` (lines 31-60)
- **Change:** Add Elite/Open event handling (use `5K_from_km`/`5K_to_km`):
  ```python
  elif event == "Elite" and density_cfg.get("5K_from_km") is not None:
      return (density_cfg["5K_from_km"], density_cfg["5K_to_km"])
  elif event == "Open" and density_cfg.get("5K_from_km") is not None:
      return (density_cfg["5K_from_km"], density_cfg["5K_to_km"])
  ```

- **Function:** Event validation (line 55)
- **Change:** Update validation list:
  ```python
  # Current: if event not in ["Full", "Half", "10K"]:
  # New: if event not in ["Full", "Half", "10K", "Elite", "Open"]:
  ```

- **Function:** Event column mapping (around line 247)
- **Change:** Add Elite/Open mapping:
  ```python
  events = tuple(e for e, col in [
      ("Full", "full"),
      ("Half", "half"),
      ("10K", "10K"),
      ("Elite", "elite"),  # ADD THIS
      ("Open", "open"),    # ADD THIS
  ] if segment.get(col) == 'y')
  ```
- **Priority:** 🟡 **HIGH** - Required for density analysis

---

### 6. Flow Analysis

#### `app/core/flow/flow.py`
- **Function:** Event pair generation
- **Current:** Generates Full/Half, Full/10K, Half/10K (3 pairs)
- **Change:** Add Elite/Open pair ONLY (no cross-day pairs)
- **Code Logic:**
  ```python
  # Saturday events: Elite, Open
  saturday_events = ["Elite", "Open"]
  # Sunday events: Full, Half, 10K
  sunday_events = ["Full", "Half", "10K"]
  
  # Generate pairs within same day only
  for i, event_a in enumerate(saturday_events):
      for event_b in saturday_events[i+1:]:
          pairs.append((event_a, event_b))  # Elite/Open
  
  for i, event_a in enumerate(sunday_events):
      for event_b in sunday_events[i+1:]:
          pairs.append((event_a, event_b))  # Full/Half, Full/10K, Half/10K
  ```
- **Priority:** 🟡 **HIGH** - Correct pair generation critical

---

### 7. Constants and Defaults

#### `app/utils/constants.py`
- **Variable:** `DEFAULT_START_TIMES` (around line 83)
- **Change:** Add Elite and Open start times:
  ```python
  DEFAULT_START_TIMES = {
      "Full": 420,
      "10K": 440,
      "Half": 460,
      "Elite": 480,  # ADD THIS - 08:00
      "Open": 510,   # ADD THIS - 08:30
  }
  ```
- **Priority:** 🟢 **MEDIUM** - Required for default analysis

---

## 🎨 UI and API Changes

### 8. API Endpoints - Day Filtering

#### `app/routes/api_dashboard.py`
- **Endpoint:** `/api/dashboard/summary`
- **Change:** Add `day` query parameter filtering
- **Logic:**
  ```python
  day = request.query_params.get("day")  # "5K" or "Sunday"
  if day == "5K":
      # Filter to Elite/Open events only
  elif day == "Sunday":
      # Filter to Full/Half/10K events only
  ```

#### `app/routes/api_segments.py`
- **Endpoint:** `/api/segments/geojson` and `/api/segments/summary`
- **Change:** Add `day` query parameter filtering
- **Logic:** Filter segments.geojson features by events array

#### `app/routes/api_density.py`
- **Endpoint:** `/api/density/segments`
- **Change:** Add `day` query parameter filtering

#### `app/routes/api_flow.py`
- **Endpoint:** `/api/flow/segments`
- **Change:** Add `day` query parameter filtering
- **Logic:** Only return flow pairs for selected day

- **Priority:** 🟢 **MEDIUM** - Required for UI day selectors

---

### 9. UI Components - Day Selectors

#### `templates/pages/dashboard.html`
- **Change:** Add dropdown selector: "5K (Saturday)" vs "Full/Half/10K (Sunday)"
- **JavaScript:** Filter metric tiles by selected day

#### `templates/pages/segments.html`
- **Change:** Add dropdown selector and filter map display
- **JavaScript:** Filter segments.geojson features by events array

#### `templates/pages/density.html`
- **Change:** Add dropdown selector and filter segment table

#### `templates/pages/flow.html`
- **Change:** Add dropdown selector and filter flow pairs table

- **Priority:** 🟢 **MEDIUM** - Required for UI functionality

---

## 📊 Report Generation Updates

### 10. Density Reports

#### `app/density_report.py`
- **Task:** Verify no hardcoded 3-event assumptions
- **Change:** Ensure charts/tables adapt dynamically to 5 events
- **Priority:** 🟡 **HIGH** - Reports must work with all events

#### `app/flow_report.py`
- **Task:** Verify handles 4 pairs correctly (not 3)
- **Change:** Ensure comparison views work with Saturday vs Sunday separation
- **Priority:** 🟡 **HIGH** - Flow reports must be accurate

#### `app/heatmap_generator.py`
- **Task:** Verify heatmaps generated for Elite/Open segments
- **Change:** Ensure no event filtering excludes N1-N3, O1-O3 segments
- **Priority:** 🟢 **MEDIUM** - Visualizations must be complete

---

## 🔧 Parquet & JSON Outputs

### 11. Parquet File Generation

#### Verify: `segments.parquet` Generation
- **File:** Wherever segments.parquet is created from segments.csv
- **Task:** Ensure Elite/Open segments included in parquet file
- **Priority:** 🟢 **MEDIUM** - Used in load-time analytics

### 12. Segment Metrics JSON

#### Verify: `segment_metrics.json` Generation
- **File:** Artifact export module
- **Task:** Ensure metrics calculated for all segments including Elite/Open
- **Priority:** 🟡 **HIGH** - Used by UI dashboards

---

## 🧪 Testing Requirements

### 13. Test Artifact Generation

#### Create Test: Verify segments.geojson Events Property
- **Test:** After E2E run, verify segments.geojson includes:
  - Segments N1-N3 have `events: ["Elite"]` or `events: ["Elite", "Open"]`
  - Segments O1-O3 have `events: ["Open"]` or `events: ["Elite", "Open"]`
- **Priority:** 🔴 **CRITICAL** - UI depends on this

#### Create Test: Verify Flow Pairs
- **Test:** After analysis, verify exactly 4 flow pairs:
  - Full/Half, Full/10K, Half/10K (Sunday)
  - Elite/Open (Saturday)
  - NO cross-day pairs
- **Priority:** 🔴 **CRITICAL** - Analysis correctness

---

## 📝 Deployment & Workflow

### 14. E2E Configuration

#### `e2e.py`
- **Change:** Add Elite and Open to start times configuration
- **Code:**
  ```python
  start_times = {
      "Full": 420,
      "Half": 460,
      "10K": 440,
      "Elite": 480,  # ADD THIS
      "Open": 510,   # ADD THIS
  }
  ```
- **Priority:** 🟡 **HIGH** - Required for E2E testing

---

### 15. Documentation Updates

#### `README.md`
- **Change:** Add Elite and Open to feature list
- **Change:** Note 5K events are on Saturday, others on Sunday

#### `docs/reference/QUICK_REFERENCE.md`
- **Change:** Add Elite and Open to event lists

- **Priority:** 🟢 **LOW** - Documentation completeness

---

## 🔍 Files to Search/Review (May Need Changes)

### Potential Issues to Check:
1. **Any file with hardcoded event lists** - Search for: `["Full", "Half", "10K"]`
2. **Leaflet map filtering logic** - Check `static/js/map/segments.js` for event filtering
3. **Report template engines** - Verify dynamic event handling
4. **Flagging thresholds** - Ensure appropriate for smaller participant sets (Elite)

---

## 📋 Summary Checklist

### Phase 1: Critical Fixes (Do First) 🔴
- [x] ~~Fix `app/conversion_audit.py`~~ - **ARCHIVED** (not used in runtime)
- [ ] Fix `app/core/flow/flow.py` - `_get_segment_events()` (lines 63-80)
- [ ] Fix `app/density_report.py` - Add elite/open + 5K_from_km/5K_to_km to segments_list (lines 2534-2548)
- [ ] Fix `app/core/artifacts/frontend.py` - Add Elite/Open to events list (lines 510 and 547)
- [ ] Fix `app/core/artifacts/frontend.py` - Add 5K_length to length_km calculation (lines 509 and 546)

### Phase 2: Core Infrastructure 🟡
- [ ] Update `app/core/gpx/processor.py` - Load 5KElite.gpx and 5KOpen.gpx
- [ ] Update `app/core/density/compute.py` - Event recognition and intervals
- [ ] Update `app/core/flow/flow.py` - Correct pair generation (4 pairs only)
- [ ] Update `app/utils/constants.py` - Default start times

### Phase 3: API & UI 🟢
- [ ] Update API endpoints - Add day filtering
- [ ] Update UI templates - Add day selectors
- [ ] Test day filtering on all pages

### Phase 4: Reports & Artifacts 🟡
- [ ] Review `app/density_report.py` - Dynamic event handling
- [ ] Review `app/flow_report.py` - 4 pairs support
- [ ] Review `app/heatmap_generator.py` - Elite/Open segments
- [ ] Verify segment_metrics.json includes all segments

### Phase 5: Testing & Documentation 🟢
- [ ] Update `e2e.py` - Add Elite/Open start times
- [ ] Create test for segments.geojson events property
- [ ] Create test for flow pairs (4 total)
- [ ] Update documentation

---

**Next Steps:**
1. Start with Phase 1 Critical Fixes
2. Verify artifact generation logic location
3. Test segments.geojson events property after each fix
4. Systematic testing after each phase

