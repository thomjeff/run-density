/**
 * Course Mapping page: map, Street/Satellite toggle, course New/Open/Save.
 * Issue #732: Course storage under {data_dir}/courses/{id}.
 */

document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('course-mapping-map');
    if (!container) return;

    const loadingEl = container.querySelector('.map-loading');
    const toggleEl = document.getElementById('basemap-toggle');

    // Course state; data_dir is always from app utils constants (runflow root)
    let currentCourseId = null;
    let currentCourse = null;

    function updateCourseUI() {
        const saveBtn = document.getElementById('btn-save-course');
        const label = document.getElementById('current-course-label');
        if (saveBtn) saveBtn.disabled = !currentCourseId;
        var displayName = (currentCourse && currentCourse.name && currentCourse.name.trim()) ? currentCourse.name.trim() : currentCourseId;
        if (label) label.textContent = currentCourseId ? 'Course: ' + displayName : '';
        updateExportButton();
    }

    function setCourse(id, course) {
        currentCourseId = id;
        currentCourse = course;
        if (currentCourse && !Array.isArray(currentCourse.segment_breaks)) currentCourse.segment_breaks = [];
        if (currentCourse && !Array.isArray(currentCourse.locations)) currentCourse.locations = [];
        if (currentCourse && typeof currentCourse.segment_break_labels !== 'object') currentCourse.segment_break_labels = {};
        updateCourseUI();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateAddLocationButton();
        updateExportButton();
        renderCourseLine();
        renderSegmentPins();
        renderLocationPins();
        syncSegmentsFromBreaks();
        renderSegmentsList();
        renderLocationsList();
        renderStartFinishIcons();
        fitMapToCourse();
    }

    var LOCATION_TYPES = (window.LOCATION_TYPES_FROM_SERVER || []).slice().sort(function (a, b) { return (a.label || a.value).localeCompare(b.label || b.value); });
    var EVENT_CHOICES = window.EVENT_CHOICES_FROM_SERVER || [{ value: 'full', label: 'Full' }, { value: 'half', label: 'Half' }, { value: '10k', label: '10K' }, { value: 'elite', label: 'Elite' }, { value: 'open', label: 'Open' }];
    var LOCATION_PIN_COLORS = { aid: '#e74c3c', course: '#27ae60', official: '#f1c40f', traffic: '#95a5a6', water: '#3498db' };
    var SEGMENT_PIN_COLOR = '#3498db';
    var ROUTE_LINE_STYLE = { color: '#2f9e44', weight: 2, opacity: 0.45, dashArray: '4 6' };
    var SEGMENT_HIT_STYLE = { color: '#2f9e44', weight: 20, opacity: 0, dashArray: '4 6' };
    var SCHEMA_OPTIONS = [{ value: 'on_course_open', label: 'on_course_open' }, { value: 'on_course_narrow', label: 'on_course_narrow' }];
    var DIRECTION_OPTIONS = [{ value: 'uni', label: 'uni' }, { value: 'bi', label: 'bi' }];

    let segmentLinesLayer = null;
    let segmentInfoIconsLayer = null;
    let segmentPinsLayer = null;
    let startFinishLayer = null;
    let locationsLayer = null;
    let drawMode = false;
    let segmentPinMode = false;
    let locationPinMode = false;
    let drawRoutingInProgress = false;
    let mapClickHandler = null;

    // Snap-to-road: use our backend proxy (avoids CORS, uses OSRM driving profile).
    function fetchRouteSegment(fromLonLat, toLonLat, callback) {
        var fromStr = fromLonLat[0] + ',' + fromLonLat[1];
        var toStr = toLonLat[0] + ',' + toLonLat[1];
        var url = '/api/courses/route/segment?from_ll=' + encodeURIComponent(fromStr) + '&to_ll=' + encodeURIComponent(toStr);
        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.ok && data.coordinates && data.coordinates.length) {
                    callback(null, data.coordinates);
                } else {
                    callback(new Error(data.detail || 'No route'));
                }
            })
            .catch(function (err) { callback(err); });
    }

    function haversineMeters(lon1, lat1, lon2, lat2) {
        var R = 6371000;
        var dLat = (lat2 - lat1) * Math.PI / 180;
        var dLon = (lon2 - lon1) * Math.PI / 180;
        var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function cumulativeKm(coordinates) {
        if (!coordinates || coordinates.length < 2) return [];
        var cum = [0];
        for (var i = 1; i < coordinates.length; i++) {
            var c0 = coordinates[i - 1], c1 = coordinates[i];
            cum.push(cum[i - 1] + haversineMeters(c0[0], c0[1], c1[0], c1[1]) / 1000);
        }
        return cum;
    }

    function syncSegmentsFromBreaks() {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length < 2) return;
        if (!Array.isArray(currentCourse.segment_breaks)) currentCourse.segment_breaks = [];
        var coords = currentCourse.geometry.coordinates;
        var cum = cumulativeKm(coords);
        var breaks = currentCourse.segment_breaks.slice().sort(function (a, b) { return a - b; });
        breaks = breaks.filter(function (idx) { return idx > 0 && idx < coords.length; });
        var eventIds = (currentCourse.events || []).map(function (e) { return e.id || e; });
        var existing = (currentCourse.segments || []).reduce(function (acc, s) {
            var key = (s.start_index != null && s.end_index != null) ? s.start_index + '-' + s.end_index : null;
            if (key) acc[key] = { seg_label: s.seg_label, events: s.events, width_m: s.width_m, schema: s.schema, direction: s.direction, description: s.description, info_icon_lat: s.info_icon_lat, info_icon_lon: s.info_icon_lon };
            return acc;
        }, {});
        var segs = [];
        var startIdx = 0;
        for (var b = 0; b <= breaks.length; b++) {
            var endIdx = b < breaks.length ? breaks[b] : coords.length - 1;
            if (endIdx <= startIdx) continue;
            var from_km = cum[startIdx], to_km = cum[endIdx];
            var key = startIdx + '-' + endIdx;
            var prev = existing[key];
            segs.push({
                seg_id: 'A' + (segs.length + 1),
                seg_label: (prev && prev.seg_label) ? prev.seg_label : ('Segment A' + (segs.length + 1)),
                width_m: (prev && prev.width_m != null) ? prev.width_m : 3,
                direction: (prev && prev.direction) ? prev.direction : 'uni',
                schema: (prev && prev.schema) ? prev.schema : 'on_course_open',
                description: (prev && prev.description) ? prev.description : '',
                events: (prev && Array.isArray(prev.events) && prev.events.length) ? prev.events.slice() : eventIds.slice(),
                from_km: Math.round(from_km * 100) / 100,
                to_km: Math.round(to_km * 100) / 100,
                start_index: startIdx,
                end_index: endIdx,
                info_icon_lat: prev && prev.info_icon_lat,
                info_icon_lon: prev && prev.info_icon_lon
            });
            startIdx = endIdx;
        }
        if (segs.length === 0 && coords.length >= 2) {
            var key0 = '0-' + (coords.length - 1);
            var prev0 = existing[key0];
            segs.push({
                seg_id: 'A1',
                seg_label: (prev0 && prev0.seg_label) ? prev0.seg_label : 'Segment A1',
                width_m: (prev0 && prev0.width_m != null) ? prev0.width_m : 3,
                direction: (prev0 && prev0.direction) ? prev0.direction : 'uni',
                schema: (prev0 && prev0.schema) ? prev0.schema : 'on_course_open',
                description: (prev0 && prev0.description) ? prev0.description : '',
                events: (prev0 && Array.isArray(prev0.events) && prev0.events.length) ? prev0.events.slice() : eventIds.slice(),
                from_km: 0,
                to_km: Math.round(cum[coords.length - 1] * 100) / 100,
                start_index: 0,
                end_index: coords.length - 1,
                info_icon_lat: prev0 && prev0.info_icon_lat,
                info_icon_lon: prev0 && prev0.info_icon_lon
            });
        }
        currentCourse.segments = segs;
    }

    function updateDrawButtons() {
        const drawBtn = document.getElementById('btn-draw-line');
        const clearBtn = document.getElementById('btn-clear-line');
        const hasCourse = !!currentCourseId && !!currentCourse;
        if (drawBtn) drawBtn.disabled = !hasCourse;
        if (clearBtn) clearBtn.disabled = !hasCourse || !(currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length);
        if (drawBtn && drawMode) drawBtn.classList.add('active'); else if (drawBtn) drawBtn.classList.remove('active');
    }

    function updateSegmentPinButton() {
        const btn = document.getElementById('btn-add-segment-pin');
        const hasLine = !!(currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length >= 2);
        if (btn) btn.disabled = !currentCourseId || !currentCourse || !hasLine;
        if (btn && segmentPinMode) btn.classList.add('active'); else if (btn) btn.classList.remove('active');
    }

    function updateUndoButton() {
        const btn = document.getElementById('btn-undo-point');
        const canUndo = !!(currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length > 0);
        if (btn) btn.disabled = !currentCourseId || !currentCourse || !canUndo;
    }

    function updateAddLocationButton() {
        const btn = document.getElementById('btn-add-location');
        if (btn) btn.disabled = !currentCourseId || !currentCourse;
        if (btn && locationPinMode) btn.classList.add('active'); else if (btn) btn.classList.remove('active');
    }

    function updateExportButton() {
        const btn = document.getElementById('btn-export');
        const canExport = !!(currentCourseId && currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length >= 2);
        if (btn) btn.disabled = !canExport;
    }

    function undoLastPoint() {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length === 0) return;
        currentCourse.geometry.coordinates.pop();
        if (currentCourse.segment_breaks) {
            var len = currentCourse.geometry.coordinates.length;
            currentCourse.segment_breaks = currentCourse.segment_breaks.filter(function (idx) { return idx > 0 && idx < len; });
        }
        if (currentCourse.geometry.coordinates.length < 2) {
            currentCourse.segments = [];
        } else {
            syncSegmentsFromBreaks();
        }
        renderCourseLine();
        renderSegmentPins();
        renderSegmentsList();
        renderStartFinishIcons();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateCourseUI();
    }

    function openSegmentAnnotationPopup(segIdx, latlng) {
        var s = currentCourse.segments[segIdx];
        if (!s) return;
        var content = document.createElement('div');
        content.style.minWidth = '240px';
        content.innerHTML = '<strong>Segment ' + (s.seg_id || '') + '</strong><br/>';
        function addLabel(text) { var l = document.createElement('label'); l.textContent = text; content.appendChild(l); }
        function addInput(attr, val) {
            var el = document.createElement('input');
            el.type = attr === 'number' ? 'number' : 'text';
            el.style.display = 'block'; el.style.width = '100%'; el.style.marginBottom = '8px'; el.style.boxSizing = 'border-box';
            if (attr === 'number') { el.min = 0; el.step = 0.5; }
            el.value = val != null ? val : '';
            content.appendChild(el);
            return el;
        }
        addLabel('Segment label');
        var inputLabel = addInput('text', s.seg_label || '');
        addLabel('Width (m)');
        var inputWidth = addInput('number', s.width_m != null ? s.width_m : 3);
        addLabel('Schema');
        var selSchema = document.createElement('select');
        selSchema.style.display = 'block'; selSchema.style.width = '100%'; selSchema.style.marginBottom = '8px'; selSchema.style.boxSizing = 'border-box';
        SCHEMA_OPTIONS.forEach(function (o) { var opt = document.createElement('option'); opt.value = o.value; opt.textContent = o.label; if (o.value === (s.schema || 'on_course_open')) opt.selected = true; selSchema.appendChild(opt); });
        content.appendChild(selSchema);
        addLabel('Direction');
        var selDirection = document.createElement('select');
        selDirection.style.display = 'block'; selDirection.style.width = '100%'; selDirection.style.marginBottom = '8px'; selDirection.style.boxSizing = 'border-box';
        DIRECTION_OPTIONS.forEach(function (o) { var opt = document.createElement('option'); opt.value = o.value; opt.textContent = o.label; if (o.value === (s.direction || 'uni')) opt.selected = true; selDirection.appendChild(opt); });
        content.appendChild(selDirection);
        addLabel('Description');
        var inputDesc = document.createElement('textarea');
        inputDesc.rows = 2; inputDesc.style.display = 'block'; inputDesc.style.width = '100%'; inputDesc.style.marginBottom = '8px'; inputDesc.style.boxSizing = 'border-box';
        inputDesc.value = s.description || '';
        content.appendChild(inputDesc);
        addLabel('Events using this segment');
        var eventsDiv = document.createElement('div');
        eventsDiv.style.marginBottom = '8px';
        var selectedEvents = (s.events || []).slice();
        EVENT_CHOICES.forEach(function (ev) {
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = ev.value;
            cb.checked = selectedEvents.indexOf(ev.value) >= 0;
            cb.style.marginRight = '4px';
            var span = document.createElement('span');
            span.textContent = ev.label;
            span.style.marginRight = '10px';
            eventsDiv.appendChild(cb);
            eventsDiv.appendChild(span);
        });
        content.appendChild(eventsDiv);
        var btnSave = document.createElement('button');
        btnSave.type = 'button';
        btnSave.textContent = 'Save';
        content.appendChild(btnSave);
        var pop = L.popup().setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            s.seg_label = (inputLabel.value && inputLabel.value.trim()) ? inputLabel.value.trim() : (s.seg_id || '');
            s.width_m = parseFloat(inputWidth.value);
            if (isNaN(s.width_m) || s.width_m < 0) s.width_m = 3;
            s.schema = selSchema.value || 'on_course_open';
            s.direction = selDirection.value || 'uni';
            s.description = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
            s.events = [];
            eventsDiv.querySelectorAll('input[type="checkbox"]').forEach(function (cb) { if (cb.checked) s.events.push(cb.value); });
            if (s.events.length === 0) s.events = (currentCourse.events || []).map(function (e) { return e.id || e; });
            window.courseMappingMap.closePopup();
            renderSegmentInfoIcons();
            renderSegmentPins();
            renderSegmentsList();
            updateCourseUI();
        };
    }

    function segmentMidpoint(seg, coords) {
        var startIdx = seg.start_index != null ? seg.start_index : 0;
        var endIdx = seg.end_index != null ? seg.end_index : (coords.length - 1);
        var mid = Math.floor((startIdx + endIdx) / 2);
        var c = coords[mid];
        return c ? [c[1], c[0]] : null;
    }

    function isSegmentAnnotated(seg) {
        var defaultLabel = 'Segment ' + (seg.seg_id || '');
        if ((seg.seg_label && seg.seg_label.trim() && seg.seg_label !== defaultLabel)) return true;
        if (seg.description && seg.description.trim()) return true;
        if (seg.width_m != null && seg.width_m !== 3) return true;
        if (seg.schema && seg.schema !== 'on_course_open') return true;
        if (seg.direction && seg.direction !== 'uni') return true;
        return false;
    }

    function renderSegmentInfoIcons() {
        if (!window.courseMappingMap) return;
        if (segmentInfoIconsLayer) {
            window.courseMappingMap.removeLayer(segmentInfoIconsLayer);
            segmentInfoIconsLayer = null;
        }
        if (!currentCourse || !currentCourse.segments || currentCourse.segments.length === 0) return;
        var coords = (currentCourse.geometry && currentCourse.geometry.coordinates) || [];
        segmentInfoIconsLayer = L.layerGroup();
        currentCourse.segments.forEach(function (seg, segIdx) {
            if (!isSegmentAnnotated(seg)) return;
            var lat = seg.info_icon_lat;
            var lon = seg.info_icon_lon;
            if (lat == null || lon == null) {
                var mid = segmentMidpoint(seg, coords);
                if (!mid) return;
                lat = mid[0];
                lon = mid[1];
            }
            var icon = L.divIcon({
                className: 'segment-info-icon',
                html: '<div style="width:18px;height:18px;background:#27ae60;color:#fff;border:1px solid #1e8449;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">i</div>',
                iconSize: [18, 18],
                iconAnchor: [9, 9]
            });
            var m = L.marker([lat, lon], { icon: icon, draggable: true });
            m._segmentIndex = segIdx;
            m.bindTooltip('Segment info (drag to move)', { permanent: false, direction: 'top' });
            m.on('dragend', function () {
                var ll = m.getLatLng();
                var segEl = currentCourse.segments[m._segmentIndex];
                if (segEl) {
                    segEl.info_icon_lat = ll.lat;
                    segEl.info_icon_lon = ll.lng;
                    renderSegmentInfoIcons();
                    updateCourseUI();
                }
            });
            m.on('click', function (e) {
                if (locationPinMode) return;
                L.DomEvent.stopPropagation(e);
                if (segmentPinMode) {
                    var coords = (currentCourse.geometry && currentCourse.geometry.coordinates) || [];
                    var ll = e.latlng || m.getLatLng();
                    var idx = closestVertexIndex(ll, coords);
                    if (idx > 0 && idx < coords.length - 1) {
                        if (!Array.isArray(currentCourse.segment_breaks)) currentCourse.segment_breaks = [];
                        if (currentCourse.segment_breaks.indexOf(idx) < 0) {
                            currentCourse.segment_breaks.push(idx);
                            currentCourse.segment_breaks.sort(function (a, b) { return a - b; });
                            if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
                            var label = window.prompt('Segment pin label (optional)', '');
                            if (label !== null) currentCourse.segment_break_labels[idx] = (label && label.trim()) ? label.trim() : '';
                            syncSegmentsFromBreaks();
                            renderCourseLine();
                            renderSegmentPins();
                            renderSegmentsList();
                            updateCourseUI();
                        }
                    }
                    return;
                }
                var s = currentCourse.segments[m._segmentIndex];
                if (!s) return;
                var info = document.createElement('div');
                info.style.minWidth = '200px';
                info.innerHTML = '<strong>' + (s.seg_id || '') + ': ' + (s.seg_label || '') + '</strong><br/>' +
                    'Width: ' + (s.width_m != null ? s.width_m : 3) + ' m<br/>Schema: ' + (s.schema || 'on_course_open') + '<br/>Direction: ' + (s.direction || 'uni') + '<br/>' +
                    (s.description ? 'Description: ' + s.description + '<br/>' : '') +
                    'From ' + (s.from_km != null ? s.from_km : '') + ' to ' + (s.to_km != null ? s.to_km : '') + ' km<br/>';
                var btnEdit = document.createElement('button');
                btnEdit.type = 'button';
                btnEdit.textContent = 'Edit';
                btnEdit.style.marginTop = '6px';
                info.appendChild(btnEdit);
                var pop = L.popup().setContent(info).setLatLng(e.latlng).openOn(window.courseMappingMap);
                btnEdit.onclick = function () {
                    window.courseMappingMap.closePopup();
                    openSegmentAnnotationPopup(m._segmentIndex, e.latlng);
                };
            });
            segmentInfoIconsLayer.addLayer(m);
        });
        segmentInfoIconsLayer.addTo(window.courseMappingMap);
    }

    function renderStartFinishIcons() {
        if (!window.courseMappingMap) return;
        if (startFinishLayer) {
            window.courseMappingMap.removeLayer(startFinishLayer);
            startFinishLayer = null;
        }
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length === 0) return;
        var coords = currentCourse.geometry.coordinates;
        startFinishLayer = L.layerGroup();
        var first = coords[0];
        var startIcon = L.divIcon({
            className: 'start-finish-icon',
            html: '<div style="width:20px;height:20px;background:#27ae60;color:#fff;border:2px solid #1e8449;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">S</div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });
        startFinishLayer.addLayer(L.marker([first[1], first[0]], { icon: startIcon }));
        if (coords.length >= 2) {
            var last = coords[coords.length - 1];
            var finishIcon = L.divIcon({
                className: 'start-finish-icon',
                html: '<div style="width:20px;height:20px;background:#27ae60;color:#fff;border:2px solid #1e8449;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">F</div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            startFinishLayer.addLayer(L.marker([last[1], last[0]], { icon: finishIcon }));
        }
        startFinishLayer.addTo(window.courseMappingMap);
    }

    function renderCourseLine() {
        if (!window.courseMappingMap) return;
        if (segmentLinesLayer) {
            window.courseMappingMap.removeLayer(segmentLinesLayer);
            segmentLinesLayer = null;
        }
        if (!currentCourse || !currentCourse.geometry || currentCourse.geometry.type !== 'LineString' || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length < 2) return;
        var coords = currentCourse.geometry.coordinates;
        var segments = currentCourse.segments || [];
        if (segments.length === 0) {
            syncSegmentsFromBreaks();
            segments = currentCourse.segments || [];
        }
        segmentLinesLayer = L.layerGroup();
        segments.forEach(function (seg, segIdx) {
            var startIdx = seg.start_index != null ? seg.start_index : 0;
            var endIdx = seg.end_index != null ? seg.end_index : (coords.length - 1);
            var latlngs = [];
            for (var i = startIdx; i <= endIdx; i++) latlngs.push([coords[i][1], coords[i][0]]);
            if (latlngs.length < 2) return;
            var line = L.polyline(latlngs, ROUTE_LINE_STYLE);
            line._segmentIndex = segIdx;
            var openPopup = function (e) {
                if (segmentPinMode || locationPinMode) return;
                L.DomEvent.stopPropagation(e);
                var latlng = e.latlng || (latlngs.length ? L.latLng(latlngs[Math.floor(latlngs.length / 2)][0], latlngs[Math.floor(latlngs.length / 2)][1]) : null);
                var idx = latlng ? segmentIndexAtLatLng(latlng) : segIdx;
                if (latlng) openSegmentAnnotationPopup(idx, latlng);
            };
            line.on('click', openPopup);
            segmentLinesLayer.addLayer(line);
            var hitLine = L.polyline(latlngs, SEGMENT_HIT_STYLE);
            hitLine._segmentIndex = segIdx;
            hitLine.on('click', openPopup);
            segmentLinesLayer.addLayer(hitLine);
        });
        segmentLinesLayer.addTo(window.courseMappingMap);
        renderSegmentInfoIcons();
    }

    function getSegmentBreakLabel(idx) {
        if (!currentCourse || !currentCourse.segment_break_labels) return '';
        return (currentCourse.segment_break_labels[idx] || currentCourse.segment_break_labels['' + idx] || '').trim();
    }

    function renderSegmentPins() {
        if (!window.courseMappingMap) return;
        if (segmentPinsLayer) {
            window.courseMappingMap.removeLayer(segmentPinsLayer);
            segmentPinsLayer = null;
        }
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || !Array.isArray(currentCourse.segment_breaks) || currentCourse.segment_breaks.length === 0) return;
        var coords = currentCourse.geometry.coordinates;
        if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
        segmentPinsLayer = L.layerGroup();
        currentCourse.segment_breaks.forEach(function (idx) {
            if (idx <= 0 || idx >= coords.length) return;
            var c = coords[idx];
            var label = getSegmentBreakLabel(idx);
            var squareIcon = L.divIcon({
                className: 'segment-pin-square',
                html: '<div style="width:12px;height:12px;background:' + SEGMENT_PIN_COLOR + ';border:2px solid #2980b9;border-radius:0;"></div>',
                iconSize: [12, 12],
                iconAnchor: [6, 6]
            });
            var m = L.marker([c[1], c[0]], { icon: squareIcon, draggable: true });
            m._segmentBreakIndex = idx;
            m.bindTooltip(label || 'Segment boundary (drag to move)', { permanent: false, direction: 'top' });
            m.on('dragend', function () {
                var ll = m.getLatLng();
                currentCourse.geometry.coordinates[idx] = [ll.lng, ll.lat];
                renderCourseLine();
                renderSegmentPins();
                syncSegmentsFromBreaks();
                renderSegmentsList();
                updateCourseUI();
            });
            m.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                var i = e.target._segmentBreakIndex;
                var name = getSegmentBreakLabel(i) || 'Segment boundary';
                var content = document.createElement('div');
                content.innerHTML = '<strong>' + (name || 'Segment boundary') + '</strong><br/><span style="color:#666;">Segment boundary</span><br/>';
                var btnEdit = document.createElement('button');
                btnEdit.type = 'button';
                btnEdit.textContent = 'Edit';
                btnEdit.style.marginRight = '6px';
                var btnDel = document.createElement('button');
                btnDel.type = 'button';
                btnDel.textContent = 'Delete';
                content.appendChild(btnEdit);
                content.appendChild(btnDel);
                var pop = L.popup().setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
                btnEdit.onclick = function () {
                    var newLabel = window.prompt('Segment pin label', name || '');
                    if (newLabel !== null && currentCourse.segment_break_labels) {
                        currentCourse.segment_break_labels[i] = newLabel.trim();
                        window.courseMappingMap.closePopup();
                        renderSegmentPins();
                        renderSegmentsList();
                        updateCourseUI();
                    }
                };
                btnDel.onclick = function () {
                    if (!window.confirm('Remove this segment boundary? This cannot be undone.')) return;
                    window.courseMappingMap.closePopup();
                    currentCourse.segment_breaks = currentCourse.segment_breaks.filter(function (x) { return x !== i; });
                    if (currentCourse.segment_break_labels) delete currentCourse.segment_break_labels[i];
                    syncSegmentsFromBreaks();
                    renderSegmentPins();
                    renderSegmentsList();
                    updateCourseUI();
                };
            });
            segmentPinsLayer.addLayer(m);
        });
        segmentPinsLayer.addTo(window.courseMappingMap);
    }

    function renderSegmentsList() {
        var card = document.getElementById('segments-card');
        var empty = document.getElementById('segments-empty');
        var wrap = document.getElementById('segments-table-wrap');
        var tbody = document.getElementById('segments-tbody');
        if (!card || !tbody) return;
        if (!currentCourse || !currentCourse.segments || currentCourse.segments.length === 0) {
            card.style.display = currentCourseId && currentCourse ? 'block' : 'none';
            if (empty) empty.style.display = 'block';
            if (wrap) wrap.style.display = 'none';
            return;
        }
        card.style.display = 'block';
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        tbody.innerHTML = '';
        currentCourse.segments.forEach(function (seg) {
            var len = (seg.to_km - seg.from_km);
            var tr = document.createElement('tr');
            tr.innerHTML = '<td>' + (seg.seg_id || '') + '</td><td>' + (seg.seg_label || '') + '</td><td>' + seg.from_km + '</td><td>' + seg.to_km + '</td><td>' + Math.round(len * 100) / 100 + '</td>';
            tbody.appendChild(tr);
        });
    }

    function getLocationTypeLabel(locType) {
        var t = LOCATION_TYPES.find(function (x) { return x.value === locType; });
        return t ? t.label : (locType || '').toString();
    }

    function renderLocationPins() {
        if (!window.courseMappingMap) return;
        if (locationsLayer) {
            window.courseMappingMap.removeLayer(locationsLayer);
            locationsLayer = null;
        }
        if (!currentCourse || !Array.isArray(currentCourse.locations) || currentCourse.locations.length === 0) return;
        locationsLayer = L.layerGroup();
        currentCourse.locations.forEach(function (loc, i) {
            var lat = typeof loc.lat === 'number' ? loc.lat : parseFloat(loc.lat);
            var lon = typeof loc.lon === 'number' ? loc.lon : parseFloat(loc.lon);
            if (isNaN(lat) || isNaN(lon)) return;
            var fill = LOCATION_PIN_COLORS[loc.loc_type] || '#27ae60';
            var stroke = fill;
            var locIcon = L.divIcon({
                className: 'location-pin-circle',
                html: '<div style="width:16px;height:16px;background:' + fill + ';border:2px solid ' + stroke + ';border-radius:50%;"></div>',
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            });
            var m = L.marker([lat, lon], { icon: locIcon, draggable: true });
            m._locationIndex = i;
            var tip = (loc.loc_label || getLocationTypeLabel(loc.loc_type) || 'Location');
            m.bindTooltip(tip + ' (drag to move)', { permanent: false, direction: 'top' });
            m.on('dragend', function () {
                var ll = m.getLatLng();
                loc.lat = ll.lat;
                loc.lon = ll.lng;
                renderLocationPins();
                renderLocationsList();
                updateCourseUI();
            });
            m.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                var idx = e.target._locationIndex;
                var locEl = currentCourse.locations[idx];
                if (!locEl) return;
                var name = locEl.loc_label || getLocationTypeLabel(locEl.loc_type) || 'Location';
                var typeLabel = getLocationTypeLabel(locEl.loc_type);
                var content = document.createElement('div');
                content.innerHTML = '<strong>' + name + '</strong><br/><span style="color:#666;">' + typeLabel + '</span><br/>';
                var btnEdit = document.createElement('button');
                btnEdit.type = 'button';
                btnEdit.textContent = 'Edit';
                btnEdit.style.marginRight = '6px';
                var btnDel = document.createElement('button');
                btnDel.type = 'button';
                btnDel.textContent = 'Delete';
                content.appendChild(btnEdit);
                content.appendChild(btnDel);
                var pop = L.popup().setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
                btnEdit.onclick = function () {
                    var newType = window.prompt('Type: aid, course, official, traffic, water', locEl.loc_type || 'course');
                    if (newType !== null) {
                        var t = (newType && newType.trim()) ? newType.trim().toLowerCase() : 'course';
                        if (['aid', 'course', 'official', 'traffic', 'water'].indexOf(t) >= 0) locEl.loc_type = t;
                    }
                    var newLabel = window.prompt('Label', locEl.loc_label || '');
                    if (newLabel !== null) locEl.loc_label = (newLabel && newLabel.trim()) ? newLabel.trim() : '';
                    window.courseMappingMap.closePopup();
                    renderLocationPins();
                    renderLocationsList();
                    updateCourseUI();
                };
                btnDel.onclick = function () {
                    if (!window.confirm('Remove this location? This cannot be undone.')) return;
                    window.courseMappingMap.closePopup();
                    currentCourse.locations.splice(idx, 1);
                    renderLocationPins();
                    renderLocationsList();
                    updateCourseUI();
                };
            });
            locationsLayer.addLayer(m);
        });
        locationsLayer.addTo(window.courseMappingMap);
    }

    function renderLocationsList() {
        var card = document.getElementById('locations-card');
        var empty = document.getElementById('locations-empty');
        var wrap = document.getElementById('locations-table-wrap');
        var tbody = document.getElementById('locations-tbody');
        if (!card || !tbody) return;
        if (!currentCourse || !currentCourse.locations || currentCourse.locations.length === 0) {
            card.style.display = currentCourseId && currentCourse ? 'block' : 'none';
            if (empty) empty.style.display = 'block';
            if (wrap) wrap.style.display = 'none';
            return;
        }
        card.style.display = 'block';
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        tbody.innerHTML = '';
        currentCourse.locations.forEach(function (loc, i) {
            var lat = typeof loc.lat === 'number' ? loc.lat : parseFloat(loc.lat);
            var lon = typeof loc.lon === 'number' ? loc.lon : parseFloat(loc.lon);
            var tr = document.createElement('tr');
            var typeLabel = getLocationTypeLabel(loc.loc_type);
            tr.innerHTML = '<td>' + typeLabel + '</td><td>' + (loc.loc_label || '') + '</td><td>' + (isNaN(lat) ? '' : lat.toFixed(5)) + '</td><td>' + (isNaN(lon) ? '' : lon.toFixed(5)) + '</td><td><button type="button" class="btn-remove-loc" data-index="' + i + '" style="font-size: 0.75rem;">Remove</button></td>';
            tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.btn-remove-loc').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var idx = parseInt(btn.getAttribute('data-index'), 10);
                if (currentCourse && Array.isArray(currentCourse.locations) && idx >= 0 && idx < currentCourse.locations.length) {
                    currentCourse.locations.splice(idx, 1);
                    renderLocationPins();
                    renderLocationsList();
                    updateCourseUI();
                }
            });
        });
    }

    function closestVertexIndex(latLng, coordinates) {
        var minD = 1e9, best = 0;
        var lat = latLng.lat, lon = latLng.lng;
        for (var i = 0; i < coordinates.length; i++) {
            var c = coordinates[i];
            var d = (c[1] - lat) * (c[1] - lat) + (c[0] - lon) * (c[0] - lon);
            if (d < minD) { minD = d; best = i; }
        }
        return best;
    }

    function segmentIndexAtLatLng(latlng) {
        if (!currentCourse || !currentCourse.segments || !currentCourse.geometry || !currentCourse.geometry.coordinates) return 0;
        var coords = currentCourse.geometry.coordinates;
        var idx = closestVertexIndex(latlng, coords);
        var segments = currentCourse.segments;
        for (var s = 0; s < segments.length; s++) {
            var seg = segments[s];
            var startIdx = seg.start_index != null ? seg.start_index : 0;
            var endIdx = seg.end_index != null ? seg.end_index : (coords.length - 1);
            if (idx >= startIdx && idx <= endIdx) return s;
        }
        return 0;
    }

    function fitMapToCourse() {
        if (!window.courseMappingMap || !currentCourse) return;
        var points = [];
        if (currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length >= 2) {
            currentCourse.geometry.coordinates.forEach(function (c) { points.push([c[1], c[0]]); });
        }
        if (Array.isArray(currentCourse.segment_breaks) && currentCourse.geometry && currentCourse.geometry.coordinates) {
            var coords = currentCourse.geometry.coordinates;
            currentCourse.segment_breaks.forEach(function (idx) {
                if (idx > 0 && idx < coords.length) points.push([coords[idx][1], coords[idx][0]]);
            });
        }
        if (Array.isArray(currentCourse.locations)) {
            currentCourse.locations.forEach(function (loc) {
                var lat = typeof loc.lat === 'number' ? loc.lat : parseFloat(loc.lat);
                var lon = typeof loc.lon === 'number' ? loc.lon : parseFloat(loc.lon);
                if (!isNaN(lat) && !isNaN(lon)) points.push([lat, lon]);
            });
        }
        if (points.length < 2) return;
        var bounds = L.latLngBounds(points);
        window.courseMappingMap.fitBounds(bounds, { padding: [20, 20], maxZoom: 16 });
    }

    try {
        const map = initMap('course-mapping-map', { zoomPosition: 'topleft' });

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

        // ——— Course API ———
        const btnNew = document.getElementById('btn-new-course');
        const btnOpen = document.getElementById('btn-open-course');
        const courseList = document.getElementById('course-list');
        const btnLoad = document.getElementById('btn-load-course');
        const btnSave = document.getElementById('btn-save-course');

        if (btnNew) {
            btnNew.addEventListener('click', async function () {
                try {
                    const res = await fetch('/api/courses', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (data.ok && data.course) {
                        setCourse(data.id, data.course);
                        console.log('Created course:', data.id);
                    }
                } catch (e) {
                    console.error('Create course failed:', e);
                    alert('Failed to create course: ' + e.message);
                }
            });
        }

        if (btnOpen) {
            btnOpen.addEventListener('click', async function () {
                try {
                    const res = await fetch('/api/courses');
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (!data.ok || !data.courses) return;
                    if (courseList) {
                        courseList.innerHTML = '<option value="">Select a course...</option>';
                        data.courses.forEach(function (c) {
                            const opt = document.createElement('option');
                            opt.value = c.id;
                            var displayName = (c.name && c.name.trim()) ? c.name.trim() : c.id;
                            opt.textContent = displayName + (c.updated ? ' (' + c.updated.slice(0, 10) + ')' : '');
                            courseList.appendChild(opt);
                        });
                        courseList.style.display = 'inline-block';
                    }
                    if (btnLoad) btnLoad.style.display = 'inline-block';
                } catch (e) {
                    console.error('List courses failed:', e);
                    alert('Failed to list courses: ' + e.message);
                }
            });
        }

        function loadCourseById(id) {
            if (!id) return;
            fetch('/api/courses/' + encodeURIComponent(id))
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.ok && data.course) {
                        setCourse(data.course.id, data.course);
                        if (courseList) courseList.style.display = 'none';
                        if (btnLoad) btnLoad.style.display = 'none';
                        console.log('Loaded course:', data.course.id);
                    }
                })
                .catch(function (e) {
                    console.error('Load course failed:', e);
                    alert('Failed to load course: ' + e.message);
                });
        }

        if (btnLoad) {
            btnLoad.addEventListener('click', function () {
                if (courseList && courseList.value) loadCourseById(courseList.value);
            });
        }

        if (btnSave) {
            btnSave.addEventListener('click', async function () {
                if (!currentCourseId || !currentCourse) return;
                var currentName = (currentCourse.name && currentCourse.name.trim()) ? currentCourse.name.trim() : '';
                var name = window.prompt('Course name (shown in list)', currentName || '');
                if (name === null) return;
                currentCourse.name = (name && name.trim()) ? name.trim() : '';
                try {
                    const res = await fetch('/api/courses/' + encodeURIComponent(currentCourseId), {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ course: currentCourse })
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (data.ok && data.course) {
                        currentCourse = data.course;
                        updateCourseUI();
                        updateExportButton();
                        console.log('Saved course:', currentCourseId, currentCourse.name || '(no name)');
                    }
                } catch (e) {
                    console.error('Save course failed:', e);
                    alert('Failed to save course: ' + e.message);
                }
            });
        }

        // ——— Draw line ———
        const btnDraw = document.getElementById('btn-draw-line');
        const btnClear = document.getElementById('btn-clear-line');

        function startDrawMode() {
            if (drawMode || !currentCourse) return;
            stopSegmentPinMode();
            stopLocationPinMode();
            drawMode = true;
            if (btnDraw) btnDraw.classList.add('active');
            if (!currentCourse.geometry || currentCourse.geometry.type !== 'LineString') {
                currentCourse.geometry = { type: 'LineString', coordinates: [] };
            }
            if (!Array.isArray(currentCourse.geometry.coordinates)) currentCourse.geometry.coordinates = [];
            mapClickHandler = function (e) {
                if (drawRoutingInProgress) return;
                var snapEl = document.getElementById('snap-to-road');
                var coords = currentCourse.geometry.coordinates;
                var toPoint = [e.latlng.lng, e.latlng.lat];
                if (snapEl && snapEl.checked && coords.length >= 1) {
                    drawRoutingInProgress = true;
                    fetchRouteSegment(coords[coords.length - 1], toPoint, function (err, routeCoords) {
                        drawRoutingInProgress = false;
                        if (!err && routeCoords && routeCoords.length > 1) {
                            for (var i = 1; i < routeCoords.length; i++) coords.push(routeCoords[i]);
                        } else {
                            coords.push(toPoint);
                        }
                        syncSegmentsFromBreaks();
                        renderCourseLine();
                        renderStartFinishIcons();
                        updateDrawButtons();
                        updateUndoButton();
                    });
                } else {
                    coords.push(toPoint);
                    syncSegmentsFromBreaks();
                    renderCourseLine();
                    renderStartFinishIcons();
                    updateDrawButtons();
                    updateUndoButton();
                }
            };
            map.on('click', mapClickHandler);
            renderStartFinishIcons();
        }

        function stopDrawMode() {
            drawMode = false;
            if (btnDraw) btnDraw.classList.remove('active');
            if (mapClickHandler) {
                map.off('click', mapClickHandler);
                mapClickHandler = null;
            }
        }

        function startSegmentPinMode() {
            if (segmentPinMode || !currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length < 2) return;
            stopDrawMode();
            stopLocationPinMode();
            segmentPinMode = true;
            updateSegmentPinButton();
            mapClickHandler = function (e) {
                var coords = currentCourse.geometry.coordinates;
                var idx = closestVertexIndex(e.latlng, coords);
                if (idx <= 0 || idx >= coords.length - 1) return;
                if (!Array.isArray(currentCourse.segment_breaks)) currentCourse.segment_breaks = [];
                if (currentCourse.segment_breaks.indexOf(idx) >= 0) return;
                currentCourse.segment_breaks.push(idx);
                currentCourse.segment_breaks.sort(function (a, b) { return a - b; });
                if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
                var label = window.prompt('Segment pin label (optional)', '');
                if (label !== null) currentCourse.segment_break_labels[idx] = (label && label.trim()) ? label.trim() : '';
                syncSegmentsFromBreaks();
                renderSegmentPins();
                renderSegmentsList();
                updateCourseUI();
            };
            map.on('click', mapClickHandler);
        }

        function stopSegmentPinMode() {
            segmentPinMode = false;
            updateSegmentPinButton();
            if (mapClickHandler) {
                map.off('click', mapClickHandler);
                mapClickHandler = null;
            }
        }

        function startLocationPinMode() {
            if (locationPinMode || !currentCourse) return;
            stopDrawMode();
            stopSegmentPinMode();
            locationPinMode = true;
            updateAddLocationButton();
            if (!Array.isArray(currentCourse.locations)) currentCourse.locations = [];
            mapClickHandler = function (e) {
                var content = document.createElement('div');
                content.style.minWidth = '180px';
                var lblType = document.createElement('label');
                lblType.textContent = 'Type';
                content.appendChild(lblType);
                var sel = document.createElement('select');
                sel.style.display = 'block';
                sel.style.width = '100%';
                sel.style.marginBottom = '8px';
                LOCATION_TYPES.forEach(function (t) {
                    var opt = document.createElement('option');
                    opt.value = t.value;
                    opt.textContent = t.label;
                    sel.appendChild(opt);
                });
                content.appendChild(sel);
                var lblLabel = document.createElement('label');
                lblLabel.textContent = 'Label (optional)';
                content.appendChild(lblLabel);
                var input = document.createElement('input');
                input.type = 'text';
                input.placeholder = 'Label';
                input.style.display = 'block';
                input.style.width = '100%';
                input.style.marginBottom = '8px';
                input.style.boxSizing = 'border-box';
                content.appendChild(input);
                var btnAdd = document.createElement('button');
                btnAdd.type = 'button';
                btnAdd.textContent = 'Add';
                btnAdd.style.marginRight = '6px';
                var btnCancel = document.createElement('button');
                btnCancel.type = 'button';
                btnCancel.textContent = 'Cancel';
                content.appendChild(btnAdd);
                content.appendChild(btnCancel);
                var pop = L.popup().setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
                btnAdd.onclick = function () {
                    var locType = sel.value || 'course';
                    var locLabel = (input.value && input.value.trim()) ? input.value.trim() : '';
                    currentCourse.locations.push({
                        id: 'loc_' + Date.now(),
                        loc_type: locType,
                        loc_label: locLabel,
                        lat: e.latlng.lat,
                        lon: e.latlng.lng
                    });
                    window.courseMappingMap.closePopup();
                    renderLocationPins();
                    renderLocationsList();
                    updateCourseUI();
                };
                btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
            };
            map.on('click', mapClickHandler);
        }

        function stopLocationPinMode() {
            locationPinMode = false;
            updateAddLocationButton();
            if (mapClickHandler) {
                map.off('click', mapClickHandler);
                mapClickHandler = null;
            }
        }

        if (btnDraw) {
            btnDraw.addEventListener('click', function () {
                if (drawMode) stopDrawMode(); else startDrawMode();
            });
        }
        if (btnClear) {
            btnClear.addEventListener('click', function () {
                if (!currentCourse) return;
                currentCourse.geometry = null;
                if (currentCourse.segment_breaks) currentCourse.segment_breaks = [];
                currentCourse.segments = [];
                stopDrawMode();
                stopSegmentPinMode();
                renderCourseLine();
                renderSegmentPins();
                renderSegmentsList();
                renderStartFinishIcons();
                updateDrawButtons();
                updateSegmentPinButton();
                updateUndoButton();
                updateExportButton();
                updateCourseUI();
            });
        }

        var btnUndo = document.getElementById('btn-undo-point');
        if (btnUndo) btnUndo.addEventListener('click', undoLastPoint);

        var btnSegmentPin = document.getElementById('btn-add-segment-pin');
        if (btnSegmentPin) {
            btnSegmentPin.addEventListener('click', function () {
                if (segmentPinMode) stopSegmentPinMode(); else startSegmentPinMode();
            });
        }

        var btnAddLocation = document.getElementById('btn-add-location');
        if (btnAddLocation) {
            btnAddLocation.addEventListener('click', function () {
                if (locationPinMode) stopLocationPinMode(); else startLocationPinMode();
            });
        }

        var btnExport = document.getElementById('btn-export');
        if (btnExport) {
            btnExport.addEventListener('click', function () {
                if (!currentCourseId || !currentCourse) return;
                window.location.href = '/api/courses/' + encodeURIComponent(currentCourseId) + '/export?segments=1&flow=1&locations=1&gpx=1';
            });
        }

        updateCourseUI();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateAddLocationButton();
        updateExportButton();
    } catch (e) {
        console.error('Course mapping map init failed:', e);
        if (loadingEl) loadingEl.textContent = 'Failed to load map';
    }
});
