# Issue #479 Implementation Plan

## Clarifying Questions & Answers

### Q1: CSV Output
**Question**: Should `timing_source` be included in the CSV output, or only in the API/UI?

**Answer**: Included in CSV output.

---

### Q2: Default for Non-Traffic Locations
**Question**: For course/water/aid locations, should `timing_source` default to `"modeled"` or be omitted/null?

**Answer**: Default to `"modeled"` for all non-traffic locations.

---

### Q3: UI Display Format
**Question**: For the "Source" column in the UI, should it show:
- Full value: `"proxy:2"`
- Short: `"proxy"`
- Descriptive: `"proxy (loc 2)"` or `"End time derived from location 2"`

**Answer**: Descriptive format: `"End time derived from location 2"`

---

### Q4: Error Handling
**Question**: If `proxy_loc_id` points to a location that doesn't exist or hasn't been processed yet, should we:
- Leave `loc_end`/`duration` as `None` and log a warning?
- Set `timing_source="error:proxy_not_found"`?

**Answer**: Set `timing_source="error:proxy_not_found"` and log error.

---

### Q5: Validation
**Question**: Should we add a precheck that rejects `proxy_loc_id` for non-traffic locations, or just log a warning and ignore it?

**Answer**: Log warning and ignore (don't use proxy logic for non-traffic).

---

## Implementation Plan

### Backend Changes (`app/location_report.py`)

1. **Add `timing_source` field to all report rows:**
   - Initialize as `"modeled"` for all locations
   - Update to `"proxy:{proxy_loc_id}"` for traffic locations with valid proxy
   - Set to `"error:proxy_not_found"` if proxy lookup fails

2. **After processing all course/water/aid locations:**
   - Build lookup dictionary: `{loc_id: report_row}` for all processed locations
   - Iterate traffic locations
   - For each traffic location with `proxy_loc_id`:
     - Look up proxy location in dictionary
     - If found and has `loc_end`: 
       - Copy `loc_end` from proxy
       - Calculate `duration = loc_end - loc_start` (in minutes)
       - Set `timing_source="proxy:{proxy_loc_id}"`
     - If not found or missing `loc_end`:
       - Set `timing_source="error:proxy_not_found"`
       - Log error
       - Leave `loc_end`/`duration` as `None`

3. **Validation:**
   - If `proxy_loc_id` is provided for non-traffic locations: log warning and ignore

4. **Include `timing_source` in CSV output**

### UI Changes (`templates/pages/locations.html`)

1. **Add "Source" column to table** (after "Peak Window")
2. **Display logic:**
   - If `timing_source` starts with `"proxy:"`: Extract ID and show `"End time derived from location {id}"`
   - If `timing_source == "error:proxy_not_found"`: Show `"Error: proxy not found"`
   - If `timing_source == "modeled"` or missing: Show `"Modeled"`
3. **Update tooltips/popups** to include source information

### Data Structure
- `locations.csv` already has `proxy_loc_id` column (column 15)
- Traffic locations have `proxy_loc_id` values (e.g., loc_id=1 → proxy_loc_id=2, loc_id=17 → proxy_loc_id=16)
- Proxy references point to course locations that will have calculated `loc_end` values

### Files to Modify
1. `app/location_report.py` - Add proxy logic after main processing loop
2. `templates/pages/locations.html` - Add Source column and display logic
3. `static/js/map/locations.js` - Update popups/tooltips to show source (if needed)
