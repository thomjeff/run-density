/**
 * Junction Flow authoring (Issue #817) — Package Build → Junctions tab.
 */
(function () {
    'use strict';

    let state = {
        configId: null,
        proximityM: 10,
        doc: { version: 1, junctions: [] },
        selectedId: null,
        dirty: false,
        placeMode: false,
        map: null,
        pinMarker: null,
        segLayer: null,
        highlightLayer: null,
        nearby: [],
        mapFeatures: [],
        nearbySortCol: 'seg_id',
        nearbySortDir: 'asc',
        chromeBound: false,
        editingIxId: null,
        unloadBound: false,
        nearbyRequestSeq: 0,
    };

    function getConfigId() {
        const params = new URLSearchParams(window.location.search);
        return (params.get('config_id') || '').trim() || null;
    }

    function status(msg, isError) {
        const el = document.getElementById('junctions-status');
        if (!el) return;
        el.textContent = msg || '';
        el.style.color = isError ? '#c0392b' : '#666';
    }

    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function selectedJunction() {
        return (state.doc.junctions || []).find(function (j) {
            return j.id === state.selectedId;
        }) || null;
    }

    function markDirty() {
        state.dirty = true;
        status('Unsaved changes');
    }

    function hasCourseSegments() {
        if (window.configPackageCourse && window.configPackageCourse.hasCombinedCourse) {
            return !!window.configPackageCourse.hasCombinedCourse();
        }
        return false;
    }

    function ensureCourseLoaded() {
        if (hasCourseSegments()) return Promise.resolve(true);
        if (!state.configId) return Promise.resolve(false);
        return fetch('/api/config/packages/' + encodeURIComponent(state.configId) + '/course', {
            credentials: 'same-origin',
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                const segs = data && data.course && data.course.segments;
                return !!(segs && segs.length);
            })
            .catch(function () { return false; });
    }

    function ensureMap() {
        if (state.map) {
            setTimeout(function () { state.map.invalidateSize(); }, 50);
            return state.map;
        }
        const el = document.getElementById('junctions-map');
        if (!el || typeof L === 'undefined') return null;
        state.map = L.map(el, { zoomControl: true }).setView([45.95, -66.64], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '© OpenStreetMap, © CARTO',
            maxZoom: 19,
        }).addTo(state.map);
        state.segLayer = L.layerGroup().addTo(state.map);
        state.highlightLayer = L.layerGroup().addTo(state.map);
        // Clicks on polylines must reach the map (interactive:false on lines below)
        state.map.on('click', onMapClick);
        return state.map;
    }

    function onMapClick(ev) {
        if (!state.placeMode) return;
        ensureDraftJunction();
        setPin(ev.latlng.lat, ev.latlng.lng, true);
        stopPlaceMode();
        discoverNearby();
    }

    function stopPlaceMode() {
        state.placeMode = false;
        const btn = document.getElementById('junctions-btn-place');
        if (btn) {
            btn.classList.remove('active');
            btn.style.outline = '';
            btn.style.background = '';
        }
        if (state.map) state.map.getContainer().style.cursor = '';
    }

    function ensureDraftJunction() {
        if (selectedJunction()) return selectedJunction();
        const id = 'junc_' + Date.now().toString(36);
        const labelEl = document.getElementById('junction-label');
        const label = (labelEl && labelEl.value.trim()) || 'New junction';
        const j = {
            id: id,
            label: label,
            lat: null,
            lon: null,
            nearby_seg_ids: [],
            nearby_segments: [],
            interactions: [],
            streams: [],
        };
        state.doc.junctions = state.doc.junctions || [];
        state.doc.junctions.push(j);
        state.selectedId = id;
        renderList();
        if (labelEl) labelEl.value = j.label;
        markDirty();
        return j;
    }

    function startPlaceMode() {
        ensureMap();
        ensureDraftJunction();
        state.placeMode = true;
        const btn = document.getElementById('junctions-btn-place');
        if (btn) {
            btn.classList.add('active');
            btn.style.outline = '2px solid #2980b9';
            btn.style.background = '#eaf4fb';
        }
        if (state.map) {
            state.map.getContainer().style.cursor = 'crosshair';
            setTimeout(function () { state.map.invalidateSize(); }, 50);
        }
        status('Place pin active — click the map (including on course lines)');
    }

    function setPin(lat, lon, fromUser) {
        const j = ensureDraftJunction();
        if (!j) return;
        j.lat = Number(lat);
        j.lon = Number(lon);
        const latEl = document.getElementById('junction-lat');
        const lonEl = document.getElementById('junction-lon');
        if (latEl) latEl.value = String(j.lat);
        if (lonEl) lonEl.value = String(j.lon);
        const map = ensureMap();
        if (!map) return;
        if (state.pinMarker) {
            state.pinMarker.setLatLng([j.lat, j.lon]);
        } else {
            state.pinMarker = L.circleMarker([j.lat, j.lon], {
                radius: 10,
                color: '#111',
                weight: 2,
                fillColor: '#111',
                fillOpacity: 0.45,
                interactive: false,
            }).addTo(map);
        }
        map.panTo([j.lat, j.lon]);
        if (fromUser) markDirty();
    }

    function fitMapToNearby() {
        const map = state.map;
        if (!map || !(state.nearby || []).length) return;
        const points = [];
        if (state.pinMarker) points.push(state.pinMarker.getLatLng());
        // Zoom to the junction cluster (near-side endpoints), not full spur polylines
        state.nearby.forEach(function (s) {
            const near = s.near_endpoint || '';
            if ((near === 'start' || near === 'both') &&
                s.start_lat != null && s.start_lon != null) {
                points.push([s.start_lat, s.start_lon]);
            }
            if ((near === 'end' || near === 'both') &&
                s.end_lat != null && s.end_lon != null) {
                points.push([s.end_lat, s.end_lon]);
            }
        });
        if (!points.length) return;
        try {
            map.fitBounds(L.latLngBounds(points), {
                padding: [48, 48],
                maxZoom: 17,
            });
        } catch (e) { /* ignore */ }
    }

    function renderSegLines(highlightIds, options) {
        const map = ensureMap();
        if (!map || !state.segLayer) return;
        options = options || {};
        state.segLayer.clearLayers();
        state.highlightLayer.clearLayers();
        const hi = {};
        (highlightIds || []).forEach(function (id) { hi[id] = true; });
        const allBounds = [];
        state.mapFeatures.forEach(function (f) {
            const coords = (f.geometry && f.geometry.coordinates) || [];
            if (coords.length < 2) return;
            const latlngs = coords.map(function (c) { return [c[1], c[0]]; });
            const segId = (f.properties && f.properties.seg_id) || '';
            const isHi = !!hi[segId];
            const line = L.polyline(latlngs, {
                color: isHi ? '#c0392b' : '#8B7355',
                weight: isHi ? 5 : 3,
                opacity: isHi ? 0.95 : 0.7,
                interactive: false,
            });
            line.bindTooltip(segId + (f.properties.seg_label ? ' — ' + f.properties.seg_label : ''));
            (isHi ? state.highlightLayer : state.segLayer).addLayer(line);
            latlngs.forEach(function (ll) { allBounds.push(ll); });
        });
        if (options.fit === 'nearby' && (highlightIds || []).length) {
            fitMapToNearby();
        } else if (options.fit === 'all' && allBounds.length) {
            if (state.pinMarker) allBounds.push(state.pinMarker.getLatLng());
            try {
                map.fitBounds(allBounds, { padding: [24, 24], maxZoom: 15 });
            } catch (e) { /* ignore */ }
        }
    }

    function loadMapSegments() {
        if (!state.configId) return Promise.resolve();
        return fetch('/api/config/packages/' + encodeURIComponent(state.configId) + '/junctions/map-segments', {
            credentials: 'same-origin',
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                state.mapFeatures = (data && data.features) || [];
                const nearbyIds = (state.nearby || []).map(function (s) { return s.seg_id; });
                renderSegLines(nearbyIds, {
                    fit: nearbyIds.length ? 'nearby' : 'all',
                });
            })
            .catch(function () {
                state.mapFeatures = [];
            });
    }

    function classifyNearbyRow(seg) {
        const id = seg.seg_id || '';
        // Heuristic for legend: "(2)" / later full pass vs university spur naming
        if (/\(2\)\s*$/.test(seg.seg_label || '') || / \(2\)$/.test(seg.seg_label || '')) {
            return 'second-pass';
        }
        const events = (seg.events || []).map(function (e) { return String(e).toLowerCase(); });
        if (events.length === 1 && events[0] === '10k' && /university|forest hill/i.test(seg.seg_label || '')) {
            return 'spur';
        }
        return '';
    }

    function eventLabelForTableId(eventId) {
        const eid = String(eventId || '').toLowerCase();
        if (eid === '10k') return '10K';
        if (!eid) return '';
        return eid.charAt(0).toUpperCase() + eid.slice(1);
    }

    function formatKmRange(fromKm, toKm) {
        if (fromKm == null || toKm == null || fromKm === '' || toKm === '') return '—';
        const a = Number(fromKm);
        const b = Number(toKm);
        if (!isFinite(a) || !isFinite(b)) return '—';
        if (a === 0 && b === 0) return '0';
        return a.toFixed(2) + '–' + b.toFixed(2);
    }

    function eventsDisplayList(events) {
        return (events || []).map(function (e) {
            return eventLabelForTableId(e);
        }).join(', ');
    }

    function segIdSortKey(segId) {
        const s = String(segId || '');
        const m = s.match(/^([A-Za-z]*)(\d+)(.*)$/);
        if (!m) return [s.toLowerCase(), 0, ''];
        return [m[1].toLowerCase(), parseInt(m[2], 10) || 0, m[3].toLowerCase()];
    }

    function compareSegIds(a, b) {
        const ka = segIdSortKey(a);
        const kb = segIdSortKey(b);
        for (let i = 0; i < 3; i++) {
            if (ka[i] < kb[i]) return -1;
            if (ka[i] > kb[i]) return 1;
        }
        return 0;
    }

    function sortNearbyRows() {
        const dir = state.nearbySortDir === 'desc' ? -1 : 1;
        state.nearby.sort(function (a, b) {
            return dir * compareSegIds(a.seg_id, b.seg_id);
        });
    }

    function renderSegmentsTableHeader(eventIds) {
        const thead = document.getElementById('junctions-segments-thead-row');
        if (!thead) return;
        thead.innerHTML = '';
        const idTh = document.createElement('th');
        idTh.id = 'junctions-segments-sort-id';
        idTh.className = 'table-sortable';
        idTh.setAttribute('data-sort', 'seg_id');
        idTh.style.cursor = 'pointer';
        idTh.innerHTML = 'ID <span class="table-sortable-indicator">▲</span>';
        idTh.setAttribute('aria-sort', state.nearbySortDir === 'desc' ? 'descending' : 'ascending');
        const ind = idTh.querySelector('.table-sortable-indicator');
        if (ind) ind.textContent = state.nearbySortDir === 'desc' ? '▼' : '▲';
        thead.appendChild(idTh);
        ['Label', 'End', 'Dist m', 'Events'].forEach(function (label) {
            const th = document.createElement('th');
            th.textContent = label;
            thead.appendChild(th);
        });
        (eventIds || []).forEach(function (eid) {
            const th = document.createElement('th');
            th.textContent = eventLabelForTableId(eid);
            thead.appendChild(th);
        });
        const lenTh = document.createElement('th');
        lenTh.textContent = 'Length';
        thead.appendChild(lenTh);
    }

    function renderNearby() {
        const tbody = document.getElementById('junctions-segments-tbody');
        if (!tbody) return;
        const eventIds = packageEventIds();
        renderSegmentsTableHeader(eventIds);
        tbody.innerHTML = '';
        const colCount = 5 + eventIds.length + 1;
        if (!state.nearby.length) {
            tbody.innerHTML =
                '<tr><td colspan="' + colCount + '" class="text-secondary">' +
                'No segments within proximity. Place a pin and Find nearby.</td></tr>';
            const legend = document.getElementById('junctions-segments-legend');
            if (legend) legend.textContent = '';
            renderSegLines([]);
            return;
        }
        sortNearbyRows();
        state.nearby.forEach(function (seg) {
            const tr = document.createElement('tr');
            const kind = classifyNearbyRow(seg);
            if (kind === 'second-pass') tr.className = 'junctions-row-second-pass';
            if (kind === 'spur') tr.className = 'junctions-row-spur';
            const ek = seg.event_kms || {};
            let html =
                '<td style="font-weight:600;">' + escapeHtml(seg.seg_id) + '</td>' +
                '<td>' + escapeHtml(seg.seg_label || '') + '</td>' +
                '<td>' + escapeHtml(seg.near_endpoint || '—') + '</td>' +
                '<td>' + escapeHtml(seg.distance_m != null ? seg.distance_m : '—') + '</td>' +
                '<td>' + escapeHtml(eventsDisplayList(seg.events)) + '</td>';
            eventIds.forEach(function (eid) {
                const row = ek[eid] || ek[String(eid).toLowerCase()] || {};
                html += '<td>' + escapeHtml(formatKmRange(row.from_km, row.to_km)) + '</td>';
            });
            html += '<td>' + escapeHtml(
                seg.length_km != null && isFinite(Number(seg.length_km))
                    ? String(Math.round(Number(seg.length_km) * 100) / 100)
                    : '—'
            ) + '</td>';
            tr.innerHTML = html;
            tbody.appendChild(tr);
        });
        const legend = document.getElementById('junctions-segments-legend');
        if (legend) {
            legend.textContent = state.nearby.length + ' within ' + state.proximityM + ' m';
        }
        renderSegLines(state.nearby.map(function (s) { return s.seg_id; }), { fit: 'nearby' });
    }

    function nearbyById() {
        const byId = {};
        // Prefer live discovery; fall back to selected junction cache
        const rows = (state.nearby && state.nearby.length)
            ? state.nearby
            : ((selectedJunction() || {}).nearby_segments || []);
        rows.forEach(function (s) { byId[s.seg_id] = s; });
        return byId;
    }

    function formatEventList(events) {
        const order = ['full', 'half', '10k', 'elite', 'open'];
        const labels = {
            full: 'Full',
            half: 'Half',
            '10k': '10k',
            elite: 'Elite',
            open: 'Open',
        };
        const lower = {};
        (events || []).forEach(function (e) {
            if (e) lower[String(e).toLowerCase()] = true;
        });
        const seen = [];
        order.forEach(function (k) {
            if (lower[k]) seen.push(labels[k]);
        });
        Object.keys(lower).sort().forEach(function (k) {
            if (order.indexOf(k) < 0) {
                seen.push(k.charAt(0).toUpperCase() + k.slice(1));
            }
        });
        return seen.length ? seen.join('+') : 'runners';
    }

    function namedSeg(segId, byId) {
        const row = byId[segId] || {};
        const label = String(row.seg_label || row.name || '').trim();
        if (!label || label === segId) return '(' + segId + ')';
        return label + ' (' + segId + ')';
    }

    function segEvents(segId, byId) {
        const row = byId[segId] || {};
        if (row.events && row.events.length) {
            return row.events.map(function (e) { return String(e).toLowerCase(); });
        }
        const ek = row.event_kms || {};
        return Object.keys(ek).map(function (e) { return String(e).toLowerCase(); });
    }

    function interactionDescription(ix) {
        const byId = nearbyById();
        const fromId = String(ix.from_seg_id || '').trim();
        const toIds = (ix.to_seg_ids || []).map(function (s) {
            return String(s || '').trim();
        }).filter(Boolean);
        if (!fromId || !toIds.length) return '';

        const scoped = {};
        (ix.events || []).forEach(function (e) {
            if (e) scoped[String(e).toLowerCase()] = true;
        });
        const hasScope = Object.keys(scoped).length > 0;

        if (ix.type === 'cross') {
            const conflicts = String(ix.conflicts_with_seg_id || '').trim();
            const fromEv = segEvents(fromId, byId);
            const toEv = segEvents(toIds[0], byId);
            let crossing = fromEv.filter(function (e) { return toEv.indexOf(e) >= 0; });
            if (!crossing.length) crossing = fromEv.slice();
            let crossed = segEvents(conflicts, byId);
            if (hasScope) {
                const c1 = crossing.filter(function (e) { return scoped[e]; });
                const c2 = crossed.filter(function (e) { return scoped[e]; });
                if (c1.length) crossing = c1;
                if (c2.length) crossed = c2;
            }
            const side = String(ix.side || '').toLowerCase();
            const mid = (side === 'left' || side === 'right') ? (' ' + side + ' to ') : ' to ';
            return (
                formatEventList(crossing) + ' runners from ' + namedSeg(fromId, byId) +
                ' crossing ' + formatEventList(crossed) + ' runners from ' +
                (conflicts ? namedSeg(conflicts, byId) : 'the conflict stream') +
                mid + namedSeg(toIds[0], byId)
            );
        }

        // merge
        let joining = segEvents(fromId, byId);
        let through = [];
        toIds.forEach(function (tid) {
            segEvents(tid, byId).forEach(function (e) {
                if ((e === 'full' || e === 'half') && through.indexOf(e) < 0) through.push(e);
            });
        });
        if (hasScope) {
            const j1 = joining.filter(function (e) { return scoped[e]; });
            const t1 = through.filter(function (e) { return scoped[e]; });
            if (j1.length) joining = j1;
            if (t1.length) through = t1;
        }
        const toPart = toIds.map(function (tid) { return namedSeg(tid, byId); }).join(', ');
        const throughBit = through.length
            ? (formatEventList(through) + ' traffic')
            : 'through traffic';
        return (
            formatEventList(joining) + ' runners from ' + namedSeg(fromId, byId) +
            ' merging into ' + throughBit + ' on ' + toPart
        );
    }

    function displayDescription(ix) {
        const authored = String(ix.description || '').trim();
        if (authored) return authored;
        return interactionDescription(ix);
    }

    function applyAutoDescriptionIfUnlocked(ix, typedBefore, autoBefore, descEl) {
        const suggested = interactionDescription(ix);
        if (!typedBefore || typedBefore === autoBefore) {
            ix.description = suggested;
            ix._lastAutoDescription = suggested;
            if (descEl) descEl.value = suggested;
            return suggested;
        }
        return String(ix.description || '').trim();
    }

    function deriveEvents(fromId, toIds) {
        const byId = {};
        state.nearby.forEach(function (s) { byId[s.seg_id] = s; });
        const from = byId[fromId];
        if (!from) return [];
        let set = {};
        (from.events || []).forEach(function (e) { set[String(e).toLowerCase()] = true; });
        const toList = Array.isArray(toIds) ? toIds : String(toIds || '').split(',');
        let union = {};
        toList.forEach(function (tid) {
            const t = byId[String(tid).trim()];
            if (!t) return;
            (t.events || []).forEach(function (e) { union[String(e).toLowerCase()] = true; });
        });
        return Object.keys(set).filter(function (e) { return union[e]; });
    }

    function packageEventIds() {
        if (window.CONFIG_PACKAGE_EVENTS && window.CONFIG_PACKAGE_EVENTS.length) {
            return window.CONFIG_PACKAGE_EVENTS.map(function (e) {
                return String(e).toLowerCase();
            });
        }
        const raw = window.EVENT_CHOICES_FROM_SERVER || [];
        return raw.map(function (item) {
            if (typeof item === 'string') return item.toLowerCase();
            return String(item.value || item.label || '').toLowerCase();
        }).filter(Boolean);
    }

    function nearbySegIds(extra) {
        const ids = state.nearby.map(function (s) { return s.seg_id; });
        const extras = Array.isArray(extra) ? extra : (extra ? [extra] : []);
        extras.forEach(function (id) {
            const sid = String(id || '').trim();
            if (sid && ids.indexOf(sid) < 0) ids.push(sid);
        });
        return ids;
    }

    function segSelectHtml(field, selected, includeBlank) {
        let html = '<select data-f="' + field + '" class="config-package-input">';
        if (includeBlank) html += '<option value="">—</option>';
        nearbySegIds(selected).forEach(function (id) {
            html += '<option value="' + escapeHtml(id) + '"' +
                (id === selected ? ' selected' : '') + '>' + escapeHtml(id) + '</option>';
        });
        html += '</select>';
        return html;
    }

    function multiSelectHtml(field, options, selectedValues) {
        const selectedSet = {};
        (selectedValues || []).forEach(function (v) {
            selectedSet[String(v).toLowerCase()] = true;
        });
        const opts = options || [];
        const size = Math.min(5, Math.max(2, opts.length || 2));
        let html = '<select data-f="' + field + '" class="config-package-input" multiple size="' +
            size + '" style="min-width:5.5rem; max-width:8rem;">';
        opts.forEach(function (val) {
            const v = String(val);
            html += '<option value="' + escapeHtml(v) + '"' +
                (selectedSet[v.toLowerCase()] ? ' selected' : '') + '>' +
                escapeHtml(v) + '</option>';
        });
        html += '</select>';
        return html;
    }

    function selectedOptions(el) {
        if (!el) return [];
        return Array.prototype.slice.call(el.selectedOptions || [])
            .map(function (o) { return o.value; })
            .filter(Boolean);
    }

    function displayText(value) {
        if (value == null || value === '') return '—';
        if (Array.isArray(value)) {
            const parts = value.filter(Boolean);
            return parts.length ? parts.join(', ') : '—';
        }
        return String(value);
    }

    function typeLabel(type) {
        return type === 'merge' ? 'Merge' : 'Cross';
    }

    function sideLabel(side) {
        if (side === 'left') return 'Left';
        if (side === 'right') return 'Right';
        return '—';
    }

    function finishEditingInteraction() {
        syncEditingInteractionFromDom();
        state.editingIxId = null;
    }

    function syncEditingInteractionFromDom() {
        const j = selectedJunction();
        if (!j || !state.editingIxId) return;
        const tr = document.querySelector(
            '#junctions-ix-tbody tr[data-ix="' + state.editingIxId + '"]'
        );
        if (!tr) return;
        const ix = (j.interactions || []).find(function (x) {
            return x.id === state.editingIxId;
        });
        if (!ix) return;
        const typeEl = tr.querySelector('[data-f=type]');
        if (!typeEl) return;
        const type = typeEl.value || 'cross';
        const side = (tr.querySelector('[data-f=side]') || {}).value || '';
        const from = (tr.querySelector('[data-f=from]') || {}).value || '';
        let toSegs = [];
        const toEl = tr.querySelector('[data-f=to]');
        if (type === 'merge') {
            toSegs = selectedOptions(toEl);
        } else if (toEl && toEl.value) {
            toSegs = [toEl.value];
        }
        const conflictsEl = tr.querySelector('[data-f=conflicts]');
        const conflicts = type === 'cross' && conflictsEl ? (conflictsEl.value || '') : '';
        let events = selectedOptions(tr.querySelector('[data-f=events]'));
        if (!events.length) events = deriveEvents(from, toSegs);
        ix.type = type;
        ix.side = side;
        ix.from_seg_id = from;
        ix.to_seg_ids = toSegs;
        ix.conflicts_with_seg_id = conflicts;
        ix.events = events;
        const descEl = tr.querySelector('[data-f=description]');
        if (descEl) {
            ix.description = String(descEl.value || '').trim();
        }
        j.nearby_seg_ids = state.nearby.map(function (s) { return s.seg_id; });
        j.nearby_segments = state.nearby.slice();
    }

    function syncInteractionsFromDom() {
        syncEditingInteractionFromDom();
        const j = selectedJunction();
        if (!j) return;
        j.nearby_seg_ids = state.nearby.map(function (s) { return s.seg_id; });
        j.nearby_segments = state.nearby.slice();
    }

    function deleteInteraction(ixId) {
        const j = selectedJunction();
        if (!j) return;
        const ta = window.TableActions;
        if (ta && !ta.doubleConfirmDelete({
            subject: 'this interaction',
            detail: 'It will remain until you click Save junctions (or discard by leaving).',
        })) {
            return;
        }
        if (!ta && !window.confirm('Delete this interaction?')) return;
        syncEditingInteractionFromDom();
        j.interactions = (j.interactions || []).filter(function (x) { return x.id !== ixId; });
        if (state.editingIxId === ixId) state.editingIxId = null;
        renderInteractions();
        markDirty();
    }

    function beginEditInteraction(ixId) {
        if (state.editingIxId && state.editingIxId !== ixId) {
            syncEditingInteractionFromDom();
        }
        if (state.editingIxId === ixId) {
            finishEditingInteraction();
            renderInteractions();
            return;
        }
        state.editingIxId = ixId;
        renderInteractions();
    }

    function wireInteractionRow(tr, ix) {
        tr.querySelectorAll('select, textarea, input').forEach(function (el) {
            const evtName = el.tagName === 'TEXTAREA' || el.tagName === 'INPUT' ? 'input' : 'change';
            el.addEventListener(evtName, function () {
                const field = el.getAttribute('data-f');
                const descEl = tr.querySelector('[data-f=description]');
                const typedBefore = descEl
                    ? String(descEl.value || '').trim()
                    : String(ix.description || '').trim();
                const autoBefore = ix._lastAutoDescription || interactionDescription(ix);
                syncEditingInteractionFromDom();
                markDirty();
                if (field === 'description') {
                    return;
                }
                const j = selectedJunction();
                const live = j && (j.interactions || []).find(function (x) {
                    return x.id === ix.id;
                });
                if (!live) return;
                applyAutoDescriptionIfUnlocked(live, typedBefore, autoBefore, descEl);
                if (field === 'type') {
                    renderInteractions();
                }
            });
        });
        const actions = document.createElement('td');
        actions.className = 'course-map-action-cell';
        const ta = window.TableActions;
        if (ta) {
            actions.appendChild(
                ta.createIconButton(
                    'edit',
                    state.editingIxId === ix.id ? 'Done editing' : 'Edit interaction',
                    function (ev) {
                        ev.stopPropagation();
                        beginEditInteraction(ix.id);
                    }
                )
            );
            actions.appendChild(
                ta.createIconButton('delete', 'Delete interaction', function (ev) {
                    ev.stopPropagation();
                    deleteInteraction(ix.id);
                })
            );
        }
        tr.appendChild(actions);
    }

    function renderInteractions() {
        const j = selectedJunction();
        const tbody = document.getElementById('junctions-ix-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (!j) return;
        if (!(j.interactions || []).length) {
            tbody.innerHTML =
                '<tr><td colspan="8" class="text-secondary">' +
                'No interactions yet. Add a cross or merge.</td></tr>';
            return;
        }
        (j.interactions || []).forEach(function (ix, idx) {
            const id = ix.id || ('ix_' + (idx + 1));
            ix.id = id;
            const tr = document.createElement('tr');
            tr.setAttribute('data-ix', id);
            const editing = state.editingIxId === id;
            const isMerge = ix.type === 'merge';
            const toIds = ix.to_seg_ids || [];
            if (!String(ix.description || '').trim()) {
                ix.description = interactionDescription(ix);
                ix._lastAutoDescription = ix.description;
            }
            const desc = displayDescription(ix);

            if (!editing) {
                tr.innerHTML =
                    '<td>' + escapeHtml(typeLabel(ix.type)) + '</td>' +
                    '<td>' + escapeHtml(sideLabel(ix.side)) + '</td>' +
                    '<td>' + escapeHtml(displayText(ix.from_seg_id)) + '</td>' +
                    '<td>' + escapeHtml(displayText(toIds)) + '</td>' +
                    '<td>' + escapeHtml(isMerge ? '—' : displayText(ix.conflicts_with_seg_id)) + '</td>' +
                    '<td class="junctions-ix-desc-col" title="' + escapeHtml(desc) + '">' +
                    escapeHtml(desc || '—') + '</td>' +
                    '<td>' + escapeHtml(eventsDisplayList(ix.events || [])) + '</td>';
                tbody.appendChild(tr);
                wireInteractionRow(tr, ix);
                return;
            }

            const toCell = isMerge
                ? multiSelectHtml('to', nearbySegIds(toIds), toIds)
                : segSelectHtml('to', toIds[0] || '', true);
            const conflictsCell = isMerge
                ? '<select data-f="conflicts" class="config-package-input" disabled>' +
                  '<option value="">—</option></select>'
                : segSelectHtml('conflicts', ix.conflicts_with_seg_id || '', true);

            tr.innerHTML =
                '<td>' +
                '<select data-f="type" class="config-package-input">' +
                '<option value="cross"' + (!isMerge ? ' selected' : '') + '>Cross</option>' +
                '<option value="merge"' + (isMerge ? ' selected' : '') + '>Merge</option></select></td>' +
                '<td>' +
                '<select data-f="side" class="config-package-input" title="Direction the runner turns">' +
                '<option value=""' + (!ix.side ? ' selected' : '') + '>—</option>' +
                '<option value="left"' + (ix.side === 'left' ? ' selected' : '') + '>Left</option>' +
                '<option value="right"' + (ix.side === 'right' ? ' selected' : '') + '>Right</option></select></td>' +
                '<td>' + segSelectHtml('from', ix.from_seg_id || '', true) + '</td>' +
                '<td>' + toCell + '</td>' +
                '<td>' + conflictsCell + '</td>' +
                '<td class="junctions-ix-desc-col">' +
                '<textarea data-f="description" class="config-package-input junctions-ix-desc-input" ' +
                'rows="3" placeholder="Plain-language description for race directors">' +
                escapeHtml(desc) + '</textarea></td>' +
                '<td>' + multiSelectHtml('events', packageEventIds(), ix.events || []) + '</td>';

            tbody.appendChild(tr);
            wireInteractionRow(tr, ix);
        });
    }

    function renderList() {
        const ul = document.getElementById('junctions-list');
        if (!ul) return;
        ul.innerHTML = '';
        (state.doc.junctions || []).forEach(function (j) {
            const li = document.createElement('li');
            li.style.cssText = 'padding:0.5rem 0.75rem; border-bottom:1px solid #eee; cursor:pointer;';
            if (j.id === state.selectedId) {
                li.style.background = '#eef5fb';
                li.style.fontWeight = '600';
            }
            li.textContent = j.label || j.id;
            li.addEventListener('click', function () {
                syncFormToSelected();
                selectJunction(j.id);
            });
            ul.appendChild(li);
        });
        if (!(state.doc.junctions || []).length) {
            ul.innerHTML = '<li style="padding:0.75rem; color:#666;">No junctions yet</li>';
        }
    }

    function syncFormToSelected() {
        const j = selectedJunction();
        if (!j) return;
        const labelEl = document.getElementById('junction-label');
        if (labelEl) j.label = labelEl.value.trim() || j.label;
        const latEl = document.getElementById('junction-lat');
        const lonEl = document.getElementById('junction-lon');
        if (latEl && latEl.value !== '') j.lat = Number(latEl.value);
        if (lonEl && lonEl.value !== '') j.lon = Number(lonEl.value);
        syncInteractionsFromDom();
    }

    function clearPin() {
        if (state.pinMarker && state.map) {
            state.map.removeLayer(state.pinMarker);
        }
        state.pinMarker = null;
    }

    function resetEditorSurfaces() {
        state.nearby = [];
        state.editingIxId = null;
        clearPin();
        const labelEl = document.getElementById('junction-label');
        const latEl = document.getElementById('junction-lat');
        const lonEl = document.getElementById('junction-lon');
        const j = selectedJunction();
        if (labelEl) labelEl.value = j ? (j.label || '') : '';
        if (latEl) latEl.value = j && j.lat != null ? j.lat : '';
        if (lonEl) lonEl.value = j && j.lon != null ? j.lon : '';
        renderNearby();
        renderInteractions();
        renderSegLines([], { fit: 'all' });
    }

    function selectJunction(id, opts) {
        opts = opts || {};
        if (state.selectedId && state.selectedId !== id) {
            syncFormToSelected();
            state.editingIxId = null;
        }
        // Invalidate in-flight nearby lookups from the previous junction
        if (!opts.keepNearbyRequest) state.nearbyRequestSeq += 1;
        state.selectedId = id;
        const j = selectedJunction();
        renderList();
        if (!j) {
            resetEditorSurfaces();
            return;
        }
        document.getElementById('junction-label').value = j.label || '';
        document.getElementById('junction-lat').value = j.lat != null ? j.lat : '';
        document.getElementById('junction-lon').value = j.lon != null ? j.lon : '';
        state.nearby = Array.isArray(j.nearby_segments) ? j.nearby_segments.slice() : [];
        state.editingIxId = null;
        if (j.lat != null && j.lon != null && isFinite(Number(j.lat)) && isFinite(Number(j.lon))) {
            setPin(j.lat, j.lon, false);
            if (!state.nearby.length && !opts.skipDiscover) discoverNearby();
            else {
                renderNearby();
                renderInteractions();
            }
        } else {
            clearPin();
            renderNearby();
            renderInteractions();
            renderSegLines([], { fit: 'all' });
        }
        if (opts.preserveStatus) status(opts.preserveStatus);
    }

    function newJunction() {
        syncFormToSelected();
        finishEditingInteraction();
        const id = 'junc_' + Date.now().toString(36);
        const j = {
            id: id,
            label: 'New junction',
            lat: null,
            lon: null,
            nearby_seg_ids: [],
            nearby_segments: [],
            interactions: [],
            streams: [],
        };
        state.doc.junctions = state.doc.junctions || [];
        state.doc.junctions.push(j);
        markDirty();
        state.nearbyRequestSeq += 1;
        state.selectedId = id;
        state.editingIxId = null;
        state.nearby = [];
        renderList();
        document.getElementById('junction-label').value = j.label;
        document.getElementById('junction-lat').value = '';
        document.getElementById('junction-lon').value = '';
        clearPin();
        renderNearby();
        renderInteractions();
        renderSegLines([], { fit: 'all' });
        startPlaceMode();
        status('New junction — place a pin on the map');
    }

    function deleteSelected() {
        const j = selectedJunction();
        if (!j) return;
        if (!window.confirm('Delete junction "' + (j.label || j.id) + '"?')) return;
        state.doc.junctions = (state.doc.junctions || []).filter(function (x) { return x.id !== j.id; });
        state.selectedId = (state.doc.junctions[0] && state.doc.junctions[0].id) || null;
        markDirty();
        renderList();
        if (state.selectedId) selectJunction(state.selectedId);
        else {
            state.nearbyRequestSeq += 1;
            resetEditorSurfaces();
            status('No junctions');
        }
    }

    function discoverNearby() {
        const j = selectedJunction();
        if (!j || !state.configId) return;
        const lat = Number(document.getElementById('junction-lat').value);
        const lon = Number(document.getElementById('junction-lon').value);
        if (!isFinite(lat) || !isFinite(lon)) {
            status('Set lat/lon or place a pin first', true);
            return;
        }
        j.lat = lat;
        j.lon = lon;
        stopPlaceMode();
        status('Finding nearby segments…');
        state.nearbyRequestSeq += 1;
        const seq = state.nearbyRequestSeq;
        const forId = j.id;
        fetch('/api/config/packages/' + encodeURIComponent(state.configId) + '/junctions/nearby', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: lat, lon: lon }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                if (seq !== state.nearbyRequestSeq || state.selectedId !== forId) return;
                const target = selectedJunction();
                if (!target || target.id !== forId) return;
                if (!res.ok) throw new Error((res.d && res.d.detail) || 'Nearby lookup failed');
                state.nearby = res.d.segments || [];
                if (res.d.radius_m != null) state.proximityM = res.d.radius_m;
                const proxLabel = document.getElementById('junctions-proximity-label');
                if (proxLabel) proxLabel.textContent = String(state.proximityM);
                target.nearby_seg_ids = state.nearby.map(function (s) { return s.seg_id; });
                target.nearby_segments = state.nearby.slice();
                renderNearby();
                renderInteractions();
                markDirty();
                status(
                    state.nearby.length
                        ? (state.nearby.length + ' segment(s) within ' + state.proximityM + ' m')
                        : ('0 segments within ' + state.proximityM +
                            ' m — move the pin onto a segment start/end (not mid-corridor)')
                );
            })
            .catch(function (err) {
                if (seq !== state.nearbyRequestSeq || state.selectedId !== forId) return;
                status(err.message || String(err), true);
            });
    }

    function saveAll() {
        finishEditingInteraction();
        syncFormToSelected();
        if (!state.configId) return Promise.reject(new Error('No package open'));
        status('Saving…');
        return fetch('/api/config/packages/' + encodeURIComponent(state.configId) + '/junctions', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                version: state.doc.version || 1,
                junctions: state.doc.junctions || [],
            }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                if (!res.ok) throw new Error((res.d && res.d.detail) || 'Save failed');
                state.doc = {
                    version: res.d.version || 1,
                    junctions: res.d.junctions || [],
                    updated: res.d.updated,
                };
                state.dirty = false;
                state.editingIxId = null;
                const savedMsg = 'Saved' + (res.d.updated ? ' · ' + res.d.updated : '');
                status(savedMsg);
                renderList();
                if (state.selectedId) {
                    selectJunction(state.selectedId, {
                        skipDiscover: true,
                        keepNearbyRequest: true,
                        preserveStatus: savedMsg,
                    });
                }
            })
            .catch(function (err) {
                status(err.message || String(err), true);
                throw err;
            });
    }

    function loadDoc() {
        if (!state.configId) return Promise.resolve();
        // Don't wipe in-progress authoring when re-entering the tab
        if (state.dirty && (state.doc.junctions || []).length) {
            renderList();
            if (state.selectedId) selectJunction(state.selectedId);
            return Promise.resolve();
        }
        return fetch('/api/config/packages/' + encodeURIComponent(state.configId) + '/junctions', {
            credentials: 'same-origin',
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data) return;
                state.doc = {
                    version: data.version || 1,
                    junctions: data.junctions || [],
                    updated: data.updated,
                };
                if (data.proximity_m != null) state.proximityM = data.proximity_m;
                const proxLabel = document.getElementById('junctions-proximity-label');
                if (proxLabel) proxLabel.textContent = String(state.proximityM);
                state.dirty = false;
                renderList();
                if (state.doc.junctions.length) {
                    selectJunction(state.doc.junctions[0].id);
                }
            });
    }

    function showWorkspace(show) {
        const gate = document.getElementById('junctions-gate');
        const ws = document.getElementById('junctions-workspace');
        if (gate) gate.style.display = show ? 'none' : 'block';
        if (ws) ws.style.display = show ? 'block' : 'none';
    }

    function bindChrome() {
        if (state.chromeBound) return;
        state.chromeBound = true;
        const btnNew = document.getElementById('junctions-btn-new');
        const btnSave = document.getElementById('junctions-btn-save');
        const btnPlace = document.getElementById('junctions-btn-place');
        const btnDiscover = document.getElementById('junctions-btn-discover');
        const btnDelete = document.getElementById('junctions-btn-delete');
        const btnAddIx = document.getElementById('junctions-btn-add-ix');
        const segmentsTable = document.getElementById('junctions-segments-table');
        if (btnNew) btnNew.onclick = newJunction;
        if (btnSave) {
            btnSave.onclick = function () {
                saveAll().catch(function () { /* status already set */ });
            };
        }
        if (btnPlace) btnPlace.onclick = startPlaceMode;
        if (btnDiscover) btnDiscover.onclick = discoverNearby;
        if (btnDelete) btnDelete.onclick = deleteSelected;
        if (segmentsTable) {
            segmentsTable.addEventListener('click', function (e) {
                const th = e.target.closest('#junctions-segments-sort-id');
                if (!th) return;
                if (state.nearbySortCol === 'seg_id') {
                    state.nearbySortDir = state.nearbySortDir === 'asc' ? 'desc' : 'asc';
                } else {
                    state.nearbySortCol = 'seg_id';
                    state.nearbySortDir = 'asc';
                }
                renderNearby();
            });
        }
        if (btnAddIx) {
            btnAddIx.onclick = function () {
                const j = selectedJunction();
                if (!j) return;
                finishEditingInteraction();
                j.interactions = j.interactions || [];
                const newId = 'ix_' + Date.now().toString(36);
                j.interactions.push({
                    id: newId,
                    type: 'cross',
                    side: 'left',
                    from_seg_id: (state.nearby[0] && state.nearby[0].seg_id) || '',
                    to_seg_ids: [(state.nearby[1] && state.nearby[1].seg_id) || ''],
                    conflicts_with_seg_id: (state.nearby[2] && state.nearby[2].seg_id) || '',
                    events: [],
                    description: '',
                });
                const created = j.interactions[j.interactions.length - 1];
                created.events = deriveEvents(created.from_seg_id, created.to_seg_ids);
                created.description = interactionDescription(created);
                created._lastAutoDescription = created.description;
                state.editingIxId = newId;
                renderInteractions();
                markDirty();
            };
        }
        ['junction-label', 'junction-lat', 'junction-lon'].forEach(function (id) {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', function () {
                syncFormToSelected();
                const j = selectedJunction();
                if (j && (id === 'junction-lat' || id === 'junction-lon')) {
                    if (j.lat != null && j.lon != null) setPin(j.lat, j.lon, false);
                }
                markDirty();
            });
        });
        if (!state.unloadBound) {
            state.unloadBound = true;
            window.addEventListener('beforeunload', function (e) {
                if (!state.dirty) return;
                e.preventDefault();
                e.returnValue = '';
            });
        }
    }

    function initJunctionsAuthoring() {
        const root = document.getElementById('junctions-authoring-root');
        if (!root) return;
        state.configId = getConfigId();
        if (!state.configId) {
            status('Open a package to author junctions', true);
            showWorkspace(false);
            return;
        }
        bindChrome();
        ensureCourseLoaded().then(function (ready) {
            showWorkspace(ready);
            if (!ready) {
                status('Waiting for course segments', true);
                return;
            }
            ensureMap();
            Promise.all([loadDoc(), loadMapSegments()]).then(function () {
                status((state.doc.junctions || []).length + ' junction(s) loaded');
                setTimeout(function () {
                    if (state.map) state.map.invalidateSize();
                }, 100);
            });
        });
    }

    window.initJunctionsAuthoring = initJunctionsAuthoring;
    window.junctionsAuthoring = {
        isDirty: function () { return !!state.dirty; },
        saveAll: saveAll,
    };
})();
