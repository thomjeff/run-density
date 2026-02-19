/**
 * Course Mapping page: map with Street/Satellite basemap toggle.
 * Issue #732: Minimal first slice — map + basemap. Course drawing, pins, export follow.
 */

document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('course-mapping-map');
    if (!container) return;

    const loadingEl = container.querySelector('.map-loading');
    const toggleEl = document.getElementById('basemap-toggle');

    try {
        const map = initMap('course-mapping-map');

        // Add Satellite tile layer (Issue #732: Street ↔ Satellite)
        const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: '© Esri',
            maxZoom: 19
        });
        if (!map._layers) map._layers = {};
        map._layers.satellite = satelliteLayer;

        // Hide loading, show toggle
        if (loadingEl) loadingEl.remove();
        if (toggleEl) toggleEl.style.display = 'flex';

        const btnStreet = document.getElementById('btn-street');
        const btnSatellite = document.getElementById('btn-satellite');

        function setBasemap(layerKey) {
            map.eachLayer(function (layer) {
                if (layer instanceof L.TileLayer) map.removeLayer(layer);
            });
            const layer = map._layers[layerKey];
            if (layer) layer.addTo(map);
            if (btnStreet) btnStreet.classList.toggle('active', layerKey === 'carto');
            if (btnSatellite) btnSatellite.classList.toggle('active', layerKey === 'satellite');
        }

        if (btnStreet) btnStreet.addEventListener('click', function () { setBasemap('carto'); });
        if (btnSatellite) btnSatellite.addEventListener('click', function () { setBasemap('satellite'); });

        window.courseMappingMap = map;
    } catch (e) {
        console.error('Course mapping map init failed:', e);
        if (loadingEl) loadingEl.textContent = 'Failed to load map';
    }
});
