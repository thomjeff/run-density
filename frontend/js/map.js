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

  let currentLayer = null;
  let currentSummary = null;

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
      const response = await fetch('/api/segments.geojson');
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
    fetchDensityData(this.value);
  });

  document.getElementById('refresh').addEventListener('click', function() {
    const metric = document.getElementById('metric').value;
    fetchDensityData(this.value);
  });

  // Zone filter event handlers
  document.getElementById('zoneFilter').addEventListener('change', function() {
    updateLegendStatus();
    // Re-render the map with current zone filter
    if (currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    }
  });

  document.getElementById('showAll').addEventListener('click', function() {
    const zoneFilter = document.getElementById('zoneFilter');
    Array.from(zoneFilter.options).forEach(option => {
      option.selected = true;
    });
    updateLegendStatus();
    // Re-render the map
    if (currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    }
  });

  document.getElementById('hideAll').addEventListener('click', function() {
    const zoneFilter = document.getElementById('zoneFilter');
    Array.from(zoneFilter.options).forEach(option => {
      option.selected = false;
    });
    updateLegendStatus();
    // Re-render the map
    if (currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
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
    if (currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    }
  });

  document.getElementById('bwMode').addEventListener('click', function() {
    document.getElementById('bwMode').classList.add('active');
    document.getElementById('colorMode').classList.remove('active');
    // Show B&W legend, hide color legend
    document.getElementById('colorLegend').style.display = 'none';
    document.getElementById('bwLegend').style.display = 'block';
    // Re-render the map with B&W mode
    if (currentLayer && currentSummary) {
      renderMap(segmentsGeoJSON, currentSummary);
    }
  });

  // Initial load
  fetchDensityData('areal');
  updateLegendStatus();
})();
