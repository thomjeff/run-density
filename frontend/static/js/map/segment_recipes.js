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
    var pendingLegLocations = [];
    var legLocationPreviewLayer = null;
    /** Bumped on each leg selection / clear so stale geometry fetches do not draw extra lines. */
    var legGeometryRequestId = 0;
    var recipesModalDismissed = false;
    var coursePreviewMap = null;
    var coursePreviewLineLayer = null;
    var coursePreviewLocationsLayer = null;
    var coursePreviewSelectedEvent = null;

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

    var LEG_LOCATION_PIN_COLORS = {
        aid: '#e74c3c',
        course: '#27ae60',
        extract: '#9c27b0',
        official: '#f1c40f',
        traffic: '#95a5a6',
        water: '#3498db'
    };

    function locationTypeSnapsToLegRoute(locType) {
        var offCourse = window.OFF_COURSE_LOCATION_TYPES_FROM_SERVER || ['traffic', 'extract'];
        return offCourse.indexOf(String(locType || 'course').toLowerCase()) < 0;
    }

    function legLocationPlacement(locType) {
        return locationTypeSnapsToLegRoute(locType) ? 'along' : 'off';
    }

    function legLocationColor(locType) {
        return LEG_LOCATION_PIN_COLORS[locType] || '#3498db';
    }

    function getSelectedLeg() {
        return (libraryState && libraryState.chunks || []).find(function (c) {
            return c.id === selectedLegId;
        });
    }

    function updateAddLocationButtonLabel() {
        var btn = document.getElementById('btn-leg-add-location');
        if (!btn) return;
        btn.textContent = addLocationOnMap ? 'Save' : 'Add Locations';
    }

    function clearLegLocationPreviewLayer() {
        var map = window.courseMappingMap;
        if (map && legLocationPreviewLayer) {
            map.removeLayer(legLocationPreviewLayer);
            legLocationPreviewLayer = null;
        }
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
            if (still) {
                refreshSelectedLegMap({ preserveZoom: true });
            } else {
                clearLegMap();
            }
        }
        if (
            window.configPackageCourse &&
            window.configPackageCourse.reloadCourse
        ) {
            window.configPackageCourse.reloadCourse({ skipMapRefresh: true });
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
        clearLegLocationPreviewLayer();
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
        pendingLegLocations = [];
        clearLegLocationPreviewLayer();
        updateAddLocationButtonLabel();
        var btn = document.getElementById('btn-leg-add-location');
        if (btn) btn.classList.remove('active');
        var map = window.courseMappingMap;
        if (map && legLocationClickHandler) {
            map.off('click', legLocationClickHandler);
            legLocationClickHandler = null;
        }
    }

    function addLegLocationMarker(loc, group, opts) {
        opts = opts || {};
        if (loc.lat == null || loc.lon == null) return;
        var isPending = !!opts.isPending;
        var fill = legLocationColor(loc.loc_type || 'course');
        var stroke = isPending ? '#2c3e50' : fill;
        var marker = L.marker([loc.lat, loc.lon], {
            icon: L.divIcon({
                className: 'leg-location-pin' + (isPending ? ' leg-location-pin-pending' : ''),
                html:
                    '<div style="width:14px;height:14px;background:' +
                    fill +
                    ';border:2px solid ' +
                    stroke +
                    ';border-radius:50%;box-sizing:border-box;cursor:grab;"></div>',
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            }),
            draggable: true,
            autoPan: true
        });
        var suffix = isPending ? ' (unsaved)' : '';
        if (loc.placement === 'off') suffix += ' (off-course)';
        marker.bindTooltip(
            (loc.loc_label || 'Location') +
                ' (' +
                (loc.loc_type || 'course') +
                ')' +
                suffix +
                ' — drag to move; click to edit'
        );
        marker.on('click', function (e) {
            L.DomEvent.stopPropagation(e);
            if (isPending && opts.pendingIndex != null) {
                openLegLocationPopup({
                    mode: 'edit-pending',
                    loc: loc,
                    pendingIndex: opts.pendingIndex,
                    latlng: marker.getLatLng()
                });
            } else if (!isPending && opts.locIndex != null) {
                openLegLocationPopup({
                    mode: 'edit-saved',
                    loc: loc,
                    locIndex: opts.locIndex,
                    latlng: marker.getLatLng()
                });
            }
        });
        marker.on('mousedown', function (e) {
            L.DomEvent.stopPropagation(e);
        });
        marker.on('dragstart', function () {
            if (window.courseMappingMap) window.courseMappingMap.closePopup();
        });
        marker.on('dragend', function () {
            var ll = marker.getLatLng();
            var coords = finalizeLegLocationCoords(loc, ll.lat, ll.lng);
            loc.lat = coords.lat;
            loc.lon = coords.lon;
            marker.setLatLng([loc.lat, loc.lon]);
            if (isPending) {
                setLegStatus(
                    'Position updated. Drag pins to fine-tune, then click Save when finished.'
                );
                return;
            }
            if (opts.locIndex == null || !selectedLegId) return;
            var leg = getSelectedLeg();
            if (!leg) return;
            var locations = (leg.locations || []).slice();
            if (opts.locIndex < 0 || opts.locIndex >= locations.length) return;
            locations[opts.locIndex] = Object.assign({}, locations[opts.locIndex], coords);
            setLegStatus('Saving position…');
            saveLegLocations(selectedLegId, locations)
                .then(function () {
                    setLegStatus('Location position saved.');
                })
                .catch(function (err) {
                    setLegStatus(err.message || String(err), true);
                });
        });
        marker.addTo(group);
    }

    function finalizeLegLocationCoords(loc, lat, lon) {
        var placeLat = lat;
        var placeLon = lon;
        if (locationTypeSnapsToLegRoute(loc.loc_type) && selectedLegLatLngs) {
            var snapped = snapClickToLegRoute(lat, lon, selectedLegLatLngs);
            placeLat = snapped.lat;
            placeLon = snapped.lon;
        }
        return {
            lat: Math.round(placeLat * 1e6) / 1e6,
            lon: Math.round(placeLon * 1e6) / 1e6
        };
    }

    function applyLegLocationLabelType(loc, locLabel, locType) {
        var updated = Object.assign({}, loc, {
            loc_label: locLabel,
            loc_type: locType,
            placement: legLocationPlacement(locType)
        });
        if (updated.lat != null && updated.lon != null) {
            var coords = finalizeLegLocationCoords(updated, updated.lat, updated.lon);
            updated.lat = coords.lat;
            updated.lon = coords.lon;
        }
        return updated;
    }

    function confirmRemoveLegLocation(label) {
        var subject = (label || 'this location').trim() || 'this location';
        var ta = window.TableActions;
        if (ta && ta.doubleConfirmDelete) {
            return ta.doubleConfirmDelete({
                subject: subject,
                detail: 'This removes the location from the leg and updates the combined course when recipes are applied.'
            });
        }
        return window.confirm('Remove ' + subject + '?');
    }

    function openLegLocationPopup(opts) {
        opts = opts || {};
        var map = window.courseMappingMap;
        if (!map) return;
        var mode = opts.mode || 'add';
        var latlng = opts.latlng;
        if (!latlng) return;

        var content = document.createElement('div');
        content.className = 'course-map-popup';
        content.style.minWidth = '200px';

        var title = document.createElement('p');
        title.style.cssText = 'font-weight:600;margin:0 0 0.65rem 0;color:#2c3e50;font-size:0.95rem;';
        title.textContent =
            mode === 'add'
                ? 'Add location'
                : mode === 'edit-pending'
                  ? 'Edit location (unsaved)'
                  : 'Edit location';
        content.appendChild(title);

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
        var initialType = (opts.loc && opts.loc.loc_type) || 'course';
        locationTypes().forEach(function (t) {
            var opt = document.createElement('option');
            opt.value = t.value;
            opt.textContent = t.label;
            if (t.value === initialType) opt.selected = true;
            sel.appendChild(opt);
        });
        content.appendChild(sel);

        var hint = document.createElement('p');
        hint.style.cssText = 'font-size:0.8rem;color:#7f8c8d;margin:0 0 0.65rem 0;line-height:1.35;';
        function updatePlacementHint() {
            hint.textContent = locationTypeSnapsToLegRoute(sel.value)
                ? 'Snaps to the purple route when saved. Set seg_id on the Course tab if needed.'
                : 'Stays at your click (off-course). Set Proxy loc ID on the Course tab for timing.';
        }
        updatePlacementHint();
        sel.addEventListener('change', updatePlacementHint);
        content.appendChild(hint);

        var lblLabel = document.createElement('label');
        lblLabel.textContent = 'Label';
        lblLabel.style.display = 'block';
        lblLabel.style.marginBottom = '0.25rem';
        content.appendChild(lblLabel);
        var input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'e.g. Water station';
        input.value = (opts.loc && opts.loc.loc_label) || '';
        input.style.display = 'block';
        input.style.width = '100%';
        input.style.marginBottom = '0.65rem';
        input.style.boxSizing = 'border-box';
        content.appendChild(input);

        var btnRow = document.createElement('div');
        btnRow.style.display = 'flex';
        btnRow.style.flexWrap = 'wrap';
        btnRow.style.gap = '0.5rem';
        btnRow.style.alignItems = 'center';

        var btnPrimary = document.createElement('button');
        btnPrimary.type = 'button';
        btnPrimary.className = 'course-btn primary';
        btnPrimary.textContent = mode === 'add' ? 'Add' : 'Save';

        var btnCancel = document.createElement('button');
        btnCancel.type = 'button';
        btnCancel.className = 'course-btn';
        btnCancel.textContent = 'Cancel';

        var btnDelete = null;
        if (mode === 'edit-saved' || mode === 'edit-pending') {
            btnDelete = document.createElement('button');
            btnDelete.type = 'button';
            btnDelete.className = 'course-btn';
            btnDelete.textContent = 'Delete';
            btnDelete.style.marginRight = 'auto';
            btnDelete.style.color = '#c0392b';
            btnDelete.style.borderColor = '#e74c3c';
        }

        if (btnDelete) btnRow.appendChild(btnDelete);
        btnRow.appendChild(btnPrimary);
        btnRow.appendChild(btnCancel);
        content.appendChild(btnRow);

        var pop = L.popup({ maxWidth: 375, className: 'location-popup' })
            .setContent(content)
            .setLatLng(latlng)
            .openOn(map);

        btnCancel.onclick = function () {
            map.closePopup();
        };

        function closeAndRedraw() {
            map.closePopup();
            redrawLegLocationMarkers(getSelectedLeg());
        }

        btnPrimary.onclick = function () {
            var locLabel = (input.value && input.value.trim()) || 'Location';
            var locType = sel.value || 'course';

            if (mode === 'add') {
                var clickLat = opts.clickLat;
                var clickLon = opts.clickLon;
                var placeLat = clickLat;
                var placeLon = clickLon;
                if (locationTypeSnapsToLegRoute(locType)) {
                    var snapped = snapClickToLegRoute(clickLat, clickLon, selectedLegLatLngs);
                    placeLat = snapped.lat;
                    placeLon = snapped.lon;
                }
                pendingLegLocations.push({
                    loc_label: locLabel,
                    loc_type: locType,
                    lat: Math.round(placeLat * 1e6) / 1e6,
                    lon: Math.round(placeLon * 1e6) / 1e6,
                    placement: legLocationPlacement(locType)
                });
                map.closePopup();
                redrawLegLocationMarkers(getSelectedLeg());
                setLegStatus(
                    pendingLegLocations.length === 1
                        ? 'Location added. Drag pins to adjust, add more, or click Save.'
                        : pendingLegLocations.length +
                              ' locations ready. Drag pins to adjust, then Save.'
                );
                return;
            }

            if (mode === 'edit-pending') {
                var pIdx = opts.pendingIndex;
                if (pIdx == null || pIdx < 0 || pIdx >= pendingLegLocations.length) return;
                pendingLegLocations[pIdx] = applyLegLocationLabelType(
                    pendingLegLocations[pIdx],
                    locLabel,
                    locType
                );
                closeAndRedraw();
                setLegStatus('Unsaved location updated.');
                return;
            }

            if (mode === 'edit-saved') {
                var locIndex = opts.locIndex;
                var leg = getSelectedLeg();
                if (!leg || locIndex == null || !selectedLegId) return;
                var locations = (leg.locations || []).slice();
                if (locIndex < 0 || locIndex >= locations.length) return;
                locations[locIndex] = applyLegLocationLabelType(
                    locations[locIndex],
                    locLabel,
                    locType
                );
                setLegStatus('Saving location…');
                saveLegLocations(selectedLegId, locations)
                    .then(function () {
                        closeAndRedraw();
                        setLegStatus('Location updated.');
                    })
                    .catch(function (err) {
                        setLegStatus(err.message || String(err), true);
                    });
            }
        };

        if (btnDelete) {
            btnDelete.onclick = function () {
                var locLabel = (input.value && input.value.trim()) || (opts.loc && opts.loc.loc_label) || 'Location';
                if (!confirmRemoveLegLocation(locLabel)) return;
                map.closePopup();

                if (mode === 'edit-pending') {
                    var pIdx = opts.pendingIndex;
                    if (pIdx == null || pIdx < 0 || pIdx >= pendingLegLocations.length) return;
                    pendingLegLocations.splice(pIdx, 1);
                    redrawLegLocationMarkers(getSelectedLeg());
                    setLegStatus(
                        pendingLegLocations.length
                            ? pendingLegLocations.length + ' unsaved location(s). Click Save when finished.'
                            : 'Location removed. Click the map to add more, or exit Add Locations.'
                    );
                    return;
                }

                var locIndex = opts.locIndex;
                var leg = getSelectedLeg();
                if (!leg || locIndex == null || !selectedLegId) return;
                var locations = (leg.locations || []).slice();
                if (locIndex < 0 || locIndex >= locations.length) return;
                locations.splice(locIndex, 1);
                setLegStatus('Removing location…');
                saveLegLocations(selectedLegId, locations)
                    .then(function () {
                        redrawLegLocationMarkers(getSelectedLeg());
                        setLegStatus('Location removed.');
                    })
                    .catch(function (err) {
                        setLegStatus(err.message || String(err), true);
                    });
            };
        }
    }

    function redrawLegLocationMarkers(leg) {
        var map = window.courseMappingMap;
        if (!map || !leg) return;
        if (legMapLayers.locs) {
            map.removeLayer(legMapLayers.locs);
            legMapLayers.locs = null;
        }
        clearLegLocationPreviewLayer();
        var saved = Array.isArray(leg.locations) ? leg.locations : [];
        if (saved.length || pendingLegLocations.length) {
            var group = L.layerGroup();
            saved.forEach(function (loc, idx) {
                addLegLocationMarker(loc, group, { isPending: false, locIndex: idx });
            });
            legMapLayers.locs = group;
            group.addTo(map);
        }
        if (pendingLegLocations.length) {
            legLocationPreviewLayer = L.layerGroup();
            pendingLegLocations.forEach(function (loc, idx) {
                addLegLocationMarker(loc, legLocationPreviewLayer, {
                    isPending: true,
                    pendingIndex: idx
                });
            });
            legLocationPreviewLayer.addTo(map);
        }
    }

    function fitLegMapBounds(leg) {
        var map = window.courseMappingMap;
        if (!map) return;
        var points = [];
        if (selectedLegLatLngs && selectedLegLatLngs.length >= 2) {
            points.push(selectedLegLatLngs[0]);
            points.push(selectedLegLatLngs[selectedLegLatLngs.length - 1]);
        }
        if (leg) {
            if (leg.start_lat != null && leg.start_lon != null) {
                points.push([leg.start_lat, leg.start_lon]);
            }
            if (leg.end_lat != null && leg.end_lon != null) {
                points.push([leg.end_lat, leg.end_lon]);
            }
            (leg.locations || []).forEach(function (loc) {
                if (loc.lat != null && loc.lon != null) points.push([loc.lat, loc.lon]);
            });
        }
        pendingLegLocations.forEach(function (loc) {
            if (loc.lat != null && loc.lon != null) points.push([loc.lat, loc.lon]);
        });
        if (points.length === 0) return;
        if (points.length === 1) {
            map.setView(points[0], Math.max(map.getZoom(), 14));
            return;
        }
        try {
            map.fitBounds(L.latLngBounds(points), { padding: [48, 48] });
        } catch (e) { /* empty */ }
    }

    function refreshSelectedLegMap(options) {
        options = options || {};
        if (!selectedLegId) return;
        var leg = getSelectedLeg();
        if (!leg) return;
        if (selectedLegLatLngs && selectedLegLatLngs.length >= 2 && legMapLayers.line) {
            redrawLegLocationMarkers(leg);
            if (!options.preserveZoom) {
                fitLegMapBounds(leg);
            }
            return;
        }
        selectLegById(selectedLegId, options);
    }

    function commitPendingLegLocations() {
        if (!selectedLegId) return Promise.resolve();
        var leg = getSelectedLeg();
        if (!leg) return Promise.resolve();
        if (!pendingLegLocations.length) {
            stopLegLocationPinMode();
            setLegStatus('');
            return Promise.resolve();
        }
        var locations = (leg.locations || []).slice().concat(pendingLegLocations);
        setLegStatus('Saving locations…');
        return saveLegLocations(selectedLegId, locations)
            .then(function () {
                pendingLegLocations = [];
                stopLegLocationPinMode();
                refreshSelectedLegMap({ preserveZoom: true });
                setLegStatus(
                    'Locations saved on leg ' +
                        selectedLegId +
                        '. Open the Course tab to assign resources and segment details.'
                );
            });
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
        pendingLegLocations = [];
        window._legLocationPinModeActive = true;
        updateAddLocationButtonLabel();
        var btn = document.getElementById('btn-leg-add-location');
        if (btn) btn.classList.add('active');
        var map = window.courseMappingMap;
        if (!map) return;

        legLocationClickHandler = function (e) {
            if (!addLocationOnMap || !selectedLegId) return;
            L.DomEvent.stopPropagation(e);
            openLegLocationPopup({
                mode: 'add',
                latlng: e.latlng,
                clickLat: e.latlng.lat,
                clickLon: e.latlng.lng
            });
        };
        map.on('click', legLocationClickHandler);
        setLegStatus(
            'Click the map to add locations. Click a pin to edit label/type or delete. ' +
                'Drag pins to move. Course/water/aid/official snap to the route; traffic and extract stay off-course.'
        );
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

    function selectLegById(legId, options) {
        options = options || {};
        var leg = (libraryState && libraryState.chunks || []).find(function (c) {
            return c.id === legId;
        });
        if (!leg) return;
        selectedLegId = legId;
        updateLegActionButtons();
        document.querySelectorAll('#course-legs-tbody tr').forEach(function (tr) {
            tr.classList.toggle('selected', tr.dataset.legId === legId);
        });
        if (!options.keepPinMode) {
            stopLegLocationPinMode();
        }
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
                var currentLeg = getSelectedLeg() || leg;
                legMapLayers.start = endpointMarker(
                    latlngs[0][0], latlngs[0][1],
                    props.start_label || currentLeg.start_label,
                    'start',
                    legId
                );
                legMapLayers.end = endpointMarker(
                    latlngs[latlngs.length - 1][0], latlngs[latlngs.length - 1][1],
                    props.end_label || currentLeg.end_label,
                    'end',
                    legId
                );
                redrawLegLocationMarkers(currentLeg);
                if (!options.preserveZoom) {
                    fitLegMapBounds(currentLeg);
                }
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function selectLeg(leg) {
        if (!leg) return;
        selectLegById(leg.id);
    }

    function exportLeg(legId) {
        var leg = (libraryState && libraryState.chunks || []).find(function (c) {
            return c.id === legId;
        });
        var label = (leg && leg.leg_label) || legId;
        setLegStatus('Preparing export for leg ' + legId + '…');
        fetch(
            apiBase() + '/segment-library/legs/' + encodeURIComponent(legId) + '/export',
            { credentials: 'same-origin' }
        )
            .then(function (r) {
                if (!r.ok) {
                    return r.json().then(function (d) {
                        throw new Error(formatApiError(r, d));
                    });
                }
                var disposition = r.headers.get('Content-Disposition') || '';
                var match = /filename="?([^";]+)"?/i.exec(disposition);
                var filename = (match && match[1]) || legId + '_leg_export.zip';
                return r.blob().then(function (blob) {
                    return { blob: blob, filename: filename };
                });
            })
            .then(function (payload) {
                var url = URL.createObjectURL(payload.blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = payload.filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                setLegStatus('Exported leg ' + legId + ' (' + label + ').');
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
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
                    ta.createIconButton('export', 'Export leg (GPX + metadata + locations)', function (ev) {
                        ev.stopPropagation();
                        exportLeg(ch.id);
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

    function ensureCoursePreviewMap() {
        if (coursePreviewMap) return coursePreviewMap;
        var el = document.getElementById('course-preview-map');
        if (!el || typeof L === 'undefined') return null;
        coursePreviewMap = L.map('course-preview-map', { zoomControl: true }).setView([45.95, -66.64], 13);
        L.tileLayer(
            'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
            { attribution: '© OpenStreetMap contributors, © CARTO', maxZoom: 19 }
        ).addTo(coursePreviewMap);
        return coursePreviewMap;
    }

    function renderCoursePreviewToolbar() {
        var toolbar = document.getElementById('course-preview-event-toolbar');
        if (!toolbar) return;
        toolbar.innerHTML = '';
        packageEvents().forEach(function (eid) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'course-btn' + (coursePreviewSelectedEvent === eid ? ' active' : '');
            btn.textContent = eventColumnLabel(eid);
            btn.addEventListener('click', function () {
                coursePreviewSelectedEvent = eid;
                renderCoursePreviewToolbar();
                loadCoursePreviewRoute(eid);
            });
            toolbar.appendChild(btn);
        });
    }

    function clearCoursePreviewLocationsLayer(map) {
        if (!map || !coursePreviewLocationsLayer) return;
        map.removeLayer(coursePreviewLocationsLayer);
        coursePreviewLocationsLayer = null;
    }

    function renderCoursePreviewLocations() {
        var map = ensureCoursePreviewMap();
        if (!map) return;
        clearCoursePreviewLocationsLayer(map);
        var pkg = window.configPackageCourse;
        if (!pkg || !pkg.getCourseLocations) return;
        var locs = pkg.getCourseLocations();
        if (!locs.length) return;
        var buildTip = pkg.buildLocationTooltipHtml;
        var pinColor = pkg.getLocationPinColor;
        coursePreviewLocationsLayer = L.featureGroup();
        locs.forEach(function (loc, i) {
            var lat = typeof loc.lat === 'number' ? loc.lat : parseFloat(loc.lat);
            var lon = typeof loc.lon === 'number' ? loc.lon : parseFloat(loc.lon);
            if (isNaN(lat) || isNaN(lon)) return;
            var fill = pinColor ? pinColor(loc.loc_type) : '#27ae60';
            var marker = L.marker([lat, lon], {
                icon: L.divIcon({
                    className: 'location-pin-circle',
                    html:
                        '<div style="width:14px;height:14px;background:' +
                        fill +
                        ';border:2px solid ' +
                        fill +
                        ';border-radius:50%;box-sizing:border-box;"></div>',
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                }),
                interactive: true
            });
            marker._locationIndex = i;
            if (buildTip) {
                marker.bindTooltip(buildTip(loc, i), {
                    permanent: false,
                    direction: 'top',
                    offset: [0, -10],
                    className: 'course-map-tooltip'
                });
            }
            marker.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                if (pkg.highlightLocationInTable) {
                    pkg.highlightLocationInTable(i);
                }
                var rows = document.querySelectorAll('#locations-tbody tr:not(.locations-totals-row)');
                if (rows[i]) {
                    rows[i].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                }
            });
            coursePreviewLocationsLayer.addLayer(marker);
        });
        if (coursePreviewLocationsLayer.getLayers().length) {
            coursePreviewLocationsLayer.addTo(map);
        } else {
            coursePreviewLocationsLayer = null;
        }
    }

    function loadCoursePreviewRoute(eventId) {
        var wrap = document.getElementById('course-preview-map-wrap');
        var meta = document.getElementById('course-preview-meta');
        var empty = document.getElementById('course-preview-empty');
        if (!eventId || !hasCombinedCourse()) return;
        fetch(
            apiBase() + '/segment-library/events/' + encodeURIComponent(eventId) + '/preview',
            { credentials: 'same-origin' }
        )
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                var data = payload.data;
                var map = ensureCoursePreviewMap();
                if (!map) return;
                if (coursePreviewLineLayer) {
                    map.removeLayer(coursePreviewLineLayer);
                    coursePreviewLineLayer = null;
                }
                clearCoursePreviewLocationsLayer(map);
                var latlngs = (data.coordinates || []).map(function (c) { return [c[1], c[0]]; });
                if (latlngs.length < 2) throw new Error('Route has too few points');
                coursePreviewLineLayer = L.polyline(latlngs, {
                    color: '#2563eb',
                    weight: 5,
                    opacity: 0.92
                }).addTo(map);
                renderCoursePreviewLocations();
                var bounds = coursePreviewLineLayer.getBounds();
                if (coursePreviewLocationsLayer) {
                    bounds = bounds.extend(coursePreviewLocationsLayer.getBounds());
                }
                map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
                if (wrap) wrap.style.display = 'block';
                if (empty) empty.style.display = 'none';
                if (meta) {
                    meta.style.display = 'block';
                    meta.textContent =
                        eventColumnLabel(eventId) +
                        ': ' +
                        Number(data.length_km).toFixed(2) +
                        ' km · ' +
                        (data.leg_count || 0) +
                        ' legs';
                }
                setTimeout(function () { map.invalidateSize(); }, 120);
            })
            .catch(function (err) {
                var map = coursePreviewMap;
                if (map) clearCoursePreviewLocationsLayer(map);
                if (empty) {
                    empty.style.display = 'block';
                    empty.textContent = err.message || String(err);
                }
                if (wrap) wrap.style.display = 'none';
                if (meta) meta.style.display = 'none';
            });
    }

    function syncCoursePreviewUi() {
        var section = document.getElementById('course-preview-section');
        var empty = document.getElementById('course-preview-empty');
        var wrap = document.getElementById('course-preview-map-wrap');
        var meta = document.getElementById('course-preview-meta');
        if (!section) return;
        if (!hasCombinedCourse()) {
            section.style.display = 'none';
            return;
        }
        section.style.display = 'block';
        if (empty) {
            empty.style.display = 'block';
            empty.textContent = 'Select an event to preview its stitched route.';
        }
        var events = packageEvents();
        if (!coursePreviewSelectedEvent || events.indexOf(coursePreviewSelectedEvent) < 0) {
            coursePreviewSelectedEvent = events.length ? events[0] : null;
        }
        renderCoursePreviewToolbar();
        if (!coursePreviewSelectedEvent) {
            if (wrap) wrap.style.display = 'none';
            if (meta) meta.style.display = 'none';
            return;
        }
        loadCoursePreviewRoute(coursePreviewSelectedEvent);
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
        syncCoursePreviewUi();
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
                syncCoursePreviewUi();
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
            : 'Edit metadata here. Add or adjust locations on the map (select the leg, then Add Locations).';
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
        var hasJson = false;
        for (var j = 0; j < files.length; j++) {
            var n = (files[j].name || '').toLowerCase();
            if (n.endsWith('.json')) hasJson = true;
        }
        setLegStatus('Importing leg file' + (files.length > 1 ? 's' : '') + '…');
        fetch(apiBase() + '/segment-library/upload', { method: 'POST', credentials: 'same-origin', body: fd })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                applyLibraryState(payload.data);
                var count = (payload.data.chunks || []).length;
                var msg =
                    'Imported ' +
                    count +
                    ' leg(s). Select a leg to view on the map.';
                if (!hasJson) {
                    msg +=
                        ' Tip: include the .json from a leg export zip to restore locations and metadata.';
                }
                setLegStatus(msg);
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
                    var status = 'Exported ' + (data.apply.segment_count || 0) + ' segments';
                    if (data.apply.flow_csv_path) status += ', flow.csv';
                    var gpxCount = (data.apply.gpx_files || []).length;
                    if (gpxCount) status += ', ' + gpxCount + ' GPX file(s)';
                    setRecipeStatus(status + '.');
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
                    commitPendingLegLocations().catch(function (err) {
                        setLegStatus(err.message || String(err), true);
                    });
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
        syncCoursePreviewUi();
    });

    window.segmentRecipes = {
        load: loadLibrary,
        refresh: loadLibrary,
        onCourseTabShown: onCourseTabShown,
        syncCoursePanelUi: syncCoursePanelUi,
        renderCoursePreviewLocations: renderCoursePreviewLocations,
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
