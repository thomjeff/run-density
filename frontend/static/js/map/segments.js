/**
 * Segments map rendering with dual-mode data loading
 * Handles both local and cloud environments
 * 
 * @file segments.js
 * @description Segment visualization with LOS-based styling and tooltips
 */

// Version stamp to detect stale/cached script loads
console.log("segments.js VERSION:", "2025-12-13T21:20Z");

// LOS colors from reporting.yml (SSOT)
const losColors = {
    'A': '#4CAF50',  // Green - excellent
    'B': '#8BC34A',  // Light green - good
    'C': '#FFC107',  // Amber - acceptable
    'D': '#FF9800',  // Orange - concerning
    'E': '#FF5722',  // Red-orange - poor
    'F': '#F44336'   // Red - unacceptable
};

/**
 * TEMP FIX (Sydney milestone):
 * Deduplicate segment coordinates client-side to avoid visual jitter.
 * Backend geometry simplification will be handled post-Sydney (#330 planned).
 * 
 * @param {Array} coords - Array of coordinate pairs
 * @returns {Array} Deduplicated coordinates
 */
function cleanCoords(coords) {
    const seen = new Set();
    return coords.filter(([x, y]) => {
        const key = `${x.toFixed(6)},${y.toFixed(6)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

/**
 * Clean duplicate coordinates from a GeoJSON feature
 * @param {Object} feature - GeoJSON feature
 * @returns {Object} Feature with cleaned coordinates
 */
function cleanFeature(feature) {
    if (feature.geometry.type === "LineString") {
        feature.geometry.coordinates = cleanCoords(feature.geometry.coordinates);
    } else if (feature.geometry.type === "MultiLineString") {
        feature.geometry.coordinates = feature.geometry.coordinates.map(cleanCoords);
    }
    return feature;
}

function currentDayAndRun() {
    const urlParams = new URLSearchParams(window.location.search);
    const dayParam = urlParams.get('day');
    const runParam = urlParams.get('run_id');
    const dayFromSelect = document.getElementById('day-selector')?.value;

    // Prefer URL → selector → global → storage fallbacks
    const day = (dayParam || dayFromSelect || (window.runflowDay && window.runflowDay.selected) || localStorage.getItem('selected_day') || '')
        .toLowerCase()
        .trim();
    const run_id = runParam || (window.runflowDay && window.runflowDay.run_id) || localStorage.getItem('selected_run_id') || '';
    return { day, run_id };
}

/**
 * Load segments data with fallback strategy
 * Primary: /api/segments/geojson (cloud/local via StorageService)
 * Fallback: ./data/current/segments.geojson (local only)
 * 
 * @returns {Promise<Object|null>} GeoJSON data or null if unavailable
 */
async function loadSegments() {
    try {
        // Resolve directly from URL to avoid any timing issues
        const urlParams = new URLSearchParams(window.location.search);
        const dayParam = urlParams.get("day");
        const runParam = urlParams.get("run_id");

        let day = (dayParam || '').toLowerCase().trim();
        let run_id = (runParam || '').trim();

        // Hard guard: refuse to fetch without both values to avoid silent fallbacks
        if (!run_id || !day) {
            console.error("❌ Refusing to fetch segments without day+run_id", {
                href: window.location.href,
                dayParam,
                runParam,
                dayFromSelect: document.getElementById("day-selector")?.value,
                runflowDay: window.runflowDay
            });
            return null;
        }

        const params = new URLSearchParams();
        if (run_id) params.set('run_id', run_id);
        if (day) params.set('day', day);
        params.set('_', Date.now().toString()); // cache buster during dev
        const apiUrl = `/api/segments/geojson?${params.toString()}`;
        
        console.log('Loading segments via API...', { apiUrl, day, run_id });
        const response = await fetch(apiUrl, { cache: 'no-store' });
        
        if (!response.ok) {
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log(`✅ Loaded ${data.features?.length || 0} segments via API for day=${day || 'default'}`);
        return data;
        
    } catch (error) {
        console.warn('⚠️ API unavailable, falling back to local dataset:', error.message);
        
        try {
            const response = await fetch('./data/current/segments.geojson');
            
            if (!response.ok) {
                throw new Error(`Local file returned ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log(`✅ Loaded ${data.features?.length || 0} segments from local file`);
            return data;
            
        } catch (fallbackError) {
            console.error('❌ Both API and local fallback failed:', fallbackError.message);
            return null;
        }
    }
}

/**
 * Create segment style function for GeoJSON rendering
 * @param {Object} feature - GeoJSON feature
 * @returns {Object} Leaflet style object
 */
function getSegmentStyle(feature) {
    const los = feature.properties.worst_los || 'E';
    const color = losColors[los] || '#999999';
    
    return {
        color: color,
        weight: 3,
        opacity: 0.8,
        fillOpacity: 0.1
    };
}

/**
 * Create tooltip content for segment
 * @param {Object} properties - Segment properties
 * @returns {string} HTML tooltip content
 */
function createTooltipContent(properties) {
    const props = properties || {};
    
    return `
        <div style="font-family: Arial, sans-serif; font-size: 14px;">
            <strong>${props.seg_id || 'Unknown'} — ${props.label || 'Unnamed'}</strong><br>
            ${props.length_km || 'N/A'} km · ${props.width_m || 'N/A'} m · ${props.direction || 'N/A'}<br>
            Events: ${props.events ? props.events.join(', ') : 'N/A'}<br>
            LOS: <span style="color: ${losColors[props.worst_los] || '#999'}; font-weight: bold;">${props.worst_los || 'E'}</span>
        </div>
    `;
}

// Use var to avoid duplicate declaration errors if script is re-evaluated
var segmentsLayer = window.segmentsLayer || null;

/**
 * Render segments on map with LOS-based styling
 * @param {L.Map} map - Leaflet map instance
 * @returns {Promise<void>}
 */
async function renderSegments(map) {
    console.log('🔄 Loading segment data...');
    const data = await loadSegments();
    
    if (!data || !data.features || data.features.length === 0) {
        console.warn('⚠️ No segment data available');
        
        // Show empty state overlay
        const emptyControl = createEmptyStateControl('No segments available');
        emptyControl.addTo(map);
        return;
    }

    console.log(`🔄 Rendering ${data.features.length} segments...`);

    // Issue #477: Coordinates are already in WGS84 from backend API
    // No conversion needed - backend handles UTM → WGS84 transformation
    // Only clean duplicate coordinates to avoid visual jitter
    data.features.forEach(feature => {
        if (feature.geometry && feature.geometry.coordinates) {
            const originalCount = feature.geometry.coordinates.length;
            // Clean duplicate coordinates (still needed for visual quality)
            feature = cleanFeature(feature);
            const cleanedCount = feature.geometry.coordinates.length;
            
            // Log deduplication effect for segments with significant reduction
            if (originalCount > cleanedCount && originalCount > 10) {
                console.log(`🧹 Cleaned ${feature.properties.seg_id}: ${originalCount} → ${cleanedCount} coordinates (${((originalCount - cleanedCount) / originalCount * 100).toFixed(1)}% reduction)`);
            }
        }
    });

    // Remove prior layer if exists (stale day)
    if (window.segmentsLayer) {
        map.removeLayer(window.segmentsLayer);
    }

    // Remove prior layer if exists (stale day)
    if (segmentsLayer) {
        map.removeLayer(segmentsLayer);
    }

    // Create segments layer with styling and interactions
    segmentsLayer = L.geoJSON(data, {
        style: getSegmentStyle,
        onEachFeature: function(feature, layer) {
            // Bind tooltip with segment metadata
            const tooltipContent = createTooltipContent(feature.properties);
            layer.bindTooltip(tooltipContent, {
                permanent: false,
                direction: 'top',
                offset: [0, -10],
                className: 'segment-tooltip'
            });
            
            // Add hover effects
            layer.on('mouseover', function(e) {
                e.target.setStyle({
                    weight: 5,
                    opacity: 1.0
                });
            });
            
            layer.on('mouseout', function(e) {
                e.target.setStyle({
                    weight: 3,
                    opacity: 0.8
                });
            });
            
            // Add click handler for table highlighting
            layer.on('click', function(e) {
                const segmentId = feature.properties.seg_id;
                if (window.highlightSegmentInTable) {
                    window.highlightSegmentInTable(segmentId);
                }
            });
        }
    });

    // Add segments to map
    segmentsLayer.addTo(map);
    
    // Make filtering functions globally available
    window.filterMapToSegment = filterMapToSegment;
    window.clearMapFilter = clearMapFilter;
    window.segmentsLayer = segmentsLayer;
    
    // Fit map to segments bounds with padding
    if (data.features.length > 0) {
        const bounds = segmentsLayer.getBounds();
        console.log('🗺️ Segment bounds:', bounds);
        console.log('🗺️ Map center before fitBounds:', map.getCenter());
        
        map.fitBounds(bounds, { 
            padding: [20, 20],
            maxZoom: 16
        });
        
        console.log('🗺️ Map center after fitBounds:', map.getCenter());
        console.log('🗺️ Map zoom after fitBounds:', map.getZoom());
    }
    
    console.log(`✅ Rendered ${data.features.length} segments with LOS colors`);
    
    // Hide the loading overlay
    const loadingOverlay = document.querySelector('.map-loading');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
        console.log('✅ Hidden loading overlay');
    }
    
    // Update the table with segment data
    updateTable(data.features);
    
    // Log LOS distribution for debugging
    const losCounts = {};
    data.features.forEach(feature => {
        const los = feature.properties.worst_los || 'E';
        losCounts[los] = (losCounts[los] || 0) + 1;
    });
    console.log('📊 LOS distribution:', losCounts);
}

/**
 * Re-render segments when day/run_id changes (e.g., selector change)
 */
async function refreshSegmentsOnDayChange() {
    if (!window.map) return;
    // Clear existing layer
    if (window.segmentsLayer) {
        window.segmentsLayer.remove();
        window.segmentsLayer = null;
    }
    await renderSegments(window.map);
}

/**
 * Filter map to show only the selected segment
 * @param {string} segmentId - ID of the segment to show
 */
function filterMapToSegment(segmentId) {
    if (!window.segmentsLayer) {
        console.warn('Segments layer not available');
        return;
    }
    
    console.log(`🔍 Filtering map to show only segment: ${segmentId}`);
    
    // Hide all segments first
    window.segmentsLayer.eachLayer(function(layer) {
        layer.setStyle({ opacity: 0, fillOpacity: 0 });
    });
    
    // Show only the selected segment
    window.segmentsLayer.eachLayer(function(layer) {
        const feature = layer.feature;
        if (feature && feature.properties && feature.properties.seg_id === segmentId) {
            // Restore original styling for the selected segment
            const style = getSegmentStyle(feature);
            layer.setStyle(style);
            
            // Fit map to this segment's bounds
            const bounds = layer.getBounds();
            if (bounds.isValid()) {
                window.map.fitBounds(bounds, { 
                    padding: [20, 20],
                    maxZoom: 18
                });
                console.log(`✅ Focused map on segment ${segmentId}`);
            }
        }
    });
    
    // Highlight the selected row in the table
    highlightTableRow(segmentId);
    
    // Show clear filter button and update status
    updateFilterUI(segmentId);

    // Show heatmap preview if available
    showHeatmapPreview(segmentId);
}

/**
 * Clear map filter to show all segments
 */
function clearMapFilter() {
    if (!window.segmentsLayer) {
        console.warn('Segments layer not available');
        return;
    }
    
    console.log('🔄 Clearing map filter - showing all segments');
    
    // Show all segments with original styling
    window.segmentsLayer.eachLayer(function(layer) {
        const feature = layer.feature;
        if (feature) {
            const style = getSegmentStyle(feature);
            layer.setStyle(style);
        }
    });
    
    // Fit map to all segments bounds
    if (window.segmentsLayer.getBounds().isValid()) {
        window.map.fitBounds(window.segmentsLayer.getBounds(), { 
            padding: [20, 20],
            maxZoom: 16
        });
    }
    
    // Clear table row highlighting
    clearTableRowHighlight();
    
    // Hide clear filter button and update status
    updateFilterUI(null);

    // Hide heatmap preview
    hideHeatmapPreview();
}

/**
 * Highlight a specific row in the table
 * @param {string} segmentId - ID of the segment to highlight
 */
function highlightTableRow(segmentId) {
    // Clear any existing highlights
    clearTableRowHighlight();
    
    // Find and highlight the target row
    const rows = document.querySelectorAll('#segments-table tbody tr');
    rows.forEach(row => {
        const firstCell = row.querySelector('td');
        if (firstCell && firstCell.textContent.trim() === segmentId) {
            row.classList.add('selected-row');
            row.style.backgroundColor = '#e3f2fd';
            row.style.cursor = 'pointer';
            console.log(`✅ Highlighted table row for segment ${segmentId}`);
        }
    });
}

/**
 * Clear table row highlighting
 */
function clearTableRowHighlight() {
    const rows = document.querySelectorAll('#segments-table tbody tr');
    rows.forEach(row => {
        row.classList.remove('selected-row');
        row.style.backgroundColor = '';
        row.style.cursor = 'pointer';
    });
}

/**
 * Update the filter UI (status text only - Issue #532: Clear Filter button removed)
 * @param {string|null} segmentId - ID of the filtered segment, or null if no filter
 */
function updateFilterUI(segmentId) {
    // Issue #532: Clear Filter button removed - users can unselect row to clear filter
    // No UI updates needed since button is removed
}

/**
 * Attempt to show heatmap preview for a segment
 * Looks for runflow/{run_id}/{day}/ui/heatmaps/{seg_id}.png
 */
async function showHeatmapPreview(segmentId) {
    const overlay = document.getElementById('heatmap-overlay');
    const img = document.getElementById('heatmap-image');
    const status = document.getElementById('heatmap-status');

    if (!overlay || !img || !status) return;

    const urlParams = new URLSearchParams(window.location.search);
    const day = (urlParams.get('day') || '').toLowerCase().trim();
    const runId = (urlParams.get('run_id') || '').trim();
    if (!day || !runId) {
        status.textContent = 'Missing day/run context.';
        img.style.display = 'none';
        overlay.style.display = 'block';
        return;
    }

    const candidates = [
        `${segmentId}.png`,
        `${segmentId.toLowerCase()}.png`,
        `${day}_${segmentId}.png`,
        `${day}_${segmentId.toLowerCase()}.png`,
        `${segmentId}_heatmap.png`,
        `${segmentId.toLowerCase()}_heatmap.png`
    ];

    let foundUrl = null;
    const bases = [
        // Preferred mount: FastAPI mounts RUNFLOW_ROOT at /heatmaps
        // Issue #580: Updated path to visualizations/ subdirectory
        `/heatmaps/${runId}/${day}/ui/visualizations/`,
        `/heatmaps/${runId}/${day}/ui/heatmaps/`,
        `/heatmaps/${runId}/heatmaps/`,
        `/heatmaps/${runId}/ui/heatmaps/`,
        // Legacy direct paths
        `/runflow/${runId}/${day}/ui/visualizations/`,
        `/runflow/${runId}/${day}/ui/heatmaps/`,
        `/runflow/${runId}/heatmaps/`,
        `/runflow/${runId}/ui/heatmaps/`
    ];

    for (const base of bases) {
        for (const name of candidates) {
            const url = `${base}${name}?_=${Date.now()}`;
            try {
                const headResp = await fetch(url, { method: 'HEAD', cache: 'no-store' });
                if (headResp.ok) {
                    foundUrl = url;
                    break;
                }
            } catch (e) {
                // continue to next candidate/base
            }
        }
        if (foundUrl) break;
    }

    if (!foundUrl) {
        status.textContent = 'No heatmap available for this segment.';
        img.style.display = 'none';
        overlay.style.display = 'block';
        return;
    }

    img.src = foundUrl;
    img.style.display = 'block';
    status.textContent = `Heatmap for ${segmentId}`;
    overlay.style.display = 'block';
}

function hideHeatmapPreview() {
    const overlay = document.getElementById('heatmap-overlay');
    const img = document.getElementById('heatmap-image');
    const status = document.getElementById('heatmap-status');
    if (overlay) overlay.style.display = 'none';
    if (img) img.style.display = 'none';
    if (status) status.textContent = 'Select a segment to view heatmap.';
}

/**
 * Update the segments table with data
 * @param {Array} features - GeoJSON features array
 */
function updateTable(features) {
    const tbody = document.querySelector('#segments-table tbody');
    if (!tbody) {
        console.warn('Table body not found');
        return;
    }
    
    tbody.innerHTML = '';
    
    features.forEach(feature => {
        const props = feature.properties;
        const row = document.createElement('tr');
        
        row.innerHTML = `
            <td>${props.seg_id || 'Unknown'}</td>
            <td>${props.label || 'Unnamed'}</td>
            <td>${props.length_km || 'N/A'}</td>
            <td>${props.width_m || 'N/A'}</td>
            <td>${props.direction || 'N/A'}</td>
            <td>${props.events ? props.events.join(', ') : 'N/A'}</td>
            <td><span class="badge-los badge-${props.worst_los || 'E'}">${props.worst_los || 'E'}</span></td>
            <td style="max-width: 400px; word-wrap: break-word;">${props.description || 'No description available'}</td>
        `;
        
        // Add click handler for table-to-map filtering
        row.addEventListener('click', function() {
            const segmentId = props.seg_id;
            
            // Check if this row is already selected
            if (row.classList.contains('selected-row')) {
                // If already selected, clear the filter
                clearMapFilter();
            } else {
                // If not selected, filter map to this segment
                filterMapToSegment(segmentId);
            }
        });
        
        // Add hover effects
        row.addEventListener('mouseenter', function() {
            if (!row.classList.contains('selected-row')) {
                row.style.backgroundColor = '#f5f5f5';
            }
        });
        
        row.addEventListener('mouseleave', function() {
            if (!row.classList.contains('selected-row')) {
                row.style.backgroundColor = '';
            }
        });
        
        tbody.appendChild(row);
    });
    
    console.log(`✅ Updated table with ${features.length} segments`);
}

/**
 * Initialize segments map when DOM is ready
 */
document.addEventListener('DOMContentLoaded', async function() {
    const mapContainer = document.getElementById('segments-map');
    if (!mapContainer) {
        console.error('❌ Segments map container not found');
        return;
    }

    try {
        console.log('🚀 Initializing segments map...');
        
        // If map already exists (reload), just refresh data; otherwise init
        if (!window.map) {
            const map = initMap('segments-map');
            window.map = map;
        }
        
        // Render/refresh segments for current day/run_id
        await renderSegments(window.map);
        
        // If day selector exists, trigger refresh on change to re-fetch correct day/run_id
        const daySelector = document.getElementById('day-selector');
        if (daySelector) {
            daySelector.addEventListener('change', async () => {
                await refreshSegmentsOnDayChange();
            });
        }
        
        console.log('✅ Segments map initialized successfully');
        
    } catch (error) {
        console.error('❌ Failed to initialize segments map:', error);
        
        // Show error state
        const errorControl = createEmptyStateControl('Failed to load segments map');
        errorControl.addTo(map);
    }
});

// Handle bfcache / soft navigation cases: refresh data when page is shown
window.addEventListener('pageshow', async () => {
    if (window.map) {
        await refreshSegmentsOnDayChange();
    }
});

// Also trigger a delayed refresh after load to ensure correct day/run_id is used
setTimeout(async () => {
    if (window.map) {
        await refreshSegmentsOnDayChange();
    }
}, 200);
