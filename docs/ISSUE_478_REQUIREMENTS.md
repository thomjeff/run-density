# Issue #478: Add Interactive Map to Locations Report Table

## Overview
Add an interactive Leaflet map to the locations report page, similar to the segments page pattern, with bidirectional interaction between the map and table.

## Requirements

### 1. Map Data Source
- **Use existing `/api/locations` endpoint** and convert to GeoJSON client-side
- Data already structured per location with lat/lon
- Keeps API surface smaller
- Use a `convertToGeoJSON()` helper on the client (similar to segments pattern)

### 2. Map Markers
- Use **circle markers or icons**, styled by `loc_type`:
  - `traffic`: gray
  - `course`: blue
  - `aid`: red
  - `water`: green
  - `marshal`: orange (or yellow if too close to aid/water visually)
- Use consistent visual legend or badge style (same colors as table, if any)
- Icons are optional — color alone is sufficient for now unless existing icon sets are available

### 3. Interaction Behavior
- **Match segments page pattern exactly:**
  - Click table row → highlight map marker and pan/zoom to it
  - Click map marker → highlight corresponding row in table (scroll into view)
  - Optional: Filter toggle ("Show only selected") to hide other table rows when marker is selected
- Debounce map events if needed for performance

### 4. Map Bounds
- **Auto-fit to show all locations** on initial load
- When specific location selected, zoom in to appropriate level (e.g., zoom 16–17)
- Provide a "Reset View" button to return to full bounds

### 5. Additional Features
- **Hover tooltips** with:
  - `loc_label`
  - `loc_type`
  - `loc_start → loc_end` (if available)
  - `duration` in minutes
- **Click popups** with same information
- Popups should mirror the most relevant fields already visible in the table

## Implementation Notes

### Files to Create/Modify
1. **New file**: `static/js/map/locations.js` - Similar to `segments.js`
   - Load locations from `/api/locations`
   - Convert to GeoJSON client-side
   - Render markers with type-based styling
   - Handle table ↔ map interactions
   - Implement tooltips and popups

2. **Modify**: `templates/pages/locations.html`
   - Add map container (similar to segments page)
   - Include Leaflet CSS/JS (if not already included)
   - Include `base_map.js` and new `locations.js`
   - Add "Reset View" button

3. **Reference Implementation**: `static/js/map/segments.js`
   - Use as pattern for structure and interaction logic

### Technical Details
- Use Leaflet.js (already in use for segments)
- Use `base_map.js` for map initialization
- Follow existing code style and patterns
- Ensure responsive design matches segments page

## Related Issues
- **Issue #277**: Original locations feature implementation
- **Segments page**: Reference implementation for map + table pattern

## Status
Requirements documented - Ready for implementation
