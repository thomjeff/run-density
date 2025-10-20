# Issue #282 - UI/UX Polish - Match Canva v2 Design Mocks

**Created**: 2025-10-19  
**GitHub Issue**: https://github.com/thomjeff/run-density/issues/282  
**Parent Issue**: #279 (RF-FE-002 - New Multi-Page Web UI)  
**Project**: runflow  
**Label**: enhancement  
**Status**: Open

---

## Problem

The RF-FE-002 Step 8 implementation is **functionally correct** but has two critical UX gaps:

### 1. Visual Inconsistency
Current UI feels "bootstrap-ish" instead of matching the clean, modern Canva v2 design mocks:
- ❌ Generic styling (default browser/bootstrap look)
- ❌ Inconsistent spacing and typography
- ❌ Missing modern UI elements (rounded cards, soft shadows)
- ❌ No cohesive design system

### 2. Broken Segments Map
The Segments page map is **non-functional**:
- ❌ Shows only OpenStreetMap base tiles
- ❌ No segment lines/features visible
- ❌ Empty gray area (staring at Atlantic Ocean)
- ❌ Makes the page essentially useless

---

## Solution from ChatGPT

Apply **targeted visual polish** and **fix the Segments map** to match Canva v2 mocks without adding heavy frameworks.

---

## 1) Visual Polish - Lightweight Design System

### A. Create `static/css/app.css`

**Single CSS file** with modern design system:

**Design Tokens**:
- Colors: `--bg`, `--panel`, `--ink`, `--brand`, `--ok`, `--warn`, `--danger`
- Spacing: `--gap`, `--radius`
- Shadows: `--shadow` (soft, professional)
- LOS Colors: `--los-a` through `--los-f` (from SSOT)

**Components**:
- `.header` - Dark navigation bar (#0f172a)
- `.container` - Page container (max-width 1100px)
- `.section` - White card with rounded corners and shadow
- `.kpi-grid` - Responsive 3-column grid
- `.kpi` - KPI tile with large value + hint
- `.badge` - Pill badge with LOS colors
- `.table` - Modern table with rounded row ends
- `.map-wrap` - Fixed-height map container (360px)
- `.legend` - Map legend box
- `.status-banner` - Warning/danger banners

**Typography**: Inter font family (loaded from Google Fonts)

**Features**:
- ✅ CSS variables for consistency
- ✅ Responsive breakpoint at 900px
- ✅ Soft shadows and rounded corners
- ✅ Clean spacing (16px gap standard)
- ✅ Professional color palette

### B. SSOT Color Integration

Inject LOS colors from `reporting.yml` into CSS:

```html
<!-- templates/base.html -->
<style>
:root {
  --los-a: {{ los_colors["A"] }};
  --los-b: {{ los_colors["B"] }};
  --los-c: {{ los_colors["C"] }};
  --los-d: {{ los_colors["D"] }};
  --los-e: {{ los_colors["E"] }};
  --los-f: {{ los_colors["F"] }};
}
</style>
```

**Benefits**:
- ✅ No hardcoded colors
- ✅ Consistent with analytics
- ✅ Easy to update (change YAML, CSS updates)

### C. Update Page Templates

Apply new classes to all pages:

```html
<div class="container">
  <div class="section">
    <h2>Section Title</h2>
    <!-- content -->
  </div>
  
  <div class="section">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="value">1,898</div>
        <div class="hint">Total Participants</div>
      </div>
    </div>
  </div>
</div>
```

---

## 2) Fix Broken Segments Map

### Root Causes Identified

Map shows only tiles (no features) because:
1. ❌ GeoJSON never added to map
2. ❌ `fitBounds()` never called (default center is Atlantic)
3. ❌ Map container created before visible (needs `invalidateSize()`)
4. ❌ API possibly returning empty FeatureCollection

### Complete Map Fix

**File**: `templates/pages/segments.html`

**A. Fixed-Height Container**:
```html
<div class="section">
  <h2>Course Map</h2>
  <div id="segments-map" class="map-wrap"></div>
</div>
```

**B. Proper Initialization**:
```javascript
const map = L.map('segments-map', { 
  zoomControl: true, 
  preferCanvas: true 
});

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18, 
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Fix layout issue
setTimeout(() => map.invalidateSize(), 50);
```

**C. Load GeoJSON with Error Handling**:
```javascript
fetch('/api/segments/geojson')
  .then(r => r.json())
  .then(gj => {
    if (!gj || !gj.features || !gj.features.length) {
      console.warn('No segments found for map.');
      map.setView([45.95, -66.65], 12); // Fredericton fallback
      return;
    }
    
    const layer = L.geoJSON(gj, {
      style: f => styleByLos(f.properties.worst_los),
      onEachFeature: (f, l) => {
        // Add tooltips with segment details
      }
    }).addTo(map);
    
    // Auto-fit to features
    map.fitBounds(layer.getBounds().pad(0.15));
  })
  .catch(err => {
    console.error('Failed to load segments:', err);
    map.setView([45.95, -66.65], 12);
  });
```

**D. Style by LOS (SSOT)**:
```javascript
const LOS_COLORS = {{ los_colors | tojson }};

const styleByLos = (los) => ({
  color: (LOS_COLORS[los] || '#6b7280'),
  weight: 4,
  opacity: 0.9
});
```

**E. Add Legend**:
```javascript
const legend = L.control({position: 'bottomleft'});
legend.onAdd = function() {
  const div = L.DomUtil.create('div', 'legend');
  // Render A-F badges with SSOT colors
  return div;
};
legend.addTo(map);
```

**F. Deep-Link Support**:
```javascript
// Support ?focus=B2 in URL
const params = new URLSearchParams(location.search);
const focus = params.get('focus');
if (focus) {
  // Find and zoom to specific segment
}
```

### Debugging Steps

If map still shows no lines:
1. Hit `/api/segments/geojson` in browser
2. Check if `features: []` (upstream issue)
3. Verify `artifacts/<run_id>/ui/segments.geojson` exists
4. Check API logs for warnings

---

## 3) Density Page Integration

### Depends on Issue #280

This issue integrates with Issue #280 for:
- ✅ Heatmap PNGs
- ✅ Auto-caption text
- ✅ API returns `heatmap_png_url` and `caption`

### Template Updates

```html
<div class="section">
  <h4>Density Heatmap</h4>
  <img id="heatmap-image" 
       src="" 
       alt="Density heatmap" 
       aria-describedby="heatmap-caption"
       style="max-width:100%; border-radius:12px;" />
  
  <div id="heatmap-caption" class="caption">
    <!-- Auto-generated caption text -->
  </div>
</div>
```

---

## 4) UX Details

### A. Navigation Bar
- Dark theme (`#0f172a` background)
- Reduced height
- Active state highlighting (`.nav a.active`)
- Clean typography

### B. Status Banners
```html
<!-- Warning -->
<div class="status-banner">
  ⚠️ Action Required
</div>

<!-- Danger -->
<div class="status-banner status-danger">
  ⛑️ Critical Conditions
</div>
```

### C. Tables
- Right-align numeric columns
- LOS as pill badges (not plain text)
- Subtle hover effect
- Rounded row ends

### D. Typography
- Inter font family
- Clear hierarchy
- Proper color contrast (WCAG AA)

---

## Implementation Plan

### Phase 1: Design System (2-3 hours)
1. Create `static/css/app.css`
2. Add Google Fonts link
3. Inject LOS colors
4. Test on Dashboard

### Phase 2: Segments Map Fix (1-2 hours)
1. Update `segments.html` with fixed map code
2. Add GeoJSON loading
3. Add legend
4. Test focus query

### Phase 3: Apply to All Pages (2-3 hours)
1. Update all page templates
2. Apply new CSS classes
3. Test responsiveness

### Phase 4: UX Details (1 hour)
1. Update nav bar
2. Add status banners
3. Update tables
4. Add badges

### Phase 5: Testing (1 hour)
1. Visual QA on all pages
2. Test different screen sizes
3. Verify SSOT colors
4. Test map thoroughly

**Total**: 7-10 hours

---

## Acceptance Criteria

### Visual Polish
- [ ] Design system CSS created
- [ ] Inter font loaded
- [ ] LOS colors from SSOT
- [ ] All pages use new classes
- [ ] Navigation has dark theme

### Segments Map
- [ ] Map has fixed height (360px)
- [ ] `invalidateSize()` called
- [ ] GeoJSON features display as colored lines
- [ ] Lines styled by `worst_los`
- [ ] Tooltips show on hover
- [ ] Auto-fits to bounds
- [ ] `?focus=` works
- [ ] Legend appears
- [ ] Fallback if no features

### Density Page
- [ ] Heatmap PNG displays (from #280)
- [ ] Caption text displays (from #280)
- [ ] Caption word-wrapped
- [ ] Fallback if missing

### UX Details
- [ ] Nav height reduced
- [ ] Active item highlighted
- [ ] Numbers right-aligned
- [ ] LOS pill badges
- [ ] Row hover effect

---

## Why This Is Safe

- ✅ **No new runtime deps** (just CSS + font CDN)
- ✅ **Colors from SSOT** (`reporting.yml`)
- ✅ **Isolated changes** (Leaflet only on Segments page)
- ✅ **CSS is additive** (not replacing HTML)
- ✅ **API unchanged**
- ✅ **Easy rollback** (remove CSS file)

---

## Dependencies

**Requires**:
- Issue #280 for Density heatmaps/captions

**Independent**:
- Design system CSS
- Segments map fix
- General UX polish

---

## Priority

**Medium-High Priority**

Visual polish and working Segments map are important for:
- Professional appearance
- User trust
- Operational usability
- Stakeholder expectations

Should complete before closing Issue #279.

---

## References

- **GitHub Issue**: https://github.com/thomjeff/run-density/issues/282
- **Parent Issue**: #279 (RF-FE-002)
- **Related Issue**: #280 (Density Features)
- **Design Source**: Canva v2 mocks
- **Branch**: `feature/rf-fe-002`

---

**Status**: ✅ Issue created with complete specification from ChatGPT  
**Next Step**: Implement design system and map fix

