/**
 * Race Configuration hub — package entry and tabs.
 * Issue #756
 */

(function () {
    const CONFIG_PATH_PREFIX = '/config';

    let packagesListData = [];
    let packageSortColumn = 'updated';
    let packageSortDirection = 'desc';
    let currentConfigId = null;
    let editingPackageId = null;

    function getQuery() {
        return new URLSearchParams(window.location.search);
    }

    function buildConfigUrl(configId, tab) {
        const params = new URLSearchParams();
        if (configId) params.set('config_id', configId);
        if (tab) params.set('tab', tab);
        const qs = params.toString();
        return CONFIG_PATH_PREFIX + (qs ? '?' + qs : '');
    }

    function getConfigId() {
        const raw = getQuery().get('config_id');
        return raw ? raw.trim() : null;
    }

    function getTab() {
        const raw = getQuery().get('tab');
        if (raw === 'runners') return 'runners';
        if (raw === 'course') return 'course';
        return 'legs';
    }

    function eventChoiceList() {
        const raw = window.EVENT_CHOICES_FROM_SERVER || [];
        return raw.map(function (item) {
            if (typeof item === 'string') {
                return { value: item, label: item };
            }
            return {
                value: item.value || item.label,
                label: item.label || item.value,
            };
        });
    }

    function formatEventLabel(eventId) {
        const id = String(eventId || '').toLowerCase();
        const found = eventChoiceList().find(function (c) {
            return String(c.value).toLowerCase() === id;
        });
        return found ? found.label : id.toUpperCase();
    }

    function syncConfigPackagePanels(tab) {
        const legsPanel = document.getElementById('config-package-legs-panel');
        const coursePanel = document.getElementById('config-package-course-panel');
        const mapContainer = document.getElementById('course-map-container');
        const legacyHeader = document.getElementById('course-legacy-draw-header');
        const isPackage = !!document.getElementById('race-config-workspace');
        if (!isPackage) return;
        if (legacyHeader) legacyHeader.style.display = 'none';
        const showLegs = tab === 'legs';
        const showCourse = tab === 'course';
        if (legsPanel) legsPanel.style.display = showLegs ? 'block' : 'none';
        if (coursePanel) coursePanel.style.display = showCourse ? 'block' : 'none';
        if (mapContainer) mapContainer.style.display = showLegs ? 'block' : 'none';
        if (showLegs && window.courseMappingMap) {
            setTimeout(function () {
                window.courseMappingMap.invalidateSize();
            }, 120);
        }
        if (showLegs && window.segmentRecipes && window.segmentRecipes.onLegsTabShown) {
            window.segmentRecipes.onLegsTabShown();
        }
        if (showCourse) {
            if (window.segmentRecipes && window.segmentRecipes.onCourseTabShown) {
                window.segmentRecipes.onCourseTabShown();
            } else if (window.segmentRecipes && window.segmentRecipes.load) {
                window.segmentRecipes.load();
            }
        }
        if (showCourse && window.courseMappingMap) {
            setTimeout(function () {
                window.courseMappingMap.invalidateSize();
            }, 120);
        }
    }

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function truncate(str, len) {
        if (!str) return '';
        const s = String(str).trim();
        return s.length <= len ? s : s.slice(0, len) + '…';
    }

    function formatSavedOn(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            const m = ('0' + (d.getMonth() + 1)).slice(-2);
            const day = ('0' + d.getDate()).slice(-2);
            const h = ('0' + d.getHours()).slice(-2);
            const min = ('0' + d.getMinutes()).slice(-2);
            return m + '-' + day + ' ' + h + ':' + min;
        } catch (e) {
            return '—';
        }
    }

    function setPageTitle(text) {
        const el = document.getElementById('race-config-page-title');
        if (el) el.textContent = text || 'Race Configuration';
    }

    function showEntryOnly() {
        const entry = document.getElementById('race-config-entry');
        const workspace = document.getElementById('race-config-workspace');
        const pageHeader = document.querySelector('.race-config-page .page-header');
        if (entry) entry.style.display = 'block';
        if (workspace) workspace.style.display = 'none';
        if (pageHeader) pageHeader.style.display = '';
        setPageTitle('Race Configuration');
    }

    function isPackageWorkspaceDirty() {
        return window.configPackageCourse && window.configPackageCourse.isDirty();
    }

    function showWorkspace(manifest, configId) {
        const entry = document.getElementById('race-config-entry');
        const workspace = document.getElementById('race-config-workspace');
        const pageHeader = document.querySelector('.race-config-page .page-header');

        currentConfigId = configId;
        if (entry) entry.style.display = 'none';
        if (workspace) workspace.style.display = 'block';
        if (pageHeader) pageHeader.style.display = 'none';

        const label = (manifest && manifest.label) || configId;
        setPageTitle(label);
        const description = (manifest && manifest.description) || '';
        const eventDay = (manifest && manifest.event_day) || '';

        if (window.updateConfigNavLinks) {
            window.updateConfigNavLinks(configId);
        }
        syncCourseMappingConfigId(configId);
        window.CONFIG_PACKAGE_RESOURCES = (manifest && manifest.resources) || [];
        const packageEvents = (manifest && manifest.package_events) || [];
        window.CONFIG_PACKAGE_EVENT_DAY = eventDay;
        window.CONFIG_PACKAGE_EVENTS = packageEvents;
        window.PENDING_PACKAGE_META = {
            label: label,
            description: description,
            event_day: eventDay,
            package_events: packageEvents,
        };
        if (window.syncConfigPackageDetailsCard) {
            window.syncConfigPackageDetailsCard(label, description, eventDay, packageEvents);
        }
        if (window.configPackageCourse && window.configPackageCourse.syncHeaderFromMeta) {
            window.configPackageCourse.syncHeaderFromMeta(
                label,
                description,
                eventDay,
                packageEvents
            );
            delete window.PENDING_PACKAGE_META;
        }
        syncConfigPackagePanels(getTab());
        if (window.segmentRecipes && window.segmentRecipes.load) {
            window.segmentRecipes.load();
        }
    }

    function setActiveTab(tab) {
        document.querySelectorAll('.race-config-page .subnav-tab').forEach(function (btn) {
            const isActive = btn.getAttribute('data-tab') === tab;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        const workspacePanel = document.getElementById('race-config-tab-workspace');
        const runnersPanel = document.getElementById('race-config-tab-runners');
        const isWorkspace = tab === 'legs' || tab === 'course';
        if (workspacePanel) workspacePanel.style.display = isWorkspace ? 'block' : 'none';
        if (runnersPanel) runnersPanel.style.display = tab === 'runners' ? 'block' : 'none';
        syncConfigPackagePanels(tab);
        if (tab === 'runners' && window.initRunnersBaseline) {
            window.initRunnersBaseline();
        }
    }

    function syncCourseMappingConfigId(configId) {
        var root = document.getElementById('course-mapping-root');
        if (root) {
            if (configId) root.dataset.configId = configId;
            else delete root.dataset.configId;
        }
    }

    function sortPackages(list) {
        return list.slice().sort(function (a, b) {
            let av = a[packageSortColumn];
            let bv = b[packageSortColumn];
            if (packageSortColumn === 'updated') {
                av = av ? new Date(av).getTime() : 0;
                bv = bv ? new Date(bv).getTime() : 0;
                return packageSortDirection === 'desc' ? bv - av : av - bv;
            }
            av = av != null ? String(av) : '';
            bv = bv != null ? String(bv) : '';
            return packageSortDirection === 'asc'
                ? av.localeCompare(bv)
                : bv.localeCompare(av);
        });
    }

    function renderPackageTable(selectedId) {
        const tbody = document.getElementById('race-config-list-tbody');
        if (!tbody) return;

        const sorted = sortPackages(packagesListData);
        if (sorted.length === 0) {
            tbody.innerHTML =
                '<tr><td colspan="4" class="placeholder">No configurations yet. Click <strong>New configuration</strong> to create one.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        sorted.forEach(function (pkg) {
            const tr = document.createElement('tr');
            tr.className = 'config-row';
            tr.dataset.configId = pkg.config_id;
            if (pkg.config_id === selectedId) {
                tr.classList.add('selected');
            }
            const name = (pkg.label || pkg.config_id) + (pkg.legacy ? ' (legacy)' : '');
            tr.innerHTML =
                '<td>' +
                escapeHtml(truncate(name, 40)) +
                '</td><td>' +
                escapeHtml(truncate(pkg.description || '', 50)) +
                '</td><td>' +
                escapeHtml(formatSavedOn(pkg.updated)) +
                '</td><td style="text-align: right;"></td>';
            const actionsTd = tr.lastElementChild;
            actionsTd.className = 'course-map-action-cell';
            const ta = window.TableActions;
            if (ta) {
                actionsTd.appendChild(
                    ta.createIconButton(
                        'edit',
                        'Edit package name, day, and description',
                        function (e) {
                            e.stopPropagation();
                            openEditPackageModal(pkg.config_id);
                        }
                    )
                );
                actionsTd.appendChild(
                    ta.createIconButton(
                        'delete',
                        'Delete configuration',
                        function (e) {
                            e.stopPropagation();
                            deleteConfigPackage(pkg);
                        }
                    )
                );
            }
            tr.addEventListener('click', function () {
                window.location.href = buildConfigUrl(pkg.config_id, 'legs');
            });
            tbody.appendChild(tr);
        });
    }

    function closeEditPackageModal() {
        const modal = document.getElementById('race-config-edit-package-modal');
        if (modal) modal.classList.remove('open');
        editingPackageId = null;
    }

    async function openEditPackageModal(configId) {
        const modal = document.getElementById('race-config-edit-package-modal');
        const labelInput = document.getElementById('race-config-edit-label');
        const descInput = document.getElementById('race-config-edit-description');
        const dayInput = document.getElementById('race-config-edit-day');
        const eventsNote = document.getElementById('race-config-edit-events-note');
        const saveBtn = document.getElementById('race-config-edit-save');
        if (!modal || !labelInput) return;
        editingPackageId = configId;
        labelInput.value = '';
        if (descInput) descInput.value = '';
        if (dayInput) dayInput.value = '';
        if (eventsNote) eventsNote.textContent = 'Loading…';
        if (saveBtn) saveBtn.disabled = true;
        modal.classList.add('open');
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(configId),
                { credentials: 'same-origin' }
            );
            if (!resp.ok) throw new Error('Failed to load package');
            const data = await resp.json();
            const manifest = data.manifest || {};
            if (!data.manifest_editable) {
                if (eventsNote) {
                    eventsNote.textContent =
                        'Legacy package — metadata cannot be edited here.';
                }
                if (saveBtn) saveBtn.disabled = true;
            } else {
                labelInput.value = manifest.label || configId;
                if (descInput) descInput.value = manifest.description || '';
                if (dayInput) dayInput.value = manifest.event_day || '';
                const events = manifest.package_events || [];
                if (eventsNote) {
                    eventsNote.textContent = events.length
                        ? 'Events (set at create): ' +
                          events.map(formatEventLabel).join(', ')
                        : 'Events were not recorded for this package.';
                }
                if (saveBtn) saveBtn.disabled = false;
            }
            labelInput.focus();
        } catch (err) {
            closeEditPackageModal();
            alert(err.message || String(err));
        }
    }

    async function deleteConfigPackage(pkg) {
        const ta = window.TableActions;
        const label = (pkg.label || pkg.config_id).trim();
        const subject = 'configuration “' + label + '”';
        if (
            ta &&
            !ta.doubleConfirmDelete({
                subject: subject,
                detail:
                    'All legs, course data, runners, and files under runflow/config/' +
                    pkg.config_id +
                    '/ will be removed.',
            })
        ) {
            return;
        }
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(pkg.config_id),
                { method: 'DELETE', credentials: 'same-origin' }
            );
            const data = await resp.json().catch(function () {
                return {};
            });
            if (!resp.ok) {
                throw new Error(
                    (data && data.detail) || 'Failed to delete configuration'
                );
            }
            if (currentConfigId === pkg.config_id) {
                window.location.href = CONFIG_PATH_PREFIX;
                return;
            }
            await loadPackageList();
        } catch (err) {
            alert(err.message || String(err));
        }
    }

    async function saveEditPackage() {
        if (!editingPackageId) return;
        const labelInput = document.getElementById('race-config-edit-label');
        const descInput = document.getElementById('race-config-edit-description');
        const dayInput = document.getElementById('race-config-edit-day');
        const saveBtn = document.getElementById('race-config-edit-save');
        const label = labelInput && labelInput.value.trim();
        const description = descInput && descInput.value.trim();
        const eventDay = dayInput && dayInput.value.trim();
        if (!label) {
            alert('Enter a name.');
            return;
        }
        if (saveBtn) saveBtn.disabled = true;
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(editingPackageId),
                {
                    method: 'PATCH',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        label: label,
                        description: description || '',
                        event_day: eventDay,
                    }),
                }
            );
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Failed to save');
            closeEditPackageModal();
            if (currentConfigId === editingPackageId) {
                const m = data.manifest || {};
                const events = m.package_events || [];
                window.CONFIG_PACKAGE_EVENTS = events;
                if (window.syncConfigPackageDetailsCard) {
                    window.syncConfigPackageDetailsCard(
                        m.label || label,
                        m.description != null ? m.description : description,
                        m.event_day != null ? m.event_day : eventDay,
                        events
                    );
                }
                if (window.configPackageCourse && window.configPackageCourse.syncHeaderFromMeta) {
                    window.configPackageCourse.syncHeaderFromMeta(
                        m.label || label,
                        m.description != null ? m.description : description,
                        m.event_day != null ? m.event_day : eventDay,
                        events
                    );
                }
            }
            await loadPackageList();
        } catch (err) {
            alert(err.message || String(err));
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    async function loadPackageList() {
        const tbody = document.getElementById('race-config-list-tbody');
        if (tbody) {
            tbody.innerHTML =
                '<tr><td colspan="4" class="placeholder">Loading configurations…</td></tr>';
        }
        try {
            const resp = await fetch('/api/config/packages', { credentials: 'same-origin' });
            if (!resp.ok) throw new Error('Failed to load packages');
            const data = await resp.json();
            packagesListData = data.packages || [];
            renderPackageTable(null);
        } catch (e) {
            console.error('Failed to load config packages', e);
            packagesListData = [];
            if (tbody) {
                tbody.innerHTML =
                    '<tr><td colspan="4" class="placeholder">Failed to load configurations.</td></tr>';
            }
        }
    }

    function renderNewPackageEventChoices() {
        const host = document.getElementById('race-config-new-events');
        if (!host) return;
        host.innerHTML = '';
        eventChoiceList().forEach(function (choice) {
            const id = 'race-config-ev-' + choice.value;
            const label = document.createElement('label');
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.id = id;
            cb.value = choice.value;
            cb.name = 'package_events';
            label.appendChild(cb);
            label.appendChild(document.createTextNode(choice.label));
            host.appendChild(label);
        });
    }

    function openNewModal() {
        const modal = document.getElementById('race-config-new-modal');
        const labelInput = document.getElementById('race-config-new-label');
        const descInput = document.getElementById('race-config-new-description');
        const dayInput = document.getElementById('race-config-new-day');
        if (labelInput) labelInput.value = '';
        if (descInput) descInput.value = '';
        if (dayInput) dayInput.value = '';
        renderNewPackageEventChoices();
        if (modal) modal.classList.add('open');
        if (labelInput) labelInput.focus();
    }

    function closeNewModal() {
        const modal = document.getElementById('race-config-new-modal');
        if (modal) modal.classList.remove('open');
    }

    async function createPackage() {
        const labelInput = document.getElementById('race-config-new-label');
        const descInput = document.getElementById('race-config-new-description');
        const dayInput = document.getElementById('race-config-new-day');
        const createBtn = document.getElementById('race-config-create-btn');
        const label = labelInput && labelInput.value.trim();
        const description = descInput && descInput.value.trim();
        const eventDay = dayInput && dayInput.value.trim();
        const packageEvents = [];
        document
            .querySelectorAll('#race-config-new-events input[type="checkbox"]:checked')
            .forEach(function (cb) {
                packageEvents.push(cb.value);
            });
        if (!label) {
            alert('Enter a name (e.g. FM 2027 Test).');
            return;
        }
        if (!eventDay) {
            alert('Select the race day for this configuration.');
            return;
        }
        if (!packageEvents.length) {
            alert('Select at least one event.');
            return;
        }
        if (createBtn) createBtn.disabled = true;
        try {
            const resp = await fetch('/api/config/packages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    label: label,
                    description: description || '',
                    event_day: eventDay,
                    package_events: packageEvents,
                }),
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || 'Failed to create package');
            }
            closeNewModal();
            window.location.href = buildConfigUrl(data.config_id, 'legs');
        } catch (err) {
            alert(err.message || String(err));
        } finally {
            if (createBtn) createBtn.disabled = false;
        }
    }

    function bindTableSort() {
        const table = document.getElementById('race-config-list-table');
        if (!table) return;
        table.querySelectorAll('th.table-sortable').forEach(function (th) {
            th.style.cursor = 'pointer';
            th.addEventListener('click', function () {
                const col = th.getAttribute('data-sort');
                if (!col) return;
                if (packageSortColumn === col) {
                    packageSortDirection =
                        packageSortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    packageSortColumn = col;
                    packageSortDirection = col === 'updated' ? 'desc' : 'asc';
                }
                renderPackageTable(null);
            });
        });
    }

    async function initWorkspace(configId) {
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(configId),
                { credentials: 'same-origin' }
            );
            if (!resp.ok) {
                showEntryOnly();
                loadPackageList();
                return;
            }
            const data = await resp.json();
            const manifest = data.manifest || {};
            showWorkspace(manifest, configId);
            setActiveTab(getTab());
        } catch (e) {
            console.error(e);
            showEntryOnly();
            loadPackageList();
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        renderNewPackageEventChoices();
        bindTableSort();

        const configId = getConfigId();
        if (!configId) {
            showEntryOnly();
            loadPackageList();
        } else {
            initWorkspace(configId);
        }

        const newBtn = document.getElementById('race-config-new-btn');
        if (newBtn) newBtn.addEventListener('click', openNewModal);

        const cancelBtn = document.getElementById('race-config-new-cancel');
        if (cancelBtn) cancelBtn.addEventListener('click', closeNewModal);

        const modal = document.getElementById('race-config-new-modal');
        if (modal) {
            modal.addEventListener('click', function (e) {
                if (e.target === modal) closeNewModal();
            });
        }

        const createBtn = document.getElementById('race-config-create-btn');
        if (createBtn) createBtn.addEventListener('click', createPackage);

        const editCancel = document.getElementById('race-config-edit-cancel');
        if (editCancel) editCancel.addEventListener('click', closeEditPackageModal);
        const editSave = document.getElementById('race-config-edit-save');
        if (editSave) editSave.addEventListener('click', saveEditPackage);
        const editModal = document.getElementById('race-config-edit-package-modal');
        if (editModal) {
            editModal.addEventListener('click', function (e) {
                if (e.target === editModal) closeEditPackageModal();
            });
        }

        function switchWorkspaceTab(tab, cid) {
            window.history.pushState({}, '', buildConfigUrl(cid, tab));
            setActiveTab(tab);
        }

        document.querySelectorAll('.race-config-page .subnav-tab').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                const tab = btn.getAttribute('data-tab');
                const cid = getConfigId();
                if (!cid) return;
                if (tab === getTab()) return;
                e.preventDefault();
                if (isPackageWorkspaceDirty() && window.configPackageCourse && window.configPackageCourse.saveAll) {
                    window.configPackageCourse
                        .saveAll()
                        .then(function () {
                            switchWorkspaceTab(tab, cid);
                        })
                        .catch(function (err) {
                            alert(
                                'Could not save changes before switching tabs: ' +
                                    (err.message || String(err))
                            );
                        });
                    return;
                }
                switchWorkspaceTab(tab, cid);
            });
        });

        window.addEventListener('popstate', function () {
            const cid = getConfigId();
            if (!cid || !document.getElementById('race-config-workspace')) return;
            setActiveTab(getTab());
        });
    });
})();
