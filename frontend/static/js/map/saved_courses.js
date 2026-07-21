/**
 * Global org courses + package course assignment.
 */
(function () {
    'use strict';

    var orgCourses = [];
    var draftDistance = '10k';
    var draftOrderGrid = {};
    var selectedCourseId = null;
    var editingCourseId = null;
    var orgCoursePreviewMap = null;
    var orgCoursePreviewLine = null;
    var orgCoursePreviewLocationsLayer = null;

    var LOCATION_PIN_COLORS = {
        aid: '#e74c3c',
        course: '#27ae60',
        extract: '#9c27b0',
        official: '#f1c40f',
        traffic: '#95a5a6',
        water: '#3498db',
    };

    function configId() {
        if (window.CONFIG_PACKAGE_ID) return String(window.CONFIG_PACKAGE_ID).trim();
        var params = new URLSearchParams(window.location.search);
        return params.get('config_id') ? params.get('config_id').trim() : '';
    }

    function packageApiBase() {
        var cid = configId();
        return cid ? '/api/config/packages/' + encodeURIComponent(cid) : '';
    }

    function setHubStatus(msg, isError) {
        var el = document.getElementById('saved-courses-status');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.textContent = msg;
        el.style.color = isError ? '#c0392b' : '#7f8c8d';
    }

    function setAssignStatus(msg, isError, asHtml) {
        var el = document.getElementById('assign-courses-status');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        if (asHtml) {
            el.innerHTML = msg;
        } else {
            el.textContent = msg;
        }
        el.style.color = isError ? '#c0392b' : '#7f8c8d';
    }

    function eventLabel(eid) {
        var choices = window.EVENT_CHOICES_FROM_SERVER || [];
        var found = choices.find(function (c) {
            return String(c.value || c).toLowerCase() === String(eid).toLowerCase();
        });
        if (found && found.label) return found.label;
        return String(eid).toUpperCase();
    }

    function packageEvents() {
        if (window.CONFIG_PACKAGE_EVENTS && window.CONFIG_PACKAGE_EVENTS.length) {
            return window.CONFIG_PACKAGE_EVENTS.slice();
        }
        return ['full', 'half', '10k'];
    }

    function fetchOrgLegsState() {
        return fetch('/api/org/legs/state', { credentials: 'same-origin' })
            .then(function (r) {
                return r.ok ? r.json() : null;
            });
    }

    function fetchOrgCourses(distance) {
        var url = '/api/org/courses';
        if (distance) url += '?distance=' + encodeURIComponent(distance);
        return fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (d) {
                    return r.ok && d.courses ? d.courses : [];
                });
            })
            .catch(function () {
                return [];
            });
    }

    function parseOrderValues(raw) {
        if (raw == null || raw === '') return [];
        return String(raw)
            .split(',')
            .map(function (p) {
                return parseInt(p.trim(), 10);
            })
            .filter(function (n) {
                return !isNaN(n) && n > 0;
            });
    }

    function recipeFromOrderGrid(legs, orderGrid, distance) {
        var slots = {};
        (legs || []).forEach(function (leg) {
            var id = leg.id;
            var raw = orderGrid[distance] && orderGrid[distance][id];
            parseOrderValues(raw).forEach(function (slot) {
                if (!slots[slot]) slots[slot] = [];
                slots[slot].push(id);
            });
        });
        var keys = Object.keys(slots)
            .map(function (k) {
                return parseInt(k, 10);
            })
            .filter(function (n) {
                return !isNaN(n);
            })
            .sort(function (a, b) {
                return a - b;
            });
        var recipe = [];
        keys.forEach(function (k) {
            slots[k].forEach(function (lid) {
                recipe.push(lid);
            });
        });
        return recipe;
    }

    function orderGridFromRecipe(recipe, distance) {
        var grid = {};
        ['full', 'half', '10k', 'elite', 'open'].forEach(function (ev) {
            grid[ev] = {};
        });
        if (!distance || !grid[distance]) return grid;
        var positions = {};
        (recipe || []).forEach(function (legId, idx) {
            var id = String(legId || '').trim();
            if (!id) return;
            if (!positions[id]) positions[id] = [];
            positions[id].push(idx + 1);
        });
        Object.keys(positions).forEach(function (id) {
            grid[distance][id] = positions[id].join(',');
        });
        return grid;
    }

    function syncSavedCourseModalMode() {
        var title = document.getElementById('saved-course-modal-title');
        var saveBtn = document.getElementById('btn-saved-course-save');
        var nameInput = document.getElementById('saved-course-name');
        var distSel = document.getElementById('saved-course-distance');
        var idWrap = document.getElementById('saved-course-id-wrap');
        var idInput = document.getElementById('saved-course-id');
        var editNote = document.getElementById('saved-course-edit-note');
        var isEdit = !!editingCourseId;
        if (title) title.textContent = isEdit ? 'Edit course recipe' : 'New course';
        if (saveBtn) {
            saveBtn.textContent = isEdit ? 'Save recipe' : 'Save course snapshot';
        }
        if (nameInput) nameInput.readOnly = isEdit;
        if (distSel) distSel.disabled = isEdit;
        if (idWrap) idWrap.style.display = isEdit ? '' : 'none';
        if (idInput) idInput.value = isEdit ? editingCourseId : '';
        if (editNote) editNote.style.display = isEdit ? 'block' : 'none';
    }

    function ensureOrgCoursePreviewMap() {
        if (orgCoursePreviewMap) return orgCoursePreviewMap;
        var el = document.getElementById('org-course-preview-map');
        if (!el || typeof L === 'undefined') return null;
        orgCoursePreviewMap = L.map('org-course-preview-map', { zoomControl: true }).setView(
            [45.95, -66.64],
            13
        );
        L.tileLayer(
            'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
            { attribution: '© OpenStreetMap contributors, © CARTO', maxZoom: 19 }
        ).addTo(orgCoursePreviewMap);
        return orgCoursePreviewMap;
    }

    function clearOrgCoursePreviewLine(map) {
        if (!map || !orgCoursePreviewLine) return;
        map.removeLayer(orgCoursePreviewLine);
        orgCoursePreviewLine = null;
    }

    function clearOrgCoursePreviewLocationsLayer(map) {
        if (!map || !orgCoursePreviewLocationsLayer) return;
        map.removeLayer(orgCoursePreviewLocationsLayer);
        orgCoursePreviewLocationsLayer = null;
    }

    function getLocationPinColor(locType) {
        return LOCATION_PIN_COLORS[locType] || '#27ae60';
    }

    function buildOrgCourseLocationTooltip(loc) {
        var parts = [];
        if (loc.loc_label) parts.push(loc.loc_label);
        if (loc.loc_type) parts.push(String(loc.loc_type));
        if (loc.zone) parts.push('Zone ' + loc.zone);
        var resources = loc.resources || {};
        Object.keys(resources).forEach(function (code) {
            var n = parseInt(resources[code], 10);
            if (n > 0) parts.push(String(code).toUpperCase() + ': ' + n);
        });
        return parts.join(' · ') || 'Location';
    }

    function renderOrgCoursePreviewLocations(map, locations) {
        if (!map) return;
        clearOrgCoursePreviewLocationsLayer(map);
        if (!locations || !locations.length) return;
        orgCoursePreviewLocationsLayer = L.featureGroup();
        locations.forEach(function (loc) {
            var lat = typeof loc.lat === 'number' ? loc.lat : parseFloat(loc.lat);
            var lon = typeof loc.lon === 'number' ? loc.lon : parseFloat(loc.lon);
            if (isNaN(lat) || isNaN(lon)) return;
            var fill = getLocationPinColor(loc.loc_type);
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
                    iconAnchor: [7, 7],
                }),
                interactive: true,
            });
            marker.bindTooltip(buildOrgCourseLocationTooltip(loc), {
                permanent: false,
                direction: 'top',
                offset: [0, -10],
                className: 'course-map-tooltip',
            });
            orgCoursePreviewLocationsLayer.addLayer(marker);
        });
        if (orgCoursePreviewLocationsLayer.getLayers().length) {
            orgCoursePreviewLocationsLayer.addTo(map);
        } else {
            orgCoursePreviewLocationsLayer = null;
        }
    }

    function renderOrgCoursePreviewRecipeTable(recipeLegs) {
        var wrap = document.getElementById('org-course-preview-recipe-wrap');
        var tbody = document.getElementById('org-course-preview-recipe-tbody');
        if (!wrap || !tbody) return;
        tbody.innerHTML = '';
        if (!recipeLegs || !recipeLegs.length) {
            wrap.style.display = 'none';
            return;
        }
        wrap.style.display = 'block';
        recipeLegs.forEach(function (leg) {
            var tr = document.createElement('tr');
            function td(text) {
                var cell = document.createElement('td');
                cell.textContent = text == null ? '' : String(text);
                return cell;
            }
            tr.appendChild(td(leg.order != null ? leg.order : ''));
            tr.appendChild(td(leg.id || ''));
            tr.appendChild(td(leg.leg_label || ''));
            tr.appendChild(td(leg.start_label || ''));
            tr.appendChild(td(leg.end_label || ''));
            tr.appendChild(
                td(leg.length_km != null ? Number(leg.length_km).toFixed(2) + ' km' : '—')
            );
            tbody.appendChild(tr);
        });
    }

    function hideOrgCoursePreview() {
        var section = document.getElementById('org-course-preview-section');
        if (section) section.style.display = 'none';
        selectedCourseId = null;
        document.querySelectorAll('#saved-courses-tbody tr.org-course-row').forEach(function (tr) {
            tr.classList.remove('selected');
        });
        var map = orgCoursePreviewMap;
        clearOrgCoursePreviewLine(map);
        clearOrgCoursePreviewLocationsLayer(map);
        renderOrgCoursePreviewRecipeTable([]);
    }

    function selectOrgCourse(courseId) {
        selectedCourseId = courseId;
        document.querySelectorAll('#saved-courses-tbody tr.org-course-row').forEach(function (tr) {
            tr.classList.toggle('selected', tr.dataset.courseId === courseId);
        });
        loadOrgCoursePreview(courseId);
    }

    function loadOrgCoursePreview(courseId) {
        var section = document.getElementById('org-course-preview-section');
        var metaEl = document.getElementById('org-course-preview-meta');
        if (!courseId || !section) return;

        section.style.display = 'block';
        if (metaEl) {
            metaEl.textContent = 'Loading route…';
            metaEl.style.color = '#7f8c8d';
        }
        renderOrgCoursePreviewRecipeTable([]);

        fetch('/api/org/courses/' + encodeURIComponent(courseId) + '/preview', {
            credentials: 'same-origin',
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    throw new Error(payload.data.detail || 'Failed to load course map');
                }
                var data = payload.data;
                var map = ensureOrgCoursePreviewMap();
                if (!map) return;
                clearOrgCoursePreviewLine(map);
                clearOrgCoursePreviewLocationsLayer(map);
                var latlngs = (data.coordinates || []).map(function (c) {
                    return [c[1], c[0]];
                });
                if (latlngs.length < 2) {
                    throw new Error('Course route has too few points to display');
                }
                orgCoursePreviewLine = L.polyline(latlngs, {
                    color: '#8e44ad',
                    weight: 5,
                    opacity: 0.92,
                }).addTo(map);
                renderOrgCoursePreviewLocations(map, data.locations || []);
                var bounds = orgCoursePreviewLine.getBounds();
                if (orgCoursePreviewLocationsLayer) {
                    bounds = bounds.extend(orgCoursePreviewLocationsLayer.getBounds());
                }
                map.fitBounds(bounds, {
                    padding: [28, 28],
                    maxZoom: 15,
                });
                setTimeout(function () {
                    map.invalidateSize();
                }, 120);
                if (metaEl) {
                    metaEl.textContent =
                        (data.name || data.course_id) +
                        ' · ' +
                        String(data.distance || '').toUpperCase() +
                        ' · ' +
                        Number(data.length_km || 0).toFixed(2) +
                        ' km · ' +
                        (data.leg_count || 0) +
                        ' leg(s)' +
                        (data.locations && data.locations.length
                            ? ' · ' + data.locations.length + ' location(s)'
                            : '');
                    metaEl.style.color = '#7f8c8d';
                }
                renderOrgCoursePreviewRecipeTable(data.recipe_legs || []);
            })
            .catch(function (err) {
                if (metaEl) {
                    metaEl.textContent = err.message || String(err);
                    metaEl.style.color = '#c0392b';
                }
                renderOrgCoursePreviewRecipeTable([]);
            });
    }

    function renderOrgCoursesTable() {
        var wrap = document.getElementById('saved-courses-table-wrap');
        var empty = document.getElementById('saved-courses-empty');
        var tbody = document.getElementById('saved-courses-tbody');
        if (!tbody) return;

        if (!orgCourses.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            tbody.innerHTML = '';
            hideOrgCoursePreview();
            return;
        }
        if (wrap) wrap.style.display = 'block';
        if (empty) empty.style.display = 'none';
        tbody.innerHTML = '';

        orgCourses.forEach(function (sc) {
            var tr = document.createElement('tr');
            tr.className = 'org-course-row';
            tr.dataset.courseId = sc.id;
            if (sc.id === selectedCourseId) {
                tr.classList.add('selected');
            }
            tr.addEventListener('click', function (e) {
                if (e.target && e.target.closest('button')) return;
                selectOrgCourse(sc.id);
            });
            function td(text) {
                var cell = document.createElement('td');
                cell.textContent = text == null ? '' : String(text);
                return cell;
            }
            tr.appendChild(td(sc.id));
            tr.appendChild(td(sc.name || sc.id));
            tr.appendChild(td(String(sc.distance || '').toUpperCase()));
            tr.appendChild(
                td(sc.length_km != null ? Number(sc.length_km).toFixed(2) + ' km' : '—')
            );
            var actions = document.createElement('td');
            actions.className = 'course-map-action-cell';
            var ta = window.TableActions;
            if (ta) {
                actions.appendChild(
                    ta.createIconButton('edit', 'Edit recipe', function (ev) {
                        ev.stopPropagation();
                        openEditRecipeModal(sc);
                    })
                );
                actions.appendChild(
                    ta.createIconButton('delete', 'Delete course', function (ev) {
                        ev.stopPropagation();
                        if (
                            !ta.doubleConfirmDelete({
                                subject: 'course ' + sc.id + ' (“' + (sc.name || sc.id) + '”)',
                                detail: 'Frozen exports under runflow/org/courses/' + sc.id + '/ will be removed.',
                            })
                        ) {
                            return;
                        }
                        fetch('/api/org/courses/' + encodeURIComponent(sc.id), {
                            method: 'DELETE',
                            credentials: 'same-origin',
                        })
                            .then(function (r) {
                                return r.json().then(function (d) {
                                    return { ok: r.ok, data: d };
                                });
                            })
                            .then(function (payload) {
                                if (!payload.ok) {
                                    throw new Error(payload.data.detail || 'Delete failed');
                                }
                                orgCourses = payload.data.courses || [];
                                renderOrgCoursesTable();
                                setHubStatus('Deleted course ' + sc.id + '.');
                            })
                            .catch(function (err) {
                                setHubStatus(err.message || String(err), true);
                            });
                    })
                );
            } else {
                var editBtn = document.createElement('button');
                editBtn.type = 'button';
                editBtn.className = 'course-btn';
                editBtn.textContent = 'Edit recipe';
                editBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    openEditRecipeModal(sc);
                });
                actions.appendChild(editBtn);
            }
            tr.appendChild(actions);
            tbody.appendChild(tr);
        });

        if (selectedCourseId && orgCourses.some(function (c) { return c.id === selectedCourseId; })) {
            loadOrgCoursePreview(selectedCourseId);
        } else if (orgCourses.length) {
            selectOrgCourse(orgCourses[0].id);
        }
    }

    function compareLegIds(a, b) {
        var na = parseInt(a, 10);
        var nb = parseInt(b, 10);
        if (!isNaN(na) && !isNaN(nb)) return na - nb;
        return String(a).localeCompare(String(b));
    }

    function renderDraftRecipeTable(legs) {
        var tbody = document.getElementById('saved-course-recipe-tbody');
        var thead = document.getElementById('saved-course-recipe-thead');
        if (!tbody || !thead) return;
        thead.innerHTML =
            '<th>Leg</th><th>Label</th><th>km</th><th>' +
            eventLabel(draftDistance) +
            ' order</th>';
        tbody.innerHTML = '';
        if (!draftOrderGrid[draftDistance]) draftOrderGrid[draftDistance] = {};
        (legs || [])
            .slice()
            .sort(function (a, b) {
                return compareLegIds(a.id, b.id);
            })
            .forEach(function (leg) {
            var tr = document.createElement('tr');
            tr.appendChild(document.createElement('td')).textContent = leg.id;
            tr.appendChild(document.createElement('td')).textContent = leg.leg_label || '';
            tr.appendChild(document.createElement('td')).textContent =
                leg.length_km != null ? Number(leg.length_km).toFixed(2) : '';
            var orderTd = document.createElement('td');
            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'segment-recipe-order-input';
            input.placeholder = '—';
            input.dataset.legId = leg.id;
            input.value =
                draftOrderGrid[draftDistance][leg.id] != null
                    ? String(draftOrderGrid[draftDistance][leg.id])
                    : '';
            input.addEventListener('input', function () {
                draftOrderGrid[draftDistance][leg.id] = input.value.trim();
            });
            orderTd.appendChild(input);
            tr.appendChild(orderTd);
            tbody.appendChild(tr);
        });
    }

    function openSaveModal() {
        var modal = document.getElementById('saved-course-modal');
        if (!modal) return;
        editingCourseId = null;
        setHubStatus('');
        fetchOrgLegsState().then(function (lib) {
            if (!lib || !lib.legs || !lib.legs.length) {
                alert('Add legs in the Legs library first.');
                return;
            }
            draftOrderGrid = {};
            var events = ['full', 'half', '10k', 'elite', 'open'];
            draftDistance = '10k';
            events.forEach(function (ev) {
                draftOrderGrid[ev] = {};
            });
            var distSel = document.getElementById('saved-course-distance');
            if (distSel) {
                distSel.innerHTML = '';
                ['full', 'half', '10k'].forEach(function (ev) {
                    var opt = document.createElement('option');
                    opt.value = ev;
                    opt.textContent = eventLabel(ev);
                    if (ev === draftDistance) opt.selected = true;
                    distSel.appendChild(opt);
                });
            }
            var nameInput = document.getElementById('saved-course-name');
            if (nameInput) nameInput.value = '';
            syncSavedCourseModalMode();
            renderDraftRecipeTable(lib.legs);
            modal.hidden = false;
            modal.setAttribute('aria-hidden', 'false');
        });
    }

    function openEditRecipeModal(course) {
        var modal = document.getElementById('saved-course-modal');
        if (!modal || !course) return;
        editingCourseId = course.id;
        setHubStatus('');
        fetchOrgLegsState().then(function (lib) {
            if (!lib || !lib.legs || !lib.legs.length) {
                alert('Add legs in the Legs library first.');
                return;
            }
            draftDistance = String(course.distance || '10k').toLowerCase();
            draftOrderGrid = orderGridFromRecipe(course.recipe || [], draftDistance);
            var distSel = document.getElementById('saved-course-distance');
            if (distSel) {
                distSel.innerHTML = '';
                var opt = document.createElement('option');
                opt.value = draftDistance;
                opt.textContent = eventLabel(draftDistance);
                opt.selected = true;
                distSel.appendChild(opt);
            }
            var nameInput = document.getElementById('saved-course-name');
            if (nameInput) nameInput.value = course.name || course.id || '';
            syncSavedCourseModalMode();
            renderDraftRecipeTable(lib.legs);
            modal.hidden = false;
            modal.setAttribute('aria-hidden', 'false');
        });
    }

    function closeSaveModal() {
        var modal = document.getElementById('saved-course-modal');
        if (!modal) return;
        editingCourseId = null;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
    }

    function saveNamedCourse() {
        var nameInput = document.getElementById('saved-course-name');
        var distSel = document.getElementById('saved-course-distance');
        var name = nameInput ? nameInput.value.trim() : '';
        var distance = distSel ? distSel.value : draftDistance;
        if (!name) {
            alert('Enter a course name (e.g. 10K University).');
            return;
        }
        fetchOrgLegsState().then(function (lib) {
            if (!lib) return;
            var recipe = recipeFromOrderGrid(lib.legs, draftOrderGrid, distance);
            if (recipe.length < 1) {
                alert('Set order numbers (1, 2, 3…) for legs in this course.');
                return;
            }
            var url = editingCourseId
                ? '/api/org/courses/' + encodeURIComponent(editingCourseId)
                : '/api/org/courses';
            var method = editingCourseId ? 'PUT' : 'POST';
            var body = editingCourseId
                ? { recipe: recipe, name: name }
                : { name: name, distance: distance, recipe: recipe };
            setHubStatus(
                editingCourseId ? 'Updating course recipe…' : 'Saving course snapshot…'
            );
            fetch(url, {
                method: method,
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            })
                .then(function (r) {
                    return r.json().then(function (d) {
                        return { ok: r.ok, data: d };
                    });
                })
                .then(function (payload) {
                    if (!payload.ok) {
                        throw new Error(payload.data.detail || 'Save failed');
                    }
                    orgCourses = payload.data.courses || [];
                    var savedId =
                        (payload.data.saved_course && payload.data.saved_course.id) ||
                        editingCourseId;
                    editingCourseId = null;
                    selectedCourseId = savedId || selectedCourseId;
                    renderOrgCoursesTable();
                    closeSaveModal();
                    var warnings = payload.data.stitch_warnings || [];
                    var msg =
                        'Saved "' +
                        name +
                        '"' +
                        (savedId ? ' (' + savedId + ').' : '.');
                    if (warnings.length) {
                        msg += ' Warnings: ' + warnings.join(' · ');
                    }
                    setHubStatus(msg, warnings.length > 0);
                    refreshAssignForm();
                })
                .catch(function (err) {
                    setHubStatus(err.message || String(err), true);
                });
        });
    }

    function refreshHubCourses() {
        fetchOrgCourses().then(function (list) {
            orgCourses = list;
            renderOrgCoursesTable();
        });
    }

    function refreshAssignForm() {
        var form = document.getElementById('assign-courses-form');
        var base = packageApiBase();
        if (!form || !base) return;

        Promise.all([
            fetch(base + '/assigned-courses', { credentials: 'same-origin' }).then(function (r) {
                return r.json();
            }),
            fetchOrgCourses(),
        ]).then(function (results) {
            var assignPayload = results[0];
            var courses = results[1] || [];
            orgCourses = courses;
            if (!assignPayload || !assignPayload.ok) {
                setAssignStatus(
                    (assignPayload && assignPayload.detail) || 'Failed to load assignments',
                    true
                );
                return;
            }
            var events = assignPayload.package_events || packageEvents();
            var assigned = assignPayload.assigned_courses || {};
            form.innerHTML = '';
            events.forEach(function (ev) {
                var row = document.createElement('div');
                row.className = 'assign-courses-row';
                row.style.cssText =
                    'display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;flex-wrap:wrap;';
                var label = document.createElement('label');
                label.style.cssText = 'min-width:5rem;font-weight:600;';
                label.textContent = eventLabel(ev);
                var sel = document.createElement('select');
                sel.className = 'course-btn';
                sel.dataset.distance = ev;
                sel.style.minWidth = '16rem';
                var blank = document.createElement('option');
                blank.value = '';
                blank.textContent = '— select course —';
                sel.appendChild(blank);
                courses
                    .filter(function (c) {
                        return String(c.distance || '').toLowerCase() === String(ev).toLowerCase();
                    })
                    .forEach(function (c) {
                        var opt = document.createElement('option');
                        opt.value = c.id;
                        opt.textContent = (c.name || c.id) + ' (' + c.id + ')';
                        if (assigned[ev] === c.id) opt.selected = true;
                        sel.appendChild(opt);
                    });
                row.appendChild(label);
                row.appendChild(sel);
                form.appendChild(row);
            });
            var saveRow = document.createElement('button');
            saveRow.type = 'button';
            saveRow.className = 'course-btn';
            saveRow.textContent = 'Save assignments';
            saveRow.style.marginTop = '0.5rem';
            saveRow.addEventListener('click', saveAssignments);
            form.appendChild(saveRow);

            var dirEl = document.getElementById('assign-courses-data-dir');
            if (dirEl) {
                dirEl.style.display = 'block';
                dirEl.innerHTML =
                    'After <strong>Build race exports</strong>, use <strong>Run analysis</strong> or analyze with <code>data_dir</code>: <code>runflow/config/' +
                    configId() +
                    '</code>';
            }
            refreshPackageReadiness();
            refreshPackageLatestRuns();
        });
    }

    function saveAssignments() {
        var base = packageApiBase();
        if (!base) return;
        var form = document.getElementById('assign-courses-form');
        if (!form) return;
        var assigned = {};
        form.querySelectorAll('select[data-distance]').forEach(function (sel) {
            if (sel.value) assigned[sel.dataset.distance] = sel.value;
        });
        setAssignStatus('Saving assignments…');
        fetch(base + '/assigned-courses', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ assigned_courses: assigned }),
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) throw new Error(payload.data.detail || 'Save failed');
                setAssignStatus('Assignments saved.');
            })
            .catch(function (err) {
                setAssignStatus(err.message || String(err), true);
            });
    }

    function syncRunAnalysisButton(readiness) {
        var btn = document.getElementById('btn-run-package-analysis');
        if (!btn) return;
        var ready = !!(readiness && readiness.analyze_ready);
        btn.disabled = !ready || !configId();
        if (ready) {
            btn.title =
                'Run v2 analysis using runflow/config/' +
                configId() +
                ' (you will enter start times for each event)';
        } else {
            var missing = (readiness && readiness.missing) || [];
            var extras = [];
            if (readiness && !readiness.has_runners) extras.push('*_runners.csv');
            if (readiness && !readiness.has_gpx) extras.push('*.gpx');
            btn.title =
                'Analysis not ready — missing: ' +
                (missing.concat(extras).join(', ') || 'required files');
        }
    }

    function refreshPackageReadiness() {
        var base = packageApiBase();
        if (!base) {
            syncRunAnalysisButton(null);
            return Promise.resolve(null);
        }
        return fetch(base, { credentials: 'same-origin' })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                var readiness = (data && data.readiness) || null;
                syncRunAnalysisButton(readiness);
                return readiness;
            })
            .catch(function () {
                syncRunAnalysisButton(null);
                return null;
            });
    }

    function packageIdFromDataDir(dataDir) {
        if (!dataDir) return '';
        var normalized = String(dataDir).replace(/\\/g, '/').replace(/\/+$/, '');
        var marker = '/config/';
        var idx = normalized.lastIndexOf(marker);
        if (idx < 0) return '';
        return (normalized.slice(idx + marker.length).split('/')[0] || '').trim();
    }

    function refreshPackageLatestRuns() {
        var wrap = document.getElementById('package-latest-runs');
        var list = document.getElementById('package-latest-runs-list');
        var empty = document.getElementById('package-latest-runs-empty');
        var pkgId = configId();
        if (!wrap || !list || !empty || !pkgId) {
            if (wrap) wrap.style.display = 'none';
            return Promise.resolve();
        }
        wrap.style.display = 'block';
        list.innerHTML = '';
        empty.style.display = 'none';
        empty.textContent = 'Loading recent runs…';
        empty.style.display = 'block';

        return fetch('/api/runs/list', { credentials: 'same-origin' })
            .then(function (r) {
                return r.ok ? r.json() : null;
            })
            .then(function (data) {
                var runs = (data && data.runs) || [];
                // Newest first; only probe a small recent window (client-side, zero new API)
                var candidates = runs.slice(0, 20);
                return Promise.all(
                    candidates.map(function (run) {
                        return fetch(
                            '/api/analysis/' + encodeURIComponent(run.run_id) + '/config',
                            { credentials: 'same-origin' }
                        )
                            .then(function (r) {
                                return r.ok ? r.json() : null;
                            })
                            .then(function (cfg) {
                                var matched = packageIdFromDataDir(cfg && cfg.data_dir) === pkgId;
                                return matched
                                    ? {
                                          run_id: run.run_id,
                                          description: run.description || '',
                                          date: run.formatted_date || run.created_at || '',
                                      }
                                    : null;
                            })
                            .catch(function () {
                                return null;
                            });
                    })
                );
            })
            .then(function (matched) {
                var hits = (matched || []).filter(Boolean).slice(0, 5);
                list.innerHTML = '';
                if (!hits.length) {
                    empty.textContent = 'No analysis runs found for this package yet.';
                    empty.style.display = 'block';
                    return;
                }
                empty.style.display = 'none';
                hits.forEach(function (hit) {
                    var li = document.createElement('li');
                    li.style.marginBottom = '0.25rem';
                    var a = document.createElement('a');
                    a.href = '/density?run_id=' + encodeURIComponent(hit.run_id);
                    a.textContent = hit.description || hit.run_id;
                    a.title = hit.run_id;
                    li.appendChild(a);
                    if (hit.date) {
                        var span = document.createElement('span');
                        span.style.color = '#7f8c8d';
                        span.style.marginLeft = '0.4rem';
                        span.textContent = '(' + hit.date + ')';
                        li.appendChild(span);
                    }
                    list.appendChild(li);
                });
            })
            .catch(function () {
                empty.textContent = 'Could not load latest runs.';
                empty.style.display = 'block';
            });
    }

    function minutesToTime(minutes) {
        var m = parseInt(minutes, 10);
        if (isNaN(m)) return '';
        var h = Math.floor(m / 60);
        var min = m % 60;
        return String(h).padStart(2, '0') + ':' + String(min).padStart(2, '0');
    }

    function timeToMinutes(timeStr) {
        if (!timeStr) return null;
        var parts = String(timeStr).trim().split(':');
        if (parts.length < 2) return null;
        var h = parseInt(parts[0], 10);
        var m = parseInt(parts[1], 10);
        if (isNaN(h) || isNaN(m)) return null;
        return h * 60 + m;
    }

    function showRunAnalysisModal(show) {
        var modal = document.getElementById('run-analysis-modal');
        if (!modal) return;
        modal.hidden = !show;
        modal.setAttribute('aria-hidden', show ? 'false' : 'true');
    }

    function setRunAnalysisModalError(msg) {
        var el = document.getElementById('run-analysis-modal-error');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.textContent = msg;
    }

    function renderRunAnalysisEventRows(events) {
        var tbody = document.getElementById('run-analysis-events-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        (events || []).forEach(function (ev) {
            var tr = document.createElement('tr');
            var nameTd = document.createElement('td');
            nameTd.textContent = eventLabel(ev.name || ev.id || '');
            nameTd.dataset.eventName = ev.name;
            tr.appendChild(nameTd);

            var startTd = document.createElement('td');
            var startInput = document.createElement('input');
            startInput.type = 'time';
            startInput.className = 'config-package-input';
            startInput.dataset.eventName = ev.name;
            startInput.required = true;
            var suggested =
                ev.suggested_start_time_label ||
                (ev.suggested_start_time != null ? minutesToTime(ev.suggested_start_time) : '');
            if (suggested) startInput.value = suggested;
            startTd.appendChild(startInput);
            tr.appendChild(startTd);

            var durTd = document.createElement('td');
            var durInput = document.createElement('input');
            durInput.type = 'number';
            durInput.min = '1';
            durInput.max = '500';
            durInput.className = 'config-package-input';
            durInput.style.width = '5rem';
            durInput.dataset.eventName = ev.name;
            durInput.required = true;
            if (ev.suggested_event_duration_minutes != null) {
                durInput.value = String(ev.suggested_event_duration_minutes);
            }
            durTd.appendChild(durInput);
            tr.appendChild(durTd);

            tbody.appendChild(tr);
        });
    }

    function collectRunAnalysisEvents(eventDay) {
        var tbody = document.getElementById('run-analysis-events-tbody');
        if (!tbody) return [];
        var events = [];
        tbody.querySelectorAll('tr').forEach(function (tr) {
            var name = tr.querySelector('td[data-event-name]');
            var startInput = tr.querySelector('input[type="time"]');
            var durInput = tr.querySelector('input[type="number"]');
            if (!name || !startInput || !durInput) return;
            var eventName = name.dataset.eventName;
            var startMinutes = timeToMinutes(startInput.value);
            var duration = parseInt(durInput.value, 10);
            if (!eventName) return;
            if (startMinutes == null || startMinutes < 300 || startMinutes > 1200) {
                throw new Error(
                    eventLabel(eventName) + ': start time must be between 05:00 and 20:00'
                );
            }
            if (isNaN(duration) || duration < 1 || duration > 500) {
                throw new Error(
                    eventLabel(eventName) + ': duration must be between 1 and 500 minutes'
                );
            }
            events.push({
                name: eventName,
                day: eventDay,
                start_time: startMinutes,
                event_duration_minutes: duration,
            });
        });
        return events;
    }

    var runAnalysisSetup = null;

    function openRunAnalysisModal() {
        var base = packageApiBase();
        if (!base) return;
        setRunAnalysisModalError('');
        setAssignStatus('Loading analysis setup…');
        fetch(base + '/analyze-setup', { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    throw new Error(
                        (payload.data && payload.data.detail) || 'Failed to load analysis setup'
                    );
                }
                var setup = payload.data;
                if (!setup.readiness || !setup.readiness.analyze_ready) {
                    throw new Error('Package is not analysis-ready yet.');
                }
                runAnalysisSetup = setup;
                var dayEl = document.getElementById('run-analysis-event-day');
                if (dayEl) {
                    dayEl.textContent =
                        'Race day: ' + String(setup.event_day || 'sun').toUpperCase();
                }
                renderRunAnalysisEventRows(setup.events || []);
                showRunAnalysisModal(true);
                setAssignStatus('');
            })
            .catch(function (err) {
                setAssignStatus(err.message || String(err), true);
            });
    }

    function submitRunAnalysisModal() {
        var base = packageApiBase();
        if (!base || !runAnalysisSetup) return;
        setRunAnalysisModalError('');
        var events;
        try {
            events = collectRunAnalysisEvents(runAnalysisSetup.event_day || 'sun');
        } catch (err) {
            setRunAnalysisModalError(err.message || String(err));
            return;
        }
        if (!events.length) {
            setRunAnalysisModalError('Add at least one event schedule.');
            return;
        }
        showRunAnalysisModal(false);
        setAssignStatus('Starting analysis…');
        fetch(base + '/run-analysis', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description: runAnalysisSetup.description || '',
                enable_audit: 'n',
                events: events,
            }),
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    throw new Error(
                        (payload.data && (payload.data.error || payload.data.detail)) ||
                            'Analysis start failed'
                    );
                }
                var runId = payload.data.run_id;
                var eventDay = (
                    (runAnalysisSetup && runAnalysisSetup.event_day) ||
                    ''
                )
                    .toLowerCase()
                    .trim();
                if (runId) {
                    localStorage.setItem('selected_run_id', runId);
                    if (eventDay) localStorage.setItem('selected_day', eventDay);
                }
                var msg =
                    'Analysis started. Run ID: ' +
                    runId +
                    '. Results will appear under Results in a few minutes.';
                setAssignStatus(
                    msg +
                        ' <a href="/density?run_id=' +
                        encodeURIComponent(runId) +
                        (eventDay ? '&day=' + encodeURIComponent(eventDay) : '') +
                        '">Open Density</a> · <a href="/dashboard?run_id=' +
                        encodeURIComponent(runId) +
                        '">Runs</a>',
                    false,
                    true
                );
                refreshPackageLatestRuns();
                if (runId && window.confirm(msg + '\n\nOpen Density results now?')) {
                    var dest =
                        '/density?run_id=' + encodeURIComponent(runId);
                    if (eventDay) dest += '&day=' + encodeURIComponent(eventDay);
                    window.location.href = dest;
                }
            })
            .catch(function (err) {
                setAssignStatus(err.message || String(err), true);
            });
    }

    function runPackageAnalysis() {
        refreshPackageReadiness().then(function (readiness) {
            if (!readiness || !readiness.analyze_ready) {
                setAssignStatus('Package is not analysis-ready yet.', true);
                return;
            }
            openRunAnalysisModal();
        });
    }

    function buildRaceExports() {
        var base = packageApiBase();
        if (!base) return;
        setAssignStatus('Building multi-distance race exports…');
        fetch(base + '/build-race-exports', {
            method: 'POST',
            credentials: 'same-origin',
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) throw new Error(payload.data.detail || 'Build failed');
                var warnings = payload.data.stitch_warnings || [];
                var msg =
                    'Race exports ready at ' +
                    (payload.data.analysis_data_dir || 'package root') +
                    '.';
                if (warnings.length) msg += ' Warnings: ' + warnings.join(' · ');
                setAssignStatus(msg, warnings.length > 0);
                syncRunAnalysisButton(payload.data.readiness || null);
                document.dispatchEvent(
                    new CustomEvent('segment-recipes-applied', {
                        detail: { course: null },
                    })
                );
                if (window.segmentRecipes && window.segmentRecipes.load) {
                    window.segmentRecipes.load();
                }
            })
            .catch(function (err) {
                setAssignStatus(err.message || String(err), true);
            });
    }

    function bindUi() {
        var btn = document.getElementById('btn-save-named-course');
        if (btn) btn.addEventListener('click', openSaveModal);
        var saveBtn = document.getElementById('btn-saved-course-save');
        if (saveBtn) saveBtn.addEventListener('click', saveNamedCourse);
        var buildBtn = document.getElementById('btn-build-race-exports');
        if (buildBtn) buildBtn.addEventListener('click', buildRaceExports);
        var runBtn = document.getElementById('btn-run-package-analysis');
        if (runBtn) runBtn.addEventListener('click', runPackageAnalysis);
        var runSubmit = document.getElementById('btn-run-analysis-submit');
        if (runSubmit) runSubmit.addEventListener('click', submitRunAnalysisModal);
        ['run-analysis-modal-close', 'run-analysis-modal-cancel'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.addEventListener('click', function () {
                    showRunAnalysisModal(false);
                    runAnalysisSetup = null;
                });
            }
        });
        var runBackdrop = document.querySelector('#run-analysis-modal .course-location-modal-backdrop');
        if (runBackdrop) {
            runBackdrop.addEventListener('click', function () {
                showRunAnalysisModal(false);
                runAnalysisSetup = null;
            });
        }
        var distSel = document.getElementById('saved-course-distance');
        if (distSel) {
            distSel.addEventListener('change', function () {
                draftDistance = distSel.value;
                fetchOrgLegsState().then(function (lib) {
                    if (lib) renderDraftRecipeTable(lib.legs);
                });
            });
        }
        ['saved-course-modal-close', 'saved-course-modal-cancel'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('click', closeSaveModal);
        });
        var backdrop = document.querySelector(
            '#saved-course-modal .course-location-modal-backdrop'
        );
        if (backdrop) backdrop.addEventListener('click', closeSaveModal);
    }

    document.addEventListener('DOMContentLoaded', bindUi);
    document.addEventListener('race-config-hub-courses-shown', function () {
        refreshHubCourses();
        setTimeout(function () {
            if (orgCoursePreviewMap) {
                orgCoursePreviewMap.invalidateSize();
            }
        }, 150);
    });
    document.addEventListener('race-config-course-tab-shown', function () {
        refreshAssignForm();
    });

    window.SavedCoursesPanel = {
        refresh: refreshHubCourses,
        refreshAssign: refreshAssignForm,
    };
})();
