/**
 * Org runner datasets — Build hub catalog and Package picker (Issue #879).
 */
(function () {
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
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

    function participantsLabel(dataset) {
        const summary = (dataset && dataset.summary) || {};
        const events = (dataset && dataset.events) || [];
        const parts = events.map(function (event) {
            const row = summary[event] || {};
            const n = row.participants;
            return event + ' ' + (n == null ? '—' : n);
        });
        return parts.length ? parts.join(' · ') : '—';
    }

    const PACE_METRIC_ROWS = [
        { key: 'participants', label: 'Participants', kind: 'count' },
        { key: 'p00', label: 'P00 (Lead)', kind: 'pace' },
        { key: 'p05', label: 'P05', kind: 'pace' },
        { key: 'p25', label: 'P25', kind: 'pace' },
        { key: 'p50', label: 'P50 (Median)', kind: 'pace' },
        { key: 'p75', label: 'P75', kind: 'pace' },
        { key: 'p95', label: 'P95', kind: 'pace' },
        { key: 'p100', label: 'P100 (Last)', kind: 'pace' },
    ];

    function formatPace(value) {
        if (value == null || value === '') return '—';
        const n = Number(value);
        if (!isFinite(n)) return '—';
        return n.toFixed(2);
    }

    function summaryHasFullPercentiles(summary) {
        const events = Object.keys(summary || {});
        if (!events.length) return false;
        return events.every(function (event) {
            const row = summary[event] || {};
            return row.p05 != null && row.p50 != null && row.p95 != null;
        });
    }

    function hidePackageDatasetMetrics() {
        const wrap = document.getElementById('package-runner-dataset-metrics');
        const table = document.getElementById('package-runner-dataset-metrics-table');
        if (wrap) wrap.style.display = 'none';
        if (table) table.innerHTML = '';
    }

    function renderPackageDatasetMetrics(dataset) {
        const wrap = document.getElementById('package-runner-dataset-metrics');
        const table = document.getElementById('package-runner-dataset-metrics-table');
        if (!wrap || !table) return;
        const summary = (dataset && dataset.summary) || {};
        const events = (dataset && dataset.events && dataset.events.length)
            ? dataset.events
            : Object.keys(summary);
        if (!events.length) {
            hidePackageDatasetMetrics();
            return;
        }
        let html = '<div class="scrollable-table-container"><table class="table-sticky-header" id="package-runner-metrics-grid">';
        html += '<thead><tr><th>Metric</th>';
        events.forEach(function (event) {
            html += '<th>' + escapeHtml(event) + '</th>';
        });
        html += '</tr></thead><tbody>';
        PACE_METRIC_ROWS.forEach(function (row) {
            html += '<tr><td>' + escapeHtml(row.label) + '</td>';
            events.forEach(function (event) {
                const stats = summary[event] || {};
                const raw = stats[row.key];
                const text = row.kind === 'count'
                    ? (raw == null ? '—' : String(raw))
                    : formatPace(raw);
                html += '<td>' + escapeHtml(text) + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody></table></div>';
        table.innerHTML = html;
        wrap.style.display = 'block';
    }

    let packagePickerState = { compatible: [], assigned: null, required: [] };

    function datasetFromPicker(datasetId) {
        if (!datasetId) return null;
        if (packagePickerState.assigned && packagePickerState.assigned.dataset_id === datasetId) {
            return packagePickerState.assigned;
        }
        const rows = packagePickerState.compatible || [];
        for (let i = 0; i < rows.length; i += 1) {
            if (rows[i].dataset_id === datasetId) return rows[i];
        }
        return null;
    }

    async function showSelectedPackageDatasetStats() {
        const select = document.getElementById('package-runner-dataset-select');
        const datasetId = select && select.value ? select.value.trim() : '';
        if (!datasetId) {
            hidePackageDatasetMetrics();
            return;
        }
        let dataset = datasetFromPicker(datasetId);
        if (!dataset || !summaryHasFullPercentiles((dataset && dataset.summary) || {})) {
            try {
                const resp = await fetch(
                    '/api/org/runners/' + encodeURIComponent(datasetId),
                    { credentials: 'same-origin' }
                );
                const data = await resp.json().catch(function () { return {}; });
                if (resp.ok && data.dataset) dataset = data.dataset;
            } catch (err) {
                /* Keep whatever summary we already have. */
            }
        }
        if (!dataset) {
            hidePackageDatasetMetrics();
            return;
        }
        renderPackageDatasetMetrics(dataset);
    }

    function sourceLabel(dataset, byId) {
        const sourceId = dataset && dataset.source_dataset_id;
        if (!sourceId) return 'Actuals';
        const src = byId[sourceId];
        return src ? src.label : sourceId;
    }

    function parsePercentToDecimal(inputValue) {
        if (!inputValue || String(inputValue).trim() === '') return 0;
        const cleaned = String(inputValue).trim().replace(/%$/, '');
        const percentValue = parseFloat(cleaned);
        if (isNaN(percentValue)) {
            throw new Error('Invalid percentage value: "' + inputValue + '"');
        }
        return percentValue / 100;
    }

    function apiError(data, fallback) {
        if (!data) return fallback;
        if (typeof data.detail === 'string') return data.detail;
        if (Array.isArray(data.detail) && data.detail[0] && data.detail[0].msg) {
            return data.detail[0].msg;
        }
        return fallback;
    }

    function setStatus(el, message, isError) {
        if (!el) return;
        if (!message) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.style.color = isError ? '#c0392b' : '#27ae60';
        el.textContent = message;
    }

    let hubDatasets = [];
    let scenarioSourceId = null;
    let hubListenersBound = false;
    let packageListenersBound = false;

    async function loadHubDatasets() {
        const tbody = document.getElementById('race-config-runners-tbody');
        if (!tbody) return;
        tbody.innerHTML =
            '<tr><td colspan="6" class="placeholder">Loading runner datasets…</td></tr>';
        try {
            const resp = await fetch('/api/org/runners', { credentials: 'same-origin' });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Failed to load datasets'));
            hubDatasets = data.datasets || [];
            renderHubTable();
        } catch (err) {
            tbody.innerHTML =
                '<tr><td colspan="6" class="placeholder">' +
                escapeHtml(err.message || String(err)) +
                '</td></tr>';
        }
    }

    function renderHubTable() {
        const tbody = document.getElementById('race-config-runners-tbody');
        if (!tbody) return;
        if (!hubDatasets.length) {
            tbody.innerHTML =
                '<tr><td colspan="6" class="placeholder">No runner datasets yet. Import actuals to create the first dataset.</td></tr>';
            return;
        }
        const byId = {};
        hubDatasets.forEach(function (row) {
            byId[row.dataset_id] = row;
        });
        tbody.innerHTML = '';
        hubDatasets.forEach(function (row) {
            const tr = document.createElement('tr');
            const events = (row.events || []).join(', ') || '—';
            tr.innerHTML =
                '<td>' + escapeHtml(row.label || row.dataset_id) + '</td>' +
                '<td>' + escapeHtml(events) + '</td>' +
                '<td>' + escapeHtml(sourceLabel(row, byId)) + '</td>' +
                '<td>' + escapeHtml(participantsLabel(row)) + '</td>' +
                '<td>' + escapeHtml(formatSavedOn(row.created)) + '</td>' +
                '<td class="course-map-action-cell"></td>';
            const actions = tr.querySelector('.course-map-action-cell');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'course-btn';
            btn.textContent = 'Create scenario';
            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                openScenarioPanel(row);
            });
            actions.appendChild(btn);
            tbody.appendChild(tr);
        });
    }

    function openImportModal() {
        const modal = document.getElementById('runner-dataset-import-modal');
        const label = document.getElementById('runner-dataset-import-label');
        const desc = document.getElementById('runner-dataset-import-description');
        const files = document.getElementById('runner-dataset-import-files');
        if (label) label.value = '';
        if (desc) desc.value = '';
        if (files) files.value = '';
        setStatus(document.getElementById('runner-dataset-import-status'), '', false);
        if (modal) modal.classList.add('open');
        if (label) label.focus();
    }

    function closeImportModal() {
        const modal = document.getElementById('runner-dataset-import-modal');
        if (modal) modal.classList.remove('open');
    }

    async function submitImport() {
        const labelEl = document.getElementById('runner-dataset-import-label');
        const descEl = document.getElementById('runner-dataset-import-description');
        const filesEl = document.getElementById('runner-dataset-import-files');
        const saveBtn = document.getElementById('runner-dataset-import-save');
        const label = labelEl && labelEl.value.trim();
        const files = filesEl && filesEl.files ? Array.from(filesEl.files) : [];
        if (!label) {
            setStatus(document.getElementById('runner-dataset-import-status'), 'Enter a name.', true);
            return;
        }
        if (!files.length) {
            setStatus(document.getElementById('runner-dataset-import-status'), 'Select at least one CSV.', true);
            return;
        }
        const fd = new FormData();
        fd.append('label', label);
        fd.append('description', (descEl && descEl.value.trim()) || '');
        files.forEach(function (file) {
            fd.append('files', file, file.name);
        });
        if (saveBtn) saveBtn.disabled = true;
        setStatus(document.getElementById('runner-dataset-import-status'), 'Importing…', false);
        try {
            const resp = await fetch('/api/org/runners', {
                method: 'POST',
                credentials: 'same-origin',
                body: fd,
            });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Import failed'));
            closeImportModal();
            await loadHubDatasets();
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-import-status'),
                err.message || String(err),
                true
            );
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    function openScenarioPanel(dataset) {
        scenarioSourceId = dataset.dataset_id;
        const panel = document.getElementById('runner-dataset-scenario-panel');
        const sourceEl = document.getElementById('runner-dataset-scenario-source');
        const labelEl = document.getElementById('runner-dataset-scenario-label');
        const descEl = document.getElementById('runner-dataset-scenario-description');
        const host = document.getElementById('runner-dataset-scenario-controls');
        if (sourceEl) {
            sourceEl.textContent =
                'Source: ' + (dataset.label || dataset.dataset_id) +
                ' (' + ((dataset.events || []).join(', ') || 'no events') + '). ' +
                'Creates a new dataset; the source files are not changed.';
        }
        if (labelEl) labelEl.value = (dataset.label || 'Dataset') + ' scenario';
        if (descEl) descEl.value = '';
        setStatus(document.getElementById('runner-dataset-scenario-status'), '', false);
        const events = dataset.events || [];
        if (host) {
            if (!events.length) {
                host.innerHTML = '<p class="card-help">This dataset has no event files.</p>';
            } else {
                let html = '<table class="table-sticky-header" style="width:100%;font-size:0.875rem;"><thead><tr>';
                html += '<th>Variable</th>';
                events.forEach(function (event) {
                    html += '<th>' + escapeHtml(event) + '</th>';
                });
                html += '</tr></thead><tbody>';
                const rows = [
                    { key: 'chg_participants', label: 'Participants %' },
                    { key: 'chg_p00', label: 'P00 (Lead) %' },
                    { key: 'chg_p05', label: 'P05 %' },
                    { key: 'chg_p25', label: 'P25 %' },
                    { key: 'chg_p50', label: 'P50 (Median) %' },
                    { key: 'chg_p75', label: 'P75 %' },
                    { key: 'chg_p95', label: 'P95 %' },
                    { key: 'chg_p100', label: 'P100 (Last) %' },
                ];
                rows.forEach(function (row) {
                    html += '<tr><td>' + escapeHtml(row.label) + '</td>';
                    events.forEach(function (event) {
                        html +=
                            '<td><input type="text" data-rf-chg="' +
                            escapeHtml(row.key) +
                            '" data-rf-event="' +
                            escapeHtml(event) +
                            '" value="0" style="width:4.5rem;padding:0.25rem;"></td>';
                    });
                    html += '</tr>';
                });
                html += '</tbody></table>';
                html += '<p class="card-help" style="margin-top:0.5rem;">Percent change vs the source (40 = +40%). Default 0 copies the source distribution into a new dataset id.</p>';
                host.innerHTML = html;
            }
        }
        if (panel) {
            panel.style.display = 'block';
            panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function closeScenarioPanel() {
        scenarioSourceId = null;
        const panel = document.getElementById('runner-dataset-scenario-panel');
        if (panel) panel.style.display = 'none';
    }

    async function submitScenario() {
        if (!scenarioSourceId) return;
        const labelEl = document.getElementById('runner-dataset-scenario-label');
        const descEl = document.getElementById('runner-dataset-scenario-description');
        const saveBtn = document.getElementById('runner-dataset-scenario-save');
        const label = labelEl && labelEl.value.trim();
        if (!label) {
            setStatus(document.getElementById('runner-dataset-scenario-status'), 'Enter a name.', true);
            return;
        }
        const controlVariables = {};
        const inputs = document.querySelectorAll('#runner-dataset-scenario-controls input[data-rf-chg]');
        try {
            inputs.forEach(function (input) {
                const event = input.getAttribute('data-rf-event');
                const key = input.getAttribute('data-rf-chg');
                if (!event || !key) return;
                if (!controlVariables[event]) controlVariables[event] = {};
                controlVariables[event][key] = parsePercentToDecimal(input.value);
            });
        } catch (err) {
            setStatus(document.getElementById('runner-dataset-scenario-status'), err.message || String(err), true);
            return;
        }
        if (!Object.keys(controlVariables).length) {
            setStatus(document.getElementById('runner-dataset-scenario-status'), 'Source has no events.', true);
            return;
        }
        if (saveBtn) saveBtn.disabled = true;
        setStatus(document.getElementById('runner-dataset-scenario-status'), 'Creating dataset…', false);
        try {
            const resp = await fetch(
                '/api/org/runners/' + encodeURIComponent(scenarioSourceId) + '/scenarios',
                {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        label: label,
                        description: (descEl && descEl.value.trim()) || '',
                        control_variables: controlVariables,
                    }),
                }
            );
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Scenario failed'));
            closeScenarioPanel();
            await loadHubDatasets();
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-scenario-status'),
                err.message || String(err),
                true
            );
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    function bindHubListeners() {
        if (hubListenersBound) return;
        const importBtn = document.getElementById('runner-dataset-import-btn');
        if (importBtn) importBtn.addEventListener('click', openImportModal);
        const importCancel = document.getElementById('runner-dataset-import-cancel');
        if (importCancel) importCancel.addEventListener('click', closeImportModal);
        const importSave = document.getElementById('runner-dataset-import-save');
        if (importSave) importSave.addEventListener('click', submitImport);
        const importModal = document.getElementById('runner-dataset-import-modal');
        if (importModal) {
            importModal.addEventListener('click', function (e) {
                if (e.target === importModal) closeImportModal();
            });
        }
        const scenarioSave = document.getElementById('runner-dataset-scenario-save');
        if (scenarioSave) scenarioSave.addEventListener('click', submitScenario);
        const scenarioCancel = document.getElementById('runner-dataset-scenario-cancel');
        if (scenarioCancel) scenarioCancel.addEventListener('click', closeScenarioPanel);
        hubListenersBound = true;
    }

    function getConfigId() {
        const raw = new URLSearchParams(window.location.search).get('config_id');
        return raw ? raw.trim() : null;
    }

    async function loadPackagePicker() {
        const configId = getConfigId();
        const select = document.getElementById('package-runner-dataset-select');
        const assignBtn = document.getElementById('package-runner-dataset-assign');
        const currentEl = document.getElementById('package-runner-dataset-current');
        const helpEl = document.getElementById('package-runner-dataset-help');
        if (!configId || !select) return;
        select.innerHTML = '<option value="">Loading compatible datasets…</option>';
        if (assignBtn) assignBtn.disabled = true;
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(configId) + '/runner-datasets',
                { credentials: 'same-origin' }
            );
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Failed to load datasets'));
            const required = data.required_events || [];
            const assignedId = data.runners_dataset_id || '';
            const dataset = data.dataset;
            const compatible = data.compatible_datasets || [];
            packagePickerState = {
                compatible: compatible,
                assigned: dataset && !dataset.missing ? dataset : null,
                required: required,
            };
            if (currentEl) {
                if (dataset && !dataset.missing) {
                    currentEl.textContent =
                        'Assigned: ' + (dataset.label || assignedId) +
                        ' (' + ((dataset.events || []).join(', ') || 'files') + ').';
                } else if (assignedId) {
                    currentEl.textContent =
                        'Assigned dataset ' + assignedId + ' is missing from the library. Package-local CSVs are unchanged.';
                } else {
                    currentEl.textContent =
                        'No dataset assigned. Analysis will use package-local *_runners.csv files if they are already present.';
                }
            }
            if (helpEl) {
                helpEl.textContent = required.length
                    ? 'This package requires: ' + required.join(', ') + '. Only datasets that include all of those events are listed.'
                    : 'This package has no events, so a dataset cannot be assigned.';
            }
            select.innerHTML = '';
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = compatible.length
                ? 'Select a compatible dataset…'
                : 'No compatible datasets';
            select.appendChild(placeholder);
            compatible.forEach(function (row) {
                const opt = document.createElement('option');
                opt.value = row.dataset_id;
                opt.textContent = (row.label || row.dataset_id) + ' (' + ((row.events || []).join(', ') || '') + ')';
                if (row.dataset_id === assignedId) opt.selected = true;
                select.appendChild(opt);
            });
            if (assignBtn) assignBtn.disabled = !select.value;
            await showSelectedPackageDatasetStats();
        } catch (err) {
            select.innerHTML = '<option value="">' + escapeHtml(err.message || String(err)) + '</option>';
            if (currentEl) currentEl.textContent = '';
            hidePackageDatasetMetrics();
        }
    }

    async function assignPackageDataset() {
        const configId = getConfigId();
        const select = document.getElementById('package-runner-dataset-select');
        const assignBtn = document.getElementById('package-runner-dataset-assign');
        const datasetId = select && select.value ? select.value.trim() : '';
        if (!configId || !datasetId) return;
        if (assignBtn) assignBtn.disabled = true;
        setStatus(document.getElementById('package-runner-dataset-status'), 'Assigning…', false);
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(configId) + '/runner-dataset',
                {
                    method: 'PUT',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dataset_id: datasetId }),
                }
            );
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Assignment failed'));
            setStatus(
                document.getElementById('package-runner-dataset-status'),
                'Assigned ' + ((data.dataset && data.dataset.label) || datasetId) +
                    '. Copied ' + ((data.copied_files || []).join(', ') || 'files') + '.',
                false
            );
            await loadPackagePicker();
            if (window.SavedCoursesPanel && window.SavedCoursesPanel.refreshReadiness) {
                window.SavedCoursesPanel.refreshReadiness();
            }
        } catch (err) {
            setStatus(
                document.getElementById('package-runner-dataset-status'),
                err.message || String(err),
                true
            );
            if (assignBtn) assignBtn.disabled = !(select && select.value);
        }
    }

    function bindPackageListeners() {
        if (packageListenersBound) return;
        const select = document.getElementById('package-runner-dataset-select');
        const assignBtn = document.getElementById('package-runner-dataset-assign');
        if (select) {
            select.addEventListener('change', function () {
                if (assignBtn) assignBtn.disabled = !select.value;
                setStatus(document.getElementById('package-runner-dataset-status'), '', false);
                showSelectedPackageDatasetStats();
            });
        }
        if (assignBtn) assignBtn.addEventListener('click', assignPackageDataset);
        packageListenersBound = true;
    }

    window.runnerDatasets = {
        loadHub: function () {
            bindHubListeners();
            return loadHubDatasets();
        },
        loadPackagePicker: function () {
            bindPackageListeners();
            return loadPackagePicker();
        },
    };
})();
