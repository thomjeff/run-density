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
 * @returns {L.Map} Configured Leaflet map instance
 */
function initMap(containerId) {
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
    
    // Default view centered on course area (New Brunswick, Canada)
    const map = L.map(containerId).setView([45.95, -66.64], 13);
    
    // Store reference to prevent double initialization
    window.existingMap = map;
    
    // Primary tile layer - OpenStreetMap
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    });
    
    // Fallback tile layer - Carto Light (minimal styling)
    const cartoLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors, © CARTO',
        maxZoom: 19
    });
    
    // Add primary layer
    osmLayer.addTo(map);
    
    // Store layer references for potential switching
    map._layers = {
        osm: osmLayer,
        carto: cartoLayer
    };
    
    console.log(`Map initialized in container: ${containerId}`);
    return map;
}

/**
 * Switch map tile layer
 * @param {L.Map} map - Leaflet map instance
 * @param {string} layerType - 'osm' or 'carto'
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
window.createEmptyStateControl = createEmptyStateControl;
