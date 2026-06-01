/**
 * Course legs + event recipes (config packages). Issue #769 / #770
 */
(function () {
    'use strict';

    var libraryState = null;
    var orderGrid = {};
    var legEditorMode = null;
    var legEditorLegId = null;
    var pendingGpxFile = null;
    var selectedLegId = null;
    var addLocationOnMap = false;
    var legLocationClickHandler = null;
    var selectedLegLatLngs = null;
    var legMapLayers = { line: null, start: null, end: null, locs: null };
    /** Bumped on each leg selection / clear so stale geometry fetches do not draw extra lines. */
    var legGeometryRequestId = 0;
    var recipesModalDismissed = false;

    function schemaLabelForValue(value) {
        var v = String(value || 'on_course_open');
        var raw = window.SEGMENT_SCHEMA_CHOICES_FROM_SERVER || [];
        var found = raw.find(function (c) { return String(c.value) === v; });
        if (found && found.label) return found.label;
        return v;
    }

    function directionLabelForValue(value) {
        var v = String(value || 'uni');
        var raw = window.SEGMENT_DIRECTION_CHOICES_FROM_SERVER || [];
        var found = raw.find(function (c) { return String(c.value) === v; });
        if (found && found.label) return found.label;
        return v;
    }

    function formatLegWidth(width) {
        if (width == null || width === '') return '—';
        var n = Number(width);
        if (isNaN(n)) return '—';
        return String(n);
    }

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

    function packageEvents() {
        if (libraryState && libraryState.package_events && libraryState.package_events.length) {
            return libraryState.package_events.slice();
        }
        if (window.CONFIG_PACKAGE_EVENTS && window.CONFIG_PACKAGE_EVENTS.length) {
            return window.CONFIG_PACKAGE_EVENTS.slice();
        }
        return [];
    }

    function eventColumnLabel(eventId) {
        var raw = window.EVENT_CHOICES_FROM_SERVER || [];
        for (var i = 0; i < raw.length; i++) {
            var item = raw[i];
            if (typeof item === 'string' && item === eventId) {
                return eventId === '10k' ? '10K' : item.charAt(0).toUpperCase() + item.slice(1);
            }
            if (item && String(item.value).toLowerCase() === String(eventId).toLowerCase()) {
                return item.label || item.value;
            }
        }
        return eventId === '10k' ? '10K' : String(eventId);
    }

    function locationTypes() {
        var raw = window.LOCATION_TYPES_FROM_SERVER || ['aid', 'course', 'traffic', 'water', 'official'];
        return raw.map(function (t) {
            if (typeof t === 'string') return { value: t, label: t.charAt(0).toUpperCase() + t.slice(1) };
            return { value: t.value || t.label, label: t.label || t.value };
        });
    }

    function showPackageLegsUi(visible) {
        if (!visible || !isConfigPackageWorkspace()) {
            clearLegMap();
        }
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
        var list = document.getElementById('recipe-totals-list');
        if (!wrap || !list || !lengths) return;
        wrap.style.display = 'block';
        var events = packageEvents();
        list.textContent = events.map(function (ev) {
            var km = lengths[ev];
            return eventColumnLabel(ev) + ' ' + (km != null ? Number(km).toFixed(2) : '—') + ' km';
        }).join(' · ');
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
        recomputeTotalsLocal();
    }

    function recomputeTotalsLocal() {
        if (!libraryState || !libraryState.chunks) return;
        var lengths = {};
        packageEvents().forEach(function (ev) { lengths[ev] = 0; });
        packageEvents().forEach(function (ev) {
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
        if (selectedLegId) {
            var still = (data.chunks || []).some(function (c) { return c.id === selectedLegId; });
            if (still) selectLegById(selectedLegId);
            else clearLegMap();
        }
        if (
            hasCombinedCourse() &&
            window.configPackageCourse &&
            window.configPackageCourse.reloadCourse
        ) {
            window.configPackageCourse.reloadCourse();
        } else if (
            window.configPackageCourse &&
            typeof window.configPackageCourse.renderSegmentsList === 'function'
        ) {
            window.configPackageCourse.renderSegmentsList();
        }
    }

    function updateLegActionButtons() {
        var hasLeg = !!selectedLegId;
        ['btn-leg-add-location'].forEach(function (id) {
            var btn = document.getElementById(id);
            if (btn) btn.disabled = !hasLeg;
        });
    }

    function clearLegMapLayers() {
        var map = window.courseMappingMap;
        if (!map) return;
        if (legMapLayers.line) {
            map.removeLayer(legMapLayers.line);
            legMapLayers.line = null;
        }
        if (legMapLayers.start) {
            map.removeLayer(legMapLayers.start);
            legMapLayers.start = null;
        }
        if (legMapLayers.end) {
            map.removeLayer(legMapLayers.end);
            legMapLayers.end = null;
        }
        if (legMapLayers.locs) {
            map.removeLayer(legMapLayers.locs);
            legMapLayers.locs = null;
        }
        selectedLegLatLngs = null;
    }

    function invalidateLegGeometryRequests() {
        legGeometryRequestId += 1;
    }

    /** Nearest point on leg polyline ([[lat, lon], ...]) to a map click. */
    function snapClickToLegRoute(lat, lon, latlngs) {
        if (!latlngs || latlngs.length < 2) return { lat: lat, lon: lon };
        var bestLat = lat;
        var bestLon = lon;
        var bestD = Infinity;
        for (var i = 0; i < latlngs.length - 1; i++) {
            var lat1 = latlngs[i][0];
            var lon1 = latlngs[i][1];
            var lat2 = latlngs[i + 1][0];
            var lon2 = latlngs[i + 1][1];
            var dx = lon2 - lon1;
            var dy = lat2 - lat1;
            var len2 = dx * dx + dy * dy;
            var t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((lon - lon1) * dx + (lat - lat1) * dy) / len2));
            var plat = lat1 + t * dy;
            var plon = lon1 + t * dx;
            var d = (plat - lat) * (plat - lat) + (plon - lon) * (plon - lon);
            if (d < bestD) {
                bestD = d;
                bestLat = plat;
                bestLon = plon;
            }
        }
        return { lat: bestLat, lon: bestLon };
    }

    function stopLegLocationPinMode() {
        addLocationOnMap = false;
        window._legLocationPinModeActive = false;
        var btn = document.getElementById('btn-leg-add-location');
        if (btn) btn.classList.remove('active');
        var map = window.courseMappingMap;
        if (map && legLocationClickHandler) {
            map.off('click', legLocationClickHandler);
            legLocationClickHandler = null;
        }
    }

    function startLegLocationPinMode() {
        if (!selectedLegId) {
            setLegStatus('Select a leg in the table first.', true);
            return;
        }
        if (!selectedLegLatLngs || selectedLegLatLngs.length < 2) {
            setLegStatus('Wait for the leg route to finish loading on the map.', true);
            return;
        }
        stopLegLocationPinMode();
        addLocationOnMap = true;
        window._legLocationPinModeActive = true;
        var btn = document.getElementById('btn-leg-add-location');
        if (btn) btn.classList.add('active');
        var map = window.courseMappingMap;
        if (!map) return;

        legLocationClickHandler = function (e) {
            if (!addLocationOnMap || !selectedLegId) return;
            L.DomEvent.stopPropagation(e);
            var leg = (libraryState.chunks || []).find(function (c) { return c.id === selectedLegId; });
            if (!leg) return;

            var snapped = snapClickToLegRoute(e.latlng.lat, e.latlng.lng, selectedLegLatLngs);
            var placeLat = snapped.lat;
            var placeLon = snapped.lon;

            var content = document.createElement('div');
            content.className = 'course-map-popup';
            content.style.minWidth = '200px';
            var lblType = document.createElement('label');
            lblType.textContent = 'Type';
            lblType.style.display = 'block';
            lblType.style.marginBottom = '0.25rem';
            content.appendChild(lblType);
            var sel = document.createElement('select');
            sel.style.display = 'block';
            sel.style.width = '100%';
            sel.style.marginBottom = '0.65rem';
            sel.style.boxSizing = 'border-box';
            locationTypes().forEach(function (t) {
                var opt = document.createElement('option');
                opt.value = t.value;
                opt.textContent = t.label;
                if (t.value === 'course') opt.selected = true;
                sel.appendChild(opt);
            });
            content.appendChild(sel);
            var lblLabel = document.createElement('label');
            lblLabel.textContent = 'Label';
            lblLabel.style.display = 'block';
            lblLabel.style.marginBottom = '0.25rem';
            content.appendChild(lblLabel);
            var input = document.createElement('input');
            input.type = 'text';
            input.placeholder = 'e.g. Water station';
            input.style.display = 'block';
            input.style.width = '100%';
            input.style.marginBottom = '0.65rem';
            input.style.boxSizing = 'border-box';
            content.appendChild(input);
            var btnRow = document.createElement('div');
            btnRow.style.display = 'flex';
            btnRow.style.gap = '0.5rem';
            var btnAdd = document.createElement('button');
            btnAdd.type = 'button';
            btnAdd.className = 'course-btn primary';
            btnAdd.textContent = 'Add';
            var btnCancel = document.createElement('button');
            btnCancel.type = 'button';
            btnCancel.className = 'course-btn';
            btnCancel.textContent = 'Cancel';
            btnRow.appendChild(btnAdd);
            btnRow.appendChild(btnCancel);
            content.appendChild(btnRow);

            var pop = L.popup({ maxWidth: 375, className: 'location-popup' })
                .setContent(content)
                .setLatLng(e.latlng)
                .openOn(map);

            btnCancel.onclick = function () {
                map.closePopup();
            };
            btnAdd.onclick = function () {
                var locLabel = (input.value && input.value.trim()) || 'Location';
                var locType = sel.value || 'course';
                var locations = (leg.locations || []).slice();
                locations.push({
                    loc_label: locLabel,
                    loc_type: locType,
                    lat: Math.round(placeLat * 1e6) / 1e6,
                    lon: Math.round(placeLon * 1e6) / 1e6,
                    placement: 'along'
                });
                map.closePopup();
                setLegStatus('Saving location…');
                saveLegLocations(selectedLegId, locations)
                    .then(function () {
                        setLegStatus(
                            'Location placed on leg ' +
                                selectedLegId +
                                '. Open the Course tab to assign resources and segment details.'
                        );
                        selectLegById(selectedLegId);
                        if (
                            window.configPackageCourse &&
                            window.configPackageCourse.reloadCourse
                        ) {
                            return window.configPackageCourse.reloadCourse();
                        }
                    })
                    .catch(function (err) {
                        setLegStatus(err.message || String(err), true);
                    });
            };
        };
        map.on('click', legLocationClickHandler);
        setLegStatus('Click the purple route to place a location (snaps to the leg track).');
    }

    function clearLegMap() {
        stopLegLocationPinMode();
        invalidateLegGeometryRequests();
        clearLegMapLayers();
        selectedLegId = null;
        updateLegActionButtons();
    }

    function saveLegEndpoints(legId, startLabel, endLabel) {
        return fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legId), {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_label: startLabel, end_label: endLabel })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
            });
    }

    function endpointMarker(lat, lon, label, role, legId) {
        var map = window.courseMappingMap;
        if (!map || lat == null || lon == null) return null;
        var marker = L.circleMarker([lat, lon], {
            radius: 8,
            color: role === 'start' ? '#27ae60' : '#c0392b',
            fillColor: role === 'start' ? '#2ecc71' : '#e74c3c',
            fillOpacity: 0.9,
            weight: 2
        });
        marker.bindTooltip(label || (role === 'start' ? 'Start' : 'End'), { permanent: false });
        marker.on('click', function () {
            var next = window.prompt('Place name:', label || '');
            if (next == null) return;
            var fields = role === 'start' ? { start_label: next } : { end_label: next };
            fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legId), {
                method: 'PUT',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fields)
            })
                .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
                .then(function (payload) {
                    if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                    applyLibraryState(payload.data);
                })
                .catch(function (err) { setLegStatus(err.message || String(err), true); });
        });
        marker.addTo(map);
        return marker;
    }

    function drawLegLocations(leg) {
        var map = window.courseMappingMap;
        if (!map || !leg || !leg.locations) return;
        var group = L.layerGroup();
        leg.locations.forEach(function (loc, idx) {
            if (loc.lat == null || loc.lon == null) return;
            var m = L.circleMarker([loc.lat, loc.lon], {
                radius: 6,
                color: '#2980b9',
                fillColor: '#3498db',
                fillOpacity: 0.85,
                weight: 2
            });
            m.bindTooltip((loc.loc_label || 'Location') + ' (' + (loc.loc_type || 'course') + ')');
            m.addTo(group);
        });
        group.addTo(map);
        legMapLayers.locs = group;
    }

    function selectLegById(legId) {
        var leg = (libraryState && libraryState.chunks || []).find(function (c) { return c.id === legId; });
        if (!leg) return;
        selectedLegId = legId;
        updateLegActionButtons();
        document.querySelectorAll('#course-legs-tbody tr').forEach(function (tr) {
            tr.classList.toggle('selected', tr.dataset.legId === legId);
        });
        stopLegLocationPinMode();
        legGeometryRequestId += 1;
        var requestId = legGeometryRequestId;
        clearLegMapLayers();
        updateLegActionButtons();
        fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legId) + '/geometry', { credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (requestId !== legGeometryRequestId || selectedLegId !== legId) {
                    return;
                }
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                var map = window.courseMappingMap;
                if (!map) return;
                clearLegMapLayers();
                if (requestId !== legGeometryRequestId || selectedLegId !== legId) {
                    return;
                }
                var feature = payload.data.feature;
                var coords = feature.geometry.coordinates;
                var latlngs = coords.map(function (c) { return [c[1], c[0]]; });
                selectedLegLatLngs = latlngs;
                legMapLayers.line = L.polyline(latlngs, { color: '#8e44ad', weight: 5, opacity: 0.85 }).addTo(map);
                var props = feature.properties || {};
                legMapLayers.start = endpointMarker(
                    latlngs[0][0], latlngs[0][1],
                    props.start_label || leg.start_label,
                    'start',
                    legId
                );
                legMapLayers.end = endpointMarker(
                    latlngs[latlngs.length - 1][0], latlngs[latlngs.length - 1][1],
                    props.end_label || leg.end_label,
                    'end',
                    legId
                );
                drawLegLocations(leg);
                try { map.fitBounds(legMapLayers.line.getBounds(), { padding: [40, 40] }); } catch (e) { /* empty */ }
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function selectLeg(leg) {
        if (!leg) return;
        selectLegById(leg.id);
    }

    function saveLegLocations(legId, locations) {
        return fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(legId), {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ locations: locations })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
            });
    }

    function bindLegMapControls() {
        var map = window.courseMappingMap;
        if (!map || typeof L === 'undefined') return;
        var toolbar = document.getElementById('leg-map-toolbar');
        if (toolbar) {
            L.DomEvent.disableClickPropagation(toolbar);
            L.DomEvent.disableScrollPropagation(toolbar);
        }
        var basemap = document.getElementById('basemap-toggle');
        if (basemap) {
            L.DomEvent.disableClickPropagation(basemap);
            L.DomEvent.disableScrollPropagation(basemap);
        }
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
            clearLegMap();
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        tbody.innerHTML = '';
        chunks.forEach(function (ch) {
            var tr = document.createElement('tr');
            tr.dataset.legId = ch.id;
            tr.style.cursor = 'pointer';
            if (ch.id === selectedLegId) tr.classList.add('selected');
            [ch.id, (ch.leg_label || '').slice(0, 40), (ch.start_label || '').slice(0, 28),
                (ch.end_label || '').slice(0, 28),
                ch.length_km != null ? Number(ch.length_km).toFixed(2) : '—',
                formatLegWidth(ch.width_m),
                schemaLabelForValue(ch.schema),
                directionLabelForValue(ch.direction),
                String(ch.location_count != null ? ch.location_count : (ch.locations || []).length)
            ].forEach(function (text) {
                var td = document.createElement('td');
                td.textContent = text;
                tr.appendChild(td);
            });
            var actions = document.createElement('td');
            actions.className = 'course-map-action-cell';
            var ta = window.TableActions;
            if (ta) {
                actions.appendChild(
                    ta.createIconButton('edit', 'Edit leg', function (ev) {
                        ev.stopPropagation();
                        openLegEditor(ch);
                    })
                );
                actions.appendChild(
                    ta.createIconButton('delete', 'Delete leg', function (ev) {
                        ev.stopPropagation();
                        if (
                            !ta.doubleConfirmDelete({
                                subject: 'leg ' + ch.id,
                                detail:
                                    (ch.leg_label || '').trim() ||
                                    'GPX route and any locations on this leg will be removed.',
                            })
                        ) {
                            return;
                        }
                        deleteLeg(ch.id);
                    })
                );
            }
            tr.appendChild(actions);
            tr.addEventListener('click', function () { selectLeg(ch); });
            tbody.appendChild(tr);
        });
    }

    function renderRecipeTable() {
        var tbody = document.getElementById('segment-recipes-tbody');
        var thead = document.getElementById('segment-recipes-thead-row');
        var wrap = document.getElementById('segment-recipes-table-wrap');
        var empty = document.getElementById('segment-recipes-empty');
        var applyBtn = document.getElementById('btn-segment-recipes-apply');
        var events = packageEvents();
        if (!tbody) return;
        if (!libraryState || !libraryState.has_library || !libraryState.chunks.length || !events.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            if (applyBtn) applyBtn.disabled = true;
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        if (applyBtn) applyBtn.disabled = false;
        if (thead) {
            thead.innerHTML = '<th>Leg</th><th>Label</th><th>km</th>';
            events.forEach(function (ev) {
                var th = document.createElement('th');
                th.textContent = eventColumnLabel(ev);
                thead.appendChild(th);
            });
        }
        tbody.innerHTML = '';
        libraryState.chunks.forEach(function (ch) {
            var tr = document.createElement('tr');
            [ch.id, (ch.leg_label || '').slice(0, 48), ch.length_km != null ? Number(ch.length_km).toFixed(2) : '—']
                .forEach(function (text) {
                    var td = document.createElement('td');
                    td.textContent = text;
                    tr.appendChild(td);
                });
            events.forEach(function (ev) {
                var td = document.createElement('td');
                var inp = document.createElement('input');
                inp.type = 'number';
                inp.min = '1';
                inp.max = '99';
                inp.className = 'segment-recipe-order-input';
                inp.value = getOrder(ch.id, ev);
                inp.addEventListener('input', function () { setOrder(ch.id, ev, inp.value); });
                td.appendChild(inp);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function hasCombinedCourse() {
        if (window.configPackageCourse && window.configPackageCourse.hasCombinedCourse) {
            return window.configPackageCourse.hasCombinedCourse();
        }
        return false;
    }

    /** Live leg start/end/label for combined-course segment rows (package workspace). */
    function resolveLegLabelsForSegment(seg, segIdx) {
        if (!libraryState || !libraryState.chunks || !libraryState.chunks.length) {
            return null;
        }
        var legId = seg && seg.chunk_id != null ? String(seg.chunk_id).trim() : '';
        if (!legId) {
            var segId = seg && seg.seg_id != null ? String(seg.seg_id) : '';
            var m = /^S(\d+)$/i.exec(segId);
            if (m) {
                var ord = parseInt(m[1], 10) - 1;
                if (ord >= 0 && ord < libraryState.chunks.length) {
                    legId = libraryState.chunks[ord].id;
                }
            } else if (segIdx >= 0 && segIdx < libraryState.chunks.length) {
                legId = libraryState.chunks[segIdx].id;
            }
        }
        var ch = libraryState.chunks.find(function (c) { return c.id === legId; });
        if (!ch) return null;
        return {
            from: (ch.start_label || '').trim(),
            to: (ch.end_label || '').trim(),
            seg_label: (ch.leg_label || '').trim()
        };
    }

    function showRecipesModal() {
        var modal = document.getElementById('segment-recipes-modal');
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        renderRecipeTable();
    }

    function closeRecipesModal() {
        var modal = document.getElementById('segment-recipes-modal');
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        recipesModalDismissed = true;
    }

    function syncCoursePanelUi(options) {
        options = options || {};
        var editBtn = document.getElementById('btn-edit-event-recipes');
        var hasCourse = hasCombinedCourse();
        if (editBtn) {
            editBtn.style.display = hasCourse ? '' : 'none';
        }
        var hasLegs = libraryState && libraryState.chunks && libraryState.chunks.length;
        if (
            !hasCourse &&
            hasLegs &&
            !recipesModalDismissed &&
            options.autoOpen !== false
        ) {
            showRecipesModal();
        }
    }

    function loadLibrary() {
        if (!isConfigPackageWorkspace()) {
            showPackageLegsUi(false);
            return Promise.resolve();
        }
        showPackageLegsUi(true);
        return fetch(apiBase() + '/segment-library', { credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                setLegStatus('');
                setRecipeStatus('');
                bindLegMapControls();
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function onCourseTabShown() {
        recipesModalDismissed = false;
        var chain = Promise.resolve();
        if (window.configPackageCourse && window.configPackageCourse.reloadCourse) {
            chain = window.configPackageCourse.reloadCourse();
        }
        return chain
            .then(function () { return loadLibrary(); })
            .then(function () {
                syncCoursePanelUi({ autoOpen: true });
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
                if (selectedLegId === legId) clearLegMap();
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
            direction: 'uni'
        };

        if (title) {
            if (isNew) {
                title.textContent = 'Add leg';
            } else {
                var legLabel = (leg.leg_label || '').trim();
                title.textContent = leg.id + (legLabel ? ': ' + legLabel : '');
            }
        }
        body.innerHTML = '';
        var hint = document.createElement('p');
        hint.style.cssText = 'font-size:0.85rem;color:#7f8c8d;margin:0 0 0.75rem 0;';
        hint.textContent = isNew
            ? 'Set names for this leg. Add locations on the map after saving.'
            : 'Edit metadata here. Add or adjust locations on the map (select the leg, then Add location on map).';
        body.appendChild(hint);

        function segmentSchemaChoices() {
            var raw = window.SEGMENT_SCHEMA_CHOICES_FROM_SERVER || [];
            if (raw.length) return raw.slice();
            return [
                { value: 'on_course_narrow', label: 'Narrow' },
                { value: 'on_course_open', label: 'Open' },
                { value: 'start_corral', label: 'Corral' }
            ];
        }

        function segmentDirectionChoices() {
            var raw = window.SEGMENT_DIRECTION_CHOICES_FROM_SERVER || [];
            if (raw.length) return raw.slice();
            return [{ value: 'uni', label: 'Uni' }, { value: 'bi', label: 'Bi' }];
        }

        function choicesWithCurrent(choices, current) {
            var value = current != null ? String(current).trim() : '';
            if (!value) return choices;
            if (choices.some(function (c) { return String(c.value != null ? c.value : c) === value; })) {
                return choices;
            }
            return choices.concat([{ value: value, label: value + ' (custom)' }]);
        }

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

        function addSelectField(label, id, value, choices) {
            var wrap = document.createElement('div');
            wrap.style.marginBottom = '0.65rem';
            var lab = document.createElement('label');
            lab.textContent = label;
            lab.style.display = 'block';
            lab.style.fontWeight = '600';
            lab.style.fontSize = '0.85rem';
            var sel = document.createElement('select');
            sel.id = id;
            sel.style.width = '100%';
            sel.style.boxSizing = 'border-box';
            var current = value != null ? String(value) : '';
            choicesWithCurrent(choices, current).forEach(function (opt) {
                var o = document.createElement('option');
                o.value = opt.value != null ? opt.value : opt;
                o.textContent = opt.label != null ? opt.label : o.value;
                if (o.value === current) o.selected = true;
                sel.appendChild(o);
            });
            wrap.appendChild(lab);
            wrap.appendChild(sel);
            body.appendChild(wrap);
            return sel;
        }

        addField('Leg label', 'leg-label', leg.leg_label);
        addField('Start place', 'leg-start-label', leg.start_label);
        addField('End place', 'leg-end-label', leg.end_label);
        addField('Width (m)', 'leg-width', leg.width_m, 'number');
        addSelectField('Schema', 'leg-schema', leg.schema || 'on_course_open', segmentSchemaChoices());
        addSelectField('Direction', 'leg-direction', leg.direction || 'uni', segmentDirectionChoices());

        footer.innerHTML = '';
        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'course-btn';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', closeLegEditor);
        var saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'course-btn primary';
        saveBtn.textContent = 'Save leg';
        saveBtn.addEventListener('click', function () { saveLegEditor(); });
        if (!isNew) {
            var gpxBtn = document.createElement('button');
            gpxBtn.type = 'button';
            gpxBtn.className = 'course-btn';
            gpxBtn.textContent = 'Replace GPX…';
            gpxBtn.style.marginRight = 'auto';
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
            footer.appendChild(gpxBtn);
        }
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
            schema: ((document.getElementById('leg-schema') || {}).value || 'on_course_open').trim(),
            direction: ((document.getElementById('leg-direction') || {}).value || 'uni').trim()
        };
    }

    function saveLegEditor() {
        var fields = collectLegFields();
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
                    setLegStatus('Leg added. Select it in the table to view on the map.');
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
                setLegStatus('Imported ' + (payload.data.chunks || []).length + ' leg(s). Select a leg to view on the map.');
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
                closeRecipesModal();
                syncCoursePanelUi({ autoOpen: false });
            })
            .catch(function (err) { setRecipeStatus(err.message || String(err), true); });
    }

    function bindUi() {
        var importBtn = document.getElementById('btn-import-gpx');
        var bulkInput = document.getElementById('segment-library-gpx-input');
        if (importBtn && bulkInput) {
            importBtn.addEventListener('click', function () {
                bulkInput.value = '';
                bulkInput.click();
            });
        }
        if (bulkInput) {
            bulkInput.addEventListener('change', function () {
                uploadGpxBulk(bulkInput.files);
                bulkInput.value = '';
            });
        }
        var addLocBtn = document.getElementById('btn-leg-add-location');
        if (addLocBtn) {
            addLocBtn.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                if (ev.preventDefault) ev.preventDefault();
                if (!selectedLegId) {
                    setLegStatus('Select a leg in the table first.', true);
                    return;
                }
                if (addLocationOnMap) {
                    stopLegLocationPinMode();
                    setLegStatus('');
                    return;
                }
                setTimeout(function () {
                    startLegLocationPinMode();
                }, 0);
            });
        }
        var goRecipes = document.getElementById('btn-go-to-recipes');
        if (goRecipes) {
            goRecipes.addEventListener('click', function () {
                var cid = resolveConfigPackageId();
                if (!cid) return;
                window.location.href = '/config?config_id=' + encodeURIComponent(cid) + '&tab=course';
            });
        }
        var applyBtn = document.getElementById('btn-segment-recipes-apply');
        if (applyBtn) applyBtn.addEventListener('click', saveRecipes);
        var editRecipesBtn = document.getElementById('btn-edit-event-recipes');
        if (editRecipesBtn) {
            editRecipesBtn.addEventListener('click', function () {
                showRecipesModal();
            });
        }
        ['segment-recipes-modal-close', 'segment-recipes-modal-cancel'].forEach(function (id) {
            var btn = document.getElementById(id);
            if (btn) btn.addEventListener('click', closeRecipesModal);
        });
        var recipesBackdrop = document.querySelector(
            '#segment-recipes-modal .course-location-modal-backdrop'
        );
        if (recipesBackdrop) {
            recipesBackdrop.addEventListener('click', closeRecipesModal);
        }
        var closeBtn = document.getElementById('leg-editor-close');
        if (closeBtn) closeBtn.addEventListener('click', closeLegEditor);
        var backdrop = document.querySelector('#leg-editor-modal .course-location-modal-backdrop');
        if (backdrop) backdrop.addEventListener('click', closeLegEditor);
    }

    document.addEventListener('DOMContentLoaded', function () {
        bindUi();
        if (isConfigPackageWorkspace()) {
            loadLibrary().then(function () {
                bindLegMapControls();
            });
        }
    });
    window.addEventListener('popstate', function () {
        if (isConfigPackageWorkspace()) loadLibrary();
        else showPackageLegsUi(false);
    });

    document.addEventListener('segment-recipes-applied', function () {
        syncCoursePanelUi({ autoOpen: false });
    });

    window.segmentRecipes = {
        load: loadLibrary,
        refresh: loadLibrary,
        onCourseTabShown: onCourseTabShown,
        syncCoursePanelUi: syncCoursePanelUi,
        openRecipesModal: showRecipesModal,
        closeRecipesModal: closeRecipesModal,
        resolveLegLabelsForSegment: resolveLegLabelsForSegment,
        onLegsTabShown: function () {
            bindLegMapControls();
            if (window.courseMappingMap) {
                setTimeout(function () {
                    window.courseMappingMap.invalidateSize();
                    bindLegMapControls();
                }, 100);
            }
        }
    };
})();
