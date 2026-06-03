/**
 * Location grid editor (Issue #773) — spreadsheet power mode + in-grid bulk edit (#772).
 * Requires init from course_mapping.js with package course callbacks.
 */
(function () {
    'use strict';

    var deps = null;
    var snapshotJson = '';
    var workingLocations = [];
    var selectedRows = new Set();
    var showSystemColumns = false;
    var dirty = false;

    var BULK_FIELDS = [
        { key: 'zone', label: 'Zone', type: 'text' },
        { key: 'buffer', label: 'Buffer (min)', type: 'int' },
        { key: 'interval', label: 'Interval (min)', type: 'int' },
        { key: 'onepage', label: 'Create one-pager', type: 'yn' },
        { key: 'equipment', label: 'Equipment', type: 'text' },
        { key: 'contact', label: 'Contact', type: 'text' },
        { key: 'notes', label: 'Notes', type: 'textarea' },
        { key: 'resources', label: 'Resources scheduled', type: 'resources' }
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

    function offCourseType(t) {
        if (deps && deps.offCourseUsesProxyTiming) return deps.offCourseUsesProxyTiming(t);
        var x = (t || '').toLowerCase();
        return x === 'traffic' || x === 'extract';
    }

    function ynDisplay(v) {
        return String(v || 'n').toLowerCase() === 'y' ? 'y' : 'n';
    }

    function getCellValue(loc, col, rowIndex) {
        var key = col.key;
        if (key === 'id') return String(locationId(loc, rowIndex));
        if (key === 'proxy_loc_id') {
            var p = loc.proxy_loc_id;
            return p != null && p !== '' ? String(p) : '';
        }
        if (col.resourceCode) {
            var code = col.resourceCode;
            if (loc.resources && loc.resources[code] != null) return String(loc.resources[code]);
            return String(loc[code + '_count'] != null ? loc[code + '_count'] : 0);
        }
        if (key === 'onepage') return ynDisplay(loc.onepage);
        var v = loc[key];
        return v != null ? String(v) : '';
    }

    function setCellValue(loc, col, raw, rowIndex) {
        var key = col.key;
        if (col.readOnly) return;
        if (key === 'proxy_loc_id') {
            loc.proxy_loc_id = raw ? parseInt(raw, 10) : '';
            if (raw && isNaN(loc.proxy_loc_id)) loc.proxy_loc_id = raw;
            return;
        }
        if (col.resourceCode) {
            var n = parseInt(raw, 10);
            if (isNaN(n) || n < 0) n = 0;
            if (!loc.resources) loc.resources = {};
            loc.resources[col.resourceCode] = n;
            loc[col.resourceCode + '_count'] = n;
            return;
        }
        if (key === 'buffer' || key === 'interval') {
            var iv = parseInt(raw, 10);
            loc[key] = isNaN(iv) ? (key === 'buffer' ? 10 : 5) : iv;
            return;
        }
        if (key === 'onepage') {
            loc.onepage = raw === 'y' ? 'y' : 'n';
            return;
        }
        if (key === 'lat' || key === 'lon') {
            var f = parseFloat(raw);
            if (!isNaN(f)) loc[key] = f;
            return;
        }
        loc[key] = raw;
    }

    function buildColumns() {
        var cols = [
            { key: '_select', label: '', bulk: true, width: 40 },
            { key: 'id', label: 'ID', readOnly: true, width: 48 },
            { key: 'loc_label', label: 'Label', type: 'text', width: 140 },
            { key: 'loc_type', label: 'Type', type: 'select', width: 90 },
            { key: 'lat', label: 'Lat', type: 'number', width: 88 },
            { key: 'lon', label: 'Lon', type: 'number', width: 88 },
            { key: 'proxy_loc_id', label: 'Proxy timing', type: 'proxy', width: 160 },
            { key: 'seg_id', label: 'Seg ID', type: 'text', width: 72 },
            { key: 'zone', label: 'Zone', type: 'text', width: 56 },
            { key: 'buffer', label: 'Buffer', type: 'number', width: 64 },
            { key: 'interval', label: 'Interval', type: 'number', width: 72 }
        ];
        var events = (deps && deps.eventChoices) || [];
        events.forEach(function (ev) {
            cols.push({
                key: ev.value || ev,
                label: (ev.label || ev.value || '').toString(),
                readOnly: true,
                width: 44
            });
        });
        var resources = (deps && deps.getResources) ? deps.getResources() : [];
        resources.forEach(function (res) {
            cols.push({
                key: res.code + '_count',
                label: res.code,
                type: 'number',
                resourceCode: res.code,
                width: 52
            });
        });
        cols.push(
            { key: 'onepage', label: '1-pg', type: 'yn', width: 48 },
            { key: 'equipment', label: 'Equipment', type: 'text', width: 100 },
            { key: 'contact', label: 'Contact', type: 'text', width: 100 },
            { key: 'notes', label: 'Notes', type: 'text', width: 160 }
        );
        if (showSystemColumns) {
            cols.push(
                { key: 'source', label: 'Source', readOnly: true, width: 56 },
                { key: 'leg_id', label: 'Leg', readOnly: true, width: 48 },
                { key: 'placement', label: 'Placement', readOnly: true, width: 72 }
            );
        }
        var pkgDay = deps && deps.getPackageEventDay ? deps.getPackageEventDay() : '';
        cols.splice(8, 0, {
            key: 'day',
            label: 'Day',
            type: pkgDay ? 'readonly' : 'text',
            readOnly: !!pkgDay,
            width: 56
        });
        return cols;
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
            var lat = parseFloat(loc.lat);
            var lon = parseFloat(loc.lon);
            if (isNaN(lat) || isNaN(lon)) {
                errors.push(label + ': invalid latitude/longitude');
            }
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

    function buildProxySelect(loc, rowIndex, editable) {
        var sel = document.createElement('select');
        sel.className = 'location-grid-cell-input';
        sel.disabled = !editable;
        var none = document.createElement('option');
        none.value = '';
        none.textContent = '—';
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
            setCellValue(loc, { key: 'proxy_loc_id' }, sel.value, rowIndex);
            if (sel.value && offCourseType(loc.loc_type)) {
                loc.seg_id = '';
            }
            markDirty();
            renderGridBody();
        });
        return sel;
    }

    function createCellInput(loc, col, rowIndex, editable) {
        if (col.readOnly || col.type === 'readonly') {
            var span = document.createElement('span');
            span.className = 'location-grid-readonly';
            span.textContent = getCellValue(loc, col, rowIndex);
            return span;
        }
        if (col.type === 'proxy') {
            return buildProxySelect(loc, rowIndex, editable);
        }
        if (col.type === 'select' && col.key === 'loc_type') {
            var sel = document.createElement('select');
            sel.className = 'location-grid-cell-input';
            sel.disabled = !editable;
            (deps.locationTypes || []).forEach(function (t) {
                var opt = document.createElement('option');
                opt.value = t.value;
                opt.textContent = t.label || t.value;
                if ((loc.loc_type || 'course') === t.value) opt.selected = true;
                sel.appendChild(opt);
            });
            sel.addEventListener('change', function () {
                setCellValue(loc, col, sel.value, rowIndex);
                markDirty();
            });
            return sel;
        }
        if (col.type === 'yn') {
            var ysel = document.createElement('select');
            ysel.className = 'location-grid-cell-input';
            ysel.disabled = !editable;
            ['n', 'y'].forEach(function (v) {
                var o = document.createElement('option');
                o.value = v;
                o.textContent = v;
                if (ynDisplay(loc.onepage) === v) o.selected = true;
                ysel.appendChild(o);
            });
            ysel.addEventListener('change', function () {
                setCellValue(loc, col, ysel.value, rowIndex);
                markDirty();
            });
            return ysel;
        }
        var inp = document.createElement('input');
        inp.className = 'location-grid-cell-input';
        inp.type = col.type === 'number' ? 'number' : 'text';
        inp.disabled = !editable;
        inp.value = getCellValue(loc, col, rowIndex);
        inp.addEventListener('change', function () {
            setCellValue(loc, col, inp.value, rowIndex);
            markDirty();
        });
        inp.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                inp.blur();
                focusNextCell(rowIndex, col.key, 1);
            }
        });
        return inp;
    }

    function focusNextCell(rowIndex, colKey, dir) {
        var cols = buildColumns().filter(function (c) {
            return c.key !== '_select' && !c.readOnly;
        });
        var idx = cols.findIndex(function (c) {
            return c.key === colKey;
        });
        if (idx < 0) return;
        idx += dir;
        if (idx >= cols.length) {
            rowIndex += 1;
            idx = 0;
        }
        if (rowIndex >= workingLocations.length) return;
        var tbody = $('location-grid-tbody');
        if (!tbody) return;
        var tr = tbody.children[rowIndex];
        if (!tr) return;
        var colIdx = buildColumns().findIndex(function (c) {
            return c.key === cols[idx].key;
        });
        if (colIdx < 0) return;
        var cell = tr.children[colIdx];
        if (!cell) return;
        var focusable = cell.querySelector('input, select, textarea');
        if (focusable) focusable.focus();
    }

    function renderGridHead() {
        var head = $('location-grid-thead-row');
        if (!head) return;
        head.innerHTML = '';
        var cols = buildColumns();
        cols.forEach(function (col) {
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
        tbody.innerHTML = '';
        var cols = buildColumns();
        var editable = deps && deps.canEdit && deps.canEdit();
        workingLocations.forEach(function (loc, rowIndex) {
            var tr = document.createElement('tr');
            if (selectedRows.has(rowIndex)) tr.className = 'location-grid-row-selected';
            cols.forEach(function (col) {
                var td = document.createElement('td');
                if (col.key === '_select') {
                    var rowCb = document.createElement('input');
                    rowCb.type = 'checkbox';
                    rowCb.checked = selectedRows.has(rowIndex);
                    rowCb.addEventListener('change', function () {
                        if (rowCb.checked) selectedRows.add(rowIndex);
                        else selectedRows.delete(rowIndex);
                        updateSelectionToolbar();
                        renderGridBody();
                    });
                    td.appendChild(rowCb);
                } else {
                    td.appendChild(createCellInput(loc, col, rowIndex, editable));
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function renderGrid() {
        renderGridHead();
        renderGridBody();
        var title = $('location-grid-title');
        if (title) {
            title.textContent =
                'Location grid · ' + workingLocations.length + ' locations';
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
            showModal($('location-grid-unsaved-modal'));
            return;
        }
        hideModal($('location-grid-modal'));
        workingLocations = [];
        selectedRows.clear();
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
            'Apply shared values to ' +
            selectedRows.size +
            ' selected location(s). Check each field to update.';
        body.appendChild(lead);

        var fieldState = [];
        BULK_FIELDS.forEach(function (field) {
            var wrap = document.createElement('div');
            wrap.className = 'location-grid-bulk-field';
            var check = document.createElement('label');
            check.className = 'location-grid-bulk-check';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.dataset.field = field.key;
            check.appendChild(cb);
            check.appendChild(document.createTextNode(' Update ' + field.label));
            wrap.appendChild(check);

            var control = null;
            if (field.type === 'resources') {
                var grid = document.createElement('div');
                grid.className = 'location-resource-grid';
                var resInputs = {};
                (deps.getResources() || []).forEach(function (res) {
                    var lbl = document.createElement('span');
                    lbl.textContent = res.label || res.code;
                    var inp = document.createElement('input');
                    inp.type = 'number';
                    inp.min = '0';
                    inp.value = '0';
                    inp.disabled = true;
                    resInputs[res.code] = inp;
                    grid.appendChild(lbl);
                    grid.appendChild(inp);
                });
                control = grid;
                fieldState.push({ field: field, cb: cb, resInputs: resInputs });
            } else if (field.type === 'yn') {
                control = document.createElement('select');
                control.disabled = true;
                ['n', 'y'].forEach(function (v) {
                    var o = document.createElement('option');
                    o.value = v;
                    o.textContent = v;
                    control.appendChild(o);
                });
                fieldState.push({ field: field, cb: cb, control: control });
            } else if (field.type === 'textarea') {
                control = document.createElement('textarea');
                control.rows = 2;
                control.disabled = true;
                fieldState.push({ field: field, cb: cb, control: control });
            } else {
                control = document.createElement('input');
                control.type = field.type === 'int' ? 'number' : 'text';
                control.disabled = true;
                if (field.type === 'int') control.min = '0';
                fieldState.push({ field: field, cb: cb, control: control });
            }
            cb.addEventListener('change', function () {
                control.disabled = !cb.checked;
                if (fs.resInputs) {
                    Object.keys(fs.resInputs).forEach(function (code) {
                        fs.resInputs[code].disabled = !cb.checked;
                    });
                }
            });
            wrap.appendChild(control);
            body.appendChild(wrap);
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
                var withVal = 0;
                selectedRows.forEach(function (ri) {
                    var loc = workingLocations[ri];
                    if (key === 'resources') return;
                    var v = loc[key];
                    if (v != null && String(v).trim() !== '') withVal += 1;
                });
                if (key !== 'resources') {
                    lines.push(
                        fs.field.label +
                            ': ' +
                            withVal +
                            ' of ' +
                            selectedRows.size +
                            ' already have a value (will overwrite).'
                    );
                }
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
                if (fs.field.key === 'resources') {
                    patch.resources = {};
                    Object.keys(fs.resInputs).forEach(function (code) {
                        var n = parseInt(fs.resInputs[code].value, 10);
                        patch.resources[code] = isNaN(n) ? 0 : Math.max(0, n);
                    });
                } else if (fs.field.type === 'int') {
                    patch[fs.field.key] = parseInt(fs.control.value, 10) || 0;
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
                    if (!loc.resources) loc.resources = {};
                    Object.keys(patch.resources).forEach(function (code) {
                        loc.resources[code] = patch.resources[code];
                        loc[code + '_count'] = patch.resources[code];
                    });
                } else if (patch[f] !== undefined) {
                    loc[f] = patch[f];
                }
            });
        });
    }

    function open() {
        if (!deps || !deps.canEdit || !deps.canEdit()) {
            alert('Load a config package course with locations to use the grid editor.');
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
        var sysToggle = $('location-grid-show-system');
        if (sysToggle) {
            sysToggle.addEventListener('change', function () {
                showSystemColumns = sysToggle.checked;
                renderGrid();
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
