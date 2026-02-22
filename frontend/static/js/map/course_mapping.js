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
    let courseDirty = false;

    function blankCourse() {
        return {
            id: null,
            name: '',
            description: '',
            segments: [],
            locations: [],
            geometry: null,
            segment_breaks: [],
            segment_break_labels: {},
            segment_break_descriptions: {},
            segment_break_ids: {},
            turnaround_indices: []
        };
    }

    function setDirty() { courseDirty = true; }
    function clearDirty() { courseDirty = false; }
    function isDirty() { return courseDirty; }

    var isEditMode = false;

    function setEditMode(edit) {
        isEditMode = !!edit;
        var nameText = document.getElementById('course-map-name-text');
        var nameInput = document.getElementById('course-map-name');
        var descText = document.getElementById('course-map-description-text');
        var descInput = document.getElementById('course-map-description');
        var editToolbar = document.getElementById('course-edit-toolbar');
        var saveBtn = document.getElementById('btn-save-course');
        var editBtn = document.getElementById('btn-edit-course');
        var exportBtn = document.getElementById('btn-export');
        var delBtn = document.getElementById('btn-delete-course');
        if (nameText) nameText.style.display = isEditMode ? 'none' : 'inline';
        if (nameInput) nameInput.style.display = (isEditMode && currentCourse) ? 'inline-block' : 'none';
        if (descText) descText.style.display = isEditMode ? 'none' : 'inline';
        if (descInput) {
            descInput.style.display = (isEditMode && currentCourse) ? 'block' : 'none';
            if (isEditMode && currentCourse) resizeDescriptionTextarea();
        }
        if (editToolbar) editToolbar.style.display = (isEditMode && currentCourse) ? 'flex' : 'none';
        if (saveBtn) saveBtn.style.display = isEditMode ? 'inline-block' : 'none';
        if (editBtn) editBtn.textContent = isEditMode ? 'Cancel' : 'Edit';
        if (exportBtn) exportBtn.style.display = isEditMode ? 'none' : 'inline-block';
        if (delBtn) delBtn.style.display = isEditMode ? 'none' : 'inline-block';
        if (!isEditMode && nameInput && descInput && currentCourse) {
            nameInput.value = currentCourse.name || '';
            descInput.value = currentCourse.description || '';
        }
        renderCourseLine();
        renderSegmentPins();
        renderLocationPins();
        updateSameRouteBackButtons();
    }

    function resizeDescriptionTextarea() {
        var el = document.getElementById('course-map-description');
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = Math.max(el.scrollHeight, 2.5 * 16) + 'px';
    }

    function syncCourseToHeaderInputs() {
        var nameText = document.getElementById('course-map-name-text');
        var nameInput = document.getElementById('course-map-name');
        var descText = document.getElementById('course-map-description-text');
        var descInput = document.getElementById('course-map-description');
        var val = currentCourse ? (currentCourse.name || '') : '';
        if (nameText) nameText.textContent = val || '(no name)';
        if (nameInput) nameInput.value = val;
        val = currentCourse ? (currentCourse.description || '') : '';
        if (descText) descText.textContent = val || '(none)';
        if (descInput) {
            descInput.value = val;
            if (descInput.style.display && descInput.style.display !== 'none') resizeDescriptionTextarea();
        }
    }

    function updateCourseUI() {
        const saveBtn = document.getElementById('btn-save-course');
        const idEl = document.getElementById('course-map-id');
        const exportBtn = document.getElementById('btn-export');
        const delBtn = document.getElementById('btn-delete-course');
        if (saveBtn) {
            saveBtn.disabled = !currentCourse || sameRouteBackMode;
            saveBtn.title = sameRouteBackMode ? 'Confirm or Cancel Same Route Back first' : '';
        }
        if (idEl) idEl.textContent = currentCourseId ? 'Course: ' + currentCourseId : '';
        if (exportBtn) exportBtn.disabled = !currentCourseId;
        if (delBtn) delBtn.disabled = !currentCourseId;
        syncCourseToHeaderInputs();
        setEditMode(isEditMode);
        updateExportButton();
    }

    function setCourse(id, course) {
        currentCourseId = id;
        currentCourse = course;
        clearDirty();
        isEditMode = false;
        if (window.courseMappingMap && (!course || !course.geometry)) {
            if (segmentLinesLayer) { window.courseMappingMap.removeLayer(segmentLinesLayer); segmentLinesLayer = null; }
            if (segmentInfoIconsLayer) { window.courseMappingMap.removeLayer(segmentInfoIconsLayer); segmentInfoIconsLayer = null; }
            if (segmentPinsLayer) { window.courseMappingMap.removeLayer(segmentPinsLayer); segmentPinsLayer = null; }
            if (startFinishLayer) { window.courseMappingMap.removeLayer(startFinishLayer); startFinishLayer = null; }
            if (locationsLayer) { window.courseMappingMap.removeLayer(locationsLayer); locationsLayer = null; }
            if (turnaroundMarkerLayer) { window.courseMappingMap.removeLayer(turnaroundMarkerLayer); turnaroundMarkerLayer = null; }
            if (uturnIconsLayer) { window.courseMappingMap.removeLayer(uturnIconsLayer); uturnIconsLayer = null; }
        }
        if (currentCourse && !Array.isArray(currentCourse.segment_breaks)) currentCourse.segment_breaks = [];
        if (currentCourse && !Array.isArray(currentCourse.locations)) currentCourse.locations = [];
        if (currentCourse && typeof currentCourse.segment_break_labels !== 'object') currentCourse.segment_break_labels = {};
        if (currentCourse && typeof currentCourse.segment_break_descriptions !== 'object') currentCourse.segment_break_descriptions = {};
        if (currentCourse && typeof currentCourse.segment_break_ids !== 'object') currentCourse.segment_break_ids = {};
        if (currentCourse && !Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = [];
        syncCourseToHeaderInputs();
        updateCourseUI();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateAddLocationButton();
        updateSameRouteBackButtons();
        updateExportButton();
        renderCourseLine();
        renderSegmentPins();
        renderLocationPins();
        syncSegmentsFromBreaks();
        renderSegmentsList();
        renderLocationsList();
        renderStartFinishIcons();
        renderUturnIcons();
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
    let turnaroundMarkerLayer = null;
    let uturnIconsLayer = null;
    let drawMode = false;
    let sameRouteBackMode = false;
    let segmentPinMode = false;
    let locationPinMode = false;
    let drawRoutingInProgress = false;
    let mapClickHandler = null;
    var lastAddedPointCount = 0;

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

    function escapeHtml(s) {
        if (s == null) return '';
        var t = String(s);
        return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function buildPopupRowsHtml(rows) {
        var html = '<div class="course-map-popup">';
        rows.forEach(function (r) {
            var val = r.value != null && r.value !== '' ? String(r.value) : '(none)';
            html += '<div class="popup-row"><span class="popup-label">' + escapeHtml(r.label) + ':</span> <span class="popup-value">' + escapeHtml(val) + '</span></div>';
        });
        html += '</div>';
        return html;
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
        var eventIds = (EVENT_CHOICES || []).map(function (e) { return e.value || e; });
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
            var pinLabel = (currentCourse.segment_break_labels && (currentCourse.segment_break_labels[endIdx] || currentCourse.segment_break_labels['' + endIdx] || '').trim()) || '';
            var isLastSegment = (b >= breaks.length && endIdx === coords.length - 1);
            var defaultLabel = pinLabel || (isLastSegment ? 'Finish' : ('Segment ' + (segs.length + 1)));
            segs.push({
                seg_id: String(segs.length + 1),
                seg_label: (prev && prev.seg_label) ? prev.seg_label : defaultLabel,
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
            var endIdx0 = coords.length - 1;
            var pinLabel0 = (currentCourse.segment_break_labels && (currentCourse.segment_break_labels[endIdx0] || currentCourse.segment_break_labels['' + endIdx0] || '').trim()) || '';
            segs.push({
                seg_id: '1',
                seg_label: (prev0 && prev0.seg_label) ? prev0.seg_label : (pinLabel0 || 'Segment 1'),
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
        const hasCourse = !!currentCourse;
        if (drawBtn) drawBtn.disabled = !hasCourse;
        if (clearBtn) clearBtn.disabled = !hasCourse || !(currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length);
        if (drawBtn && drawMode) drawBtn.classList.add('active'); else if (drawBtn) drawBtn.classList.remove('active');
        updateSameRouteBackButtons();
    }

    function updateSegmentPinButton() {
        const btn = document.getElementById('btn-add-segment-pin');
        if (btn) btn.disabled = !currentCourse;
        if (btn && segmentPinMode) btn.classList.add('active'); else if (btn) btn.classList.remove('active');
    }

    function updateUndoButton() {
        const btn = document.getElementById('btn-undo-point');
        const canUndo = !!(currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length > 0);
        if (btn) btn.disabled = !currentCourse || !canUndo;
    }

    function updateAddLocationButton() {
        const btn = document.getElementById('btn-add-location');
        if (btn) btn.disabled = !currentCourse;
        if (btn && locationPinMode) btn.classList.add('active'); else if (btn) btn.classList.remove('active');
    }

    function updateSameRouteBackButtons() {
        var btnSame = document.getElementById('btn-same-route-back');
        var btnConfirm = document.getElementById('btn-confirm-turnaround');
        var btnCancel = document.getElementById('btn-cancel-turnaround');
        var canSame = !!(currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length >= 3) && drawMode && isEditMode;
        if (btnSame) {
            btnSame.disabled = !canSame;
            btnSame.style.display = (isEditMode && drawMode && !sameRouteBackMode) ? 'inline-block' : 'none';
        }
        if (btnConfirm) {
            btnConfirm.disabled = !sameRouteBackMode;
            btnConfirm.style.display = sameRouteBackMode ? 'inline-block' : 'none';
        }
        if (btnCancel) {
            btnCancel.disabled = !sameRouteBackMode;
            btnCancel.style.display = sameRouteBackMode ? 'inline-block' : 'none';
        }
        if (btnSame && sameRouteBackMode) btnSame.classList.add('active'); else if (btnSame) btnSame.classList.remove('active');
    }

    function updateExportButton() {
        const btn = document.getElementById('btn-export');
        const canExport = !!(currentCourseId && currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length >= 2);
        if (btn) btn.disabled = !canExport;
    }

    function undoLastPoint() {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length === 0) return;
        var coords = currentCourse.geometry.coordinates;
        var toRemove = (lastAddedPointCount > 0 && lastAddedPointCount < coords.length) ? lastAddedPointCount : 1;
        for (var i = 0; i < toRemove; i++) coords.pop();
        lastAddedPointCount = 0;
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
        setDirty();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateCourseUI();
    }

    function openSegmentAnnotationPopup(segIdx, latlng) {
        var s = currentCourse.segments[segIdx];
        if (!s) return;
        var segId = (s.seg_id != null && s.seg_id !== '') ? String(s.seg_id) : String(segIdx + 1);
        var content = document.createElement('div');
        content.style.minWidth = '240px';
        content.innerHTML = '<strong>Segment ' + segId + '</strong><br/>';
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
        var pop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            s.seg_label = (inputLabel.value && inputLabel.value.trim()) ? inputLabel.value.trim() : segId;
            s.width_m = parseFloat(inputWidth.value);
            if (isNaN(s.width_m) || s.width_m < 0) s.width_m = 3;
            s.schema = selSchema.value || 'on_course_open';
            s.direction = selDirection.value || 'uni';
            s.description = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
            s.events = [];
            eventsDiv.querySelectorAll('input[type="checkbox"]').forEach(function (cb) { if (cb.checked) s.events.push(cb.value); });
            if (s.events.length === 0) s.events = (EVENT_CHOICES || []).map(function (e) { return e.value || e; });
            window.courseMappingMap.closePopup();
            renderSegmentInfoIcons();
            renderSegmentPins();
            renderSegmentsList();
            setDirty();
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

    function isSegmentAnnotated(seg, segIdx) {
        var defaultLabel = 'Segment S' + ((segIdx != null ? segIdx + 1 : 1));
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
            if (!isSegmentAnnotated(seg, segIdx)) return;
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
            var m = L.marker([lat, lon], { icon: icon, draggable: isEditMode });
            m._segmentIndex = segIdx;
            var seg = currentCourse.segments[segIdx];
            var segId = (seg.seg_id != null && seg.seg_id !== '') ? String(seg.seg_id) : String(segIdx + 1);
            var tipHtml = buildPopupRowsHtml([
                { label: 'Seg ID', value: segId },
                { label: 'Label', value: seg.seg_label },
                { label: 'Description', value: seg.description },
                { label: 'Events', value: (seg.events || []).join(', ') || '(none)' }
            ]) + (isEditMode ? '<div class="popup-row" style="font-size:0.75rem;color:#7f8c8d;">(drag to move)</div>' : '');
            m.bindTooltip(tipHtml, { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
            m.on('dragend', function () {
                var ll = m.getLatLng();
                var segEl = currentCourse.segments[m._segmentIndex];
                if (segEl) {
                    segEl.info_icon_lat = ll.lat;
                    segEl.info_icon_lon = ll.lng;
                    renderSegmentInfoIcons();
                    setDirty();
                    updateCourseUI();
                }
            });
            m.on('click', function (e) {
                if (locationPinMode) return;
                L.DomEvent.stopPropagation(e);
                if (segmentPinMode) return;
                var s = currentCourse.segments[m._segmentIndex];
                if (!s) return;
                var evts = (s.events || []).join(', ') || '(none)';
                var segId = (s.seg_id != null && s.seg_id !== '') ? String(s.seg_id) : String(m._segmentIndex + 1);
                var info = document.createElement('div');
                info.innerHTML = buildPopupRowsHtml([
                    { label: 'Seg ID', value: segId },
                    { label: 'Label', value: s.seg_label },
                    { label: 'Description', value: s.description },
                    { label: 'Width', value: (s.width_m != null ? s.width_m : 3) + ' m' },
                    { label: 'Schema', value: s.schema || 'on_course_open' },
                    { label: 'Direction', value: s.direction || 'uni' },
                    { label: 'Events', value: evts },
                    { label: 'From–To (km)', value: (s.from_km != null ? s.from_km : '') + ' – ' + (s.to_km != null ? s.to_km : '') }
                ]);
                if (isEditMode) {
                    var btnEdit = document.createElement('button');
                    btnEdit.type = 'button';
                    btnEdit.textContent = 'Edit';
                    btnEdit.style.marginTop = '6px';
                    info.appendChild(btnEdit);
                    btnEdit.onclick = function () {
                        window.courseMappingMap.closePopup();
                        openSegmentAnnotationPopup(m._segmentIndex, e.latlng);
                    };
                }
                var pop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(info).setLatLng(e.latlng).openOn(window.courseMappingMap);
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
        var turnaroundSet = new Set(Array.isArray(currentCourse.turnaround_indices) ? currentCourse.turnaround_indices : []);
        var lastIdx = coords.length - 1;
        startFinishLayer = L.layerGroup();
        var first = coords[0];
        var last = coords.length >= 2 ? coords[lastIdx] : null;
        var lastIsTurnaround = turnaroundSet.has(lastIdx);
        var samePoint = last && !lastIsTurnaround && Math.abs(first[0] - last[0]) < 1e-9 && Math.abs(first[1] - last[1]) < 1e-9;
        if (samePoint && last) {
            var sfIcon = L.divIcon({
                className: 'start-finish-icon',
                html: '<div style="width:20px;height:20px;background:#27ae60;color:#fff;border:2px solid #1e8449;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;">S/F</div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            startFinishLayer.addLayer(L.marker([first[1], first[0]], { icon: sfIcon }));
        } else {
            var startIcon = L.divIcon({
                className: 'start-finish-icon',
                html: '<div style="width:20px;height:20px;background:#27ae60;color:#fff;border:2px solid #1e8449;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">S</div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            startFinishLayer.addLayer(L.marker([first[1], first[0]], { icon: startIcon }));
            if (coords.length >= 2 && !lastIsTurnaround) {
                var finishIcon = L.divIcon({
                    className: 'start-finish-icon',
                    html: '<div style="width:20px;height:20px;background:#27ae60;color:#fff;border:2px solid #1e8449;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">F</div>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                });
                startFinishLayer.addLayer(L.marker([last[1], last[0]], { icon: finishIcon }));
            }
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
                if (sameRouteBackMode && e && e.latlng) {
                    L.DomEvent.stopPropagation(e);
                    setTurnaroundFromClick(e.latlng);
                    return;
                }
                if (segmentPinMode || locationPinMode) return;
                L.DomEvent.stopPropagation(e);
                var latlng = e.latlng || (latlngs.length ? L.latLng(latlngs[Math.floor(latlngs.length / 2)][0], latlngs[Math.floor(latlngs.length / 2)][1]) : null);
                var idx = latlng ? segmentIndexAtLatLng(latlng) : segIdx;
                if (latlng) {
                    if (isEditMode) {
                        openSegmentAnnotationPopup(idx, latlng);
                    } else {
                        var s = currentCourse.segments[idx];
                        if (!s) return;
                        var segId = (s.seg_id != null && s.seg_id !== '') ? String(s.seg_id) : String(idx + 1);
                        var viewInfo = document.createElement('div');
                        viewInfo.innerHTML = buildPopupRowsHtml([
                            { label: 'Seg ID', value: segId },
                            { label: 'Label', value: s.seg_label },
                            { label: 'Description', value: s.description },
                            { label: 'Width', value: (s.width_m != null ? s.width_m : 3) + ' m' },
                            { label: 'Schema', value: s.schema || 'on_course_open' },
                            { label: 'Direction', value: s.direction || 'uni' },
                            { label: 'Events', value: (s.events || []).join(', ') || '(none)' },
                            { label: 'From–To (km)', value: (s.from_km != null ? s.from_km : '') + ' – ' + (s.to_km != null ? s.to_km : '') }
                        ]);
                        L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(viewInfo).setLatLng(latlng).openOn(window.courseMappingMap);
                    }
                }
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
        renderUturnIcons();
    }

    function getSegmentBreakLabel(idx) {
        if (!currentCourse || !currentCourse.segment_break_labels) return '';
        return (currentCourse.segment_break_labels[idx] || currentCourse.segment_break_labels['' + idx] || '').trim();
    }

    function getPinLabelForIndex(idx, coordsLen) {
        if (idx <= 0) return 'Start';
        if (coordsLen && idx >= coordsLen - 1) return 'Finish';
        return getSegmentBreakLabel(idx) || '';
    }

    function getSegmentBreakDescription(idx) {
        if (!currentCourse || !currentCourse.segment_break_descriptions) return '';
        return (currentCourse.segment_break_descriptions[idx] || currentCourse.segment_break_descriptions['' + idx] || '').trim();
    }

    function getSegmentBreakId(idx) {
        if (!currentCourse || !currentCourse.segment_break_ids) return idx;
        var id = currentCourse.segment_break_ids[idx] || currentCourse.segment_break_ids['' + idx];
        return id != null ? id : idx;
    }

    function nextSegmentPinId() {
        if (!currentCourse || !currentCourse.segment_break_ids) return 1;
        var ids = Object.values(currentCourse.segment_break_ids);
        var max = 0;
        ids.forEach(function (v) { var n = parseInt(v, 10); if (!isNaN(n) && n > max) max = n; });
        return max + 1;
    }

    function nextLocationId() {
        if (!currentCourse || !currentCourse.locations || currentCourse.locations.length === 0) return 1;
        var max = 0;
        currentCourse.locations.forEach(function (loc) {
            var v = loc.id;
            var n = typeof v === 'number' ? v : parseInt(String(v).replace(/^loc_/, ''), 10);
            if (!isNaN(n) && n > max) max = n;
        });
        return max + 1;
    }

    function openSegmentPinFormTile(idx, latlng, onSave) {
        var label = getSegmentBreakLabel(idx);
        var desc = getSegmentBreakDescription(idx);
        var content = document.createElement('div');
        content.style.minWidth = '220px';
        var lblLabel = document.createElement('label');
        lblLabel.textContent = 'Label';
        content.appendChild(lblLabel);
        var inputLabel = document.createElement('input');
        inputLabel.type = 'text';
        inputLabel.placeholder = 'Segment boundary label';
        inputLabel.value = label;
        inputLabel.style.display = 'block';
        inputLabel.style.width = '100%';
        inputLabel.style.marginBottom = '8px';
        inputLabel.style.boxSizing = 'border-box';
        content.appendChild(inputLabel);
        var lblDesc = document.createElement('label');
        lblDesc.textContent = 'Description';
        content.appendChild(lblDesc);
        var inputDesc = document.createElement('textarea');
        inputDesc.rows = 2;
        inputDesc.placeholder = 'Optional description';
        inputDesc.value = desc;
        inputDesc.style.display = 'block';
        inputDesc.style.width = '100%';
        inputDesc.style.marginBottom = '8px';
        inputDesc.style.boxSizing = 'border-box';
        content.appendChild(inputDesc);
        var btnSave = document.createElement('button');
        btnSave.type = 'button';
        btnSave.textContent = 'Save';
        btnSave.style.marginRight = '6px';
        var btnCancel = document.createElement('button');
        btnCancel.type = 'button';
        btnCancel.textContent = 'Cancel';
        content.appendChild(btnSave);
        content.appendChild(btnCancel);
        var pop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
            if (!currentCourse.segment_break_descriptions) currentCourse.segment_break_descriptions = {};
            currentCourse.segment_break_labels[idx] = (inputLabel.value && inputLabel.value.trim()) ? inputLabel.value.trim() : '';
            currentCourse.segment_break_descriptions[idx] = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
            window.courseMappingMap.closePopup();
            setDirty();
            if (onSave) onSave();
        };
        btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
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
            var m = L.marker([c[1], c[0]], { icon: squareIcon, draggable: isEditMode });
            m._segmentBreakIndex = idx;
            var desc = getSegmentBreakDescription(idx);
            var pinId = getSegmentBreakId(idx);
            var tipHtml = buildPopupRowsHtml([
                { label: 'ID', value: pinId },
                { label: 'Label', value: label },
                { label: 'Description', value: desc }
            ]) + (isEditMode ? '<div class="popup-row" style="font-size:0.75rem;color:#7f8c8d;">Segment boundary (drag to move)</div>' : '');
            m.bindTooltip(tipHtml, { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
            m.on('dragend', function () {
                var ll = m.getLatLng();
                currentCourse.geometry.coordinates[idx] = [ll.lng, ll.lat];
                renderCourseLine();
                renderSegmentPins();
                syncSegmentsFromBreaks();
                renderSegmentsList();
                setDirty();
                updateCourseUI();
            });
            m.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                var i = e.target._segmentBreakIndex;
                var pinId = getSegmentBreakId(i);
                var label = getSegmentBreakLabel(i);
                var desc = getSegmentBreakDescription(i);
                var content = document.createElement('div');
                content.innerHTML = buildPopupRowsHtml([
                    { label: 'ID', value: pinId },
                    { label: 'Label', value: label },
                    { label: 'Description', value: desc }
                ]);
                content.classList.add('course-map-popup-wrap');
                if (isEditMode) {
                    var btnWrap = document.createElement('div');
                    btnWrap.style.marginTop = '0.5rem';
                    var btnEdit = document.createElement('button');
                    btnEdit.type = 'button';
                    btnEdit.textContent = 'Edit';
                    btnEdit.style.marginRight = '6px';
                    btnEdit.style.marginTop = '6px';
                    var btnDel = document.createElement('button');
                    btnDel.type = 'button';
                    btnDel.textContent = 'Delete';
                    btnWrap.appendChild(btnEdit);
                    btnWrap.appendChild(btnDel);
                    content.appendChild(btnWrap);
                    btnEdit.onclick = function () {
                        window.courseMappingMap.closePopup();
                        openSegmentPinFormTile(i, e.latlng, function () {
                            renderSegmentPins();
                            renderSegmentsList();
                            updateCourseUI();
                        });
                    };
                    btnDel.onclick = function () {
                        if (!window.confirm('Remove this segment boundary? This cannot be undone.')) return;
                        window.courseMappingMap.closePopup();
                        currentCourse.segment_breaks = currentCourse.segment_breaks.filter(function (x) { return x !== i; });
                        if (currentCourse.segment_break_labels) delete currentCourse.segment_break_labels[i];
                        if (currentCourse.segment_break_descriptions) delete currentCourse.segment_break_descriptions[i];
                        if (currentCourse.segment_break_ids) delete currentCourse.segment_break_ids[i];
                        syncSegmentsFromBreaks();
                        renderSegmentPins();
                        renderSegmentsList();
                        setDirty();
                        updateCourseUI();
                    };
                }
                var pop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
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
            card.style.display = currentCourse ? 'block' : 'none';
            if (empty) empty.style.display = 'block';
            if (wrap) wrap.style.display = 'none';
            return;
        }
        card.style.display = 'block';
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        tbody.innerHTML = '';
        var coords = (currentCourse.geometry && currentCourse.geometry.coordinates) || [];
        var coordsLen = coords.length;
        currentCourse.segments.forEach(function (seg, segIdx) {
            var len = (seg.to_km - seg.from_km);
            var startIdx = seg.start_index != null ? seg.start_index : 0;
            var endIdx = seg.end_index != null ? seg.end_index : (coordsLen ? coordsLen - 1 : 0);
            var segId = (seg.seg_id != null && seg.seg_id !== '') ? String(seg.seg_id) : String(segIdx + 1);
            var pinStart = getPinLabelForIndex(startIdx, coordsLen);
            var pinEnd = getPinLabelForIndex(endIdx, coordsLen);
            var displayLabel = (seg.seg_label && seg.seg_label.trim()) ? seg.seg_label : (pinEnd || '');
            var width = (seg.width_m != null && seg.width_m !== '') ? seg.width_m : 3;
            var tr = document.createElement('tr');
            tr.innerHTML = '<td>' + segId + '</td><td>' + escapeHtml(pinStart) + '</td><td>' + escapeHtml(pinEnd) + '</td><td>' + escapeHtml(displayLabel || '') + '</td><td>' + width + '</td><td>' + seg.from_km + '</td><td>' + seg.to_km + '</td><td>' + Math.round(len * 100) / 100 + '</td>';
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
            var m = L.marker([lat, lon], { icon: locIcon, draggable: isEditMode });
            m._locationIndex = i;
            var locId = loc.id != null ? String(loc.id) : (i + 1);
            var tipHtml = buildPopupRowsHtml([
                { label: 'ID', value: locId },
                { label: 'Label', value: loc.loc_label || getLocationTypeLabel(loc.loc_type) || 'Location' },
                { label: 'Type', value: getLocationTypeLabel(loc.loc_type) },
                { label: 'Description', value: loc.loc_description || '' }
            ]) + (isEditMode ? '<div class="popup-row" style="font-size:0.75rem;color:#7f8c8d;">(drag to move)</div>' : '');
            m.bindTooltip(tipHtml, { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
            m.on('dragend', function () {
                var ll = m.getLatLng();
                loc.lat = ll.lat;
                loc.lon = ll.lng;
                renderLocationPins();
                renderLocationsList();
                setDirty();
                updateCourseUI();
            });
            m.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                var idx = e.target._locationIndex;
                var locEl = currentCourse.locations[idx];
                if (!locEl) return;
            var locId = locEl.id != null ? String(locEl.id) : (idx + 1);
            var name = locEl.loc_label || getLocationTypeLabel(locEl.loc_type) || 'Location';
            var typeLabel = getLocationTypeLabel(locEl.loc_type);
            var desc = locEl.loc_description || '';
                var content = document.createElement('div');
                content.innerHTML = buildPopupRowsHtml([
                    { label: 'ID', value: locId },
                    { label: 'Label', value: name },
                    { label: 'Type', value: typeLabel },
                    { label: 'Description', value: desc }
                ]);
                content.classList.add('course-map-popup-wrap');
                if (isEditMode) {
                    var btnWrap = document.createElement('div');
                    btnWrap.style.marginTop = '0.5rem';
                    var btnEdit = document.createElement('button');
                    btnEdit.type = 'button';
                    btnEdit.textContent = 'Edit';
                    btnEdit.style.marginRight = '6px';
                    var btnDel = document.createElement('button');
                    btnDel.type = 'button';
                    btnDel.textContent = 'Delete';
                    btnWrap.appendChild(btnEdit);
                    btnWrap.appendChild(btnDel);
                    content.appendChild(btnWrap);
                    btnEdit.onclick = function () {
                        window.courseMappingMap.closePopup();
                        var editContent = document.createElement('div');
                    editContent.style.minWidth = '180px';
                    var lblType = document.createElement('label');
                    lblType.textContent = 'Type';
                    editContent.appendChild(lblType);
                    var sel = document.createElement('select');
                    sel.style.display = 'block';
                    sel.style.width = '100%';
                    sel.style.marginBottom = '8px';
                    LOCATION_TYPES.forEach(function (t) {
                        var opt = document.createElement('option');
                        opt.value = t.value;
                        opt.textContent = t.label;
                        if ((locEl.loc_type || 'course') === t.value) opt.selected = true;
                        sel.appendChild(opt);
                    });
                    editContent.appendChild(sel);
                    var lblLabel = document.createElement('label');
                    lblLabel.textContent = 'Label (optional)';
                    editContent.appendChild(lblLabel);
                    var input = document.createElement('input');
                    input.type = 'text';
                    input.placeholder = 'Label';
                    input.value = locEl.loc_label || '';
                    input.style.display = 'block';
                    input.style.width = '100%';
                    input.style.marginBottom = '8px';
                    input.style.boxSizing = 'border-box';
                    editContent.appendChild(input);
                    var lblDesc = document.createElement('label');
                    lblDesc.textContent = 'Description (optional)';
                    editContent.appendChild(lblDesc);
                    var inputDesc = document.createElement('textarea');
                    inputDesc.rows = 2;
                    inputDesc.placeholder = 'Description';
                    inputDesc.value = locEl.loc_description || '';
                    inputDesc.style.display = 'block';
                    inputDesc.style.width = '100%';
                    inputDesc.style.marginBottom = '8px';
                    inputDesc.style.boxSizing = 'border-box';
                    editContent.appendChild(inputDesc);
                    var btnSave = document.createElement('button');
                    btnSave.type = 'button';
                    btnSave.textContent = 'Save';
                    btnSave.style.marginRight = '6px';
                    var btnCancel = document.createElement('button');
                    btnCancel.type = 'button';
                    btnCancel.textContent = 'Cancel';
                    editContent.appendChild(btnSave);
                    editContent.appendChild(btnCancel);
                    var editPop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(editContent).setLatLng(e.latlng).openOn(window.courseMappingMap);
                    btnSave.onclick = function () {
                        locEl.loc_type = sel.value || 'course';
                        locEl.loc_label = (input.value && input.value.trim()) ? input.value.trim() : '';
                        locEl.loc_description = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
                        window.courseMappingMap.closePopup();
                        renderLocationPins();
                        renderLocationsList();
                        setDirty();
                        updateCourseUI();
                    };
                    btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
                };
                btnDel.onclick = function () {
                    if (!window.confirm('Remove this location? This cannot be undone.')) return;
                    window.courseMappingMap.closePopup();
                    currentCourse.locations.splice(idx, 1);
                    renderLocationPins();
                    renderLocationsList();
                    setDirty();
                    updateCourseUI();
                };
                }
                var pop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
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
            card.style.display = currentCourse ? 'block' : 'none';
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
                    setDirty();
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
        const courseTbody = document.getElementById('course-list-tbody');
        const courseTable = document.getElementById('course-list-table');
        const btnSave = document.getElementById('btn-save-course');
        let coursesListData = [];
        let courseSortColumn = 'updated';
        let courseSortDirection = 'desc';

        function confirmUnsavedChanges(callback) {
            if (isDirty()) {
                if (!window.confirm('You have unsaved changes. Discard them and continue?')) return;
            }
            if (callback) callback();
        }

        function truncate(str, len) {
            if (!str) return '';
            var s = String(str).trim();
            return s.length <= len ? s : s.slice(0, len) + '…';
        }

        function formatSavedOn(iso) {
            if (!iso) return '—';
            try {
                var d = new Date(iso);
                var m = ('0' + (d.getMonth() + 1)).slice(-2);
                var day = ('0' + d.getDate()).slice(-2);
                var h = ('0' + d.getHours()).slice(-2);
                var min = ('0' + d.getMinutes()).slice(-2);
                return m + '-' + day + ' ' + h + ':' + min;
            } catch (e) { return '—'; }
        }

        function sortCourses(list) {
            return list.slice().sort(function (a, b) {
                var av = a[courseSortColumn];
                var bv = b[courseSortColumn];
                if (courseSortColumn === 'updated') {
                    av = av ? new Date(av).getTime() : 0;
                    bv = bv ? new Date(bv).getTime() : 0;
                    return courseSortDirection === 'desc' ? (bv - av) : (av - bv);
                }
                if (typeof av === 'number' && typeof bv === 'number') return courseSortDirection === 'asc' ? (av - bv) : (bv - av);
                av = (av != null ? String(av) : '');
                bv = (bv != null ? String(bv) : '');
                return courseSortDirection === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
            });
        }

        function renderCourseTable() {
            if (!courseTbody) return;
            var sorted = sortCourses(coursesListData);
            if (sorted.length === 0) {
                courseTbody.innerHTML = '<tr><td colspan="6" class="placeholder">No courses yet. Click New course to create one.</td></tr>';
                return;
            }
            courseTbody.innerHTML = '';
            sorted.forEach(function (c) {
                var tr = document.createElement('tr');
                tr.className = 'course-row';
                tr.dataset.courseId = c.id;
                if (c.id === currentCourseId) tr.classList.add('selected');
                tr.innerHTML = '<td>' + escapeHtml(truncate(c.name || '(Untitled)', 30)) + '</td><td>' + escapeHtml(truncate(c.description || '', 30)) + '</td><td>' + formatSavedOn(c.updated) + '</td><td style="text-align:right">' + (c.distance_km != null ? c.distance_km.toFixed(2) + ' km' : '—') + '</td><td style="text-align:center">' + (c.segments_count != null ? c.segments_count : 0) + '</td><td style="text-align:center">' + (c.locations_count != null ? c.locations_count : 0) + '</td>';
                tr.addEventListener('click', function () {
                    confirmUnsavedChanges(function () { loadCourseById(c.id); });
                });
                courseTbody.appendChild(tr);
            });
        }

        function loadCourseList() {
            fetch('/api/courses')
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (!data.ok || !data.courses) {
                        coursesListData = [];
                    } else {
                        coursesListData = data.courses;
                    }
                    renderCourseTable();
                    if (coursesListData.length > 0 && !currentCourseId) {
                        var first = sortCourses(coursesListData)[0];
                        if (first) loadCourseById(first.id);
                    }
                })
                .catch(function (e) {
                    console.error('List courses failed:', e);
                    coursesListData = [];
                    if (courseTbody) courseTbody.innerHTML = '<tr><td colspan="6" class="placeholder">Failed to load courses.</td></tr>';
                });
        }

        function loadCourseById(id) {
            if (!id) return;
            fetch('/api/courses/' + encodeURIComponent(id))
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.ok && data.course) {
                        setCourse(data.course.id, data.course);
                        renderCourseTable();
                        console.log('Loaded course:', data.course.id);
                    }
                })
                .catch(function (e) {
                    console.error('Load course failed:', e);
                    alert('Failed to load course: ' + e.message);
                });
        }

        if (courseTable && courseTable.querySelectorAll('.table-sortable').length) {
            courseTable.querySelectorAll('.table-sortable').forEach(function (th) {
                th.addEventListener('click', function () {
                    var col = th.getAttribute('data-sort');
                    if (!col) return;
                    if (courseSortColumn === col) courseSortDirection = courseSortDirection === 'asc' ? 'desc' : 'asc';
                    else { courseSortColumn = col; courseSortDirection = 'desc'; }
                    courseTable.querySelectorAll('.table-sortable-indicator').forEach(function (ind) {
                        ind.textContent = '↕';
                    });
                    var ind = th.querySelector('.table-sortable-indicator');
                    if (ind) ind.textContent = courseSortDirection === 'asc' ? '↑' : '↓';
                    renderCourseTable();
                });
            });
        }

        if (btnNew) {
            btnNew.addEventListener('click', function () {
                confirmUnsavedChanges(function () {
                    setCourse(null, blankCourse());
                    renderCourseTable();
                });
            });
        }

        var btnDelete = document.getElementById('btn-delete-course');
        if (btnDelete) {
            btnDelete.addEventListener('click', function () {
                if (!currentCourseId) return;
                if (!window.confirm('Delete this course? This action cannot be undone.')) return;
                if (!window.confirm('Are you sure? The course folder and all files will be permanently deleted.')) return;
                fetch('/api/courses/' + encodeURIComponent(currentCourseId), { method: 'DELETE' })
                    .then(function (res) { return res.json(); })
                    .then(function (data) {
                        if (data.ok) {
                            setCourse(null, blankCourse());
                            loadCourseList();
                        } else alert('Delete failed');
                    })
                    .catch(function (e) {
                        alert('Delete failed: ' + e.message);
                    });
            });
        }

        var btnEdit = document.getElementById('btn-edit-course');
        if (btnEdit) {
            btnEdit.addEventListener('click', function () {
                if (isEditMode) {
                    if (isDirty() && !window.confirm('Discard unsaved changes?')) return;
                    clearDirty();
                    setEditMode(false);
                    syncCourseToHeaderInputs();
                } else {
                    setEditMode(true);
                }
            });
        }

        var nameInput = document.getElementById('course-map-name');
        var descInput = document.getElementById('course-map-description');
        if (nameInput) nameInput.addEventListener('input', function () { if (currentCourse) setDirty(); });
        if (descInput) descInput.addEventListener('input', function () {
            if (currentCourse) setDirty();
            resizeDescriptionTextarea();
        });

        if (btnSave) {
            btnSave.addEventListener('click', async function () {
                if (!currentCourse) return;
                var n = nameInput ? String(nameInput.value || '').trim().slice(0, 255) : '';
                var d = descInput ? String(descInput.value || '').trim().slice(0, 255) : '';
                currentCourse.name = n;
                currentCourse.description = d;
                try {
                    var courseIdToSave = currentCourseId;
                    if (!courseIdToSave) {
                        var createRes = await fetch('/api/courses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
                        var createData = await createRes.json();
                        if (!createRes.ok) throw new Error(createData.detail || createRes.statusText);
                        if (!createData.ok || !createData.id) throw new Error('Failed to create course');
                        courseIdToSave = createData.id;
                        currentCourse.id = courseIdToSave;
                    }
                    // Build payload with explicit geometry and turnaround_indices to ensure Same Route Back is persisted (Issue #732)
                    var toSave = JSON.parse(JSON.stringify({
                        id: currentCourse.id,
                        name: currentCourse.name,
                        description: currentCourse.description,
                        segments: currentCourse.segments || [],
                        locations: currentCourse.locations || [],
                        geometry: currentCourse.geometry,
                        segment_breaks: currentCourse.segment_breaks || [],
                        segment_break_labels: currentCourse.segment_break_labels || {},
                        segment_break_descriptions: currentCourse.segment_break_descriptions || {},
                        segment_break_ids: currentCourse.segment_break_ids || {},
                        turnaround_indices: Array.isArray(currentCourse.turnaround_indices) ? currentCourse.turnaround_indices.slice() : []
                    }));
                    const res = await fetch('/api/courses/' + encodeURIComponent(courseIdToSave), {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ course: toSave })
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (data.ok && data.course) {
                        setCourse(data.course.id, data.course);
                        loadCourseList();
                        console.log('Saved course:', data.course.id, data.course.name || '(no name)');
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
                if (drawRoutingInProgress || sameRouteBackMode) return;
                var snapEl = document.getElementById('snap-to-road');
                var coords = currentCourse.geometry.coordinates;
                var toPoint = [e.latlng.lng, e.latlng.lat];
                if (snapEl && snapEl.classList && snapEl.classList.contains('active') && coords.length >= 1) {
                    drawRoutingInProgress = true;
                    fetchRouteSegment(coords[coords.length - 1], toPoint, function (err, routeCoords) {
                        drawRoutingInProgress = false;
                        if (!err && routeCoords && routeCoords.length > 1) {
                            var before = coords.length;
                            for (var i = 1; i < routeCoords.length; i++) coords.push(routeCoords[i]);
                            lastAddedPointCount = coords.length - before;
                        } else {
                            coords.push(toPoint);
                            lastAddedPointCount = 1;
                        }
                        syncSegmentsFromBreaks();
                        renderCourseLine();
                        renderStartFinishIcons();
                        setDirty();
                        updateDrawButtons();
                        updateUndoButton();
                    });
                } else {
                    coords.push(toPoint);
                    lastAddedPointCount = 1;
                    syncSegmentsFromBreaks();
                    renderCourseLine();
                    renderStartFinishIcons();
                    setDirty();
                    updateDrawButtons();
                    updateUndoButton();
                }
            };
            map.on('click', mapClickHandler);
            renderStartFinishIcons();
        }

        function stopDrawMode() {
            drawMode = false;
            stopSameRouteBackMode();
            if (btnDraw) btnDraw.classList.remove('active');
            if (mapClickHandler) {
                map.off('click', mapClickHandler);
                mapClickHandler = null;
            }
        }

        var turnaroundMarkerIndex = 0;
        var turnaroundMarker = null;
        var sameRouteBackClickHandler = null;

        function setTurnaroundFromClick(latlng) {
            if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || !turnaroundMarker) return;
            var coords = currentCourse.geometry.coordinates;
            var idx = closestVertexIndex(latlng, coords);
            idx = Math.max(0, Math.min(idx, coords.length - 1));
            turnaroundMarkerIndex = idx;
            turnaroundMarker._turnaroundIndex = idx;
            var c = coords[idx];
            turnaroundMarker.setLatLng([c[1], c[0]]);
        }

        function startSameRouteBackMode() {
            if (sameRouteBackMode || !currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates) return;
            var coords = currentCourse.geometry.coordinates;
            if (coords.length < 3) return;
            stopSegmentPinMode();
            stopLocationPinMode();
            sameRouteBackMode = true;
            turnaroundMarkerIndex = Math.max(0, coords.length - 2);
            var c = coords[turnaroundMarkerIndex];
            var redIcon = L.divIcon({
                className: 'turnaround-marker',
                html: '<div style="width:20px;height:20px;background:#e74c3c;border:2px solid #c0392b;border-radius:50%;"></div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            if (turnaroundMarkerLayer) {
                window.courseMappingMap.removeLayer(turnaroundMarkerLayer);
                turnaroundMarkerLayer = null;
            }
            turnaroundMarkerLayer = L.layerGroup();
            turnaroundMarker = L.marker([c[1], c[0]], { icon: redIcon, draggable: true });
            turnaroundMarker._turnaroundIndex = turnaroundMarkerIndex;
            turnaroundMarker.bindTooltip('Click route or drag to set where return ends (finish point)', { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
            turnaroundMarker.on('dragend', function () {
                var ll = turnaroundMarker.getLatLng();
                setTurnaroundFromClick(ll);
            });
            turnaroundMarkerLayer.addLayer(turnaroundMarker);
            turnaroundMarkerLayer.addTo(window.courseMappingMap);
            sameRouteBackClickHandler = function (e) {
                if (!sameRouteBackMode || !turnaroundMarker) return;
                L.DomEvent.stopPropagation(e);
                setTurnaroundFromClick(e.latlng);
            };
            map.on('click', sameRouteBackClickHandler);
            updateSameRouteBackButtons();
        }

        function stopSameRouteBackMode() {
            sameRouteBackMode = false;
            if (sameRouteBackClickHandler) {
                map.off('click', sameRouteBackClickHandler);
                sameRouteBackClickHandler = null;
            }
            if (turnaroundMarkerLayer && window.courseMappingMap) {
                window.courseMappingMap.removeLayer(turnaroundMarkerLayer);
                turnaroundMarkerLayer = null;
            }
            turnaroundMarker = null;
            updateSameRouteBackButtons();
        }

        function confirmSameRouteBack() {
            if (!sameRouteBackMode || !currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates) return;
            var coords = currentCourse.geometry.coordinates;
            var k = turnaroundMarkerIndex;
            if (k < 0 || k >= coords.length) return;
            var turnaroundIdx = coords.length - 1;
            var returnSegment = [];
            for (var i = turnaroundIdx - 1; i >= k; i--) returnSegment.push(coords[i].slice());
            coords.push.apply(coords, returnSegment);
            if (!Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = [];
            currentCourse.turnaround_indices.push(turnaroundIdx);
            setDirty();
            stopSameRouteBackMode();
            syncSegmentsFromBreaks();
            renderCourseLine();
            renderSegmentPins();
            renderSegmentsList();
            renderStartFinishIcons();
            renderUturnIcons();
            setDirty();
            updateDrawButtons();
            updateSegmentPinButton();
            updateUndoButton();
            updateExportButton();
            updateCourseUI();
        }

        function cancelSameRouteBack() {
            stopSameRouteBackMode();
            updateDrawButtons();
        }

        function renderUturnIcons() {
            if (!window.courseMappingMap || !currentCourse) return;
            if (uturnIconsLayer) {
                window.courseMappingMap.removeLayer(uturnIconsLayer);
                uturnIconsLayer = null;
            }
            var indices = currentCourse.turnaround_indices;
            if (!Array.isArray(indices) || indices.length === 0) return;
            var coords = (currentCourse.geometry && currentCourse.geometry.coordinates) || [];
            if (coords.length < 2) return;
            uturnIconsLayer = L.layerGroup();
            indices.forEach(function (idx) {
                if (idx < 0 || idx >= coords.length) return;
                var c = coords[idx];
                var icon = L.divIcon({
                    className: 'uturn-icon',
                    html: '<div style="width:24px;height:24px;background:#3498db;color:#fff;border:2px solid #2980b9;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:bold;">↺</div>',
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });
                var m = L.marker([c[1], c[0]], { icon: icon });
                m.bindTooltip('U-turn (Same Route Back)', { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
                uturnIconsLayer.addLayer(m);
            });
            uturnIconsLayer.addTo(window.courseMappingMap);
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
                if (!currentCourse.segment_break_descriptions) currentCourse.segment_break_descriptions = {};
                if (!currentCourse.segment_break_ids) currentCourse.segment_break_ids = {};
                currentCourse.segment_break_ids[idx] = nextSegmentPinId();
                setDirty();
                openSegmentPinFormTile(idx, e.latlng, function () {
                    syncSegmentsFromBreaks();
                    renderSegmentPins();
                    renderSegmentsList();
                    updateCourseUI();
                });
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
                var lblDesc = document.createElement('label');
                lblDesc.textContent = 'Description (optional)';
                content.appendChild(lblDesc);
                var inputDesc = document.createElement('textarea');
                inputDesc.rows = 2;
                inputDesc.placeholder = 'Description';
                inputDesc.style.display = 'block';
                inputDesc.style.width = '100%';
                inputDesc.style.marginBottom = '8px';
                inputDesc.style.boxSizing = 'border-box';
                content.appendChild(inputDesc);
                var btnAdd = document.createElement('button');
                btnAdd.type = 'button';
                btnAdd.textContent = 'Add';
                btnAdd.style.marginRight = '6px';
                var btnCancel = document.createElement('button');
                btnCancel.type = 'button';
                btnCancel.textContent = 'Cancel';
                content.appendChild(btnAdd);
                content.appendChild(btnCancel);
                var pop = L.popup({ maxWidth: 300, className: 'location-popup' }).setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
                btnAdd.onclick = function () {
                    var locType = sel.value || 'course';
                    var locLabel = (input.value && input.value.trim()) ? input.value.trim() : '';
                    var locDesc = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
                    currentCourse.locations.push({
                        id: nextLocationId(),
                        loc_type: locType,
                        loc_label: locLabel,
                        loc_description: locDesc,
                        lat: e.latlng.lat,
                        lon: e.latlng.lng
                    });
                    setDirty();
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
                if (currentCourse.turnaround_indices) currentCourse.turnaround_indices = [];
                setDirty();
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

        var btnSameRouteBack = document.getElementById('btn-same-route-back');
        if (btnSameRouteBack) {
            btnSameRouteBack.addEventListener('click', function () {
                if (sameRouteBackMode) stopSameRouteBackMode(); else startSameRouteBackMode();
            });
        }
        var btnConfirmTurnaround = document.getElementById('btn-confirm-turnaround');
        if (btnConfirmTurnaround) btnConfirmTurnaround.addEventListener('click', confirmSameRouteBack);
        var btnCancelTurnaround = document.getElementById('btn-cancel-turnaround');
        if (btnCancelTurnaround) btnCancelTurnaround.addEventListener('click', cancelSameRouteBack);

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

        var snapBtn = document.getElementById('snap-to-road');
        if (snapBtn) {
            snapBtn.addEventListener('click', function () {
                snapBtn.classList.toggle('active');
            });
        }

        var btnExport = document.getElementById('btn-export');
        if (btnExport) {
            btnExport.addEventListener('click', function () {
                if (!currentCourseId || !currentCourse) return;
                var url = '/api/courses/' + encodeURIComponent(currentCourseId) + '/export?to_folder=1';
                fetch(url).then(function (r) { return r.json(); }).then(function (data) {
                    if (data.ok) alert('All map files exported to map folder.');
                    else alert('Export failed');
                }).catch(function () { alert('Export failed'); });
            });
        }

        setCourse(null, blankCourse());
        loadCourseList();

        updateCourseUI();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateAddLocationButton();
        updateSameRouteBackButtons();
        updateExportButton();
    } catch (e) {
        console.error('Course mapping map init failed:', e);
        if (loadingEl) loadingEl.textContent = 'Failed to load map';
    }
});
