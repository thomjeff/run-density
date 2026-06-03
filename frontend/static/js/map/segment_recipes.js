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
    var legReshapeActive = false;
    var legReshapeDraftLatLngs = null;
    var legReshapeAnchorIndices = null;
    var legReshapeAnchorLayer = null;
    var legReshapeSavedLatLngs = null;
    var legTrimActive = false;
    var legTrimSavedLatLngs = null;
    var legTrimStartIdx = 0;
    var legTrimEndIdx = 0;
    var legTrimGhostLayer = null;
    var legTrimMarkerLayer = null;
    var legBoundsCache = {};
    var legsTableBoundsFilter = null;
    var coursePreviewBoundsFilter = null;

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

    function flowTypeLabelForValue(value) {
        var v = String(value || 'none');
        var raw = window.FLOW_TYPE_CHOICES_FROM_SERVER || [];
        var found = raw.find(function (c) { return String(c.value) === v; });
        if (found && found.label) return found.label;
        return v;
    }

    function flowTypeChoices() {
        var raw = window.FLOW_TYPE_CHOICES_FROM_SERVER || [];
        if (raw.length) return raw.slice();
        return [
            { value: 'overtake', label: 'Overtake' },
            { value: 'merge', label: 'Merge' },
            { value: 'counterflow', label: 'Counterflow' },
            { value: 'parallel', label: 'Parallel' },
            { value: 'none', label: 'None' }
        ];
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

    function getOrder(legId, eventId) {
        var row = orderGrid[eventId] || {};
        var v = row[legId];
        return v == null || v === '' ? '' : String(v);
    }

    function setOrder(legId, eventId, value) {
        if (!orderGrid[eventId]) orderGrid[eventId] = {};
        var trimmed = String(value || '').trim();
        if (!trimmed) orderGrid[eventId][legId] = null;
        else {
            var n = parseInt(trimmed, 10);
            orderGrid[eventId][legId] = isNaN(n) || n < 1 ? null : n;
        }
        recomputeTotalsLocal();
    }

    function recomputeTotalsLocal() {
        if (!libraryState || !libraryState.legs) return;
        var lengths = {};
        packageEvents().forEach(function (ev) { lengths[ev] = 0; });
        packageEvents().forEach(function (ev) {
            var pairs = [];
            libraryState.legs.forEach(function (ch) {
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

    function locationTypeSnapsToLegRoute(locType, placement) {
        if (String(placement || '').toLowerCase() === 'off') {
            return false;
        }
        var noSnap =
            window.LEG_MAP_NO_SNAP_LOCATION_TYPES_FROM_SERVER ||
            window.OFF_COURSE_LOCATION_TYPES_FROM_SERVER ||
            ['traffic', 'extract', 'aid'];
        return noSnap.indexOf(String(locType || 'course').toLowerCase()) < 0;
    }

    function resolveLegLocationRecord(loc, opts, isPending) {
        if (isPending && opts.pendingIndex != null && pendingLegLocations[opts.pendingIndex]) {
            return pendingLegLocations[opts.pendingIndex];
        }
        if (opts.locIndex != null) {
            var leg = getSelectedLeg();
            if (leg && leg.locations && leg.locations[opts.locIndex]) {
                return leg.locations[opts.locIndex];
            }
        }
        return loc;
    }

    function legLocationPlacement(locType) {
        return locationTypeSnapsToLegRoute(locType) ? 'along' : 'off';
    }

    function legLocationColor(locType) {
        return LEG_LOCATION_PIN_COLORS[locType] || '#3498db';
    }

    function getSelectedLeg() {
        return (libraryState && libraryState.legs || []).find(function (c) {
            return c.id === selectedLegId;
        });
    }

    function updateLegsMapBoundsStatus(visible, total) {
        var el = document.getElementById('leg-map-bounds-status');
        if (!el) return;
        if (!total) {
            el.textContent = '';
            return;
        }
        if (visible >= total) {
            el.textContent = 'Showing all ' + total + ' legs';
        } else {
            el.textContent = 'Showing ' + visible + ' of ' + total + ' legs in map view';
        }
    }

    function updateCoursePreviewBoundsStatus(segVisible, segTotal, locVisible, locTotal) {
        var el = document.getElementById('course-preview-bounds-status');
        if (!el) return;
        if (!segTotal && !locTotal) {
            el.textContent = '';
            return;
        }
        var parts = [];
        if (segTotal) {
            parts.push(
                segVisible >= segTotal
                    ? 'All ' + segTotal + ' segments'
                    : segVisible + ' of ' + segTotal + ' segments'
            );
        }
        if (locTotal) {
            parts.push(
                locVisible >= locTotal
                    ? 'all ' + locTotal + ' locations'
                    : locVisible + ' of ' + locTotal + ' locations'
            );
        }
        el.textContent = 'Map view: ' + parts.join(' · ');
    }

    function legIntersectsBounds(leg, bounds) {
        if (!leg || !bounds || !bounds.isValid()) return false;
        var cached = legBoundsCache[leg.id];
        if (cached && cached.isValid && cached.isValid()) {
            return bounds.intersects(cached);
        }
        function hasPt(lat, lon) {
            var la = parseFloat(lat);
            var lo = parseFloat(lon);
            return !isNaN(la) && !isNaN(lo) && bounds.contains([la, lo]);
        }
        if (hasPt(leg.start_lat, leg.start_lon) || hasPt(leg.end_lat, leg.end_lon)) return true;
        var locs = leg.locations || [];
        for (var i = 0; i < locs.length; i++) {
            if (hasPt(locs[i].lat, locs[i].lon)) return true;
        }
        return false;
    }

    function initLegsTableBoundsFilter() {
        if (!window.MapBoundsTableFilter || legsTableBoundsFilter) return;
        legsTableBoundsFilter = window.MapBoundsTableFilter.create({
            getMap: function () { return window.courseMappingMap; },
            isItemInBounds: function (leg, bounds) {
                return legIntersectsBounds(leg, bounds);
            },
            onFilter: function (visible, stats) {
                renderLegsTable(visible);
                updateLegsMapBoundsStatus(stats.visible, stats.total);
            }
        });
    }

    function syncLegsTableBoundsFilterItems() {
        initLegsTableBoundsFilter();
        if (!legsTableBoundsFilter) return;
        legsTableBoundsFilter.setAllItems((libraryState && libraryState.legs) || []);
    }

    function attachLegsTableBoundsFilter() {
        initLegsTableBoundsFilter();
        if (!legsTableBoundsFilter) return;
        var map = window.courseMappingMap;
        if (map) {
            legsTableBoundsFilter.attach(map);
            syncLegsTableBoundsFilterItems();
        }
    }

    function fitLegMapToAllLegs() {
        var map = window.courseMappingMap;
        var legs = (libraryState && libraryState.legs) || [];
        if (!map || !legs.length || selectedLegId) return;
        var points = [];
        legs.forEach(function (leg) {
            if (leg.start_lat != null && leg.start_lon != null) {
                points.push([leg.start_lat, leg.start_lon]);
            }
            if (leg.end_lat != null && leg.end_lon != null) {
                points.push([leg.end_lat, leg.end_lon]);
            }
        });
        if (points.length < 2) return;
        function doFit() {
            try {
                map.fitBounds(L.latLngBounds(points), { padding: [48, 48], maxZoom: 14 });
            } catch (e) { /* empty */ }
        }
        if (legsTableBoundsFilter) {
            legsTableBoundsFilter.runProgrammatic(doFit);
        } else {
            doFit();
        }
    }

    function resolveLegIdForSegment(seg, segIdx) {
        if (!libraryState || !libraryState.legs || !libraryState.legs.length) return '';
        var legId = seg && (seg.leg_id != null || seg.chunk_id != null)
            ? String(seg.leg_id != null ? seg.leg_id : seg.chunk_id).trim()
            : '';
        if (!legId) {
            var segId = seg && seg.seg_id != null ? String(seg.seg_id) : '';
            var m = /^S(\d+)$/i.exec(segId);
            if (m) {
                var ord = parseInt(m[1], 10) - 1;
                if (ord >= 0 && ord < libraryState.legs.length) {
                    legId = libraryState.legs[ord].id;
                }
            } else if (segIdx >= 0 && segIdx < libraryState.legs.length) {
                legId = libraryState.legs[segIdx].id;
            }
        }
        return legId;
    }

    function activePreviewEventId() {
        if (coursePreviewSelectedEvent) return coursePreviewSelectedEvent;
        var evs = packageEvents();
        return evs.length ? evs[0] : null;
    }

    function flattenPreviewLatLngs(layer) {
        if (!layer) return [];
        var latlngs = layer.getLatLngs();
        if (!latlngs || !latlngs.length) return [];
        if (latlngs[0] && latlngs[0].lat != null) return latlngs;
        var flat = [];
        latlngs.forEach(function (part) {
            if (Array.isArray(part)) {
                part.forEach(function (ll) {
                    flat.push(ll);
                });
            }
        });
        return flat;
    }

    function haversineKm(a, b) {
        var R = 6371;
        var dLat = ((b.lat - a.lat) * Math.PI) / 180;
        var dLon = ((b.lng - a.lng) * Math.PI) / 180;
        var lat1 = (a.lat * Math.PI) / 180;
        var lat2 = (b.lat * Math.PI) / 180;
        var x =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
    }

    function buildRouteKmTable(latlngs) {
        var cum = [0];
        for (var i = 1; i < latlngs.length; i++) {
            cum.push(cum[i - 1] + haversineKm(latlngs[i - 1], latlngs[i]));
        }
        return cum;
    }

    function latLngAtRouteKm(latlngs, cum, km) {
        if (!latlngs.length) return null;
        if (km <= 0) return latlngs[0];
        var total = cum[cum.length - 1];
        if (km >= total) return latlngs[latlngs.length - 1];
        for (var i = 1; i < cum.length; i++) {
            if (cum[i] >= km) {
                var segLen = cum[i] - cum[i - 1];
                var t = segLen > 0 ? (km - cum[i - 1]) / segLen : 0;
                var a = latlngs[i - 1];
                var b = latlngs[i];
                return L.latLng(a.lat + (b.lat - a.lat) * t, a.lng + (b.lng - a.lng) * t);
            }
        }
        return latlngs[latlngs.length - 1];
    }

    function segmentIntersectsPreviewRoute(seg, bounds) {
        if (!coursePreviewLineLayer || !seg || !bounds || !bounds.isValid()) return false;
        var eventId = activePreviewEventId();
        if (!eventId) return false;
        var el = String(eventId).toLowerCase();
        var fromKm = parseFloat(seg[el + '_from_km']);
        var toKm = parseFloat(seg[el + '_to_km']);
        if (isNaN(fromKm) || isNaN(toKm) || toKm <= fromKm) return false;
        var latlngs = flattenPreviewLatLngs(coursePreviewLineLayer);
        if (latlngs.length < 2) return false;
        var cum = buildRouteKmTable(latlngs);
        var span = toKm - fromKm;
        var steps = Math.max(2, Math.min(20, Math.ceil(span * 5)));
        for (var s = 0; s <= steps; s++) {
            var km = fromKm + (span * s) / steps;
            var ll = latLngAtRouteKm(latlngs, cum, km);
            if (ll && bounds.contains(ll)) return true;
        }
        return false;
    }

    function segmentIntersectsBounds(seg, bounds, segIdx) {
        if (!seg || !bounds || !bounds.isValid()) return false;
        if (segmentIntersectsPreviewRoute(seg, bounds)) return true;
        var legId = resolveLegIdForSegment(seg, segIdx != null ? segIdx : -1);
        if (legId && libraryState && libraryState.legs) {
            var leg = libraryState.legs.find(function (c) {
                return c.id === legId;
            });
            if (leg && legIntersectsBounds(leg, bounds)) return true;
        }
        if (coursePreviewLineLayer && seg.start_index != null && seg.end_index != null) {
            var flat = flattenPreviewLatLngs(coursePreviewLineLayer);
            var lo = Math.min(seg.start_index, seg.end_index);
            var hi = Math.max(seg.start_index, seg.end_index);
            for (var i = lo; i <= hi && i < flat.length; i++) {
                if (bounds.contains(flat[i])) return true;
            }
        }
        return false;
    }

    function buildCoursePreviewBoundsItems() {
        var items = [];
        var pkg = window.configPackageCourse;
        if (!pkg || !pkg.getCourse) return items;
        var course = pkg.getCourse();
        if (!course) return items;
        (course.segments || []).forEach(function (seg, i) {
            items.push({ kind: 'segment', index: i, data: seg });
        });
        (course.locations || []).forEach(function (loc, i) {
            items.push({ kind: 'location', index: i, data: loc });
        });
        return items;
    }

    function applyCoursePreviewBoundsToTables(visibleItems, stats) {
        var segIndices = [];
        var locIndices = [];
        var segTotal = 0;
        var locTotal = 0;
        var pkg = window.configPackageCourse;
        if (pkg && pkg.getCourse) {
            var course = pkg.getCourse();
            if (course) {
                segTotal = (course.segments || []).length;
                locTotal = (course.locations || []).length;
            }
        }
        (visibleItems || []).forEach(function (item) {
            if (item.kind === 'segment') segIndices.push(item.index);
            else if (item.kind === 'location') locIndices.push(item.index);
        });
        if (pkg) {
            if (pkg.renderSegmentsListFiltered) pkg.renderSegmentsListFiltered(segIndices);
            if (pkg.renderLocationsListFiltered) pkg.renderLocationsListFiltered(locIndices);
        }
        updateCoursePreviewBoundsStatus(segIndices.length, segTotal, locIndices.length, locTotal);
    }

    function initCoursePreviewBoundsFilter() {
        if (!window.MapBoundsTableFilter || coursePreviewBoundsFilter) return;
        coursePreviewBoundsFilter = window.MapBoundsTableFilter.create({
            getMap: function () { return coursePreviewMap; },
            isItemInBounds: function (item, bounds) {
                if (item.kind === 'location') {
                    var lat = parseFloat(item.data.lat);
                    var lon = parseFloat(item.data.lon);
                    return !isNaN(lat) && !isNaN(lon) && bounds.contains([lat, lon]);
                }
                return segmentIntersectsBounds(item.data, bounds, item.index);
            },
            onFilter: function (visible, stats) {
                applyCoursePreviewBoundsToTables(visible, stats);
            }
        });
    }

    function syncCoursePreviewBoundsFilterItems() {
        initCoursePreviewBoundsFilter();
        if (!coursePreviewBoundsFilter) return;
        coursePreviewBoundsFilter.setAllItems(buildCoursePreviewBoundsItems());
    }

    function attachCoursePreviewBoundsFilter() {
        initCoursePreviewBoundsFilter();
        if (!coursePreviewBoundsFilter) return;
        var map = ensureCoursePreviewMap();
        if (map) {
            coursePreviewBoundsFilter.attach(map);
            syncCoursePreviewBoundsFilterItems();
        }
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
        syncLegsTableBoundsFilterItems();
        renderRecipeTable();
        renderTotals(data.recipe_lengths_km);
        renderWarnings(data.stitch_warnings);
        if (selectedLegId) {
            var still = (data.legs || []).some(function (c) { return c.id === selectedLegId; });
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

    function isLegRouteEditActive() {
        return legReshapeActive || legTrimActive;
    }

    function updateLegActionButtons() {
        var hasLeg = !!selectedLegId;
        var hasLine = !!(selectedLegLatLngs && selectedLegLatLngs.length >= 2);
        var routeEditActive = isLegRouteEditActive();
        var reshapeBtn = document.getElementById('btn-leg-reshape-route');
        var trimBtn = document.getElementById('btn-leg-trim-route');
        var addLocBtn = document.getElementById('btn-leg-add-location');
        var routeEditActions = document.getElementById('leg-route-edit-actions');
        if (reshapeBtn) {
            reshapeBtn.style.display = routeEditActive ? 'none' : '';
            reshapeBtn.disabled = !hasLeg || !hasLine || legTrimActive;
            reshapeBtn.title = !hasLeg
                ? 'Select a leg in the table first'
                : !hasLine
                  ? 'Loading route on the map…'
                  : 'Simplify the route and drag yellow anchors to nudge the track (e.g. off a sidewalk)';
        }
        if (trimBtn) {
            trimBtn.style.display = routeEditActive ? 'none' : '';
            trimBtn.disabled = !hasLeg || !hasLine || legReshapeActive;
            trimBtn.title = !hasLeg
                ? 'Select a leg in the table first'
                : !hasLine
                  ? 'Loading route on the map…'
                  : 'Drag the green or red end along the route to shorten the leg';
        }
        if (routeEditActions) {
            routeEditActions.style.display = routeEditActive ? 'inline-flex' : 'none';
        }
        if (addLocBtn) {
            addLocBtn.disabled = !hasLeg || routeEditActive;
        }
    }

    function copyLatLngs(latlngs) {
        return (latlngs || []).map(function (ll) {
            return [ll[0], ll[1]];
        });
    }

    /** Douglas–Peucker tolerance (m) when entering reshape — PlotARoute-style semantic vertices. */
    var LEG_RESHAPE_SIMPLIFY_TOLERANCE_M = 5;
    var LEG_RESHAPE_SIMPLIFY_MAX_VERTICES = 96;

    function perpendicularDistanceMeters(point, lineStart, lineEnd) {
        var midLat = (lineStart[0] + lineEnd[0]) / 2;
        var metersPerDegLat = 111320;
        var metersPerDegLon = 111320 * Math.cos((midLat * Math.PI) / 180);
        var ax = (lineEnd[1] - lineStart[1]) * metersPerDegLon;
        var ay = (lineEnd[0] - lineStart[0]) * metersPerDegLat;
        var px = (point[1] - lineStart[1]) * metersPerDegLon;
        var py = (point[0] - lineStart[0]) * metersPerDegLat;
        var lenSq = ax * ax + ay * ay;
        if (lenSq < 1e-6) {
            return Math.sqrt(px * px + py * py);
        }
        var t = Math.max(0, Math.min(1, (px * ax + py * ay) / lenSq));
        var dx = px - t * ax;
        var dy = py - t * ay;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function douglasPeuckerKeepMask(latlngs, startIdx, endIdx, toleranceM, keep) {
        if (endIdx <= startIdx + 1) {
            return;
        }
        var maxDist = 0;
        var maxIdx = startIdx;
        var lineStart = latlngs[startIdx];
        var lineEnd = latlngs[endIdx];
        var i;
        for (i = startIdx + 1; i < endIdx; i++) {
            var dist = perpendicularDistanceMeters(latlngs[i], lineStart, lineEnd);
            if (dist > maxDist) {
                maxDist = dist;
                maxIdx = i;
            }
        }
        if (maxDist > toleranceM) {
            keep[maxIdx] = true;
            douglasPeuckerKeepMask(latlngs, startIdx, maxIdx, toleranceM, keep);
            douglasPeuckerKeepMask(latlngs, maxIdx, endIdx, toleranceM, keep);
        }
    }

    function douglasPeuckerSimplify(latlngs, toleranceM) {
        if (!latlngs || latlngs.length < 2) {
            return [];
        }
        if (latlngs.length === 2) {
            return copyLatLngs(latlngs);
        }
        var keep = { 0: true };
        keep[latlngs.length - 1] = true;
        douglasPeuckerKeepMask(latlngs, 0, latlngs.length - 1, toleranceM, keep);
        var out = [];
        var idx;
        for (idx = 0; idx < latlngs.length; idx++) {
            if (keep[idx]) {
                out.push([latlngs[idx][0], latlngs[idx][1]]);
            }
        }
        return out;
    }

    /** Simplify dense GPX to editable corners; relax tolerance if still too many vertices. */
    function simplifyLegRouteForReshape(latlngs) {
        if (!latlngs || latlngs.length < 3) {
            return { latlngs: copyLatLngs(latlngs || []), toleranceM: LEG_RESHAPE_SIMPLIFY_TOLERANCE_M };
        }
        var toleranceM = LEG_RESHAPE_SIMPLIFY_TOLERANCE_M;
        var simplified = douglasPeuckerSimplify(latlngs, toleranceM);
        var attempts = 0;
        while (
            simplified.length > LEG_RESHAPE_SIMPLIFY_MAX_VERTICES &&
            toleranceM < 40 &&
            attempts < 12
        ) {
            toleranceM = Math.round(toleranceM * 1.35 * 10) / 10;
            simplified = douglasPeuckerSimplify(latlngs, toleranceM);
            attempts += 1;
        }
        return { latlngs: simplified, toleranceM: toleranceM };
    }

    function allVertexAnchorIndices(vertexCount) {
        var indices = [];
        var i;
        for (i = 0; i < vertexCount; i++) {
            indices.push(i);
        }
        return indices;
    }

    function getActiveLegLatLngs() {
        if (legTrimActive && legTrimSavedLatLngs) {
            return getLegTrimDraftLatLngs();
        }
        if (legReshapeActive && legReshapeDraftLatLngs) {
            return legReshapeDraftLatLngs;
        }
        return selectedLegLatLngs;
    }

    function setLegRoutePolyline(latlngs) {
        var map = window.courseMappingMap;
        if (!map || !latlngs || latlngs.length < 2) {
            return;
        }
        if (legMapLayers.line) {
            map.removeLayer(legMapLayers.line);
        }
        legMapLayers.line = L.polyline(latlngs, {
            color: '#8e44ad',
            weight: 5,
            opacity: 0.85
        }).addTo(map);
    }

    function clearLegReshapeAnchorLayer() {
        var map = window.courseMappingMap;
        if (map && legReshapeAnchorLayer) {
            map.removeLayer(legReshapeAnchorLayer);
            legReshapeAnchorLayer = null;
        }
    }

    function drawLegReshapeAnchors() {
        var map = window.courseMappingMap;
        var latlngs = legReshapeDraftLatLngs;
        if (!map || !latlngs || !legReshapeAnchorIndices) {
            return;
        }
        clearLegReshapeAnchorLayer();
        legReshapeAnchorLayer = L.layerGroup();
        legReshapeAnchorIndices.forEach(function (idx) {
            if (idx < 0 || idx >= latlngs.length) {
                return;
            }
            var ll = latlngs[idx];
            var marker = L.marker([ll[0], ll[1]], {
                icon: L.divIcon({
                    className: 'leg-route-anchor-pin',
                    html: '<div></div>',
                    iconSize: [13, 13],
                    iconAnchor: [6, 6]
                }),
                draggable: true,
                autoPan: true,
                zIndexOffset: 800
            });
            marker.on('drag', function () {
                var pos = marker.getLatLng();
                legReshapeDraftLatLngs[idx] = [
                    Math.round(pos.lat * 1e6) / 1e6,
                    Math.round(pos.lng * 1e6) / 1e6
                ];
                selectedLegLatLngs = legReshapeDraftLatLngs;
                setLegRoutePolyline(legReshapeDraftLatLngs);
            });
            marker.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
            });
            marker.addTo(legReshapeAnchorLayer);
        });
        legReshapeAnchorLayer.addTo(map);
    }

    function stopLegReshapeRoute(discard) {
        if (!legReshapeActive && !legReshapeDraftLatLngs) {
            return;
        }
        legReshapeActive = false;
        if (discard && legReshapeSavedLatLngs) {
            selectedLegLatLngs = copyLatLngs(legReshapeSavedLatLngs);
            setLegRoutePolyline(selectedLegLatLngs);
        }
        legReshapeDraftLatLngs = null;
        legReshapeAnchorIndices = null;
        legReshapeSavedLatLngs = null;
        clearLegReshapeAnchorLayer();
        updateLegActionButtons();
        var reshapeBtn = document.getElementById('btn-leg-reshape-route');
        if (reshapeBtn) {
            reshapeBtn.classList.remove('active');
        }
    }

    function startLegReshapeRoute() {
        if (!selectedLegId) {
            setLegStatus('Select a leg in the table first.', true);
            return;
        }
        if (!selectedLegLatLngs || selectedLegLatLngs.length < 2) {
            setLegStatus('Wait for the leg route to load on the map.', true);
            return;
        }
        stopLegTrimRoute(true);
        if (addLocationOnMap) {
            if (!pendingLegLocations.length) {
                stopLegLocationPinMode();
            } else {
                setLegStatus('Save or cancel pending locations before reshaping the route.', true);
                return;
            }
        }
        stopLegReshapeRoute(true);
        var originalCount = selectedLegLatLngs.length;
        legReshapeSavedLatLngs = copyLatLngs(selectedLegLatLngs);
        var simplified = simplifyLegRouteForReshape(legReshapeSavedLatLngs);
        legReshapeDraftLatLngs = simplified.latlngs;
        legReshapeAnchorIndices = allVertexAnchorIndices(legReshapeDraftLatLngs.length);
        legReshapeActive = true;
        setLegRoutePolyline(legReshapeDraftLatLngs);
        var reshapeBtn = document.getElementById('btn-leg-reshape-route');
        if (reshapeBtn) {
            reshapeBtn.classList.add('active');
        }
        updateLegActionButtons();
        drawLegReshapeAnchors();
        var anchorCount = legReshapeAnchorIndices.length;
        var statusMsg =
            'Route simplified to ' +
            anchorCount +
            ' anchor' +
            (anchorCount === 1 ? '' : 's') +
            ' (from ' +
            originalCount +
            ' track points). Drag yellow pins to nudge; Confirm saves this shape, Cancel restores the original.';
        if (originalCount > anchorCount && simplified.toleranceM > LEG_RESHAPE_SIMPLIFY_TOLERANCE_M) {
            statusMsg +=
                ' (used ' + simplified.toleranceM + ' m simplify tolerance to keep the map usable).';
        }
        setLegStatus(statusMsg);
    }

    function confirmLegReshapeRoute() {
        if (!legReshapeActive || !selectedLegId || !legReshapeDraftLatLngs) {
            return;
        }
        var coordinates = legReshapeDraftLatLngs.map(function (ll) {
            return [ll[1], ll[0]];
        });
        setLegStatus('Saving route…');
        fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(selectedLegId) + '/geometry', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coordinates: coordinates })
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { res: r, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.res.ok) {
                    throw new Error(formatApiError(payload.res, payload.data));
                }
                applyLibraryState(payload.data);
                legReshapeActive = false;
                legReshapeDraftLatLngs = null;
                legReshapeAnchorIndices = null;
                legReshapeSavedLatLngs = null;
                clearLegReshapeAnchorLayer();
                updateLegActionButtons();
                var reshapeBtn = document.getElementById('btn-leg-reshape-route');
                if (reshapeBtn) {
                    reshapeBtn.classList.remove('active');
                }
                selectLegById(selectedLegId, { preserveZoom: true, keepPinMode: true });
                setLegStatus('Route saved for leg ' + selectedLegId + '.');
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function getLegTrimDraftLatLngs() {
        if (!legTrimSavedLatLngs || legTrimEndIdx < legTrimStartIdx) {
            return [];
        }
        return legTrimSavedLatLngs.slice(legTrimStartIdx, legTrimEndIdx + 1);
    }

    function closestVertexIndexOnRoute(lat, lon, latlngs, minIdx, maxIdx) {
        if (!latlngs || latlngs.length < 2) {
            return minIdx;
        }
        minIdx = Math.max(0, minIdx);
        maxIdx = Math.min(latlngs.length - 1, maxIdx);
        if (maxIdx < minIdx) {
            return minIdx;
        }
        var snapped = snapClickToLegRoute(lat, lon, latlngs);
        var bestIdx = minIdx;
        var bestD = Infinity;
        var i;
        for (i = minIdx; i <= maxIdx; i++) {
            var dlat = latlngs[i][0] - snapped.lat;
            var dlon = latlngs[i][1] - snapped.lon;
            var d = dlat * dlat + dlon * dlon;
            if (d < bestD) {
                bestD = d;
                bestIdx = i;
            }
        }
        return bestIdx;
    }

    function clearLegTrimGhostLayer() {
        var map = window.courseMappingMap;
        if (map && legTrimGhostLayer) {
            map.removeLayer(legTrimGhostLayer);
            legTrimGhostLayer = null;
        }
    }

    function clearLegTrimMarkerLayer() {
        var map = window.courseMappingMap;
        if (map && legTrimMarkerLayer) {
            map.removeLayer(legTrimMarkerLayer);
            legTrimMarkerLayer = null;
        }
    }

    function clearLegTrimEndpointMarkers() {
        var map = window.courseMappingMap;
        if (!map) {
            return;
        }
        if (legMapLayers.start) {
            map.removeLayer(legMapLayers.start);
            legMapLayers.start = null;
        }
        if (legMapLayers.end) {
            map.removeLayer(legMapLayers.end);
            legMapLayers.end = null;
        }
    }

    function drawLegTrimEndpointMarkers() {
        var map = window.courseMappingMap;
        var base = legTrimSavedLatLngs;
        if (!map || !base || !legTrimActive) {
            return;
        }
        clearLegTrimMarkerLayer();
        legTrimMarkerLayer = L.layerGroup();
        var draft = getLegTrimDraftLatLngs();
        if (draft.length < 2) {
            return;
        }

        function trimEndpointIcon(role) {
            return L.divIcon({
                className: 'leg-trim-endpoint leg-trim-endpoint--' + role,
                html: '<div></div>',
                iconSize: [18, 18],
                iconAnchor: [9, 9]
            });
        }

        function onTrimDrag(role) {
            return function (ev) {
                var pos = ev.target.getLatLng();
                if (role === 'start') {
                    legTrimStartIdx = closestVertexIndexOnRoute(
                        pos.lat,
                        pos.lng,
                        base,
                        0,
                        legTrimEndIdx - 1
                    );
                } else {
                    legTrimEndIdx = closestVertexIndexOnRoute(
                        pos.lat,
                        pos.lng,
                        base,
                        legTrimStartIdx + 1,
                        base.length - 1
                    );
                }
                updateLegTrimDisplay();
            };
        }

        var startLl = draft[0];
        var endLl = draft[draft.length - 1];
        var startMarker = L.marker([startLl[0], startLl[1]], {
            icon: trimEndpointIcon('start'),
            draggable: true,
            autoPan: true,
            zIndexOffset: 900
        });
        startMarker.on('drag', onTrimDrag('start'));
        startMarker.on('click', function (e) {
            L.DomEvent.stopPropagation(e);
        });
        startMarker.bindTooltip('Start — drag along route', { permanent: false });
        startMarker.addTo(legTrimMarkerLayer);

        var endMarker = L.marker([endLl[0], endLl[1]], {
            icon: trimEndpointIcon('end'),
            draggable: true,
            autoPan: true,
            zIndexOffset: 900
        });
        endMarker.on('drag', onTrimDrag('end'));
        endMarker.on('click', function (e) {
            L.DomEvent.stopPropagation(e);
        });
        endMarker.bindTooltip('End — drag along route', { permanent: false });
        endMarker.addTo(legTrimMarkerLayer);

        legTrimMarkerLayer.addTo(map);
    }

    function updateLegTrimDisplay() {
        var map = window.courseMappingMap;
        if (!map || !legTrimSavedLatLngs || !legTrimActive) {
            return;
        }
        var base = legTrimSavedLatLngs;
        var draft = getLegTrimDraftLatLngs();
        if (draft.length < 2) {
            return;
        }
        selectedLegLatLngs = copyLatLngs(draft);
        setLegRoutePolyline(draft);
        clearLegTrimGhostLayer();
        if (legTrimStartIdx > 0 || legTrimEndIdx < base.length - 1) {
            legTrimGhostLayer = L.layerGroup();
            var ghostStyle = {
                color: '#7f8c8d',
                weight: 4,
                opacity: 0.55,
                dashArray: '8,10'
            };
            if (legTrimStartIdx > 0) {
                L.polyline(base.slice(0, legTrimStartIdx + 1), ghostStyle).addTo(legTrimGhostLayer);
            }
            if (legTrimEndIdx < base.length - 1) {
                L.polyline(base.slice(legTrimEndIdx), ghostStyle).addTo(legTrimGhostLayer);
            }
            legTrimGhostLayer.addTo(map);
        }
        drawLegTrimEndpointMarkers();
    }

    function stopLegTrimRoute(discard) {
        if (!legTrimActive && !legTrimSavedLatLngs) {
            return;
        }
        legTrimActive = false;
        clearLegTrimGhostLayer();
        clearLegTrimMarkerLayer();
        if (discard && legTrimSavedLatLngs) {
            selectedLegLatLngs = copyLatLngs(legTrimSavedLatLngs);
            setLegRoutePolyline(selectedLegLatLngs);
        }
        legTrimSavedLatLngs = null;
        legTrimStartIdx = 0;
        legTrimEndIdx = 0;
        updateLegActionButtons();
        var trimBtn = document.getElementById('btn-leg-trim-route');
        if (trimBtn) {
            trimBtn.classList.remove('active');
        }
        if (discard && selectedLegId && selectedLegLatLngs) {
            var leg = getSelectedLeg();
            var legId = selectedLegId;
            var latlngs = selectedLegLatLngs;
            var map = window.courseMappingMap;
            if (map && leg && latlngs.length >= 2) {
                legMapLayers.start = endpointMarker(
                    latlngs[0][0],
                    latlngs[0][1],
                    leg.start_label,
                    'start',
                    legId
                );
                legMapLayers.end = endpointMarker(
                    latlngs[latlngs.length - 1][0],
                    latlngs[latlngs.length - 1][1],
                    leg.end_label,
                    'end',
                    legId
                );
            }
        }
    }

    function filterLocationsForTrim(locations, baseLatLngs, startIdx, endIdx) {
        return (locations || []).filter(function (loc) {
            if (loc.lat == null || loc.lon == null) {
                return true;
            }
            if (!locationTypeSnapsToLegRoute(loc.loc_type, loc.placement)) {
                return true;
            }
            var idx = closestVertexIndexOnRoute(
                loc.lat,
                loc.lon,
                baseLatLngs,
                0,
                baseLatLngs.length - 1
            );
            return idx >= startIdx && idx <= endIdx;
        });
    }

    function startLegTrimRoute() {
        if (!selectedLegId) {
            setLegStatus('Select a leg in the table first.', true);
            return;
        }
        if (!selectedLegLatLngs || selectedLegLatLngs.length < 2) {
            setLegStatus('Wait for the leg route to load on the map.', true);
            return;
        }
        stopLegReshapeRoute(true);
        if (addLocationOnMap) {
            if (!pendingLegLocations.length) {
                stopLegLocationPinMode();
            } else {
                setLegStatus('Save or cancel pending locations before trimming the route.', true);
                return;
            }
        }
        stopLegTrimRoute(true);
        legTrimSavedLatLngs = copyLatLngs(selectedLegLatLngs);
        legTrimStartIdx = 0;
        legTrimEndIdx = legTrimSavedLatLngs.length - 1;
        legTrimActive = true;
        clearLegTrimEndpointMarkers();
        var trimBtn = document.getElementById('btn-leg-trim-route');
        if (trimBtn) {
            trimBtn.classList.add('active');
        }
        updateLegActionButtons();
        updateLegTrimDisplay();
        setLegStatus(
            'Drag the green start or red end along the purple route to shorten the leg. ' +
                'Grey dashed sections will be removed. Confirm to save, Cancel to discard.'
        );
    }

    function confirmLegTrimRoute() {
        if (!legTrimActive || !selectedLegId || !legTrimSavedLatLngs) {
            return;
        }
        var draft = getLegTrimDraftLatLngs();
        if (draft.length < 2) {
            setLegStatus('The leg must keep at least two route points.', true);
            return;
        }
        var coordinates = draft.map(function (ll) {
            return [ll[1], ll[0]];
        });
        var leg = getSelectedLeg();
        var priorLocations = (leg && leg.locations) || [];
        var filteredLocations = filterLocationsForTrim(
            priorLocations,
            legTrimSavedLatLngs,
            legTrimStartIdx,
            legTrimEndIdx
        );
        var removedLocCount = priorLocations.length - filteredLocations.length;
        setLegStatus('Saving trimmed route…');
        fetch(apiBase() + '/segment-library/legs/' + encodeURIComponent(selectedLegId) + '/geometry', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coordinates: coordinates })
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { res: r, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.res.ok) {
                    throw new Error(formatApiError(payload.res, payload.data));
                }
                applyLibraryState(payload.data);
                if (removedLocCount > 0) {
                    return saveLegLocations(selectedLegId, filteredLocations).then(function () {
                        return payload;
                    });
                }
                return payload;
            })
            .then(function () {
                legTrimActive = false;
                legTrimSavedLatLngs = null;
                clearLegTrimGhostLayer();
                clearLegTrimMarkerLayer();
                updateLegActionButtons();
                var trimBtn = document.getElementById('btn-leg-trim-route');
                if (trimBtn) {
                    trimBtn.classList.remove('active');
                }
                selectLegById(selectedLegId, { preserveZoom: true, keepPinMode: true });
                var msg = 'Trimmed route saved for leg ' + selectedLegId + '.';
                if (removedLocCount > 0) {
                    msg +=
                        ' Removed ' +
                        removedLocCount +
                        ' location' +
                        (removedLocCount === 1 ? '' : 's') +
                        ' on the trimmed-off section.';
                }
                setLegStatus(msg);
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function confirmLegRouteEdit() {
        if (legTrimActive) {
            confirmLegTrimRoute();
        } else if (legReshapeActive) {
            confirmLegReshapeRoute();
        }
    }

    function cancelLegRouteEdit() {
        if (legTrimActive) {
            stopLegTrimRoute(true);
            setLegStatus('Route trim cancelled.');
        } else if (legReshapeActive) {
            stopLegReshapeRoute(true);
            setLegStatus('Route reshape cancelled.');
        }
    }

    function clearLegMapLayers() {
        var map = window.courseMappingMap;
        if (!map) return;
        clearLegReshapeAnchorLayer();
        clearLegTrimGhostLayer();
        clearLegTrimMarkerLayer();
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
        if (!isLegRouteEditActive()) {
            selectedLegLatLngs = null;
        }
    }

    function invalidateLegGeometryRequests() {
        legGeometryRequestId += 1;
    }

    /** Nearest point on leg polyline ([[lat, lon], ...]) to a map click. */
    function snapClickToLegRoute(lat, lon, latlngs) {
        if (!latlngs) {
            latlngs = getActiveLegLatLngs();
        }
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
            var currentLoc = resolveLegLocationRecord(loc, opts, isPending);
            var coords = finalizeLegLocationCoords(currentLoc, ll.lat, ll.lng);
            currentLoc.lat = coords.lat;
            currentLoc.lon = coords.lon;
            marker.setLatLng([currentLoc.lat, currentLoc.lon]);
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
            locations[opts.locIndex] = Object.assign({}, locations[opts.locIndex], coords, {
                placement: legLocationPlacement(locations[opts.locIndex].loc_type)
            });
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
        if (locationTypeSnapsToLegRoute(loc.loc_type, loc.placement) && selectedLegLatLngs) {
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
        function syncPopupLocTypeFromSelect() {
            var locType = sel.value || 'course';
            var target = opts.loc;
            if (target) {
                target.loc_type = locType;
                target.placement = legLocationPlacement(locType);
            }
            updatePlacementHint();
        }
        function updatePlacementHint() {
            hint.textContent = locationTypeSnapsToLegRoute(sel.value)
                ? 'Snaps to the purple route when saved. Set seg_id on the Course tab if needed.'
                : 'Stays at your click (off-course). Set Proxy loc ID on the Course tab for timing.';
        }
        syncPopupLocTypeFromSelect();
        sel.addEventListener('change', syncPopupLocTypeFromSelect);
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
        function doFit() {
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
        if (legsTableBoundsFilter) {
            legsTableBoundsFilter.runProgrammatic(doFit);
        } else {
            doFit();
        }
    }

    function refreshSelectedLegMap(options) {
        options = options || {};
        if (!selectedLegId) return;
        var leg = getSelectedLeg();
        if (!leg) return;
        if (selectedLegLatLngs && selectedLegLatLngs.length >= 2 && legMapLayers.line) {
            redrawLegLocationMarkers(leg);
            updateLegActionButtons();
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
        if (isLegRouteEditActive()) {
            setLegStatus('Confirm or cancel route editing before adding locations.', true);
            return;
        }
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
                'Drag pins to move. Course, water, and official snap to the route; aid, traffic, and extract stay where you place them.'
        );
    }

    function clearLegMap() {
        stopLegLocationPinMode();
        stopLegReshapeRoute(true);
        stopLegTrimRoute(true);
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
        var leg = (libraryState && libraryState.legs || []).find(function (c) {
            return c.id === legId;
        });
        if (!leg) return;
        if (!options.keepReshape) {
            stopLegReshapeRoute(true);
        }
        if (!options.keepTrim) {
            stopLegTrimRoute(true);
        }
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
                try {
                    legBoundsCache[legId] = L.latLngBounds(latlngs);
                } catch (e) {
                    delete legBoundsCache[legId];
                }
                setLegRoutePolyline(latlngs);
                var props = feature.properties || {};
                var currentLeg = getSelectedLeg() || leg;
                if (!legTrimActive) {
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
                }
                redrawLegLocationMarkers(currentLeg);
                updateLegActionButtons();
                if (!options.preserveZoom) {
                    fitLegMapBounds(currentLeg);
                }
            })
            .catch(function (err) {
                updateLegActionButtons();
                setLegStatus(err.message || String(err), true);
            });
    }

    function selectLeg(leg) {
        if (!leg) return;
        selectLegById(leg.id);
    }

    function exportLeg(legId) {
        var leg = (libraryState && libraryState.legs || []).find(function (c) {
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

    function renderLegsTable(legsSubset) {
        var tbody = document.getElementById('course-legs-tbody');
        var wrap = document.getElementById('course-legs-table-wrap');
        var empty = document.getElementById('course-legs-empty');
        if (!tbody) return;
        var allLegs = (libraryState && libraryState.legs) || [];
        var legs = legsSubset || allLegs;
        if (!allLegs.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            clearLegMap();
            updateLegsMapBoundsStatus(0, 0);
            return;
        }
        if (!legs.length) {
            if (wrap) wrap.style.display = 'block';
            if (empty) empty.style.display = 'none';
            tbody.innerHTML = '';
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        tbody.innerHTML = '';
        legs.forEach(function (ch) {
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
                flowTypeLabelForValue(ch.flow_type),
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
        if (!libraryState || !libraryState.has_library || !libraryState.legs.length || !events.length) {
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
        libraryState.legs.forEach(function (ch) {
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
        if (!libraryState || !libraryState.legs || !libraryState.legs.length) {
            return null;
        }
        var legId = resolveLegIdForSegment(seg, segIdx);
        var ch = libraryState.legs.find(function (c) { return c.id === legId; });
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
                loadCoursePreviewRoute(eid).then(function () {
                    syncCoursePreviewBoundsFilterItems();
                });
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
        if (!eventId || !hasCombinedCourse()) return Promise.resolve();
        return fetch(
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
                function finishPreviewLoad() {
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
                    attachCoursePreviewBoundsFilter();
                    syncCoursePreviewBoundsFilterItems();
                    setTimeout(function () { map.invalidateSize(); }, 120);
                }
                if (coursePreviewBoundsFilter) {
                    coursePreviewBoundsFilter.runProgrammatic(function () {
                        map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
                        finishPreviewLoad();
                    });
                } else {
                    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
                    finishPreviewLoad();
                }
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
        var hasLegs = libraryState && libraryState.legs && libraryState.legs.length;
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
                attachLegsTableBoundsFilter();
                fitLegMapToAllLegs();
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
                attachCoursePreviewBoundsFilter();
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
            direction: 'uni',
            flow_type: 'none',
            flow_notes: ''
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
        addSelectField('Flow type', 'leg-flow-type', leg.flow_type || 'none', flowTypeChoices());

        var notesWrap = document.createElement('div');
        notesWrap.style.marginBottom = '0.65rem';
        var notesLab = document.createElement('label');
        notesLab.textContent = 'Flow notes (optional)';
        notesLab.style.display = 'block';
        notesLab.style.fontWeight = '600';
        notesLab.style.fontSize = '0.85rem';
        var notesTa = document.createElement('textarea');
        notesTa.id = 'leg-flow-notes';
        notesTa.rows = 2;
        notesTa.maxLength = 500;
        notesTa.placeholder = 'Notes for flow.csv export';
        notesTa.value = leg.flow_notes != null ? String(leg.flow_notes) : '';
        notesTa.style.width = '100%';
        notesTa.style.boxSizing = 'border-box';
        notesTa.style.resize = 'vertical';
        notesTa.style.fontFamily = 'inherit';
        notesWrap.appendChild(notesLab);
        notesWrap.appendChild(notesTa);
        body.appendChild(notesWrap);

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
            direction: ((document.getElementById('leg-direction') || {}).value || 'uni').trim(),
            flow_type: ((document.getElementById('leg-flow-type') || {}).value || 'none').trim(),
            flow_notes: ((document.getElementById('leg-flow-notes') || {}).value || '').trim()
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
            fd.append('flow_type', fields.flow_type);
            fd.append('flow_notes', fields.flow_notes);
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
                var count = (payload.data.legs || []).length;
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
                    var segRefresh = data.apply.seg_id_refresh_count || 0;
                    if (segRefresh > 0) {
                        status += '; segment IDs updated on ' + segRefresh + ' location(s)';
                    }
                    var unmapped = data.apply.seg_id_unmapped || [];
                    if (unmapped.length) {
                        status +=
                            '; ' +
                            unmapped.length +
                            ' location(s) could not be mapped to a segment (Course tab)';
                    }
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
        var reshapeBtn = document.getElementById('btn-leg-reshape-route');
        if (reshapeBtn) {
            reshapeBtn.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                if (isLegRouteEditActive()) {
                    return;
                }
                startLegReshapeRoute();
            });
        }
        var trimBtn = document.getElementById('btn-leg-trim-route');
        if (trimBtn) {
            trimBtn.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                if (legTrimActive) {
                    return;
                }
                startLegTrimRoute();
            });
        }
        var routeEditConfirm = document.getElementById('btn-leg-route-edit-confirm');
        if (routeEditConfirm) {
            routeEditConfirm.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                confirmLegRouteEdit();
            });
        }
        var routeEditCancel = document.getElementById('btn-leg-route-edit-cancel');
        if (routeEditCancel) {
            routeEditCancel.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                cancelLegRouteEdit();
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
            attachLegsTableBoundsFilter();
            if (window.courseMappingMap) {
                setTimeout(function () {
                    window.courseMappingMap.invalidateSize();
                    bindLegMapControls();
                    attachLegsTableBoundsFilter();
                }, 100);
            }
        },
        attachLegsTableBoundsFilter: attachLegsTableBoundsFilter,
        attachCoursePreviewBoundsFilter: attachCoursePreviewBoundsFilter,
        syncCoursePreviewBoundsFilterItems: syncCoursePreviewBoundsFilterItems
    };
})();
