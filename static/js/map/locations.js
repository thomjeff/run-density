/**
 * Locations map rendering with interactive table integration
 * 
 * @file locations.js
 * @description Location point visualization with type-based styling and tooltips
 * Issue #478: Add Interactive Map to Locations Report Table
 */

// Location type colors (from requirements)
const locationTypeColors = {
    'traffic': '#808080',  // Gray
    'course': '#2196F3',   // Blue
    'aid': '#F44336',      // Red
    'water': '#4CAF50',    // Green
    'marshal': '#FF9800'   // Orange
};

/**
 * Convert locations JSON data to GeoJSON format
 * @param {Array} locations - Array of location objects from API
 * @returns {Object} GeoJSON FeatureCollection
 */
function convertToGeoJSON(locations) {
    const features = locations
        .filter(loc => loc.lat != null && loc.lon != null && !isNaN(loc.lat) && !isNaN(loc.lon))
        .map(loc => ({
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [parseFloat(loc.lon), parseFloat(loc.lat)]
            },
            properties: {
                loc_id: loc.loc_id,
                loc_label: loc.loc_label || 'Unknown',
                loc_type: loc.loc_type || 'unknown',
                loc_start: loc.loc_start,
                loc_end: loc.loc_end,
                duration: loc.duration,
                peak_start: loc.peak_start,
                peak_end: loc.peak_end,
                zone: loc.zone,
                notes: loc.notes
            }
        }));
    
    return {
        type: 'FeatureCollection',
        features: features
    };
}

/**
 * Get marker color based on location type
 * @param {string} locType - Location type
 * @returns {string} Color hex code
 */
function getLocationMarkerColor(locType) {
    return locationTypeColors[locType?.toLowerCase()] || '#999999';
}

/**
 * Create tooltip content for location marker
 * @param {Object} properties - Location properties
 * @returns {string} HTML tooltip content
 */
function createLocationTooltip(properties) {
    const props = properties || {};
    const locType = props.loc_type || 'unknown';
    const locStart = props.loc_start && props.loc_start !== 'NA' ? props.loc_start : null;
    const locEnd = props.loc_end && props.loc_end !== 'NA' ? props.loc_end : null;
    const duration = props.duration != null && props.duration !== 'NA' ? props.duration : null;
    
    let tooltip = `
        <div style="font-family: Arial, sans-serif; font-size: 14px;">
            <strong>${props.loc_label || 'Unknown'}</strong><br>
            <span style="color: ${getLocationMarkerColor(locType)}; font-weight: bold;">${locType}</span>
    `;
    
    if (locStart && locEnd) {
        tooltip += `<br>${locStart} → ${locEnd}`;
    }
    
    if (duration != null) {
        tooltip += `<br>Duration: ${duration} min`;
    }
    
    tooltip += '</div>';
    return tooltip;
}

/**
 * Create popup content for location marker
 * @param {Object} properties - Location properties
 * @returns {string} HTML popup content
 */
function createLocationPopup(properties) {
    const props = properties || {};
    const locType = props.loc_type || 'unknown';
    const locStart = props.loc_start && props.loc_start !== 'NA' ? props.loc_start : null;
    const locEnd = props.loc_end && props.loc_end !== 'NA' ? props.loc_end : null;
    const duration = props.duration != null && props.duration !== 'NA' ? props.duration : null;
    const peakStart = props.peak_start && props.peak_start !== 'NA' ? props.peak_start : null;
    const peakEnd = props.peak_end && props.peak_end !== 'NA' ? props.peak_end : null;
    
    let popup = `
        <div style="font-family: Arial, sans-serif; font-size: 14px; min-width: 200px;">
            <h3 style="margin: 0 0 0.5rem 0; font-size: 16px; color: #2c3e50;">${props.loc_label || 'Unknown'}</h3>
            <div style="margin-bottom: 0.5rem;">
                <strong>Type:</strong> <span style="color: ${getLocationMarkerColor(locType)}; font-weight: bold;">${locType}</span>
            </div>
    `;
    
    if (props.loc_id != null) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>ID:</strong> ${props.loc_id}</div>`;
    }
    
    if (locStart && locEnd) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Operational Window:</strong><br>${locStart} → ${locEnd}</div>`;
    }
    
    if (duration != null) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Duration:</strong> ${duration} minutes</div>`;
    }
    
    if (peakStart && peakEnd) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Peak Window:</strong><br>${peakStart} → ${peakEnd}</div>`;
    }
    
    if (props.zone) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Zone:</strong> ${props.zone}</div>`;
    }
    
    popup += '</div>';
    return popup;
}

/**
 * Load locations data from API
 * @returns {Promise<Object|null>} GeoJSON data or null if unavailable
 */
async function loadLocations() {
    try {
        console.log('Loading locations via API...');
        const response = await fetch('/api/locations');
        
        if (!response.ok) {
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data.ok || !data.locations) {
            throw new Error('Invalid response format');
        }
        
        // Convert to GeoJSON
        const geojson = convertToGeoJSON(data.locations);
        console.log(`✅ Loaded ${geojson.features.length} locations via API`);
        return geojson;
        
    } catch (error) {
        console.error('❌ Failed to load locations:', error.message);
        return null;
    }
}

/**
 * Render locations on map with type-based styling
 * @param {L.Map} map - Leaflet map instance
 * @returns {Promise<void>}
 */
async function renderLocations(map) {
    console.log('🔄 Loading location data...');
    const data = await loadLocations();
    
    if (!data || !data.features || data.features.length === 0) {
        console.warn('⚠️ No location data available');
        
        // Show empty state overlay
        const emptyControl = createEmptyStateControl('No locations available');
        emptyControl.addTo(map);
        
        // Hide loading overlay
        const loadingOverlay = document.querySelector('.map-loading');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
        return;
    }

    console.log(`🔄 Rendering ${data.features.length} locations...`);

    // Create markers layer (use featureGroup for getBounds support)
    const markersLayer = L.featureGroup();
    
    // Store markers by loc_id for table interactions
    const markersByLocId = {};
    
    data.features.forEach(feature => {
        const props = feature.properties;
        const [lon, lat] = feature.geometry.coordinates;
        const locType = props.loc_type?.toLowerCase() || 'unknown';
        const color = getLocationMarkerColor(locType);
        
        // Create circle marker
        const marker = L.circleMarker([lat, lon], {
            radius: 8,
            fillColor: color,
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });
        
        // Store feature data on marker for later use
        marker.feature = feature;
        
        // Bind tooltip (hover)
        const tooltipContent = createLocationTooltip(props);
        marker.bindTooltip(tooltipContent, {
            permanent: false,
            direction: 'top',
            offset: [0, -10],
            className: 'location-tooltip'
        });
        
        // Bind popup (click)
        const popupContent = createLocationPopup(props);
        marker.bindPopup(popupContent, {
            maxWidth: 300,
            className: 'location-popup'
        });
        
        // Add hover effects
        marker.on('mouseover', function(e) {
            e.target.setStyle({
                radius: 10,
                weight: 3
            });
        });
        
        marker.on('mouseout', function(e) {
            e.target.setStyle({
                radius: 8,
                weight: 2
            });
        });
        
        // Add click handler for table highlighting
        marker.on('click', function(e) {
            const locId = props.loc_id;
            if (window.highlightLocationInTable) {
                window.highlightLocationInTable(locId);
            }
        });
        
        // Store marker reference
        markersByLocId[props.loc_id] = marker;
        
        // Add to layer
        marker.addTo(markersLayer);
    });

    // Add markers layer to map
    markersLayer.addTo(map);
    
    // Make layers globally available for interactions
    window.locationsLayer = markersLayer;
    window.locationsMarkersByLocId = markersByLocId;
    
    // Make filtering functions globally available
    window.filterMapToLocation = filterMapToLocation;
    window.clearMapFilter = clearMapFilter;
    window.resetMapView = resetMapView;
    
    // Store initial bounds for reset functionality
    // Calculate bounds manually from coordinates (more reliable than getBounds)
    if (data.features.length > 0) {
        const lats = data.features.map(f => f.geometry.coordinates[1]);
        const lons = data.features.map(f => f.geometry.coordinates[0]);
        const bounds = L.latLngBounds(
            [Math.min(...lats), Math.min(...lons)],
            [Math.max(...lats), Math.max(...lons)]
        );
        window.locationsInitialBounds = bounds;
        map.fitBounds(bounds, { padding: [20, 20], maxZoom: 16 });
        console.log('✅ Fitted map to all locations using manual bounds calculation');
    }
    
    console.log(`✅ Rendered ${data.features.length} locations with type-based colors`);
    
    // Hide the loading overlay
    const loadingOverlay = document.querySelector('.map-loading');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
        console.log('✅ Hidden loading overlay');
    }
    
    // Store all features globally for bounds filtering
    window.allLocationsFeatures = data.features;
    
    // Update the table with location data (if function exists)
    // Wait a bit to ensure the table script has loaded
    setTimeout(() => {
        if (window.updateLocationsTable) {
            window.updateLocationsTable(data.features);
        } else {
            // Fallback: if updateLocationsTable doesn't exist, trigger table load
            console.log('⚠️ updateLocationsTable not available, table will load independently');
        }
    }, 100);
}

/**
 * Filter map to show only the selected location
 * @param {number|string} locId - ID of the location to show
 */
function filterMapToLocation(locId) {
    if (!window.locationsLayer || !window.locationsMarkersByLocId) {
        console.warn('Locations layer not available');
        return;
    }
    
    console.log(`🔍 Filtering map to show only location: ${locId}`);
    
    const targetMarker = window.locationsMarkersByLocId[locId];
    if (!targetMarker) {
        console.warn(`Location ${locId} not found`);
        return;
    }
    
    // Dim all markers
    window.locationsLayer.eachLayer(function(marker) {
        marker.setStyle({
            fillOpacity: 0.3,
            opacity: 0.5
        });
    });
    
    // Highlight selected marker
    targetMarker.setStyle({
        fillOpacity: 1.0,
        opacity: 1.0,
        radius: 10,
        weight: 3
    });
    
    // Pan and zoom to selected location (programmatic move - disable bounds filtering temporarily)
    const latlng = targetMarker.getLatLng();
    isProgrammaticMapMove = true;
    window.map.setView(latlng, 17, {
        animate: true,
        duration: 0.5
    });
    // Re-enable bounds filtering after animation completes
    setTimeout(() => {
        isProgrammaticMapMove = false;
    }, 600);
    
    // Open popup
    targetMarker.openPopup();
    
    // Highlight the selected row in the table
    if (window.highlightLocationInTable) {
        window.highlightLocationInTable(locId);
    }
    
    // Show clear filter button and update status
    updateFilterUI(locId);
}

/**
 * Clear map filter to show all locations
 */
function clearMapFilter() {
    if (!window.locationsLayer) {
        console.warn('Locations layer not available');
        return;
    }
    
    console.log('🔄 Clearing map filter - showing all locations');
    
    // Restore all markers to original styling
    window.locationsLayer.eachLayer(function(marker) {
        if (marker.feature) {
            const props = marker.feature.properties || {};
            const locType = props.loc_type?.toLowerCase() || 'unknown';
            const color = getLocationMarkerColor(locType);
            
            marker.setStyle({
                radius: 8,
                fillColor: color,
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            });
        }
    });
    
    // Close any open popups
    window.locationsLayer.eachLayer(function(marker) {
        marker.closePopup();
    });
    
    // Fit map to all locations bounds (programmatic move - disable bounds filtering temporarily)
    if (window.locationsInitialBounds && window.locationsInitialBounds.isValid()) {
        isProgrammaticMapMove = true;
        window.map.fitBounds(window.locationsInitialBounds, { 
            padding: [20, 20],
            maxZoom: 16
        });
        // Re-enable bounds filtering after animation completes
        setTimeout(() => {
            isProgrammaticMapMove = false;
            // Now filter table based on the new bounds
            filterTableByMapBounds();
        }, 600);
    }
    
    // Clear table row highlighting
    if (window.clearLocationTableHighlight) {
        window.clearLocationTableHighlight();
    }
    
    // Restore full table (show all locations)
    if (window.allLocationsFeatures && window.updateLocationsTable) {
        window.updateLocationsTable(window.allLocationsFeatures);
    }
    
    // Hide clear filter button and update status
    updateFilterUI(null);
}

/**
 * Reset map view to show all locations
 */
function resetMapView() {
    if (!window.locationsInitialBounds || !window.locationsInitialBounds.isValid()) {
        console.warn('Initial bounds not available');
        return;
    }
    
    console.log('🔄 Resetting map view to show all locations');
    
    clearMapFilter();
}

/**
 * Highlight a specific row in the table
 * @param {number|string} locId - ID of the location to highlight
 */
function highlightLocationInTable(locId) {
    // Clear any existing highlights
    if (window.clearLocationTableHighlight) {
        window.clearLocationTableHighlight();
    }
    
    // Find and highlight the target row
    const rows = document.querySelectorAll('#locations-table tbody tr');
    rows.forEach(row => {
        const firstCell = row.querySelector('td');
        if (firstCell && firstCell.textContent.trim() == locId) {
            row.classList.add('selected-row');
            row.style.backgroundColor = '#e3f2fd';
            row.style.cursor = 'pointer';
            
            // Scroll into view
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            console.log(`✅ Highlighted table row for location ${locId}`);
        }
    });
}

/**
 * Clear table row highlighting
 */
function clearLocationTableHighlight() {
    const rows = document.querySelectorAll('#locations-table tbody tr');
    rows.forEach(row => {
        row.classList.remove('selected-row');
        row.style.backgroundColor = '';
        row.style.cursor = 'pointer';
    });
}

/**
 * Update the filter UI (button visibility and status text)
 * @param {number|string|null} locId - ID of the filtered location, or null if no filter
 */
function updateFilterUI(locId) {
    const filterControls = document.getElementById('map-filter-controls');
    const clearBtn = document.getElementById('clear-filter-btn');
    const statusSpan = document.getElementById('filter-status');
    
    if (locId) {
        // Show filter controls overlay and update status
        if (filterControls) {
            filterControls.style.display = 'block';
        }
        if (statusSpan) {
            statusSpan.textContent = `Showing only location ${locId}`;
            statusSpan.style.color = '#007bff';
        }
    } else {
        // Hide filter controls overlay
        if (filterControls) {
            filterControls.style.display = 'none';
        }
    }
}

// Flag to track programmatic map movements (to avoid filtering during table row clicks)
let isProgrammaticMapMove = false;

/**
 * Filter table rows based on current map bounds
 * Only shows locations that are currently visible in the map viewport
 */
function filterTableByMapBounds() {
    // Skip filtering if this is a programmatic map movement (e.g., from table row click)
    if (isProgrammaticMapMove) {
        return;
    }
    
    if (!window.map || !window.allLocationsFeatures) {
        return;
    }
    
    const bounds = window.map.getBounds();
    if (!bounds || !bounds.isValid()) {
        return;
    }
    
    // Find locations within current map bounds
    const visibleFeatures = window.allLocationsFeatures.filter(feature => {
        const [lon, lat] = feature.geometry.coordinates;
        return bounds.contains([lat, lon]);
    });
    
    console.log(`🔍 Map bounds filter: ${visibleFeatures.length} of ${window.allLocationsFeatures.length} locations visible`);
    
    // Update table with filtered locations
    if (window.updateLocationsTable) {
        window.updateLocationsTable(visibleFeatures);
    }
}

/**
 * Debounced version of filterTableByMapBounds to avoid excessive updates while panning
 */
let boundsFilterTimeout = null;
function debouncedFilterTableByMapBounds() {
    if (boundsFilterTimeout) {
        clearTimeout(boundsFilterTimeout);
    }
    boundsFilterTimeout = setTimeout(() => {
        filterTableByMapBounds();
    }, 150); // 150ms debounce delay
}

/**
 * Initialize locations map when DOM is ready
 */
document.addEventListener('DOMContentLoaded', async function() {
    const mapContainer = document.getElementById('locations-map');
    if (!mapContainer) {
        console.error('❌ Locations map container not found');
        return;
    }

    try {
        console.log('🚀 Initializing locations map...');
        
        // Initialize base map
        const map = initMap('locations-map');
        
        // Make map globally available for table interactions
        window.map = map;
        
        // Render locations
        await renderLocations(map);
        
        // Make table interaction functions globally available
        window.highlightLocationInTable = highlightLocationInTable;
        window.clearLocationTableHighlight = clearLocationTableHighlight;
        
        // Add event listeners for map pan/zoom to filter table
        map.on('moveend', debouncedFilterTableByMapBounds);
        map.on('zoomend', debouncedFilterTableByMapBounds);
        
        console.log('✅ Locations map initialized successfully with bounds filtering');
        
    } catch (error) {
        console.error('❌ Failed to initialize locations map:', error);
        
        // Show error state
        const errorControl = createEmptyStateControl('Failed to load locations map');
        errorControl.addTo(window.map || initMap('locations-map'));
    }
});
