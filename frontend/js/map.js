// Map Page JavaScript - Issue #249: Bin-Level Visualization
// LOD + Tooltips + Time Coupling
(function(){
  'use strict';

  // ============================================================================
  // STATE MANAGEMENT
  // ============================================================================
  
  const mapState = {
    currentWindow: 0,
    maxWindow: 79,
    manifest: null,
    isPlaying: false,
    playbackSpeed: 2,  // windows per second
    cachedWindows: new Map(),  // LRU cache: windowIdx -> GeoJSON
    maxCacheSize: 10,
    activeLayers: {
      segments: null,
      bins: null,
      binsFlagged: null
    }
  };

  // LOS color ramp (matches density report and rulebook)
  const LOS_COLORS = {
    "A": "#2ecc71",  // Green - Free flow
    "B": "#8ddc7f",  // Light green - Comfortable
    "C": "#f1c40f",  // Yellow - Moderate
    "D": "#e67e22",  // Orange - Dense
    "E": "#e74c3c",  // Red - Very dense
    "F": "#c0392b"   // Dark red - Extremely dense
  };

  let map = null;

  // ============================================================================
  // INITIALIZATION
  // ============================================================================

  async function init() {
    try {
      console.log('🗺️ Initializing map...');
      updateStatus('Initializing map...', 'loading');
      
      // Initialize Leaflet map
      console.log('  📍 Creating Leaflet map...');
      map = L.map('map').setView([45.9620, -66.6500], 13);
      
      // Add OSM base tiles
      console.log('  🗺️ Adding base tiles...');
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 20,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);
      
      // Load manifest
      console.log('  📥 Loading manifest...');
      updateStatus('Loading manifest...', 'loading');
      await loadManifest();
      console.log('  ✅ Manifest loaded');
      
      // Initialize UI controls
      console.log('  🎛️ Initializing controls...');
      setupTimeSlider();
      setupPlaybackControls();
      setupFilters();
      setupZoomLOD();
      console.log('  ✅ Controls initialized');
      
      // Load initial data (window 0)
      console.log('  📥 Loading segments layer...');
      updateStatus('Loading segments...', 'loading');
      await loadSegmentsLayer();
      console.log('  ✅ Segments loaded');
      
      console.log('  📥 Loading bins for window 0...');
      updateStatus('Loading bins...', 'loading');
      await loadBinsForWindow(mapState.currentWindow);
      console.log('  ✅ Bins loaded');
      
      updateTimeDisplay();
      updateStatus('✅ Map loaded', 'success');
      
      console.log('✅ Map initialization complete');
    } catch (error) {
      console.error('❌ Map initialization failed:', error);
      console.error('Error stack:', error.stack);
      updateStatus(`❌ Failed to load map: ${error.message}`, 'error');
    }
  }

  // ============================================================================
  // MANIFEST & DATA LOADING
  // ============================================================================

  async function loadManifest() {
    console.log('📥 Loading manifest...');
    
    try {
      const response = await fetch('/api/map/manifest');
      if (!response.ok) {
        throw new Error(`Manifest fetch failed: ${response.status}`);
      }
      
      const data = await response.json();
      if (!data.ok) {
        throw new Error('Manifest data not available');
      }
      
      mapState.manifest = data;
      mapState.maxWindow = data.window_count - 1;
      
      console.log(`✅ Manifest loaded: ${data.window_count} windows, ${data.segments.length} segments`);
      return data;
    } catch (error) {
      console.error('❌ Failed to load manifest:', error);
      throw error;
    }
  }

  async function loadSegmentsLayer() {
    console.log('📥 Loading segments layer...');
    
    try {
      // Use new /api/map/segments endpoint (Issue #249 Phase 1.5)
      const response = await fetch('/api/map/segments');
      if (!response.ok) {
        throw new Error(`Segments fetch failed: ${response.status}`);
      }
      
      const geojson = await response.json();
      if (!geojson.features || geojson.features.length === 0) {
        throw new Error('No segment features available');
      }
      
      // Create segments GeoJSON layer with GPX centerlines
      mapState.activeLayers.segments = L.geoJSON(geojson, {
        style: featStyleSegments,
        onEachFeature: (feature, layer) => {
          layer.on('click', (e) => showSegmentTooltip(e, feature));
          layer.on('mouseover', function() {
            this.setStyle({ weight: 6, opacity: 1.0 });
          });
          layer.on('mouseout', function() {
            mapState.activeLayers.segments.resetStyle(this);
          });
        }
      });
      
      // Add to map (will be controlled by LOD)
      mapState.activeLayers.segments.addTo(map);
      
      console.log(`✅ Segments layer loaded: ${geojson.features.length} segments`);
    } catch (error) {
      console.error('❌ Failed to load segments:', error);
      throw error;
    }
  }

  async function loadBinsForWindow(windowIdx) {
    console.log(`📥 Loading bins for window ${windowIdx}...`);
    
    // Get severity filter for cache key (Phase 1.5)
    const severityFilter = document.getElementById('severity-filter');
    const severityValue = severityFilter ? severityFilter.value : 'any';
    const cacheKey = `${windowIdx}_${severityValue}`;
    
    // Check cache first
    if (mapState.cachedWindows.has(cacheKey)) {
      console.log(`  ✅ Using cached data for window ${windowIdx} (severity: ${severityValue})`);
      return mapState.cachedWindows.get(cacheKey);
    }
    
    try {
      // Get current map bounds in Web Mercator meters (not pixels)
      const bounds = map.getBounds();
      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();
      
      // Convert lat/lng to Web Mercator meters (zoom level 0 = meters)
      const swMercator = L.CRS.EPSG3857.latLngToPoint(sw, 0);
      const neMercator = L.CRS.EPSG3857.latLngToPoint(ne, 0);
      
      const bbox = `${swMercator.x},${swMercator.y},${neMercator.x},${neMercator.y}`;
      
      console.log(`  📐 Bbox: ${bbox}`);
      
      // Fetch bins from server (severityValue already set above)
      const url = `/api/map/bins?window_idx=${windowIdx}&bbox=${bbox}&severity=${severityValue}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Bins fetch failed: ${response.status}`);
      }
      
      const geojson = await response.json();
      
      // Cache the result (include severity in cache key for Phase 1.5)
      manageCacheSize();
      const cacheKey = `${windowIdx}_${severityValue}`;
      mapState.cachedWindows.set(cacheKey, geojson);
      
      console.log(`✅ Loaded ${geojson.features.length} bins for window ${windowIdx}`);
      
      // Log performance metrics (Phase 1.5)
      setTimeout(() => logPerformanceMetrics(), 100);
      
      return geojson;
    } catch (error) {
      console.error(`❌ Failed to load bins for window ${windowIdx}:`, error);
      return { type: "FeatureCollection", features: [] };
    }
  }

  function manageCacheSize() {
    // LRU cache management
    if (mapState.cachedWindows.size >= mapState.maxCacheSize) {
      // Remove oldest entry
      const firstKey = mapState.cachedWindows.keys().next().value;
      mapState.cachedWindows.delete(firstKey);
      console.log(`  🗑️ Evicted window ${firstKey} from cache`);
    }
  }

  // ============================================================================
  // LOD (LEVEL OF DETAIL) MANAGEMENT
  // ============================================================================

  function setupZoomLOD() {
    map.on('zoomend', updateLOD);
    updateLOD();  // Initial LOD
  }

  function updateLOD() {
    if (!mapState.manifest) return;
    
    const z = map.getZoom();
    const lod = mapState.manifest.lod;
    
    console.log(`🔍 Zoom level: ${z}, updating LOD...`);
    
    if (z <= lod.segments_only) {
      // Z ≤ 12: Segments only
      showSegmentsOnly();
    } else if (z <= lod.flagged_bins) {
      // 12 < Z ≤ 14: Segments + flagged bins
      showSegmentsAndFlaggedBins();
    } else {
      // Z > 14: All bins
      showAllBins();
    }
  }

  function showSegmentsOnly() {
    console.log('  📍 LOD: Segments only');
    if (mapState.activeLayers.segments) map.addLayer(mapState.activeLayers.segments);
    if (mapState.activeLayers.binsFlagged) map.removeLayer(mapState.activeLayers.binsFlagged);
    if (mapState.activeLayers.bins) map.removeLayer(mapState.activeLayers.bins);
  }

  function showSegmentsAndFlaggedBins() {
    console.log('  📍 LOD: Segments + flagged bins');
    if (mapState.activeLayers.segments) map.addLayer(mapState.activeLayers.segments);
    if (mapState.activeLayers.binsFlagged) {
      map.addLayer(mapState.activeLayers.binsFlagged);
    } else {
      // Load flagged bins for current window
      loadFlaggedBinsForWindow(mapState.currentWindow);
    }
    if (mapState.activeLayers.bins) map.removeLayer(mapState.activeLayers.bins);
  }

  function showAllBins() {
    console.log('  📍 LOD: All bins');
    if (mapState.activeLayers.segments) map.addLayer(mapState.activeLayers.segments);
    if (mapState.activeLayers.binsFlagged) map.removeLayer(mapState.activeLayers.binsFlagged);
    if (mapState.activeLayers.bins) {
      map.addLayer(mapState.activeLayers.bins);
    } else {
      // Load all bins for current window
      refreshBinsForWindow();
    }
  }

  async function loadFlaggedBinsForWindow(windowIdx) {
    // Use same bbox calculation as loadBinsForWindow
    const bounds = map.getBounds();
    const sw = bounds.getSouthWest();
    const ne = bounds.getNorthEast();
    
    // Convert lat/lng to Web Mercator meters (zoom level 0 = meters)
    const swMercator = L.CRS.EPSG3857.latLngToPoint(sw, 0);
    const neMercator = L.CRS.EPSG3857.latLngToPoint(ne, 0);
    
    const bbox = `${swMercator.x},${swMercator.y},${neMercator.x},${neMercator.y}`;
    
    const url = `/api/map/bins?window_idx=${windowIdx}&bbox=${bbox}&severity=any`;
    const response = await fetch(url);
    const geojson = await response.json();
    
    if (mapState.activeLayers.binsFlagged) {
      map.removeLayer(mapState.activeLayers.binsFlagged);
    }
    
    mapState.activeLayers.binsFlagged = L.geoJSON(geojson, {
      style: featStyleBins,
      onEachFeature: (feature, layer) => {
        layer.on('click', showBinTooltip);
      }
    });
    
    if (map.getZoom() > mapState.manifest.lod.segments_only && 
        map.getZoom() <= mapState.manifest.lod.flagged_bins) {
      map.addLayer(mapState.activeLayers.binsFlagged);
    }
  }

  async function refreshBinsForWindow() {
    const geojson = await loadBinsForWindow(mapState.currentWindow);
    
    if (mapState.activeLayers.bins) {
      map.removeLayer(mapState.activeLayers.bins);
    }
    
    mapState.activeLayers.bins = L.geoJSON(geojson, {
      style: featStyleBins,
      onEachFeature: (feature, layer) => {
        layer.on('click', showBinTooltip);
      }
    });
    
    if (map.getZoom() > mapState.manifest.lod.flagged_bins) {
      map.addLayer(mapState.activeLayers.bins);
    }
  }

  // ============================================================================
  // STYLING
  // ============================================================================

  function featStyleSegments(feature) {
    const props = feature.properties || {};
    const los = props.los_class || props.max_los || "A";
    
      return {
      weight: 5,
      color: LOS_COLORS[los] || "#999",
      fillOpacity: 0.3,
      opacity: 0.8
    };
  }

  function featStyleBins(feature) {
    const props = feature.properties || {};
    const los = props.los_class || "A";
    const severity = props.flag_severity || "none";  // Issue #254: Use flag_severity
    
    // Severity-based styling (Phase 1.5)
    const severityStyles = {
      "critical": { borderColor: "#c0392b", borderWeight: 2.5, fillOpacity: 0.8 },  // Red border, high opacity
      "caution":  { borderColor: "#e67e22", borderWeight: 2.0, fillOpacity: 0.7 },  // Orange border
      "watch":    { borderColor: "#f1c40f", borderWeight: 1.5, fillOpacity: 0.6 },  // Yellow border
      "none":     { borderColor: "#333",    borderWeight: 0.5, fillOpacity: 0.4 }   // Subtle
    };
    
    const style = severityStyles[severity] || severityStyles["none"];
    
      return {
      weight: style.borderWeight,
      color: style.borderColor,
      fillColor: LOS_COLORS[los] || "#999",
      fillOpacity: style.fillOpacity,
      opacity: 0.8
    };
  }

  // ============================================================================
  // TOOLTIPS
  // ============================================================================

  function showSegmentTooltip(e, feature) {
    const props = feature.properties;
    
    // Basic segment info (from /api/map/segments)
    const html = `
      <div class="tooltip-header"><b>${props.segment_label || props.segment_id}</b></div>
      <div>Schema: ${props.schema_key || '—'} · Width: ${props.width_m ? props.width_m.toFixed(1) : '—'} m</div>
      <div>Length: ${props.length_km ? props.length_km.toFixed(2) : '—'} km (${props.from_km?.toFixed(1)} - ${props.to_km?.toFixed(1)} km)</div>
      <div class="tooltip-note">⚠️ Aggregated stats coming in next phase</div>
    `;
    
    L.popup({ className: 'segment-popup' })
      .setLatLng(e.latlng)
      .setContent(html)
      .openOn(map);
  }

  function showBinTooltip(e) {
    const props = e.target.feature.properties;
    
    // Enhanced tooltip with P90 flagging metrics (Phase 1.5 + Issue #254)
    const severity = props.flag_severity || 'none';
    const reason = props.flag_reason || 'none';
    
    // Severity badge with color
    const severityColors = {
      'critical': '#c0392b',
      'caution': '#e67e22',
      'watch': '#f1c40f',
      'none': '#95a5a6'
    };
    const sevColor = severityColors[severity] || '#95a5a6';
    const sevBadge = `<span style="background: ${sevColor}; color: white; padding: 2px 6px; border-radius: 3px; font-weight: bold;">${severity.toUpperCase()}</span>`;
    
    // Build metrics section
    let metricsHtml = `
      <div>Density: ${fmt(props.density)} p/m² (LOS ${props.los_class})</div>
      <div>Rate: ${fmt(props.rate)} p/s`;
    
    if (props.rate_per_m_per_min) {
      metricsHtml += ` (${fmt(props.rate_per_m_per_min)} p/m/min)`;
    }
    metricsHtml += `</div>`;
    
    // Utilization metrics (if available)
    if (props.util_percentile !== null && props.util_percentile !== undefined) {
      metricsHtml += `<div>Utilization: P${Math.round(props.util_percentile)}`;
      if (props.util_percent) {
        metricsHtml += ` (${Math.round(props.util_percent)}% of capacity)`;
      }
      metricsHtml += `</div>`;
    }
    
    // Flag reason (if flagged)
    let flagHtml = '';
    if (severity !== 'none') {
      flagHtml = `<div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid #ddd;">
        <strong>Flag Reason:</strong> ${reason}
      </div>`;
    }
    
    const html = `
      <div class="tooltip-header">
        <b>${props.segment_id} · ${props.start_km.toFixed(1)}-${props.end_km.toFixed(1)} km</b>
      </div>
      <div style="margin: 4px 0;">${sevBadge}</div>
      <div>Time: ${props.t_start_hhmm}–${props.t_end_hhmm} (Window ${props.window_idx})</div>
      ${metricsHtml}
      ${flagHtml}
    `;
    
    L.popup({ className: 'bin-popup' })
      .setLatLng(e.latlng)
      .setContent(html)
      .openOn(map);
  }

  function fmt(x) {
    return (x == null || isNaN(x)) ? "—" : Number(x).toFixed(3);
  }

  // Performance monitoring (Phase 1.5)
  function logPerformanceMetrics() {
    if (mapState.activeLayers.bins) {
      const binCount = mapState.activeLayers.bins.getLayers().length;
      const cacheSize = mapState.cachedWindows.size;
      const memoryUsage = performance.memory ? 
        `${Math.round(performance.memory.usedJSHeapSize / 1024 / 1024)}MB` : 'N/A';
      
      console.log(`📊 Performance: ${binCount} bins, ${cacheSize} cached windows, ${memoryUsage} memory`);
      
      // Check payload size (approximate)
      if (mapState.cachedWindows.size > 0) {
        const latestWindow = Array.from(mapState.cachedWindows.values()).pop();
        const payloadSize = JSON.stringify(latestWindow).length;
        const payloadKB = Math.round(payloadSize / 1024);
        console.log(`📦 Latest payload: ${payloadKB}KB (target: ≤800KB)`);
      }
    }
  }

  function fmtWindowToTime(windowIdx) {
    if (!mapState.manifest) return `#${windowIdx}`;
    
    const windowSeconds = mapState.manifest.window_seconds;
    // Race starts at 07:00 (7 * 3600 seconds)
    const totalSeconds = windowIdx * windowSeconds + (7 * 3600);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
  }

  // ============================================================================
  // TIME SLIDER
  // ============================================================================

  function setupTimeSlider() {
    const slider = document.getElementById('time-slider');
    if (!slider) {
      console.warn('Time slider element not found');
      return;
    }
    
    slider.max = mapState.maxWindow;
    slider.value = 0;
    
    // Debounce slider to avoid excessive requests
    let sliderTimeout = null;
    slider.addEventListener('input', (e) => {
      const newWindow = parseInt(e.target.value, 10);
      
      // Update display immediately
      mapState.currentWindow = newWindow;
      updateTimeDisplay();
      
      // Debounce actual data loading (300ms)
      clearTimeout(sliderTimeout);
      sliderTimeout = setTimeout(() => {
        onWindowChange(newWindow);
      }, 300);
    });
    
    console.log('✅ Time slider initialized');
  }

  function setupPlaybackControls() {
    const playBtn = document.getElementById('play-pause');
    if (!playBtn) {
      console.warn('Play/pause button not found');
      return;
    }
    
    playBtn.addEventListener('click', togglePlayback);
    console.log('✅ Playback controls initialized');
  }

  let playbackInterval = null;

  function togglePlayback() {
    const playBtn = document.getElementById('play-pause');
    
    if (mapState.isPlaying) {
      // Stop playback
      mapState.isPlaying = false;
      playBtn.textContent = '▶ Play';
      clearInterval(playbackInterval);
      playbackInterval = null;
    } else {
      // Start playback
      mapState.isPlaying = true;
      playBtn.textContent = '⏸ Pause';
      
      const intervalMs = 1000 / mapState.playbackSpeed;  // e.g., 500ms for 2 windows/sec
      playbackInterval = setInterval(() => {
        mapState.currentWindow++;
        
        if (mapState.currentWindow > mapState.maxWindow) {
          // Loop back to start
          mapState.currentWindow = 0;
        }
        
        const slider = document.getElementById('time-slider');
        if (slider) slider.value = mapState.currentWindow;
        
        updateTimeDisplay();
        onWindowChange(mapState.currentWindow);
      }, intervalMs);
    }
  }

  async function onWindowChange(newWindow) {
    console.log(`⏱️ Window changed to ${newWindow}`);
    
    // Reload bins for new window
    await refreshBinsForWindow();
    
    // Update flagged bins if in mid-zoom LOD
    const z = map.getZoom();
    if (z > mapState.manifest.lod.segments_only && z <= mapState.manifest.lod.flagged_bins) {
      await loadFlaggedBinsForWindow(newWindow);
    }
  }

  function updateTimeDisplay() {
    const timeDisplay = document.getElementById('time-display');
    if (timeDisplay) {
      const timeStr = fmtWindowToTime(mapState.currentWindow);
      const endWindow = mapState.currentWindow + 1 > mapState.maxWindow ? 
                        mapState.maxWindow : mapState.currentWindow + 1;
      const endTimeStr = fmtWindowToTime(endWindow);
      timeDisplay.textContent = `${timeStr}-${endTimeStr}`;
    }
  }

  // ============================================================================
  // FILTERS
  // ============================================================================

  function setupFilters() {
    // Severity filter
    const severityFilter = document.getElementById('severity-filter');
    if (severityFilter) {
      severityFilter.addEventListener('change', applyFilters);
    }
    
    // Segment prefix filter
    const prefixFilter = document.getElementById('prefix-filter');
    if (prefixFilter) {
      prefixFilter.addEventListener('change', applyFilters);
    }
    
    // LOS filter
    const losFilter = document.getElementById('los-filter');
    if (losFilter) {
      losFilter.addEventListener('change', applyFilters);
    }
    
    console.log('✅ Filters initialized');
  }

  function applyFilters() {
    // Filters are applied client-side via style updates
    // Server-side severity filtering happens in loadBinsForWindow
    console.log('🔍 Applying filters...');
    
    // Get current filter values (Phase 1.5)
    const severityFilter = document.getElementById('severity-filter');
    const prefixFilter = document.getElementById('prefix-filter');
    const losFilter = document.getElementById('los-filter');
    
    const severityValue = severityFilter ? severityFilter.value : 'any';
    const prefixValue = prefixFilter ? prefixFilter.value : 'all';
    const losValue = losFilter ? losFilter.value : 'all';
    
    console.log(`  📊 Filters: severity=${severityValue}, prefix=${prefixValue}, los=${losValue}`);
    
    // Apply client-side filters to current bins layer
    if (mapState.activeLayers.bins) {
      mapState.activeLayers.bins.eachLayer(function(layer) {
        const feature = layer.feature;
        const props = feature.properties || {};
        
        // Check if bin passes filters
        let showBin = true;
        
        // Segment prefix filter
        if (prefixValue !== 'all') {
          const segmentId = props.segment_id || '';
          showBin = showBin && segmentId.startsWith(prefixValue);
        }
        
        // LOS filter
        if (losValue !== 'all') {
          const losClass = props.los_class || 'A';
          showBin = showBin && losClass === losValue;
        }
        
        // Update layer visibility
        if (showBin) {
          layer.setStyle(featStyleBins(feature));
          layer.setOpacity(1.0);
        } else {
          layer.setOpacity(0.0);  // Hide but keep in layer for performance
        }
      });
      
      console.log(`  ✅ Applied client-side filters to bins layer`);
    }
    
    // Refresh bins with current filter settings (for server-side severity filter)
    refreshBinsForWindow();
  }

  // ============================================================================
  // UTILITY FUNCTIONS
  // ============================================================================

  function updateStatus(message, type = 'loading') {
    const statusEl = document.getElementById('status');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = `status ${type}`;
    }
  }

  // ============================================================================
  // INITIALIZATION ON DOM READY
  // ============================================================================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
