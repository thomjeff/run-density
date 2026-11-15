/**
 * Package clearance rules authoring + static playbook preview (Issue #832).
 */
(function () {
    'use strict';

    var state = {
        configId: null,
        assets: [],
        rules: [],
        dirty: false,
    };

    function configId() {
        if (window.CONFIG_PACKAGE_ID) return String(window.CONFIG_PACKAGE_ID).trim();
        var params = new URLSearchParams(window.location.search);
        return (params.get('config_id') || '').trim();
    }

    function apiBase() {
        var cid = state.configId || configId();
        return cid ? '/api/config/packages/' + encodeURIComponent(cid) : '';
    }

    function setStatus(msg, isError) {
        var el = document.getElementById('clearance-status');
        if (!el) return;
        el.textContent = msg || '';
        el.style.color = isError ? '#c0392b' : '#7f8c8d';
    }

    function setPlaybookStatus(msg, isError) {
        var el = document.getElementById('clearance-playbook-status');
        if (!el) return;
        el.textContent = msg || '';
        el.style.color = isError ? '#c0392b' : '#7f8c8d';
    }

    function renderRules() {
        var tbody = document.getElementById('clearance-rules-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (!state.rules.length) {
            tbody.innerHTML =
                '<tr><td colspan="4" class="placeholder">No rules yet. Add a pair or group (AND).</td></tr>';
            return;
        }
        state.rules.forEach(function (rule, index) {
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td><input data-field="blocked" data-i="' +
                index +
                '" value="' +
                esc(rule.blocked) +
                '" class="config-package-input" style="width:6rem;" /></td>' +
                '<td><input data-field="until" data-i="' +
                index +
                '" value="' +
                esc((rule.until || []).join(', ')) +
                '" class="config-package-input" style="min-width:12rem;" placeholder="12, 16" /></td>' +
                '<td>last_runner</td>' +
                '<td class="course-map-action-cell"><button type="button" class="course-btn" data-remove-rule="' +
                index +
                '">Remove</button></td>';
            tbody.appendChild(tr);
        });
    }

    function renderAssets() {
        var tbody = document.getElementById('clearance-assets-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (!state.assets.length) {
            tbody.innerHTML =
                '<tr><td colspan="4" class="placeholder">None yet</td></tr>';
            return;
        }
        state.assets.forEach(function (asset, index) {
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td><input data-asset="asset_id" data-i="' +
                index +
                '" value="' +
                esc(asset.asset_id) +
                '" class="config-package-input" style="width:8rem;" /></td>' +
                '<td><input data-asset="label" data-i="' +
                index +
                '" value="' +
                esc(asset.label || '') +
                '" class="config-package-input" style="min-width:10rem;" /></td>' +
                '<td><input data-asset="loc_id" data-i="' +
                index +
                '" value="' +
                esc(asset.loc_id || '') +
                '" class="config-package-input" style="width:5rem;" /></td>' +
                '<td class="course-map-action-cell"><button type="button" class="course-btn" data-remove-asset="' +
                index +
                '">Remove</button></td>';
            tbody.appendChild(tr);
        });
    }

    function esc(s) {
        return String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
    }

    function readFormIntoState() {
        document.querySelectorAll('#clearance-rules-tbody input[data-field]').forEach(function (el) {
            var i = Number(el.getAttribute('data-i'));
            var field = el.getAttribute('data-field');
            if (!state.rules[i]) return;
            if (field === 'until') {
                state.rules[i].until = String(el.value || '')
                    .split(/[,\s]+/)
                    .map(function (p) {
                        return p.trim();
                    })
                    .filter(Boolean);
            } else {
                state.rules[i][field] = String(el.value || '').trim();
            }
        });
        document.querySelectorAll('#clearance-assets-tbody input[data-asset]').forEach(function (el) {
            var i = Number(el.getAttribute('data-i'));
            var field = el.getAttribute('data-asset');
            if (!state.assets[i]) return;
            var val = String(el.value || '').trim();
            if (field === 'loc_id' && !val) {
                delete state.assets[i].loc_id;
            } else {
                state.assets[i][field] = val;
            }
        });
    }

    function load() {
        state.configId = configId();
        if (!apiBase()) {
            setStatus('Open a package to author clearance rules.', true);
            return;
        }
        setStatus('Loading…');
        fetch(apiBase() + '/clearance-rules', { credentials: 'same-origin' })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) throw new Error(data.detail || 'Load failed');
                    return data;
                });
            })
            .then(function (data) {
                state.rules = (data.rules || []).map(function (r) {
                    return {
                        id: r.id,
                        blocked: r.blocked,
                        until: (r.until || []).slice(),
                        clear_when: 'last_runner',
                    };
                });
                state.assets = (data.assets || []).map(function (a) {
                    return {
                        asset_id: a.asset_id,
                        label: a.label || a.asset_id,
                        loc_id: a.loc_id || '',
                    };
                });
                state.dirty = false;
                renderRules();
                renderAssets();
                setStatus(state.rules.length ? state.rules.length + ' rule(s)' : 'No rules yet');
                var dayInput = document.getElementById('clearance-playbook-day');
                if (dayInput && !dayInput.value && window.CONFIG_PACKAGE_EVENT_DAY) {
                    dayInput.value = window.CONFIG_PACKAGE_EVENT_DAY;
                }
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function save() {
        readFormIntoState();
        if (!apiBase()) return;
        setStatus('Saving…');
        var payload = {
            assets: state.assets.map(function (a) {
                var row = { asset_id: a.asset_id, label: a.label || a.asset_id };
                if (a.loc_id) row.loc_id = a.loc_id;
                return row;
            }),
            rules: state.rules.map(function (r, i) {
                return {
                    id: r.id || 'rule-' + (i + 1),
                    blocked: r.blocked,
                    until: r.until,
                    clear_when: 'last_runner',
                };
            }),
        };
        fetch(apiBase() + '/clearance-rules', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) throw new Error(data.detail || 'Save failed');
                    return data;
                });
            })
            .then(function (data) {
                state.rules = data.rules || [];
                state.assets = data.assets || [];
                state.dirty = false;
                renderRules();
                renderAssets();
                setStatus('Saved.');
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function previewPlaybook() {
        if (!apiBase()) return;
        var runId = (document.getElementById('clearance-playbook-run-id') || {}).value || '';
        var day = (document.getElementById('clearance-playbook-day') || {}).value || '';
        var qs =
            '?run_id=' +
            encodeURIComponent(String(runId).trim()) +
            '&day=' +
            encodeURIComponent(String(day).trim());
        setPlaybookStatus('Loading playbook…');
        fetch(apiBase() + '/clearance/playbook' + qs, { credentials: 'same-origin' })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) throw new Error(data.detail || 'Preview failed');
                    return data;
                });
            })
            .then(function (data) {
                var tbody = document.getElementById('clearance-playbook-tbody');
                if (!tbody) return;
                tbody.innerHTML = '';
                var steps = data.steps || [];
                if (!steps.length) {
                    tbody.innerHTML =
                        '<tr><td colspan="4" class="placeholder">' +
                        esc(data.message || 'No steps') +
                        '</td></tr>';
                    setPlaybookStatus(data.message || '');
                    return;
                }
                steps.forEach(function (step) {
                    var blockers = (step.blockers || [])
                        .map(function (b) {
                            return (
                                b.subject +
                                (b.last_runner ? ' @ ' + b.last_runner : ' (no timing)')
                            );
                        })
                        .join('; ');
                    var tr = document.createElement('tr');
                    tr.innerHTML =
                        '<td>' +
                        esc(step.blocked) +
                        '</td><td>' +
                        esc(step.reopen_not_before || '—') +
                        '</td><td>' +
                        esc(blockers) +
                        '</td><td>' +
                        esc(step.explanation || '') +
                        '</td>';
                    tbody.appendChild(tr);
                });
                setPlaybookStatus(
                    (data.report_found ? 'Using Locations report. ' : 'No report found — timings empty. ') +
                        steps.length +
                        ' step(s).'
                );
            })
            .catch(function (err) {
                setPlaybookStatus(err.message || String(err), true);
            });
    }

    function bind() {
        var addRule = document.getElementById('clearance-add-rule');
        if (addRule) {
            addRule.addEventListener('click', function () {
                readFormIntoState();
                state.rules.push({
                    id: 'rule-' + (state.rules.length + 1),
                    blocked: '',
                    until: [],
                    clear_when: 'last_runner',
                });
                state.dirty = true;
                renderRules();
            });
        }
        var addAsset = document.getElementById('clearance-add-asset');
        if (addAsset) {
            addAsset.addEventListener('click', function () {
                readFormIntoState();
                state.assets.push({
                    asset_id: 'asset_' + (state.assets.length + 1),
                    label: '',
                    loc_id: '',
                });
                state.dirty = true;
                renderAssets();
            });
        }
        var saveBtn = document.getElementById('clearance-save');
        if (saveBtn) saveBtn.addEventListener('click', save);
        var previewBtn = document.getElementById('clearance-playbook-load');
        if (previewBtn) previewBtn.addEventListener('click', previewPlaybook);

        var root = document.getElementById('clearance-workspace');
        if (root) {
            root.addEventListener('click', function (ev) {
                var rmRule = ev.target.getAttribute('data-remove-rule');
                if (rmRule != null) {
                    readFormIntoState();
                    state.rules.splice(Number(rmRule), 1);
                    state.dirty = true;
                    renderRules();
                    return;
                }
                var rmAsset = ev.target.getAttribute('data-remove-asset');
                if (rmAsset != null) {
                    readFormIntoState();
                    state.assets.splice(Number(rmAsset), 1);
                    state.dirty = true;
                    renderAssets();
                }
            });
            root.addEventListener('input', function () {
                state.dirty = true;
            });
        }
    }

    window.clearanceAuthoring = {
        load: load,
        isDirty: function () {
            return !!state.dirty;
        },
    };

    document.addEventListener('DOMContentLoaded', bind);
})();
