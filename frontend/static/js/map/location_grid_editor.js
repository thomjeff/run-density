/**
 * Location grid editor (Issue #773) — compact operational table + expandable row detail.
 * Identity/geometry read-only; bulk edit excludes proxy timing (#775 / #751).
 */
(function () {
    'use strict';

    var deps = null;
    var snapshotJson = '';
    var workingLocations = [];
    var selectedRows = new Set();
    var expandedRows = new Set();
    var dirty = false;
    var rowMaps = {};

    var COLLAPSED_COLS = 10;

    var BULK_FIELDS = [
        { key: 'zone', label: 'Zone', type: 'text' },
        { key: 'buffer', label: 'Buffer (min)', type: 'int' },
        { key: 'interval', label: 'Interval (min)', type: 'int' },
        { key: 'onepage', label: 'Create one-pager', type: 'yn' },
        { key: 'equipment', label: 'Equipment', type: 'text' },
        { key: 'contact', label: 'Contact', type: 'text' },
        { key: 'notes', label: 'Notes', type: 'textarea' },
        { key: 'resources', label: 'Resource counts', type: 'resources' }
    ];

    function $(id) {
        return document.getElementById(id);
    }

    function deepCloneLocations(locs) {
        return JSON.parse(JSON.stringify(locs || []));
    }

    function locationId(loc, index) {
        if (deps && deps.locationNumericId) return deps.locationNumericId(loc) || index + 1;
        var raw = loc.id != null ? loc.id : index + 1;
        var n = parseInt(raw, 10);
        return isNaN(n) ? index + 1 : n;
    }

    function typeLabel(locType) {
        if (deps && deps.getLocationTypeLabel) return deps.getLocationTypeLabel(locType);
        return (locType || '').toString();
    }

    function offCourseType(t) {
        if (deps && deps.offCourseUsesProxyTiming) return deps.offCourseUsesProxyTiming(t);
        var x = (t || '').toLowerCase();
        return x === 'traffic' || x === 'extract';
    }

    function ynDisplay(v) {
        return String(v || 'n').toLowerCase() === 'y' ? 'y' : 'n';
    }

    function resourceCount(loc, code) {
        if (loc.resources && loc.resources[code] != null) {
            var n = parseInt(loc.resources[code], 10);
            return isNaN(n) ? 0 : Math.max(0, n);
        }
        var c = loc[code + '_count'];
        if (c == null || c === '') return 0;
        var n2 = parseInt(c, 10);
        return isNaN(n2) ? 0 : Math.max(0, n2);
    }

    function setResourceCount(loc, code, raw) {
        var n = parseInt(raw, 10);
        if (isNaN(n) || n < 0) n = 0;
        if (!loc.resources) loc.resources = {};
        loc.resources[code] = n;
        loc[code + '_count'] = n;
    }

    function formatResourcesSummary(loc) {
        var parts = [];
        (deps && deps.getResources ? deps.getResources() : []).forEach(function (res) {
            var code = res.code;
            var n = resourceCount(loc, code);
            if (n > 0) parts.push(String(code).toUpperCase() + '-' + n);
        });
        return parts.length ? parts.join('; ') : '—';
    }

    function proxyDisplay(loc) {
        var p = loc.proxy_loc_id;
        if (p == null || p === '' || String(p).trim() === '') return '—';
        return String(p);
    }

    function latLonDisplay(loc) {
        var lat = loc.lat;
        var lon = loc.lon;
        if (lat == null || lon == null || isNaN(parseFloat(lat)) || isNaN(parseFloat(lon))) {
            return '—';
        }
        return parseFloat(lat).toFixed(5) + ', ' + parseFloat(lon).toFixed(5);
    }

    function markDirty() {
        dirty = true;
        updateDirtyLabel();
    }

    function updateDirtyLabel() {
        var el = $('location-grid-dirty-label');
        if (!el) return;
        el.textContent = dirty ? 'Unsaved changes' : 'No unsaved changes';
        el.style.color = dirty ? '#c0392b' : '#7f8c8d';
    }

    function isDirtyState() {
        return dirty || snapshotJson !== JSON.stringify(workingLocations);
    }

    function validateAll() {
        var errors = [];
        workingLocations.forEach(function (loc, i) {
            var label = (loc.loc_label || '').trim() || 'Row ' + (i + 1);
            var seg = (loc.seg_id || '').trim();
            var proxy = loc.proxy_loc_id;
            var hasProxy = proxy != null && proxy !== '' && String(proxy).trim() !== '';
            if (hasProxy && seg) {
                errors.push(label + ': use proxy timing or Seg ID, not both (Issue #751)');
            }
            if (hasProxy && locationId(loc, i) === parseInt(proxy, 10)) {
                errors.push(label + ': proxy cannot reference itself');
            }
        });
        return errors;
    }

    function destroyAllRowMaps() {
        Object.keys(rowMaps).forEach(function (key) {
            try {
                if (rowMaps[key]) rowMaps[key].remove();
            } catch (e) { /* ignore teardown errors */ }
            delete rowMaps[key];
        });
    }

    function mountRowMap(rowIndex, loc) {
        var el = document.getElementById('location-grid-map-' + rowIndex);
        if (!el) return;
        var lat = parseFloat(loc.lat);
        var lon = parseFloat(loc.lon);
        if (isNaN(lat) || isNaN(lon)) {
            el.classList.add('location-grid-detail-map--empty');
            el.textContent = '—';
            return;
        }
        if (typeof L === 'undefined') {
            el.classList.add('location-grid-detail-map--empty');
            el.textContent = 'Map unavailable';
            return;
        }
        if (rowMaps[rowIndex]) {
            try {
                rowMaps[rowIndex].remove();
            } catch (e) { /* ignore */ }
            delete rowMaps[rowIndex];
        }
        el.classList.remove('location-grid-detail-map--empty');
        el.textContent = '';
        var map = L.map(el, {
            zoomControl: false,
            attributionControl: false,
            dragging: false,
            scrollWheelZoom: false,
            doubleClickZoom: false,
            boxZoom: false,
            keyboard: false,
            touchZoom: false
        });
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
            subdomains: ['a', 'b', 'c', 'd'],
            maxZoom: 19
        }).addTo(map);
        L.circleMarker([lat, lon], {
            radius: 5,
            color: '#2563eb',
            fillColor: '#2563eb',
            fillOpacity: 0.85,
            weight: 2
        }).addTo(map);
        map.setView([lat, lon], 16);
        rowMaps[rowIndex] = map;
        setTimeout(function () {
            if (rowMaps[rowIndex]) rowMaps[rowIndex].invalidateSize();
        }, 80);
    }

    function scheduleRowMaps() {
        expandedRows.forEach(function (rowIndex) {
            var loc = workingLocations[rowIndex];
            if (loc) mountRowMap(rowIndex, loc);
        });
    }

    function buildOnepagerControl(loc, editable) {
        var wrap = document.createElement('div');
        wrap.className = 'location-grid-onepager-wrap';
        var lbl = document.createElement('label');
        lbl.className = 'location-onepager-inline';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = ynDisplay(loc.onepage) === 'y';
        cb.disabled = !editable;
        var span = document.createElement('span');
        span.textContent = 'Create One-Pager';
        lbl.appendChild(cb);
        lbl.appendChild(span);
        cb.addEventListener('change', function () {
            loc.onepage = cb.checked ? 'y' : 'n';
            markDirty();
        });
        wrap.appendChild(lbl);
        return wrap;
    }

    function buildProxySelect(loc, rowIndex, editable) {
        var sel = document.createElement('select');
        sel.className = 'location-grid-detail-input';
        sel.disabled = !editable;
        var none = document.createElement('option');
        none.value = '';
        none.textContent = '— None —';
        sel.appendChild(none);
        var selfId = locationId(loc, rowIndex);
        workingLocations.forEach(function (other, j) {
            var oid = locationId(other, j);
            if (!oid || oid === selfId) return;
            var opt = document.createElement('option');
            opt.value = String(oid);
            opt.textContent =
                oid +
                ' — ' +
                (other.loc_label || 'Untitled') +
                (other.loc_type ? ' (' + other.loc_type + ')' : '');
            sel.appendChild(opt);
        });
        var pv =
            loc.proxy_loc_id != null && loc.proxy_loc_id !== ''
                ? String(loc.proxy_loc_id)
                : '';
        if (pv) {
            sel.value = pv;
            if (sel.value !== pv) {
                var miss = document.createElement('option');
                miss.value = pv;
                miss.textContent = pv + ' (missing)';
                sel.appendChild(miss);
                sel.value = pv;
            }
        }
        sel.addEventListener('change', function () {
            if (sel.value) {
                var pid = parseInt(sel.value, 10);
                loc.proxy_loc_id = isNaN(pid) ? sel.value : pid;
            } else {
                loc.proxy_loc_id = '';
            }
            if (sel.value && offCourseType(loc.loc_type)) {
                loc.seg_id = '';
            }
            markDirty();
            renderGridBody();
        });
        return sel;
    }

    function addDetailField(parent, labelText, controlOrText, isReadOnlyText) {
        var wrap = document.createElement('div');
        wrap.className = 'location-grid-detail-field';
        var lbl = document.createElement('label');
        lbl.textContent = labelText;
        wrap.appendChild(lbl);
        if (isReadOnlyText) {
            var span = document.createElement('span');
            span.className = 'location-grid-detail-readonly';
            span.textContent = controlOrText;
            wrap.appendChild(span);
        } else {
            wrap.appendChild(controlOrText);
        }
        parent.appendChild(wrap);
        return wrap;
    }

    function buildDetailPanel(loc, rowIndex, editable) {
        var panel = document.createElement('div');
        panel.className = 'location-grid-detail-panel';

        var banner = document.createElement('p');
        banner.className = 'location-grid-detail-note location-grid-detail-note--banner';
        banner.textContent =
            'Identity, geometry, and segment placement are edited in the Legs / map authoring UI. These fields are not editable here.';
        panel.appendChild(banner);

        var columns = document.createElement('div');
        columns.className = 'location-grid-detail-columns';

        var col1 = document.createElement('div');
        col1.className = 'location-grid-detail-col location-grid-detail-col--identity';
        var col1Fields = document.createElement('div');
        col1Fields.className = 'location-grid-detail-col-fields';
        addDetailField(col1Fields, 'Label', (loc.loc_label || '').trim() || '—', true);
        addDetailField(col1Fields, 'Type', typeLabel(loc.loc_type), true);
        addDetailField(col1Fields, 'Seg ID', (loc.seg_id || '').trim() || '—', true);
        addDetailField(col1Fields, 'Lat / Lon', latLonDisplay(loc), true);
        col1.appendChild(col1Fields);
        var mapWrap = document.createElement('div');
        mapWrap.className = 'location-grid-detail-map-wrap';
        var mapEl = document.createElement('div');
        mapEl.id = 'location-grid-map-' + rowIndex;
        mapEl.className = 'location-grid-detail-map';
        mapWrap.appendChild(mapEl);
        col1.appendChild(mapWrap);

        var col2 = document.createElement('div');
        col2.className = 'location-grid-detail-col';
        var note2 = document.createElement('p');
        note2.className = 'location-grid-detail-note';
        note2.textContent = 'Set per location. Not available in bulk edit.';
        col2.appendChild(note2);
        addDetailField(col2, 'Proxy timing', buildProxySelect(loc, rowIndex, editable), false);

        var zoneInp = document.createElement('input');
        zoneInp.type = 'text';
        zoneInp.className = 'location-grid-detail-input';
        zoneInp.value = loc.zone != null ? String(loc.zone) : '';
        zoneInp.disabled = !editable;
        zoneInp.addEventListener('change', function () {
            loc.zone = zoneInp.value;
            markDirty();
            renderGridBody();
        });
        addDetailField(col2, 'Zone', zoneInp, false);

        var bufInp = document.createElement('input');
        bufInp.type = 'number';
        bufInp.min = '0';
        bufInp.className = 'location-grid-detail-input';
        bufInp.value = loc.buffer != null ? String(loc.buffer) : '10';
        bufInp.disabled = !editable;
        bufInp.addEventListener('change', function () {
            var iv = parseInt(bufInp.value, 10);
            loc.buffer = isNaN(iv) ? 10 : iv;
            markDirty();
        });
        addDetailField(col2, 'Buffer (min)', bufInp, false);

        var intInp = document.createElement('input');
        intInp.type = 'number';
        intInp.min = '0';
        intInp.className = 'location-grid-detail-input';
        intInp.value = loc.interval != null ? String(loc.interval) : '5';
        intInp.disabled = !editable;
        intInp.addEventListener('change', function () {
            var iv = parseInt(intInp.value, 10);
            loc.interval = isNaN(iv) ? 5 : iv;
            markDirty();
        });
        addDetailField(col2, 'Interval (min)', intInp, false);

        var resWrap = document.createElement('div');
        resWrap.className = 'location-grid-resource-grid';
        (deps && deps.getResources ? deps.getResources() : []).forEach(function (res) {
            var code = res.code;
            var cell = document.createElement('div');
            cell.className = 'location-grid-resource-cell';
            var rl = document.createElement('label');
            rl.textContent = res.label || code;
            var rin = document.createElement('input');
            rin.type = 'number';
            rin.min = '0';
            rin.className = 'location-grid-detail-input';
            rin.value = String(resourceCount(loc, code));
            rin.disabled = !editable;
            rin.addEventListener('change', function () {
                setResourceCount(loc, code, rin.value);
                markDirty();
                renderGridBody();
            });
            cell.appendChild(rl);
            cell.appendChild(rin);
            resWrap.appendChild(cell);
        });
        addDetailField(col2, 'Resource counts', resWrap, false);

        var col3 = document.createElement('div');
        col3.className = 'location-grid-detail-col';
        col3.appendChild(buildOnepagerControl(loc, editable));

        var eqInp = document.createElement('input');
        eqInp.type = 'text';
        eqInp.className = 'location-grid-detail-input';
        eqInp.value = loc.equipment != null ? String(loc.equipment) : '';
        eqInp.disabled = !editable;
        eqInp.addEventListener('change', function () {
            loc.equipment = eqInp.value;
            markDirty();
        });
        addDetailField(col3, 'Equipment', eqInp, false);

        var ctInp = document.createElement('input');
        ctInp.type = 'text';
        ctInp.className = 'location-grid-detail-input';
        ctInp.value = loc.contact != null ? String(loc.contact) : '';
        ctInp.disabled = !editable;
        ctInp.addEventListener('change', function () {
            loc.contact = ctInp.value;
            markDirty();
        });
        addDetailField(col3, 'Contact', ctInp, false);

        var notesTa = document.createElement('textarea');
        notesTa.className = 'location-grid-detail-textarea';
        notesTa.rows = 4;
        notesTa.value = loc.notes != null ? String(loc.notes) : '';
        notesTa.disabled = !editable;
        notesTa.addEventListener('change', function () {
            loc.notes = notesTa.value;
            markDirty();
        });
        addDetailField(col3, 'Notes', notesTa, false);

        columns.appendChild(col1);
        columns.appendChild(col2);
        columns.appendChild(col3);
        panel.appendChild(columns);
        return panel;
    }

    function renderGridHead() {
        var head = $('location-grid-thead-row');
        if (!head) return;
        head.innerHTML = '';
        var headers = [
            { key: '_expand', label: '', width: 36 },
            { key: '_select', label: '', width: 40 },
            { key: 'id', label: 'ID', width: 48 },
            { key: 'location_key', label: 'Key', width: 56 },
            { key: 'loc_label', label: 'Label', width: 140 },
            { key: 'loc_type', label: 'Type', width: 88 },
            { key: 'zone', label: 'Zone', width: 72 },
            { key: 'seg_id', label: 'Seg ID', width: 64 },
            { key: 'proxy_loc_id', label: 'Proxy ID', width: 72 },
            { key: 'resources', label: 'Resources', width: 200 }
        ];
        headers.forEach(function (col) {
            var th = document.createElement('th');
            if (col.width) th.style.minWidth = col.width + 'px';
            if (col.key === '_select') {
                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.title = 'Select all';
                cb.checked =
                    workingLocations.length > 0 &&
                    selectedRows.size === workingLocations.length;
                cb.addEventListener('change', function () {
                    selectedRows.clear();
                    if (cb.checked) {
                        workingLocations.forEach(function (_, i) {
                            selectedRows.add(i);
                        });
                    }
                    updateSelectionToolbar();
                    renderGridBody();
                });
                th.appendChild(cb);
            } else {
                th.textContent = col.label;
            }
            head.appendChild(th);
        });
    }

    function renderGridBody() {
        var tbody = $('location-grid-tbody');
        if (!tbody) return;
        destroyAllRowMaps();
        tbody.innerHTML = '';
        var editable = deps && deps.canEdit && deps.canEdit();

        workingLocations.forEach(function (loc, rowIndex) {
            var tr = document.createElement('tr');
            tr.className = 'location-grid-summary-row';
            if (selectedRows.has(rowIndex)) tr.classList.add('location-grid-row-selected');

            var expandTd = document.createElement('td');
            expandTd.className = 'location-grid-expand-cell';
            var expandBtn = document.createElement('button');
            expandBtn.type = 'button';
            expandBtn.className = 'location-grid-expand-btn';
            expandBtn.setAttribute('aria-expanded', expandedRows.has(rowIndex) ? 'true' : 'false');
            expandBtn.title = expandedRows.has(rowIndex) ? 'Collapse' : 'Expand details';
            expandBtn.textContent = expandedRows.has(rowIndex) ? '▼' : '▶';
            expandBtn.addEventListener('click', function () {
                if (expandedRows.has(rowIndex)) expandedRows.delete(rowIndex);
                else expandedRows.add(rowIndex);
                renderGridBody();
            });
            expandTd.appendChild(expandBtn);
            tr.appendChild(expandTd);

            var selTd = document.createElement('td');
            selTd.className = 'grid-col-select';
            var rowCb = document.createElement('input');
            rowCb.type = 'checkbox';
            rowCb.checked = selectedRows.has(rowIndex);
            rowCb.addEventListener('change', function () {
                if (rowCb.checked) selectedRows.add(rowIndex);
                else selectedRows.delete(rowIndex);
                updateSelectionToolbar();
                renderGridBody();
            });
            selTd.appendChild(rowCb);
            tr.appendChild(selTd);

            var idTd = document.createElement('td');
            idTd.className = 'location-grid-readonly';
            idTd.textContent = String(locationId(loc, rowIndex));
            tr.appendChild(idTd);

            var keyTd = document.createElement('td');
            keyTd.className = 'location-grid-readonly';
            keyTd.textContent = (loc.location_key && String(loc.location_key).trim())
                ? String(loc.location_key).trim()
                : '—';
            tr.appendChild(keyTd);

            var labelTd = document.createElement('td');
            labelTd.className = 'location-grid-readonly';
            labelTd.textContent = (loc.loc_label || '').trim() || '—';
            tr.appendChild(labelTd);

            var typeTd = document.createElement('td');
            typeTd.className = 'location-grid-readonly';
            typeTd.textContent = typeLabel(loc.loc_type);
            tr.appendChild(typeTd);

            var zoneTd = document.createElement('td');
            zoneTd.className = 'location-grid-readonly';
            var zoneVal = loc.zone != null ? String(loc.zone).trim() : '';
            zoneTd.textContent = zoneVal !== '' ? zoneVal : '—';
            tr.appendChild(zoneTd);

            var segTd = document.createElement('td');
            segTd.className = 'location-grid-readonly';
            segTd.textContent = (loc.seg_id || '').trim() || '—';
            tr.appendChild(segTd);

            var proxyTd = document.createElement('td');
            proxyTd.className = 'location-grid-readonly';
            proxyTd.textContent = proxyDisplay(loc);
            tr.appendChild(proxyTd);

            var resTd = document.createElement('td');
            resTd.className = 'location-grid-resources-summary';
            resTd.textContent = formatResourcesSummary(loc);
            resTd.title = resTd.textContent;
            tr.appendChild(resTd);

            tbody.appendChild(tr);

            if (expandedRows.has(rowIndex)) {
                var detailTr = document.createElement('tr');
                detailTr.className = 'location-grid-detail-row';
                if (selectedRows.has(rowIndex)) detailTr.classList.add('location-grid-row-selected');
                var detailTd = document.createElement('td');
                detailTd.colSpan = COLLAPSED_COLS;
                detailTd.appendChild(buildDetailPanel(loc, rowIndex, editable));
                detailTr.appendChild(detailTd);
                tbody.appendChild(detailTr);
            }
        });
        scheduleRowMaps();
    }

    function renderGrid() {
        renderGridHead();
        renderGridBody();
        var title = $('location-grid-title');
        if (title) {
            title.textContent =
                'Location operations · ' + workingLocations.length + ' locations';
        }
    }

    function updateSelectionToolbar() {
        var n = selectedRows.size;
        var countEl = $('location-grid-selection-count');
        var bulkBtn = $('location-grid-bulk-edit');
        if (countEl) countEl.textContent = n ? n + ' selected' : '';
        if (bulkBtn) bulkBtn.disabled = n < 1;
    }

    function showModal(modal) {
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
    }

    function hideModal(modal) {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
    }

    function applyWorkingToCourse() {
        if (!deps || !deps.applyLocations) return;
        deps.applyLocations(workingLocations);
    }

    function saveGrid(stayOpen) {
        var errors = validateAll();
        if (errors.length) {
            alert('Fix before save:\n\n' + errors.slice(0, 12).join('\n'));
            return Promise.reject(new Error('validation'));
        }
        applyWorkingToCourse();
        if (!deps || !deps.persist) return Promise.resolve();
        return deps.persist().then(function () {
            snapshotJson = JSON.stringify(workingLocations);
            dirty = false;
            updateDirtyLabel();
            if (deps.onSaved) deps.onSaved();
            if (!stayOpen) closeGrid(true);
        });
    }

    function closeGrid(force) {
        if (!force && isDirtyState()) {
            var countEl = $('location-grid-unsaved-count');
            if (countEl) countEl.textContent = String(workingLocations.length);
            showModal($('location-grid-unsaved-modal'));
            return;
        }
        hideModal($('location-grid-modal'));
        destroyAllRowMaps();
        workingLocations = [];
        selectedRows.clear();
        expandedRows.clear();
        dirty = false;
    }

    function openBulkModal() {
        if (selectedRows.size < 1) return;
        var body = $('location-grid-bulk-body');
        if (!body) return;
        body.innerHTML = '';
        var lead = document.createElement('p');
        lead.className = 'course-modal-lead';
        lead.textContent =
            'Apply shared operational values to ' +
            selectedRows.size +
            ' selected location(s). Proxy timing is not bulk-editable.';
        body.appendChild(lead);

        var fieldState = [];
        BULK_FIELDS.forEach(function (field) {
            var wrap = document.createElement('div');
            wrap.className = 'location-grid-bulk-field';
            var check = document.createElement('label');
            check.className = 'location-grid-bulk-check';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            check.appendChild(cb);
            check.appendChild(document.createTextNode(' Update ' + field.label));
            wrap.appendChild(check);

            var control = null;
            var fs = { field: field, cb: cb, control: null, resInputs: null };
            if (field.type === 'resources') {
                var grid = document.createElement('div');
                grid.className = 'location-grid-resource-grid';
                var resInputs = {};
                (deps.getResources() || []).forEach(function (res) {
                    var cell = document.createElement('div');
                    cell.className = 'location-grid-resource-cell';
                    var lbl = document.createElement('label');
                    lbl.textContent = res.label || res.code;
                    var inp = document.createElement('input');
                    inp.type = 'number';
                    inp.min = '0';
                    inp.value = '0';
                    inp.disabled = true;
                    resInputs[res.code] = inp;
                    cell.appendChild(lbl);
                    cell.appendChild(inp);
                    grid.appendChild(cell);
                });
                control = grid;
                fs.resInputs = resInputs;
                fs.control = control;
            } else if (field.type === 'yn') {
                control = document.createElement('select');
                control.disabled = true;
                ['n', 'y'].forEach(function (v) {
                    var o = document.createElement('option');
                    o.value = v;
                    o.textContent = v === 'y' ? 'Yes' : 'No';
                    control.appendChild(o);
                });
                fs.control = control;
            } else if (field.type === 'textarea') {
                control = document.createElement('textarea');
                control.rows = 3;
                control.disabled = true;
                fs.control = control;
            } else {
                control = document.createElement('input');
                control.type = field.type === 'int' ? 'number' : 'text';
                control.disabled = true;
                if (field.type === 'int') control.min = '0';
                fs.control = control;
            }
            cb.addEventListener('change', function () {
                if (fs.control) fs.control.disabled = !cb.checked;
                if (fs.resInputs) {
                    Object.keys(fs.resInputs).forEach(function (code) {
                        fs.resInputs[code].disabled = !cb.checked;
                    });
                }
            });
            wrap.appendChild(control);
            body.appendChild(wrap);
            fieldState.push(fs);
        });

        var impact = document.createElement('div');
        impact.id = 'location-grid-bulk-impact';
        impact.className = 'location-grid-bulk-impact';
        body.appendChild(impact);

        function updateImpact() {
            var lines = ['Applying to ' + selectedRows.size + ' locations.'];
            fieldState.forEach(function (fs) {
                if (!fs.cb.checked) return;
                var key = fs.field.key;
                if (key === 'resources') return;
                var withVal = 0;
                selectedRows.forEach(function (ri) {
                    var loc = workingLocations[ri];
                    var v = loc[key];
                    if (v != null && String(v).trim() !== '') withVal += 1;
                });
                lines.push(
                    fs.field.label +
                        ': ' +
                        withVal +
                        ' of ' +
                        selectedRows.size +
                        ' already have a value (will overwrite).'
                );
            });
            impact.textContent = lines.join('\n');
        }
        fieldState.forEach(function (fs) {
            fs.cb.addEventListener('change', updateImpact);
        });
        updateImpact();

        $('location-grid-bulk-apply').onclick = function () {
            var patch = {};
            var fields = [];
            fieldState.forEach(function (fs) {
                if (!fs.cb.checked) return;
                fields.push(fs.field.key);
                if (fs.field.key === 'resources' && fs.resInputs) {
                    patch.resources = {};
                    Object.keys(fs.resInputs).forEach(function (code) {
                        var n = parseInt(fs.resInputs[code].value, 10);
                        patch.resources[code] = isNaN(n) ? 0 : Math.max(0, n);
                    });
                } else if (fs.field.type === 'int') {
                    patch[fs.field.key] = parseInt(fs.control.value, 10) || 0;
                } else if (fs.field.type === 'yn') {
                    patch[fs.field.key] = fs.control.value === 'y' ? 'y' : 'n';
                } else {
                    patch[fs.field.key] = fs.control.value;
                }
            });
            if (!fields.length) {
                alert('Select at least one field to update.');
                return;
            }
            applyBulkLocationPatch(workingLocations, selectedRows, patch, fields);
            markDirty();
            renderGrid();
            hideModal($('location-grid-bulk-modal'));
        };
        showModal($('location-grid-bulk-modal'));
    }

    function applyBulkLocationPatch(locations, indices, patch, fields) {
        var rowIndices = indices instanceof Set ? Array.from(indices) : indices;
        rowIndices.forEach(function (i) {
            var loc = locations[i];
            if (!loc) return;
            fields.forEach(function (f) {
                if (f === 'resources' && patch.resources) {
                    Object.keys(patch.resources).forEach(function (code) {
                        setResourceCount(loc, code, patch.resources[code]);
                    });
                } else if (patch[f] !== undefined) {
                    loc[f] = patch[f];
                }
            });
        });
    }

    function open() {
        if (!deps || !deps.canEdit || !deps.canEdit()) {
            alert('Load a config package course with locations to use the location operations editor.');
            return;
        }
        var locs = deps.getLocations ? deps.getLocations() : [];
        if (!locs.length) {
            alert('No locations to edit. Save event recipes first.');
            return;
        }
        workingLocations = deepCloneLocations(locs);
        snapshotJson = JSON.stringify(workingLocations);
        selectedRows.clear();
        expandedRows.clear();
        dirty = false;
        updateDirtyLabel();
        updateSelectionToolbar();
        renderGrid();
        showModal($('location-grid-modal'));
    }

    function bindUi() {
        var openBtn = $('btn-edit-locations-grid');
        if (openBtn) openBtn.addEventListener('click', open);

        var closeBtn = $('location-grid-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                closeGrid(false);
            });
        }
        var saveBtn = $('location-grid-save');
        if (saveBtn) saveBtn.addEventListener('click', function () { saveGrid(true); });
        var saveCloseBtn = $('location-grid-save-close');
        if (saveCloseBtn) {
            saveCloseBtn.addEventListener('click', function () { saveGrid(false); });
        }
        var discardBtn = $('location-grid-discard');
        if (discardBtn) {
            discardBtn.addEventListener('click', function () {
                workingLocations = deepCloneLocations(JSON.parse(snapshotJson));
                dirty = false;
                updateDirtyLabel();
                renderGrid();
            });
        }
        var bulkBtn = $('location-grid-bulk-edit');
        if (bulkBtn) bulkBtn.addEventListener('click', openBulkModal);
        var clearSel = $('location-grid-clear-selection');
        if (clearSel) {
            clearSel.addEventListener('click', function () {
                selectedRows.clear();
                updateSelectionToolbar();
                renderGridBody();
            });
        }
        function closeBulkModal() {
            hideModal($('location-grid-bulk-modal'));
        }
        var bulkCancel = $('location-grid-bulk-cancel');
        if (bulkCancel) bulkCancel.addEventListener('click', closeBulkModal);
        var bulkCancelFooter = $('location-grid-bulk-cancel-footer');
        if (bulkCancelFooter) bulkCancelFooter.addEventListener('click', closeBulkModal);
        var unsavedCancel = $('location-grid-unsaved-cancel');
        if (unsavedCancel) {
            unsavedCancel.addEventListener('click', function () {
                hideModal($('location-grid-unsaved-modal'));
            });
        }
        var unsavedDiscard = $('location-grid-unsaved-discard');
        if (unsavedDiscard) {
            unsavedDiscard.addEventListener('click', function () {
                hideModal($('location-grid-unsaved-modal'));
                closeGrid(true);
            });
        }
        var unsavedSave = $('location-grid-unsaved-save-close');
        if (unsavedSave) {
            unsavedSave.addEventListener('click', function () {
                hideModal($('location-grid-unsaved-modal'));
                saveGrid(false);
            });
        }
        var gridModal = $('location-grid-modal');
        if (gridModal) {
            var backdrop = gridModal.querySelector('.course-location-modal-backdrop');
            if (backdrop) {
                backdrop.addEventListener('click', function () {
                    closeGrid(false);
                });
            }
        }
    }

    function init(dependencies) {
        deps = dependencies;
        bindUi();
    }

    function updateOpenButtonVisibility(visible) {
        var btn = $('btn-edit-locations-grid');
        if (btn) btn.style.display = visible ? '' : 'none';
    }

    window.locationGridEditor = {
        init: init,
        open: open,
        updateOpenButtonVisibility: updateOpenButtonVisibility,
        applyBulkLocationPatch: applyBulkLocationPatch
    };
})();
