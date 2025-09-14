// Map Page JavaScript
(function(){
  const ZONES = {
    "green":"#4CAF50",
    "yellow":"#FFC107",
    "orange":"#FF9800",
    "red":"#F44336",
    "dark-red":"#B71C1C"
  };

  // Initialize map centered on a default location (can be overridden)
  const map = L.map('map').setView([45.9620, -66.6500], 14);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 20, 
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // We'll fetch real segment data from the API
  let segmentsGeoJSON = null;
  let binsGeoJSON = null;

  let currentLayer = null;
  let currentSummary = null;
  let currentViewMode = 'segments';

  function updateStatus(message, type = 'loading') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
  }

  function updateLegendStatus() {
    const zoneFilter = document.getElementById('zoneFilter');
    const selectedZones = Array.from(zoneFilter.selectedOptions).map(opt => opt.value);
    const legendStatus = document.getElementById('legendStatus');
    
    if (selectedZones.length === 0) {
      legendStatus.textContent = 'No zones visible';
      legendStatus.style.color = '#d32f2f';
    } else if (selectedZones.length === 5) {
      legendStatus.textContent = 'All zones visible';
      legendStatus.style.color = '#388e3c';
    } else {
      legendStatus.textContent = `${selectedZones.length}/5 zones visible`;
      legendStatus.style.color = '#f57c00';
    }
  }

  function styleFor(seg) {
    const zone = (seg && seg.zone) || 'green';
    
    // Check if this zone should be visible
    const zoneFilter = document.getElementById('zoneFilter');
    const selectedZones = Array.from(zoneFilter.selectedOptions).map(opt => opt.value);
    
    if (!selectedZones.includes(zone)) {
      // Hide this segment by making it transparent
      return {
        color: ZONES[zone] || '#4CAF50',
        weight: 6,
        opacity: 0.1,
        fillOpacity: 0.1
      };
    }
    
    // Check display mode
    const isBWMode = document.getElementById('bwMode').classList.contains('active');
    
    if (isBWMode) {
      // Black and white mode with different line weights and patterns
      const bwStyles = {
        "green": { color: "#000000", weight: 2, opacity: 0.8, dashArray: null },
        "yellow": { color: "#000000", weight: 3, opacity: 0.8, dashArray: null },
        "orange": { color: "#000000", weight: 4, opacity: 0.9, dashArray: "5,5" },
        "red": { color: "#000000", weight: 5, opacity: 0.9, dashArray: "10,5" },
        "dark-red": { color: "#000000", weight: 6, opacity: 1.0, dashArray: "15,5" }
      };
      
      return bwStyles[zone] || bwStyles["green"];
    } else {
      // Color mode
      return {
        color: ZONES[zone] || '#4CAF50',
        weight: 6,
        opacity: 0.9
      };
    }
  }

  function styleForBin(bin) {
    const densityLevel = bin.density_level || 'A';
    const density = bin.density || 0;
    const convergencePoint = bin.convergence_point || false;
    
    // Map density levels to colors
    const densityColors = {
      "A": "#4CAF50",    // Green
      "B": "#8BC34A",    // Light Green
      "C": "#FFC107",    // Yellow
      "D": "#FF9800",    // Orange
      "E": "#F44336",    // Red
      "F": "#B71C1C"     // Dark Red
    };
    
    const baseColor = densityColors[densityLevel] || "#4CAF50";
    
    // Check if this density level should be visible
    const zoneFilter = document.getElementById('zoneFilter');
    const selectedZones = Array.from(zoneFilter.selectedOptions).map(opt => opt.value);
    
    // Map density levels to zone names for filtering
    const levelToZone = {
      "A": "green",
      "B": "green", 
      "C": "yellow",
      "D": "orange",
      "E": "red",
      "F": "dark-red"
    };
    
    const zone = levelToZone[densityLevel] || "green";
    
    if (!selectedZones.includes(zone)) {
      return {
        color: baseColor,
        weight: 2,
        opacity: 0.1,
        fillOpacity: 0.1
      };
    }
    
    // Check display mode
    const isBWMode = document.getElementById('bwMode').classList.contains('active');
    
    if (isBWMode) {
      // Black and white mode for bins
      return {
        color: "#000000",
        weight: 1,
        opacity: 0.6,
        fillOpacity: 0.3,
        dashArray: convergencePoint ? "3,3" : null
      };
    } else {
      // Color mode for bins
      return {
        color: baseColor,
        weight: 2,
        opacity: 0.7,
        fillOpacity: 0.4,
        dashArray: convergencePoint ? "3,3" : null
      };
    }
  }

  function renderBins(binsData) {
    // Performance timing
    const startTime = performance.now();
    
    // Remove existing layer if any
    if (currentLayer) {
      map.removeLayer(currentLayer);
    }

    // Pre-calculate styling for better performance
    const binStyles = new Map();
    
    // Create new layer for bins with optimized rendering
    currentLayer = L.geoJSON(binsData, {
      style: f => {
        const bin = f.properties;
        const binKey = `${bin.segment_id}-${bin.bin_index}`;
        
        // Use cached styles if available
        if (binStyles.has(binKey)) {
          return binStyles.get(binKey);
        }
        
        const style = styleForBin(bin);
        binStyles.set(binKey, style);
        return style;
      },
      onEachFeature: function (feature, layer) {
        const bin = feature.properties;
        const segmentId = bin.segment_id;
        const binIndex = bin.bin_index;
        const density = bin.density || 0;
        const densityLevel = bin.density_level || 'A';
        const rsiScore = bin.rsi_score || 0;
        const convergencePoint = bin.convergence_point || false;
        
        // Build tooltip text with optimized string building
        const tooltipParts = [
          `<div class="seg-label">${segmentId} — Bin ${binIndex}</div>`,
          `<div>Density: <b>${density.toFixed(2)}</b> pax/m² (${densityLevel})</div>`,
          `<div>RSI Score: <b>${rsiScore.toFixed(3)}</b></div>`
        ];
        
        if (convergencePoint) {
          tooltipParts.push(`<div style="color: #FF5722; font-weight: bold;">⚠️ Convergence Point</div>`);
        }
        
        // Add overtakes and co-presence data if available
        if (bin.overtakes && Object.keys(bin.overtakes).length > 0) {
          const overtakesStr = Object.entries(bin.overtakes).map(([k,v]) => `${k}:${v}`).join(', ');
          tooltipParts.push(`<div>Overtakes: ${overtakesStr}</div>`);
        }
        if (bin.co_presence && Object.keys(bin.co_presence).length > 0) {
          const coPresenceStr = Object.entries(bin.co_presence).map(([k,v]) => `${k}:${v}`).join(', ');
          tooltipParts.push(`<div>Co-presence: ${coPresenceStr}</div>`);
        }
        
        const tooltipText = tooltipParts.join('');
        layer.bindTooltip(tooltipText, { sticky: true });
        
        // Optimized event handlers
        layer.on('mouseover', () => {
          layer.setStyle({ weight: 3, opacity: 0.9 });
        });
        layer.on('mouseout', () => {
          layer.setStyle({ weight: 2, opacity: 0.7 });
        });
      }
    }).addTo(map);

    // Fit bounds if we have features
    try { 
      if (binsData.features.length > 0) {
        map.fitBounds(currentLayer.getBounds(), {padding:[30,30]});
      }
    } catch(_) {}

    // Performance timing
    const endTime = performance.now();
    const renderTime = Math.round(endTime - startTime);

    // Update UI with performance info
    const meta = document.getElementById('meta');
    meta.textContent = `Bin-Level View: ${binsData.features.length} bins (${renderTime}ms)`;
    
    updateStatus(`Rendered ${binsData.features.length} bins in ${renderTime}ms`, 'success');
  }

  function renderMap(geojson, summary) {
    // Remove existing layer if any
    if (currentLayer) {
      map.removeLayer(currentLayer);
    }

    currentSummary = summary;
    const bySeg = {};
    (summary.segments || []).forEach(s => { bySeg[s.seg_id] = s; });

    // Debug logging
    console.log('Density summary segments:', Object.keys(bySeg));
    console.log('GeoJSON features:', geojson.features.map(f => f.properties.seg_id));
    console.log('D2 in density data:', bySeg['D2']);
    console.log('D2 in GeoJSON:', geojson.features.find(f => f.properties.seg_id === 'D2'));

    // Check for segments with coordinate issues (from GPX processor)
    const problematicSegments = [];
    geojson.features.forEach(feature => {
      if (feature.properties.coord_issue) {
        problematicSegments.push(feature.properties.seg_id);
        console.warn(`⚠️ Segment ${feature.properties.seg_id} has coordinate issues`);
      }
    });

    // Create new layer
    currentLayer = L.geoJSON(geojson, {
      style: f => {
        const seg = bySeg[f.properties.seg_id];
        console.log(`Styling ${f.properties.seg_id}:`, seg);
        
        // Special styling for problematic segments
        if (problematicSegments.includes(f.properties.seg_id)) {
          return {
            color: '#FF0000', // Red to highlight the issue
            weight: 8,
            opacity: 0.8,
            dashArray: '5,5' // Dashed line to show it's problematic
          };
        }
        
        return styleFor(seg);
      },
      onEachFeature: function (feature, layer) {
        const seg = bySeg[feature.properties.seg_id];
        const label = feature.properties.segment_label || (seg && seg.segment_label) || feature.properties.seg_id;
        const zone = seg ? seg.zone : 'green';
        const areal = seg ? seg.areal_density : null;
        const crowd = seg ? seg.crowd_density : null;
        
        // Add warning for problematic segments
        let tooltipText = `<div class="seg-label">${feature.properties.seg_id} — ${label}</div>`;
        if (problematicSegments.includes(feature.properties.seg_id)) {
          tooltipText += `<div style="color: red; font-weight: bold;">⚠️ COORDINATE ISSUE</div>`;
        }
        tooltipText += `zone: <b>${zone}</b><br/>areal: ${areal ?? '—'} pax/m<br/>crowd: ${crowd ?? '—'} pax/m²`;
        
        layer.bindTooltip(tooltipText, { sticky:true });
        
        layer.on('mouseover', () => layer.setStyle({ weight: 8 }));
        layer.on('mouseout',  () => layer.setStyle({ weight: 6 }));
      }
    }).addTo(map);

    // Fit bounds if we have features
    try { 
      if (geojson.features.length > 0) {
        map.fitBounds(currentLayer.getBounds(), {padding:[30,30]});
      }
    } catch(_) {}

    // Update UI
    const metricSel = document.getElementById('metric');
    const meta = document.getElementById('meta');
    metricSel.value = (summary.zone_by || 'areal');
    meta.textContent = `Zoning: ${summary.zone_by || 'areal'}`;
    
    // Show warning for problematic segments
    if (problematicSegments.length > 0) {
      updateStatus(`Loaded ${summary.segments?.length || 0} segments (${problematicSegments.length} with coordinate issues)`, 'error');
      console.warn(`⚠️ Segments with coordinate issues: ${problematicSegments.join(', ')}`);
    } else {
      updateStatus(`Loaded ${summary.segments?.length || 0} segments`, 'success');
    }
  }

  async function fetchSegments() {
    try {
      const response = await fetch('/api/segments.geojson?paceCsv=data/runners.csv&segmentsCsv=data/segments.csv&startTimes={"Full":420,"10K":440,"Half":460}');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      segmentsGeoJSON = await response.json();
      return segmentsGeoJSON;
    } catch (error) {
      console.error('Error fetching segments:', error);
      // Return fallback data
      return {
        "type": "FeatureCollection",
        "features": [
          { 
            "type":"Feature",
            "properties": { "seg_id":"A1a", "segment_label":"Start to Queen/Regent" },
            "geometry": { 
              "type":"LineString",
              "coordinates": [
                [-66.6528, 45.9611], [-66.6505, 45.9620]
              ]
            }
          },
          { 
            "type":"Feature",
            "properties": { "seg_id":"A2a", "segment_label":"Start to Queen/Regent" },
            "geometry": { 
              "type":"LineString",
              "coordinates": [
                [-66.6528, 45.9611], [-66.6505, 45.9620]
              ]
            }
          },
          { 
            "type":"Feature",
            "properties": { "seg_id":"A3a", "segment_label":"Start to Queen/Regent" },
            "geometry": { 
              "type":"LineString",
              "coordinates": [
                [-66.6528, 45.9611], [-66.6505, 45.9620]
              ]
            }
          }
        ]
      };
    }
  }

  async function fetchBins() {
    try {
      updateStatus('Loading bin data...', 'loading');
      
      // Add performance timing
      const startTime = performance.now();
      
      const response = await fetch('/api/flow-bins', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          paceCsv: "data/runners.csv",
          segmentsCsv: "data/segments.csv",
          startTimes: {"Full": 420, "10K": 440, "Half": 460}
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const binsData = await response.json();
      
      if (!binsData.ok) {
        throw new Error(`API Error: ${binsData.message || 'Unknown error'}`);
      }

      // Convert to GeoJSON format for rendering with performance optimizations
      const geojson = {
        "type": "FeatureCollection",
        "features": []
      };

      // Pre-calculate constants for better performance
      const baseLat = 45.9620;
      const baseLon = -66.6500;
      const latOffset = 0.001;
      const lonOffset = 0.001;
      const binSize = 0.0005;

      // Process all segments and their bins with optimized loops
      const segments = binsData.segments || {};
      const segmentIds = Object.keys(segments);
      
      for (let i = 0; i < segmentIds.length; i++) {
        const segmentId = segmentIds[i];
        const segmentData = segments[segmentId];
        const bins = segmentData.bins || [];
        
        for (let j = 0; j < bins.length; j++) {
          const bin = bins[j];
          
          // Create a simple rectangular polygon for each bin with optimized calculations
          const binCenterLat = baseLat + (bin.bin_index * latOffset);
          const binCenterLon = baseLon + (bin.bin_index * lonOffset);
          
          // Pre-calculate polygon coordinates
          const halfSize = binSize / 2;
          const coordinates = [[
            [binCenterLon - halfSize, binCenterLat - halfSize],
            [binCenterLon + halfSize, binCenterLat - halfSize],
            [binCenterLon + halfSize, binCenterLat + halfSize],
            [binCenterLon - halfSize, binCenterLat + halfSize],
            [binCenterLon - halfSize, binCenterLat - halfSize]
          ]];
          
          geojson.features.push({
            "type": "Feature",
            "properties": {
              "segment_id": segmentId,
              "segment_label": segmentData.segment_label,
              "bin_index": bin.bin_index,
              "start_km": bin.start_km,
              "end_km": bin.end_km,
              "density": bin.density,
              "density_level": bin.density_level,
              "overtakes": bin.overtakes,
              "co_presence": bin.co_presence,
              "rsi_score": bin.rsi_score,
              "convergence_point": bin.convergence_point,
              "centroid_lat": binCenterLat,
              "centroid_lon": binCenterLon
            },
            "geometry": {
              "type": "Polygon",
              "coordinates": coordinates
            }
          });
        }
      }

      // Performance timing
      const endTime = performance.now();
      const loadTime = Math.round(endTime - startTime);
      
      binsGeoJSON = geojson;
      
      // Update status with performance info
      updateStatus(`Loaded ${geojson.features.length} bins in ${loadTime}ms`, 'success');
      
      return geojson;
      
    } catch (error) {
      console.error('Error fetching bins:', error);
      updateStatus(`Error loading bins: ${error.message}`, 'error');
      
      // Return empty GeoJSON on error
      return {
        "type": "FeatureCollection",
        "features": []
      };
    }
  }

  async function fetchDensityData(zoneMetric = 'areal') {
    updateStatus('Fetching data...', 'loading');
    
    try {
      // Fetch both segments and density data
      const [segments, densityResponse] = await Promise.all([
        fetchSegments(),
        fetch(`/api/density.summary?zoneMetric=${zoneMetric}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            paceCsv: "data/your_pace_data.csv",
            overlapsCsv: "data/overlaps.csv",
            startTimes: {"Full":420,"Half":460,"10K":440},
            stepKm: 0.03,
            timeWindow: 60,
            depth_m: 3.0
          })
        })
      ]);

      if (!densityResponse.ok) {
        throw new Error(`HTTP ${densityResponse.status}: ${densityResponse.statusText}`);
      }

      const summary = await densityResponse.json();
      renderMap(segments, summary);
      
    } catch (error) {
      console.error('Error fetching data:', error);
      updateStatus(`Error: ${error.message}`, 'error');
      
      // Fallback to placeholder data
      const fallbackSummary = {
        "engine": "density",
        "zone_by": zoneMetric,
        "segments": [
          { "seg_id":"A1a", "segment_label":"Start to Queen/Regent", "zone":"dark-red", "areal_density":58.6, "crowd_density":19.53 },
          { "seg_id":"A2a", "segment_label":"Start to Queen/Regent", "zone":"orange", "areal_density":28.6, "crowd_density":9.53 },
          { "seg_id":"A3a", "segment_label":"Start to Queen/Regent", "zone":"orange", "areal_density":28.6, "crowd_density":9.53 }
        ]
      };
      
      const fallbackSegments = await fetchSegments();
      renderMap(fallbackSegments, fallbackSummary);
    }
  }

  // Event handlers
  document.getElementById('metric').addEventListener('change', function() {
    if (currentViewMode === 'segments') {
      fetchDensityData(this.value);
    }
  });

  document.getElementById('refresh').addEventListener('click', function() {
    if (currentViewMode === 'segments') {
      const metric = document.getElementById('metric').value;
      fetchDensityData(metric);
    } else {
      fetchBins().then(binsData => {
        renderBins(binsData);
      });
    }
  });

  // View mode change handler
  document.getElementById('viewMode').addEventListener('change', function() {
    currentViewMode = this.value;
    const binControls = document.getElementById('binControls');
    
    if (currentViewMode === 'bins') {
      binControls.style.display = 'block';
      // Load bins if not already loaded
      if (!binsGeoJSON) {
        fetchBins().then(binsData => {
          renderBins(binsData);
        });
      } else {
        renderBins(binsGeoJSON);
      }
    } else {
      binControls.style.display = 'none';
      // Switch back to segments view
      if (segmentsGeoJSON && currentSummary) {
        renderMap(segmentsGeoJSON, currentSummary);
      } else {
        fetchDensityData('areal');
      }
    }
  });

  // Bin control handlers
  document.getElementById('loadBins').addEventListener('click', function() {
    fetchBins().then(binsData => {
      renderBins(binsData);
    });
  });

  document.getElementById('clearBins').addEventListener('click', function() {
    binsGeoJSON = null;
    if (currentViewMode === 'bins') {
      updateStatus('Bins cleared', 'success');
      // Clear the map
      if (currentLayer) {
        map.removeLayer(currentLayer);
        currentLayer = null;
      }
    }
  });

  // Zone filter event handlers
  document.getElementById('zoneFilter').addEventListener('change', function() {
    updateLegendStatus();
    // Re-render the map with current zone filter
    if (currentViewMode === 'segments' && currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    } else if (currentViewMode === 'bins' && currentLayer && binsGeoJSON) {
      renderBins(binsGeoJSON);
    }
  });

  document.getElementById('showAll').addEventListener('click', function() {
    const zoneFilter = document.getElementById('zoneFilter');
    Array.from(zoneFilter.options).forEach(option => {
      option.selected = true;
    });
    updateLegendStatus();
    // Re-render the map
    if (currentViewMode === 'segments' && currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    } else if (currentViewMode === 'bins' && currentLayer && binsGeoJSON) {
      renderBins(binsGeoJSON);
    }
  });

  document.getElementById('hideAll').addEventListener('click', function() {
    const zoneFilter = document.getElementById('zoneFilter');
    Array.from(zoneFilter.options).forEach(option => {
      option.selected = false;
    });
    updateLegendStatus();
    // Re-render the map
    if (currentViewMode === 'segments' && currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    } else if (currentViewMode === 'bins' && currentLayer && binsGeoJSON) {
      renderBins(binsGeoJSON);
    }
  });

  // Display mode event handlers
  document.getElementById('colorMode').addEventListener('click', function() {
    document.getElementById('colorMode').classList.add('active');
    document.getElementById('bwMode').classList.remove('active');
    // Show color legend, hide B&W legend
    document.getElementById('colorLegend').style.display = 'block';
    document.getElementById('bwLegend').style.display = 'none';
    // Re-render the map with color mode
    if (currentViewMode === 'segments' && currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    } else if (currentViewMode === 'bins' && currentLayer && binsGeoJSON) {
      renderBins(binsGeoJSON);
    }
  });

  document.getElementById('bwMode').addEventListener('click', function() {
    document.getElementById('bwMode').classList.add('active');
    document.getElementById('colorMode').classList.remove('active');
    // Show B&W legend, hide color legend
    document.getElementById('colorLegend').style.display = 'none';
    document.getElementById('bwLegend').style.display = 'block';
    // Re-render the map with B&W mode
    if (currentViewMode === 'segments' && currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    } else if (currentViewMode === 'bins' && currentLayer && binsGeoJSON) {
      renderBins(binsGeoJSON);
    }
  });

  // Initial load
  fetchDensityData('areal');
  updateLegendStatus();
})();
