// Map Page JavaScript
(function(){
  // Configuration - should be loaded from server or environment
  const CONFIG = {
    startTimes: {"Full": 420, "10K": 440, "Half": 460},
    paceCsv: "data/runners.csv",
    segmentsCsv: "data/segments.csv",
    apiBaseUrl: "" // Will be set dynamically
  };

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
  let currentViewMode = 'segments'; // Will be updated after DOM loads
  let bySeg = {};
  let allBinsData = null; // Store all bin data for filtering

  function updateStatus(message, type = 'loading') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
  }


  function filterBinsBySegment(selectedSegmentId) {
    if (!allBinsData) {
      console.log('No bin data available for filtering');
      return null;
    }
    
    if (!selectedSegmentId) {
      console.log('No segment selected, showing all bins');
      return allBinsData;
    }
    
    // Filter bins by selected segment
    const filteredFeatures = allBinsData.features.filter(feature => 
      feature.properties.segment_id === selectedSegmentId
    );
    
    const filteredBinsData = {
      ...allBinsData,
      features: filteredFeatures
    };
    
    console.log(`Filtered bins for segment ${selectedSegmentId}: ${filteredFeatures.length} bins`);
    return filteredBinsData;
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

  function determineZone(density) {
    // Determine zone color based on density value using same thresholds as backend
    if (density < 0.36) {
      return "green";
    } else if (density < 0.54) {
      return "yellow";
    } else if (density < 0.72) {
      return "orange";
    } else if (density < 1.08) {
      return "red";
    } else {
      return "dark-red";
    }
  }

  function getZoneColor(zone) {
    const zoneColors = {
      "green": "#4CAF50",
      "yellow": "#FFC107", 
      "orange": "#FF9800",
      "red": "#F44336",
      "dark-red": "#D32F2F"
    };
    return zoneColors[zone] || "#666";
  }

  function showSegmentDetails(segmentId, segmentData) {
    const sidebar = document.getElementById('segmentDetails');
    const title = document.getElementById('selectedSegmentTitle');
    const content = document.getElementById('segmentDetailsContent');
    
    if (!segmentData) {
      console.warn('No segment data available for', segmentId);
      return;
    }
    
    // Update title
    title.textContent = `${segmentId} — ${segmentData.segment_label || segmentId}`;
    
    // Build detailed content
    let html = '';
    
    // Basic Info Section
    html += '<div class="detail-section">';
    html += '<h4>Basic Information</h4>';
    html += `<div class="detail-item"><span class="detail-label">Segment ID</span><span class="detail-value">${segmentId}</span></div>`;
    html += `<div class="detail-item"><span class="detail-label">Label</span><span class="detail-value">${segmentData.segment_label || '—'}</span></div>`;
    html += `<div class="detail-item"><span class="detail-label">Width</span><span class="detail-value">${segmentData.width_m ? segmentData.width_m.toFixed(1) + 'm' : '—'}</span></div>`;
    html += '</div>';
    
    // Density Metrics Section
    html += '<div class="detail-section">';
    html += '<h4>Density Metrics</h4>';
    html += `<div class="detail-item"><span class="detail-label">Zone</span><span class="detail-value zone ${segmentData.zone || 'green'}">${(segmentData.zone || 'green').toUpperCase()}</span></div>`;
    html += `<div class="detail-item"><span class="detail-label">Peak Areal Density</span><span class="detail-value">${segmentData.peak_areal_density ? segmentData.peak_areal_density.toFixed(3) + ' pax/m' : '—'}</span></div>`;
    html += `<div class="detail-item"><span class="detail-label">Peak Crowd Density</span><span class="detail-value">${segmentData.peak_crowd_density ? segmentData.peak_crowd_density.toFixed(3) + ' pax/m²' : '—'}</span></div>`;
    html += '</div>';
    
    // Flow Information Section
    html += '<div class="detail-section">';
    html += '<h4>Flow Information</h4>';
    const flowType = segmentData.flow_type || 'normal';
    const flowIndicator = `<span class="flow-indicator ${flowType}"></span>`;
    html += `<div class="detail-item"><span class="detail-label">Flow Type</span><span class="detail-value">${flowIndicator}${flowType.charAt(0).toUpperCase() + flowType.slice(1)}</span></div>`;
    html += '</div>';
    
    // Add any additional metrics if available
    if (segmentData.overtakes || segmentData.co_presence) {
      html += '<div class="detail-section">';
      html += '<h4>Flow Analysis</h4>';
      if (segmentData.overtakes) {
        const overtakesStr = Object.entries(segmentData.overtakes)
          .map(([key, value]) => `${key}: ${value}`)
          .join(', ');
        html += `<div class="detail-item"><span class="detail-label">Overtakes</span><span class="detail-value">${overtakesStr}</span></div>`;
      }
      if (segmentData.co_presence) {
        const coPresenceStr = Object.entries(segmentData.co_presence)
          .map(([key, value]) => `${key}: ${value}`)
          .join(', ');
        html += `<div class="detail-item"><span class="detail-label">Co-presence</span><span class="detail-value">${coPresenceStr}</span></div>`;
      }
      html += '</div>';
    }
    
    content.innerHTML = html;
    sidebar.classList.add('show');
  }

  function hideSegmentDetails() {
    const sidebar = document.getElementById('segmentDetails');
    sidebar.classList.remove('show');
  }



  function styleFor(seg) {
    // Determine zone based on selected metric
    const metric = document.getElementById('metric').value;
    let density;
    if (metric === 'crowd' && seg && seg.peak_crowd_density !== undefined) {
      density = seg.peak_crowd_density;
    } else if (seg && seg.peak_areal_density !== undefined) {
      density = seg.peak_areal_density;
    } else {
      density = 0; // Default to green for missing data
    }
    
    const zone = determineZone(density);
    
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
      // Enhanced color mode with flow type indicators
      const baseStyle = {
        color: ZONES[zone] || '#4CAF50',
        weight: 6,
        opacity: 0.9
      };
      
      // Add flow type visual indicators and highlight high-flow segments
      if (seg && seg.flow_type) {
        switch (seg.flow_type) {
          case 'overtake':
            baseStyle.dashArray = "8,4"; // Dashed line for overtake segments
            baseStyle.weight = 7; // Slightly thicker
            break;
          case 'convergence':
            baseStyle.dashArray = "12,6"; // Different dash pattern for convergence
            baseStyle.weight = 8; // Thicker for convergence points
            break;
          case 'bottleneck':
            baseStyle.dashArray = "4,2"; // Tight dashes for bottlenecks
            baseStyle.weight = 8; // Thicker for bottlenecks
            break;
          default:
            // Solid line for normal flow
            break;
        }
      }
      
      // Add special highlighting for high-flow segments
      if (seg && seg.peak_crowd_density > 1.5) {
        // High crowd density - add pulsing effect with thicker line
        baseStyle.weight = Math.max(baseStyle.weight, 8);
        baseStyle.opacity = 1.0;
        // Add a subtle glow effect by making it slightly brighter
        if (baseStyle.color === '#4CAF50') baseStyle.color = '#66BB6A';
        else if (baseStyle.color === '#FFC107') baseStyle.color = '#FFD54F';
        else if (baseStyle.color === '#FF9800') baseStyle.color = '#FFB74D';
        else if (baseStyle.color === '#F44336') baseStyle.color = '#EF5350';
      }
      
      // Add special highlighting for segments with high overtakes
      if (seg && seg.overtakes) {
        const overtakeValues = Object.values(seg.overtakes);
        const maxOvertakes = Math.max(...overtakeValues);
        if (maxOvertakes > 500) { // High overtake threshold
          baseStyle.weight = Math.max(baseStyle.weight, 9);
          baseStyle.dashArray = "6,3"; // Distinctive pattern for high overtakes
        }
      }
      
      return baseStyle;
    }
  }

  function styleForBin(bin) {
    const densityLevel = bin.density_level || 'A';
    const density = bin.density || 0;
    const convergencePoint = bin.convergence_point || false;
    
    console.log('Styling bin:', bin.segment_id, bin.bin_index, 'density_level:', densityLevel);
    
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
    
    console.log('Bin zone check:', zone, 'selectedZones:', selectedZones, 'included:', selectedZones.includes(zone));
    
    if (!selectedZones.includes(zone)) {
      console.log('Bin filtered out due to zone filter');
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
      const style = {
        color: baseColor,
        weight: 2,
        opacity: 0.7,
        fillOpacity: 0.4,
        dashArray: convergencePoint ? "3,3" : null
      };
      console.log('Final bin style:', style);
      return style;
    }
  }

  function renderBins(binsData) {
    console.log('renderBins called with:', binsData);
    console.log('Number of bin features:', binsData.features.length);
    
    // Performance timing
    const startTime = performance.now();
    
    // Remove existing layer if any
    if (currentLayer) {
      console.log('Removing existing layer:', currentLayer);
      map.removeLayer(currentLayer);
      console.log('Layer removed successfully');
    } else {
      console.log('No existing layer to remove');
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
    
    console.log('Bin layer added to map:', currentLayer);

    // Fit bounds if we have features
    try { 
      if (binsData.features.length > 0) {
        const bounds = currentLayer.getBounds();
        map.fitBounds(bounds, {padding:[30,30]});
        console.log('Fitted map bounds to bins:', bounds);
      }
    } catch(error) {
      console.error('Error fitting bounds:', error);
    }

    // Performance timing
    const endTime = performance.now();
    const renderTime = Math.round(endTime - startTime);

    // Update UI with performance info
    console.log(`Rendered ${binsData.features.length} bins in ${renderTime}ms`);
    updateStatus(`Rendered ${binsData.features.length} bins in ${renderTime}ms`, 'success');
  }

  function renderMap(geojson, summary) {
    // Remove existing layer if any
    if (currentLayer) {
      map.removeLayer(currentLayer);
    }

    currentSummary = summary;
    bySeg = {}; // Use global bySeg variable
    if (summary && summary.segments) {
      summary.segments.forEach(s => { bySeg[s.seg_id] = s; });
    } else if (summary && summary.data && summary.data.segments) {
      // Handle the actual data structure from density analysis
      Object.entries(summary.data.segments).forEach(([segId, segData]) => {
        bySeg[segId] = segData.summary; // Use the summary part of each segment
      });
    }

    // Debug logging
    console.log('Density summary segments:', Object.keys(bySeg));
    console.log('GeoJSON features:', geojson.features.map(f => f.properties.segment_id));
    console.log('D2 in density data:', bySeg['D2']);
    console.log('D2 in GeoJSON:', geojson.features.find(f => f.properties.seg_id === 'D2'));

    // Check for segments with coordinate issues (from GPX processor)
    const problematicSegments = [];
    geojson.features.forEach(feature => {
      if (feature.properties.coord_issue) {
        problematicSegments.push(feature.properties.segment_id);
        console.warn(`⚠️ Segment ${feature.properties.segment_id} has coordinate issues`);
      }
    });

    // Create new layer
    currentLayer = L.geoJSON(geojson, {
      style: f => {
        const seg = bySeg[f.properties.segment_id];
        console.log(`Styling ${f.properties.segment_id}:`, seg);
        
        // Special styling for problematic segments
        if (problematicSegments.includes(f.properties.segment_id)) {
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
        const seg = bySeg[feature.properties.segment_id];
        const label = feature.properties.seg_label || (seg && seg.segment_label) || feature.properties.segment_id;
        const areal = seg ? seg.peak_areal_density : null;
        const crowd = seg ? seg.peak_crowd_density : null;
        
        // Determine zone based on selected metric (same logic as styleFor)
        const metric = document.getElementById('metric').value;
        let density;
        if (metric === 'crowd' && crowd !== null) {
          density = crowd;
        } else if (areal !== null) {
          density = areal;
        } else {
          density = 0;
        }
        const zone = determineZone(density);
        
        // Enhanced tooltip with comprehensive segment data
        const segmentData = seg; // Use the seg variable that's already available
        const flowType = segmentData?.flow_type || 'none';
        const width = segmentData?.width_m || 0;
        
        let tooltipText = `<div class="seg-label" style="font-size: 14px; font-weight: bold; margin-bottom: 8px;">${feature.properties.segment_id} — ${label}</div>`;
        
        if (problematicSegments.includes(feature.properties.segment_id)) {
          tooltipText += `<div style="color: red; font-weight: bold; margin-bottom: 6px;">⚠️ COORDINATE ISSUE</div>`;
        }
        
        // Density metrics with better formatting
        tooltipText += `<div style="margin-bottom: 6px;">`;
        tooltipText += `<div style="font-weight: bold; color: #2196F3;">Density Metrics</div>`;
        tooltipText += `<div>Zone: <b style="color: ${getZoneColor(zone)};">${zone.toUpperCase()}</b></div>`;
        tooltipText += `<div>Areal: <b>${areal ? areal.toFixed(2) : '—'}</b> pax/m</div>`;
        tooltipText += `<div>Crowd: <b>${crowd ? crowd.toFixed(2) : '—'}</b> pax/m²</div>`;
        tooltipText += `</div>`;
        
        // Flow and geometry info
        tooltipText += `<div style="margin-bottom: 6px;">`;
        tooltipText += `<div style="font-weight: bold; color: #4CAF50;">Flow & Geometry</div>`;
        tooltipText += `<div>Flow Type: <b>${flowType}</b></div>`;
        tooltipText += `<div>Width: <b>${width.toFixed(1)}m</b></div>`;
        tooltipText += `</div>`;
        
        // Add segment length if available
        if (feature.properties.from_km && feature.properties.to_km) {
          const length = (feature.properties.to_km - feature.properties.from_km).toFixed(2);
          tooltipText += `<div style="font-size: 11px; color: #666;">Length: ${length}km</div>`;
        }
        
        layer.bindTooltip(tooltipText, { sticky:true });
        
        // Add click handler for segment details
        layer.on('click', (e) => {
          showSegmentDetails(feature.properties.segment_id, segmentData);
        });
        
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

    // Update UI - don't reset the dropdown value
    
    // Show warning for problematic segments
    if (problematicSegments.length > 0) {
      updateStatus(`Loaded ${summary?.segments?.length || 0} segments (${problematicSegments.length} with coordinate issues)`, 'error');
      console.warn(`⚠️ Segments with coordinate issues: ${problematicSegments.join(', ')}`);
    } else {
      updateStatus(`Loaded ${summary?.segments?.length || 0} segments`, 'success');
    }
  }

  async function fetchSegments() {
    try {
      const startTimes = encodeURIComponent(JSON.stringify(CONFIG.startTimes));
      const response = await fetch(`/api/segments.geojson?paceCsv=${CONFIG.paceCsv}&segmentsCsv=${CONFIG.segmentsCsv}&startTimes=${startTimes}`);
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

  async function loadCachedData() {
    try {
      updateStatus('Loading cached data...', 'loading');
      
      // Use new simplified endpoint
      const response = await fetch('/api/map-data');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const mapData = await response.json();
      
      if (mapData.ok) {
        currentSummary = mapData;
        
        // Load segments first
        const segments = await fetchSegments();
        segmentsGeoJSON = segments;
        
        // Convert mapData.segments to the format expected by renderMap
        const segmentData = {
          segments: Object.entries(mapData.segments).map(([segmentId, segmentInfo]) => ({
            seg_id: segmentId,
            seg_label: segmentInfo.segment_label,
            peak_areal_density: segmentInfo.peak_areal_density,
            peak_crowd_density: segmentInfo.peak_crowd_density,
            flow_type: segmentInfo.flow_type,
            width_m: segmentInfo.width_m,
            zone: segmentInfo.zone
          }))
        };
        
        // Render segments
        renderMap(segments, segmentData);
        updateStatus(`Loaded ${mapData.source} data from ${formatTimestamp(mapData.timestamp)}`, 'success');
      } else {
        updateStatus(`Error: ${mapData.error || 'Unknown error'}`, 'error');
      }
      
    } catch (error) {
      console.error('Error loading cached data:', error);
      updateStatus(`Error loading cached data: ${error.message}`, 'error');
    }
  }

  async function loadBinData() {
    console.log('loadBinData called');
    try {
      updateStatus('Loading bin data...', 'loading');
      
      const response = await fetch('/api/bins-data');
      const data = await response.json();
      console.log('Bin data response:', data);
      
      if (data.ok && data.geojson) {
        allBinsData = data.geojson; // Store all bin data
        binsGeoJSON = data.geojson;
        
        // Render bins on the map
        renderBins(binsGeoJSON);
        
        updateStatus(`Loaded bin data from ${data.source} at ${formatTimestamp(data.timestamp)}`, 'success');
      } else {
        updateStatus(`Error: ${data.error || 'Failed to load bin data'}`, 'error');
      }
      
    } catch (error) {
      console.error('Error loading bin data:', error);
      updateStatus(`Error loading bin data: ${error.message}`, 'error');
    }
  }

  async function checkCacheStatus(analysisType) {
    try {
      const response = await fetch(`/api/cache-status?analysisType=${analysisType}&paceCsv=${CONFIG.paceCsv}&segmentsCsv=${CONFIG.segmentsCsv}&startTimes=${encodeURIComponent(JSON.stringify(CONFIG.startTimes))}`);
      const data = await response.json();
      return data.cache_status;
    } catch (error) {
      console.error('Error checking cache status:', error);
      return { cached: false };
    }
  }

  async function getCachedAnalysis(analysisType) {
    try {
      const response = await fetch(`/api/cached-analysis?analysisType=${analysisType}&paceCsv=${CONFIG.paceCsv}&segmentsCsv=${CONFIG.segmentsCsv}&startTimes=${encodeURIComponent(JSON.stringify(CONFIG.startTimes))}`);
      return await response.json();
    } catch (error) {
      console.error('Error getting cached analysis:', error);
      return { ok: false };
    }
  }

  function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
  }

  function convertBinsToGeoJSON(binsData) {
    if (!binsData || !binsData.segments) {
      return { type: "FeatureCollection", features: [] };
    }
    
    const features = [];
    for (const [segmentId, segmentData] of Object.entries(binsData.segments)) {
      for (const bin of segmentData.bins) {
        features.push({
          type: "Feature",
          properties: {
            segment_id: segmentId,
            bin_index: bin.bin_index,
            start_km: bin.start_km,
            end_km: bin.end_km,
            density: bin.density,
            density_level: bin.density_level,
            overtakes: bin.overtakes,
            co_presence: bin.co_presence,
            rsi_score: bin.rsi_score,
            convergence_point: bin.convergence_point
          },
          geometry: {
            type: "LineString",
            coordinates: [
              [bin.start_km * 1000, 0],
              [bin.end_km * 1000, 0]
            ]
          }
        });
      }
    }
    
    return { type: "FeatureCollection", features };
  }

  async function generateNewAnalysis() {
    try {
      updateStatus('Running fresh analysis... This may take 2-3 minutes.', 'loading');
      
      // Show progress indicator
      const progressDiv = document.createElement('div');
      progressDiv.id = 'progress-indicator';
      progressDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px; margin: 10px 0;">
          <div class="spinner"></div>
          <span>Running analysis... Please wait</span>
        </div>
      `;
      document.querySelector('.panel').appendChild(progressDiv);
      
      // Force refresh analysis using new simplified endpoint
      const response = await fetch('/api/map-data?forceRefresh=true');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Remove progress indicator
      const progressIndicator = document.getElementById('progress-indicator');
      if (progressIndicator) {
        progressIndicator.remove();
      }
      
      // Reload the data
      await loadCachedData();
      
      updateStatus(`Fresh analysis completed at ${formatTimestamp(result.timestamp)}`, 'success');
      
    } catch (error) {
      console.error('Error generating new analysis:', error);
      updateStatus(`Error generating new analysis: ${error.message}`, 'error');
      
      // Remove progress indicator on error
      const progressIndicator = document.getElementById('progress-indicator');
      if (progressIndicator) {
        progressIndicator.remove();
      }
    }
  }

  async function fetchBins() {
    try {
      updateStatus('Running bin-level analysis... This may take 2-3 minutes.', 'loading');
      
      // Add performance timing
      const startTime = performance.now();
      
      const response = await fetch('/api/flow-bins', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          paceCsv: CONFIG.paceCsv,
          segmentsCsv: CONFIG.segmentsCsv,
          startTimes: CONFIG.startTimes,
          segmentId: "A1",
          binSizeKm: 0.3
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
    updateStatus('Running flow and density analysis... This may take 2-3 minutes.', 'loading');
    
    try {
      // Fetch both segments and density data
      const [segments, densityResponse] = await Promise.all([
        fetchSegments(),
        fetch(`/api/density/analyze?zoneMetric=${zoneMetric}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            paceCsv: "data/your_pace_data.csv",
            overlapsCsv: "data/overlaps.csv",
            startTimes: CONFIG.startTimes,
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
      // Re-render the map with the new metric for zone determination
      if (segmentsGeoJSON && currentSummary) {
        renderMap(segmentsGeoJSON, currentSummary);
      } else {
        loadCachedData();
      }
    }
  });

  document.getElementById('refresh').addEventListener('click', function() {
    // Always reload segment data
    loadCachedData();
  });

  // View mode change handler
  // View mode is now always segments - no event listener needed

  // Bin control handlers
  document.getElementById('generateAnalysis').addEventListener('click', function() {
    generateNewAnalysis();
  });


  // Segment selector handler - Check if element exists before adding listener
  const segmentSelector = document.getElementById('segmentSelector');
  if (segmentSelector) {
    segmentSelector.addEventListener('change', function() {
      const selectedSegmentId = this.value;
      console.log('Segment selected:', selectedSegmentId);
      
      if (currentViewMode === 'bins' && allBinsData) {
        // Filter bins by selected segment
        const filteredBinsData = filterBinsBySegment(selectedSegmentId);
        
        if (filteredBinsData) {
          binsGeoJSON = filteredBinsData;
          renderBins(binsGeoJSON);
          
          // Update status
          const segmentText = selectedSegmentId ? ` for segment ${selectedSegmentId}` : '';
          updateStatus(`Showing ${filteredBinsData.features.length} bins${segmentText}`, 'success');
        }
      }
    });
  }

  // Load bins handler - Check if element exists before adding listener
  const loadBinsBtn = document.getElementById('loadBins');
  if (loadBinsBtn) {
    loadBinsBtn.addEventListener('click', function() {
      // Load bin data for bin view
      loadBinData();
    });
  }

  // Clear bins handler - Check if element exists before adding listener
  const clearBinsBtn = document.getElementById('clearBins');
  if (clearBinsBtn) {
    clearBinsBtn.addEventListener('click', function() {
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
  }

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

  // Segment details sidebar event listeners
  document.getElementById('closeSegmentDetails').addEventListener('click', hideSegmentDetails);


  // Initialize view mode (always segments now)
  currentViewMode = 'segments';
  console.log('View mode set to segments only');
  
  // Initial load - always load segment data
  console.log('Loading segment data...');
  loadCachedData();
  updateLegendStatus();
})();
