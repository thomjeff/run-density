/**
 * Segments map rendering with dual-mode data loading
 * Handles both local and cloud environments
 * 
 * @file segments.js
 * @description Segment visualization with LOS-based styling and tooltips
 */

// LOS colors from reporting.yml (SSOT)
const losColors = {
    'A': '#00B050',  // Green
    'B': '#FFC000',  // Yellow  
    'C': '#ED7D31',  // Orange
    'D': '#C00000',  // Red
    'E': '#808080'   // Grey
};

/**
 * Convert coordinates - try different approaches
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @returns {Array} [lng, lat] in WGS84
 */
function convertCoordinates(x, y) {
    // Convert Web Mercator (EPSG:3857) to WGS84 (EPSG:4326)
    // Web Mercator coordinates are in meters from the origin
    const lng = (x / 20037508.34) * 180;
    const lat = (Math.atan(Math.sinh(Math.PI * (1 - 2 * y / 20037508.34))) * 180) / Math.PI;
    
    console.log(`Converting Web Mercator: ${x}, ${y} -> WGS84: ${lng}, ${lat}`);
    return [lng, lat];
}

/**
 * Convert GeoJSON coordinates from Web Mercator to WGS84
 * @param {Array} coordinates - Array of coordinate pairs
 * @returns {Array} Converted coordinates
 */
function convertCoordinateArray(coordinates) {
    return coordinates.map(coord => {
        if (Array.isArray(coord) && typeof coord[0] === 'number') {
            return convertCoordinates(coord[0], coord[1]);
        }
        return coord;
    });
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
        console.log('Loading segments via API...');
        const response = await fetch('/api/segments/geojson');
        
        if (!response.ok) {
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log(`✅ Loaded ${data.features?.length || 0} segments via API`);
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
        <div style="font-family: Arial, sans-serif; font-size: 12px;">
            <strong>${props.seg_id || 'Unknown'} — ${props.label || 'Unnamed'}</strong><br>
            ${props.length_km || 'N/A'} km · ${props.width_m || 'N/A'} m · ${props.direction || 'N/A'}<br>
            Events: ${props.events ? props.events.join(', ') : 'N/A'}<br>
            LOS: <span style="color: ${losColors[props.worst_los] || '#999'}; font-weight: bold;">${props.worst_los || 'E'}</span>
        </div>
    `;
}

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

    // Debug: Log first few segment coordinates
    console.log('🔍 Sample segment coordinates (before conversion):');
    data.features.slice(0, 3).forEach((feature, index) => {
        if (feature.geometry && feature.geometry.coordinates) {
            console.log(`  Segment ${index + 1}:`, feature.geometry.coordinates.slice(0, 2));
        }
    });
    
    // Convert coordinates to WGS84 lat/lng
    data.features.forEach(feature => {
        if (feature.geometry && feature.geometry.coordinates) {
            feature.geometry.coordinates = convertCoordinateArray(feature.geometry.coordinates);
        }
    });
    
    // Debug: Log converted coordinates
    console.log('🔍 Sample segment coordinates (after conversion):');
    data.features.slice(0, 3).forEach((feature, index) => {
        if (feature.geometry && feature.geometry.coordinates) {
            console.log(`  Segment ${index + 1}:`, feature.geometry.coordinates.slice(0, 2));
        }
    });

    // Create segments layer with styling and interactions
    const segmentsLayer = L.geoJSON(data, {
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
    
    // Make segmentsLayer globally available for table interactions
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
            <td>${props.peak_density ? props.peak_density.toFixed(2) : 'N/A'}</td>
            <td>${props.peak_rate ? props.peak_rate.toFixed(2) : 'N/A'}</td>
        `;
        
        // Add click handler to focus on map
        row.addEventListener('click', function() {
            if (window.focusOnSegment) {
                window.focusOnSegment(props.seg_id);
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
        
        // Initialize base map
        const map = initMap('segments-map');
        
        // Make map globally available for table interactions
        window.map = map;
        
        // Render segments
        await renderSegments(map);
        
        console.log('✅ Segments map initialized successfully');
        
    } catch (error) {
        console.error('❌ Failed to initialize segments map:', error);
        
        // Show error state
        const errorControl = createEmptyStateControl('Failed to load segments map');
        errorControl.addTo(map);
    }
});
