/**
 * Course Mapping page: map, Street/Satellite toggle, course New/Open/Save.
 * Issue #732: Course storage under {data_dir}/courses/{id}.
 * Issue #757: Config package mode uses /api/config/packages/{config_id}/course.
 */

document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('course-mapping-map');
    if (!container) return;

    const loadingEl = container.querySelector('.map-loading');
    const toggleEl = document.getElementById('basemap-toggle');

    function resolveConfigPackageId() {
        var root = document.getElementById('course-mapping-root');
        if (root && root.dataset && root.dataset.configId) {
            return String(root.dataset.configId).trim();
        }
        var params = new URLSearchParams(window.location.search);
        var fromUrl = params.get('config_id');
        if (fromUrl) return fromUrl.trim();
        if (currentCourse && currentCourse.config_id) {
            return String(currentCourse.config_id).trim();
        }
        if (window.location.pathname.indexOf('/config') === 0) {
            var cid = params.get('config_id');
            if (cid) return cid.trim();
        }
        return null;
    }

    function isConfigPackageMode() {
        return !!resolveConfigPackageId();
    }

    /** Race Configuration hub: same course card + Edit/Save as full-page mapping. */
    function usePackageLevelEditSave() {
        return isConfigPackageMode() && !!document.getElementById('race-config-workspace');
    }

    var POPUP_MAX_WIDTH = 375;
    var resourcesDirty = false;

    var workspaceActionsHome = null;

    function moveWorkspaceActionButtons() {
        if (!usePackageLevelEditSave()) return;
        var navHome = document.getElementById('race-config-workspace-actions');
        var courseHome = document.getElementById('course-map-header-buttons');
        if (!navHome || !courseHome) return;
        if (!workspaceActionsHome) {
            workspaceActionsHome = courseHome;
        }
        var ids = ['btn-edit-course', 'btn-export', 'btn-save-course', 'btn-delete-course'];
        ids.forEach(function (id) {
            var el = document.getElementById(id);
            if (el && el.parentNode !== navHome) {
                navHome.appendChild(el);
            }
        });
        var del = document.getElementById('btn-delete-course');
        if (del) del.style.display = 'none';
    }

    function initPackageEventDaySelect() {
        var sel = document.getElementById('course-map-event-day');
        if (!sel) return;
        var selected = sel.value || getPackageEventDay();
        if (sel.options.length <= 1) {
            populateDaySelect(sel, selected, '(not set)');
        }
    }

    function applyConfigPackageUIMode() {
        initPackageEventDaySelect();
        var listCard = document.getElementById('course-list-card');
        if (listCard) listCard.style.display = 'none';
        var btnNew = document.getElementById('btn-new-course');
        if (btnNew) btnNew.style.display = 'none';
        var pkgCard = document.getElementById('config-package-details-card');
        if (usePackageLevelEditSave()) {
            if (pkgCard) pkgCard.style.display = 'block';
            moveWorkspaceActionButtons();
        } else if (pkgCard) {
            pkgCard.style.display = 'none';
        }
        var btnDelete = document.getElementById('btn-delete-course');
        if (btnDelete && !usePackageLevelEditSave()) {
            btnDelete.style.display = '';
        }
        var btnExport = document.getElementById('btn-export');
        if (btnExport) {
            btnExport.disabled = false;
            btnExport.title = usePackageLevelEditSave()
                ? 'Export segments, locations, and related files for this package'
                : 'Write segments.csv, flow.csv, locations.csv, GPX to course folder';
        }
    }

    function loadConfigPackageCourse() {
        var pkgId = resolveConfigPackageId();
        if (!pkgId) return Promise.resolve();
        return fetch(
            '/api/config/packages/' + encodeURIComponent(pkgId) + '/course',
            { credentials: 'same-origin' }
        )
            .then(function (res) {
                if (res.status === 404) {
                    var c = blankCourse();
                    c.id = pkgId;
                    c.config_id = pkgId;
                    setCourse(pkgId, c);
                    clearDirty();
                    return null;
                }
                if (!res.ok) {
                    return res.json().then(function (d) {
                        throw new Error(d.detail || res.statusText);
                    });
                }
                return res.json();
            })
            .then(function (data) {
                if (!data) return;
                if (data.ok && data.course) {
                    setCourse(pkgId, data.course);
                    if (window.PENDING_PACKAGE_META) {
                        syncCourseHeaderFromPackageMeta(
                            window.PENDING_PACKAGE_META.label,
                            window.PENDING_PACKAGE_META.description,
                            window.PENDING_PACKAGE_META.event_day || ''
                        );
                        delete window.PENDING_PACKAGE_META;
                    }
                    clearDirty();
                    console.log('Loaded config package course:', pkgId);
                }
                return reloadConfigPackageManifest();
            })
            .catch(function (e) {
                console.error('Load config package course failed:', e);
                alert('Failed to load course: ' + (e.message || String(e)));
            });
    }

    function getDayShortCodes() {
        var codes = window.DAY_SHORT_CODES_FROM_SERVER;
        return Array.isArray(codes) && codes.length
            ? codes
            : ['fri', 'sat', 'sun', 'mon'];
    }

    function populateDaySelect(selectEl, selectedValue, emptyLabel) {
        if (!selectEl) return;
        selectEl.innerHTML = '';
        var emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = emptyLabel || '(not set)';
        selectEl.appendChild(emptyOpt);
        getDayShortCodes().forEach(function (day) {
            var opt = document.createElement('option');
            opt.value = day;
            opt.textContent = day;
            if (selectedValue === day) opt.selected = true;
            selectEl.appendChild(opt);
        });
    }

    function getPackageEventDay() {
        var d = window.CONFIG_PACKAGE_EVENT_DAY;
        return d ? String(d).trim().toLowerCase() : '';
    }

    function syncCourseHeaderFromPackageMeta(label, description, eventDay) {
        if (!currentCourse) return;
        if (label != null) currentCourse.name = String(label).trim();
        if (description != null) currentCourse.description = String(description).trim();
        if (eventDay != null) {
            window.CONFIG_PACKAGE_EVENT_DAY = String(eventDay).trim().toLowerCase();
        }
        syncCourseToHeaderInputs();
    }

    function applyPackageDayToLocation(loc) {
        if (!loc) return;
        var pkgDay = getPackageEventDay();
        if (pkgDay && !(loc.day || '').trim()) {
            loc.day = pkgDay;
        }
    }

    function buildCourseSavePayload(courseIdToSave) {
        return {
            id: courseIdToSave,
            config_id: resolveConfigPackageId() || currentCourse.config_id,
            name: currentCourse.name,
            description: currentCourse.description,
            segments: currentCourse.segments || [],
            locations: currentCourse.locations || [],
            geometry: currentCourse.geometry,
            segment_breaks: currentCourse.segment_breaks || [],
            segment_break_labels: currentCourse.segment_break_labels || {},
            segment_break_descriptions: currentCourse.segment_break_descriptions || {},
            segment_break_ids: currentCourse.segment_break_ids || {},
            turnaround_indices: Array.isArray(currentCourse.turnaround_indices)
                ? currentCourse.turnaround_indices.slice()
                : [],
            start_description: currentCourse.start_description || '',
            end_description: currentCourse.end_description || '',
            turnaround_descriptions: currentCourse.turnaround_descriptions || {},
            flow_control_points: Array.isArray(currentCourse.flow_control_points)
                ? JSON.parse(JSON.stringify(currentCourse.flow_control_points))
                : []
        };
    }

    function persistConfigPackageResources() {
        var pkgId = resolveConfigPackageId();
        if (!pkgId || !resourcesDirty) return Promise.resolve();
        return fetch('/api/config/packages/' + encodeURIComponent(pkgId) + '/resources', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resources: getPackageResources() })
        }).then(function (res) {
            return res.json().then(function (d) {
                if (!res.ok) throw new Error(d.detail || res.statusText);
                window.CONFIG_PACKAGE_RESOURCES = d.resources || getPackageResources();
                resourcesDirty = false;
                if (currentCourse && currentCourse.locations) {
                    currentCourse.locations.forEach(syncLocationResourceCounts);
                }
            });
        });
    }

    function persistConfigPackageCourse(meta) {
        if (!currentCourse) return Promise.reject(new Error('No course loaded'));
        var pkgId = resolveConfigPackageId();
        if (!pkgId) return Promise.reject(new Error('No config package'));
        if (meta) syncCourseHeaderFromPackageMeta(meta.label, meta.description);
        var toSave = buildCourseSavePayload(pkgId);
        currentCourse.id = pkgId;
        currentCourse.config_id = pkgId;
        return fetch('/api/config/packages/' + encodeURIComponent(pkgId) + '/course', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ course: toSave })
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok) throw new Error(data.detail || res.statusText);
                if (data.ok && data.course) {
                    setCourse(pkgId, data.course);
                }
                clearDirty();
            });
        });
    }

    function saveConfigPackageWorkspace(meta) {
        return persistConfigPackageResources()
            .then(function () { return persistConfigPackageCourse(meta); })
            .then(function () {
                renderLocationsTableHeader();
                renderLocationsList();
                updateCourseUI();
            });
    }

    function reloadConfigPackageManifest() {
        var pkgId = resolveConfigPackageId();
        if (!pkgId) return Promise.resolve();
        return fetch('/api/config/packages/' + encodeURIComponent(pkgId), { credentials: 'same-origin' })
            .then(function (res) { return res.ok ? res.json() : null; })
            .then(function (data) {
                if (!data || !data.manifest) return;
                var m = data.manifest;
                window.CONFIG_PACKAGE_RESOURCES = m.resources || [];
                syncCourseHeaderFromPackageMeta(
                    m.label || pkgId,
                    m.description || '',
                    m.event_day || ''
                );
            });
    }

    function cancelConfigPackageEdit() {
        resourcesDirty = false;
        return loadConfigPackageCourse()
            .then(function () { return reloadConfigPackageManifest(); })
            .then(function () {
                setEditMode(false);
                updateCourseUI();
                renderLocationsList();
            });
    }

    function saveConfigPackageWorkspaceWithManifest() {
        var pkgId = resolveConfigPackageId();
        if (!pkgId || !currentCourse) return Promise.reject(new Error('No package loaded'));
        var nameInput = activeNameInputEl();
        var descInput = activeDescriptionInputEl();
        var label = nameInput ? String(nameInput.value || '').trim().slice(0, 120) : '';
        var description = descInput ? String(descInput.value || '').trim().slice(0, 255) : '';
        var eventDayInput = document.getElementById('course-map-event-day');
        var event_day = eventDayInput
            ? String(eventDayInput.value || '').trim().toLowerCase().slice(0, 16)
            : '';
        if (!label) return Promise.reject(new Error('Name is required.'));
        return fetch('/api/config/packages/' + encodeURIComponent(pkgId), {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: label, description: description, event_day: event_day })
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok) throw new Error(data.detail || res.statusText);
                var m = data.manifest || {};
                window.CONFIG_PACKAGE_RESOURCES = m.resources || window.CONFIG_PACKAGE_RESOURCES || [];
                syncCourseHeaderFromPackageMeta(
                    m.label || label,
                    m.description != null ? m.description : description,
                    m.event_day != null ? m.event_day : event_day
                );
                return saveConfigPackageWorkspace({
                    label: m.label || label,
                    description: m.description != null ? m.description : description
                });
            });
        });
    }

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
            turnaround_indices: [],
            start_description: '',
            end_description: '',
            turnaround_descriptions: {},
            flow_control_points: []
        };
    }

    function setDirty() { courseDirty = true; }
    function clearDirty() { courseDirty = false; }
    function isDirty() { return courseDirty; }

    var isEditMode = false;

    function updateManageResourcesButton() {
        var btn = document.getElementById('btn-manage-resources');
        if (!btn) return;
        if (usePackageLevelEditSave()) {
            btn.disabled = !isEditMode;
            btn.title = isEditMode
                ? 'Define schedulable resources (FPF, YSSR, AWP, VOL, …)'
                : 'Click Edit to change resources';
        } else {
            btn.disabled = false;
            btn.title = 'Define schedulable resources (FPF, YSSR, AWP, VOL, …)';
        }
    }

    function setEditMode(edit) {
        isEditMode = !!edit;
        var nameText = document.getElementById('course-map-name-text');
        var nameInput = document.getElementById('course-map-name');
        var descText = document.getElementById('course-map-description-text');
        var descInput = document.getElementById('course-map-description');
        var dayText = document.getElementById('course-map-event-day-text');
        var dayInput = document.getElementById('course-map-event-day');
        var nameTextSt = document.getElementById('course-map-name-text-standalone');
        var nameInputSt = document.getElementById('course-map-name-standalone');
        var descTextSt = document.getElementById('course-map-description-text-standalone');
        var descInputSt = document.getElementById('course-map-description-standalone');
        var editToolbar = document.getElementById('course-edit-toolbar');
        var saveBtn = document.getElementById('btn-save-course');
        var editBtn = document.getElementById('btn-edit-course');
        var exportBtn = document.getElementById('btn-export');
        var delBtn = document.getElementById('btn-delete-course');
        var showInput = isEditMode && currentCourse;
        if (nameText) nameText.style.display = isEditMode ? 'none' : 'inline';
        if (nameTextSt) nameTextSt.style.display = isEditMode ? 'none' : 'inline';
        if (nameInput) nameInput.style.display = showInput ? 'block' : 'none';
        if (nameInputSt) nameInputSt.style.display = showInput ? 'inline-block' : 'none';
        if (descText) descText.style.display = isEditMode ? 'none' : 'inline';
        if (descTextSt) descTextSt.style.display = isEditMode ? 'none' : 'inline';
        if (descInput) {
            descInput.style.display = showInput ? 'block' : 'none';
            if (showInput) resizeDescriptionTextarea();
        }
        if (descInputSt) {
            descInputSt.style.display = showInput ? 'block' : 'none';
            if (showInput) resizeDescriptionTextarea();
        }
        if (dayText) dayText.style.display = isEditMode ? 'none' : 'inline';
        if (dayInput) dayInput.style.display = showInput ? 'block' : 'none';
        if (saveBtn) saveBtn.style.display = isEditMode ? 'inline-block' : 'none';
        if (editBtn) editBtn.textContent = isEditMode ? 'Cancel' : 'Edit';
        if (editToolbar) editToolbar.style.display = (isEditMode && currentCourse) ? 'flex' : 'none';
        if (exportBtn) exportBtn.style.display = isEditMode ? 'none' : 'inline-block';
        if (delBtn) {
            if (usePackageLevelEditSave()) {
                delBtn.style.display = 'none';
            } else {
                delBtn.style.display = isEditMode ? 'none' : 'inline-block';
            }
        }
        if (!isEditMode && currentCourse) {
            if (nameInput) nameInput.value = currentCourse.name || '';
            if (nameInputSt) nameInputSt.value = currentCourse.name || '';
            if (descInput) descInput.value = currentCourse.description || '';
            if (descInputSt) descInputSt.value = currentCourse.description || '';
            if (dayInput) dayInput.value = getPackageEventDay();
        }
        renderCourseLine();
        renderSegmentPins();
        renderStartFinishIcons();
        renderUturnIcons();
        renderLocationPins();
        updateSameRouteBackButtons();
        if (!isEditMode) {
            extendFromIndex = null;
            extendInsertEndIndex = null;
            if (drawMode) stopDrawMode();
        }
        updateExtendHint();
        var mapContainer = document.getElementById('course-mapping-map');
        if (mapContainer) {
            if (isEditMode) mapContainer.classList.add('course-mapping-edit-mode');
            else mapContainer.classList.remove('course-mapping-edit-mode');
        }
        updateManageResourcesButton();
        renderLocationsList();
    }

    function isConfigPackageDirty() {
        return isDirty() || resourcesDirty;
    }

    function activeNameInputEl() {
        return usePackageLevelEditSave()
            ? document.getElementById('course-map-name')
            : document.getElementById('course-map-name-standalone');
    }

    function activeDescriptionInputEl() {
        return usePackageLevelEditSave()
            ? document.getElementById('course-map-description')
            : document.getElementById('course-map-description-standalone');
    }

    function resizeDescriptionTextarea() {
        [document.getElementById('course-map-description'), document.getElementById('course-map-description-standalone')]
            .forEach(function (el) {
                if (!el || el.style.display === 'none') return;
                el.style.height = 'auto';
                el.style.height = Math.max(el.scrollHeight, 2.5 * 16) + 'px';
            });
    }

    function syncCourseToHeaderInputs() {
        var nameText = document.getElementById('course-map-name-text');
        var nameInput = document.getElementById('course-map-name');
        var descText = document.getElementById('course-map-description-text');
        var descInput = document.getElementById('course-map-description');
        var dayText = document.getElementById('course-map-event-day-text');
        var dayInput = document.getElementById('course-map-event-day');
        var nameTextSt = document.getElementById('course-map-name-text-standalone');
        var nameInputSt = document.getElementById('course-map-name-standalone');
        var descTextSt = document.getElementById('course-map-description-text-standalone');
        var descInputSt = document.getElementById('course-map-description-standalone');
        var idSt = document.getElementById('course-map-id-standalone');
        var pkgDay = getPackageEventDay();
        var dayDisplay = pkgDay || '(not set)';
        var val = currentCourse ? (currentCourse.name || '') : '';
        var nameDisplay = val || '(no name)';
        if (nameText) nameText.textContent = nameDisplay;
        if (nameTextSt) nameTextSt.textContent = nameDisplay;
        if (nameInput) nameInput.value = val;
        if (nameInputSt) nameInputSt.value = val;
        val = currentCourse ? (currentCourse.description || '') : '';
        var descDisplay = val || '(none)';
        if (descText) descText.textContent = descDisplay;
        if (descTextSt) descTextSt.textContent = descDisplay;
        if (descInput) {
            descInput.value = val;
            if (descInput.style.display && descInput.style.display !== 'none') resizeDescriptionTextarea();
        }
        if (descInputSt) {
            descInputSt.value = val;
            if (descInputSt.style.display && descInputSt.style.display !== 'none') resizeDescriptionTextarea();
        }
        if (dayText) dayText.textContent = dayDisplay;
        if (dayInput) {
            initPackageEventDaySelect();
            dayInput.value = pkgDay;
        }
        var idVal = currentCourseId || '';
        var idEl = document.getElementById('course-map-id');
        if (idEl) idEl.textContent = idVal;
        if (idSt) {
            idSt.textContent = idVal
                ? (isConfigPackageMode() ? 'Config package: ' + idVal : 'Course: ' + idVal)
                : '';
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
        syncCourseToHeaderInputs();
        if (exportBtn) exportBtn.disabled = !currentCourseId;
        if (delBtn) delBtn.disabled = !currentCourseId;
        syncCourseToHeaderInputs();
        setEditMode(isEditMode);
        updateManageResourcesButton();
        updateExportButton();
    }

    function setCourse(id, course) {
        currentCourseId = id;
        currentCourse = course;
        clearDirty();
        resourcesDirty = false;
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
        if (currentCourse) normalizeCourseLocations(currentCourse);
        if (currentCourse && !Array.isArray(currentCourse.flow_control_points)) currentCourse.flow_control_points = [];
        if (currentCourse && typeof currentCourse.segment_break_labels !== 'object') currentCourse.segment_break_labels = {};
        if (currentCourse && typeof currentCourse.segment_break_descriptions !== 'object') currentCourse.segment_break_descriptions = {};
        if (currentCourse && typeof currentCourse.segment_break_ids !== 'object') currentCourse.segment_break_ids = {};
        if (currentCourse && !Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = [];
        extendFromIndex = null;
        extendInsertEndIndex = null;
        syncCourseToHeaderInputs();
        updateCourseUI();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateAddLocationButton();
        updateSameRouteBackButtons();
        updateExportButton();
        updateExtendHint();
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

    /** Drop deprecated loc_description; migrate into notes for one-pager export. */
    function normalizeCourseLocations(course) {
        if (!course || !Array.isArray(course.locations)) return;
        course.locations.forEach(function (loc) {
            if (loc.loc_description && !loc.notes) {
                loc.notes = String(loc.loc_description).trim();
            }
            if (loc.loc_description != null) delete loc.loc_description;
        });
    }

    function truncateNotesPreview(notes, maxLen) {
        var s = (notes || '').trim();
        if (!s) return '—';
        return s.length <= maxLen ? s : s.slice(0, maxLen) + '…';
    }

    var DEFAULT_PACKAGE_RESOURCES = [
        { code: 'fpf', label: 'FPF' },
        { code: 'yssr', label: 'YSSR' },
        { code: 'awp', label: 'AWP' },
        { code: 'vol', label: 'VOL' }
    ];
    var locationEditorIndex = null;
    var locationEditorMap = null;
    var locationEditorMapMarker = null;

    function destroyLocationEditorMap() {
        if (locationEditorMap) {
            locationEditorMap.remove();
            locationEditorMap = null;
            locationEditorMapMarker = null;
        }
    }

    function refreshLocationEditorMap(lat, lon) {
        if (typeof L === 'undefined') return;
        var el = document.getElementById('location-editor-map');
        if (!el) return;
        if (isNaN(lat) || isNaN(lon)) return;
        if (!locationEditorMap) {
            locationEditorMap = L.map(el, {
                scrollWheelZoom: false,
                zoomControl: true,
                attributionControl: false
            });
            L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
                subdomains: ['a', 'b', 'c', 'd'],
                maxZoom: 19
            }).addTo(locationEditorMap);
            locationEditorMapMarker = L.marker([lat, lon]).addTo(locationEditorMap);
            locationEditorMap.setView([lat, lon], 16);
            setTimeout(function () {
                if (locationEditorMap) locationEditorMap.invalidateSize();
            }, 80);
        } else {
            locationEditorMapMarker.setLatLng([lat, lon]);
            locationEditorMap.setView([lat, lon], locationEditorMap.getZoom());
        }
    }

    function distancePointToSegmentMeters(lat, lon, lon1, lat1, lon2, lat2) {
        var dx = lon2 - lon1;
        var dy = lat2 - lat1;
        var len2 = dx * dx + dy * dy;
        var t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((lon - lon1) * dx + (lat - lat1) * dy) / len2));
        var px = lon1 + t * dx;
        var py = lat1 + t * dy;
        return haversineMeters(lon, lat, px, py);
    }

    function distancePointToPolylineMeters(lat, lon, coords, startIdx, endIdx) {
        var best = Infinity;
        for (var i = startIdx; i < endIdx; i++) {
            var c0 = coords[i];
            var c1 = coords[i + 1];
            var d = distancePointToSegmentMeters(lat, lon, c0[0], c0[1], c1[0], c1[1]);
            if (d < best) best = d;
        }
        return best;
    }

    function suggestLocationSegIdClient(location) {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.segments) {
            return { seg_id: '', rationale: '' };
        }
        var coords = currentCourse.geometry.coordinates;
        if (!coords || coords.length < 2) {
            return { seg_id: '', rationale: 'Draw the course route to suggest a segment.' };
        }
        var lat = parseFloat(location.lat);
        var lon = parseFloat(location.lon);
        if (isNaN(lat) || isNaN(lon)) {
            return { seg_id: '', rationale: 'Set coordinates to suggest a segment.' };
        }
        var bestSeg = null;
        var bestDist = Infinity;
        currentCourse.segments.forEach(function (seg) {
            var startIdx = seg.start_index != null ? seg.start_index : 0;
            var endIdx = seg.end_index != null ? seg.end_index : coords.length - 1;
            var d = distancePointToPolylineMeters(lat, lon, coords, startIdx, endIdx);
            if (d < bestDist) {
                bestDist = d;
                bestSeg = seg;
            }
        });
        if (!bestSeg) return { seg_id: '', rationale: '' };
        return {
            seg_id: String(bestSeg.seg_id || '').trim(),
            rationale: 'Nearest segment: ' + (bestSeg.seg_label || bestSeg.seg_id) + '.'
        };
    }

    function applySuggestedSegIdToLocation(loc) {
        if (!loc || (loc.seg_id || '').trim()) return '';
        var result = suggestLocationSegIdClient(loc);
        if (result.seg_id) loc.seg_id = result.seg_id;
        return result.rationale || '';
    }
    var resourcesEditorDraft = null;
    var resourcesEditingIndex = null;
    var RESOURCE_CODE_MAX_LEN = 16;

    function normalizeResourceCodeInput(value) {
        var s = (value || '').toLowerCase().replace(/[^a-z0-9_]/g, '');
        if (s.length > RESOURCE_CODE_MAX_LEN) {
            s = s.slice(0, RESOURCE_CODE_MAX_LEN);
        }
        return s;
    }

    function attachResourceCodeInput(el) {
        if (!el) return;
        el.setAttribute('maxlength', String(RESOURCE_CODE_MAX_LEN));
        el.addEventListener('input', function () {
            var normalized = normalizeResourceCodeInput(el.value);
            if (el.value !== normalized) el.value = normalized;
        });
    }

    function migrateLocationResourceCode(oldCode, newCode) {
        if (!oldCode || !newCode || oldCode === newCode || !currentCourse || !currentCourse.locations) return;
        currentCourse.locations.forEach(function (loc) {
            if (!loc.resources || typeof loc.resources !== 'object') loc.resources = {};
            if (loc.resources[oldCode] != null) {
                loc.resources[newCode] = loc.resources[oldCode];
                delete loc.resources[oldCode];
            }
            var oldCol = oldCode + '_count';
            var newCol = newCode + '_count';
            if (loc[oldCol] != null) {
                loc[newCol] = loc[oldCol];
                delete loc[oldCol];
            }
        });
        setDirty();
    }

    function getPackageResources() {
        var r = window.CONFIG_PACKAGE_RESOURCES;
        if (Array.isArray(r) && r.length) return r.slice();
        return DEFAULT_PACKAGE_RESOURCES.slice();
    }

    function syncLocationResourceCounts(loc) {
        if (!loc) return;
        if (!loc.resources || typeof loc.resources !== 'object') loc.resources = {};
        getPackageResources().forEach(function (res) {
            var code = res.code;
            var col = code + '_count';
            if (loc[col] != null && loc[col] !== '') {
                loc.resources[code] = parseInt(loc[col], 10) || 0;
            }
            loc[col] = loc.resources[code] != null ? loc.resources[code] : 0;
        });
    }

    function showModal(el) {
        if (!el) return;
        el.hidden = false;
        el.setAttribute('aria-hidden', 'false');
    }

    function hideModal(el) {
        if (!el) return;
        el.hidden = true;
        el.setAttribute('aria-hidden', 'true');
    }

    function openResourcesEditorModal() {
        if (!isConfigPackageMode() || !resolveConfigPackageId()) {
            alert('Open a config package to manage resources.');
            return;
        }
        if (usePackageLevelEditSave() && !isEditMode) {
            alert('Click Edit to change resources.');
            return;
        }
        resourcesEditorDraft = getPackageResources().map(function (r) {
            return { code: r.code, label: r.label || r.code.toUpperCase() };
        });
        resourcesEditingIndex = null;
        renderResourcesEditorList();
        showModal(document.getElementById('resources-editor-modal'));
    }

    function renderResourcesEditorList() {
        var list = document.getElementById('resources-editor-list');
        if (!list || !resourcesEditorDraft) return;
        list.innerHTML = '';
        resourcesEditorDraft.forEach(function (res, i) {
            var row = document.createElement('div');
            row.className = 'resource-row';
            if (resourcesEditingIndex === i) {
                var codeInp = document.createElement('input');
                codeInp.type = 'text';
                codeInp.value = res.code;
                codeInp.style.width = '90px';
                codeInp.title = 'Lowercase, max ' + RESOURCE_CODE_MAX_LEN + ' chars';
                attachResourceCodeInput(codeInp);
                var labelInp = document.createElement('input');
                labelInp.type = 'text';
                labelInp.value = res.label;
                labelInp.style.flex = '1';
                labelInp.style.minWidth = '120px';
                labelInp.maxLength = 64;
                var btnDone = document.createElement('button');
                btnDone.type = 'button';
                btnDone.textContent = 'Done';
                btnDone.addEventListener('click', function () {
                    var newCode = normalizeResourceCodeInput(codeInp.value);
                    var newLabel = (labelInp.value || '').trim();
                    if (!newCode || !/^[a-z]/.test(newCode)) {
                        alert('Code must start with a letter (lowercase, max ' + RESOURCE_CODE_MAX_LEN + ' chars).');
                        return;
                    }
                    if (resourcesEditorDraft.some(function (r, j) { return j !== i && r.code === newCode; })) {
                        alert('Resource code already exists.');
                        return;
                    }
                    if (!newLabel) newLabel = newCode.toUpperCase();
                    migrateLocationResourceCode(res.code, newCode);
                    resourcesEditorDraft[i] = { code: newCode, label: newLabel };
                    resourcesEditingIndex = null;
                    renderResourcesEditorList();
                });
                var btnCancelEdit = document.createElement('button');
                btnCancelEdit.type = 'button';
                btnCancelEdit.textContent = 'Cancel';
                btnCancelEdit.addEventListener('click', function () {
                    resourcesEditingIndex = null;
                    renderResourcesEditorList();
                });
                row.appendChild(codeInp);
                row.appendChild(labelInp);
                row.appendChild(btnDone);
                row.appendChild(btnCancelEdit);
            } else {
                var span = document.createElement('span');
                span.style.flex = '1';
                span.innerHTML = '<strong>' + escapeHtml(res.code) + '</strong> — ' + escapeHtml(res.label);
                var btnEdit = document.createElement('button');
                btnEdit.type = 'button';
                btnEdit.textContent = 'Edit';
                btnEdit.addEventListener('click', function () {
                    resourcesEditingIndex = i;
                    renderResourcesEditorList();
                });
                var btnRemove = document.createElement('button');
                btnRemove.type = 'button';
                btnRemove.textContent = 'Remove';
                btnRemove.addEventListener('click', function () {
                    if (resourcesEditorDraft.length <= 1) {
                        alert('At least one resource is required.');
                        return;
                    }
                    resourcesEditorDraft.splice(i, 1);
                    if (resourcesEditingIndex === i) resourcesEditingIndex = null;
                    else if (resourcesEditingIndex != null && resourcesEditingIndex > i) resourcesEditingIndex -= 1;
                    renderResourcesEditorList();
                });
                row.appendChild(span);
                row.appendChild(btnEdit);
                row.appendChild(btnRemove);
            }
            list.appendChild(row);
        });
    }

    function savePackageResources() {
        var pkgId = resolveConfigPackageId();
        if (!pkgId || !resourcesEditorDraft) return;
        if (usePackageLevelEditSave()) {
            window.CONFIG_PACKAGE_RESOURCES = resourcesEditorDraft.map(function (r) {
                return { code: r.code, label: r.label || r.code.toUpperCase() };
            });
            resourcesDirty = true;
            setDirty();
            hideModal(document.getElementById('resources-editor-modal'));
            if (currentCourse && currentCourse.locations) {
                currentCourse.locations.forEach(syncLocationResourceCounts);
            }
            renderLocationsTableHeader();
            renderLocationsList();
            return;
        }
        fetch('/api/config/packages/' + encodeURIComponent(pkgId) + '/resources', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resources: resourcesEditorDraft })
        }).then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
            .then(function (result) {
                if (!result.ok) throw new Error(result.data.detail || 'Save failed');
                window.CONFIG_PACKAGE_RESOURCES = result.data.resources || resourcesEditorDraft;
                hideModal(document.getElementById('resources-editor-modal'));
                if (currentCourse && currentCourse.locations) {
                    currentCourse.locations.forEach(syncLocationResourceCounts);
                }
                renderLocationsList();
                alert('Package resources saved.');
            })
            .catch(function (e) { alert('Failed to save resources: ' + (e.message || String(e))); });
    }

    function openLocationEditorModal(idx, readOnly) {
        if (!currentCourse || !currentCourse.locations || idx < 0 || idx >= currentCourse.locations.length) return;
        destroyLocationEditorMap();
        locationEditorIndex = idx;
        var loc = currentCourse.locations[idx];
        syncLocationResourceCounts(loc);
        var modal = document.getElementById('location-editor-modal');
        var body = document.getElementById('location-editor-body');
        var footer = document.getElementById('location-editor-footer');
        var title = document.getElementById('location-editor-title');
        if (!modal || !body || !footer) return;
        var locId = loc.id != null ? String(loc.id) : String(idx + 1);
        var editable = !readOnly;
        var labelDisplay = (loc.loc_label || '').trim() || '(no label)';
        if (title) title.textContent = locId + ': ' + labelDisplay;
        body.innerHTML = '';
        footer.innerHTML = '';
        applyPackageDayToLocation(loc);
        var segRationale = applySuggestedSegIdToLocation(loc);
        var eventsRationale = applySuggestedEventsToLocation(loc);

        function addSection(heading) {
            var sec = document.createElement('div');
            sec.className = 'location-editor-section';
            var h = document.createElement('h5');
            h.textContent = heading;
            sec.appendChild(h);
            body.appendChild(sec);
            return sec;
        }

        function addField(sec, label, el) {
            var lbl = document.createElement('label');
            lbl.textContent = label;
            lbl.appendChild(el);
            sec.appendChild(lbl);
        }

        var secId = addSection('Identity');
        var inpLabel = document.createElement('input');
        inpLabel.type = 'text';
        inpLabel.value = loc.loc_label || '';
        inpLabel.disabled = !editable;
        addField(secId, 'Label', inpLabel);
        var selType = document.createElement('select');
        LOCATION_TYPES.forEach(function (t) {
            var opt = document.createElement('option');
            opt.value = t.value;
            opt.textContent = t.label;
            if ((loc.loc_type || 'course') === t.value) opt.selected = true;
            selType.appendChild(opt);
        });
        selType.disabled = !editable;
        addField(secId, 'Type', selType);

        var secPlace = addSection('Placement');
        var inpLat = document.createElement('input');
        inpLat.type = 'text';
        inpLat.value = loc.lat != null ? String(loc.lat) : '';
        inpLat.disabled = !editable;
        addField(secPlace, 'Latitude', inpLat);
        var inpLon = document.createElement('input');
        inpLon.type = 'text';
        inpLon.value = loc.lon != null ? String(loc.lon) : '';
        inpLon.disabled = !editable;
        addField(secPlace, 'Longitude', inpLon);
        var mapWrap = document.createElement('div');
        mapWrap.className = 'location-editor-map-wrap';
        var mapEl = document.createElement('div');
        mapEl.id = 'location-editor-map';
        mapEl.className = 'location-editor-map';
        mapWrap.appendChild(mapEl);
        secPlace.appendChild(mapWrap);
        function updateLocationEditorMapFromInputs() {
            var la = parseFloat(inpLat.value);
            var lo = parseFloat(inpLon.value);
            if (!isNaN(la) && !isNaN(lo)) refreshLocationEditorMap(la, lo);
        }
        updateLocationEditorMapFromInputs();
        if (editable) {
            inpLat.addEventListener('input', updateLocationEditorMapFromInputs);
            inpLon.addEventListener('input', updateLocationEditorMapFromInputs);
        }

        var secCourse = addSection('Course link');
        var inpSeg = document.createElement('input');
        inpSeg.type = 'text';
        inpSeg.placeholder = 'e.g. A1 or A1,G1';
        inpSeg.value = loc.seg_id || '';
        inpSeg.disabled = !editable;
        addField(secCourse, 'Segment ID(s)', inpSeg);
        var pkgDay = getPackageEventDay();
        var inpDay = document.createElement('select');
        populateDaySelect(inpDay, loc.day || pkgDay || '', 'Select day');
        inpDay.disabled = !editable || !!pkgDay;
        addField(secCourse, 'Day', inpDay);
        if (pkgDay) {
            var dayHint = document.createElement('div');
            dayHint.style.cssText = 'font-size:0.8rem;color:#7f8c8d;margin-top:0.25rem;';
            dayHint.textContent = 'From package event day (' + pkgDay + ').';
            secCourse.appendChild(dayHint);
        }
        var inpZone = document.createElement('input');
        inpZone.type = 'text';
        inpZone.value = loc.zone != null ? String(loc.zone) : '';
        inpZone.disabled = !editable;
        addField(secCourse, 'Zone', inpZone);
        var eventsDisplay = document.createElement('div');
        eventsDisplay.className = 'location-events-readonly';
        eventsDisplay.style.cssText = 'font-size:0.875rem;color:#34495e;margin-top:0.35rem;';
        var activeEvents = EVENT_CHOICES.filter(function (ev) {
            return (loc[ev.value] || 'n').toString().toLowerCase() === 'y';
        }).map(function (ev) { return ev.label; });
        eventsDisplay.textContent = activeEvents.length
            ? ('Events (from segments): ' + activeEvents.join(', '))
            : 'Events (from segments): none';
        secCourse.appendChild(eventsDisplay);
        var rationaleEl = document.createElement('div');
        rationaleEl.id = 'location-suggest-rationale';
        rationaleEl.style.cssText = 'font-size:0.8rem;color:#7f8c8d;margin-top:0.35rem;';
        var rationaleParts = [];
        if (segRationale) rationaleParts.push(segRationale);
        if (eventsRationale) rationaleParts.push(eventsRationale);
        rationaleEl.textContent = rationaleParts.join(' ');
        secCourse.appendChild(rationaleEl);

        var secTiming = addSection('Timing');
        var inpBuffer = document.createElement('input');
        inpBuffer.type = 'number';
        inpBuffer.min = '0';
        inpBuffer.value = loc.buffer != null ? loc.buffer : 10;
        inpBuffer.disabled = !editable;
        addField(secTiming, 'Buffer (min)', inpBuffer);
        var inpInterval = document.createElement('input');
        inpInterval.type = 'number';
        inpInterval.min = '1';
        inpInterval.value = loc.interval != null ? loc.interval : 5;
        inpInterval.disabled = !editable;
        addField(secTiming, 'Interval (min)', inpInterval);
        var inpProxy = document.createElement('input');
        inpProxy.type = 'text';
        inpProxy.value = loc.proxy_loc_id != null ? String(loc.proxy_loc_id) : '';
        inpProxy.disabled = !editable;
        addField(secTiming, 'Proxy loc ID', inpProxy);

        var secRes = addSection('Resources scheduled');
        var resGrid = document.createElement('div');
        resGrid.className = 'location-resource-grid';
        var resourceInputs = {};
        getPackageResources().forEach(function (res) {
            var code = res.code;
            var lbl = document.createElement('span');
            lbl.textContent = (res.label || code.toUpperCase());
            var inp = document.createElement('input');
            inp.type = 'number';
            inp.min = '0';
            inp.value = (loc.resources && loc.resources[code] != null) ? loc.resources[code] : (loc[code + '_count'] || 0);
            inp.disabled = !editable;
            resourceInputs[code] = inp;
            resGrid.appendChild(lbl);
            resGrid.appendChild(inp);
        });
        secRes.appendChild(resGrid);

        var secSheet = addSection('Loc sheet');
        var inpOnepage = document.createElement('input');
        inpOnepage.type = 'checkbox';
        inpOnepage.checked = (loc.onepage || 'n').toString().toLowerCase() === 'y';
        inpOnepage.disabled = !editable;
        var lblOp = document.createElement('label');
        lblOp.className = 'location-onepager-inline';
        lblOp.appendChild(inpOnepage);
        var onepagerText = document.createElement('span');
        onepagerText.textContent = 'Create One-Pager';
        lblOp.appendChild(onepagerText);
        secSheet.appendChild(lblOp);
        var inpEquip = document.createElement('input');
        inpEquip.type = 'text';
        inpEquip.value = loc.equipment || '';
        inpEquip.disabled = !editable;
        addField(secSheet, 'Equipment', inpEquip);
        var inpContact = document.createElement('input');
        inpContact.type = 'text';
        inpContact.value = loc.contact || '';
        inpContact.disabled = !editable;
        addField(secSheet, 'Contact', inpContact);
        var inpNotes = document.createElement('textarea');
        inpNotes.rows = 4;
        inpNotes.value = loc.notes || '';
        inpNotes.disabled = !editable;
        addField(secSheet, 'Notes', inpNotes);

        var btnClose = document.createElement('button');
        btnClose.type = 'button';
        btnClose.textContent = 'Close';
        btnClose.onclick = function () {
            destroyLocationEditorMap();
            hideModal(modal);
            locationEditorIndex = null;
        };
        footer.appendChild(btnClose);

        if (editable) {
            var btnSave = document.createElement('button');
            btnSave.type = 'button';
            btnSave.className = 'primary';
            btnSave.textContent = 'Save location';
            btnSave.onclick = function () {
                loc.loc_label = inpLabel.value.trim();
                loc.loc_type = selType.value || 'course';
                var lat = parseFloat(inpLat.value);
                var lon = parseFloat(inpLon.value);
                if (isNaN(lat) || isNaN(lon)) {
                    alert('Enter valid latitude and longitude.');
                    return;
                }
                loc.lat = lat;
                loc.lon = lon;
                loc.seg_id = inpSeg.value.trim();
                if (!loc.seg_id) applySuggestedSegIdToLocation(loc);
                loc.day = getPackageEventDay() || inpDay.value.trim();
                loc.zone = inpZone.value.trim();
                applySuggestedEventsToLocation(loc);
                loc.buffer = parseInt(inpBuffer.value, 10) || 10;
                loc.interval = parseInt(inpInterval.value, 10) || 5;
                loc.proxy_loc_id = inpProxy.value.trim();
                loc.onepage = inpOnepage.checked ? 'y' : 'n';
                loc.equipment = inpEquip.value.trim();
                loc.contact = inpContact.value.trim();
                loc.notes = inpNotes.value.trim();
                if (!loc.resources) loc.resources = {};
                getPackageResources().forEach(function (res) {
                    var n = parseInt(resourceInputs[res.code].value, 10);
                    loc.resources[res.code] = isNaN(n) ? 0 : Math.max(0, n);
                    loc[res.code + '_count'] = loc.resources[res.code];
                });
                destroyLocationEditorMap();
                hideModal(modal);
                locationEditorIndex = null;
                setDirty();
                renderLocationPins();
                renderLocationsList();
                updateCourseUI();
            };
            footer.insertBefore(btnSave, btnClose);
        }

        highlightLocationRow(idx);
        showModal(modal);
        setTimeout(updateLocationEditorMapFromInputs, 120);
    }

    function suggestLocationEventsClient(location) {
        var segments = (currentCourse && currentCourse.segments) || [];
        var segRaw = (location && location.seg_id) ? String(location.seg_id).trim() : '';
        var segIds = [];
        if (segRaw) {
            segRaw.replace(/"/g, '').split(',').forEach(function (s) {
                s = s.trim();
                if (s) segIds.push(s);
            });
        }
        var events = {};
        EVENT_CHOICES.forEach(function (ev) { events[ev.value] = 'n'; });
        if (!segIds.length) {
            return { events: events, rationale: 'Set segment ID(s) to derive events from the course.' };
        }
        var matched = [];
        var union = {};
        segments.forEach(function (seg) {
            var sid = String(seg.seg_id || '').trim();
            if (sid && segIds.indexOf(sid) >= 0) matched.push(seg);
        });
        if (!matched.length) {
            return { events: events, rationale: 'No course segment matches seg_id "' + segIds.join(',') + '".' };
        }
        var labels = [];
        matched.forEach(function (seg) {
            labels.push(seg.seg_label || seg.seg_id || '');
            (seg.events || []).forEach(function (ev) {
                union[String(ev).trim().toLowerCase()] = true;
            });
        });
        EVENT_CHOICES.forEach(function (ev) {
            events[ev.value] = union[ev.value] ? 'y' : 'n';
        });
        var active = EVENT_CHOICES.filter(function (ev) { return events[ev.value] === 'y'; })
            .map(function (ev) { return ev.label; });
        return {
            events: events,
            rationale: 'From segment(s) ' + labels.join(', ') + ': ' + (active.length ? active.join(', ') : '(none)')
        };
    }

    function applySuggestedEventsToLocation(loc) {
        if (!loc) return;
        var result = suggestLocationEventsClient(loc);
        EVENT_CHOICES.forEach(function (ev) {
            loc[ev.value] = result.events[ev.value] || 'n';
        });
        return result.rationale;
    }

    function renderLocationsTableHeader() {
        var row = document.getElementById('locations-thead-row');
        if (!row) return;
        row.innerHTML = '';
        ['ID', 'Type', 'Label'].forEach(function (text) {
            var th = document.createElement('th');
            th.textContent = text;
            row.appendChild(th);
        });
        getPackageResources().forEach(function (res) {
            var th = document.createElement('th');
            th.textContent = res.code;
            th.title = (res.label || res.code) + ' (' + res.code + '_count)';
            row.appendChild(th);
        });
        if (isEditMode) {
            var actionTh = document.createElement('th');
            actionTh.textContent = '';
            row.appendChild(actionTh);
        }
    }

    function highlightLocationRow(idx) {
        document.querySelectorAll('#locations-tbody tr:not(.locations-totals-row)').forEach(function (tr) {
            tr.classList.remove('location-row-highlight');
        });
        var rows = document.querySelectorAll('#locations-tbody tr:not(.locations-totals-row)');
        if (rows[idx]) rows[idx].classList.add('location-row-highlight');
    }

    var LOCATION_TYPES = (window.LOCATION_TYPES_FROM_SERVER || []).slice().sort(function (a, b) { return (a.label || a.value).localeCompare(b.label || b.value); });
    var EVENT_CHOICES = window.EVENT_CHOICES_FROM_SERVER || [{ value: 'full', label: 'Full' }, { value: 'half', label: 'Half' }, { value: '10k', label: '10K' }, { value: 'elite', label: 'Elite' }, { value: 'open', label: 'Open' }];
    var LOCATION_PIN_COLORS = {
        aid: '#e74c3c',
        course: '#27ae60',
        extract: '#9c27b0',
        official: '#f1c40f',
        traffic: '#95a5a6',
        water: '#3498db'
    };
    var ROUTE_COLOR = '#2563eb';
    var ROUTE_LINE_CASING_STYLE = { color: '#ffffff', weight: 7, opacity: 0.9, lineCap: 'round', lineJoin: 'round' };
    var ROUTE_LINE_STYLE = { color: ROUTE_COLOR, weight: 5, opacity: 0.92, lineCap: 'round', lineJoin: 'round' };
    var SEGMENT_HIT_STYLE = { color: ROUTE_COLOR, weight: 22, opacity: 0, lineCap: 'round', lineJoin: 'round' };
    var START_MARKER = { bg: '#22c55e', border: '#15803d' };
    var FINISH_MARKER = { bg: '#ef4444', border: '#b91c1c' };
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
    /** When set by "Add pin on segment", only allow adding a pin at a vertex in this range. { startIdx, endIdx } or null. */
    let addPinSegmentRange = null;
    /** When set, new points are inserted after this index (extend from segment pin). null = append at end. */
    let extendFromIndex = null;
    /** In extend mode, index of last inserted point (route from here for next click). */
    let extendInsertEndIndex = null;
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
        // Preserve metadata by ordinal (position in list) so that moving a pin doesn't wipe events/labels.
        // When segment count is unchanged, segment at position i keeps existing[i]'s metadata.
        // When a pin is added (one more segment), the new segment inherits from the segment it was split from.
        // When a pin is removed (one fewer segment), remaining segments keep their ordinal mapping.
        var existingArr = (currentCourse.segments || []).slice();
        function prevAt(ordinal) {
            if (ordinal < 0 || ordinal >= existingArr.length) return null;
            var s = existingArr[ordinal];
            return s ? { seg_label: s.seg_label, events: s.events, width_m: s.width_m, schema: s.schema, direction: s.direction, description: s.description, info_icon_lat: s.info_icon_lat, info_icon_lon: s.info_icon_lon } : null;
        }
        function segmentLabelFromPinRange(startIdx, endIdx, coordsLen, ordinal) {
            var startLbl = getPinLabelForIndex(startIdx, coordsLen);
            var endLbl = getPinLabelForIndex(endIdx, coordsLen);
            if (startLbl && endLbl && startLbl !== endLbl) return startLbl + ' to ' + endLbl;
            return endLbl || startLbl || ('Segment ' + (ordinal + 1));
        }
        var segs = [];
        var startIdx = 0;
        for (var b = 0; b <= breaks.length; b++) {
            var endIdx = b < breaks.length ? breaks[b] : coords.length - 1;
            if (endIdx <= startIdx) continue;
            var from_km = cum[startIdx], to_km = cum[endIdx];
            var zeroLength = Math.abs(from_km - to_km) < 1e-6;
            if (zeroLength && b < breaks.length) {
                startIdx = endIdx;
                continue;
            }
            var ordinal = segs.length;
            var prev = prevAt(ordinal);
            var defaultLabel = segmentLabelFromPinRange(startIdx, endIdx, coords.length, ordinal);
            var inheritedLabel = (prev && prev.seg_label) ? prev.seg_label : '';
            var useInherited = inheritedLabel && inheritedLabel !== 'Finish' && !/^Segment \d+$/.test(inheritedLabel);
            segs.push({
                seg_id: String(segs.length + 1),
                seg_label: useInherited ? inheritedLabel : defaultLabel,
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
            var prev0 = prevAt(0);
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
        // Apply flow-control: at each flow_control point, set segment.events for matching (start_index, end_index)
        var fcp = currentCourse.flow_control_points || [];
        for (var fc = 0; fc < fcp.length; fc++) {
            var v = fcp[fc].vertex_index;
            var branches = fcp[fc].branches || [];
            for (var br = 0; br < branches.length; br++) {
                var endV = branches[br].end_vertex_index;
                var evts = branches[br].events || [];
                for (var si = 0; si < segs.length; si++) {
                    if (segs[si].start_index === v && segs[si].end_index === endV) {
                        segs[si].events = evts.slice();
                        break;
                    }
                }
            }
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
        var rejoinWrap = document.getElementById('rejoin-at-wrap');
        var rejoinSelect = document.getElementById('rejoin-at-pin');
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
        if (rejoinWrap) rejoinWrap.style.display = sameRouteBackMode ? 'inline-flex' : 'none';
        if (sameRouteBackMode && rejoinSelect && currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates) {
            var coords = currentCourse.geometry.coordinates;
            var breaks = (currentCourse.segment_breaks || []).slice().sort(function (a, b) { return a - b; }).filter(function (i) { return i >= 0 && i < coords.length; });
            var labels = currentCourse.segment_break_labels || {};
            rejoinSelect.innerHTML = '';
            var addOpt = function (value, text) {
                var opt = document.createElement('option');
                opt.value = value;
                opt.textContent = text;
                rejoinSelect.appendChild(opt);
            };
            var added = {};
            addOpt(0, 'Start');
            added[0] = true;
            breaks.forEach(function (idx) {
                var label = (labels[idx] || labels['' + idx] || '').trim() || ('Segment boundary @ ' + idx);
                addOpt(idx, label);
                added[idx] = true;
            });
            if (coords.length > 1) {
                addOpt(coords.length - 1, 'Last point');
                added[coords.length - 1] = true;
            }
            var currentIdx = typeof turnaroundMarkerIndex !== 'undefined' ? turnaroundMarkerIndex : (coords.length > 1 ? coords.length - 2 : 0);
            if (!added[currentIdx]) addOpt(currentIdx, 'Vertex ' + currentIdx);
            rejoinSelect.value = String(currentIdx);
        }
    }

    function setRejoinIndexFromSelect(idx) {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || idx == null) return;
        var coords = currentCourse.geometry.coordinates;
        idx = Math.max(0, Math.min(parseInt(idx, 10), coords.length - 1));
        turnaroundMarkerIndex = idx;
        if (turnaroundMarker) {
            var c = coords[idx];
            turnaroundMarker._turnaroundIndex = idx;
            turnaroundMarker.setLatLng([c[1], c[0]]);
        }
    }

    function updateExportButton() {
        const btn = document.getElementById('btn-export');
        const canExport = !!(currentCourseId && currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates && currentCourse.geometry.coordinates.length >= 2);
        if (btn) btn.disabled = !canExport;
    }

    function updateExtendHint() {
        var hintEl = document.getElementById('extend-hint');
        var doneBtn = document.getElementById('btn-done-extending');
            if (extendFromIndex != null && currentCourse && currentCourse.geometry && currentCourse.geometry.coordinates) {
            var label = (currentCourse.segment_break_labels && currentCourse.segment_break_labels[extendFromIndex]) ? currentCourse.segment_break_labels[extendFromIndex] : ('point ' + extendFromIndex);
            var endLabel = (currentCourse.segment_break_labels && currentCourse.segment_break_labels[extendInsertEndIndex]) ? currentCourse.segment_break_labels[extendInsertEndIndex] : (extendInsertEndIndex != null ? ('point ' + extendInsertEndIndex) : '');
            if (hintEl) {
                hintEl.style.display = 'block';
                hintEl.innerHTML = 'Fork from: <strong>' + label + '</strong>. '
                    + (extendInsertEndIndex != null ? 'Line currently ends at <strong>' + (endLabel || 'rejoin') + '</strong>. Each map click adds a point <em>from here</em>. ' : '')
                    + 'Add outbound points to the turn (e.g. Full Turn). Then in the <strong>toolbar</strong>, click <strong>Same Route Back</strong>, set Rejoin at to &quot;' + (label || 'this pin') + '&quot;, click Confirm. Then either add more points (from the rejoin) or click <strong>Done extending</strong>.';
            }
            if (doneBtn) {
                doneBtn.style.display = 'inline-block';
                doneBtn.disabled = false;
            }
        } else {
            if (hintEl) hintEl.style.display = 'none';
            if (doneBtn) {
                doneBtn.style.display = 'none';
                doneBtn.disabled = true;
            }
        }
    }

    function shiftIndicesAfter(breaksOrTurnarounds, afterIndex, delta) {
        if (!Array.isArray(breaksOrTurnarounds)) return;
        for (var j = 0; j < breaksOrTurnarounds.length; j++) {
            if (breaksOrTurnarounds[j] > afterIndex) breaksOrTurnarounds[j] += delta;
        }
    }

    /** When segment_breaks indices shift (insert/delete points), update labels/descriptions/ids and flow_control_points so keys/indices match. */
    function shiftSegmentBreakMetadata(afterIndex, delta) {
        if (!currentCourse || delta === 0) return;
        ['segment_break_labels', 'segment_break_descriptions', 'segment_break_ids'].forEach(function (key) {
            var obj = currentCourse[key];
            if (!obj || typeof obj !== 'object') return;
            var toAdd = {};
            Object.keys(obj).forEach(function (k) {
                var idx = parseInt(k, 10);
                if (isNaN(idx)) return;
                if (idx > afterIndex) {
                    toAdd[idx + delta] = obj[k];
                }
            });
            Object.keys(toAdd).forEach(function (newIdx) {
                var oldIdx = newIdx - delta;
                delete obj[oldIdx];
                delete obj['' + oldIdx];
                obj[newIdx] = toAdd[newIdx];
            });
        });
        var fcp = currentCourse.flow_control_points;
        if (Array.isArray(fcp)) {
            fcp.forEach(function (pt) {
                if (pt.vertex_index > afterIndex) pt.vertex_index += delta;
                var branches = pt.branches || [];
                branches.forEach(function (b) {
                    if (b.end_vertex_index > afterIndex) b.end_vertex_index += delta;
                });
            });
        }
        var td = currentCourse.turnaround_descriptions;
        if (td && typeof td === 'object') {
            var toAddT = {};
            Object.keys(td).forEach(function (k) {
                var idx = parseInt(k, 10);
                if (!isNaN(idx) && idx > afterIndex) toAddT[idx + delta] = td[k];
            });
            Object.keys(toAddT).forEach(function (newIdx) {
                var oldIdx = newIdx - delta;
                delete td[oldIdx];
                delete td['' + oldIdx];
                td[newIdx] = toAddT[newIdx];
            });
        }
    }

    function undoLastPoint() {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length === 0) return;
        var coords = currentCourse.geometry.coordinates;
        var toRemove = (lastAddedPointCount > 0 && lastAddedPointCount < coords.length) ? lastAddedPointCount : 1;
        if (extendFromIndex != null && extendInsertEndIndex != null) {
            var removeFrom = extendInsertEndIndex - toRemove + 1;
            if (removeFrom <= extendFromIndex) return;
            var oldEnd = extendInsertEndIndex;
            coords.splice(removeFrom, toRemove);
            shiftIndicesAfter(currentCourse.segment_breaks, oldEnd, -toRemove);
            shiftSegmentBreakMetadata(oldEnd, -toRemove);
            shiftIndicesAfter(currentCourse.turnaround_indices, oldEnd, -toRemove);
            extendInsertEndIndex -= toRemove;
        } else {
            for (var i = 0; i < toRemove; i++) coords.pop();
        }
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
        renderUturnIcons();
        setDirty();
        updateDrawButtons();
        updateSegmentPinButton();
        updateUndoButton();
        updateExtendHint();
        updateCourseUI();
    }

    function eventsToDisplayList(events) {
        if (!events || !events.length) return '';
        var eidLower = function (v) { return String(v || '').toLowerCase(); };
        return (events || []).map(function (eid) {
            var ev = (EVENT_CHOICES || []).find(function (x) { return eidLower(x.value || x) === eidLower(eid); });
            return ev && ev.label ? ev.label : (eid && String(eid).charAt(0).toUpperCase() + String(eid).slice(1));
        }).join(', ');
    }

    function openSegmentEditInTile(segIdx) {
        var s = currentCourse.segments[segIdx];
        if (!s) return;
        var segId = (s.seg_id != null && s.seg_id !== '') ? String(s.seg_id) : String(segIdx + 1);
        var tile = document.getElementById('segment-edit-tile');
        var titleEl = document.getElementById('segment-edit-tile-title');
        var contentEl = document.getElementById('segment-edit-tile-content');
        var saveBtn = document.getElementById('segment-edit-tile-save');
        var cancelBtn = document.getElementById('segment-edit-tile-cancel');
        if (!tile || !contentEl) return;
        titleEl.textContent = 'Edit segment ' + segId;
        contentEl.innerHTML = '';
        function addLabel(text) { var l = document.createElement('label'); l.textContent = text; l.style.display = 'block'; l.style.marginTop = '8px'; l.style.marginBottom = '2px'; contentEl.appendChild(l); }
        function addInput(attr, val) {
            var el = document.createElement('input');
            el.type = attr === 'number' ? 'number' : 'text';
            el.style.display = 'block'; el.style.width = '100%'; el.style.marginBottom = '8px'; el.style.boxSizing = 'border-box';
            if (attr === 'number') { el.min = 0; el.step = 0.5; }
            el.value = val != null ? val : '';
            contentEl.appendChild(el);
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
        contentEl.appendChild(selSchema);
        addLabel('Direction');
        var selDirection = document.createElement('select');
        selDirection.style.display = 'block'; selDirection.style.width = '100%'; selDirection.style.marginBottom = '8px'; selDirection.style.boxSizing = 'border-box';
        DIRECTION_OPTIONS.forEach(function (o) { var opt = document.createElement('option'); opt.value = o.value; opt.textContent = o.label; if (o.value === (s.direction || 'uni')) opt.selected = true; selDirection.appendChild(opt); });
        contentEl.appendChild(selDirection);
        addLabel('Description');
        var inputDesc = document.createElement('textarea');
        inputDesc.rows = 2; inputDesc.style.display = 'block'; inputDesc.style.width = '100%'; inputDesc.style.marginBottom = '8px'; inputDesc.style.boxSizing = 'border-box';
        inputDesc.value = s.description || '';
        contentEl.appendChild(inputDesc);
        addLabel('Events using this segment');
        var eventsDiv = document.createElement('div');
        eventsDiv.style.marginBottom = '8px';
        var selectedEvents = (s.events || []).slice();
        (EVENT_CHOICES || []).forEach(function (ev) {
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = ev.value || ev;
            cb.checked = selectedEvents.indexOf(ev.value || ev) >= 0;
            cb.style.marginRight = '4px';
            var span = document.createElement('span');
            span.textContent = ev.label || ev.value || ev;
            span.style.marginRight = '10px';
            eventsDiv.appendChild(cb);
            eventsDiv.appendChild(span);
        });
        contentEl.appendChild(eventsDiv);
        tile.style.display = 'block';
        var onSave = function () {
            s.seg_label = (inputLabel.value && inputLabel.value.trim()) ? inputLabel.value.trim() : segId;
            s.width_m = parseFloat(inputWidth.value);
            if (isNaN(s.width_m) || s.width_m < 0) s.width_m = 3;
            s.schema = selSchema.value || 'on_course_open';
            s.direction = selDirection.value || 'uni';
            s.description = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
            s.events = [];
            eventsDiv.querySelectorAll('input[type="checkbox"]').forEach(function (cb) { if (cb.checked) s.events.push(cb.value); });
            if (s.events.length === 0) s.events = (EVENT_CHOICES || []).map(function (e) { return e.value || e; });
            tile.style.display = 'none';
            syncSegmentsFromBreaks();
            renderSegmentInfoIcons();
            renderSegmentPins();
            renderSegmentsList();
            setDirty();
            updateCourseUI();
        };
        var onCancel = function () { tile.style.display = 'none'; };
        saveBtn.onclick = onSave;
        cancelBtn.onclick = onCancel;
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
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
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
        var label = (seg.seg_label || '').trim();
        var isDefaultLabel = label === 'Finish' || /^Segment \d+$/.test(label);
        if (label && !isDefaultLabel) return true;
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
                var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(info).setLatLng(e.latlng).openOn(window.courseMappingMap);
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
        var addStartFinishMarker = function (lat, lon, icon, pointType, coordIndex, coordIndex2) {
            var m = L.marker([lat, lon], { icon: icon, draggable: isEditMode });
            m._pointType = pointType;
            m._coordIndex = coordIndex;
            m._coordIndex2 = coordIndex2;
            var tip = pointType === 'sf' ? 'Start/Finish' : (pointType === 'start' ? 'Start' : 'Finish');
            if (isEditMode) m.bindTooltip(tip + ' (drag to move or click to edit)', { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
            else m.bindTooltip(tip, { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
            if (isEditMode) {
                m.on('dragend', function () {
                    var ll = m.getLatLng();
                    coords[coordIndex] = [ll.lng, ll.lat];
                    if (coordIndex2 != null) coords[coordIndex2] = [ll.lng, ll.lat];
                    syncSegmentsFromBreaks();
                    renderCourseLine();
                    renderSegmentPins();
                    renderStartFinishIcons();
                    renderUturnIcons();
                    renderSegmentsList();
                    setDirty();
                    updateCourseUI();
                });
                m.on('click', function (e) {
                    L.DomEvent.stopPropagation(e);
                    var breaks = currentCourse.segment_breaks || [];
                    var idx = pointType === 'sf' ? coordIndex2 : coordIndex;
                    if (idx != null && breaks.indexOf(idx) >= 0) {
                        openSegmentPinPopupForIndex(idx);
                    } else {
                        openPointEditTile(pointType === 'sf' ? 'start' : pointType, coordIndex, e.latlng, function () {}, pointType === 'sf' ? coordIndex2 : null);
                    }
                });
            }
            startFinishLayer.addLayer(m);
        };
        if (samePoint && last) {
            var sfIcon = L.divIcon({
                className: 'start-finish-icon',
                html: '<div style="width:20px;height:20px;background:' + START_MARKER.bg + ';color:#fff;border:3px solid ' + FINISH_MARKER.border + ';border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;">S/F</div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            addStartFinishMarker(first[1], first[0], sfIcon, 'sf', 0, lastIdx);
        } else {
            var startIcon = L.divIcon({
                className: 'start-finish-icon',
                html: '<div style="width:20px;height:20px;background:' + START_MARKER.bg + ';color:#fff;border:2px solid ' + START_MARKER.border + ';border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">S</div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            addStartFinishMarker(first[1], first[0], startIcon, 'start', 0, null);
            if (coords.length >= 2) {
                var finishIcon = L.divIcon({
                    className: 'start-finish-icon',
                    html: '<div style="width:20px;height:20px;background:' + FINISH_MARKER.bg + ';color:#fff;border:2px solid ' + FINISH_MARKER.border + ';border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;">F</div>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                });
                addStartFinishMarker(last[1], last[0], finishIcon, 'finish', lastIdx, null);
            }
        }
        startFinishLayer.addTo(window.courseMappingMap);
        if (window.courseMappingMap && segmentPinsLayer && window.courseMappingMap.hasLayer(segmentPinsLayer)) {
            window.courseMappingMap.removeLayer(segmentPinsLayer);
            segmentPinsLayer.addTo(window.courseMappingMap);
        }
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
        var inExtendMode = extendFromIndex != null && extendInsertEndIndex != null;
        segments.forEach(function (seg, segIdx) {
            var startIdx = seg.start_index != null ? seg.start_index : 0;
            var endIdx = seg.end_index != null ? seg.end_index : (coords.length - 1);
            var latlngChunks = [];
            if (inExtendMode && startIdx <= extendInsertEndIndex && endIdx >= extendInsertEndIndex + 1) {
                var mainToFork = [];
                for (var i = startIdx; i <= extendFromIndex; i++) mainToFork.push([coords[i][1], coords[i][0]]);
                var forkOutbound = [];
                for (var fi = extendFromIndex; fi <= extendInsertEndIndex; fi++) forkOutbound.push([coords[fi][1], coords[fi][0]]);
                var mainContinuation = [];
                mainContinuation.push([coords[extendFromIndex][1], coords[extendFromIndex][0]]);
                for (var mi = extendInsertEndIndex + 1; mi <= endIdx; mi++) mainContinuation.push([coords[mi][1], coords[mi][0]]);
                if (mainToFork.length >= 2) latlngChunks.push(mainToFork);
                if (forkOutbound.length >= 2) latlngChunks.push(forkOutbound);
                if (mainContinuation.length >= 2) latlngChunks.push(mainContinuation);
            } else {
                var latlngs = [];
                for (var i = startIdx; i <= endIdx; i++) latlngs.push([coords[i][1], coords[i][0]]);
                if (latlngs.length >= 2) latlngChunks.push(latlngs);
            }
            latlngChunks.forEach(function (latlngs) {
            if (latlngs.length < 2) return;
            var casing = L.polyline(latlngs, ROUTE_LINE_CASING_STYLE);
            casing._segmentIndex = segIdx;
            segmentLinesLayer.addLayer(casing);
            var line = L.polyline(latlngs, ROUTE_LINE_STYLE);
            line._segmentIndex = segIdx;
            var openPopup = function (e) {
                if (sameRouteBackMode && e && e.latlng) {
                    L.DomEvent.stopPropagation(e);
                    setTurnaroundFromClick(e.latlng);
                    return;
                }
                if (segmentPinMode || locationPinMode) return;
                if ((drawMode || (extendFromIndex != null && extendInsertEndIndex != null)) && mapClickHandler && e && e.latlng) {
                    L.DomEvent.stopPropagation(e);
                    mapClickHandler(e);
                    return;
                }
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
                        L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(viewInfo).setLatLng(latlng).openOn(window.courseMappingMap);
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

    /** Return true if two coord pairs are the same (same location). */
    function sameCoord(c1, c2) {
        if (!c1 || !c2) return false;
        return Math.abs((c1[0] || 0) - (c2[0] || 0)) < 1e-9 && Math.abs((c1[1] || 0) - (c2[1] || 0)) < 1e-9;
    }

    /** Open flow-control editor: at this pin, which events take which outgoing leg. Updates flow_control_points and syncs segments.
     * When the same location has multiple vertices (e.g. Friel before 10K leg and Friel after return), we show all legs from any vertex at this location. */
    function openFlowControlForPin(pinIndex, latlng) {
        if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates) return;
        syncSegmentsFromBreaks();
        var coords = currentCourse.geometry.coordinates;
        var segments = currentCourse.segments || [];
        var pinCoord = coords[pinIndex];
        var breaksAtSameLocation = (currentCourse.segment_breaks || []).filter(function (idx) {
            return idx >= 0 && idx < coords.length && sameCoord(coords[idx], pinCoord);
        });
        var segmentsFromPin = segments.filter(function (s) {
            return breaksAtSameLocation.indexOf(s.start_index) >= 0;
        });
        var pinLabel = getSegmentBreakLabel(pinIndex) || getPinLabelForIndex(pinIndex, coords.length) || ('Vertex ' + pinIndex);
        var content = document.createElement('div');
        content.className = 'course-map-popup-wrap';
        var title = document.createElement('div');
        title.style.fontWeight = 'bold';
        title.style.marginBottom = '0.5rem';
        title.textContent = 'Flow control at: ' + (pinLabel || 'this point');
        content.appendChild(title);
        var hint = document.createElement('p');
        hint.style.fontSize = '0.8rem';
        hint.style.color = '#7f8c8d';
        hint.style.marginBottom = '0.5rem';
        hint.textContent = 'Which event(s) take which leg from this point?';
        content.appendChild(hint);
        if (segmentsFromPin.length === 0) {
            var none = document.createElement('p');
            none.style.fontSize = '0.85rem';
            none.textContent = 'No outgoing legs from this point (no segment starts here). Add segment pins and legs first.';
            content.appendChild(none);
        } else {
            var fcp = currentCourse.flow_control_points || [];
            var eventIds = (EVENT_CHOICES || []).map(function (e) { return (e.value != null ? e.value : e).toString().toLowerCase(); });
            var checkboxesBySeg = {};
            segmentsFromPin.forEach(function (seg) {
                var row = document.createElement('div');
                row.style.marginBottom = '0.6rem';
                var endLabel = getPinLabelForIndex(seg.end_index, coords.length) || seg.seg_label || ('Segment to ' + seg.end_index);
                var legLabel = document.createElement('label');
                legLabel.style.display = 'block';
                legLabel.style.fontWeight = '500';
                legLabel.style.marginBottom = '0.25rem';
                legLabel.textContent = 'Leg to: ' + endLabel;
                row.appendChild(legLabel);
                var boxWrap = document.createElement('div');
                boxWrap.style.display = 'flex';
                boxWrap.style.flexWrap = 'wrap';
                boxWrap.style.gap = '0.5rem';
                var existingAtV = fcp.filter(function (x) { return x.vertex_index === seg.start_index; })[0];
                var branch = existingAtV && (existingAtV.branches || []).filter(function (b) { return b.end_vertex_index === seg.end_index; })[0];
                var selectedEvents = (branch && branch.events && branch.events.length) ? branch.events.map(function (x) { return String(x).toLowerCase(); }) : (seg.events || []).map(function (x) { return String(x).toLowerCase(); });
                checkboxesBySeg[seg.start_index + '-' + seg.end_index] = {};
                eventIds.forEach(function (eid) {
                    var evLabel = eid;
                    (EVENT_CHOICES || []).forEach(function (ev) { if ((ev.value || ev) === eid && ev.label) evLabel = ev.label; });
                    var lbl = document.createElement('label');
                    lbl.style.display = 'inline-flex';
                    lbl.style.alignItems = 'center';
                    lbl.style.marginRight = '8px';
                    var cb = document.createElement('input');
                    cb.type = 'checkbox';
                    cb.value = eid;
                    if (selectedEvents.indexOf(eid) >= 0) cb.checked = true;
                    lbl.appendChild(cb);
                    lbl.appendChild(document.createTextNode(' ' + evLabel));
                    boxWrap.appendChild(lbl);
                    checkboxesBySeg[seg.start_index + '-' + seg.end_index][eid] = cb;
                });
                row.appendChild(boxWrap);
                content.appendChild(row);
            });
        }
        var btnWrap = document.createElement('div');
        btnWrap.style.marginTop = '0.75rem';
        var btnSave = document.createElement('button');
        btnSave.type = 'button';
        btnSave.textContent = 'Save';
        btnSave.style.marginRight = '6px';
        var btnCancel = document.createElement('button');
        btnCancel.type = 'button';
        btnCancel.textContent = 'Cancel';
        btnWrap.appendChild(btnSave);
        btnWrap.appendChild(btnCancel);
        content.appendChild(btnWrap);
        btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
        btnSave.onclick = function () {
            if (segmentsFromPin.length === 0) { window.courseMappingMap.closePopup(); return; }
            var fcpList = currentCourse.flow_control_points || [];
            currentCourse.flow_control_points = fcpList.filter(function (x) { return breaksAtSameLocation.indexOf(x.vertex_index) < 0; });
            for (var vi = 0; vi < breaksAtSameLocation.length; vi++) {
                var v = breaksAtSameLocation[vi];
                var segsAtV = segmentsFromPin.filter(function (s) { return s.start_index === v; });
                var branches = segsAtV.map(function (seg) {
                    var key = seg.start_index + '-' + seg.end_index;
                    var cbs = checkboxesBySeg[key];
                    var evts = [];
                    if (cbs) for (var eid in cbs) if (cbs[eid].checked) evts.push(eid);
                    return { end_vertex_index: seg.end_index, events: evts };
                });
                currentCourse.flow_control_points.push({ vertex_index: v, label: pinLabel, branches: branches });
            }
            syncSegmentsFromBreaks();
            renderSegmentPins();
            renderSegmentsList();
            setDirty();
            updateCourseUI();
            window.courseMappingMap.closePopup();
        };
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
    }

    /** Open the segment-pin popup (Edit, Delete, Extend from here) at a pin by index. Used when clicking From/To in Segments table. */
    function openSegmentPinPopupForIndex(pinIndex) {
        if (!window.courseMappingMap || !currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates) return;
        var coords = currentCourse.geometry.coordinates;
        if (pinIndex < 0 || pinIndex >= coords.length) return;
        var c = coords[pinIndex];
        var latlng = L.latLng(c[1], c[0]);
        window.courseMappingMap.closePopup();
        window.courseMappingMap.panTo(latlng, { animate: true, duration: 0.3 });
        var coordsLen = coords.length;
        var isStart = pinIndex <= 0;
        var isFinish = pinIndex >= coordsLen - 1;
        var label = isStart ? 'Start' : (isFinish ? 'Finish' : getSegmentBreakLabel(pinIndex));
        var pinId = getSegmentBreakId(pinIndex);
        var desc = getSegmentBreakDescription(pinIndex);
        var content = document.createElement('div');
        content.innerHTML = buildPopupRowsHtml([
            { label: 'ID', value: String(pinId) },
            { label: 'Label', value: label },
            { label: 'Description', value: desc || '' }
        ]);
        content.classList.add('course-map-popup-wrap');
        if (isEditMode) {
            var btnWrap = document.createElement('div');
            btnWrap.style.marginTop = '0.5rem';
            var pinTitle = isStart ? 'Start' : (isFinish ? 'Finish' : label);
            addEditLatLonButton(btnWrap, pinIndex, latlng, pinTitle, desc, function (d) {
                if (isStart) currentCourse.start_description = d;
                else if (isFinish) currentCourse.end_description = d;
                else {
                    if (!currentCourse.segment_break_descriptions) currentCourse.segment_break_descriptions = {};
                    currentCourse.segment_break_descriptions[pinIndex] = d;
                }
            }, function () {
                renderSegmentPins();
                renderSegmentsList();
                updateCourseUI();
            });
            if (!isStart && !isFinish) {
                var btnEdit = document.createElement('button');
                btnEdit.type = 'button';
                btnEdit.textContent = 'Edit label';
                btnEdit.style.marginRight = '6px';
                btnEdit.style.marginTop = '6px';
                var btnDel = document.createElement('button');
                btnDel.type = 'button';
                btnDel.textContent = 'Delete';
                btnDel.style.marginRight = '6px';
                btnWrap.appendChild(btnEdit);
                btnWrap.appendChild(btnDel);
                btnEdit.onclick = function () {
                    window.courseMappingMap.closePopup();
                    openSegmentPinFormTile(pinIndex, latlng, function () {
                        renderSegmentPins();
                        renderSegmentsList();
                        updateCourseUI();
                    });
                };
                btnDel.onclick = function () {
                    var isEndPin = pinIndex >= coords.length - 1;
                    var msg = isEndPin
                        ? 'Remove this segment boundary? The course will still end at the same location; only the segment split is removed.'
                        : 'Remove this segment boundary? This cannot be undone.';
                    if (!window.confirm(msg)) return;
                    window.courseMappingMap.closePopup();
                    currentCourse.segment_breaks = currentCourse.segment_breaks.filter(function (x) { return x !== pinIndex; });
                    if (currentCourse.segment_break_labels) delete currentCourse.segment_break_labels[pinIndex];
                    if (currentCourse.segment_break_descriptions) delete currentCourse.segment_break_descriptions[pinIndex];
                    if (currentCourse.segment_break_ids) delete currentCourse.segment_break_ids[pinIndex];
                    syncSegmentsFromBreaks();
                    renderCourseLine();
                    renderSegmentPins();
                    renderStartFinishIcons();
                    renderUturnIcons();
                    renderSegmentsList();
                    setDirty();
                    updateCourseUI();
                };
            }
            var btnExtend = document.createElement('button');
            btnExtend.type = 'button';
            btnExtend.textContent = 'Extend from here';
            btnExtend.title = 'Start drawing a new leg from this point.';
            btnWrap.appendChild(btnExtend);
            btnExtend.onclick = function () {
                window.courseMappingMap.closePopup();
                extendFromIndex = pinIndex;
                extendInsertEndIndex = pinIndex;
                startDrawMode();
                updateDrawButtons();
                updateExtendHint();
            };
            if (!isStart && !isFinish && pinIndex < coordsLen - 1) {
                var btnEndHere = document.createElement('button');
                btnEndHere.type = 'button';
                btnEndHere.textContent = 'End course here';
                btnEndHere.title = 'Remove all points after this pin and make this the finish. Use this to fix an extra out-and-back or tail.';
                btnEndHere.style.marginRight = '6px';
                btnWrap.appendChild(btnEndHere);
                btnEndHere.onclick = function () {
                    window.courseMappingMap.closePopup();
                    if (!window.confirm('End the course at this pin? All points after this will be removed. This cannot be undone.')) return;
                    var coords = currentCourse.geometry.coordinates;
                    var newLen = pinIndex + 1;
                    currentCourse.geometry.coordinates = coords.slice(0, newLen);
                    currentCourse.segment_breaks = (currentCourse.segment_breaks || []).filter(function (idx) { return idx <= pinIndex; });
                    var labels = currentCourse.segment_break_labels;
                    var descs = currentCourse.segment_break_descriptions;
                    var ids = currentCourse.segment_break_ids;
                    if (labels) { Object.keys(labels).forEach(function (k) { if (parseInt(k, 10) > pinIndex) delete labels[k]; }); }
                    if (descs) { Object.keys(descs).forEach(function (k) { if (parseInt(k, 10) > pinIndex) delete descs[k]; }); }
                    if (ids) { Object.keys(ids).forEach(function (k) { if (parseInt(k, 10) > pinIndex) delete ids[k]; }); }
                    if (Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = currentCourse.turnaround_indices.filter(function (i) { return i <= pinIndex; });
                    extendFromIndex = null;
                    extendInsertEndIndex = null;
                    syncSegmentsFromBreaks();
                    renderCourseLine();
                    renderSegmentPins();
                    renderStartFinishIcons();
                    renderUturnIcons();
                    renderSegmentsList();
                    setDirty();
                    updateCourseUI();
                    updateDrawButtons();
                    updateExtendHint();
                };
            }
            content.appendChild(btnWrap);
        }
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
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

    function openCoordinateEditTile(coordIndex, latlng, title, descValue, onDescSave, onSave) {
        var content = document.createElement('div');
        content.className = 'course-map-popup-form';
        content.innerHTML = '<strong>' + escapeHtml(title || 'Edit position') + '</strong><br/>';
        var lblLat = document.createElement('label');
        lblLat.textContent = 'Latitude';
        content.appendChild(lblLat);
        var inputLat = document.createElement('input');
        inputLat.type = 'text';
        inputLat.value = String(latlng.lat);
        inputLat.style.display = 'block';
        inputLat.style.width = '100%';
        inputLat.style.boxSizing = 'border-box';
        content.appendChild(inputLat);
        var lblLon = document.createElement('label');
        lblLon.textContent = 'Longitude';
        content.appendChild(lblLon);
        var inputLon = document.createElement('input');
        inputLon.type = 'text';
        inputLon.value = String(latlng.lng);
        inputLon.style.display = 'block';
        inputLon.style.width = '100%';
        inputLon.style.boxSizing = 'border-box';
        content.appendChild(inputLon);
        var inputDesc = null;
        if (descValue !== undefined) {
            var lblDesc = document.createElement('label');
            lblDesc.textContent = 'Description (optional)';
            content.appendChild(lblDesc);
            inputDesc = document.createElement('textarea');
            inputDesc.rows = 2;
            inputDesc.placeholder = 'Optional description';
            inputDesc.value = descValue || '';
            inputDesc.style.display = 'block';
            inputDesc.style.width = '100%';
            inputDesc.style.boxSizing = 'border-box';
            content.appendChild(inputDesc);
        }
        var btnSave = document.createElement('button');
        btnSave.type = 'button';
        btnSave.textContent = 'Save';
        var btnCancel = document.createElement('button');
        btnCancel.type = 'button';
        btnCancel.textContent = 'Cancel';
        content.appendChild(btnSave);
        content.appendChild(btnCancel);
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            var newLat = parseFloat(inputLat.value);
            var newLon = parseFloat(inputLon.value);
            if (isNaN(newLat) || isNaN(newLon)) {
                alert('Enter valid latitude and longitude.');
                return;
            }
            var coords = currentCourse.geometry.coordinates;
            if (coordIndex >= 0 && coordIndex < coords.length) {
                coords[coordIndex] = [newLon, newLat];
            }
            if (inputDesc && onDescSave) onDescSave((inputDesc.value || '').trim());
            window.courseMappingMap.closePopup();
            setDirty();
            syncSegmentsFromBreaks();
            renderCourseLine();
            renderSegmentPins();
            renderStartFinishIcons();
            renderUturnIcons();
            renderSegmentsList();
            renderLocationPins();
            updateCourseUI();
            if (onSave) onSave();
        };
        btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
    }

    function addEditLatLonButton(btnWrap, coordIndex, latlng, title, descValue, onDescSave, onAfterSave) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = 'Edit lat/lon';
        btn.title = 'Edit latitude and longitude for this point';
        btn.onclick = function () {
            window.courseMappingMap.closePopup();
            openCoordinateEditTile(coordIndex, latlng, title, descValue, onDescSave, onAfterSave);
        };
        btnWrap.appendChild(btn);
    }

    function openLocationLatLonEdit(locEl, latlng, onSave) {
        var content = document.createElement('div');
        content.className = 'course-map-popup-form';
        content.innerHTML = '<strong>' + escapeHtml(locEl.loc_label || 'Location') + '</strong><br/>';
        var lblLat = document.createElement('label');
        lblLat.textContent = 'Latitude';
        content.appendChild(lblLat);
        var inputLat = document.createElement('input');
        inputLat.type = 'text';
        inputLat.value = String(typeof locEl.lat === 'number' ? locEl.lat : parseFloat(locEl.lat));
        inputLat.style.display = 'block';
        inputLat.style.width = '100%';
        inputLat.style.boxSizing = 'border-box';
        content.appendChild(inputLat);
        var lblLon = document.createElement('label');
        lblLon.textContent = 'Longitude';
        content.appendChild(lblLon);
        var inputLon = document.createElement('input');
        inputLon.type = 'text';
        inputLon.value = String(typeof locEl.lon === 'number' ? locEl.lon : parseFloat(locEl.lon));
        inputLon.style.display = 'block';
        inputLon.style.width = '100%';
        inputLon.style.boxSizing = 'border-box';
        content.appendChild(inputLon);
        var btnSave = document.createElement('button');
        btnSave.type = 'button';
        btnSave.textContent = 'Save';
        var btnCancel = document.createElement('button');
        btnCancel.type = 'button';
        btnCancel.textContent = 'Cancel';
        content.appendChild(btnSave);
        content.appendChild(btnCancel);
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            var newLat = parseFloat(inputLat.value);
            var newLon = parseFloat(inputLon.value);
            if (isNaN(newLat) || isNaN(newLon)) {
                alert('Enter valid latitude and longitude.');
                return;
            }
            locEl.lat = newLat;
            locEl.lon = newLon;
            window.courseMappingMap.closePopup();
            setDirty();
            if (onSave) onSave();
        };
        btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
    }

    function openSegmentPinFormTile(idx, latlng, onSave) {
        var label = getSegmentBreakLabel(idx);
        var desc = getSegmentBreakDescription(idx);
        var content = document.createElement('div');
        content.className = 'course-map-popup-form';
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
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
            if (!currentCourse.segment_break_descriptions) currentCourse.segment_break_descriptions = {};
            currentCourse.segment_break_labels[idx] = (inputLabel.value && inputLabel.value.trim()) ? inputLabel.value.trim() : '';
            currentCourse.segment_break_descriptions[idx] = (inputDesc.value && inputDesc.value.trim()) ? inputDesc.value.trim() : '';
            syncSegmentsFromBreaks();
            renderSegmentsList();
            window.courseMappingMap.closePopup();
            setDirty();
            if (onSave) onSave();
        };
        btnCancel.onclick = function () { window.courseMappingMap.closePopup(); };
    }

    function openPointEditTile(pointType, index, latlng, onSave, optSecondIndex) {
        var lat = latlng.lat, lon = latlng.lng;
        var desc = '';
        if (pointType === 'start') desc = (currentCourse.start_description || '').trim();
        else if (pointType === 'finish') desc = (currentCourse.end_description || '').trim();
        else if (pointType === 'uturn' && currentCourse.turnaround_descriptions) desc = (currentCourse.turnaround_descriptions[index] || currentCourse.turnaround_descriptions['' + index] || '').trim();
        var label = pointType === 'start' ? (optSecondIndex != null ? 'Start/Finish' : 'Start') : (pointType === 'finish' ? 'Finish' : 'U-turn');
        var content = document.createElement('div');
        content.style.minWidth = '240px';
        content.innerHTML = '<strong>' + label + '</strong><br/>';
        var lblLat = document.createElement('label');
        lblLat.textContent = 'Latitude';
        content.appendChild(lblLat);
        var inputLat = document.createElement('input');
        inputLat.type = 'text';
        inputLat.value = String(lat);
        inputLat.style.display = 'block';
        inputLat.style.width = '100%';
        inputLat.style.marginBottom = '8px';
        inputLat.style.boxSizing = 'border-box';
        content.appendChild(inputLat);
        var lblLon = document.createElement('label');
        lblLon.textContent = 'Longitude';
        content.appendChild(lblLon);
        var inputLon = document.createElement('input');
        inputLon.type = 'text';
        inputLon.value = String(lon);
        inputLon.style.display = 'block';
        inputLon.style.width = '100%';
        inputLon.style.marginBottom = '8px';
        inputLon.style.boxSizing = 'border-box';
        content.appendChild(inputLon);
        var lblDesc = document.createElement('label');
        lblDesc.textContent = 'Description (optional)';
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
        if (pointType === 'uturn') {
            var btnRemoveUturn = document.createElement('button');
            btnRemoveUturn.type = 'button';
            btnRemoveUturn.textContent = 'Remove this U-turn';
            btnRemoveUturn.style.marginLeft = '6px';
            btnRemoveUturn.title = 'Remove the U-turn marker (course geometry is unchanged)';
            content.appendChild(btnRemoveUturn);
            btnRemoveUturn.onclick = function () {
                if (!currentCourse.turnaround_indices) return;
                currentCourse.turnaround_indices = currentCourse.turnaround_indices.filter(function (i) { return i !== index; });
                if (currentCourse.turnaround_descriptions) {
                    delete currentCourse.turnaround_descriptions[index];
                    delete currentCourse.turnaround_descriptions['' + index];
                }
                window.courseMappingMap.closePopup();
                setDirty();
                syncSegmentsFromBreaks();
                renderCourseLine();
                renderSegmentPins();
                renderStartFinishIcons();
                renderUturnIcons();
                renderSegmentsList();
                updateCourseUI();
                if (onSave) onSave();
            };
        }
        content.className = 'course-map-popup-form';
        var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(latlng).openOn(window.courseMappingMap);
        btnSave.onclick = function () {
            var newLat = parseFloat(inputLat.value);
            var newLon = parseFloat(inputLon.value);
            if (isNaN(newLat) || isNaN(newLon)) {
                alert('Enter valid latitude and longitude.');
                return;
            }
            var coords = currentCourse.geometry.coordinates;
            if (pointType === 'start') {
                coords[0] = [newLon, newLat];
                if (optSecondIndex != null && optSecondIndex < coords.length) coords[optSecondIndex] = [newLon, newLat];
                currentCourse.start_description = (inputDesc.value || '').trim();
            } else if (pointType === 'finish') {
                coords[coords.length - 1] = [newLon, newLat];
                currentCourse.end_description = (inputDesc.value || '').trim();
            } else if (pointType === 'uturn') {
                if (index >= 0 && index < coords.length) {
                    coords[index] = [newLon, newLat];
                    if (!currentCourse.turnaround_descriptions) currentCourse.turnaround_descriptions = {};
                    currentCourse.turnaround_descriptions[index] = (inputDesc.value || '').trim();
                }
            }
            window.courseMappingMap.closePopup();
            setDirty();
            syncSegmentsFromBreaks();
            renderCourseLine();
            renderSegmentPins();
            renderStartFinishIcons();
            renderUturnIcons();
            renderSegmentsList();
            updateCourseUI();
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
                className: 'segment-pin-circle',
                html: '<div style="width:12px;height:12px;background:#fff;border:2px solid ' + ROUTE_COLOR + ';border-radius:50%;"></div>',
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
                    addEditLatLonButton(btnWrap, i, e.latlng, label, desc, function (d) {
                        if (!currentCourse.segment_break_descriptions) currentCourse.segment_break_descriptions = {};
                        currentCourse.segment_break_descriptions[i] = d;
                    }, function () {
                        renderSegmentPins();
                        renderSegmentsList();
                        updateCourseUI();
                    });
                    var btnEdit = document.createElement('button');
                    btnEdit.type = 'button';
                    btnEdit.textContent = 'Edit label';
                    btnEdit.style.marginRight = '6px';
                    btnEdit.style.marginTop = '6px';
                    var btnDel = document.createElement('button');
                    btnDel.type = 'button';
                    btnDel.textContent = 'Delete';
                    btnDel.style.marginRight = '6px';
                    var btnExtend = document.createElement('button');
                    btnExtend.type = 'button';
                    btnExtend.textContent = 'Extend from here';
                    btnExtend.title = 'Start drawing a new leg from this point (e.g. full-only out-and-back). Click Draw Line, then add points; use Same Route Back for a U-turn.';
                    var btnFlow = document.createElement('button');
                    btnFlow.type = 'button';
                    btnFlow.textContent = 'Flow control';
                    btnFlow.title = 'Define which event(s) take which leg from this point (e.g. Full/10K left, Half right).';
                    btnWrap.appendChild(btnEdit);
                    btnWrap.appendChild(btnDel);
                    btnWrap.appendChild(btnExtend);
                    btnWrap.appendChild(btnFlow);
                    content.appendChild(btnWrap);
                    btnFlow.onclick = function () {
                        window.courseMappingMap.closePopup();
                        openFlowControlForPin(i, e.latlng);
                    };
                    btnEdit.onclick = function () {
                        window.courseMappingMap.closePopup();
                        openSegmentPinFormTile(i, e.latlng, function () {
                            renderSegmentPins();
                            renderSegmentsList();
                            updateCourseUI();
                        });
                    };
                    btnDel.onclick = function () {
                        var isEndPin = i >= coords.length - 1;
                        var msg = isEndPin
                            ? 'Remove this segment boundary? The course will still end at the same location; only the segment split is removed.'
                            : 'Remove this segment boundary? This cannot be undone.';
                        if (!window.confirm(msg)) return;
                        window.courseMappingMap.closePopup();
                        currentCourse.segment_breaks = currentCourse.segment_breaks.filter(function (x) { return x !== i; });
                        if (currentCourse.segment_break_labels) delete currentCourse.segment_break_labels[i];
                        if (currentCourse.segment_break_descriptions) delete currentCourse.segment_break_descriptions[i];
                        if (currentCourse.segment_break_ids) delete currentCourse.segment_break_ids[i];
                        syncSegmentsFromBreaks();
                        renderCourseLine();
                        renderSegmentPins();
                        renderStartFinishIcons();
                        renderUturnIcons();
                        renderSegmentsList();
                        setDirty();
                        updateCourseUI();
                    };
                    btnExtend.onclick = function () {
                        window.courseMappingMap.closePopup();
                        extendFromIndex = i;
                        extendInsertEndIndex = i;
                        startDrawMode();
                        updateDrawButtons();
                        updateExtendHint();
                    };
                    if (i > 0 && i < coords.length - 1) {
                        var btnEndHere = document.createElement('button');
                        btnEndHere.type = 'button';
                        btnEndHere.textContent = 'End course here';
                        btnEndHere.title = 'Remove all points after this pin and make this the finish.';
                        btnEndHere.style.marginRight = '6px';
                        btnWrap.appendChild(btnEndHere);
                        btnEndHere.onclick = function () {
                            window.courseMappingMap.closePopup();
                            if (!window.confirm('End the course at this pin? All points after this will be removed. This cannot be undone.')) return;
                            var coords = currentCourse.geometry.coordinates;
                            var pinIdx = i;
                            var newLen = pinIdx + 1;
                            currentCourse.geometry.coordinates = coords.slice(0, newLen);
                            currentCourse.segment_breaks = (currentCourse.segment_breaks || []).filter(function (idx) { return idx <= pinIdx; });
                            var labels = currentCourse.segment_break_labels;
                            var descs = currentCourse.segment_break_descriptions;
                            var ids = currentCourse.segment_break_ids;
                            if (labels) { Object.keys(labels).forEach(function (k) { if (parseInt(k, 10) > pinIdx) delete labels[k]; }); }
                            if (descs) { Object.keys(descs).forEach(function (k) { if (parseInt(k, 10) > pinIdx) delete descs[k]; }); }
                            if (ids) { Object.keys(ids).forEach(function (k) { if (parseInt(k, 10) > pinIdx) delete ids[k]; }); }
                            if (Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = currentCourse.turnaround_indices.filter(function (idx) { return idx <= pinIdx; });
                            extendFromIndex = null;
                            extendInsertEndIndex = null;
                            syncSegmentsFromBreaks();
                            renderCourseLine();
                            renderSegmentPins();
                            renderStartFinishIcons();
                            renderUturnIcons();
                            renderSegmentsList();
                            setDirty();
                            updateCourseUI();
                            updateDrawButtons();
                            updateExtendHint();
                        };
                    }
                }
                var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
            });
            segmentPinsLayer.addLayer(m);
        });
        segmentPinsLayer.addTo(window.courseMappingMap);
    }

    /**
     * Compute per-event cumulative from_km/to_km for each segment (same logic as backend).
     * Returns array of dicts: result[i][eid] = { from_km, to_km }. Used when segment has no stored per-event keys.
     */
    function computeEventDistancesForSegments(segments, eventIds) {
        var result = [];
        for (var i = 0; i < segments.length; i++) result.push({});
        function segEventsSet(seg) {
            var ev = seg.events;
            if (!ev || !Array.isArray(ev)) return {};
            return ev.reduce(function (acc, e) { acc[String(e).toLowerCase()] = true; return acc; }, {});
        }
        for (var ei = 0; ei < eventIds.length; ei++) {
            var eid = eventIds[ei];
            var accumulated = 0;
            for (var i = 0; i < segments.length; i++) {
                var seg = segments[i];
                var from_km = Number(seg.from_km) || 0;
                var to_km = Number(seg.to_km) || 0;
                var segLen = Math.round((to_km - from_km) * 100) / 100;
                var onSegment = segEventsSet(seg)[eid];
                if (!onSegment) {
                    result[i][eid] = { from_km: 0, to_km: 0 };
                } else {
                    var fromAcc = Math.round(accumulated * 100) / 100;
                    var toAcc = Math.round((accumulated + segLen) * 100) / 100;
                    result[i][eid] = { from_km: fromAcc, to_km: toAcc };
                    accumulated = toAcc;
                }
            }
        }
        return result;
    }

    function formatKm(val) {
        if (val == null || isNaN(val)) return '0';
        return Number(val).toFixed(2);
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
        var eventIds = (EVENT_CHOICES || []).map(function (e) { return String(e.value != null ? e.value : e).toLowerCase(); });
        var computedEventDistances = computeEventDistancesForSegments(currentCourse.segments, eventIds);
        currentCourse.segments.forEach(function (seg, segIdx) {
            var len = (seg.to_km - seg.from_km);
            var startIdx = seg.start_index != null ? seg.start_index : 0;
            var endIdx = seg.end_index != null ? seg.end_index : (coordsLen ? coordsLen - 1 : 0);
            var segId = (seg.seg_id != null && seg.seg_id !== '') ? String(seg.seg_id) : String(segIdx + 1);
            var pinStart = (seg.from_label && String(seg.from_label).trim())
                ? String(seg.from_label).trim()
                : getPinLabelForIndex(startIdx, coordsLen);
            var pinEnd = (seg.to_label && String(seg.to_label).trim())
                ? String(seg.to_label).trim()
                : getPinLabelForIndex(endIdx, coordsLen);
            var useLegLabels = !!(seg.from_label || seg.to_label);
            var displayLabel = (seg.seg_label && seg.seg_label.trim()) ? seg.seg_label : (pinEnd || '');
            var tr = document.createElement('tr');
            var fromCell = document.createElement('td');
            var toCell = document.createElement('td');
            var fromBtn = document.createElement('button');
            fromBtn.type = 'button';
            fromBtn.className = 'pin-link';
            fromBtn.textContent = pinStart || '—';
            fromBtn.title = 'Show pin on map: ' + (pinStart || 'From');
            if (useLegLabels) {
                fromCell.textContent = pinStart || '—';
            } else {
                fromBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    openSegmentPinPopupForIndex(startIdx);
                });
                fromCell.appendChild(fromBtn);
            }
            var toBtn = document.createElement('button');
            toBtn.type = 'button';
            toBtn.className = 'pin-link';
            toBtn.textContent = pinEnd || '—';
            toBtn.title = 'Show pin on map: ' + (pinEnd || 'To');
            if (useLegLabels) {
                toCell.textContent = pinEnd || '—';
            } else {
                toBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    openSegmentPinPopupForIndex(endIdx);
                });
                toCell.appendChild(toBtn);
            }
            var segIdCell = document.createElement('td');
            var segIdBtn = document.createElement('button');
            segIdBtn.type = 'button';
            segIdBtn.className = 'pin-link';
            segIdBtn.textContent = segId;
            segIdBtn.title = 'Edit segment: label, width, schema, direction, description, events';
            segIdBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                openSegmentEditInTile(segIdx);
            });
            segIdCell.appendChild(segIdBtn);
            tr.appendChild(segIdCell);
            tr.appendChild(fromCell);
            tr.appendChild(toCell);
            tr.appendChild(document.createElement('td')).textContent = displayLabel || '';
            var eventsCell = document.createElement('td');
            eventsCell.textContent = eventsToDisplayList(seg.events);
            tr.appendChild(eventsCell);
            eventIds.forEach(function (eid) {
                var fromVal = seg[eid + '_from_km'];
                var toVal = seg[eid + '_to_km'];
                if (fromVal == null || toVal == null) {
                    var comp = computedEventDistances[segIdx] && computedEventDistances[segIdx][eid];
                    fromVal = comp ? comp.from_km : 0;
                    toVal = comp ? comp.to_km : 0;
                } else {
                    fromVal = Number(fromVal);
                    toVal = Number(toVal);
                }
                var cell = document.createElement('td');
                cell.textContent = (fromVal === 0 && toVal === 0) ? '0' : (formatKm(fromVal) + '–' + formatKm(toVal));
                tr.appendChild(cell);
            });
            tr.appendChild(document.createElement('td')).textContent = Math.round(len * 100) / 100;
            tr.style.cursor = 'pointer';
            tr.title = 'Click row to zoom map to this segment';
            tr.addEventListener('click', function () {
                if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates) return;
                var coords = currentCourse.geometry.coordinates;
                var lo = Math.min(startIdx, endIdx);
                var hi = Math.max(startIdx, endIdx);
                if (lo <= hi && coords.length) {
                    var latlngs = [];
                    for (var i = lo; i <= hi; i++) latlngs.push(L.latLng(coords[i][1], coords[i][0]));
                    var bounds = L.latLngBounds(latlngs);
                    if (window.courseMappingMap) {
                        window.courseMappingMap.closePopup();
                        window.courseMappingMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 18, duration: 0.3 });
                    }
                }
            });
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
                { label: 'Type', value: getLocationTypeLabel(loc.loc_type) }
            ]) + (isEditMode ? '<div class="popup-row" style="font-size:0.75rem;color:#7f8c8d;">(drag to move; edit details in Locations table)</div>' : '');
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
            var notesPreview = truncateNotesPreview(locEl.notes, 120);
                var content = document.createElement('div');
                content.innerHTML = buildPopupRowsHtml([
                    { label: 'ID', value: locId },
                    { label: 'Label', value: name },
                    { label: 'Type', value: typeLabel },
                    { label: 'Notes', value: notesPreview }
                ]);
                content.classList.add('course-map-popup-wrap');
                var hint = document.createElement('p');
                hint.style.cssText = 'font-size:0.8rem;color:#7f8c8d;margin:0.5rem 0 0 0;';
                hint.textContent = 'Edit full details in the Locations table (click ID).';
                content.appendChild(hint);
                var btnWrap = document.createElement('div');
                btnWrap.style.marginTop = '0.5rem';
                var btnTable = document.createElement('button');
                btnTable.type = 'button';
                btnTable.textContent = 'Open in table';
                btnTable.onclick = function () {
                    window.courseMappingMap.closePopup();
                    openLocationEditorModal(idx, !isEditMode);
                };
                btnWrap.appendChild(btnTable);
                if (isEditMode) {
                    var btnDel = document.createElement('button');
                    btnDel.type = 'button';
                    btnDel.textContent = 'Delete';
                    btnDel.style.marginLeft = '6px';
                    btnDel.onclick = function () {
                        if (!window.confirm('Remove this location? This cannot be undone.')) return;
                        window.courseMappingMap.closePopup();
                        currentCourse.locations.splice(idx, 1);
                        renderLocationPins();
                        renderLocationsList();
                        setDirty();
                        updateCourseUI();
                    };
                    btnWrap.appendChild(btnDel);
                }
                content.appendChild(btnWrap);
                highlightLocationRow(idx);
                var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
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
        renderLocationsTableHeader();
        tbody.innerHTML = '';
        var resourceTotals = {};
        getPackageResources().forEach(function (res) { resourceTotals[res.code] = 0; });
        currentCourse.locations.forEach(function (loc, i) {
            syncLocationResourceCounts(loc);
            var tr = document.createElement('tr');
            var typeLabel = getLocationTypeLabel(loc.loc_type);
            var locId = loc.id != null ? String(loc.id) : String(i + 1);
            var idCell = document.createElement('td');
            var idBtn = document.createElement('button');
            idBtn.type = 'button';
            idBtn.className = 'loc-id-link';
            idBtn.textContent = locId;
            idBtn.title = isEditMode ? 'Edit location details' : 'View location details';
            idBtn.addEventListener('click', function () {
                openLocationEditorModal(i, !isEditMode);
            });
            idCell.appendChild(idBtn);
            tr.appendChild(idCell);
            tr.appendChild(document.createElement('td')).textContent = typeLabel;
            tr.appendChild(document.createElement('td')).textContent = loc.loc_label || '';
            getPackageResources().forEach(function (res) {
                var code = res.code;
                var count = (loc.resources && loc.resources[code] != null)
                    ? loc.resources[code]
                    : (loc[code + '_count'] || 0);
                var n = parseInt(count, 10);
                if (isNaN(n)) n = 0;
                resourceTotals[code] += n;
                tr.appendChild(document.createElement('td')).textContent = String(n);
            });
            if (isEditMode) {
                var actionCell = document.createElement('td');
                actionCell.style.whiteSpace = 'nowrap';
                var removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'btn-remove-loc';
                removeBtn.setAttribute('data-index', String(i));
                removeBtn.textContent = 'Remove';
                actionCell.appendChild(removeBtn);
                tr.appendChild(actionCell);
            }
            tbody.appendChild(tr);
        });
        var totalTr = document.createElement('tr');
        totalTr.className = 'locations-totals-row';
        totalTr.appendChild(document.createElement('td')).textContent = 'Total';
        totalTr.appendChild(document.createElement('td')).textContent = '';
        totalTr.appendChild(document.createElement('td')).textContent = '';
        getPackageResources().forEach(function (res) {
            totalTr.appendChild(document.createElement('td')).textContent =
                String(resourceTotals[res.code] || 0);
        });
        if (isEditMode) {
            totalTr.appendChild(document.createElement('td'));
        }
        tbody.appendChild(totalTr);
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

    /** Closest vertex to latLng within coordinate indices [startIdx, endIdx] (inclusive). Used when adding a pin restricted to one segment. */
    function closestVertexIndexInRange(latLng, coordinates, startIdx, endIdx) {
        var minD = 1e9, best = startIdx;
        var lat = latLng.lat, lon = latLng.lng;
        var lo = Math.max(0, Math.min(startIdx, endIdx));
        var hi = Math.min(coordinates.length - 1, Math.max(startIdx, endIdx));
        for (var i = lo; i <= hi; i++) {
            var c = coordinates[i];
            var d = (c[1] - lat) * (c[1] - lat) + (c[0] - lon) * (c[0] - lon);
            if (d < minD) { minD = d; best = i; }
        }
        return best;
    }

    /** For Same Route Back: prefer segment-break (pin) vertex when click is near one, so rejoin point snaps to pins. */
    function rejoinVertexIndex(latLng, coordinates) {
        var idx = closestVertexIndex(latLng, coordinates);
        var breaks = (currentCourse && currentCourse.segment_breaks) ? currentCourse.segment_breaks : [];
        if (breaks.length === 0) return idx;
        var lat = latLng.lat, lon = latLng.lng;
        var dBest = 1e9;
        var coordAt = function (i) {
            var c = coordinates[i];
            return (c[1] - lat) * (c[1] - lat) + (c[0] - lon) * (c[0] - lon);
        };
        var dIdx = coordAt(idx);
        for (var b = 0; b < breaks.length; b++) {
            var bi = breaks[b];
            if (bi < 0 || bi >= coordinates.length) continue;
            var db = coordAt(bi);
            if (db <= dIdx * 1.5 && db < dBest) { dBest = db; idx = bi; }
        }
        return idx;
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
                    var dirty = usePackageLevelEditSave() ? isConfigPackageDirty() : isDirty();
                    if (dirty && !window.confirm('Discard unsaved changes?')) return;
                    if (usePackageLevelEditSave()) {
                        cancelConfigPackageEdit();
                    } else {
                        clearDirty();
                        setEditMode(false);
                        syncCourseToHeaderInputs();
                    }
                } else {
                    setEditMode(true);
                }
            });
        }

        ['course-map-name', 'course-map-name-standalone'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('input', function () { if (currentCourse) setDirty(); });
        });
        ['course-map-description', 'course-map-description-standalone'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', function () {
                    if (currentCourse) setDirty();
                    resizeDescriptionTextarea();
                });
            }
        });

        if (btnSave) {
            btnSave.addEventListener('click', async function () {
                if (!currentCourse) return;
                var nameEl = activeNameInputEl();
                var descEl = activeDescriptionInputEl();
                var n = nameEl ? String(nameEl.value || '').trim().slice(0, 255) : '';
                var d = descEl ? String(descEl.value || '').trim().slice(0, 255) : '';
                currentCourse.name = n;
                currentCourse.description = d;
                try {
                    if (usePackageLevelEditSave()) {
                        await saveConfigPackageWorkspaceWithManifest();
                        setEditMode(false);
                        console.log('Saved config package:', resolveConfigPackageId());
                        return;
                    }
                    var courseIdToSave = currentCourseId;
                    if (isConfigPackageMode()) {
                        courseIdToSave = resolveConfigPackageId();
                        currentCourse.id = courseIdToSave;
                        currentCourse.config_id = courseIdToSave;
                        await saveConfigPackageWorkspace({ label: n, description: d });
                        setEditMode(false);
                        console.log('Saved config package course:', courseIdToSave);
                        return;
                    }
                    if (!courseIdToSave) {
                        var createRes = await fetch('/api/courses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
                        var createData = await createRes.json();
                        if (!createRes.ok) throw new Error(createData.detail || createRes.statusText);
                        if (!createData.ok || !createData.id) throw new Error('Failed to create course');
                        courseIdToSave = createData.id;
                        currentCourse.id = courseIdToSave;
                    }
                    var toSave = JSON.parse(JSON.stringify(buildCourseSavePayload(courseIdToSave)));
                    const res = await fetch('/api/courses/' + encodeURIComponent(courseIdToSave), {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
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
                var fromPoint = (extendFromIndex != null && extendInsertEndIndex != null) ? coords[extendInsertEndIndex] : coords[coords.length - 1];
                if (snapEl && snapEl.classList && snapEl.classList.contains('active') && fromPoint) {
                    drawRoutingInProgress = true;
                    fetchRouteSegment(fromPoint, toPoint, function (err, routeCoords) {
                        drawRoutingInProgress = false;
                        var newPoints = (!err && routeCoords && routeCoords.length > 1) ? routeCoords.slice(1) : [toPoint];
                        lastAddedPointCount = newPoints.length;
                        if (extendFromIndex != null && extendInsertEndIndex != null) {
                            var insertAt = extendInsertEndIndex + 1;
                            for (var ni = 0; ni < newPoints.length; ni++) coords.splice(insertAt + ni, 0, newPoints[ni].slice());
                            shiftIndicesAfter(currentCourse.segment_breaks, extendFromIndex, newPoints.length);
                            shiftSegmentBreakMetadata(extendFromIndex, newPoints.length);
                            shiftIndicesAfter(currentCourse.turnaround_indices, extendFromIndex, newPoints.length);
                            extendInsertEndIndex += newPoints.length;
                        } else {
                            for (var i = 0; i < newPoints.length; i++) coords.push(newPoints[i]);
                        }
                        syncSegmentsFromBreaks();
                        renderCourseLine();
                        renderSegmentPins();
                        renderStartFinishIcons();
                        renderUturnIcons();
                        setDirty();
                        updateDrawButtons();
                        updateUndoButton();
                        updateExtendHint();
                    });
                } else {
                    lastAddedPointCount = 1;
                    if (extendFromIndex != null && extendInsertEndIndex != null) {
                        coords.splice(extendInsertEndIndex + 1, 0, toPoint.slice());
                        shiftIndicesAfter(currentCourse.segment_breaks, extendFromIndex, 1);
                        shiftSegmentBreakMetadata(extendFromIndex, 1);
                        shiftIndicesAfter(currentCourse.turnaround_indices, extendFromIndex, 1);
                        extendInsertEndIndex += 1;
                    } else {
                        coords.push(toPoint);
                    }
                    syncSegmentsFromBreaks();
                    renderCourseLine();
                    renderSegmentPins();
                    renderStartFinishIcons();
                    renderUturnIcons();
                    setDirty();
                    updateDrawButtons();
                    updateUndoButton();
                    updateExtendHint();
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

        function stopExtendMode() {
            extendFromIndex = null;
            extendInsertEndIndex = null;
            stopDrawMode();
            updateExtendHint();
            updateDrawButtons();
            renderCourseLine();
            renderSegmentPins();
            renderStartFinishIcons();
            renderUturnIcons();
        }

        var turnaroundMarkerIndex = 0;
        var turnaroundMarker = null;
        var sameRouteBackClickHandler = null;

        function setTurnaroundFromClick(latlng) {
            if (!currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || !turnaroundMarker) return;
            var coords = currentCourse.geometry.coordinates;
            var idx = rejoinVertexIndex(latlng, coords);
            idx = Math.max(0, Math.min(idx, coords.length - 1));
            turnaroundMarkerIndex = idx;
            turnaroundMarker._turnaroundIndex = idx;
            var c = coords[idx];
            turnaroundMarker.setLatLng([c[1], c[0]]);
            var sel = document.getElementById('rejoin-at-pin');
            if (sel && sameRouteBackMode) sel.value = String(idx);
        }

        function startSameRouteBackMode() {
            if (sameRouteBackMode || !currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates) return;
            var coords = currentCourse.geometry.coordinates;
            if (coords.length < 3) return;
            stopSegmentPinMode();
            stopLocationPinMode();
            sameRouteBackMode = true;
            if (extendFromIndex != null && extendInsertEndIndex != null) {
                turnaroundMarkerIndex = extendFromIndex;
                var c = coords[extendFromIndex];
            } else {
                turnaroundMarkerIndex = Math.max(0, coords.length - 2);
                var c = coords[turnaroundMarkerIndex];
            }
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
            turnaroundMarker.bindTooltip('Rejoin point: return leg ends here. Same Route Back retraces to this point; or draw a different return by adding points and ending here, then Done extending.', { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
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
            if (extendFromIndex != null && extendInsertEndIndex != null) {
                turnaroundIdx = extendInsertEndIndex;
                var rejoinTarget = k;
                if (rejoinTarget < 0 || rejoinTarget > extendInsertEndIndex) rejoinTarget = extendFromIndex;
                for (var r = extendInsertEndIndex - 1; r >= rejoinTarget + 1; r--) returnSegment.push(coords[r].slice());
                returnSegment.push(coords[rejoinTarget].slice());
                for (var si = 0; si < returnSegment.length; si++) coords.splice(extendInsertEndIndex + 1 + si, 0, returnSegment[si]);
                shiftIndicesAfter(currentCourse.segment_breaks, extendInsertEndIndex, returnSegment.length);
                shiftSegmentBreakMetadata(extendInsertEndIndex, returnSegment.length);
                var rejoinIdx = extendInsertEndIndex + returnSegment.length;
                if (currentCourse.segment_breaks.indexOf(rejoinIdx) < 0) {
                    currentCourse.segment_breaks.push(rejoinIdx);
                    currentCourse.segment_breaks.sort(function (a, b) { return a - b; });
                    if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
                    currentCourse.segment_break_labels[rejoinIdx] = (currentCourse.segment_break_labels[rejoinTarget] || currentCourse.segment_break_labels['' + rejoinTarget] || '').trim() || 'Friel';
                    if (currentCourse.segment_break_ids) {
                        var nextId = 1;
                        Object.keys(currentCourse.segment_break_ids).forEach(function (key) { var n = parseInt(currentCourse.segment_break_ids[key], 10); if (!isNaN(n) && n >= nextId) nextId = n + 1; });
                        currentCourse.segment_break_ids[rejoinIdx] = nextId;
                    }
                }
                if (!Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = [];
                var ti = currentCourse.turnaround_indices;
                for (var j = 0; j < ti.length; j++) if (ti[j] > extendInsertEndIndex) ti[j] += returnSegment.length;
                ti.push(extendInsertEndIndex);
                ti.sort(function (a, b) { return a - b; });
                extendInsertEndIndex += returnSegment.length;
            } else {
                for (var i = turnaroundIdx - 1; i >= k; i--) returnSegment.push(coords[i].slice());
                coords.push.apply(coords, returnSegment);
                if (!Array.isArray(currentCourse.turnaround_indices)) currentCourse.turnaround_indices = [];
                currentCourse.turnaround_indices.push(turnaroundIdx);
            }
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
            updateExtendHint();
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
                var labelText = getSegmentBreakLabel(idx) || (currentCourse.turnaround_descriptions && (currentCourse.turnaround_descriptions[idx] || currentCourse.turnaround_descriptions['' + idx])) || 'U-turn';
                var labelEscaped = (labelText || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                var icon = L.divIcon({
                    className: 'uturn-icon',
                    html: '<div style="display:flex;flex-direction:column;align-items:center;gap:0;">' +
                        '<div style="width:24px;height:24px;background:#3498db;color:#fff;border:2px solid #2980b9;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:bold;">↺</div>' +
                        '<span style="font-size:10px;font-weight:600;color:#2980b9;white-space:nowrap;max-width:80px;overflow:hidden;text-overflow:ellipsis;text-shadow:0 0 2px #fff,0 0 2px #fff;">' + labelEscaped + '</span></div>',
                    iconSize: [24, 36],
                    iconAnchor: [12, 12]
                });
                var m = L.marker([c[1], c[0]], { icon: icon, draggable: isEditMode });
                m._turnaroundIndex = idx;
                var tip = 'U-turn (Same Route Back)';
                if (isEditMode) tip += ' — drag to move or click to edit';
                m.bindTooltip(tip, { permanent: false, direction: 'top', offset: [0, -10], className: 'course-map-tooltip' });
                if (isEditMode) {
                    m.on('dragend', function () {
                        var ll = m.getLatLng();
                        currentCourse.geometry.coordinates[m._turnaroundIndex] = [ll.lng, ll.lat];
                        syncSegmentsFromBreaks();
                        renderCourseLine();
                        renderSegmentPins();
                        renderStartFinishIcons();
                        renderUturnIcons();
                        renderSegmentsList();
                        setDirty();
                        updateCourseUI();
                    });
                    m.on('click', function (e) {
                        L.DomEvent.stopPropagation(e);
                        openPointEditTile('uturn', m._turnaroundIndex, e.latlng, function () {});
                    });
                }
                uturnIconsLayer.addLayer(m);
            });
            uturnIconsLayer.addTo(window.courseMappingMap);
        }

        function startSegmentPinMode(segmentRange) {
            if (segmentPinMode || !currentCourse || !currentCourse.geometry || !currentCourse.geometry.coordinates || currentCourse.geometry.coordinates.length < 2) return;
            stopDrawMode();
            stopLocationPinMode();
            segmentPinMode = true;
            addPinSegmentRange = segmentRange && typeof segmentRange.startIdx === 'number' && typeof segmentRange.endIdx === 'number' ? { startIdx: segmentRange.startIdx, endIdx: segmentRange.endIdx } : null;
            updateSegmentPinButton();
            mapClickHandler = function (e) {
                var coords = currentCourse.geometry.coordinates;
                var idx;
                if (addPinSegmentRange) {
                    idx = closestVertexIndexInRange(e.latlng, coords, addPinSegmentRange.startIdx, addPinSegmentRange.endIdx);
                } else {
                    idx = closestVertexIndex(e.latlng, coords);
                }
                if (idx <= 0 || idx >= coords.length) return;
                if (!Array.isArray(currentCourse.segment_breaks)) currentCourse.segment_breaks = [];
                if (currentCourse.segment_breaks.indexOf(idx) >= 0) return;
                currentCourse.segment_breaks.push(idx);
                currentCourse.segment_breaks.sort(function (a, b) { return a - b; });
                if (!currentCourse.segment_break_labels) currentCourse.segment_break_labels = {};
                if (!currentCourse.segment_break_descriptions) currentCourse.segment_break_descriptions = {};
                if (!currentCourse.segment_break_ids) currentCourse.segment_break_ids = {};
                currentCourse.segment_break_ids[idx] = nextSegmentPinId();
                setDirty();
                addPinSegmentRange = null;
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
            addPinSegmentRange = null;
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
                var pop = L.popup({ maxWidth: POPUP_MAX_WIDTH, className: 'location-popup' }).setContent(content).setLatLng(e.latlng).openOn(window.courseMappingMap);
                btnAdd.onclick = function () {
                    var locType = sel.value || 'course';
                    var locLabel = (input.value && input.value.trim()) ? input.value.trim() : '';
                    var newLoc = {
                        id: nextLocationId(),
                        loc_type: locType,
                        loc_label: locLabel,
                        notes: '',
                        lat: e.latlng.lat,
                        lon: e.latlng.lng,
                        resources: {}
                    };
                    getPackageResources().forEach(function (res) {
                        newLoc.resources[res.code] = 0;
                        newLoc[res.code + '_count'] = 0;
                    });
                    currentCourse.locations.push(newLoc);
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
        var rejoinAtPin = document.getElementById('rejoin-at-pin');
        if (rejoinAtPin) rejoinAtPin.addEventListener('change', function () {
            if (sameRouteBackMode) setRejoinIndexFromSelect(rejoinAtPin.value);
        });

        var btnSegmentPin = document.getElementById('btn-add-segment-pin');
        if (btnSegmentPin) {
            btnSegmentPin.addEventListener('click', function () {
                if (segmentPinMode) stopSegmentPinMode(); else startSegmentPinMode();
            });
        }
        var btnDoneExtending = document.getElementById('btn-done-extending');
        if (btnDoneExtending) {
            btnDoneExtending.addEventListener('click', function () {
                stopExtendMode();
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
            btnExport.addEventListener('click', async function () {
                if (!currentCourseId || !currentCourse) return;
                if (isConfigPackageMode()) {
                    if (!currentCourse.segments || currentCourse.segments.length === 0) {
                        alert('Add segment pins on the course line before exporting segments.csv.');
                        return;
                    }
                    if (isDirty()) {
                        alert('Save the course (Edit → Save) before exporting segments.csv.');
                        return;
                    }
                    try {
                        var url = '/api/config/packages/' + encodeURIComponent(resolveConfigPackageId()) + '/export/segments';
                        var res = await fetch(url, { method: 'POST', credentials: 'same-origin' });
                        var data = await res.json();
                        if (!res.ok) throw new Error(data.detail || res.statusText);
                        var msg = 'Exported to config package: segments.csv';
                        if (data.location_count != null) msg += ', locations.csv (' + data.location_count + ' rows)';
                        if (data.segments_backup_path) msg += ' (segments.csv backed up)';
                        if (data.locations_backup_path) msg += ' (locations.csv backed up)';
                        alert(msg);
                    } catch (e) {
                        alert('Export failed: ' + (e.message || String(e)));
                    }
                    return;
                }
                var url = '/api/courses/' + encodeURIComponent(currentCourseId) + '/export?to_folder=1';
                fetch(url).then(function (r) { return r.json(); }).then(function (data) {
                    if (data.ok) alert('All map files exported to map folder.');
                    else alert('Export failed');
                }).catch(function () { alert('Export failed'); });
            });
        }

        var btnManageRes = document.getElementById('btn-manage-resources');
        if (btnManageRes) btnManageRes.addEventListener('click', openResourcesEditorModal);
        var resClose = document.getElementById('resources-editor-close');
        var resCancel = document.getElementById('resources-editor-cancel');
        if (resClose) resClose.addEventListener('click', function () { hideModal(document.getElementById('resources-editor-modal')); });
        if (resCancel) resCancel.addEventListener('click', function () { hideModal(document.getElementById('resources-editor-modal')); });
        var resSave = document.getElementById('resources-editor-save');
        if (resSave) resSave.addEventListener('click', savePackageResources);
        var resAdd = document.getElementById('resources-add-row');
        attachResourceCodeInput(document.getElementById('resources-new-code'));
        if (resAdd) resAdd.addEventListener('click', function () {
            var codeInp = document.getElementById('resources-new-code');
            var labelInp = document.getElementById('resources-new-label');
            var code = normalizeResourceCodeInput(codeInp && codeInp.value);
            var label = (labelInp && labelInp.value || '').trim() || code.toUpperCase();
            if (!code || !/^[a-z]/.test(code)) {
                alert('Enter a resource code (lowercase letters, optional digits/underscore, max ' + RESOURCE_CODE_MAX_LEN + ').');
                return;
            }
            if (!resourcesEditorDraft) resourcesEditorDraft = getPackageResources().slice();
            if (resourcesEditorDraft.some(function (r) { return r.code === code; })) {
                alert('Resource code already exists.');
                return;
            }
            resourcesEditorDraft.push({ code: code, label: label });
            if (codeInp) codeInp.value = '';
            if (labelInp) labelInp.value = '';
            renderResourcesEditorList();
        });
        var locModalClose = document.getElementById('location-editor-close');
        if (locModalClose) locModalClose.addEventListener('click', function () {
            destroyLocationEditorMap();
            hideModal(document.getElementById('location-editor-modal'));
            locationEditorIndex = null;
        });
        document.querySelectorAll('.course-location-modal-backdrop').forEach(function (el) {
            el.addEventListener('click', function () {
                destroyLocationEditorMap();
                hideModal(el.closest('.course-location-modal'));
                locationEditorIndex = null;
            });
        });

        window.configPackageCourse = {
            enterEdit: function () {
                setEditMode(true);
                updateCourseUI();
            },
            exitEdit: function () {
                setEditMode(false);
                updateCourseUI();
            },
            isEditMode: function () { return isEditMode; },
            isDirty: isConfigPackageDirty,
            cancelEdit: cancelConfigPackageEdit,
            saveAll: saveConfigPackageWorkspace,
            syncHeaderFromMeta: syncCourseHeaderFromPackageMeta
        };

        document.addEventListener('segment-recipes-applied', function (ev) {
            if (!isConfigPackageMode() || !ev.detail || !ev.detail.course) return;
            currentCourse = ev.detail.course;
            updateCourseUI();
            renderSegmentsList();
        });

        if (isConfigPackageMode()) {
            applyConfigPackageUIMode();
            loadConfigPackageCourse();
            if (window.segmentRecipes && window.segmentRecipes.load) {
                window.segmentRecipes.load();
            }
        } else {
            setCourse(null, blankCourse());
            loadCourseList();
        }

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
