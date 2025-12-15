# 5K Support Implementation - Key Decisions Summary

**Date:** 2025-11-23  
**Status:** Planning Complete - Ready for Implementation

---

## ✅ All Design Decisions Confirmed

### 1. Event Naming Convention
- **Event Names:** `"Elite"` and `"Open"` (capitalized to match "Full", "Half", "10K")
- **CSV Columns:** Lowercase `elite` and `open` in data files
- **Internal Mapping:** CSV lowercase columns → Capitalized event names
- **Rationale:** Maintain consistency, avoid adding to existing inconsistencies

### 2. GPX Files
- **Separate Files:** `5KElite.gpx` and `5KOpen.gpx` (not single 5K.gpx)
- **Rationale:** Consistent with existing pattern (1 event = 1 GPX file)
- **Content:** Files will have identical content (same route) but separate files maintain code consistency

### 3. Start Times
- **Elite:** 08:00 = **480 minutes** from midnight
- **Open:** 08:30 = **510 minutes** from midnight
- **Default:** `{"Full": 420, "10K": 440, "Half": 460, "Elite": 480, "Open": 510}`

### 4. Temporal Separation (CRITICAL)
- **5K Events:** Saturday (Elite, Open)
- **Other Events:** Sunday (Full, Half, 10K)
- **Flow Analysis:** NO analysis between Saturday and Sunday events
- **Flow Pairs:** Only 4 pairs total:
  - Sunday (3 pairs): Full/Half, Full/10K, Half/10K
  - Saturday (1 pair): Elite/Open
- **Rationale:** Events are on different days with no overlap

### 5. Flow Analysis Constraints
- **Elite/Open Pair:** Keep for bad data detection
- **Cross-Day Pairs:** DO NOT generate (Full/Elite, Half/Open, etc.)
- **Separate Analysis Mode:** Future feature, not required for this sprint

---

## 🎨 UI Requirements

### Day-Based Filtering
All pages need drop-down selectors to filter by day:

1. **Dashboard** (`/dashboard`)
   - Selector: "5K (Saturday)" vs "Full/Half/10K (Sunday)"
   - 5K view: Show two metric tiles (Elite and Open)
   - Sunday view: Show current behavior (Full, Half, 10K)

2. **Segments** (`/segments`)
   - Selector: "5K" vs "Full/Half/10K"
   - Filter: Map and segment table by selected day

3. **Density** (`/density`)
   - Selector: "5K" vs "Full/Half/10K"
   - Filter: Segment table by selected day

4. **Flow** (`/flow`)
   - Selector: "5K" vs "Full/Half/10K"
   - Filter: Flow pairs table by selected day
   - 5K shows: Elite/Open pair only
   - Sunday shows: Full/Half, Full/10K, Half/10K pairs only

5. **Reports** (`/reports`)
   - No UI changes needed
   - Add 5K events to existing reports

---

## 📋 Implementation Checklist

### Phase 1: Critical Fixes (Do First) 🔴
- [x] ~~Fix `app/conversion_audit.py`~~ - **ARCHIVED** (not used in runtime)
- [ ] Fix `app/core/flow/flow.py` - `_get_segment_events()` (lines 63-80)
- [ ] Fix `app/density_report.py` - Add elite/open + 5K_from_km/5K_to_km (lines 2534-2548)
- [ ] Fix `app/core/artifacts/frontend.py` - Add Elite/Open to events list (lines 510, 547)
- [ ] Fix `app/core/artifacts/frontend.py` - Add 5K_length to length_km (lines 509, 546)

### Phase 2: Core Infrastructure 🟡
- [ ] Create `5KElite.gpx` and `5KOpen.gpx` files (copy from 5K.gpx)
- [ ] Update GPX processor to load both files
- [ ] Update constants: Add `"Elite": 480, "Open": 510` to DEFAULT_START_TIMES
- [ ] Update event recognition in density analysis

### Phase 3: Analysis Engines 🟡
- [ ] Update density analysis: Recognize "Elite" and "Open" events
- [ ] Update flow analysis: Add Elite/Open pair only (no cross-day pairs)
- [ ] Update conversion audit: Event detection for Elite/Open

### Phase 4: Integration & Testing 🟢
- [ ] Update E2E test configuration
- [ ] Verify flow pairs = 4 total (3 Sunday + 1 Saturday)
- [ ] Test API endpoints accept new events
- [ ] Verify segments.geojson includes Elite/Open in events property

### Phase 5: UI Updates 🟢
- [ ] Add day selector to Dashboard
- [ ] Add day selector to Segments page
- [ ] Add day selector to Density page
- [ ] Add day selector to Flow page
- [ ] Update backend APIs to accept day filter parameter

### Phase 6: Documentation 🟢
- [ ] Update README.md
- [ ] Update QUICK_REFERENCE.md
- [ ] Update event lists throughout docs

---

## 🔍 Runtime Discovery Notes

**Artifact Generation Location Confirmed:**
- File: `app/core/artifacts/frontend.py` (exists, filtered by .cursorignore)
- Runtime: Called during E2E test execution via `export_ui_artifacts()`
- Function: `generate_segments_geojson()` → `_create_segment_feature()` / `_build_segment_feature_properties()`
- Logs: "5️⃣ Generating segments.geojson..." appears in E2E output

**Key Finding:**
- Events property generated at lines 510 and 547 using list comprehension
- Logic already handles lowercase CSV columns correctly
- Need to add `"Elite"` and `"Open"` to the events list in both locations

---

## 🔑 Key Constraints

1. **No Cross-Day Flow Analysis:** Saturday and Sunday events are completely separate
2. **Capitalized Event Names:** "Elite" and "Open" (not "elite" and "open")
3. **Separate GPX Files:** Even though routes are identical, use separate files for consistency
4. **Flow Pairs:** 4 total pairs, not 10 (no cross-day combinations)
5. **Day Filtering:** All UI pages need selectors to filter by Saturday vs Sunday events

---

## ❓ Open Questions

1. **Day Field:** Should we introduce a "day" field along with time to explicitly separate Saturday vs Sunday events? (Decision deferred for now)

---

**Full Implementation Plan:** See `docs/implementation-plan-5k-support.md`  
**Status:** ✅ Ready for implementation

