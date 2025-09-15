// Map Page JavaScript - Updated for Phase 2
(function(){
  // Configuration - loaded from server constants
  let CONFIG = {
    startTimes: {"Full": 420, "10K": 440, "Half": 460}, // Default fallback
    paceCsv: "data/runners.csv", // Default fallback
    segmentsCsv: "data/segments.csv", // Default fallback
    apiBaseUrl: "", // Will be set dynamically
    mapCenter: [45.9620, -66.6500], // Default fallback
    mapZoom: 14, // Default fallback
    tileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", // Default fallback
    tileAttribution: "&copy; OpenStreetMap contributors", // Default fallback
    maxZoom: 20, // Default fallback
    densityThresholds: { // Default fallback
      "green": 0.36,
      "yellow": 0.54,
      "orange": 0.72,
      "red": 1.08
    },
    zoneColors: { // Default fallback
      "green": "#4CAF50",
      "yellow": "#FFC107",
      "orange": "#FF9800",
      "red": "#F44336",
      "dark-red": "#B71C1C"
    }
  };

  // Zone colors - loaded from server constants
  let ZONES = CONFIG.zoneColors;

  // Load configuration from server
  async function loadConfig() {
    try {
      const response = await fetch('/api/map-config');
      if (response.ok) {
        const data = await response.json();
        if (data.ok && data.config) {
          // Update CONFIG with server values
          Object.assign(CONFIG, data.config);
          // Update ZONES with server values
          ZONES = CONFIG.zoneColors;
          console.log('Configuration loaded from server:', CONFIG);
        }
      }
    } catch (error) {
      console.warn('Failed to load configuration from server, using defaults:', error);
    }
  }

  // Global variables
  let map;
  let segmentsLayer;
  let currentMetric = 'areal';
  let isColorMode = true;
  let selectedSegment = null;
  let segmentsData = [];

  // Load segments data from JSON
  async function loadSegmentsData() {
    try {
      const response = await fetch('/api/segments');
      if (!response.ok) throw new Error('Failed to load segments data');
      const data = await response.json();
      segmentsData = data.segments || [];
      console.log('Loaded segments data:', segmentsData.length, 'segments');
      return segmentsData;
    } catch (error) {
      console.error('Error loading segments data:', error);
      return [];
    }
  }

  // Determine zone based on density value
  function determineZone(density) {
    if (density <= CONFIG.densityThresholds.green) return 'green';
    if (density <= CONFIG.densityThresholds.yellow) return 'yellow';
    if (density <= CONFIG.densityThresholds.orange) return 'orange';
    if (density <= CONFIG.densityThresholds.red) return 'red';
    return 'dark-red';
  }

  // Get zone color
  function getZoneColor(zone) {
    return ZONES[zone] || '#999999';
  }

  // Create segment popup content
  function createSegmentPopup(segment) {
    const density = currentMetric === 'areal' ? segment.metrics?.areal_density : segment.metrics?.linear_density;
    const zone = density ? determineZone(density) : 'unknown';
    const zoneColor = getZoneColor(zone);
    
    return `
      <div class="segment-popup">
        <h3>${segment.label || segment.id}</h3>
        <p><strong>Segment ID:</strong> ${segment.id}</p>
        <p><strong>LOS:</strong> <span style="color: ${zoneColor}">${segment.los || 'Unknown'}</span></p>
        <p><strong>Status:</strong> ${segment.status || 'Unknown'}</p>
        ${density ? `<p><strong>${currentMetric === 'areal' ? 'Areal' : 'Crowd'} Density:</strong> ${density.toFixed(3)}</p>` : ''}
        ${segment.metrics?.flow_rate ? `<p><strong>Flow Rate:</strong> ${segment.metrics.flow_rate}</p>` : ''}
        ${segment.notes && segment.notes.length > 0 ? `<p><strong>Notes:</strong> ${segment.notes.join(', ')}</p>` : ''}
      </div>
    `;
  }

  // Create segment marker
  function createSegmentMarker(segment) {
    if (!segment.geometry || !segment.geometry.coordinates) return null;
    
    const density = currentMetric === 'areal' ? segment.metrics?.areal_density : segment.metrics?.linear_density;
    const zone = density ? determineZone(density) : 'unknown';
    const zoneColor = getZoneColor(zone);
    
    // Create polyline from coordinates
    const latLngs = segment.geometry.coordinates.map(coord => [coord[1], coord[0]]); // Note: GeoJSON is [lng, lat]
    
    const polyline = L.polyline(latLngs, {
      color: isColorMode ? zoneColor : '#000000',
      weight: isColorMode ? 4 : 2,
      opacity: 0.8,
      className: `segment-line segment-${zone}`
    });
    
    // Add popup
    polyline.bindPopup(createSegmentPopup(segment));
    
    // Add click handler for segment details
    polyline.on('click', function() {
      showSegmentDetails(segment);
    });
    
    return polyline;
  }

  // Show segment details in sidebar
  function showSegmentDetails(segment) {
    selectedSegment = segment;
    const title = document.getElementById('selectedSegmentTitle');
    const content = document.getElementById('segmentDetailsContent');
    const details = document.getElementById('segmentDetails');
    
    if (title && content && details) {
      title.textContent = segment.label || segment.id;
      
      const density = currentMetric === 'areal' ? segment.metrics?.areal_density : segment.metrics?.linear_density;
      const zone = density ? determineZone(density) : 'unknown';
      const zoneColor = getZoneColor(zone);
      
      content.innerHTML = `
        <div class="segment-info">
          <h4>Segment Information</h4>
          <p><strong>ID:</strong> ${segment.id}</p>
          <p><strong>Label:</strong> ${segment.label || 'N/A'}</p>
          <p><strong>Schema:</strong> ${segment.schema || 'N/A'}</p>
          <p><strong>LOS:</strong> <span style="color: ${zoneColor}">${segment.los || 'Unknown'}</span></p>
          <p><strong>Status:</strong> ${segment.status || 'Unknown'}</p>
          
          <h4>Metrics</h4>
          ${density ? `<p><strong>${currentMetric === 'areal' ? 'Areal' : 'Crowd'} Density:</strong> ${density.toFixed(3)}</p>` : ''}
          ${segment.metrics?.linear_density ? `<p><strong>Linear Density:</strong> ${segment.metrics.linear_density.toFixed(3)}</p>` : ''}
          ${segment.metrics?.flow_rate ? `<p><strong>Flow Rate:</strong> ${segment.metrics.flow_rate}</p>` : ''}
          ${segment.metrics?.flow_supply ? `<p><strong>Flow Supply:</strong> ${segment.metrics.flow_supply}</p>` : ''}
          ${segment.metrics?.flow_capacity ? `<p><strong>Flow Capacity:</strong> ${segment.metrics.flow_capacity}</p>` : ''}
          
          ${segment.notes && segment.notes.length > 0 ? `
            <h4>Notes</h4>
            <ul>
              ${segment.notes.map(note => `<li>${note}</li>`).join('')}
            </ul>
          ` : ''}
        </div>
      `;
      
      details.style.display = 'block';
    }
  }

  // Update map display
  function updateMapDisplay() {
    if (!map || !segmentsLayer) return;
    
    // Clear existing segments
    segmentsLayer.clearLayers();
    
    // Add segments based on current filter
    const zoneFilter = document.getElementById('zoneFilter');
    const selectedZones = Array.from(zoneFilter.selectedOptions).map(option => option.value);
    
    segmentsData.forEach(segment => {
      const density = currentMetric === 'areal' ? segment.metrics?.areal_density : segment.metrics?.linear_density;
      const zone = density ? determineZone(density) : 'unknown';
      
      if (selectedZones.includes(zone)) {
        const marker = createSegmentMarker(segment);
        if (marker) {
          segmentsLayer.addLayer(marker);
        }
      }
    });
    
    // Update legend status
    const legendStatus = document.getElementById('legendStatus');
    if (legendStatus) {
      const activeZones = selectedZones.length;
      const totalZones = zoneFilter.options.length;
      legendStatus.textContent = `${activeZones} of ${totalZones} zones visible`;
    }
  }

  // Initialize map
  function initializeMap() {
    // Create map
    map = L.map('map').setView(CONFIG.mapCenter, CONFIG.mapZoom);
    
    // Add tile layer
    L.tileLayer(CONFIG.tileUrl, {
      maxZoom: CONFIG.maxZoom,
      attribution: CONFIG.tileAttribution
    }).addTo(map);
    
    // Create segments layer
    segmentsLayer = L.layerGroup().addTo(map);
    
    // Load and display segments
    loadSegmentsData().then(() => {
      updateMapDisplay();
      document.getElementById('status').textContent = `Loaded ${segmentsData.length} segments`;
    });
  }

  // Event handlers
  function setupEventHandlers() {
    // Metric toggle
    const metricSelect = document.getElementById('metric');
    if (metricSelect) {
      metricSelect.addEventListener('change', function() {
        currentMetric = this.value;
        updateMapDisplay();
      });
    }
    
    // Refresh button
    const refreshBtn = document.getElementById('refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function() {
        document.getElementById('status').textContent = 'Refreshing...';
        loadSegmentsData().then(() => {
          updateMapDisplay();
          document.getElementById('status').textContent = `Loaded ${segmentsData.length} segments`;
        });
      });
    }
    
    // Display mode toggle
    const colorModeBtn = document.getElementById('colorMode');
    const bwModeBtn = document.getElementById('bwMode');
    
    if (colorModeBtn && bwModeBtn) {
      colorModeBtn.addEventListener('click', function() {
        isColorMode = true;
        colorModeBtn.classList.add('active');
        bwModeBtn.classList.remove('active');
        document.getElementById('colorLegend').style.display = 'block';
        document.getElementById('bwLegend').style.display = 'none';
        updateMapDisplay();
      });
      
      bwModeBtn.addEventListener('click', function() {
        isColorMode = false;
        bwModeBtn.classList.add('active');
        colorModeBtn.classList.remove('active');
        document.getElementById('colorLegend').style.display = 'none';
        document.getElementById('bwLegend').style.display = 'block';
        updateMapDisplay();
      });
    }
    
    // Zone filter
    const zoneFilter = document.getElementById('zoneFilter');
    if (zoneFilter) {
      zoneFilter.addEventListener('change', updateMapDisplay);
    }
    
    // Show all zones
    const showAllBtn = document.getElementById('showAll');
    if (showAllBtn) {
      showAllBtn.addEventListener('click', function() {
        Array.from(zoneFilter.options).forEach(option => option.selected = true);
        updateMapDisplay();
      });
    }
    
    // Hide all zones
    const hideAllBtn = document.getElementById('hideAll');
    if (hideAllBtn) {
      hideAllBtn.addEventListener('click', function() {
        Array.from(zoneFilter.options).forEach(option => option.selected = false);
        updateMapDisplay();
      });
    }
    
    // Close segment details
    const closeBtn = document.getElementById('closeSegmentDetails');
    if (closeBtn) {
      closeBtn.addEventListener('click', function() {
        const details = document.getElementById('segmentDetails');
        if (details) {
          details.style.display = 'none';
        }
        selectedSegment = null;
      });
    }
  }

  // Initialize everything
  async function initialize() {
    await loadConfig();
    setupEventHandlers();
    initializeMap();
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }
})();
