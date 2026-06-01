/**
 * Course legs + event recipes (config packages). Issue #769
 */
(function () {
    'use strict';

    var EVENTS = ['full', 'half', '10k'];
    var libraryState = null;
    var orderGrid = {};
    var legEditorMode = null;
    var legEditorLegId = null;
    var pendingGpxFile = null;

    function resolveConfigPackageId() {
        var params = new URLSearchParams(window.location.search);
        var raw = params.get('config_id');
        return raw ? raw.trim() : '';
    }

    function isConfigPackageWorkspace() {
        return !!resolveConfigPackageId() && !!document.getElementById('race-config-workspace');
    }

    function apiBase() {
        return '/api/config/packages/' + encodeURIComponent(resolveConfigPackageId());
    }

    function locationTypes() {
        return window.LOCATION_TYPES_FROM_SERVER || ['aid', 'course', 'traffic', 'water', 'official'];
    }

    function showConfigSections(visible) {
        var legs = document.getElementById('course-legs-card');
        var recipes = document.getElementById('segment-recipes-card');
        var on = visible && isConfigPackageWorkspace();
        if (legs) legs.style.display = on ? 'block' : 'none';
        if (recipes) recipes.style.display = on ? 'block' : 'none';
    }

    function formatApiError(res, data) {
        if (data && data.detail) {
            if (typeof data.detail === 'string') return data.detail;
            if (Array.isArray(data.detail)) {
                return data.detail.map(function (d) { return d.msg || JSON.stringify(d); }).join('; ');
            }
        }
        if (res && res.status === 404 && data && data.detail === 'Not Found') {
            return 'Segment library API is unavailable. Restart the app (make stop && make dev).';
        }
        return (res && res.status ? 'HTTP ' + res.status + ': ' : '') + 'Request failed';
    }

    function setLegStatus(msg, isError) {
        var el = document.getElementById('course-legs-status');
        if (!el) return;
        if (!msg) { el.style.display = 'none'; el.textContent = ''; return; }
        el.style.display = 'block';
        el.style.color = isError ? '#c0392b' : '#27ae60';
        el.textContent = msg;
    }

    function setRecipeStatus(msg, isError) {
        var el = document.getElementById('segment-recipes-status');
        if (!el) return;
        if (!msg) { el.style.display = 'none'; el.textContent = ''; return; }
        el.style.display = 'block';
        el.style.color = isError ? '#c0392b' : '#27ae60';
        el.textContent = msg;
    }

    function renderTotals(lengths) {
        var wrap = document.getElementById('segment-recipes-totals');
        if (!wrap || !lengths) return;
        wrap.style.display = 'block';
        var full = document.getElementById('recipe-total-full');
        var half = document.getElementById('recipe-total-half');
        var ten = document.getElementById('recipe-total-10k');
        if (full) full.textContent = ' Full ' + (lengths.full != null ? lengths.full.toFixed(2) : '—') + ' km';
        if (half) half.textContent = ' · Half ' + (lengths.half != null ? lengths.half.toFixed(2) : '—') + ' km';
        if (ten) ten.textContent = ' · 10K ' + (lengths['10k'] != null ? lengths['10k'].toFixed(2) : '—') + ' km';
    }

    function renderWarnings(warnings) {
        var el = document.getElementById('segment-recipes-warnings');
        if (!el) return;
        if (!warnings || !warnings.length) { el.style.display = 'none'; el.textContent = ''; return; }
        el.style.display = 'block';
        el.textContent = 'Stitch warnings: ' + warnings.join(' · ');
    }

    function getOrder(chunkId, eventId) {
        var row = orderGrid[eventId] || {};
        var v = row[chunkId];
        return v == null || v === '' ? '' : String(v);
    }

    function setOrder(chunkId, eventId, value) {
        if (!orderGrid[eventId]) orderGrid[eventId] = {};
        var trimmed = String(value || '').trim();
        if (!trimmed) orderGrid[eventId][chunkId] = null;
        else {
            var n = parseInt(trimmed, 10);
            orderGrid[eventId][chunkId] = isNaN(n) || n < 1 ? null : n;
        }
        if (libraryState && libraryState.recipe_lengths_km) recomputeTotalsLocal();
    }

    function recomputeTotalsLocal() {
        if (!libraryState || !libraryState.chunks) return;
        var lengths = { full: 0, half: 0, '10k': 0 };
        EVENTS.forEach(function (ev) {
            var pairs = [];
            libraryState.chunks.forEach(function (ch) {
                var o = getOrder(ch.id, ev);
                if (o) pairs.push({ order: parseInt(o, 10), km: ch.length_km || 0 });
            });
            pairs.sort(function (a, b) { return a.order - b.order; });
            lengths[ev] = Math.round(pairs.reduce(function (s, p) { return s + p.km; }, 0) * 100) / 100;
        });
        renderTotals(lengths);
    }

    function applyLibraryState(data) {
        libraryState = data;
        orderGrid = data.order_grid || {};
        renderLegsTable();
        renderRecipeTable();
        renderTotals(data.recipe_lengths_km);
        renderWarnings(data.stitch_warnings);
    }

    function renderLegsTable() {
        var tbody = document.getElementById('course-legs-tbody');
        var wrap = document.getElementById('course-legs-table-wrap');
        var empty = document.getElementById('course-legs-empty');
        if (!tbody) return;
        var chunks = (libraryState && libraryState.chunks) || [];
        if (!chunks.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        tbody.innerHTML = '';
        chunks.forEach(function (ch) {
            var tr = document.createElement('tr');
            [ch.id, (ch.leg_label || '').slice(0, 40), (ch.start_label || '').slice(0, 28),
                (ch.end_label || '').slice(0, 28),
                ch.length_km != null ? Number(ch.length_km).toFixed(2) : '—',
                String(ch.location_count != null ? ch.location_count : (ch.locations || []).length)
            ].forEach(function (text) {
                var td = document.createElement('td');
                td.textContent = text;
                tr.appendChild(td);
            });
            var actions = document.createElement('td');
            var editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.textContent = 'Edit';
            editBtn.addEventListener('click', function () { openLegEditor(ch); });
            var delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.textContent = 'Delete';
            delBtn.style.marginLeft = '0.35rem';
            delBtn.addEventListener('click', function () {
                if (!window.confirm('Delete leg ' + ch.id + '?')) return;
                deleteLeg(ch.id);
            });
            actions.appendChild(editBtn);
            actions.appendChild(delBtn);
            tr.appendChild(actions);
            tbody.appendChild(tr);
        });
    }

    function renderRecipeTable() {
        var tbody = document.getElementById('segment-recipes-tbody');
        var wrap = document.getElementById('segment-recipes-table-wrap');
        var empty = document.getElementById('segment-recipes-empty');
        var applyBtn = document.getElementById('btn-segment-recipes-apply');
        if (!tbody) return;
        if (!libraryState || !libraryState.has_library || !libraryState.chunks.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            if (applyBtn) applyBtn.disabled = true;
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        if (applyBtn) applyBtn.disabled = false;
        tbody.innerHTML = '';
        libraryState.chunks.forEach(function (ch) {
            var tr = document.createElement('tr');
            [ch.id, (ch.leg_label || '').slice(0, 48), ch.length_km != null ? Number(ch.length_km).toFixed(2) : '—']
                .forEach(function (text) {
                    var td = document.createElement('td');
                    td.textContent = text;
                    tr.appendChild(td);
                });
            EVENTS.forEach(function (ev) {
                var td = document.createElement('td');
                var inp = document.createElement('input');
                inp.type = 'number';
                inp.min = '1';
                inp.max = '99';
                inp.className = 'segment-recipe-order-input';
                inp.style.width = '3rem';
                inp.value = getOrder(ch.id, ev);
                inp.addEventListener('input', function () { setOrder(ch.id, ev, inp.value); });
                td.appendChild(inp);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function loadLibrary() {
        if (!isConfigPackageWorkspace()) { showConfigSections(false); return Promise.resolve(); }
        showConfigSections(true);
        return fetch(apiBase() + '/segment-library', { credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                setLegStatus('');
                setRecipeStatus('');
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function deleteLeg(legId) {
        setLegStatus('Deleting leg…');
        fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legId), {
            method: 'DELETE',
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                setLegStatus('Leg deleted.');
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function closeLegEditor() {
        var modal = document.getElementById('leg-editor-modal');
        if (modal) { modal.hidden = true; modal.setAttribute('aria-hidden', 'true'); }
        legEditorMode = null;
        legEditorLegId = null;
        pendingGpxFile = null;
    }

    function openLegEditor(legOrNull) {
        var modal = document.getElementById('leg-editor-modal');
        var body = document.getElementById('leg-editor-body');
        var footer = document.getElementById('leg-editor-footer');
        var title = document.getElementById('leg-editor-title');
        if (!modal || !body || !footer) return;

        var isNew = !legOrNull;
        legEditorMode = isNew ? 'create' : 'edit';
        legEditorLegId = isNew ? null : legOrNull.id;
        var leg = legOrNull || {
            leg_label: pendingGpxFile ? pendingGpxFile.name.replace(/\.gpx$/i, '').replace(/_/g, ' ') : '',
            start_label: '',
            end_label: '',
            width_m: 3,
            schema: 'on_course_open',
            direction: 'uni',
            description: '',
            locations: []
        };

        if (title) title.textContent = isNew ? 'Add leg' : ('Edit leg ' + leg.id);
        body.innerHTML = '';

        function addField(label, id, value, type) {
            var wrap = document.createElement('div');
            wrap.style.marginBottom = '0.65rem';
            var lab = document.createElement('label');
            lab.textContent = label;
            lab.style.display = 'block';
            lab.style.fontWeight = '600';
            lab.style.fontSize = '0.85rem';
            var inp = document.createElement('input');
            inp.id = id;
            inp.type = type || 'text';
            inp.value = value != null ? value : '';
            inp.style.width = '100%';
            inp.style.boxSizing = 'border-box';
            wrap.appendChild(lab);
            wrap.appendChild(inp);
            body.appendChild(wrap);
            return inp;
        }

        addField('Leg label', 'leg-label', leg.leg_label);
        addField('Start place', 'leg-start-label', leg.start_label);
        addField('End place', 'leg-end-label', leg.end_label);
        addField('Width (m)', 'leg-width', leg.width_m, 'number');
        addField('Schema', 'leg-schema', leg.schema);
        addField('Direction', 'leg-direction', leg.direction);

        var locHead = document.createElement('h5');
        locHead.textContent = 'Locations on this leg';
        locHead.style.margin = '0.75rem 0 0.35rem';
        body.appendChild(locHead);
        var locList = document.createElement('div');
        locList.id = 'leg-locations-list';
        body.appendChild(locList);

        var locations = (leg.locations || []).slice();
        function renderLocRows() {
            locList.innerHTML = '';
            locations.forEach(function (loc, idx) {
                var row = document.createElement('div');
                row.style.cssText = 'display:grid;grid-template-columns:1fr 5rem 5rem 4rem auto;gap:0.25rem;margin-bottom:0.35rem;align-items:end;';
                var lbl = document.createElement('input');
                lbl.placeholder = 'Label';
                lbl.value = loc.loc_label || '';
                lbl.addEventListener('input', function () { loc.loc_label = lbl.value; });
                var typ = document.createElement('select');
                locationTypes().forEach(function (t) {
                    var o = document.createElement('option');
                    o.value = t;
                    o.textContent = t;
                    if (t === loc.loc_type) o.selected = true;
                    typ.appendChild(o);
                });
                typ.addEventListener('change', function () { loc.loc_type = typ.value; });
                var lat = document.createElement('input');
                lat.placeholder = 'Lat';
                lat.value = loc.lat != null ? loc.lat : '';
                lat.addEventListener('input', function () { loc.lat = parseFloat(lat.value); });
                var lon = document.createElement('input');
                lon.placeholder = 'Lon';
                lon.value = loc.lon != null ? loc.lon : '';
                lon.addEventListener('input', function () { loc.lon = parseFloat(lon.value); });
                var plc = document.createElement('select');
                ['start', 'end', 'along'].forEach(function (p) {
                    var o = document.createElement('option');
                    o.value = p;
                    o.textContent = p;
                    if (p === (loc.placement || 'along')) o.selected = true;
                    plc.appendChild(o);
                });
                plc.addEventListener('change', function () { loc.placement = plc.value; });
                var rm = document.createElement('button');
                rm.type = 'button';
                rm.textContent = '×';
                rm.addEventListener('click', function () {
                    locations.splice(idx, 1);
                    renderLocRows();
                });
                row.appendChild(lbl);
                row.appendChild(typ);
                row.appendChild(lat);
                row.appendChild(lon);
                row.appendChild(plc);
                row.appendChild(rm);
                locList.appendChild(row);
            });
        }
        renderLocRows();

        var addLocBtn = document.createElement('button');
        addLocBtn.type = 'button';
        addLocBtn.textContent = 'Add location';
        addLocBtn.style.marginTop = '0.35rem';
        addLocBtn.addEventListener('click', function () {
            var lat = leg.start_lat;
            var lon = leg.start_lon;
            locations.push({
                loc_label: '',
                loc_type: 'water',
                lat: lat,
                lon: lon,
                placement: 'along'
            });
            renderLocRows();
        });
        body.appendChild(addLocBtn);

        if (!isNew) {
            var gpxBtn = document.createElement('button');
            gpxBtn.type = 'button';
            gpxBtn.textContent = 'Replace GPX file…';
            gpxBtn.style.marginTop = '0.75rem';
            gpxBtn.addEventListener('click', function () {
                var inp = document.createElement('input');
                inp.type = 'file';
                inp.accept = '.gpx';
                inp.addEventListener('change', function () {
                    if (!inp.files || !inp.files[0]) return;
                    replaceLegGpx(leg.id, inp.files[0]);
                });
                inp.click();
            });
            body.appendChild(gpxBtn);
        }

        footer.innerHTML = '';
        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', closeLegEditor);
        var saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.textContent = 'Save leg';
        saveBtn.className = 'primary';
        saveBtn.addEventListener('click', function () {
            saveLegEditor(locations);
        });
        footer.appendChild(cancelBtn);
        footer.appendChild(saveBtn);

        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
    }

    function collectLegFields() {
        return {
            leg_label: (document.getElementById('leg-label') || {}).value || '',
            start_label: (document.getElementById('leg-start-label') || {}).value || '',
            end_label: (document.getElementById('leg-end-label') || {}).value || '',
            width_m: parseFloat((document.getElementById('leg-width') || {}).value) || 3,
            schema: (document.getElementById('leg-schema') || {}).value || 'on_course_open',
            direction: (document.getElementById('leg-direction') || {}).value || 'uni'
        };
    }

    function saveLegEditor(locations) {
        var fields = collectLegFields();
        fields.locations = locations;
        if (legEditorMode === 'create') {
            if (!pendingGpxFile) {
                setLegStatus('Choose a GPX file first.', true);
                return;
            }
            var fd = new FormData();
            fd.append('file', pendingGpxFile);
            fd.append('leg_label', fields.leg_label);
            fd.append('start_label', fields.start_label);
            fd.append('end_label', fields.end_label);
            fd.append('width_m', String(fields.width_m));
            fd.append('schema', fields.schema);
            fd.append('direction', fields.direction);
            setLegStatus('Saving leg…');
            fetch(apiBase() + '/segment-library/legs', { method: 'POST', credentials: 'same-origin', body: fd })
                .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
                .then(function (payload) {
                    if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                    applyLibraryState(payload.data);
                    closeLegEditor();
                    setLegStatus('Leg added.');
                })
                .catch(function (err) { setLegStatus(err.message || String(err), true); });
            return;
        }
        setLegStatus('Saving leg…');
        fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legEditorLegId), {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(fields)
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                closeLegEditor();
                setLegStatus('Leg saved.');
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function replaceLegGpx(legId, file) {
        var fd = new FormData();
        fd.append('file', file);
        setLegStatus('Updating GPX…');
        fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legId) + '/gpx', {
            method: 'PUT',
            credentials: 'same-origin',
            body: fd
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                setLegStatus('GPX updated.');
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function seedReference() {
        setLegStatus('Loading Fredericton reference…');
        return fetch(apiBase() + '/segment-library/seed-reference', { method: 'POST', credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                setLegStatus('Reference loaded (' + (payload.data.chunks || []).length + ' legs).');
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function uploadGpxBulk(files) {
        if (!files || !files.length) return;
        var fd = new FormData();
        for (var i = 0; i < files.length; i++) fd.append('files', files[i]);
        setLegStatus('Importing GPX…');
        fetch(apiBase() + '/segment-library/upload', { method: 'POST', credentials: 'same-origin', body: fd })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                setLegStatus('Imported ' + (payload.data.chunks || []).length + ' leg(s). Edit each leg to set start/end names and locations.');
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function saveRecipes() {
        setRecipeStatus('Saving recipes and exporting…');
        fetch(apiBase() + '/segment-library/recipes', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_by_event: orderGrid, export_csv: true })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                var data = payload.data;
                if (data.library) applyLibraryState(data.library);
                if (data.apply) {
                    setRecipeStatus('Exported ' + (data.apply.segment_count || 0) + ' segments to segments.csv.');
                }
                if (data.course) {
                    document.dispatchEvent(new CustomEvent('segment-recipes-applied', {
                        detail: { course: data.course }
                    }));
                }
            })
            .catch(function (err) { setRecipeStatus(err.message || String(err), true); });
    }

    function bindUi() {
        var addLegBtn = document.getElementById('btn-add-leg');
        var addLegFile = document.createElement('input');
        addLegFile.type = 'file';
        addLegFile.accept = '.gpx';
        addLegFile.style.display = 'none';
        document.body.appendChild(addLegFile);
        if (addLegBtn) {
            addLegBtn.addEventListener('click', function () {
                addLegFile.value = '';
                addLegFile.click();
            });
        }
        addLegFile.addEventListener('change', function () {
            if (!addLegFile.files || !addLegFile.files[0]) return;
            pendingGpxFile = addLegFile.files[0];
            openLegEditor(null);
        });
        var seedBtn = document.getElementById('btn-segment-library-seed');
        if (seedBtn) {
            seedBtn.addEventListener('click', function () {
                if (!window.confirm('Load Fredericton reference legs into this package? Existing legs with the same ids may be replaced on re-seed.')) return;
                seedReference();
            });
        }
        var bulkInput = document.getElementById('segment-library-gpx-input');
        if (bulkInput) {
            bulkInput.addEventListener('change', function () {
                uploadGpxBulk(bulkInput.files);
                bulkInput.value = '';
            });
        }
        var applyBtn = document.getElementById('btn-segment-recipes-apply');
        if (applyBtn) applyBtn.addEventListener('click', saveRecipes);
        var closeBtn = document.getElementById('leg-editor-close');
        if (closeBtn) closeBtn.addEventListener('click', closeLegEditor);
        var backdrop = document.querySelector('#leg-editor-modal .course-location-modal-backdrop');
        if (backdrop) backdrop.addEventListener('click', closeLegEditor);
    }

    document.addEventListener('DOMContentLoaded', function () {
        bindUi();
        if (isConfigPackageWorkspace()) loadLibrary();
    });
    window.addEventListener('popstate', function () {
        if (isConfigPackageWorkspace()) loadLibrary();
        else showConfigSections(false);
    });

    window.segmentRecipes = { load: loadLibrary, refresh: loadLibrary };
})();
