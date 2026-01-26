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
    'course': '#4CAF50',   // Green
    'aid': '#F44336',      // Red
    'water': '#2196F3',    // Blue
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
        .map(loc => {
            // Issue #591: Include all resource count and mins fields dynamically
            // Issue #598: Include flag fields
            const properties = {
                loc_id: loc.loc_id,
                loc_label: loc.loc_label || 'Unknown',
                loc_type: loc.loc_type || 'unknown',
                loc_start: loc.loc_start,
                loc_end: loc.loc_end,
                duration: loc.duration,
                peak_start: loc.peak_start,
                peak_end: loc.peak_end,
                zone: loc.zone,
                timing_source: loc.timing_source,
                notes: loc.notes,
                first_runner: loc.first_runner,  // Issue #483: Include first_runner
                last_runner: loc.last_runner,     // Issue #483: Include last_runner
                flag: loc.flag,                   // Issue #598: Include flag
                flagged_seg_id: loc.flagged_seg_id,  // Issue #598: Include flagged_seg_id
                flag_severity: loc.flag_severity,     // Issue #598: Include flag_severity
                flag_worst_los: loc.flag_worst_los,   // Issue #598: Include flag_worst_los
                flag_note: loc.flag_note              // Issue #598: Include flag_note
            };
            
            // Issue #591: Dynamically add all resource count and mins fields
            Object.keys(loc).forEach(key => {
                if (key.endsWith('_count') || key.endsWith('_mins')) {
                    properties[key] = loc[key];
                }
            });
            
            return {
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [parseFloat(loc.lon), parseFloat(loc.lat)]
                },
                properties: properties
            };
        });
    
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
 * Format time from hh:mm:ss to hh:mm
 * @param {string|null} timeStr - Time string in hh:mm:ss or hh:mm format
 * @returns {string|null} Formatted time in hh:mm or null
 */
function formatTimeToHHMM(timeStr) {
    if (!timeStr || timeStr === 'NA') return null;
    // If already in hh:mm format, return as-is
    if (timeStr.match(/^\d{2}:\d{2}$/)) return timeStr;
    // If in hh:mm:ss format, drop seconds
    if (timeStr.match(/^\d{2}:\d{2}:\d{2}$/)) {
        return timeStr.substring(0, 5); // Take first 5 characters (hh:mm)
    }
    return timeStr; // Fallback: return original if format unexpected
}

/**
 * Create tooltip content for location marker
 * @param {Object} properties - Location properties
 * @returns {string} HTML tooltip content
 */
function createLocationTooltip(properties) {
    const props = properties || {};
    const locType = props.loc_type || 'unknown';
    const locLabel = props.loc_label || 'Unknown';
    const locId = props.loc_id != null ? String(props.loc_id) : null;
    const heading = locId ? `${locId}-${locLabel}` : locLabel;
    const locStart = props.loc_start && props.loc_start !== 'NA' ? props.loc_start : null;
    const locEnd = props.loc_end && props.loc_end !== 'NA' ? props.loc_end : null;
    const locStartFormatted = formatTimeToHHMM(locStart);
    const locEndFormatted = formatTimeToHHMM(locEnd);
    const duration = props.duration != null && props.duration !== 'NA' ? props.duration : null;
    
    // Format timing source for tooltip (Issue #479) - shorter format for tooltip
    let timingSourceTooltip = "";
    const timingSourceRaw = props.timing_source;
    if (timingSourceRaw && timingSourceRaw.startsWith("proxy:")) {
        const proxyId = timingSourceRaw.replace("proxy:", "");
        timingSourceTooltip = `<br><span style="font-size: 11px; color: #666;">Proxy: ${proxyId}</span>`;
    }
    
    let tooltip = `
        <div style="font-family: Arial, sans-serif; font-size: 14px;">
            <strong>${heading}</strong><br>
            <strong>Type:</strong> <span style="color: ${getLocationMarkerColor(locType)}; font-weight: bold;">${locType}</span>
    `;
    
    if (locStartFormatted && locEndFormatted) {
        tooltip += `<br><strong>Operational Window:</strong> ${locStartFormatted} → ${locEndFormatted}`;
    }
    
    if (duration != null) {
        tooltip += `<br><strong>Duration:</strong> ${duration} min`;
    }
    
    // Issue #592: Add resource counts to tooltip
    const resourceCounts = [];
    Object.keys(props).forEach(key => {
        if (key.endsWith('_count')) {
            const count = props[key];
            if (count && count > 0) {
                const resource = key.replace('_count', '').toUpperCase();
                resourceCounts.push(`${resource}: ${count}`);
            }
        }
    });
    if (resourceCounts.length > 0) {
        tooltip += `<br><strong>Resources:</strong> ${resourceCounts.join(', ')}`;
    }
    
    // Issue #598: Add flag to tooltip
    const locationFlag = props.flag;
    if (locationFlag === true || locationFlag === "true" || locationFlag === "Y") {
        tooltip += `<br><strong>Flag:</strong> <span style="color: #F44336; font-weight: bold;">Y</span>`;
    }
    
    if (timingSourceTooltip) {
        tooltip += timingSourceTooltip;
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
    const locLabel = props.loc_label || 'Unknown';
    const locId = props.loc_id != null ? String(props.loc_id) : null;
    const heading = locId ? `${locId}-${locLabel}` : locLabel;
    const locStart = props.loc_start && props.loc_start !== 'NA' ? props.loc_start : null;
    const locEnd = props.loc_end && props.loc_end !== 'NA' ? props.loc_end : null;
    const locStartFormatted = formatTimeToHHMM(locStart);
    const locEndFormatted = formatTimeToHHMM(locEnd);
    const duration = props.duration != null && props.duration !== 'NA' ? props.duration : null;
    const peakStart = props.peak_start && props.peak_start !== 'NA' ? props.peak_start : null;
    const peakEnd = props.peak_end && props.peak_end !== 'NA' ? props.peak_end : null;
    const peakStartFormatted = formatTimeToHHMM(peakStart);
    const peakEndFormatted = formatTimeToHHMM(peakEnd);
    const notes = props.notes && props.notes !== 'NA' ? props.notes : null;
    
    // Format timing source (Issue #479)
    let timingSourceDisplay = "Modeled";
    const timingSourceRaw = props.timing_source;
    if (timingSourceRaw) {
        if (timingSourceRaw.startsWith("proxy:")) {
            const proxyId = timingSourceRaw.replace("proxy:", "");
            timingSourceDisplay = `Proxy: ${proxyId}`;
        } else if (timingSourceRaw === "error:proxy_not_found") {
            timingSourceDisplay = "Error: proxy not found";
        } else if (timingSourceRaw === "modeled") {
            timingSourceDisplay = "Modeled";
        } else {
            timingSourceDisplay = timingSourceRaw;
        }
    }
    
    let popup = `
        <div style="font-family: Arial, sans-serif; font-size: 14px; width: 260px;">
            <h3 style="margin: 0 0 0.5rem 0; font-size: 16px; color: #2c3e50;">${heading}</h3>
            <div style="margin-bottom: 0.5rem;">
                <strong>Type:</strong> <span style="color: ${getLocationMarkerColor(locType)}; font-weight: bold;">${locType}</span>
            </div>
    `;
    
    if (locStartFormatted && locEndFormatted) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Operational Window:</strong> ${locStartFormatted} → ${locEndFormatted}</div>`;
    }
    
    if (duration != null) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Duration:</strong> ${duration} minutes</div>`;
    }
    
    if (peakStartFormatted && peakEndFormatted) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Peak Window:</strong> ${peakStartFormatted} → ${peakEndFormatted}</div>`;
    }
    
    if (props.zone) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Zone:</strong> ${props.zone}</div>`;
    }
    
    // Issue #592: Add resource counts to popup (after Zone, before Source)
    const resourceCounts = [];
    Object.keys(props).forEach(key => {
        if (key.endsWith('_count')) {
            const count = props[key];
            if (count && count > 0) {
                const resource = key.replace('_count', '').toUpperCase();
                resourceCounts.push(`${resource}: ${count}`);
            }
        }
    });
    if (resourceCounts.length > 0) {
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Resources:</strong> ${resourceCounts.join(', ')}</div>`;
    }
    
    // Issue #598: Add flag to popup
    const locationFlag = props.flag;
    if (locationFlag === true || locationFlag === "true" || locationFlag === "Y") {
        const flaggedSegId = props.flagged_seg_id || 'N/A';
        const flagSeverity = props.flag_severity || 'N/A';
        const flagWorstLos = props.flag_worst_los || 'N/A';
        popup += `<div style="margin-bottom: 0.5rem;"><strong>Flag:</strong> <span style="color: #F44336; font-weight: bold;">Y</span> (Segment: ${flaggedSegId}, Severity: ${flagSeverity}, LOS: ${flagWorstLos})</div>`;
    }

    if (notes) {
        popup += `<div style="margin-bottom: 0.5rem; word-break: break-word;"><strong>Notes:</strong> ${notes}</div>`;
    }
    
    popup += '</div>';
    return popup;
}

/**
 * Load locations data from API
 * @returns {Promise<Object|null>} GeoJSON data or null if unavailable
 */
function getRunDayParams() {
    const params = new URLSearchParams(window.location.search);
    const dayParam = params.get('day');
    const runParam = params.get('run_id');
    const day = (dayParam || (window.runflowDay && window.runflowDay.selected) || '').toLowerCase().trim();
    const run_id = (runParam || (window.runflowDay && window.runflowDay.run_id) || '').trim();
    return { day, run_id, dayParam, runParam };
}

async function loadLocations() {
    try {
        // Get run_id and day from URL or global state
        const { day, run_id, dayParam, runParam } = getRunDayParams();
        
        if (!day || !run_id) {
            console.error('❌ Refusing to fetch locations without day+run_id', {
                href: window.location.href,
                dayParam, runParam,
                runflowDay: window.runflowDay
            });
            return null;
        }
        
        const apiUrl = `/api/locations?run_id=${encodeURIComponent(run_id)}&day=${encodeURIComponent(day)}`;
        console.log('Loading locations via API...', { apiUrl, day, run_id });
        
        const response = await fetch(apiUrl, { cache: 'no-store' });
        
        if (!response.ok) {
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data.ok || !data.locations) {
            throw new Error('Invalid response format');
        }
        
        // Issue #591: Store resources_available globally for table script to use
        if (data.resources_available && window.populateResourceFilter) {
            window.populateResourceFilter(data.resources_available);
        } else if (data.resources_available) {
            // Store for later if populateResourceFilter not yet defined
            window.pendingResourcesAvailable = data.resources_available;
        }
        
        // Convert to GeoJSON
        const geojson = convertToGeoJSON(data.locations);
        console.log(`✅ Loaded ${geojson.features.length} locations via API for day ${day}`);
        return geojson;
        
    } catch (error) {
        console.error('❌ Failed to load locations:', error.message);
        return null;
    }
}

async function loadSegmentsGeojson() {
    try {
        const { day, run_id, dayParam, runParam } = getRunDayParams();
        if (!day || !run_id) {
            console.error('❌ Refusing to fetch segments without day+run_id', {
                href: window.location.href,
                dayParam, runParam,
                runflowDay: window.runflowDay
            });
            return null;
        }
        
        const apiUrl = `/api/segments/geojson?run_id=${encodeURIComponent(run_id)}&day=${encodeURIComponent(day)}`;
        console.log('Loading segments overlay via API...', { apiUrl, day, run_id });
        
        const response = await fetch(apiUrl, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`Failed to load segments overlay: ${response.status}`);
        }
        
        const data = await response.json();
        if (!data || !data.features) {
            console.warn('⚠️ Segments overlay returned empty payload');
            return null;
        }
        
        return data;
    } catch (error) {
        console.warn('⚠️ Failed to load segments overlay:', error.message);
        return null;
    }
}

async function addSegmentsOverlay(map) {
    const geojson = await loadSegmentsGeojson();
    if (!geojson || !geojson.features || geojson.features.length === 0) {
        return;
    }
    
    const paneName = 'locations-course-overlay';
    if (!map.getPane(paneName)) {
        map.createPane(paneName);
        const pane = map.getPane(paneName);
        pane.style.zIndex = 350;
        pane.style.pointerEvents = 'none';
    }
    
    const overlayLayer = L.geoJSON(geojson, {
        pane: paneName,
        style: {
            color: '#2f9e44',
            weight: 2,
            opacity: 0.45,
            dashArray: '4 6'
        }
    });
    
    overlayLayer.addTo(map);
    window.locationsCourseOverlay = overlayLayer;
    console.log(`✅ Rendered course overlay with ${geojson.features.length} segments`);
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
            
            // Scroll into view within scrollable container (Issue #484)
            const tableContainer = document.getElementById('locations-table-container');
            if (tableContainer) {
                // Calculate scroll position to center row in container
                const containerHeight = tableContainer.clientHeight;
                const rowTop = row.offsetTop;
                const rowHeight = row.offsetHeight;
                
                // Calculate desired scroll position (center the row vertically)
                const desiredScrollTop = rowTop - (containerHeight / 2) + (rowHeight / 2);
                
                tableContainer.scrollTo({
                    top: Math.max(0, desiredScrollTop),
                    behavior: 'smooth'
                });
            } else {
                // Fallback to standard scrollIntoView
                row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
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
    
    // Only log if count changed significantly (reduce console noise)
    const prevCount = window.lastVisibleCount || 0;
    if (Math.abs(visibleFeatures.length - prevCount) > 5 || visibleFeatures.length === 0) {
        console.log(`🔍 Map bounds filter: ${visibleFeatures.length} of ${window.allLocationsFeatures.length} locations visible`);
        window.lastVisibleCount = visibleFeatures.length;
    }
    
    // Update table with filtered locations (skip zone repopulation)
    if (window.updateLocationsTableFiltered) {
        window.updateLocationsTableFiltered(visibleFeatures);
    } else if (window.updateLocationsTable) {
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
        
        // Render course overlay beneath markers
        await addSegmentsOverlay(map);
        
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
