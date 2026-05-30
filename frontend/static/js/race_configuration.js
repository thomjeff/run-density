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
        return raw === 'runners' ? 'runners' : 'course';
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

    function showEntryOnly() {
        const entry = document.getElementById('race-config-entry');
        const workspace = document.getElementById('race-config-workspace');
        if (entry) entry.style.display = 'block';
        if (workspace) workspace.style.display = 'none';
    }

    function showWorkspace(manifest, configId, manifestEditable) {
        const entry = document.getElementById('race-config-entry');
        const workspace = document.getElementById('race-config-workspace');
        const idEl = document.getElementById('race-config-package-id');
        const labelInput = document.getElementById('race-config-edit-label');
        const descInput = document.getElementById('race-config-edit-description');
        const editableBlock = document.getElementById('race-config-meta-editable');
        const readonlyMsg = document.getElementById('race-config-meta-readonly');
        const saveBtn = document.getElementById('race-config-save-meta');
        const statusEl = document.getElementById('race-config-save-status');

        currentConfigId = configId;
        if (entry) entry.style.display = 'none';
        if (workspace) workspace.style.display = 'block';
        if (idEl) idEl.textContent = configId;
        if (statusEl) statusEl.style.display = 'none';

        const canEdit = manifestEditable !== false;
        if (editableBlock) editableBlock.style.display = canEdit ? 'block' : 'none';
        if (readonlyMsg) readonlyMsg.style.display = canEdit ? 'none' : 'block';
        if (saveBtn) saveBtn.style.display = canEdit ? 'inline-block' : 'none';

        if (canEdit && labelInput) {
            labelInput.value = (manifest && manifest.label) || configId;
        }
        if (canEdit && descInput) {
            descInput.value = (manifest && manifest.description) || '';
        }

        if (window.updateConfigNavLinks) {
            window.updateConfigNavLinks(configId);
        }
        syncCourseMappingConfigId(configId);
        if (getTab() === 'course' && window.courseMappingMap) {
            setTimeout(function () {
                window.courseMappingMap.invalidateSize();
            }, 150);
        }
    }

    async function savePackageMetadata() {
        if (!currentConfigId) return;
        const labelInput = document.getElementById('race-config-edit-label');
        const descInput = document.getElementById('race-config-edit-description');
        const saveBtn = document.getElementById('race-config-save-meta');
        const statusEl = document.getElementById('race-config-save-status');
        const label = labelInput && labelInput.value.trim();
        const description = descInput && descInput.value.trim();
        if (!label) {
            alert('Name is required.');
            return;
        }
        if (saveBtn) saveBtn.disabled = true;
        if (statusEl) statusEl.style.display = 'none';
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(currentConfigId),
                {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ label: label, description: description || '' }),
                }
            );
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || 'Failed to save');
            }
            if (statusEl) {
                statusEl.textContent = 'Saved.';
                statusEl.style.display = 'inline';
            }
            if (data.manifest && labelInput) {
                labelInput.value = data.manifest.label || label;
            }
            if (data.manifest && descInput) {
                descInput.value = data.manifest.description || '';
            }
        } catch (err) {
            alert(err.message || String(err));
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    function setActiveTab(tab) {
        document.querySelectorAll('.race-config-tab').forEach(function (btn) {
            const isActive = btn.getAttribute('data-tab') === tab;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        const coursePanel = document.getElementById('race-config-tab-course');
        const runnersPanel = document.getElementById('race-config-tab-runners');
        if (coursePanel) coursePanel.style.display = tab === 'course' ? 'block' : 'none';
        if (runnersPanel) runnersPanel.style.display = tab === 'runners' ? 'block' : 'none';
        if (tab === 'runners' && window.initRunnersBaseline) {
            window.initRunnersBaseline();
        }
        if (tab === 'course' && window.courseMappingMap) {
            setTimeout(function () {
                window.courseMappingMap.invalidateSize();
            }, 100);
        }
    }

    function syncCourseMappingConfigId(configId) {
        var root = document.getElementById('course-mapping-root');
        if (root) {
            if (configId) root.dataset.configId = configId;
            else delete root.dataset.configId;
        }
        var link = document.getElementById('race-config-course-fullpage-link');
        if (link) {
            link.href = configId
                ? '/course-mapping?config_id=' + encodeURIComponent(configId)
                : '/course-mapping';
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
                '<tr><td colspan="3" class="placeholder">No configurations yet. Click <strong>New configuration</strong> to create one.</td></tr>';
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
                '</td>';
            tr.addEventListener('click', function () {
                window.location.href = buildConfigUrl(pkg.config_id, 'course');
            });
            tbody.appendChild(tr);
        });
    }

    async function loadPackageList() {
        const tbody = document.getElementById('race-config-list-tbody');
        if (tbody) {
            tbody.innerHTML =
                '<tr><td colspan="3" class="placeholder">Loading configurations…</td></tr>';
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
                    '<tr><td colspan="3" class="placeholder">Failed to load configurations.</td></tr>';
            }
        }
    }

    function openNewModal() {
        const modal = document.getElementById('race-config-new-modal');
        const labelInput = document.getElementById('race-config-new-label');
        const descInput = document.getElementById('race-config-new-description');
        if (labelInput) labelInput.value = '';
        if (descInput) descInput.value = '';
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
        const createBtn = document.getElementById('race-config-create-btn');
        const label = labelInput && labelInput.value.trim();
        const description = descInput && descInput.value.trim();
        if (!label) {
            alert('Enter a name (e.g. FM 2027 Test).');
            return;
        }
        if (createBtn) createBtn.disabled = true;
        try {
            const resp = await fetch('/api/config/packages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ label: label, description: description || '' }),
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || 'Failed to create package');
            }
            closeNewModal();
            window.location.href = buildConfigUrl(data.config_id, 'course');
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
            showWorkspace(manifest, configId, data.manifest_editable);
            setActiveTab(getTab());
        } catch (e) {
            console.error(e);
            showEntryOnly();
            loadPackageList();
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
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

        const saveMetaBtn = document.getElementById('race-config-save-meta');
        if (saveMetaBtn) saveMetaBtn.addEventListener('click', savePackageMetadata);

        const changePkg = document.getElementById('race-config-change-package');
        if (changePkg) {
            changePkg.addEventListener('click', function () {
                window.location.href = CONFIG_PATH_PREFIX;
            });
        }

        document.querySelectorAll('.race-config-tab').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const tab = btn.getAttribute('data-tab');
                const cid = getConfigId();
                if (!cid) return;
                window.location.href = buildConfigUrl(cid, tab);
            });
        });
    });
})();
