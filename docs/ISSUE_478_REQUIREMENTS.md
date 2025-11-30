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
✅ **RESOLVED** - Implementation complete and tested

## Implementation Summary

### Commits
- `64cd3f6` - Issue #478: Add Interactive Map to Locations Report Table (initial implementation)
- `bc1b9c2` - Fix: Use L.featureGroup instead of L.layerGroup for getBounds support
- `5c23b30` - Fix: Add error handling for getBounds with fallback manual calculation
- `602d500` - Fix: Add static directory mount to docker-compose for hot reload
- `dbb3cc9` - Fix: Use manual bounds calculation instead of getBounds() for reliability
- `4f36bd5` - Feature: Add map pan/zoom → table filtering

### Implementation Challenges & Solutions

#### Challenge 1: Docker Static File Serving (Hot Reload)
**Problem**: After implementing the map JavaScript, changes to `static/js/map/locations.js` were not reflected in the browser. The Docker container was serving cached/old versions of static files.

**Root Cause**: The `static` directory was not volume-mounted in `docker-compose.yml`, so local file changes were not propagating to the running container.

**Solution**: Added volume mount for static files:
```yaml
volumes:
  - ./static:/app/static
```

**Lesson**: Always verify Docker volume mounts for development hot-reloading, especially for static assets that are frequently modified during development.

---

#### Challenge 2: Leaflet LayerGroup getBounds() Method
**Problem**: Initial implementation used `L.layerGroup()` which doesn't support `getBounds()`. This caused `TypeError: markersLayer.getBounds is not a function` when trying to fit map bounds to all locations.

**Initial Fix Attempt**: Changed to `L.featureGroup()` which does support `getBounds()`, but the error persisted due to Docker caching (see Challenge 1).

**Final Solution**: Implemented manual bounds calculation using `L.latLngBounds()` and raw coordinates, which is more reliable and doesn't depend on layer methods:
```javascript
const lats = data.features.map(f => f.geometry.coordinates[1]);
const lons = data.features.map(f => f.geometry.coordinates[0]);
const bounds = L.latLngBounds(
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)]
);
```

**Lesson**: When working with Leaflet layers, prefer manual bounds calculation for point data rather than relying on layer methods, especially when dealing with feature groups that may have timing issues.

---

#### Challenge 3: Map Pan/Zoom → Table Filtering
**Problem**: Requirement to filter table rows based on current map bounds when user pans or zooms was initially missing from implementation.

**Solution**: 
1. Store all location features globally (`window.allLocationsFeatures`)
2. Add event listeners for `moveend` and `zoomend` events
3. Implement debounced filtering (150ms delay) to avoid excessive updates while panning
4. Add flag to skip filtering during programmatic map movements (table row clicks, reset view)

**Key Implementation Details**:
- Debouncing prevents performance issues during continuous panning
- Programmatic move flag prevents filtering conflicts when table row clicks trigger map movements
- Full table restoration when clearing filters ensures consistent UX

**Lesson**: For interactive map features, always consider both user-initiated and programmatic map movements. Use debouncing for performance-critical event handlers.

---

#### Challenge 4: Docker Build Cache Corruption
**Problem**: During testing, Docker build failed with error: `failed to solve: failed to prepare extraction snapshot... parent snapshot does not exist: not found`

**Solution**: Cleared Docker build cache and rebuilt from scratch:
```bash
docker system prune -f
docker-compose build --no-cache
```

**Lesson**: Docker build cache can become corrupted, especially after multiple rebuilds. When encountering snapshot errors, clear cache and rebuild without cache.

---

### Testing Results

✅ **All features tested and working:**
- Map loads with all 82 location markers
- Type-based marker styling (traffic=gray, course=blue, etc.)
- Table row click → map zooms to location and shows popup
- Map marker click → opens popup with location details
- Reset View button restores full bounds and shows all locations
- Map pan/zoom → table filters to show only visible locations (38 of 82 after zoom in)
- Tooltips and popups display correct location information

### Files Modified

1. **Created**: `static/js/map/locations.js` (603 lines)
   - Location map rendering logic
   - GeoJSON conversion
   - Type-based marker styling
   - Table ↔ map bidirectional interactions
   - Bounds-based table filtering

2. **Modified**: `templates/pages/locations.html`
   - Added map container and Leaflet integration
   - Added Reset View button
   - Integrated map scripts

3. **Modified**: `docker-compose.yml`
   - Added static directory volume mount for hot reload

### Branch
- `issue-478-interactive-locations-map`

### Related Documentation
- Reference implementation: `static/js/map/segments.js`
- Base map utilities: `static/js/map/base_map.js`
