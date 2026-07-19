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
    /** Toolbar sentinel: show every event route and every location. */
    var COURSE_PREVIEW_ALL = '__all__';
    var COURSE_PREVIEW_ROUTE_COLORS = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2'];
    var legReshapeActive = false;
    var legReshapeDraftLatLngs = null;
    var legReshapeAnchorIndices = null;
    var legReshapeAnchorLayer = null;
    var legReshapeHitLayer = null;
    var legReshapeSavedLatLngs = null;
    var legTrimActive = false;
    var legTrimSavedLatLngs = null;
    var legTrimStartIdx = 0;
    var legTrimEndIdx = 0;
    var legTrimStartOverride = null;
    var legTrimEndOverride = null;
    var legTrimGhostLayer = null;
    var legTrimMarkerLayer = null;
    var legTrimStartMarker = null;
    var legTrimEndMarker = null;
    var legBoundsCache = {};
    var legsTableBoundsFilter = null;
    var coursePreviewBoundsFilter = null;
    /** Background layer showing every leg route on the legs map. */
    var allLegRoutesLayer = null;
    var allLegRoutesFetchSeq = 0;
    var ALL_LEG_ROUTES_PANE = 'all-leg-routes';
    var allLegLocationsLayer = null;
    var ALL_LEG_LOCATIONS_PANE = 'all-leg-locations';
    var legLocationsBrowserShowAllPins = false;
    var legLocationsBrowserHighlightKey = '';
    var pendingLocationFocus = null;
    var legLocationsBrowserFiltersBound = false;
    /** Draw-a-leg mode state (Issue #789 Create Leg). */
    var legDrawActive = false;
    var legDrawCoords = [];        // [[lon, lat], ...] full drawn polyline
    var legDrawClickCounts = [];   // points appended per click — undo stack
    var legDrawLayer = null;
    var legDrawClickHandler = null;
    var legDrawRoutingBusy = false;
    /** Extend selected leg at start or end with snap routing. */
    var legExtendActive = false;
    var legExtendFromEnd = true;
    var legExtendSavedLatLngs = null;
    var legExtendNewCoords = [];     // [[lon, lat], ...] new vertices only (path order)
    var legExtendClickCounts = [];   // points added per click — undo stack
    var legExtendLayer = null;
    var legExtendClickHandler = null;
    var legExtendRoutingBusy = false;
    /** When false during draw mode, existing leg routes are hidden (Trace off). */
    var legDrawTraceEnabled = true;
    /** Coordinates handed to the Add-leg editor by Finish. */
    var pendingDrawCoordinates = null;

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

    /** Global Legs hub (no package): view=legs on Race Configuration entry. */
    function isOrgLegsHubMode() {
        if (resolveConfigPackageId()) return false;
        var params = new URLSearchParams(window.location.search);
        var view = params.get('view');
        var legsPanel = document.getElementById('config-package-legs-panel');
        var hubLegs = document.getElementById('race-config-hub-legs');
        if (view === 'legs') return true;
        return !!(
            legsPanel &&
            hubLegs &&
            hubLegs.style.display !== 'none' &&
            legsPanel.offsetParent !== null
        );
    }

    function apiBase() {
        return '/api/config/packages/' + encodeURIComponent(resolveConfigPackageId());
    }

    function usesOrgLegLibrary() {
        if (isOrgLegsHubMode()) return true;
        if (!libraryState) return true;
        return libraryState.leg_source === 'org';
    }

    function legGeometryUrl(legId) {
        if (usesOrgLegLibrary()) {
            return '/api/org/legs/' + encodeURIComponent(legId) + '/geometry';
        }
        return apiBase() + '/segment-library/legs/' + encodeURIComponent(legId) + '/geometry';
    }

    function legDetailUrl(legId) {
        if (usesOrgLegLibrary()) {
            return '/api/org/legs/' + encodeURIComponent(legId);
        }
        return apiBase() + '/segment-library/legs/' + encodeURIComponent(legId);
    }

    function legUploadUrl() {
        if (usesOrgLegLibrary()) {
            return '/api/org/legs/upload';
        }
        return apiBase() + '/segment-library/upload';
    }

    function legCreateUrl() {
        if (usesOrgLegLibrary()) {
            return '/api/org/legs';
        }
        return apiBase() + '/segment-library/legs';
    }

    function getPackageResources() {
        var r = window.CONFIG_PACKAGE_RESOURCES;
        if (Array.isArray(r) && r.length) return r.slice();
        return getDefaultLegResources().slice();
    }

    var DEFAULT_LEG_RESOURCES = [
        { code: 'fpf', label: 'FPF' },
        { code: 'yssr', label: 'YSSR' },
        { code: 'awp', label: 'AWP' },
        { code: 'vol', label: 'VOL' },
    ];
    var ORG_LEG_RESOURCES_STORAGE_KEY = 'runflow.org.legResources';

    function getDefaultLegResources() {
        return DEFAULT_LEG_RESOURCES.map(function (res) {
            return { code: res.code, label: res.label };
        });
    }

    function loadOrgLegResourcesFromStorage() {
        try {
            var raw = localStorage.getItem(ORG_LEG_RESOURCES_STORAGE_KEY);
            if (!raw) return getDefaultLegResources();
            var parsed = JSON.parse(raw);
            if (!Array.isArray(parsed) || !parsed.length) return getDefaultLegResources();
            return parsed.map(function (r) {
                return {
                    code: String(r.code || '').trim(),
                    label: String(r.label || r.code || '').trim(),
                };
            }).filter(function (r) { return r.code; });
        } catch (e) {
            return getDefaultLegResources();
        }
    }

    function initOrgLegHubResources() {
        window.CONFIG_PACKAGE_RESOURCES = loadOrgLegResourcesFromStorage();
        document.dispatchEvent(
            new CustomEvent('package-resources-updated', {
                detail: { resources: window.CONFIG_PACKAGE_RESOURCES },
            })
        );
    }

    function saveOrgLegResourcesToStorage(resources) {
        var normalized = (resources || []).map(function (r) {
            return { code: r.code, label: r.label || r.code.toUpperCase() };
        });
        localStorage.setItem(ORG_LEG_RESOURCES_STORAGE_KEY, JSON.stringify(normalized));
        window.CONFIG_PACKAGE_RESOURCES = normalized;
        document.dispatchEvent(
            new CustomEvent('package-resources-updated', {
                detail: { resources: normalized },
            })
        );
    }

    function afterLegLibraryMutation(data) {
        if (usesOrgLegLibrary() || (data && data.leg_source === 'org' && !data.recipes)) {
            if (data && Array.isArray(data.legs)) {
                applyLibraryState({
                    leg_source: data.leg_source || 'org',
                    has_library: data.has_library !== false,
                    legs: data.legs,
                    recipes: (libraryState && libraryState.recipes) || {},
                    order_grid: (libraryState && libraryState.order_grid) || {},
                    package_events: (libraryState && libraryState.package_events) || [],
                    recipe_lengths_km: (libraryState && libraryState.recipe_lengths_km) || {},
                    stitch_warnings: (libraryState && libraryState.stitch_warnings) || [],
                });
                return Promise.resolve();
            }
            return loadLibrary();
        }
        applyLibraryState(data);
        return Promise.resolve();
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
        if (!visible && !isOrgLegsHubMode()) {
            clearLegMap();
        }
        var hubMode = isOrgLegsHubMode();
        var manageRes = document.getElementById('btn-manage-resources-legs');
        if (manageRes) {
            manageRes.style.display = '';
        }
        var orgLibBtn = document.getElementById('btn-org-leg-library');
        if (orgLibBtn) {
            orgLibBtn.style.display = hubMode ? 'none' : '';
        }
        var exportAllBtn = document.getElementById('btn-export-all-legs');
        if (exportAllBtn) {
            // Package zip export needs a config_id; hide on hub for now.
            exportAllBtn.style.display = hubMode ? 'none' : '';
        }
        document.dispatchEvent(new CustomEvent('race-config-place-course-map'));
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

    function parseOrderValues(raw) {
        if (raw == null || raw === '') return [];
        var parts = String(raw).split(',');
        var values = [];
        parts.forEach(function (part) {
            var n = parseInt(String(part).trim(), 10);
            if (!isNaN(n) && n >= 1 && values.indexOf(n) < 0) values.push(n);
        });
        return values.sort(function (a, b) { return a - b; });
    }

    function formatOrderValues(values) {
        if (!values || !values.length) return '';
        return values.slice().sort(function (a, b) { return a - b; }).join(',');
    }

    function getOrder(legId, eventId) {
        var row = orderGrid[eventId] || {};
        var v = row[legId];
        return v == null || v === '' ? '' : String(v);
    }

    function setOrder(legId, eventId, value) {
        if (!orderGrid[eventId]) orderGrid[eventId] = {};
        var trimmed = String(value || '').trim();
        if (!trimmed) {
            orderGrid[eventId][legId] = null;
        } else {
            var values = parseOrderValues(trimmed);
            orderGrid[eventId][legId] = values.length ? formatOrderValues(values) : null;
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
                parseOrderValues(getOrder(ch.id, ev)).forEach(function (order) {
                    pairs.push({ order: order, km: ch.length_km || 0 });
                });
            });
            pairs.sort(function (a, b) {
                return a.order - b.order || 0;
            });
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

    function offCourseUsesProxyTiming(locType) {
        var t = String(locType || '').toLowerCase();
        return t === 'traffic' || t === 'extract';
    }

    function legLocationProxyIsSet(loc) {
        if (!loc) return false;
        if (loc.proxy_leg_loc_key != null && String(loc.proxy_leg_loc_key).trim()) {
            return true;
        }
        var p = loc.proxy_loc_id;
        if (p == null || p === '') return false;
        var s = String(p).trim();
        return s !== '' && s.toLowerCase() !== 'nan';
    }

    function legLocKey(legId, index) {
        return String(legId || '').trim() + ':' + String(index);
    }

    function collectLegProxyTimingSources(excludeKey, currentLegId) {
        var items = [];
        (libraryState && libraryState.legs || []).forEach(function (leg) {
            var legId = String(leg.id || '').trim();
            if (!legId) return;
            (leg.locations || []).forEach(function (loc, idx) {
                var key = legLocKey(legId, idx);
                if (excludeKey && key === excludeKey) return;
                if (offCourseUsesProxyTiming(loc.loc_type)) return;
                if (legLocationProxyIsSet(loc)) return;
                items.push({
                    key: key,
                    legId: legId,
                    label: (loc.loc_label || '').trim() || 'Untitled',
                    loc_type: loc.loc_type || 'course',
                });
            });
        });
        var currentLeg = String(currentLegId || '').trim();
        items.sort(function (a, b) {
            var aSame = currentLeg && a.legId === currentLeg ? 0 : 1;
            var bSame = currentLeg && b.legId === currentLeg ? 0 : 1;
            if (aSame !== bSame) return aSame - bSame;
            if (a.legId !== b.legId) return a.legId.localeCompare(b.legId, undefined, { numeric: true });
            return a.key.localeCompare(b.key, undefined, { numeric: true });
        });
        return items;
    }

    function appendLegProxyTimingOptions(sel, items) {
        items.forEach(function (item) {
            var opt = document.createElement('option');
            opt.value = item.key;
            opt.textContent =
                item.key +
                ' — ' +
                item.label +
                (item.loc_type ? ' (' + item.loc_type + ')' : '');
            sel.appendChild(opt);
        });
    }

    function buildLegProxyTimingSelect(loc, excludeKey, currentLegId) {
        var sel = document.createElement('select');
        var none = document.createElement('option');
        none.value = '';
        none.textContent = '— None —';
        sel.appendChild(none);
        var currentLeg = String(currentLegId || '').trim();
        var sources = collectLegProxyTimingSources(excludeKey, currentLeg);
        var sameLeg = sources.filter(function (item) {
            return currentLeg && item.legId === currentLeg;
        });
        var otherLegs = sources.filter(function (item) {
            return !currentLeg || item.legId !== currentLeg;
        });
        if (sameLeg.length) {
            var sameGroup = document.createElement('optgroup');
            sameGroup.label = currentLeg ? 'Leg ' + currentLeg : 'This leg';
            appendLegProxyTimingOptions(sameGroup, sameLeg);
            sel.appendChild(sameGroup);
        }
        if (otherLegs.length) {
            var otherGroup = document.createElement('optgroup');
            otherGroup.label = 'Other legs';
            appendLegProxyTimingOptions(otherGroup, otherLegs);
            sel.appendChild(otherGroup);
        }
        if (!sameLeg.length && !otherLegs.length) {
            appendLegProxyTimingOptions(sel, sources);
        }
        var current =
            loc && loc.proxy_leg_loc_key != null && String(loc.proxy_leg_loc_key).trim()
                ? String(loc.proxy_leg_loc_key).trim()
                : '';
        if (current) {
            sel.value = current;
            if (sel.value !== current) {
                var stale = document.createElement('option');
                stale.value = current;
                stale.textContent = current + ' — (location not found)';
                sel.appendChild(stale);
                sel.value = current;
            }
        }
        return sel;
    }

    function collectAllLegLocationRows() {
        var rows = [];
        (libraryState && libraryState.legs || []).forEach(function (leg) {
            var legId = String(leg.id || '').trim();
            if (!legId) return;
            var legLabel = (leg.leg_label || leg.seg_label || legId).trim() || legId;
            (leg.locations || []).forEach(function (loc, idx) {
                if (!loc || loc.lat == null || loc.lon == null) return;
                rows.push({
                    legId: legId,
                    legLabel: legLabel,
                    locIndex: idx,
                    key: legLocKey(legId, idx),
                    loc: loc
                });
            });
        });
        return rows;
    }

    function formatLegLocationProxyDisplay(loc) {
        if (!loc) return '—';
        if (loc.proxy_leg_loc_key != null && String(loc.proxy_leg_loc_key).trim()) {
            return String(loc.proxy_leg_loc_key).trim();
        }
        var p = loc.proxy_loc_id;
        if (p == null || p === '') return '—';
        var s = String(p).trim();
        return s && s.toLowerCase() !== 'nan' ? s : '—';
    }

    function legLocationResourceCount(loc, code) {
        if (!loc) return 0;
        if (loc.resources && loc.resources[code] != null) {
            var n = parseInt(loc.resources[code], 10);
            return isNaN(n) ? 0 : Math.max(0, n);
        }
        var legacy = loc[code + '_count'];
        if (legacy == null || legacy === '') return 0;
        var n2 = parseInt(legacy, 10);
        return isNaN(n2) ? 0 : Math.max(0, n2);
    }

    function renderLegLocationsBrowserHeader() {
        var row = document.getElementById('leg-locations-browser-thead-row');
        if (!row) return;
        row.innerHTML = '';
        ['Leg #', 'ID', 'Label', 'Type', 'Proxy'].forEach(function (text) {
            var th = document.createElement('th');
            th.textContent = text;
            row.appendChild(th);
        });
        getPackageResources().forEach(function (res) {
            var th = document.createElement('th');
            th.textContent = String(res.code || '').toUpperCase();
            th.title = (res.label || res.code) + ' (' + res.code + '_count)';
            row.appendChild(th);
        });
        var actionTh = document.createElement('th');
        actionTh.className = 'course-map-action-cell';
        actionTh.textContent = 'Actions';
        row.appendChild(actionTh);
    }

    function scrollLegMapIntoView() {
        var el =
            document.querySelector('#config-package-legs-panel .config-legs-map-region') ||
            document.getElementById('course-map-container');
        if (el && el.scrollIntoView) {
            el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function navigateToLegLocation(legId, locIndex, opts) {
        opts = opts || {};
        legId = String(legId || '').trim();
        if (!legId || locIndex == null) return;
        var idx = parseInt(locIndex, 10);
        if (isNaN(idx) || idx < 0) return;
        pendingLocationFocus = { legId: legId, locIndex: idx };
        legLocationsBrowserHighlightKey = legLocKey(legId, idx);
        var legSel = document.getElementById('leg-locations-filter-leg');
        if (legSel) legSel.value = legId;
        if (!isOrgLegsHubMode()) {
            var url = new URL(window.location.href);
            url.searchParams.delete('id');
            url.searchParams.set('view', 'legs');
            window.history.pushState({}, '', url.toString());
            document.dispatchEvent(
                new CustomEvent('race-config-show-legs-hub', {
                    detail: { legId: legId, locIndex: idx },
                })
            );
            return;
        }
        renderLegLocationsBrowser();
        if (opts.scroll !== false) scrollLegMapIntoView();
        focusLegLocation(legId, idx);
    }

    function getLegLocationsBrowserFilters() {
        var legSel = document.getElementById('leg-locations-filter-leg');
        var typeSel = document.getElementById('leg-locations-filter-type');
        var searchInp = document.getElementById('leg-locations-filter-search');
        return {
            legId: legSel ? String(legSel.value || '').trim() : '',
            type: typeSel ? String(typeSel.value || '').trim().toLowerCase() : '',
            query: searchInp ? String(searchInp.value || '').trim().toLowerCase() : ''
        };
    }

    function legLocationRowMatchesFilters(row, filters) {
        if (!row || !row.loc) return false;
        if (filters.legId && row.legId !== filters.legId) return false;
        var locType = String(row.loc.loc_type || 'course').toLowerCase();
        if (filters.type && locType !== filters.type) return false;
        if (filters.query) {
            var label = String(row.loc.loc_label || '').toLowerCase();
            if (label.indexOf(filters.query) < 0) return false;
        }
        return true;
    }

    function ensureAllLegLocationsPane(map) {
        if (!map.getPane(ALL_LEG_LOCATIONS_PANE)) {
            var pane = map.createPane(ALL_LEG_LOCATIONS_PANE);
            pane.style.zIndex = 390;
        }
    }

    function removeAllLegLocationsLayer() {
        var map = window.courseMappingMap;
        if (map && allLegLocationsLayer) {
            map.removeLayer(allLegLocationsLayer);
        }
        allLegLocationsLayer = null;
    }

    function syncLegLocationsShowAllPinsButton() {
        var btn = document.getElementById('btn-leg-locations-show-all-pins');
        if (!btn) return;
        btn.classList.toggle('active', !!legLocationsBrowserShowAllPins);
        btn.textContent = legLocationsBrowserShowAllPins ? 'Hide all pins' : 'Show all pins';
    }

    function renderAllLegLocationsMapLayer() {
        var map = window.courseMappingMap;
        if (!map || !legLocationsBrowserShowAllPins || !isOrgLegsHubMode()) {
            removeAllLegLocationsLayer();
            return;
        }
        ensureAllLegLocationsPane(map);
        removeAllLegLocationsLayer();
        var filters = getLegLocationsBrowserFilters();
        var rows = collectAllLegLocationRows().filter(function (row) {
            return legLocationRowMatchesFilters(row, filters);
        });
        if (!rows.length) return;
        var group = L.layerGroup();
        rows.forEach(function (row) {
            var loc = row.loc;
            var fill = legLocationColor(loc.loc_type || 'course');
            var highlight = legLocationsBrowserHighlightKey && row.key === legLocationsBrowserHighlightKey;
            var marker = L.marker([loc.lat, loc.lon], {
                pane: ALL_LEG_LOCATIONS_PANE,
                icon: L.divIcon({
                    className:
                        'leg-location-pin leg-location-pin-all-legs' +
                        (highlight ? ' leg-location-pin-all-legs-highlight' : ''),
                    html:
                        '<div style="width:' +
                        (highlight ? 12 : 10) +
                        'px;height:' +
                        (highlight ? 12 : 10) +
                        'px;background:' +
                        fill +
                        ';border:2px solid ' +
                        (highlight ? '#2c3e50' : '#fff') +
                        ';border-radius:50%;box-sizing:border-box;"></div>',
                    iconSize: [highlight ? 12 : 10, highlight ? 12 : 10],
                    iconAnchor: [highlight ? 6 : 5, highlight ? 6 : 5]
                }),
                interactive: false
            });
            marker.bindTooltip(
                row.legId +
                    ':' +
                    row.locIndex +
                    ' — ' +
                    (loc.loc_label || 'Location') +
                    ' (' +
                    (loc.loc_type || 'course') +
                    ')',
                { sticky: true }
            );
            group.addLayer(marker);
        });
        allLegLocationsLayer = group.addTo(map);
    }

    function populateLegLocationsBrowserFilters() {
        var legSel = document.getElementById('leg-locations-filter-leg');
        var typeSel = document.getElementById('leg-locations-filter-type');
        if (!legSel || !typeSel) return;
        var prevLeg = legSel.value;
        var prevType = typeSel.value;
        legSel.innerHTML = '';
        var allLeg = document.createElement('option');
        allLeg.value = '';
        allLeg.textContent = 'All legs';
        legSel.appendChild(allLeg);
        (libraryState && libraryState.legs || []).forEach(function (leg) {
            var opt = document.createElement('option');
            opt.value = leg.id;
            opt.textContent = leg.id + ' — ' + ((leg.leg_label || '').slice(0, 36) || leg.id);
            legSel.appendChild(opt);
        });
        if (prevLeg && legSel.querySelector('option[value="' + prevLeg + '"]')) {
            legSel.value = prevLeg;
        }
        typeSel.innerHTML = '';
        var allType = document.createElement('option');
        allType.value = '';
        allType.textContent = 'All types';
        typeSel.appendChild(allType);
        locationTypes().forEach(function (t) {
            var opt = document.createElement('option');
            opt.value = t.value;
            opt.textContent = t.label;
            typeSel.appendChild(opt);
        });
        if (prevType) typeSel.value = prevType;
    }

    function renderLegLocationsBrowser() {
        var card = document.getElementById('leg-locations-browser-card');
        var tbody = document.getElementById('leg-locations-browser-tbody');
        var wrap = document.getElementById('leg-locations-browser-wrap');
        var empty = document.getElementById('leg-locations-browser-empty');
        var statusEl = document.getElementById('leg-locations-browser-status');
        if (!card || !tbody) return;
        var showBrowser = isOrgLegsHubMode() && libraryState && libraryState.legs && libraryState.legs.length;
        if (!showBrowser) {
            card.style.display = 'none';
            removeAllLegLocationsLayer();
            return;
        }
        card.style.display = '';
        populateLegLocationsBrowserFilters();
        var allRows = collectAllLegLocationRows();
        var filters = getLegLocationsBrowserFilters();
        var rows = allRows.filter(function (row) {
            return legLocationRowMatchesFilters(row, filters);
        });
        if (statusEl) {
            statusEl.textContent =
                rows.length +
                ' of ' +
                allRows.length +
                ' location' +
                (allRows.length === 1 ? '' : 's') +
                ' shown. Use the view action to edit on the map.';
        }
        renderLegLocationsBrowserHeader();
        tbody.innerHTML = '';
        if (!rows.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            renderAllLegLocationsMapLayer();
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        rows.forEach(function (row) {
            var tr = document.createElement('tr');
            tr.dataset.legId = row.legId;
            tr.dataset.locIndex = String(row.locIndex);
            tr.dataset.locKey = row.key;
            if (row.legId === selectedLegId) tr.classList.add('selected');
            if (legLocationsBrowserHighlightKey && row.key === legLocationsBrowserHighlightKey) {
                tr.classList.add('leg-locations-browser-row-highlight');
            }
            [
                row.legId,
                String(row.locIndex),
                (row.loc.loc_label || '').slice(0, 48),
                row.loc.loc_type || 'course',
                formatLegLocationProxyDisplay(row.loc),
            ].forEach(function (text) {
                var td = document.createElement('td');
                td.textContent = text;
                tr.appendChild(td);
            });
            getPackageResources().forEach(function (res) {
                var resTd = document.createElement('td');
                resTd.textContent = String(legLocationResourceCount(row.loc, res.code));
                tr.appendChild(resTd);
            });
            var actionTd = document.createElement('td');
            actionTd.className = 'course-map-action-cell';
            var ta = window.TableActions;
            if (ta) {
                actionTd.appendChild(
                    ta.createIconButton('view', 'View on map and edit location', function (ev) {
                        if (ev.stopPropagation) ev.stopPropagation();
                        navigateToLegLocation(row.legId, row.locIndex);
                    })
                );
            }
            tr.appendChild(actionTd);
            tr.addEventListener('click', function () {
                legLocationsBrowserHighlightKey = row.key;
                renderLegLocationsBrowser();
            });
            tbody.appendChild(tr);
        });
        renderAllLegLocationsMapLayer();
    }

    function tryOpenPendingLocationFocus() {
        if (!pendingLocationFocus) return;
        var map = window.courseMappingMap;
        var legId = pendingLocationFocus.legId;
        var locIndex = pendingLocationFocus.locIndex;
        pendingLocationFocus = null;
        if (!map || selectedLegId !== legId) return;
        var leg = getSelectedLeg();
        if (!leg || !leg.locations || locIndex < 0 || locIndex >= leg.locations.length) return;
        var loc = leg.locations[locIndex];
        if (loc.lat == null || loc.lon == null) return;
        map.setView([loc.lat, loc.lon], Math.max(map.getZoom(), 15));
        openLegLocationPopup({
            mode: 'edit-saved',
            loc: loc,
            locIndex: locIndex,
            latlng: L.latLng(loc.lat, loc.lon)
        });
    }

    function focusLegLocation(legId, locIndex) {
        legId = String(legId || '').trim();
        if (!legId || locIndex == null) return;
        pendingLocationFocus = { legId: legId, locIndex: locIndex };
        if (selectedLegId === legId && selectedLegLatLngs && selectedLegLatLngs.length >= 2) {
            tryOpenPendingLocationFocus();
            return;
        }
        selectLegById(legId, { preserveZoom: false, keepPinMode: true });
    }

    function bindLegLocationsBrowserUi() {
        if (legLocationsBrowserFiltersBound) return;
        legLocationsBrowserFiltersBound = true;
        var showBtn = document.getElementById('btn-leg-locations-show-all-pins');
        if (showBtn) {
            showBtn.addEventListener('click', function () {
                legLocationsBrowserShowAllPins = !legLocationsBrowserShowAllPins;
                syncLegLocationsShowAllPinsButton();
                renderAllLegLocationsMapLayer();
            });
        }
        ['leg-locations-filter-leg', 'leg-locations-filter-type'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', function () {
                    renderLegLocationsBrowser();
                });
            }
        });
        var searchInp = document.getElementById('leg-locations-filter-search');
        if (searchInp) {
            searchInp.addEventListener('input', function () {
                renderLegLocationsBrowser();
            });
        }
        document.addEventListener('package-resources-updated', function () {
            if (isOrgLegsHubMode()) renderLegLocationsBrowser();
        });
        syncLegLocationsShowAllPinsButton();
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
        if (coursePreviewSelectedEvent === COURSE_PREVIEW_ALL) return null;
        if (coursePreviewSelectedEvent) return coursePreviewSelectedEvent;
        var evs = packageEvents();
        return evs.length ? evs[0] : null;
    }

    function coursePreviewShowsAllEvents() {
        return coursePreviewSelectedEvent === COURSE_PREVIEW_ALL;
    }

    function normalizePreviewEventId(eventId) {
        return String(eventId || '').trim().toLowerCase();
    }

    function locationMatchesCoursePreviewEvent(loc) {
        if (!loc || coursePreviewShowsAllEvents()) return true;
        var eid = normalizePreviewEventId(coursePreviewSelectedEvent);
        if (!eid) return true;
        var flag = loc[eid];
        if (flag == null && coursePreviewSelectedEvent) {
            flag = loc[coursePreviewSelectedEvent];
        }
        return String(flag || '').toLowerCase() === 'y';
    }

    function segmentMatchesCoursePreviewEvent(seg) {
        if (!seg || coursePreviewShowsAllEvents()) return true;
        var eid = normalizePreviewEventId(coursePreviewSelectedEvent);
        if (!eid) return true;
        return (seg.events || []).some(function (ev) {
            return normalizePreviewEventId(ev) === eid;
        });
    }

    function flattenPreviewLatLngs(layer) {
        if (!layer) return [];
        if (typeof layer.eachLayer === 'function') {
            var grouped = [];
            layer.eachLayer(function (sub) {
                grouped = grouped.concat(flattenPreviewLatLngs(sub));
            });
            return grouped;
        }
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
            if (!segmentMatchesCoursePreviewEvent(seg)) return;
            items.push({ kind: 'segment', index: i, data: seg });
        });
        (course.locations || []).forEach(function (loc, i) {
            if (!locationMatchesCoursePreviewEvent(loc)) return;
            items.push({ kind: 'location', index: i, data: loc });
        });
        return items;
    }

    function countCoursePreviewSegmentsForSelection() {
        var pkg = window.configPackageCourse;
        if (!pkg || !pkg.getCourse) return 0;
        var course = pkg.getCourse();
        return (course.segments || []).filter(segmentMatchesCoursePreviewEvent).length;
    }

    function countCoursePreviewLocationsForSelection() {
        var pkg = window.configPackageCourse;
        if (!pkg || !pkg.getCourseLocations) return 0;
        return pkg.getCourseLocations().filter(locationMatchesCoursePreviewEvent).length;
    }

    function applyCoursePreviewEventFilterToTables() {
        var pkg = window.configPackageCourse;
        if (!pkg || !pkg.getCourse) return;
        var course = pkg.getCourse();
        if (!course) return;
        var segIndices = [];
        var locIndices = [];
        (course.segments || []).forEach(function (seg, i) {
            if (segmentMatchesCoursePreviewEvent(seg)) segIndices.push(i);
        });
        (course.locations || []).forEach(function (loc, i) {
            if (locationMatchesCoursePreviewEvent(loc)) locIndices.push(i);
        });
        if (pkg.renderSegmentsListFiltered) pkg.renderSegmentsListFiltered(segIndices);
        if (pkg.renderLocationsListFiltered) pkg.renderLocationsListFiltered(locIndices);
        updateCoursePreviewBoundsStatus(
            segIndices.length,
            countCoursePreviewSegmentsForSelection(),
            locIndices.length,
            countCoursePreviewLocationsForSelection()
        );
    }

    function applyCoursePreviewBoundsToTables(visibleItems, stats) {
        var segIndices = [];
        var locIndices = [];
        var pkg = window.configPackageCourse;
        (visibleItems || []).forEach(function (item) {
            if (item.kind === 'segment') segIndices.push(item.index);
            else if (item.kind === 'location') locIndices.push(item.index);
        });
        if (pkg) {
            if (pkg.renderSegmentsListFiltered) pkg.renderSegmentsListFiltered(segIndices);
            if (pkg.renderLocationsListFiltered) pkg.renderLocationsListFiltered(locIndices);
        }
        updateCoursePreviewBoundsStatus(
            segIndices.length,
            countCoursePreviewSegmentsForSelection(),
            locIndices.length,
            countCoursePreviewLocationsForSelection()
        );
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
        renderLegLocationsBrowser();
        updateLegActionButtons();
        syncLegsTableBoundsFilterItems();
        renderAllLegRoutes();
        renderRecipeTable();
        renderTotals(data.recipe_lengths_km);
        renderWarnings(data.stitch_warnings);
        if (selectedLegId) {
            var still = (data.legs || []).some(function (c) { return c.id === selectedLegId; });
            if (still) {
                refreshSelectedLegMap({ preserveZoom: true, keepPinMode: true });
            } else {
                clearLegMap();
            }
        }
        var reloadPromise = null;
        if (
            window.configPackageCourse &&
            window.configPackageCourse.reloadCourse
        ) {
            reloadPromise = window.configPackageCourse.reloadCourse({ skipMapRefresh: true });
        } else if (
            window.configPackageCourse &&
            typeof window.configPackageCourse.renderSegmentsList === 'function'
        ) {
            window.configPackageCourse.renderSegmentsList();
        }
        if (reloadPromise && typeof reloadPromise.then === 'function') {
            reloadPromise.then(function () {
                if (
                    window.configPackageCourse &&
                    window.configPackageCourse.enrichCourseSegmentsFromLegLibrary
                ) {
                    window.configPackageCourse.enrichCourseSegmentsFromLegLibrary();
                }
            });
        } else if (
            window.configPackageCourse &&
            window.configPackageCourse.enrichCourseSegmentsFromLegLibrary
        ) {
            window.configPackageCourse.enrichCourseSegmentsFromLegLibrary();
        }
    }

    function isLegRouteEditActive() {
        return legReshapeActive || legTrimActive || legExtendActive;
    }

    function updateLegActionButtons() {
        var hasLegs = !!(libraryState && libraryState.legs && libraryState.legs.length);
        var exportAllBtn = document.getElementById('btn-export-all-legs');
        if (exportAllBtn) {
            exportAllBtn.disabled = !hasLegs;
        }
        var hasLeg = !!selectedLegId;
        var hasLine = !!(selectedLegLatLngs && selectedLegLatLngs.length >= 2);
        var routeEditActive = isLegRouteEditActive();
        var reshapeBtn = document.getElementById('btn-leg-reshape-route');
        var trimBtn = document.getElementById('btn-leg-trim-route');
        var extendBtn = document.getElementById('btn-leg-extend-route');
        var addLocBtn = document.getElementById('btn-leg-add-location');
        var routeEditActions = document.getElementById('leg-route-edit-actions');
        var extendActions = document.getElementById('leg-extend-actions');
        var drawBtn = document.getElementById('btn-leg-draw');
        if (drawBtn && legExtendActive) {
            drawBtn.style.display = 'none';
        } else if (drawBtn && !legDrawActive) {
            drawBtn.style.display = '';
        }
        if (reshapeBtn) {
            reshapeBtn.style.display = routeEditActive ? 'none' : '';
            reshapeBtn.disabled = !hasLeg || !hasLine || legTrimActive || legExtendActive;
            reshapeBtn.title = !hasLeg
                ? 'Select a leg in the table first'
                : !hasLine
                  ? 'Loading route on the map…'
                  : 'Simplify the route and drag yellow anchors to nudge the track (e.g. off a sidewalk)';
        }
        if (trimBtn) {
            trimBtn.style.display = routeEditActive ? 'none' : '';
            trimBtn.disabled = !hasLeg || !hasLine || legReshapeActive || legExtendActive;
            trimBtn.title = !hasLeg
                ? 'Select a leg in the table first'
                : !hasLine
                  ? 'Loading route on the map…'
                  : 'Drag the green or red end along the route to shorten the leg';
        }
        if (extendBtn) {
            extendBtn.style.display = routeEditActive ? 'none' : '';
            extendBtn.disabled = !hasLeg || !hasLine || legTrimActive || legReshapeActive;
            extendBtn.title = !hasLeg
                ? 'Select a leg in the table first'
                : !hasLine
                  ? 'Loading route on the map…'
                  : 'Click the map to lengthen the route beyond the start or end (snap to roads/trails)';
        }
        if (extendActions) {
            extendActions.style.display = legExtendActive ? 'inline-flex' : 'none';
        }
        if (routeEditActions) {
            routeEditActions.style.display = routeEditActive ? 'inline-flex' : 'none';
        }
        if (addLocBtn) {
            addLocBtn.disabled = !hasLeg || routeEditActive;
        }
        updateLegExtendButtons();
    }

    function copyLatLngs(latlngs) {
        return (latlngs || []).map(function (ll) {
            return [ll[0], ll[1]];
        });
    }

    /** Douglas–Peucker tolerance (m) when entering reshape — simplify to semantic vertices. */
    var LEG_RESHAPE_SIMPLIFY_TOLERANCE_M = 5;
    var LEG_RESHAPE_SIMPLIFY_MAX_VERTICES = 96;
    var LEG_RESHAPE_INSERT_MIN_GAP_T = 0.04;

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
        if (legExtendActive && legExtendSavedLatLngs) {
            return getLegExtendMergedLatLngs();
        }
        return selectedLegLatLngs;
    }

    function ensureAllLegRoutesPane(map) {
        if (!map.getPane(ALL_LEG_ROUTES_PANE)) {
            var pane = map.createPane(ALL_LEG_ROUTES_PANE);
            // Below the default overlay pane (400) so the selected leg always draws on top.
            pane.style.zIndex = 380;
        }
    }

    function removeAllLegRoutesLayer() {
        var map = window.courseMappingMap;
        if (map && allLegRoutesLayer) {
            map.removeLayer(allLegRoutesLayer);
        }
        allLegRoutesLayer = null;
    }

    function shouldShowLegRoutesWhileDrawing() {
        return !legDrawActive || legDrawTraceEnabled;
    }

    function applyLegDrawTraceVisibility() {
        if (!shouldShowLegRoutesWhileDrawing()) {
            removeAllLegRoutesLayer();
            return;
        }
        if (!allLegRoutesLayer) {
            renderAllLegRoutes();
        }
    }

    /** Draw every leg route as a muted background line so the full network is visible without a selection. */
    function renderAllLegRoutes() {
        var map = window.courseMappingMap;
        var hubMode = isOrgLegsHubMode();
        if (!map || (!isConfigPackageWorkspace() && !hubMode)) return;
        if (!shouldShowLegRoutesWhileDrawing()) {
            removeAllLegRoutesLayer();
            return;
        }
        var legs = (libraryState && libraryState.legs) || [];
        if (!legs.length) {
            removeAllLegRoutesLayer();
            return;
        }
        allLegRoutesFetchSeq += 1;
        var seq = allLegRoutesFetchSeq;
        var geomUrl =
            hubMode || usesOrgLegLibrary()
                ? '/api/org/legs/geometries'
                : apiBase() + '/segment-library/leg-geometries';
        fetch(geomUrl, { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (seq !== allLegRoutesFetchSeq || !data) return;
                if (!shouldShowLegRoutesWhileDrawing()) return;
                var mapNow = window.courseMappingMap;
                if (!mapNow) return;
                ensureAllLegRoutesPane(mapNow);
                removeAllLegRoutesLayer();
                var features = data.features || [];
                if (!features.length) return;
                var group = L.layerGroup();
                features.forEach(function (feature) {
                    var geom = feature.geometry || {};
                    var coords = geom.coordinates || [];
                    if (geom.type !== 'LineString' || coords.length < 2) return;
                    var latlngs = coords.map(function (c) { return [c[1], c[0]]; });
                    var props = feature.properties || {};
                    var legId = props.leg_id;
                    if (legId) {
                        try {
                            legBoundsCache[legId] = L.latLngBounds(latlngs);
                        } catch (e) { /* ignore */ }
                    }
                    var line = L.polyline(latlngs, {
                        pane: ALL_LEG_ROUTES_PANE,
                        color: '#9b8ec4',
                        weight: 3,
                        opacity: 0.7
                    });
                    var label = String(props.leg_label || legId || '');
                    if (label) {
                        line.bindTooltip(label, { sticky: true });
                    }
                    if (legId) {
                        line.on('click', function () {
                            if (legDrawActive || legExtendActive) return;
                            selectLegById(legId);
                        });
                    }
                    group.addLayer(line);
                });
                allLegRoutesLayer = group.addTo(mapNow);
            })
            .catch(function () { /* background layer is best-effort */ });
    }

    // ——— Draw a new leg (Issue #789) ———

    function legDrawHaversineKm(coords) {
        var total = 0;
        for (var i = 1; i < coords.length; i++) {
            var lon1 = coords[i - 1][0], lat1 = coords[i - 1][1];
            var lon2 = coords[i][0], lat2 = coords[i][1];
            var dLat = (lat2 - lat1) * Math.PI / 180;
            var dLon = (lon2 - lon1) * Math.PI / 180;
            var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon / 2) * Math.sin(dLon / 2);
            total += 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        }
        return total;
    }

    function legDrawProfile() {
        var sel = document.getElementById('leg-draw-profile');
        return sel ? sel.value : 'foot';
    }

    /** Anchor positions (clicked points) derived from the undo stack. */
    function legDrawAnchorIndices() {
        var idxs = [];
        var pos = -1;
        legDrawClickCounts.forEach(function (count) {
            pos += count;
            idxs.push(pos);
        });
        return idxs;
    }

    function updateLegDrawButtons() {
        var has = legDrawCoords.length > 0;
        var canFinish = legDrawCoords.length >= 2;
        var undoBtn = document.getElementById('btn-leg-draw-undo');
        var outbackBtn = document.getElementById('btn-leg-draw-outback');
        var clearBtn = document.getElementById('btn-leg-draw-clear');
        var finishBtn = document.getElementById('btn-leg-draw-finish');
        if (undoBtn) undoBtn.disabled = !legDrawClickCounts.length;
        if (outbackBtn) outbackBtn.disabled = !canFinish;
        if (clearBtn) clearBtn.disabled = !has;
        if (finishBtn) finishBtn.disabled = !canFinish;
        var distEl = document.getElementById('leg-draw-distance');
        if (distEl) {
            distEl.textContent = canFinish ? legDrawHaversineKm(legDrawCoords).toFixed(2) + ' km' : '';
        }
    }

    function renderLegDraw() {
        var map = window.courseMappingMap;
        if (!map) return;
        if (legDrawLayer) {
            map.removeLayer(legDrawLayer);
            legDrawLayer = null;
        }
        if (legDrawCoords.length) {
            var group = L.layerGroup();
            var latlngs = legDrawCoords.map(function (c) { return [c[1], c[0]]; });
            if (latlngs.length >= 2) {
                group.addLayer(L.polyline(latlngs, { color: '#e67e22', weight: 5, opacity: 0.9 }));
            }
            // Start marker + small anchors at each clicked point
            group.addLayer(L.circleMarker(latlngs[0], {
                radius: 7, color: '#27ae60', fillColor: '#27ae60', fillOpacity: 0.9, weight: 2
            }));
            legDrawAnchorIndices().forEach(function (idx) {
                if (idx <= 0 || idx >= latlngs.length) return;
                group.addLayer(L.circleMarker(latlngs[idx], {
                    radius: 4, color: '#e67e22', fillColor: '#fff', fillOpacity: 1, weight: 2
                }));
            });
            legDrawLayer = group.addTo(map);
        }
        updateLegDrawButtons();
    }

    function legDrawAppend(points) {
        if (!points.length) return;
        points.forEach(function (p) { legDrawCoords.push([p[0], p[1]]); });
        legDrawClickCounts.push(points.length);
        renderLegDraw();
    }

    function onLegDrawClick(e) {
        if (legDrawRoutingBusy) return;
        var toPoint = [e.latlng.lng, e.latlng.lat];
        var profile = legDrawProfile();
        var fromPoint = legDrawCoords.length ? legDrawCoords[legDrawCoords.length - 1] : null;
        if (!fromPoint || profile === 'off') {
            legDrawAppend([toPoint]);
            return;
        }
        legDrawRoutingBusy = true;
        setLegStatus('Routing…');
        var url = '/api/courses/route/segment?from_ll=' + encodeURIComponent(fromPoint[0] + ',' + fromPoint[1]) +
            '&to_ll=' + encodeURIComponent(toPoint[0] + ',' + toPoint[1]) +
            '&profile=' + encodeURIComponent(profile);
        fetch(url, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                legDrawRoutingBusy = false;
                if (!legDrawActive) return;
                if (data.ok && data.coordinates && data.coordinates.length > 1) {
                    legDrawAppend(data.coordinates.slice(1));
                    setLegStatus('Drawing leg — click to extend, Undo steps back one click.');
                } else {
                    legDrawAppend([toPoint]);
                    setLegStatus('No snapped route found; added a straight line instead.', true);
                }
            })
            .catch(function () {
                legDrawRoutingBusy = false;
                if (!legDrawActive) return;
                legDrawAppend([toPoint]);
                setLegStatus('Routing unavailable; added a straight line instead.', true);
            });
    }

    function legDrawUndo() {
        if (!legDrawClickCounts.length) return;
        var count = legDrawClickCounts.pop();
        legDrawCoords.length = Math.max(0, legDrawCoords.length - count);
        renderLegDraw();
    }

    function legDrawOutAndBack() {
        if (legDrawCoords.length < 2) return;
        var back = legDrawCoords.slice(0, -1).reverse();
        legDrawAppend(back);
        setLegStatus('Out & back added — route now returns to the start (one Undo removes it).');
    }

    function legDrawClear() {
        legDrawCoords = [];
        legDrawClickCounts = [];
        renderLegDraw();
        setLegStatus('Drawing cleared — click the map to start again.');
    }

    function startLegDrawMode() {
        var map = window.courseMappingMap;
        if (!map || legDrawActive) return;
        stopLegExtendRoute(true);
        if (!usesOrgLegLibrary()) {
            setLegStatus('Drawing a new leg requires the organization leg library.', true);
            return;
        }
        clearLegMap();
        legDrawActive = true;
        legDrawCoords = [];
        legDrawClickCounts = [];
        pendingDrawCoordinates = null;
        var drawBtn = document.getElementById('btn-leg-draw');
        if (drawBtn) drawBtn.classList.add('active');
        var actions = document.getElementById('leg-draw-actions');
        if (actions) actions.style.display = 'inline-flex';
        var container = document.getElementById('course-mapping-map');
        if (container) container.classList.add('leg-draw-mode');
        legDrawClickHandler = onLegDrawClick;
        map.on('click', legDrawClickHandler);
        var traceInput = document.getElementById('leg-draw-trace');
        legDrawTraceEnabled = traceInput ? !!traceInput.checked : false;
        applyLegDrawTraceVisibility();
        renderLegDraw();
        setTimeout(function () {
            if (map && legDrawActive) map.invalidateSize();
        }, 120);
        setLegStatus('Drawing leg — click along the route. Clicks snap to roads/trails (change with the Snap menu).'
            + (legDrawTraceEnabled ? ' Trace is on: existing legs shown for reference.' : ' Check Trace to show existing legs underneath.'));
    }

    function stopLegDrawMode() {
        var map = window.courseMappingMap;
        legDrawActive = false;
        legDrawRoutingBusy = false;
        if (map && legDrawClickHandler) {
            map.off('click', legDrawClickHandler);
        }
        legDrawClickHandler = null;
        if (map && legDrawLayer) {
            map.removeLayer(legDrawLayer);
        }
        legDrawLayer = null;
        legDrawCoords = [];
        legDrawClickCounts = [];
        var drawBtn = document.getElementById('btn-leg-draw');
        if (drawBtn) drawBtn.classList.remove('active');
        var actions = document.getElementById('leg-draw-actions');
        if (actions) actions.style.display = 'none';
        var container = document.getElementById('course-mapping-map');
        if (container) container.classList.remove('leg-draw-mode');
        updateLegDrawButtons();
        renderAllLegRoutes();
        if (map) {
            setTimeout(function () { map.invalidateSize(); }, 120);
        }
    }

    function finishLegDraw() {
        if (legDrawCoords.length < 2) {
            setLegStatus('Draw at least two points before finishing.', true);
            return;
        }
        pendingDrawCoordinates = legDrawCoords.slice();
        stopLegDrawMode();
        setLegStatus('');
        openLegEditor(null);
    }

    // ——— Extend selected leg at start or end ———

    function legExtendProfile() {
        var sel = document.getElementById('leg-extend-profile');
        return sel ? sel.value : 'foot';
    }

    function legExtendAnchorLonLat() {
        if (!legExtendSavedLatLngs || !legExtendSavedLatLngs.length) {
            return null;
        }
        if (legExtendFromEnd) {
            var endLl = legExtendSavedLatLngs[legExtendSavedLatLngs.length - 1];
            return [endLl[1], endLl[0]];
        }
        var startLl = legExtendSavedLatLngs[0];
        return [startLl[1], startLl[0]];
    }

    function legExtendInnerAnchorLonLat() {
        if (legExtendFromEnd) {
            if (!legExtendNewCoords.length) {
                return legExtendAnchorLonLat();
            }
            return legExtendNewCoords[legExtendNewCoords.length - 1];
        }
        if (!legExtendNewCoords.length) {
            return legExtendAnchorLonLat();
        }
        return legExtendNewCoords[0];
    }

    function getLegExtendMergedLatLngs() {
        var base = copyLatLngs(legExtendSavedLatLngs || []);
        if (!legExtendNewCoords.length) {
            return base;
        }
        var ext = legExtendNewCoords.map(function (c) {
            return [c[1], c[0]];
        });
        if (legExtendFromEnd) {
            return base.concat(ext);
        }
        return ext.concat(base);
    }

    function legExtendMergedKm() {
        var merged = getLegExtendMergedLatLngs();
        if (merged.length < 2) {
            return 0;
        }
        var coords = merged.map(function (ll) {
            return [ll[1], ll[0]];
        });
        return legDrawHaversineKm(coords);
    }

    function updateLegExtendButtons() {
        var hasExtension = legExtendNewCoords.length > 0;
        var undoBtn = document.getElementById('btn-leg-extend-undo');
        var clearBtn = document.getElementById('btn-leg-extend-clear');
        if (undoBtn) undoBtn.disabled = !legExtendClickCounts.length;
        if (clearBtn) clearBtn.disabled = !hasExtension;
        var distEl = document.getElementById('leg-extend-distance');
        if (distEl) {
            distEl.textContent =
                legExtendActive && legExtendSavedLatLngs
                    ? legExtendMergedKm().toFixed(2) + ' km'
                    : '';
        }
        var anchorSel = document.getElementById('leg-extend-anchor');
        if (anchorSel) {
            anchorSel.disabled = hasExtension;
        }
    }

    function renderLegExtend() {
        var map = window.courseMappingMap;
        if (!map || !legExtendActive || !legExtendSavedLatLngs) {
            return;
        }
        var merged = getLegExtendMergedLatLngs();
        selectedLegLatLngs = merged;
        setLegRoutePolyline(merged);
        if (legExtendLayer) {
            map.removeLayer(legExtendLayer);
            legExtendLayer = null;
        }
        if (legExtendNewCoords.length) {
            var group = L.layerGroup();
            var extLatLngs = legExtendNewCoords.map(function (c) {
                return [c[1], c[0]];
            });
            if (extLatLngs.length >= 2) {
                group.addLayer(
                    L.polyline(extLatLngs, { color: '#e67e22', weight: 5, opacity: 0.92 })
                );
            }
            var anchor = legExtendFromEnd
                ? legExtendSavedLatLngs[legExtendSavedLatLngs.length - 1]
                : legExtendSavedLatLngs[0];
            group.addLayer(
                L.circleMarker(anchor, {
                    radius: 6,
                    color: legExtendFromEnd ? '#c0392b' : '#27ae60',
                    fillColor: legExtendFromEnd ? '#c0392b' : '#27ae60',
                    fillOpacity: 0.9,
                    weight: 2
                })
            );
            legExtendLayer = group.addTo(map);
        }
        updateLegExtendButtons();
    }

    function legExtendAppendSegment(coords) {
        if (!coords || !coords.length) {
            return;
        }
        var slice = legExtendNewCoords.length ? coords.slice(1) : coords.slice(1);
        if (!slice.length && coords.length === 1) {
            slice = coords.slice();
        }
        if (!slice.length) {
            return;
        }
        slice.forEach(function (p) {
            legExtendNewCoords.push([p[0], p[1]]);
        });
        legExtendClickCounts.push(slice.length);
        renderLegExtend();
    }

    function legExtendPrependSegment(coords) {
        if (!coords || !coords.length) {
            return;
        }
        var slice = coords.slice(0, -1);
        if (!slice.length && coords.length === 1) {
            slice = coords.slice();
        }
        if (!slice.length) {
            return;
        }
        legExtendNewCoords = slice.concat(legExtendNewCoords);
        legExtendClickCounts.unshift(slice.length);
        renderLegExtend();
    }

    function onLegExtendClick(e) {
        if (legExtendRoutingBusy) {
            return;
        }
        var profile = legExtendProfile();
        var toPoint = [e.latlng.lng, e.latlng.lat];
        var fromPoint;
        var routeToPoint;
        if (legExtendFromEnd) {
            fromPoint = legExtendInnerAnchorLonLat();
            routeToPoint = toPoint;
        } else {
            fromPoint = toPoint;
            routeToPoint = legExtendInnerAnchorLonLat();
        }
        if (!fromPoint || !routeToPoint) {
            return;
        }
        if (profile === 'off') {
            if (legExtendFromEnd) {
                legExtendAppendSegment([fromPoint, routeToPoint]);
            } else {
                legExtendPrependSegment([fromPoint, routeToPoint]);
            }
            setLegStatus(
                'Extending from ' +
                    (legExtendFromEnd ? 'end' : 'start') +
                    ' — click to add more, Confirm to save.'
            );
            return;
        }
        legExtendRoutingBusy = true;
        setLegStatus('Routing…');
        var url =
            '/api/courses/route/segment?from_ll=' +
            encodeURIComponent(fromPoint[0] + ',' + fromPoint[1]) +
            '&to_ll=' +
            encodeURIComponent(routeToPoint[0] + ',' + routeToPoint[1]) +
            '&profile=' +
            encodeURIComponent(profile);
        fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                legExtendRoutingBusy = false;
                if (!legExtendActive) {
                    return;
                }
                if (data.ok && data.coordinates && data.coordinates.length > 1) {
                    if (legExtendFromEnd) {
                        legExtendAppendSegment(data.coordinates);
                    } else {
                        legExtendPrependSegment(data.coordinates);
                    }
                    setLegStatus(
                        'Extending from ' +
                            (legExtendFromEnd ? 'end' : 'start') +
                            ' — click to add more, Confirm to save.'
                    );
                } else {
                    if (legExtendFromEnd) {
                        legExtendAppendSegment([fromPoint, routeToPoint]);
                    } else {
                        legExtendPrependSegment([fromPoint, routeToPoint]);
                    }
                    setLegStatus('No snapped route found; added a straight segment instead.', true);
                }
            })
            .catch(function () {
                legExtendRoutingBusy = false;
                if (!legExtendActive) {
                    return;
                }
                if (legExtendFromEnd) {
                    legExtendAppendSegment([fromPoint, routeToPoint]);
                } else {
                    legExtendPrependSegment([fromPoint, routeToPoint]);
                }
                setLegStatus('Routing unavailable; added a straight segment instead.', true);
            });
    }

    function legExtendUndo() {
        if (!legExtendClickCounts.length) {
            return;
        }
        var count = legExtendClickCounts.pop();
        if (legExtendFromEnd) {
            legExtendNewCoords.length = Math.max(0, legExtendNewCoords.length - count);
        } else {
            legExtendNewCoords = legExtendNewCoords.slice(count);
        }
        renderLegExtend();
        setLegStatus(
            legExtendNewCoords.length
                ? 'Extension undo — click to continue, Confirm to save.'
                : 'Extension cleared — click the map to extend the route.'
        );
    }

    function legExtendClearExtension() {
        legExtendNewCoords = [];
        legExtendClickCounts = [];
        renderLegExtend();
        setLegStatus('Extension cleared — click the map to extend the route.');
    }

    function stopLegExtendRoute(discard) {
        var map = window.courseMappingMap;
        if (!legExtendActive && !legExtendSavedLatLngs) {
            return;
        }
        legExtendActive = false;
        legExtendRoutingBusy = false;
        if (map && legExtendClickHandler) {
            map.off('click', legExtendClickHandler);
        }
        legExtendClickHandler = null;
        if (map && legExtendLayer) {
            map.removeLayer(legExtendLayer);
            legExtendLayer = null;
        }
        if (discard && legExtendSavedLatLngs) {
            selectedLegLatLngs = copyLatLngs(legExtendSavedLatLngs);
            setLegRoutePolyline(selectedLegLatLngs);
        }
        legExtendSavedLatLngs = null;
        legExtendNewCoords = [];
        legExtendClickCounts = [];
        var container = document.getElementById('course-mapping-map');
        if (container) {
            container.classList.remove('leg-extend-mode');
        }
        var extendBtn = document.getElementById('btn-leg-extend-route');
        if (extendBtn) {
            extendBtn.classList.remove('active');
        }
        updateLegActionButtons();
    }

    function startLegExtendRoute() {
        if (!selectedLegId) {
            setLegStatus('Select a leg in the table first.', true);
            return;
        }
        if (!selectedLegLatLngs || selectedLegLatLngs.length < 2) {
            setLegStatus('Wait for the leg route to load on the map.', true);
            return;
        }
        stopLegReshapeRoute(true);
        stopLegTrimRoute(true);
        if (addLocationOnMap) {
            if (!pendingLegLocations.length) {
                stopLegLocationPinMode();
            } else {
                setLegStatus('Save or cancel pending locations before extending the route.', true);
                return;
            }
        }
        stopLegExtendRoute(true);
        var anchorSel = document.getElementById('leg-extend-anchor');
        legExtendFromEnd = !anchorSel || anchorSel.value !== 'start';
        legExtendSavedLatLngs = copyLatLngs(selectedLegLatLngs);
        legExtendNewCoords = [];
        legExtendClickCounts = [];
        legExtendActive = true;
        var map = window.courseMappingMap;
        var container = document.getElementById('course-mapping-map');
        if (container) {
            container.classList.add('leg-extend-mode');
        }
        legExtendClickHandler = onLegExtendClick;
        if (map) {
            map.on('click', legExtendClickHandler);
        }
        var extendBtn = document.getElementById('btn-leg-extend-route');
        if (extendBtn) {
            extendBtn.classList.add('active');
        }
        updateLegActionButtons();
        renderLegExtend();
        setLegStatus(
            'Extending from ' +
                (legExtendFromEnd ? 'end' : 'start') +
                ' — click along roads/trails to lengthen the leg. Confirm to save, Cancel to discard.'
        );
    }

    function confirmLegExtendRoute() {
        if (!legExtendActive || !selectedLegId || !legExtendSavedLatLngs) {
            return;
        }
        if (!legExtendClickCounts.length) {
            setLegStatus('Click the map to extend the route, then Confirm.', true);
            return;
        }
        var merged = getLegExtendMergedLatLngs();
        if (merged.length < 2) {
            setLegStatus('The leg must keep at least two route points.', true);
            return;
        }
        var coordinates = merged.map(function (ll) {
            return [ll[1], ll[0]];
        });
        setLegStatus('Saving extended route…');
        fetch(legGeometryUrl(selectedLegId), {
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
                return refreshLibraryAfterGeometrySave(payload.data);
            })
            .then(function () {
                stopLegExtendRoute(false);
                selectLegById(selectedLegId, { preserveZoom: true, keepPinMode: true });
                setLegStatus('Extended route saved for leg ' + selectedLegId + '.');
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function setLegRoutePolyline(latlngs, opts) {
        opts = opts || {};
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
            opacity: 0.85,
            interactive: opts.interactive !== false
        }).addTo(map);
    }

    function clearLegReshapeHitLayer() {
        var map = window.courseMappingMap;
        if (map && legReshapeHitLayer) {
            map.removeLayer(legReshapeHitLayer);
            legReshapeHitLayer = null;
        }
    }

    function setLegReshapeMapMode(active) {
        var container = document.getElementById('course-mapping-map');
        if (!container) {
            return;
        }
        if (active) {
            container.classList.add('leg-reshape-mode');
        } else {
            container.classList.remove('leg-reshape-mode');
        }
    }

    function insertLegReshapeAnchorAt(lat, lon) {
        var latlngs = legReshapeDraftLatLngs;
        if (!legReshapeActive || !latlngs || latlngs.length < 2) {
            return false;
        }
        if (latlngs.length >= LEG_RESHAPE_SIMPLIFY_MAX_VERTICES) {
            setLegStatus(
                'Maximum ' +
                    LEG_RESHAPE_SIMPLIFY_MAX_VERTICES +
                    ' anchors reached. Confirm or remove a pin (Alt+click) before adding more.',
                true
            );
            return false;
        }
        var best = findBestSegmentProjection(lat, lon, latlngs, 0, latlngs.length - 2);
        if (
            !best ||
            best.t <= LEG_RESHAPE_INSERT_MIN_GAP_T ||
            best.t >= 1 - LEG_RESHAPE_INSERT_MIN_GAP_T
        ) {
            return false;
        }
        var insertIdx = best.segIdx + 1;
        latlngs.splice(insertIdx, 0, [
            Math.round(best.lat * 1e6) / 1e6,
            Math.round(best.lon * 1e6) / 1e6
        ]);
        legReshapeAnchorIndices = allVertexAnchorIndices(latlngs.length);
        selectedLegLatLngs = latlngs;
        refreshLegReshapeDisplay();
        setLegStatus(
            latlngs.length +
                ' anchors — drag yellow pins to nudge, click the purple route between pins to add another, Alt+click a pin to remove it.'
        );
        return true;
    }

    function removeLegReshapeAnchorAt(idx) {
        var latlngs = legReshapeDraftLatLngs;
        if (!legReshapeActive || !latlngs || latlngs.length <= 2) {
            return false;
        }
        if (idx <= 0 || idx >= latlngs.length - 1) {
            return false;
        }
        latlngs.splice(idx, 1);
        legReshapeAnchorIndices = allVertexAnchorIndices(latlngs.length);
        selectedLegLatLngs = latlngs;
        refreshLegReshapeDisplay();
        setLegStatus(
            latlngs.length +
                ' anchors — drag yellow pins to nudge, click the purple route between pins to add another, Alt+click a pin to remove it.'
        );
        return true;
    }

    function onLegReshapeRouteClick(ev) {
        L.DomEvent.stopPropagation(ev);
        insertLegReshapeAnchorAt(ev.latlng.lat, ev.latlng.lng);
    }

    function drawLegReshapeHitTarget() {
        var map = window.courseMappingMap;
        var latlngs = legReshapeDraftLatLngs;
        if (!map || !latlngs || latlngs.length < 2 || !legReshapeActive) {
            return;
        }
        clearLegReshapeHitLayer();
        legReshapeHitLayer = L.polyline(latlngs, {
            color: '#8e44ad',
            weight: 14,
            opacity: 0,
            interactive: true,
            className: 'leg-reshape-hit-line'
        });
        legReshapeHitLayer.on('click', onLegReshapeRouteClick);
        legReshapeHitLayer.addTo(map);
    }

    function refreshLegReshapeDisplay() {
        if (!legReshapeActive || !legReshapeDraftLatLngs) {
            return;
        }
        setLegRoutePolyline(legReshapeDraftLatLngs, { interactive: false });
        drawLegReshapeHitTarget();
        drawLegReshapeAnchors();
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
                setLegRoutePolyline(legReshapeDraftLatLngs, { interactive: false });
                drawLegReshapeHitTarget();
            });
            marker.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                if (e.originalEvent && e.originalEvent.altKey) {
                    removeLegReshapeAnchorAt(idx);
                }
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
        clearLegReshapeHitLayer();
        clearLegReshapeAnchorLayer();
        setLegReshapeMapMode(false);
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
        stopLegExtendRoute(true);
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
        setLegReshapeMapMode(true);
        refreshLegReshapeDisplay();
        var reshapeBtn = document.getElementById('btn-leg-reshape-route');
        if (reshapeBtn) {
            reshapeBtn.classList.add('active');
        }
        updateLegActionButtons();
        var anchorCount = legReshapeAnchorIndices.length;
        var statusMsg =
            'Route simplified to ' +
            anchorCount +
            ' anchor' +
            (anchorCount === 1 ? '' : 's') +
            ' (from ' +
            originalCount +
            ' track points). Drag yellow pins to nudge; click the purple route between pins to add another; Alt+click a pin to remove it. Confirm saves, Cancel restores the original.';
        if (originalCount > anchorCount && simplified.toleranceM > LEG_RESHAPE_SIMPLIFY_TOLERANCE_M) {
            statusMsg +=
                ' (used ' + simplified.toleranceM + ' m simplify tolerance to keep the map usable).';
        }
        setLegStatus(statusMsg);
    }

    function refreshLibraryAfterGeometrySave(data) {
        if (usesOrgLegLibrary()) {
            return afterLegLibraryMutation(data);
        }
        applyLibraryState(data);
        return Promise.resolve();
    }

    function confirmLegReshapeRoute() {
        if (!legReshapeActive || !selectedLegId || !legReshapeDraftLatLngs) {
            return;
        }
        var coordinates = legReshapeDraftLatLngs.map(function (ll) {
            return [ll[1], ll[0]];
        });
        setLegStatus('Saving route…');
        fetch(legGeometryUrl(selectedLegId), {
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
                return refreshLibraryAfterGeometrySave(payload.data);
            })
            .then(function () {
                legReshapeActive = false;
                legReshapeDraftLatLngs = null;
                legReshapeAnchorIndices = null;
                legReshapeSavedLatLngs = null;
                clearLegReshapeHitLayer();
                clearLegReshapeAnchorLayer();
                setLegReshapeMapMode(false);
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
        var base = legTrimSavedLatLngs;
        var s = legTrimStartIdx;
        var e = legTrimEndIdx;
        var draft;
        if (legTrimStartOverride) {
            draft = [[legTrimStartOverride[0], legTrimStartOverride[1]]].concat(base.slice(s + 1, e + 1));
        } else {
            draft = base.slice(s, e + 1);
        }
        if (legTrimEndOverride) {
            if (legTrimStartOverride) {
                draft = [[legTrimStartOverride[0], legTrimStartOverride[1]]]
                    .concat(base.slice(s + 1, e))
                    .concat([[legTrimEndOverride[0], legTrimEndOverride[1]]]);
            } else {
                draft = base.slice(s, e).concat([[legTrimEndOverride[0], legTrimEndOverride[1]]]);
            }
        }
        return draft.length >= 2 ? draft : [];
    }

    var TRIM_VERTEX_EPS = 1e-6;

    function findBestSegmentProjection(lat, lon, latlngs, minSegIdx, maxSegIdx) {
        if (!latlngs || latlngs.length < 2) {
            return null;
        }
        minSegIdx = Math.max(0, minSegIdx);
        maxSegIdx = Math.min(latlngs.length - 2, maxSegIdx);
        if (maxSegIdx < minSegIdx) {
            return null;
        }
        var best = null;
        var i;
        for (i = minSegIdx; i <= maxSegIdx; i++) {
            var proj = projectPointOntoSegment(
                lat,
                lon,
                latlngs[i][0],
                latlngs[i][1],
                latlngs[i + 1][0],
                latlngs[i + 1][1]
            );
            if (!best || proj.dist2 < best.dist2) {
                best = {
                    segIdx: i,
                    t: proj.t,
                    lat: proj.lat,
                    lon: proj.lon,
                    dist2: proj.dist2
                };
            }
        }
        return best;
    }

    function trimProjectionToEndpoint(best) {
        if (!best) {
            return { idx: 0, override: null };
        }
        if (best.t <= TRIM_VERTEX_EPS) {
            return { idx: best.segIdx, override: null };
        }
        if (best.t >= 1 - TRIM_VERTEX_EPS) {
            return { idx: best.segIdx + 1, override: null };
        }
        return { idx: best.segIdx, override: [best.lat, best.lon] };
    }

    function applyStartTrimDrag(lat, lon) {
        var base = legTrimSavedLatLngs;
        if (!base) {
            return false;
        }
        var maxSeg = base.length - 2;
        if (legTrimEndOverride) {
            maxSeg = Math.min(maxSeg, legTrimEndIdx - 1);
        } else {
            maxSeg = Math.min(maxSeg, legTrimEndIdx - 2);
        }
        if (maxSeg < 0) {
            return false;
        }
        var best = findBestSegmentProjection(lat, lon, base, 0, maxSeg);
        var next = trimProjectionToEndpoint(best);
        var prevStartIdx = legTrimStartIdx;
        var prevStartOverride = legTrimStartOverride;
        legTrimStartIdx = next.idx;
        legTrimStartOverride = next.override;
        if (getLegTrimDraftLatLngs().length < 2) {
            legTrimStartIdx = prevStartIdx;
            legTrimStartOverride = prevStartOverride;
            return false;
        }
        return true;
    }

    function applyEndTrimDrag(lat, lon) {
        var base = legTrimSavedLatLngs;
        if (!base) {
            return false;
        }
        var minSeg = legTrimStartOverride ? legTrimStartIdx : legTrimStartIdx;
        var maxSeg = base.length - 2;
        var best = findBestSegmentProjection(lat, lon, base, minSeg, maxSeg);
        var next = trimProjectionToEndpoint(best);
        var prevEndIdx = legTrimEndIdx;
        var prevEndOverride = legTrimEndOverride;
        legTrimEndIdx = next.idx;
        legTrimEndOverride = next.override;
        if (getLegTrimDraftLatLngs().length < 2) {
            legTrimEndIdx = prevEndIdx;
            legTrimEndOverride = prevEndOverride;
            return false;
        }
        return true;
    }

    function projectPointOntoSegment(lat, lon, lat1, lon1, lat2, lon2) {
        var dx = lon2 - lon1;
        var dy = lat2 - lat1;
        var len2 = dx * dx + dy * dy;
        if (len2 < 1e-18) {
            var dlat0 = lat - lat1;
            var dlon0 = lon - lon1;
            return { t: 0, lat: lat1, lon: lon1, dist2: dlat0 * dlat0 + dlon0 * dlon0 };
        }
        var t = ((lon - lon1) * dx + (lat - lat1) * dy) / len2;
        t = Math.max(0, Math.min(1, t));
        var plat = lat1 + t * dy;
        var plon = lon1 + t * dx;
        var dlat = lat - plat;
        var dlon = lon - plon;
        return { t: t, lat: plat, lon: plon, dist2: dlat * dlat + dlon * dlon };
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
        legTrimStartMarker = null;
        legTrimEndMarker = null;
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
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });
        }

        function onTrimDrag(role) {
            return function (ev) {
                var pos = ev.target.getLatLng();
                if (role === 'start') {
                    applyStartTrimDrag(pos.lat, pos.lng);
                } else {
                    applyEndTrimDrag(pos.lat, pos.lng);
                }
                updateLegTrimDisplay({
                    refreshMarkers: false,
                    dragMarker: ev.target,
                    dragRole: role
                });
            };
        }

        var startLl = draft[0];
        var endLl = draft[draft.length - 1];
        var startMarker = L.marker([startLl[0], startLl[1]], {
            icon: trimEndpointIcon('start'),
            draggable: true,
            autoPan: true,
            zIndexOffset: 2000
        });
        startMarker.on('drag', onTrimDrag('start'));
        startMarker.on('click', function (e) {
            L.DomEvent.stopPropagation(e);
        });
        startMarker.bindTooltip('Start — drag along route', { permanent: false });
        startMarker.addTo(legTrimMarkerLayer);
        legTrimStartMarker = startMarker;

        var endMarker = L.marker([endLl[0], endLl[1]], {
            icon: trimEndpointIcon('end'),
            draggable: true,
            autoPan: true,
            zIndexOffset: 2000
        });
        endMarker.on('drag', onTrimDrag('end'));
        endMarker.on('click', function (e) {
            L.DomEvent.stopPropagation(e);
        });
        endMarker.bindTooltip('End — drag along route', { permanent: false });
        endMarker.addTo(legTrimMarkerLayer);
        legTrimEndMarker = endMarker;

        legTrimMarkerLayer.addTo(map);
    }

    function positionLegTrimEndpointMarkers() {
        var base = legTrimSavedLatLngs;
        if (!base || !legTrimStartMarker || !legTrimEndMarker) {
            return;
        }
        var startLl = legTrimStartOverride || base[legTrimStartIdx];
        var endLl = legTrimEndOverride || base[legTrimEndIdx];
        legTrimStartMarker.setLatLng([startLl[0], startLl[1]]);
        legTrimEndMarker.setLatLng([endLl[0], endLl[1]]);
    }

    function updateLegTrimDisplay(opts) {
        opts = opts || {};
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
        setLegRoutePolyline(draft, { interactive: false });
        clearLegTrimGhostLayer();
        if (
            legTrimStartIdx > 0 ||
            legTrimStartOverride ||
            legTrimEndIdx < base.length - 1 ||
            legTrimEndOverride
        ) {
            legTrimGhostLayer = L.layerGroup();
            var ghostStyle = {
                color: '#7f8c8d',
                weight: 4,
                opacity: 0.55,
                dashArray: '8,10',
                interactive: false
            };
            if (legTrimStartIdx > 0 || legTrimStartOverride) {
                var ghostStartPts = legTrimStartOverride
                    ? base.slice(0, legTrimStartIdx).concat([legTrimStartOverride])
                    : base.slice(0, legTrimStartIdx + 1);
                if (legTrimStartOverride && ghostStartPts.length < 2) {
                    ghostStartPts = [base[0]].concat([legTrimStartOverride]);
                }
                if (ghostStartPts.length >= 2) {
                    L.polyline(ghostStartPts, ghostStyle).addTo(legTrimGhostLayer);
                }
            }
            if (legTrimEndIdx < base.length - 1 || legTrimEndOverride) {
                var ghostEndPts = legTrimEndOverride
                    ? [legTrimEndOverride].concat(base.slice(legTrimEndIdx + 1))
                    : base.slice(legTrimEndIdx);
                if (legTrimEndOverride && ghostEndPts.length < 2) {
                    ghostEndPts = [legTrimEndOverride].concat([base[base.length - 1]]);
                }
                if (ghostEndPts.length >= 2) {
                    L.polyline(ghostEndPts, ghostStyle).addTo(legTrimGhostLayer);
                }
            }
            legTrimGhostLayer.addTo(map);
        }
        if (opts.dragMarker && opts.dragRole) {
            var dragDraft = getLegTrimDraftLatLngs();
            if (opts.dragRole === 'start' && dragDraft.length) {
                opts.dragMarker.setLatLng(dragDraft[0]);
            } else if (opts.dragRole === 'end' && dragDraft.length) {
                opts.dragMarker.setLatLng(dragDraft[dragDraft.length - 1]);
            }
        } else if (opts.refreshMarkers === false) {
            positionLegTrimEndpointMarkers();
        } else {
            drawLegTrimEndpointMarkers();
        }
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
        legTrimStartOverride = null;
        legTrimEndOverride = null;
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

    function filterLocationsForTrim(locations, baseLatLngs, startIdx, endIdx, startOverride, endOverride) {
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
            if (startOverride) {
                if (idx < startIdx) {
                    return false;
                }
                if (idx === startIdx && startIdx < baseLatLngs.length - 1) {
                    var startLocProj = projectPointOntoSegment(
                        loc.lat,
                        loc.lon,
                        baseLatLngs[startIdx][0],
                        baseLatLngs[startIdx][1],
                        baseLatLngs[startIdx + 1][0],
                        baseLatLngs[startIdx + 1][1]
                    );
                    var startCutProj = projectPointOntoSegment(
                        startOverride[0],
                        startOverride[1],
                        baseLatLngs[startIdx][0],
                        baseLatLngs[startIdx][1],
                        baseLatLngs[startIdx + 1][0],
                        baseLatLngs[startIdx + 1][1]
                    );
                    return startLocProj.t >= startCutProj.t - TRIM_VERTEX_EPS;
                }
            } else if (idx < startIdx) {
                return false;
            }
            if (endOverride) {
                if (idx > endIdx) {
                    return false;
                }
                if (idx === endIdx && endIdx < baseLatLngs.length - 1) {
                    var locProj = projectPointOntoSegment(
                        loc.lat,
                        loc.lon,
                        baseLatLngs[endIdx][0],
                        baseLatLngs[endIdx][1],
                        baseLatLngs[endIdx + 1][0],
                        baseLatLngs[endIdx + 1][1]
                    );
                    var endProj = projectPointOntoSegment(
                        endOverride[0],
                        endOverride[1],
                        baseLatLngs[endIdx][0],
                        baseLatLngs[endIdx][1],
                        baseLatLngs[endIdx + 1][0],
                        baseLatLngs[endIdx + 1][1]
                    );
                    return locProj.t <= endProj.t + TRIM_VERTEX_EPS;
                }
            } else if (idx > endIdx) {
                return false;
            }
            return true;
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
        stopLegExtendRoute(true);
        stopLegTrimRoute(true);
        legTrimSavedLatLngs = copyLatLngs(selectedLegLatLngs);
        legTrimStartIdx = 0;
        legTrimEndIdx = legTrimSavedLatLngs.length - 1;
        legTrimStartOverride = null;
        legTrimEndOverride = null;
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
                'Handles snap to the route line for fine adjustments. ' +
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
            legTrimEndIdx,
            legTrimStartOverride,
            legTrimEndOverride
        );
        var removedLocCount = priorLocations.length - filteredLocations.length;
        setLegStatus('Saving trimmed route…');
        fetch(legGeometryUrl(selectedLegId), {
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
                return refreshLibraryAfterGeometrySave(payload.data).then(function () {
                    if (removedLocCount > 0) {
                        return saveLegLocations(selectedLegId, filteredLocations);
                    }
                });
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
        } else if (legExtendActive) {
            confirmLegExtendRoute();
        } else if (legReshapeActive) {
            confirmLegReshapeRoute();
        }
    }

    function cancelLegRouteEdit() {
        if (legTrimActive) {
            stopLegTrimRoute(true);
            setLegStatus('Route trim cancelled.');
        } else if (legExtendActive) {
            stopLegExtendRoute(true);
            setLegStatus('Route extension cancelled.');
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

    var legLocationPopupWheelZoomWasEnabled = false;

    function disableMapWheelForLegLocationPopup(map) {
        if (!map || !map.scrollWheelZoom) return;
        legLocationPopupWheelZoomWasEnabled = map.scrollWheelZoom.enabled();
        if (legLocationPopupWheelZoomWasEnabled) {
            map.scrollWheelZoom.disable();
        }
    }

    function restoreMapWheelForLegLocationPopup(map) {
        if (!map || !map.scrollWheelZoom || !legLocationPopupWheelZoomWasEnabled) return;
        map.scrollWheelZoom.enable();
        legLocationPopupWheelZoomWasEnabled = false;
    }

    function legLocationPopupChromeObstacles(map) {
        var container = map.getContainer();
        var rects = [];
        var toolbar = document.getElementById('leg-map-toolbar');
        if (toolbar && toolbar.offsetParent !== null) {
            rects.push(toolbar.getBoundingClientRect());
        }
        var zoom = container.querySelector('.leaflet-control-zoom');
        if (zoom) {
            rects.push(zoom.getBoundingClientRect());
        }
        return rects;
    }

    function legLocationPopupAutoPanPaddingTopLeft(map) {
        var padX = 48;
        var padY = 56;
        var container = map.getContainer();
        var mapRect = container.getBoundingClientRect();
        var toolbar = document.getElementById('leg-map-toolbar');
        if (toolbar && toolbar.offsetParent !== null) {
            var toolbarRect = toolbar.getBoundingClientRect();
            padY = Math.max(padY, toolbarRect.bottom - mapRect.top + 8);
        }
        return L.point(padX, Math.min(padY, 120));
    }

    function legLocationPopupRectsOverlap(a, b) {
        return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
    }

    function nudgeLegLocationPopupAwayFromChrome(map) {
        if (!map || typeof L === 'undefined') return;
        var container = map.getContainer();
        var popupEl = container.querySelector('.leaflet-popup.leg-location-popup');
        if (!popupEl) return;
        var obstacles = legLocationPopupChromeObstacles(map);
        if (!obstacles.length) return;
        var popRect = popupEl.getBoundingClientRect();
        var dx = 0;
        var dy = 0;
        var maxDy = 72;
        var maxDx = 28;
        obstacles.forEach(function (obs) {
            if (!legLocationPopupRectsOverlap(popRect, obs)) return;
            var overlapY = Math.min(popRect.bottom, obs.bottom) - Math.max(popRect.top, obs.top);
            var overlapX = Math.min(popRect.right, obs.right) - Math.max(popRect.left, obs.left);
            if (overlapY > 0) {
                dy = Math.max(dy, Math.min(overlapY + 6, maxDy));
            }
            // Nudge right only for narrow top-left controls (zoom), not the full toolbar row.
            var obsWidth = obs.right - obs.left;
            if (overlapX > 0 && obsWidth <= 56) {
                dx = Math.max(dx, Math.min(overlapX + 6, maxDx));
            }
        });
        if (!dx && !dy) return;
        var pos = L.DomUtil.getPosition(popupEl);
        L.DomUtil.setPosition(popupEl, L.point(pos.x + dx, pos.y + dy));
    }

    function syncLegLocationPopupMaxHeight(map) {
        if (!map || !map.getContainer) return;
        var container = map.getContainer();
        var wrapper = container.querySelector('.leaflet-popup.leg-location-popup .leaflet-popup-content-wrapper');
        if (!wrapper) return;
        var maxH = Math.max(180, container.clientHeight - 24);
        wrapper.style.maxHeight = maxH + 'px';
    }

    function bindLegLocationPopupScrollGuard(contentEl) {
        if (!contentEl) return;
        contentEl.addEventListener(
            'wheel',
            function (e) {
                e.stopPropagation();
            },
            { passive: true }
        );
    }

    function attachLegLocationPopupMapBehavior(map, contentEl) {
        disableMapWheelForLegLocationPopup(map);
        bindLegLocationPopupScrollGuard(contentEl);
        function onPopupClose() {
            restoreMapWheelForLegLocationPopup(map);
            map.off('popupclose', onPopupClose);
        }
        map.on('popupclose', onPopupClose);
        syncLegLocationPopupMaxHeight(map);
        window.requestAnimationFrame(function () {
            syncLegLocationPopupMaxHeight(map);
            nudgeLegLocationPopupAwayFromChrome(map);
        });
    }

    function appendLegPopupField(parent, labelText, controlEl, extraClass) {
        var wrap = document.createElement('div');
        wrap.className = 'leg-popup-field' + (extraClass ? ' ' + extraClass : '');
        var lab = document.createElement('label');
        lab.textContent = labelText;
        wrap.appendChild(lab);
        wrap.appendChild(controlEl);
        parent.appendChild(wrap);
        return controlEl;
    }

    function appendLegPopupOpsField(parent, labelText, controlEl, extraClass) {
        var wrap = document.createElement('div');
        wrap.className = 'leg-popup-ops-field';
        var lab = document.createElement('label');
        lab.textContent = labelText;
        wrap.appendChild(lab);
        if (extraClass) controlEl.className = extraClass;
        wrap.appendChild(controlEl);
        parent.appendChild(wrap);
        return controlEl;
    }

    function bindLegPopupCountInput(inputEl, maxVal) {
        inputEl.type = 'number';
        inputEl.min = '0';
        inputEl.max = String(maxVal);
        inputEl.className = 'leg-popup-narrow-input';
        inputEl.setAttribute('inputmode', 'numeric');
        inputEl.addEventListener('change', function () {
            var n = parseInt(inputEl.value, 10);
            if (isNaN(n) || n < 0) {
                inputEl.value = '0';
            } else if (n > maxVal) {
                inputEl.value = String(maxVal);
            }
        });
    }

    function openLegLocationPopup(opts) {
        opts = opts || {};
        var map = window.courseMappingMap;
        if (!map) return;
        var mode = opts.mode || 'add';
        var latlng = opts.latlng;
        if (!latlng) return;

        var content = document.createElement('div');
        content.className = 'course-map-popup leg-location-popup-form';

        var title = document.createElement('p');
        title.className = 'leg-popup-title';
        title.textContent =
            mode === 'add'
                ? 'Add location'
                : mode === 'edit-pending'
                  ? 'Edit location (unsaved)'
                  : 'Edit location';
        content.appendChild(title);

        var sel = document.createElement('select');
        var initialType = (opts.loc && opts.loc.loc_type) || 'course';
        locationTypes().forEach(function (t) {
            var opt = document.createElement('option');
            opt.value = t.value;
            opt.textContent = t.label;
            if (t.value === initialType) opt.selected = true;
            sel.appendChild(opt);
        });
        appendLegPopupField(content, 'Type', sel);

        var excludeProxyKey =
            mode === 'edit-saved' && selectedLegId && opts.locIndex != null
                ? legLocKey(selectedLegId, opts.locIndex)
                : '';
        var proxyWrap = document.createElement('div');
        proxyWrap.className = 'leg-popup-field leg-popup-proxy-field';
        var proxySel = buildLegProxyTimingSelect(opts.loc || {}, excludeProxyKey, selectedLegId);
        appendLegPopupField(proxyWrap, 'Proxy timing source', proxySel);
        content.appendChild(proxyWrap);

        var hint = document.createElement('p');
        hint.className = 'leg-popup-hint';
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
            var usesProxy = offCourseUsesProxyTiming(sel.value);
            proxyWrap.style.display = usesProxy ? '' : 'none';
            hint.textContent = locationTypeSnapsToLegRoute(sel.value)
                ? 'Snaps to the purple route when saved. Runner times come from the mapped segment at export.'
                : usesProxy
                  ? 'Stays at your click (off-course). Prefer a proxy on this leg (listed first); other legs are allowed for paired corridors.'
                  : 'Stays at your click (off-course).';
        }
        syncPopupLocTypeFromSelect();
        sel.addEventListener('change', syncPopupLocTypeFromSelect);
        content.appendChild(hint);

        var input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'e.g. Water station';
        input.value = (opts.loc && opts.loc.loc_label) || '';
        appendLegPopupField(content, 'Label', input);

        var opsRow = document.createElement('div');
        opsRow.className = 'leg-popup-ops-row';
        var zoneInput = document.createElement('input');
        zoneInput.type = 'text';
        zoneInput.value = (opts.loc && opts.loc.zone) || '';
        zoneInput.className = 'leg-popup-narrow-input leg-popup-zone-input';
        zoneInput.setAttribute('maxlength', '4');
        appendLegPopupOpsField(opsRow, 'Zone', zoneInput);

        var bufferInput = document.createElement('input');
        bufferInput.value = (opts.loc && opts.loc.buffer != null) ? String(opts.loc.buffer) : '10';
        bindLegPopupCountInput(bufferInput, 999);
        appendLegPopupOpsField(opsRow, 'Buffer', bufferInput);

        var resourceInputs = {};
        getPackageResources().forEach(function (res) {
            var rInp = document.createElement('input');
            var existing = 0;
            if (opts.loc && opts.loc.resources && opts.loc.resources[res.code] != null) {
                existing = parseInt(opts.loc.resources[res.code], 10) || 0;
            }
            rInp.value = String(Math.min(99, Math.max(0, existing)));
            bindLegPopupCountInput(rInp, 99);
            appendLegPopupOpsField(opsRow, res.label || res.code.toUpperCase(), rInp);
            resourceInputs[res.code] = rInp;
        });
        content.appendChild(opsRow);

        var notesInput = document.createElement('textarea');
        notesInput.rows = 2;
        notesInput.value = (opts.loc && opts.loc.notes) || '';
        appendLegPopupField(content, 'Notes', notesInput, 'leg-popup-notes-field');

        function applyOpsFields(target) {
            target.zone = zoneInput.value.trim();
            var buf = parseInt(bufferInput.value, 10);
            target.buffer = isNaN(buf) ? 10 : Math.max(0, Math.min(999, buf));
            target.notes = notesInput.value.trim();
            target.resources = {};
            Object.keys(resourceInputs).forEach(function (code) {
                var n = parseInt(resourceInputs[code].value, 10);
                target.resources[code] = isNaN(n) || n < 0 ? 0 : Math.min(99, n);
            });
            if (offCourseUsesProxyTiming(target.loc_type)) {
                var proxyKey = (proxySel.value || '').trim();
                if (proxyKey) {
                    target.proxy_leg_loc_key = proxyKey;
                } else {
                    delete target.proxy_leg_loc_key;
                }
            } else {
                delete target.proxy_leg_loc_key;
            }
        }

        var btnRow = document.createElement('div');
        btnRow.className = 'leg-popup-actions';

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

        var pop = L.popup({
            maxWidth: 380,
            className: 'location-popup leg-location-popup',
            autoPan: true,
            autoPanPaddingTopLeft: legLocationPopupAutoPanPaddingTopLeft(map),
            autoPanPaddingBottomRight: L.point(12, 12)
        })
            .setContent(content)
            .setLatLng(latlng);
        attachLegLocationPopupMapBehavior(map, content);
        pop.openOn(map);

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
                var newLoc = {
                    loc_label: locLabel,
                    loc_type: locType,
                    lat: Math.round(placeLat * 1e6) / 1e6,
                    lon: Math.round(placeLon * 1e6) / 1e6,
                    placement: legLocationPlacement(locType)
                };
                applyOpsFields(newLoc);
                pendingLegLocations.push(newLoc);
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
                var pendingLoc = applyLegLocationLabelType(
                    pendingLegLocations[pIdx],
                    locLabel,
                    locType
                );
                applyOpsFields(pendingLoc);
                pendingLegLocations[pIdx] = pendingLoc;
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
                var savedLoc = applyLegLocationLabelType(
                    locations[locIndex],
                    locLabel,
                    locType
                );
                applyOpsFields(savedLoc);
                locations[locIndex] = savedLoc;
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
            tryOpenPendingLocationFocus();
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
                        '. Apply recipes to sync locations (with resources) to the Course tab.'
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
        return fetch(legDetailUrl(legId), {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_label: startLabel, end_label: endLabel })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                return afterLegLibraryMutation(payload.data);
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
            fetch(legDetailUrl(legId), {
                method: 'PUT',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fields)
            })
                .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
                .then(function (payload) {
                    if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                    return afterLegLibraryMutation(payload.data);
                })
                .catch(function (err) { setLegStatus(err.message || String(err), true); });
        });
        marker.addTo(map);
        return marker;
    }

    function selectLegById(legId, options) {
        options = options || {};
        if (legDrawActive) stopLegDrawMode();
        if (!options.keepExtend) {
            stopLegExtendRoute(true);
        }
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
        fetch(legGeometryUrl(legId), { credentials: 'same-origin' })
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
                tryOpenPendingLocationFocus();
                renderLegLocationsBrowser();
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

    function downloadLegExportBlob(blob, filename, statusMsg) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setLegStatus(statusMsg);
    }

    function exportAllLegs() {
        var legs = (libraryState && libraryState.legs) || [];
        if (!legs.length) {
            setLegStatus('No legs to export.', true);
            return;
        }
        setLegStatus('Preparing export for ' + legs.length + ' leg' + (legs.length === 1 ? '' : 's') + '…');
        fetch(apiBase() + '/segment-library/export-legs', { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) {
                    return r.json().then(function (d) {
                        throw new Error(formatApiError(r, d));
                    });
                }
                var disposition = r.headers.get('Content-Disposition') || '';
                var match = /filename="?([^";]+)"?/i.exec(disposition);
                var filename = (match && match[1]) || 'legs_export.zip';
                return r.blob().then(function (blob) {
                    return { blob: blob, filename: filename };
                });
            })
            .then(function (payload) {
                downloadLegExportBlob(
                    payload.blob,
                    payload.filename,
                    'Exported ' + legs.length + ' leg' + (legs.length === 1 ? '' : 's') + '.'
                );
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function setOrgLibraryStatus(msg, isError) {
        var el = document.getElementById('org-leg-library-status');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.textContent = msg;
        el.style.color = isError ? '#c0392b' : '';
    }

    function closeOrgLibraryModal() {
        var modal = document.getElementById('org-leg-library-modal');
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        setOrgLibraryStatus('');
    }

    function openOrgLibraryModal() {
        var modal = document.getElementById('org-leg-library-modal');
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        refreshOrgLibraryModal();
    }

    function renderOrgLibraryTable(orgLegs) {
        var empty = document.getElementById('org-leg-library-empty');
        var wrap = document.getElementById('org-leg-library-table-wrap');
        var tbody = document.getElementById('org-leg-library-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (!orgLegs || !orgLegs.length) {
            if (empty) empty.style.display = 'block';
            if (wrap) wrap.style.display = 'none';
            return;
        }
        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        orgLegs.forEach(function (leg) {
            var tr = document.createElement('tr');
            var orgId = leg.org_leg_id || leg.id;
            [
                orgId,
                (leg.leg_label || '').slice(0, 48),
                leg.length_km != null ? Number(leg.length_km).toFixed(2) : '—',
                String(leg.location_count != null ? leg.location_count : (leg.locations || []).length)
            ].forEach(function (text) {
                var td = document.createElement('td');
                td.textContent = text;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function refreshOrgLibraryModal() {
        setOrgLibraryStatus('Loading org library…');
        fetch('/api/org/legs', { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (d) {
                    if (!r.ok) throw new Error(formatApiError(r, d));
                    return d;
                });
            })
            .then(function (data) {
                renderOrgLibraryTable(data.legs || []);
                setOrgLibraryStatus('');
            })
            .catch(function (err) {
                setOrgLibraryStatus(err.message || String(err), true);
            });
    }

    function copyLeg(legId, options) {
        options = options || {};
        var reverse = !!options.reverse;
        if (!usesOrgLegLibrary()) {
            setLegStatus('Copy leg is only available for the organization leg library.', true);
            return;
        }
        var leg = (libraryState && libraryState.legs || []).find(function (c) {
            return c.id === legId;
        });
        var label = (leg && leg.leg_label) || legId;
        setLegStatus((reverse ? 'Copying leg ' + legId + ' in reverse…' : 'Copying leg ' + legId + '…'));
        fetch('/api/org/legs/' + encodeURIComponent(legId) + '/copy', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reverse: reverse })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                var newId = payload.data.copied_leg_id;
                return afterLegLibraryMutation(payload.data).then(function () {
                    if (newId) {
                        selectLegById(newId);
                    }
                    if (reverse) {
                        setLegStatus(
                            'Created reversed leg ' + newId + ' from leg ' + legId
                            + ' (“' + label + '”). Start and finish are swapped.'
                        );
                    } else {
                        setLegStatus(
                            'Copied “' + label + '” as leg ' + newId
                            + '. Use Trim route to shorten the copy, then edit labels if needed.'
                        );
                    }
                });
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function copyLegLocationsFrom(targetLegId, sourceLegId) {
        if (!usesOrgLegLibrary()) {
            setLegStatus('Copy locations is only available for the organization leg library.', true);
            return;
        }
        targetLegId = String(targetLegId || '').trim();
        sourceLegId = String(sourceLegId || '').trim();
        if (!targetLegId || !sourceLegId) return;
        var targetLeg = (libraryState && libraryState.legs || []).find(function (c) {
            return c.id === targetLegId;
        });
        var sourceLeg = (libraryState && libraryState.legs || []).find(function (c) {
            return c.id === sourceLegId;
        });
        var targetCount = targetLeg
            ? (targetLeg.locations || []).length
            : (targetLeg && targetLeg.location_count) || 0;
        if (targetCount > 0) {
            if (
                !window.confirm(
                    'Leg ' + targetLegId + ' already has ' + targetCount
                    + ' location(s). Replace them with copies from leg ' + sourceLegId + '?'
                )
            ) {
                return;
            }
        }
        var sourceCount = sourceLeg
            ? (sourceLeg.locations || []).length
            : 0;
        if (!sourceCount) {
            setLegStatus('Leg ' + sourceLegId + ' has no locations to copy.', true);
            return;
        }
        setLegStatus('Copying ' + sourceCount + ' location(s) from leg ' + sourceLegId + ' to leg ' + targetLegId + '…');
        fetch('/api/org/legs/' + encodeURIComponent(targetLegId) + '/copy-locations', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_leg_id: sourceLegId, replace: true })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                return afterLegLibraryMutation(payload.data).then(function () {
                    selectLegById(targetLegId);
                    setLegStatus(
                        'Copied ' + (payload.data.location_count || sourceCount)
                        + ' location(s) from leg ' + sourceLegId + ' to leg ' + targetLegId + '.'
                    );
                });
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
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
                downloadLegExportBlob(
                    payload.blob,
                    payload.filename,
                    'Exported leg ' + legId + ' (' + label + ').'
                );
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function saveLegLocations(legId, locations) {
        return fetch(legDetailUrl(legId), {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ locations: locations })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                return afterLegLibraryMutation(payload.data);
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
                (ch.paired_with || '—'),
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
                if (usesOrgLegLibrary()) {
                    actions.appendChild(
                        ta.createIconButton('copy', 'Copy leg as new (same route and locations)', function (ev) {
                            ev.stopPropagation();
                            copyLeg(ch.id);
                        })
                    );
                    actions.appendChild(
                        ta.createIconButton(
                            'reverse',
                            'Copy leg reversed (finish becomes start, start becomes finish)',
                            function (ev) {
                                ev.stopPropagation();
                                copyLeg(ch.id, { reverse: true });
                            }
                        )
                    );
                    if (ch.paired_with) {
                        var pairedId = String(ch.paired_with).trim();
                        var pairedLeg = (libraryState && libraryState.legs || []).find(function (l) {
                            return l.id === pairedId;
                        });
                        var pairedLocCount = pairedLeg
                            ? (pairedLeg.locations || []).length
                            : (pairedLeg && pairedLeg.location_count) || 0;
                        if (pairedLocCount > 0) {
                            actions.appendChild(
                                ta.createIconButton(
                                    'locations',
                                    'Copy locations from paired leg ' + pairedId,
                                    function (ev) {
                                        ev.stopPropagation();
                                        copyLegLocationsFrom(ch.id, pairedId);
                                    }
                                )
                            );
                        }
                    }
                }
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
                inp.type = 'text';
                inp.inputMode = 'numeric';
                inp.pattern = '[0-9, ]*';
                inp.className = 'segment-recipe-order-input';
                inp.title = 'Order slot(s), e.g. 7 or 7,16 to reuse this leg';
                inp.placeholder = '—';
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
        var description = (ch.description != null && String(ch.description).trim())
            ? String(ch.description).trim()
            : (ch.flow_notes != null ? String(ch.flow_notes).trim() : '');
        return {
            from: (ch.start_label || '').trim(),
            to: (ch.end_label || '').trim(),
            seg_label: (ch.leg_label || '').trim(),
            description: description
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

    function clearCoursePreviewLineLayer(map) {
        if (!map || !coursePreviewLineLayer) return;
        map.removeLayer(coursePreviewLineLayer);
        coursePreviewLineLayer = null;
    }

    function renderCoursePreviewToolbar() {
        var toolbar = document.getElementById('course-preview-event-toolbar');
        if (!toolbar) return;
        toolbar.innerHTML = '';
        var events = packageEvents();

        var allBtn = document.createElement('button');
        allBtn.type = 'button';
        allBtn.className =
            'course-btn' + (coursePreviewSelectedEvent === COURSE_PREVIEW_ALL ? ' active' : '');
        allBtn.textContent = 'All';
        allBtn.title = 'Show all event routes and all locations';
        allBtn.addEventListener('click', function () {
            selectCoursePreviewEvent(COURSE_PREVIEW_ALL);
        });
        toolbar.appendChild(allBtn);

        events.forEach(function (eid) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'course-btn' + (coursePreviewSelectedEvent === eid ? ' active' : '');
            btn.textContent = eventColumnLabel(eid);
            btn.title = 'Show ' + eventColumnLabel(eid) + ' route and its locations';
            btn.addEventListener('click', function () {
                selectCoursePreviewEvent(eid);
            });
            toolbar.appendChild(btn);
        });
    }

    function selectCoursePreviewEvent(eventId) {
        coursePreviewSelectedEvent = eventId;
        renderCoursePreviewToolbar();
        var loadPromise =
            eventId === COURSE_PREVIEW_ALL
                ? loadAllCoursePreviewRoutes()
                : loadCoursePreviewRoute(eventId);
        loadPromise.then(function () {
            syncCoursePreviewBoundsFilterItems();
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
            if (!locationMatchesCoursePreviewEvent(loc)) return;
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

    function finishCoursePreviewLoad(map, bounds, metaText) {
        var wrap = document.getElementById('course-preview-map-wrap');
        var empty = document.getElementById('course-preview-empty');
        var meta = document.getElementById('course-preview-meta');

        function finishPreviewLoad() {
            if (wrap) wrap.style.display = 'block';
            if (empty) empty.style.display = 'none';
            if (meta) {
                meta.style.display = 'block';
                meta.textContent = metaText;
            }
            applyCoursePreviewEventFilterToTables();
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
    }

    function loadAllCoursePreviewRoutes() {
        var empty = document.getElementById('course-preview-empty');
        var wrap = document.getElementById('course-preview-map-wrap');
        var meta = document.getElementById('course-preview-meta');
        var events = packageEvents();
        if (!events.length || !hasCombinedCourse()) return Promise.resolve();

        return Promise.all(
            events.map(function (eid) {
                return fetch(
                    apiBase() + '/segment-library/events/' + encodeURIComponent(eid) + '/preview',
                    { credentials: 'same-origin' }
                ).then(function (r) {
                    return r.json().then(function (d) {
                        return { res: r, data: d, eventId: eid };
                    });
                });
            })
        )
            .then(function (payloads) {
                payloads.forEach(function (payload) {
                    if (!payload.res.ok) {
                        throw new Error(formatApiError(payload.res, payload.data));
                    }
                });
                var map = ensureCoursePreviewMap();
                if (!map) return;
                clearCoursePreviewLineLayer(map);
                clearCoursePreviewLocationsLayer(map);

                coursePreviewLineLayer = L.featureGroup();
                var bounds = null;
                var metaParts = [];
                payloads.forEach(function (payload, idx) {
                    var data = payload.data;
                    var latlngs = (data.coordinates || []).map(function (c) {
                        return [c[1], c[0]];
                    });
                    if (latlngs.length < 2) return;
                    var line = L.polyline(latlngs, {
                        color: COURSE_PREVIEW_ROUTE_COLORS[idx % COURSE_PREVIEW_ROUTE_COLORS.length],
                        weight: 5,
                        opacity: 0.92
                    });
                    coursePreviewLineLayer.addLayer(line);
                    var lineBounds = line.getBounds();
                    bounds = bounds ? bounds.extend(lineBounds) : lineBounds;
                    metaParts.push(
                        eventColumnLabel(payload.eventId) +
                            ' ' +
                            Number(data.length_km).toFixed(2) +
                            ' km'
                    );
                });
                if (!coursePreviewLineLayer.getLayers().length) {
                    throw new Error('No event routes could be loaded');
                }
                coursePreviewLineLayer.addTo(map);
                renderCoursePreviewLocations();
                if (coursePreviewLocationsLayer) {
                    bounds = bounds.extend(coursePreviewLocationsLayer.getBounds());
                }
                var locCount = countCoursePreviewLocationsForSelection();
                finishCoursePreviewLoad(
                    map,
                    bounds,
                    'All events · ' +
                        metaParts.join(' · ') +
                        ' · ' +
                        locCount +
                        ' locations'
                );
            })
            .catch(function (err) {
                var map = coursePreviewMap;
                if (map) {
                    clearCoursePreviewLineLayer(map);
                    clearCoursePreviewLocationsLayer(map);
                }
                if (empty) {
                    empty.style.display = 'block';
                    empty.textContent = err.message || String(err);
                }
                if (wrap) wrap.style.display = 'none';
                if (meta) meta.style.display = 'none';
            });
    }

    function loadCoursePreviewRoute(eventId) {
        var wrap = document.getElementById('course-preview-map-wrap');
        var meta = document.getElementById('course-preview-meta');
        var empty = document.getElementById('course-preview-empty');
        if (!eventId || eventId === COURSE_PREVIEW_ALL || !hasCombinedCourse()) {
            return Promise.resolve();
        }
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
                clearCoursePreviewLineLayer(map);
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
                var locCount = countCoursePreviewLocationsForSelection();
                finishCoursePreviewLoad(
                    map,
                    bounds,
                    eventColumnLabel(eventId) +
                        ': ' +
                        Number(data.length_km).toFixed(2) +
                        ' km · ' +
                        (data.leg_count || 0) +
                        ' legs · ' +
                        locCount +
                        ' locations'
                );
            })
            .catch(function (err) {
                var map = coursePreviewMap;
                if (map) {
                    clearCoursePreviewLineLayer(map);
                    clearCoursePreviewLocationsLayer(map);
                }
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
        if (
            !coursePreviewSelectedEvent ||
            (coursePreviewSelectedEvent !== COURSE_PREVIEW_ALL &&
                events.indexOf(coursePreviewSelectedEvent) < 0)
        ) {
            coursePreviewSelectedEvent = events.length ? events[0] : null;
        }
        renderCoursePreviewToolbar();
        if (!coursePreviewSelectedEvent) {
            if (wrap) wrap.style.display = 'none';
            if (meta) meta.style.display = 'none';
            return;
        }
        if (coursePreviewSelectedEvent === COURSE_PREVIEW_ALL) {
            loadAllCoursePreviewRoutes();
        } else {
            loadCoursePreviewRoute(coursePreviewSelectedEvent);
        }
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

    function loadOrgLibrary() {
        showPackageLegsUi(true);
        return fetch('/api/org/legs/state', { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { res: r, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                var data = payload.data || {};
                applyLibraryState({
                    leg_source: 'org',
                    has_library: !!data.has_library,
                    legs: data.legs || [],
                    recipes: {},
                    order_grid: {},
                    package_events: [],
                    recipe_lengths_km: {},
                    stitch_warnings: [],
                });
                setLegStatus('');
                bindLegMapControls();
                attachLegsTableBoundsFilter();
                fitLegMapToAllLegs();
            })
            .catch(function (err) {
                setLegStatus(err.message || String(err), true);
            });
    }

    function loadLibrary() {
        if (isOrgLegsHubMode()) {
            return loadOrgLibrary();
        }
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
        if (legDrawActive) stopLegDrawMode();
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
        fetch(legDetailUrl(legId), {
            method: 'DELETE',
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                if (selectedLegId === legId) clearLegMap();
                return afterLegLibraryMutation(payload.data);
            })
            .then(function () { setLegStatus('Leg deleted.'); })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function closeLegEditor() {
        var modal = document.getElementById('leg-editor-modal');
        if (modal) { modal.hidden = true; modal.setAttribute('aria-hidden', 'true'); }
        legEditorMode = null;
        legEditorLegId = null;
        pendingGpxFile = null;
        pendingDrawCoordinates = null;
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
            description: ''
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
        if (isNew && pendingDrawCoordinates) {
            hint.textContent = 'Route drawn on map: '
                + legDrawHaversineKm(pendingDrawCoordinates).toFixed(2)
                + ' km. Set names for this leg. Add locations on the map after saving.';
        } else {
            hint.textContent = isNew
                ? 'Set names for this leg. Add locations on the map after saving.'
                : 'Edit metadata here. Add or adjust locations on the map (select the leg, then Add Locations).';
        }
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

        /** Other legs eligible as a corridor pair: not self, not already paired elsewhere. */
        function pairedLegChoices(selfId, currentValue) {
            var current = String(currentValue || '').trim();
            var choices = [{ value: '', label: 'None' }];
            ((libraryState && libraryState.legs) || []).forEach(function (other) {
                var oid = String(other.id || '').trim();
                if (!oid || oid === String(selfId)) return;
                var otherPair = String(other.paired_with || '').trim();
                if (otherPair && otherPair !== String(selfId) && oid !== current) return;
                choices.push({ value: oid, label: oid + ' — ' + (other.leg_label || oid) });
            });
            return choices;
        }

        addField('Leg label', 'leg-label', leg.leg_label);
        addField('Start place', 'leg-start-label', leg.start_label);
        addField('End place', 'leg-end-label', leg.end_label);
        addField('Width (m)', 'leg-width', leg.width_m, 'number');
        addSelectField('Schema', 'leg-schema', leg.schema || 'on_course_open', segmentSchemaChoices());
        addSelectField('Direction', 'leg-direction', leg.direction || 'uni', segmentDirectionChoices());
        addSelectField('Flow type', 'leg-flow-type', leg.flow_type || 'none', flowTypeChoices());
        if (!isNew) {
            var pairSel = addSelectField(
                'Paired leg (same corridor, opposite direction)',
                'leg-paired-with',
                leg.paired_with || '',
                pairedLegChoices(leg.id, leg.paired_with)
            );
            pairSel.title = 'Marks two directional legs as one physical corridor. '
                + 'Generates opposing-pass (counterflow) flow rows on apply.';
        }

        var notesWrap = document.createElement('div');
        notesWrap.style.marginBottom = '0.65rem';
        var notesLab = document.createElement('label');
        notesLab.textContent = 'Description';
        notesLab.style.display = 'block';
        notesLab.style.fontWeight = '600';
        notesLab.style.fontSize = '0.85rem';
        var notesTa = document.createElement('textarea');
        notesTa.id = 'leg-description';
        notesTa.rows = 2;
        notesTa.maxLength = 500;
        notesTa.placeholder = 'Segment description (syncs to Course tab)';
        notesTa.value = leg.description != null && String(leg.description).trim()
            ? String(leg.description)
            : (leg.flow_notes != null ? String(leg.flow_notes) : '');
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
        var fields = {
            leg_label: (document.getElementById('leg-label') || {}).value || '',
            start_label: (document.getElementById('leg-start-label') || {}).value || '',
            end_label: (document.getElementById('leg-end-label') || {}).value || '',
            width_m: parseFloat((document.getElementById('leg-width') || {}).value) || 3,
            schema: ((document.getElementById('leg-schema') || {}).value || 'on_course_open').trim(),
            direction: ((document.getElementById('leg-direction') || {}).value || 'uni').trim(),
            flow_type: ((document.getElementById('leg-flow-type') || {}).value || 'none').trim(),
            description: ((document.getElementById('leg-description') || {}).value || '').trim()
        };
        var pairedSel = document.getElementById('leg-paired-with');
        if (pairedSel) {
            fields.paired_with = (pairedSel.value || '').trim();
        }
        return fields;
    }

    function validateLegFields(fields) {
        var missing = [];
        if (!String(fields.leg_label || '').trim()) missing.push('Leg label');
        if (!String(fields.start_label || '').trim()) missing.push('Start place');
        if (!String(fields.end_label || '').trim()) missing.push('End place');
        if (!String(fields.description || '').trim()) missing.push('Description');
        if (!(fields.width_m > 0)) missing.push('Width (m)');
        if (missing.length) {
            return 'Required: ' + missing.join(', ') + '.';
        }
        return '';
    }

    function saveLegEditor() {
        var fields = collectLegFields();
        var validationError = validateLegFields(fields);
        if (validationError) {
            setLegStatus(validationError, true);
            return;
        }
        if (legEditorMode === 'create' && pendingDrawCoordinates) {
            var drawBody = Object.assign({ coordinates: pendingDrawCoordinates }, fields);
            delete drawBody.paired_with; // not supported at create time
            setLegStatus('Saving drawn leg…');
            fetch('/api/org/legs/draw', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(drawBody)
            })
                .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
                .then(function (payload) {
                    if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                    return afterLegLibraryMutation(payload.data);
                })
                .then(function () {
                    closeLegEditor();
                    setLegStatus('Drawn leg added to the organization library. Select it in the table to view on the map.');
                })
                .catch(function (err) { setLegStatus(err.message || String(err), true); });
            return;
        }
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
            fd.append('description', fields.description);
            setLegStatus('Saving leg…');
            fetch(legCreateUrl(), { method: 'POST', credentials: 'same-origin', body: fd })
                .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
                .then(function (payload) {
                    if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                    return afterLegLibraryMutation(payload.data);
                })
                .then(function () {
                    closeLegEditor();
                    setLegStatus('Leg added to the organization library. Select it in the table to view on the map.');
                })
                .catch(function (err) { setLegStatus(err.message || String(err), true); });
            return;
        }
        setLegStatus('Saving leg…');
        fetch(legDetailUrl(legEditorLegId), {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(fields)
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                return afterLegLibraryMutation(payload.data);
            })
            .then(function () {
                closeLegEditor();
                setLegStatus('Leg saved.');
            })
            .catch(function (err) { setLegStatus(err.message || String(err), true); });
    }

    function replaceLegGpx(legId, file) {
        var fd = new FormData();
        fd.append('file', file);
        setLegStatus('Updating GPX…');
        var gpxUrl = usesOrgLegLibrary()
            ? '/api/org/legs/' + encodeURIComponent(legId) + '/gpx'
            : apiBase() + '/segment-library/legs/' + encodeURIComponent(legId) + '/gpx';
        fetch(gpxUrl, {
            method: 'PUT',
            credentials: 'same-origin',
            body: fd
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                return afterLegLibraryMutation(payload.data);
            })
            .then(function () { setLegStatus('GPX updated.'); })
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
        fetch(legUploadUrl(), { method: 'POST', credentials: 'same-origin', body: fd })
            .then(function (r) { return r.json().then(function (d) { return { res: r, data: d }; }); })
            .then(function (payload) {
                if (!payload.res.ok) throw new Error(formatApiError(payload.res, payload.data));
                return afterLegLibraryMutation(payload.data).then(function () {
                    return payload.data;
                });
            })
            .then(function (data) {
                var count = (data.legs || []).length;
                var msg =
                    'Imported ' +
                    count +
                    ' leg(s) to the organization library. Select a leg to view on the map.';
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
        bindLegLocationsBrowserUi();
        var drawToolbarBtn = document.getElementById('btn-leg-draw');
        if (drawToolbarBtn) {
            drawToolbarBtn.addEventListener('click', function () {
                if (legDrawActive) { stopLegDrawMode(); setLegStatus(''); return; }
                startLegDrawMode();
            });
        }
        var drawCardBtn = document.getElementById('btn-draw-leg-map');
        if (drawCardBtn) {
            drawCardBtn.addEventListener('click', function () {
                if (!legDrawActive) startLegDrawMode();
            });
        }
        var drawUndoBtn = document.getElementById('btn-leg-draw-undo');
        if (drawUndoBtn) drawUndoBtn.addEventListener('click', legDrawUndo);
        var drawOutbackBtn = document.getElementById('btn-leg-draw-outback');
        if (drawOutbackBtn) drawOutbackBtn.addEventListener('click', legDrawOutAndBack);
        var drawClearBtn = document.getElementById('btn-leg-draw-clear');
        if (drawClearBtn) drawClearBtn.addEventListener('click', legDrawClear);
        var drawFinishBtn = document.getElementById('btn-leg-draw-finish');
        if (drawFinishBtn) drawFinishBtn.addEventListener('click', finishLegDraw);
        var drawCancelBtn = document.getElementById('btn-leg-draw-cancel');
        if (drawCancelBtn) {
            drawCancelBtn.addEventListener('click', function () {
                stopLegDrawMode();
                setLegStatus('');
            });
        }
        var drawTraceInput = document.getElementById('leg-draw-trace');
        if (drawTraceInput) {
            drawTraceInput.addEventListener('change', function () {
                legDrawTraceEnabled = !!drawTraceInput.checked;
                applyLegDrawTraceVisibility();
            });
        }
        var importBtn = document.getElementById('btn-import-gpx');
        var exportAllBtn = document.getElementById('btn-export-all-legs');
        var bulkInput = document.getElementById('segment-library-gpx-input');
        if (importBtn && bulkInput) {
            importBtn.addEventListener('click', function () {
                bulkInput.value = '';
                bulkInput.click();
            });
        }
        if (exportAllBtn) {
            exportAllBtn.addEventListener('click', exportAllLegs);
        }
        var orgLibBtn = document.getElementById('btn-org-leg-library');
        if (orgLibBtn) {
            orgLibBtn.addEventListener('click', openOrgLibraryModal);
        }
        var orgLibClose = document.getElementById('org-leg-library-close');
        if (orgLibClose) orgLibClose.addEventListener('click', closeOrgLibraryModal);
        var orgLibDone = document.getElementById('org-leg-library-done');
        if (orgLibDone) orgLibDone.addEventListener('click', closeOrgLibraryModal);
        var orgLibBackdrop = document.querySelector('#org-leg-library-modal .course-location-modal-backdrop');
        if (orgLibBackdrop) orgLibBackdrop.addEventListener('click', closeOrgLibraryModal);
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
                if (isLegRouteEditActive()) {
                    return;
                }
                startLegTrimRoute();
            });
        }
        var extendBtn = document.getElementById('btn-leg-extend-route');
        if (extendBtn) {
            extendBtn.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                if (legExtendActive) {
                    return;
                }
                if (isLegRouteEditActive()) {
                    return;
                }
                startLegExtendRoute();
            });
        }
        var extendUndo = document.getElementById('btn-leg-extend-undo');
        if (extendUndo) {
            extendUndo.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                legExtendUndo();
            });
        }
        var extendClear = document.getElementById('btn-leg-extend-clear');
        if (extendClear) {
            extendClear.addEventListener('click', function (ev) {
                if (ev.stopPropagation) ev.stopPropagation();
                legExtendClearExtension();
            });
        }
        var extendAnchor = document.getElementById('leg-extend-anchor');
        if (extendAnchor) {
            extendAnchor.addEventListener('change', function () {
                if (!legExtendActive) {
                    return;
                }
                if (legExtendNewCoords.length) {
                    legExtendClearExtension();
                }
                legExtendFromEnd = extendAnchor.value !== 'start';
                setLegStatus(
                    'Extending from ' +
                        (legExtendFromEnd ? 'end' : 'start') +
                        ' — click the map to lengthen the leg.'
                );
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
        loadOrgLibrary: loadOrgLibrary,
        onOrgLegsHubShown: function () {
            initOrgLegHubResources();
            bindLegLocationsBrowserUi();
            if (window.configPackageCourse && window.configPackageCourse.removeLocationPins) {
                window.configPackageCourse.removeLocationPins();
            }
            loadOrgLibrary().then(function () {
                bindLegMapControls();
                attachLegsTableBoundsFilter();
                if (pendingLocationFocus) {
                    renderLegLocationsBrowser();
                    scrollLegMapIntoView();
                    focusLegLocation(
                        pendingLocationFocus.legId,
                        pendingLocationFocus.locIndex
                    );
                }
                if (window.courseMappingMap) {
                    setTimeout(function () {
                        window.courseMappingMap.invalidateSize();
                        bindLegMapControls();
                        attachLegsTableBoundsFilter();
                    }, 100);
                }
            });
        },
        onCourseTabShown: onCourseTabShown,
        syncCoursePanelUi: syncCoursePanelUi,
        renderCoursePreviewLocations: renderCoursePreviewLocations,
        openRecipesModal: showRecipesModal,
        closeRecipesModal: closeRecipesModal,
        resolveLegLabelsForSegment: resolveLegLabelsForSegment,
        onLegsTabShown: function () {
            if (window.segmentRecipes.onOrgLegsHubShown) {
                window.segmentRecipes.onOrgLegsHubShown();
            }
        },
        attachLegsTableBoundsFilter: attachLegsTableBoundsFilter,
        attachCoursePreviewBoundsFilter: attachCoursePreviewBoundsFilter,
        syncCoursePreviewBoundsFilterItems: syncCoursePreviewBoundsFilterItems,
        initOrgLegHubResources: initOrgLegHubResources,
        saveOrgLegHubResources: saveOrgLegResourcesToStorage,
        getLegResources: getPackageResources,
        focusLegLocation: focusLegLocation,
        navigateToLegLocation: navigateToLegLocation,
    };
})();
