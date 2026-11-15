/**
 * Org runner datasets — Build hub catalog and Package picker (Issues #879 / #957 / #958).
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
            const day = ('0' + (d.getDate())).slice(-2);
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

    function usedByLabel(dataset) {
        const used = (dataset && dataset.used_by) || [];
        if (!used.length) return '—';
        return used.map(function (u) { return u.label || u.config_id; }).join(', ');
    }

    function lineageLabel(dataset, byId) {
        const sourceId = dataset && dataset.source_dataset_id;
        if (!sourceId) return 'Actuals';
        const src = byId[sourceId];
        const srcName = src ? src.label : sourceId;
        const lineage = dataset.lineage || {};
        const events = lineage.events || {};
        const bits = [];
        Object.keys(events).forEach(function (event) {
            const row = events[event] || {};
            const dN = row.participants_delta;
            const dP50 = row.p50_delta;
            let part = event;
            if (dN != null) {
                part += ' ' + (dN >= 0 ? '+' : '') + dN;
                if (row.participants_delta_pct != null) {
                    part += ' (' + (row.participants_delta_pct * 100).toFixed(0) + '%)';
                }
            }
            if (dP50 != null) {
                part += ' P50 ' + (dP50 >= 0 ? '+' : '') + Number(dP50).toFixed(2);
            }
            bits.push(part);
        });
        return bits.length ? srcName + ' → ' + bits.join('; ') : srcName;
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
    let racerosterEvents = [];
    let racerosterFiles = [];

    async function loadHubDatasets() {
        const tbody = document.getElementById('race-config-runners-tbody');
        if (!tbody) return;
        tbody.innerHTML =
            '<tr><td colspan="7" class="placeholder">Loading runner datasets…</td></tr>';
        try {
            const resp = await fetch('/api/org/runners', { credentials: 'same-origin' });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Failed to load datasets'));
            hubDatasets = data.datasets || [];
            renderHubTable();
        } catch (err) {
            tbody.innerHTML =
                '<tr><td colspan="7" class="placeholder">' +
                escapeHtml(err.message || String(err)) +
                '</td></tr>';
        }
    }

    function renderHubTable() {
        const tbody = document.getElementById('race-config-runners-tbody');
        if (!tbody) return;
        if (!hubDatasets.length) {
            tbody.innerHTML =
                '<tr><td colspan="7" class="placeholder">No runner datasets yet. Import Race Roster or CSV actuals to create the first dataset.</td></tr>';
            return;
        }
        const byId = {};
        hubDatasets.forEach(function (row) {
            byId[row.dataset_id] = row;
        });
        tbody.innerHTML = '';
        hubDatasets.forEach(function (row) {
            const tr = document.createElement('tr');
            if (row.archived) tr.classList.add('is-archived');
            const events = (row.events || []).join(', ') || '—';
            const name = (row.label || row.dataset_id) + (row.archived ? ' (archived)' : '');
            tr.innerHTML =
                '<td>' + escapeHtml(name) + '</td>' +
                '<td>' + escapeHtml(events) + '</td>' +
                '<td>' + escapeHtml(lineageLabel(row, byId)) + '</td>' +
                '<td>' + escapeHtml(participantsLabel(row)) + '</td>' +
                '<td>' + escapeHtml(usedByLabel(row)) + '</td>' +
                '<td>' + escapeHtml(formatSavedOn(row.created)) + '</td>' +
                '<td class="course-map-action-cell"></td>';
            const actions = tr.querySelector('.course-map-action-cell');
            const ta = window.TableActions;
            if (ta && actions) {
                actions.appendChild(ta.createIconButton('copy', 'Create scenario', function (ev) {
                    ev.preventDefault();
                    openScenarioPanel(row);
                }));
                actions.appendChild(ta.createIconButton('edit', 'Edit name / description', function (ev) {
                    ev.preventDefault();
                    openEditModal(row);
                }));
                if (row.archived) {
                    actions.appendChild(ta.createIconButton('restore', 'Restore dataset', function (ev) {
                        ev.preventDefault();
                        archiveDataset(row, false);
                    }));
                } else {
                    actions.appendChild(ta.createIconButton('archive', 'Archive dataset', function (ev) {
                        ev.preventDefault();
                        archiveDataset(row, true);
                    }));
                }
                actions.appendChild(ta.createIconButton('delete', 'Delete dataset', function (ev) {
                    ev.preventDefault();
                    deleteDataset(row);
                }));
            }
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

    function openRaceRosterModal() {
        const modal = document.getElementById('runner-dataset-raceroster-modal');
        const label = document.getElementById('runner-dataset-raceroster-label');
        const desc = document.getElementById('runner-dataset-raceroster-description');
        const files = document.getElementById('runner-dataset-raceroster-files');
        const mapping = document.getElementById('runner-dataset-raceroster-mapping');
        const preview = document.getElementById('runner-dataset-raceroster-preview');
        if (label) label.value = '';
        if (desc) desc.value = '';
        if (files) files.value = '';
        if (mapping) mapping.innerHTML = '';
        if (preview) preview.innerHTML = '';
        racerosterFiles = [];
        racerosterEvents = [];
        const previewBtn = document.getElementById('runner-dataset-raceroster-preview-btn');
        const saveBtn = document.getElementById('runner-dataset-raceroster-save');
        if (previewBtn) previewBtn.disabled = true;
        if (saveBtn) saveBtn.disabled = true;
        setStatus(document.getElementById('runner-dataset-raceroster-status'), '', false);
        if (modal) modal.classList.add('open');
        if (label) label.focus();
    }

    function closeRaceRosterModal() {
        const modal = document.getElementById('runner-dataset-raceroster-modal');
        if (modal) modal.classList.remove('open');
    }

    function collectSheetEventMap() {
        const selects = document.querySelectorAll('#runner-dataset-raceroster-mapping select[data-rr-sheet]');
        const map = {};
        selects.forEach(function (sel) {
            const sheet = sel.getAttribute('data-rr-sheet');
            const event = (sel.value || '').trim();
            if (sheet && event) map[sheet] = event;
        });
        return map;
    }

    function renderSheetMapping(workbooks, events) {
        const host = document.getElementById('runner-dataset-raceroster-mapping');
        if (!host) return;
        racerosterEvents = events || [];
        let html = '';
        (workbooks || []).forEach(function (wb) {
            html += '<p class="card-help" style="margin:0 0 0.35rem 0;font-weight:600;">' +
                escapeHtml(wb.filename || 'Workbook') + '</p>';
            html += '<table class="table-sticky-header" style="width:100%;font-size:0.875rem;margin-bottom:0.75rem;"><thead><tr>';
            html += '<th>Sheet</th><th>Event</th></tr></thead><tbody>';
            (wb.sheets || []).forEach(function (row) {
                const sheet = row.sheet || '';
                const suggested = row.suggested_event || '';
                html += '<tr><td>' + escapeHtml(sheet) + '</td><td>';
                html += '<select data-rr-sheet="' + escapeHtml(sheet) + '" style="min-width:8rem;padding:0.25rem;">';
                html += '<option value="">— skip —</option>';
                racerosterEvents.forEach(function (ev) {
                    const selected = ev.id === suggested ? ' selected' : '';
                    html += '<option value="' + escapeHtml(ev.id) + '"' + selected + '>' +
                        escapeHtml(ev.long_label || ev.label || ev.id) + '</option>';
                });
                html += '</select></td></tr>';
            });
            html += '</tbody></table>';
        });
        host.innerHTML = html || '<p class="card-help">No sheets found.</p>';
        const previewBtn = document.getElementById('runner-dataset-raceroster-preview-btn');
        const saveBtn = document.getElementById('runner-dataset-raceroster-save');
        if (previewBtn) previewBtn.disabled = false;
        if (saveBtn) saveBtn.disabled = false;
    }

    function renderRaceRosterPreview(eventsPreview) {
        const host = document.getElementById('runner-dataset-raceroster-preview');
        if (!host) return;
        const events = Object.keys(eventsPreview || {});
        if (!events.length) {
            host.innerHTML = '<p class="card-help">No mapped events to preview.</p>';
            return;
        }
        let html = '<table class="table-sticky-header" style="width:100%;font-size:0.8rem;"><thead><tr>';
        html += '<th>Event</th><th>Runners</th><th>Skipped</th><th>P00</th><th>P50</th><th>P100</th><th>Offset</th></tr></thead><tbody>';
        events.forEach(function (event) {
            const row = eventsPreview[event] || {};
            html += '<tr><td>' + escapeHtml(event) + '</td>';
            html += '<td>' + escapeHtml(String(row.participants != null ? row.participants : '—')) + '</td>';
            html += '<td>' + escapeHtml(String(row.skipped_no_chip != null ? row.skipped_no_chip : '—')) + '</td>';
            html += '<td>' + escapeHtml(formatPace(row.p00)) + '</td>';
            html += '<td>' + escapeHtml(formatPace(row.p50)) + '</td>';
            html += '<td>' + escapeHtml(formatPace(row.p100)) + '</td>';
            html += '<td>' + escapeHtml(
                (row.start_offset_min != null && row.start_offset_max != null)
                    ? (row.start_offset_min + '–' + row.start_offset_max + 's')
                    : '—'
            ) + '</td></tr>';
        });
        html += '</tbody></table>';
        host.innerHTML = html;
    }

    async function inspectRaceRoster() {
        const filesEl = document.getElementById('runner-dataset-raceroster-files');
        const files = filesEl && filesEl.files ? Array.from(filesEl.files) : [];
        if (!files.length) {
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Select a workbook.', true);
            return;
        }
        racerosterFiles = files;
        const fd = new FormData();
        files.forEach(function (file) {
            fd.append('files', file, file.name);
        });
        setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Reading sheets…', false);
        try {
            const resp = await fetch('/api/org/runners/raceroster/inspect', {
                method: 'POST',
                credentials: 'same-origin',
                body: fd,
            });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Inspect failed'));
            renderSheetMapping(data.workbooks || [], data.events || []);
            const preview = document.getElementById('runner-dataset-raceroster-preview');
            if (preview) preview.innerHTML = '';
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Map sheets to events, then Preview.', false);
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-raceroster-status'),
                err.message || String(err),
                true
            );
        }
    }

    async function previewRaceRoster() {
        const map = collectSheetEventMap();
        if (!Object.keys(map).length) {
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Map at least one sheet to an event.', true);
            return;
        }
        const files = racerosterFiles.length
            ? racerosterFiles
            : (document.getElementById('runner-dataset-raceroster-files') &&
                Array.from(document.getElementById('runner-dataset-raceroster-files').files || []));
        if (!files.length) {
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Select a workbook.', true);
            return;
        }
        const fd = new FormData();
        fd.append('sheet_event_map', JSON.stringify(map));
        files.forEach(function (file) {
            fd.append('files', file, file.name);
        });
        setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Building preview…', false);
        try {
            const resp = await fetch('/api/org/runners/raceroster/preview', {
                method: 'POST',
                credentials: 'same-origin',
                body: fd,
            });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Preview failed'));
            renderRaceRosterPreview(data.events || {});
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Preview ready. Create when it looks right.', false);
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-raceroster-status'),
                err.message || String(err),
                true
            );
        }
    }

    async function submitRaceRoster() {
        const labelEl = document.getElementById('runner-dataset-raceroster-label');
        const descEl = document.getElementById('runner-dataset-raceroster-description');
        const saveBtn = document.getElementById('runner-dataset-raceroster-save');
        const label = labelEl && labelEl.value.trim();
        const map = collectSheetEventMap();
        if (!label) {
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Enter a name.', true);
            return;
        }
        if (!Object.keys(map).length) {
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Map at least one sheet to an event.', true);
            return;
        }
        const files = racerosterFiles.length
            ? racerosterFiles
            : (document.getElementById('runner-dataset-raceroster-files') &&
                Array.from(document.getElementById('runner-dataset-raceroster-files').files || []));
        if (!files.length) {
            setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Select a workbook.', true);
            return;
        }
        const fd = new FormData();
        fd.append('label', label);
        fd.append('description', (descEl && descEl.value.trim()) || '');
        fd.append('sheet_event_map', JSON.stringify(map));
        files.forEach(function (file) {
            fd.append('files', file, file.name);
        });
        if (saveBtn) saveBtn.disabled = true;
        setStatus(document.getElementById('runner-dataset-raceroster-status'), 'Creating dataset…', false);
        try {
            const resp = await fetch('/api/org/runners/raceroster', {
                method: 'POST',
                credentials: 'same-origin',
                body: fd,
            });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Create failed'));
            closeRaceRosterModal();
            await loadHubDatasets();
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-raceroster-status'),
                err.message || String(err),
                true
            );
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    function openEditModal(dataset) {
        const modal = document.getElementById('runner-dataset-edit-modal');
        const idEl = document.getElementById('runner-dataset-edit-id');
        const label = document.getElementById('runner-dataset-edit-label');
        const desc = document.getElementById('runner-dataset-edit-description');
        if (idEl) idEl.value = dataset.dataset_id || '';
        if (label) label.value = dataset.label || '';
        if (desc) desc.value = dataset.description || '';
        setStatus(document.getElementById('runner-dataset-edit-status'), '', false);
        if (modal) modal.classList.add('open');
        if (label) label.focus();
    }

    function closeEditModal() {
        const modal = document.getElementById('runner-dataset-edit-modal');
        if (modal) modal.classList.remove('open');
    }

    async function submitEdit() {
        const idEl = document.getElementById('runner-dataset-edit-id');
        const labelEl = document.getElementById('runner-dataset-edit-label');
        const descEl = document.getElementById('runner-dataset-edit-description');
        const saveBtn = document.getElementById('runner-dataset-edit-save');
        const datasetId = idEl && idEl.value.trim();
        const label = labelEl && labelEl.value.trim();
        if (!datasetId || !label) {
            setStatus(document.getElementById('runner-dataset-edit-status'), 'Name is required.', true);
            return;
        }
        if (saveBtn) saveBtn.disabled = true;
        try {
            const resp = await fetch('/api/org/runners/' + encodeURIComponent(datasetId), {
                method: 'PATCH',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    label: label,
                    description: (descEl && descEl.value.trim()) || '',
                }),
            });
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Save failed'));
            closeEditModal();
            await loadHubDatasets();
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-edit-status'),
                err.message || String(err),
                true
            );
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    async function archiveDataset(dataset, archived) {
        const used = (dataset.used_by || []).map(function (u) { return u.label || u.config_id; });
        if (archived && used.length) {
            window.alert('Cannot archive while packages use this dataset: ' + used.join(', '));
            return;
        }
        try {
            const resp = await fetch(
                '/api/org/runners/' + encodeURIComponent(dataset.dataset_id) + '/archive',
                {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ archived: archived }),
                }
            );
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Archive failed'));
            await loadHubDatasets();
        } catch (err) {
            window.alert(err.message || String(err));
        }
    }

    async function deleteDataset(dataset) {
        const used = (dataset.used_by || []).map(function (u) { return u.label || u.config_id; });
        if (used.length) {
            window.alert('Cannot delete while packages use this dataset: ' + used.join(', '));
            return;
        }
        const ta = window.TableActions;
        if (ta && ta.doubleConfirmDelete) {
            if (!ta.doubleConfirmDelete({
                subject: 'dataset "' + (dataset.label || dataset.dataset_id) + '"',
                detail: 'Runner CSVs will be permanently removed from the library.',
            })) {
                return;
            }
        } else if (!window.confirm('Delete dataset "' + (dataset.label || dataset.dataset_id) + '"?')) {
            return;
        }
        try {
            const resp = await fetch(
                '/api/org/runners/' + encodeURIComponent(dataset.dataset_id),
                { method: 'DELETE', credentials: 'same-origin' }
            );
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Delete failed'));
            await loadHubDatasets();
        } catch (err) {
            window.alert(err.message || String(err));
        }
    }

    function collectScenarioControls() {
        const controlVariables = {};
        const inputs = document.querySelectorAll('#runner-dataset-scenario-controls input[data-rf-chg]');
        inputs.forEach(function (input) {
            const event = input.getAttribute('data-rf-event');
            const key = input.getAttribute('data-rf-chg');
            if (!event || !key) return;
            if (!controlVariables[event]) controlVariables[event] = {};
            controlVariables[event][key] = parsePercentToDecimal(input.value);
        });
        return controlVariables;
    }

    function renderScenarioPreview(preview) {
        const host = document.getElementById('runner-dataset-scenario-preview');
        if (!host) return;
        const events = preview && preview.events ? preview.events : {};
        const keys = Object.keys(events);
        if (!keys.length) {
            host.innerHTML = '';
            return;
        }
        let html = '<p class="card-help" style="margin:0 0 0.35rem 0;">Preview (source → scenario). Nothing written yet.</p>';
        html += '<table class="table-sticky-header" style="width:100%;font-size:0.8rem;"><thead><tr>';
        html += '<th>Event</th><th>Participants</th><th>Δ</th><th>P00</th><th>P50</th><th>P100</th></tr></thead><tbody>';
        keys.forEach(function (event) {
            const row = events[event] || {};
            const src = row.source || {};
            const scn = row.scenario || {};
            const dN = row.participants_delta;
            const dPct = row.participants_delta_pct;
            let deltaText = '—';
            if (dN != null) {
                deltaText = (dN >= 0 ? '+' : '') + dN;
                if (dPct != null) deltaText += ' (' + (dPct * 100).toFixed(0) + '%)';
            }
            html += '<tr><td>' + escapeHtml(event) + '</td>';
            html += '<td>' + escapeHtml(
                (src.participants != null ? src.participants : '—') +
                ' → ' +
                (scn.participants != null ? scn.participants : '—')
            ) + '</td>';
            html += '<td>' + escapeHtml(deltaText) + '</td>';
            html += '<td>' + escapeHtml(formatPace(src.p00) + ' → ' + formatPace(scn.p00)) + '</td>';
            html += '<td>' + escapeHtml(formatPace(src.p50) + ' → ' + formatPace(scn.p50)) + '</td>';
            html += '<td>' + escapeHtml(formatPace(src.p100) + ' → ' + formatPace(scn.p100)) + '</td></tr>';
        });
        html += '</tbody></table>';
        host.innerHTML = html;
    }

    function openScenarioPanel(dataset) {
        scenarioSourceId = dataset.dataset_id;
        const panel = document.getElementById('runner-dataset-scenario-panel');
        const sourceEl = document.getElementById('runner-dataset-scenario-source');
        const labelEl = document.getElementById('runner-dataset-scenario-label');
        const descEl = document.getElementById('runner-dataset-scenario-description');
        const host = document.getElementById('runner-dataset-scenario-controls');
        const previewHost = document.getElementById('runner-dataset-scenario-preview');
        if (previewHost) previewHost.innerHTML = '';
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
                html += '<p class="card-help" style="margin-top:0.5rem;">Percent change vs the source (40 = +40%). Default 0 copies the source distribution into a new dataset id. Use Preview before Create.</p>';
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
        const previewHost = document.getElementById('runner-dataset-scenario-preview');
        if (previewHost) previewHost.innerHTML = '';
    }

    async function previewScenario() {
        if (!scenarioSourceId) return;
        let controlVariables;
        try {
            controlVariables = collectScenarioControls();
        } catch (err) {
            setStatus(document.getElementById('runner-dataset-scenario-status'), err.message || String(err), true);
            return;
        }
        if (!Object.keys(controlVariables).length) {
            setStatus(document.getElementById('runner-dataset-scenario-status'), 'Source has no events.', true);
            return;
        }
        const btn = document.getElementById('runner-dataset-scenario-preview-btn');
        if (btn) btn.disabled = true;
        setStatus(document.getElementById('runner-dataset-scenario-status'), 'Building preview…', false);
        try {
            const resp = await fetch(
                '/api/org/runners/' + encodeURIComponent(scenarioSourceId) + '/scenarios/preview',
                {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ control_variables: controlVariables }),
                }
            );
            const data = await resp.json().catch(function () { return {}; });
            if (!resp.ok) throw new Error(apiError(data, 'Preview failed'));
            renderScenarioPreview(data);
            setStatus(document.getElementById('runner-dataset-scenario-status'), 'Preview ready.', false);
        } catch (err) {
            setStatus(
                document.getElementById('runner-dataset-scenario-status'),
                err.message || String(err),
                true
            );
        } finally {
            if (btn) btn.disabled = false;
        }
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
        let controlVariables;
        try {
            controlVariables = collectScenarioControls();
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
        const rrBtn = document.getElementById('runner-dataset-raceroster-btn');
        if (rrBtn) rrBtn.addEventListener('click', openRaceRosterModal);
        const rrCancel = document.getElementById('runner-dataset-raceroster-cancel');
        if (rrCancel) rrCancel.addEventListener('click', closeRaceRosterModal);
        const rrInspect = document.getElementById('runner-dataset-raceroster-inspect');
        if (rrInspect) rrInspect.addEventListener('click', inspectRaceRoster);
        const rrPreview = document.getElementById('runner-dataset-raceroster-preview-btn');
        if (rrPreview) rrPreview.addEventListener('click', previewRaceRoster);
        const rrSave = document.getElementById('runner-dataset-raceroster-save');
        if (rrSave) rrSave.addEventListener('click', submitRaceRoster);
        const rrModal = document.getElementById('runner-dataset-raceroster-modal');
        if (rrModal) {
            rrModal.addEventListener('click', function (e) {
                if (e.target === rrModal) closeRaceRosterModal();
            });
        }
        const editCancel = document.getElementById('runner-dataset-edit-cancel');
        if (editCancel) editCancel.addEventListener('click', closeEditModal);
        const editSave = document.getElementById('runner-dataset-edit-save');
        if (editSave) editSave.addEventListener('click', submitEdit);
        const editModal = document.getElementById('runner-dataset-edit-modal');
        if (editModal) {
            editModal.addEventListener('click', function (e) {
                if (e.target === editModal) closeEditModal();
            });
        }
        const scenarioPreview = document.getElementById('runner-dataset-scenario-preview-btn');
        if (scenarioPreview) scenarioPreview.addEventListener('click', previewScenario);
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
            const compatible = (data.compatible_datasets || []).filter(function (row) {
                return !row.archived;
            });
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
