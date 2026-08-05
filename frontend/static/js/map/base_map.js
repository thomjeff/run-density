/**
 * Base Leaflet map initialization and utilities
 * Shared by segments, density heatmaps, and flow visualizations
 * 
 * @file base_map.js
 * @description Common Leaflet setup for all map components
 */

/**
 * Initialize a Leaflet map with standard configuration
 * @param {string} containerId - HTML element ID for map container
 * @param {object} [options] - Optional: { zoomPosition: 'topleft' } to put zoom control on left (e.g. so topright is free for custom controls)
 * @returns {L.Map} Configured Leaflet map instance
 */
function initMap(containerId, options) {
    // Check if map already exists and clean it up
    if (window.existingMap) {
        try {
            window.existingMap.remove();
        } catch (e) {
            console.log('Map cleanup error (expected):', e.message);
        }
        window.existingMap = null;
    }
    
    // Also check if the container has any existing map instance
    const container = document.getElementById(containerId);
    if (container && container._leaflet_id) {
        try {
            container._leaflet_id = null;
        } catch (e) {
            console.log('Container cleanup error (expected):', e.message);
        }
    }
    
    const mapOptions = {};
    if (options && options.zoomPosition === 'topleft') {
        mapOptions.zoomControl = false;
    }
    // Default view centered on course area (New Brunswick, Canada)
    const map = L.map(containerId, mapOptions).setView([45.95, -66.64], 13);
    if (options && options.zoomPosition === 'topleft') {
        L.control.zoom({ position: 'topleft' }).addTo(map);
    }
    
    // Store reference to prevent double initialization
    window.existingMap = map;
    
    // Primary tile layer - Carto Voyager (richer street detail, similar to route-planning maps)
    const cartoLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors, © CARTO',
        maxZoom: 19
    });
    
    // Fallback tile layer - Carto Dark (for contrast)
    const cartoDarkLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors, © CARTO',
        maxZoom: 19
    });

    // Satellite imagery (Build + Results Street/Satellite toggle)
    const satelliteLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
            attribution: '© Esri',
            maxZoom: 19
        }
    );
    
    // Add primary layer (light, minimal styling)
    cartoLayer.addTo(map);
    
    // Store layer references for potential switching
    map._layers = {
        carto: cartoLayer,
        cartoDark: cartoDarkLayer,
        satellite: satelliteLayer
    };
    
    console.log(`Map initialized in container: ${containerId}`);
    return map;
}

/**
 * Switch map tile layer
 * @param {L.Map} map - Leaflet map instance
 * @param {string} layerType - 'carto' | 'cartoDark' | 'satellite'
 */
function switchTileLayer(map, layerType) {
    if (!map._layers || !map._layers[layerType]) {
        console.warn(`Layer type '${layerType}' not available`);
        return;
    }
    
    // Remove current layer
    map.eachLayer(function(layer) {
        if (layer instanceof L.TileLayer) {
            map.removeLayer(layer);
        }
    });
    
    // Add new layer
    map._layers[layerType].addTo(map);
    console.log(`Switched to ${layerType} tile layer`);
}

/**
 * Wire a Street / Satellite basemap toggle (same pattern as Build course mapping).
 * @param {L.Map} map
 * @param {object} [options]
 * @param {string} [options.toggleId='basemap-toggle']
 * @param {string} [options.streetBtnId='btn-street']
 * @param {string} [options.satelliteBtnId='btn-satellite']
 */
function enableBasemapToggle(map, options) {
    options = options || {};
    const toggleEl = document.getElementById(options.toggleId || 'basemap-toggle');
    const btnStreet = document.getElementById(options.streetBtnId || 'btn-street');
    const btnSatellite = document.getElementById(options.satelliteBtnId || 'btn-satellite');
    if (!map || !toggleEl) return;

    if (!map._layers) map._layers = {};
    if (!map._layers.satellite) {
        map._layers.satellite = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            { attribution: '© Esri', maxZoom: 19 }
        );
    }
    if (!map._layers.carto) {
        map._layers.carto = L.tileLayer(
            'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
            { attribution: '© OpenStreetMap contributors, © CARTO', maxZoom: 19 }
        );
    }

    L.DomEvent.disableClickPropagation(toggleEl);
    L.DomEvent.disableScrollPropagation(toggleEl);
    toggleEl.style.display = 'flex';

    function setBasemap(layerKey) {
        switchTileLayer(map, layerKey);
        if (btnStreet) btnStreet.classList.toggle('active', layerKey === 'carto');
        if (btnSatellite) btnSatellite.classList.toggle('active', layerKey === 'satellite');
    }

    if (btnStreet && !btnStreet.dataset.basemapBound) {
        btnStreet.addEventListener('click', function () { setBasemap('carto'); });
        btnStreet.dataset.basemapBound = '1';
    }
    if (btnSatellite && !btnSatellite.dataset.basemapBound) {
        btnSatellite.addEventListener('click', function () { setBasemap('satellite'); });
        btnSatellite.dataset.basemapBound = '1';
    }
}

/**
 * Create a standardized empty state control
 * @param {string} message - Message to display
 * @returns {L.Control} Leaflet control for empty state
 */
function createEmptyStateControl(message = 'No data available') {
    const emptyControl = L.control({ position: 'topleft' });
    
    emptyControl.onAdd = function() {
        const div = L.DomUtil.create('div', 'empty-map-overlay');
        div.style.cssText = `
            background: white;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-family: Arial, sans-serif;
            font-size: 14px;
            color: #666;
        `;
        div.innerHTML = message;
        return div;
    };
    
    return emptyControl;
}

// Export functions for use in other modules
window.initMap = initMap;
window.switchTileLayer = switchTileLayer;
window.enableBasemapToggle = enableBasemapToggle;
window.createEmptyStateControl = createEmptyStateControl;
