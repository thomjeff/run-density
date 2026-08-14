/**
 * Package clearance / dependency authoring (Issue #832).
 */
(function () {
    let loadedConfigId = null;
    let dirty = false;
    let rules = [];
    let locations = [];
    let initialized = false;
    let editingIndex = null;
    let draftUntil = [];
    let untilPickerSelected = {};

    function getConfigId() {
        const params = new URLSearchParams(window.location.search);
        const raw = params.get('config_id');
        return raw ? raw.trim() : null;
    }

    function setStatus(text, isError) {
        const el = document.getElementById('clearance-status');
        if (!el) return;
        el.textContent = text || '';
        el.style.color = isError ? '#c0392b' : '';
    }

    function markDirty() {
        dirty = true;
        setStatus('Unsaved changes');
    }

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function locId(s) {
        if (!s) return '';
        return String(s.id || s.loc_id || '').trim();
    }

    function findLoc(id) {
        const want = String(id || '');
        for (let i = 0; i < locations.length; i++) {
            if (String(locations[i].id) === want) return locations[i];
        }
        return { id: want, label: want, zone: '' };
    }

    function locLabel(loc) {
        const label = (loc && loc.label) || '';
        const id = locId(loc);
        return label ? id + ' — ' + label : id;
    }

    function zoneLabel(zone) {
        const z = (zone || '').trim();
        return z ? 'Zone ' + z : 'No zone';
    }

    function uniqueZones() {
        const seen = {};
        const out = [];
        locations.forEach(function (loc) {
            const z = (loc.zone || '').trim();
            if (seen[z]) return;
            seen[z] = true;
            out.push(z);
        });
        return out;
    }

    function locationsInZone(zoneFilter) {
        if (!zoneFilter || zoneFilter === '*') return locations.slice();
        return locations.filter(function (loc) {
            return (loc.zone || '').trim() === zoneFilter;
        });
    }

    function untilOrdered(preferredZone) {
        const pref = (preferredZone || '').trim();
        const copy = locations.slice();
        copy.sort(function (a, b) {
            const az = (a.zone || '').trim();
            const bz = (b.zone || '').trim();
            const aPref = pref && az === pref ? 0 : 1;
            const bPref = pref && bz === pref ? 0 : 1;
            if (aPref !== bPref) return aPref - bPref;
            return 0;
        });
        return copy;
    }

    function newRuleId() {
        return 'clr_' + Math.random().toString(36).slice(2, 10);
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

    function fillZoneSelect(selectEl, selectedZone, includeAll) {
        if (!selectEl) return;
        const zones = uniqueZones();
        const parts = [];
        if (includeAll) {
            parts.push('<option value="*">All zones</option>');
        }
        zones.forEach(function (z) {
            const sel = z === selectedZone ? ' selected' : '';
            parts.push(
                '<option value="' +
                    escapeHtml(z) +
                    '"' +
                    sel +
                    '>' +
                    escapeHtml(zoneLabel(z)) +
                    '</option>'
            );
        });
        selectEl.innerHTML = parts.join('');
    }

    function fillBlockedSelect(selectedId, zoneFilter) {
        const sel = document.getElementById('clearance-rule-blocked');
        if (!sel) return;
        const rows = locationsInZone(zoneFilter);
        const grouped = {};
        const zoneOrder = [];
        rows.forEach(function (loc) {
            const z = (loc.zone || '').trim();
            if (!grouped[z]) {
                grouped[z] = [];
                zoneOrder.push(z);
            }
            grouped[z].push(loc);
        });
        const parts = [];
        zoneOrder.forEach(function (z) {
            parts.push('<optgroup label="' + escapeHtml(zoneLabel(z)) + '">');
            grouped[z].forEach(function (loc) {
                const id = locId(loc);
                const isSel = id === String(selectedId || '') ? ' selected' : '';
                parts.push(
                    '<option value="' +
                        escapeHtml(id) +
                        '"' +
                        isSel +
                        '>' +
                        escapeHtml(locLabel(loc)) +
                        '</option>'
                );
            });
            parts.push('</optgroup>');
        });
        sel.innerHTML = parts.join('');
        if (selectedId && sel.value !== String(selectedId) && !zoneFilter) {
            sel.insertAdjacentHTML(
                'afterbegin',
                '<option value="' +
                    escapeHtml(String(selectedId)) +
                    '" selected>' +
                    escapeHtml(locLabel(findLoc(selectedId))) +
                    '</option>'
            );
        }
    }

    function untilSummaryHtml(until) {
        const list = until || [];
        if (!list.length) return 'None selected';
        return list
            .map(function (u) {
                return locLabel(findLoc(u.id));
            })
            .join(', ');
    }

    function renderUntilSummary() {
        const el = document.getElementById('clearance-rule-until-summary');
        if (el) el.textContent = untilSummaryHtml(draftUntil);
    }

    function renderUntilPicker() {
        const list = document.getElementById('clearance-until-list');
        const searchEl = document.getElementById('clearance-until-search');
        if (!list) return;
        const q = ((searchEl && searchEl.value) || '').trim().toLowerCase();
        const blockedSel = document.getElementById('clearance-rule-blocked');
        const blockedId = blockedSel ? blockedSel.value : '';
        const preferredZone = (findLoc(blockedId).zone || '').trim();
        const ordered = untilOrdered(preferredZone);
        let html = '';
        let lastGroup = null;
        ordered.forEach(function (loc) {
            const id = locId(loc);
            if (id === blockedId) return;
            const hay = (locLabel(loc) + ' ' + (loc.zone || '')).toLowerCase();
            if (q && hay.indexOf(q) === -1) return;
            const z = (loc.zone || '').trim();
            const group = preferredZone && z === preferredZone ? 'same-zone' : z;
            if (group !== lastGroup) {
                lastGroup = group;
                const heading =
                    preferredZone && z === preferredZone
                        ? 'This zone (' + zoneLabel(z) + ')'
                        : zoneLabel(z);
                html += '<div class="clearance-until-group">' + escapeHtml(heading) + '</div>';
            }
            const checked = untilPickerSelected[id] ? ' checked' : '';
            html +=
                '<label class="clearance-until-option"><input type="checkbox" value="' +
                escapeHtml(id) +
                '"' +
                checked +
                ' /><span>' +
                escapeHtml(locLabel(loc)) +
                '</span></label>';
        });
        list.innerHTML = html || '<div class="placeholder" style="padding:0.75rem;">No matching locations.</div>';
        list.querySelectorAll('input[type="checkbox"]').forEach(function (box) {
            box.addEventListener('change', function () {
                if (box.checked) untilPickerSelected[box.value] = true;
                else delete untilPickerSelected[box.value];
            });
        });
    }

    function openUntilModal() {
        untilPickerSelected = {};
        (draftUntil || []).forEach(function (u) {
            if (u && u.id) untilPickerSelected[String(u.id)] = true;
        });
        const searchEl = document.getElementById('clearance-until-search');
        if (searchEl) searchEl.value = '';
        renderUntilPicker();
        showModal(document.getElementById('clearance-until-modal'));
        if (searchEl) searchEl.focus();
    }

    function applyUntilModal() {
        draftUntil = Object.keys(untilPickerSelected)
            .filter(function (id) {
                return untilPickerSelected[id];
            })
            .map(function (id) {
                return { kind: 'location', id: id };
            });
        renderUntilSummary();
        hideModal(document.getElementById('clearance-until-modal'));
    }

    function openRuleModal(index) {
        editingIndex = index;
        const title = document.getElementById('clearance-rule-modal-title');
        const isNew = index == null || index < 0;
        if (title) title.textContent = isNew ? 'Add rule' : 'Edit rule';
        const rule = isNew
            ? { blocked: locations[0] ? { kind: 'location', id: locations[0].id } : null, until: [], note: '' }
            : rules[index];
        const blockedId = rule && rule.blocked ? rule.blocked.id : '';
        const zone = (findLoc(blockedId).zone || '').trim();
        fillZoneSelect(document.getElementById('clearance-rule-zone'), isNew ? '*' : zone, true);
        const zoneSel = document.getElementById('clearance-rule-zone');
        if (zoneSel) zoneSel.value = isNew ? '*' : zone;
        fillBlockedSelect(blockedId, isNew ? '*' : zone);
        draftUntil = ((rule && rule.until) || []).map(function (u) {
            return { kind: 'location', id: String(u.id) };
        });
        const noteEl = document.getElementById('clearance-rule-note');
        if (noteEl) noteEl.value = (rule && rule.note) || '';
        renderUntilSummary();
        showModal(document.getElementById('clearance-rule-modal'));
    }

    function applyRuleModal() {
        const blockedSel = document.getElementById('clearance-rule-blocked');
        const noteEl = document.getElementById('clearance-rule-note');
        const blockedId = blockedSel && blockedSel.value;
        if (!blockedId) {
            window.alert('Choose a blocked location.');
            return;
        }
        if (!draftUntil.length) {
            window.alert('Choose at least one until location.');
            return;
        }
        if (draftUntil.some(function (u) { return String(u.id) === String(blockedId); })) {
            window.alert('A location cannot wait on itself.');
            return;
        }
        const next = {
            id: editingIndex == null || editingIndex < 0 ? newRuleId() : rules[editingIndex].id,
            blocked: { kind: 'location', id: String(blockedId) },
            until: draftUntil.slice(),
            note: ((noteEl && noteEl.value) || '').trim(),
        };
        if (editingIndex == null || editingIndex < 0) rules.push(next);
        else rules[editingIndex] = next;
        hideModal(document.getElementById('clearance-rule-modal'));
        markDirty();
        renderRules();
    }

    function renderRules() {
        const tbody = document.getElementById('clearance-rules-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (!rules.length) {
            tbody.innerHTML =
                '<tr><td colspan="3" class="placeholder">No rules yet. Add a pair or AND group.</td></tr>';
            return;
        }
        const ta = window.TableActions;
        rules.forEach(function (rule, i) {
            const tr = document.createElement('tr');
            tr.dataset.ruleIndex = String(i);
            tr.title = 'Click to edit';
            const blocked = findLoc(rule.blocked && rule.blocked.id);
            const untilText = untilSummaryHtml(rule.until);
            const blockedTd = document.createElement('td');
            blockedTd.textContent = locLabel(blocked);
            const untilTd = document.createElement('td');
            untilTd.textContent = untilText;
            const actionsTd = document.createElement('td');
            actionsTd.className = 'course-map-action-cell';
            if (ta) {
                actionsTd.appendChild(
                    ta.createIconButton('edit', 'Edit rule', function (ev) {
                        ev.stopPropagation();
                        openRuleModal(i);
                    })
                );
                actionsTd.appendChild(
                    ta.createIconButton('delete', 'Delete rule', function (ev) {
                        ev.stopPropagation();
                        deleteRule(i);
                    })
                );
            }
            tr.appendChild(blockedTd);
            tr.appendChild(untilTd);
            tr.appendChild(actionsTd);
            tr.addEventListener('click', function () {
                openRuleModal(i);
            });
            tbody.appendChild(tr);
        });
    }

    function deleteRule(index) {
        const ta = window.TableActions;
        if (ta && ta.doubleConfirmDelete) {
            if (
                !ta.doubleConfirmDelete({
                    subject: 'this clearance rule',
                    detail: 'It stays removed until you click Save clearance (or discard by leaving).',
                })
            ) {
                return;
            }
        } else if (!window.confirm('Delete this clearance rule?')) {
            return;
        }
        rules.splice(index, 1);
        markDirty();
        renderRules();
    }

    function payload() {
        return {
            version: 1,
            clear_when: 'last_runner',
            assets: [],
            rules: rules.map(function (r) {
                const row = {
                    id: r.id || newRuleId(),
                    blocked: { kind: 'location', id: String(r.blocked.id) },
                    until: (r.until || []).map(function (u) {
                        return { kind: 'location', id: String(u.id) };
                    }),
                    clear_when: 'last_runner',
                };
                if (r.note) row.note = r.note;
                return row;
            }),
        };
    }

    function renderPlaybook(data) {
        const tbody = document.getElementById('clearance-playbook-tbody');
        const empty = document.getElementById('clearance-playbook-empty');
        if (!tbody) return;
        const entries = (data && data.entries) || [];
        if (!entries.length) {
            tbody.innerHTML = '';
            if (empty) empty.style.display = 'block';
            return;
        }
        if (empty) empty.style.display = 'none';
        tbody.innerHTML = entries
            .map(function (e) {
                const until = (e.until || [])
                    .map(function (u) {
                        return (
                            escapeHtml(u.label || u.id) +
                            ' (' +
                            escapeHtml(u.clear_time || '—') +
                            ')'
                        );
                    })
                    .join(' AND ');
                return (
                    '<tr><td>' +
                    escapeHtml(e.reopen_at || '—') +
                    '</td><td>' +
                    escapeHtml((e.blocked && e.blocked.label) || '') +
                    '</td><td>' +
                    until +
                    '</td><td style="font-size:0.85rem;">' +
                    escapeHtml(e.explanation || '') +
                    (e.note ? '<div class="text-secondary">' + escapeHtml(e.note) + '</div>' : '') +
                    '</td></tr>'
                );
            })
            .join('');
    }

    async function loadDoc(configId) {
        const [clrRes, subRes] = await Promise.all([
            fetch('/api/config/packages/' + encodeURIComponent(configId) + '/clearance'),
            fetch('/api/config/packages/' + encodeURIComponent(configId) + '/clearance/subjects'),
        ]);
        const clr = await clrRes.json();
        const sub = await subRes.json();
        if (!clrRes.ok) throw new Error(clr.detail || 'Failed to load clearance');
        if (!subRes.ok) throw new Error(sub.detail || 'Failed to load subjects');
        rules = Array.isArray(clr.rules) ? clr.rules.slice() : [];
        locations = Array.isArray(sub.locations) ? sub.locations : [];
        dirty = false;
        loadedConfigId = configId;
        renderRules();
        setStatus(clr.updated ? 'Saved ' + clr.updated : 'No rules saved yet');
        await fillRunSelect();
        await preview();
    }

    async function save() {
        const configId = getConfigId();
        if (!configId) return;
        setStatus('Saving…');
        const res = await fetch(
            '/api/config/packages/' + encodeURIComponent(configId) + '/clearance',
            {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload()),
            }
        );
        const data = await res.json().catch(function () {
            return {};
        });
        if (!res.ok) {
            const detail = data.detail || data.message || res.statusText;
            setStatus(String(detail), true);
            window.alert('Could not save clearance: ' + detail);
            return;
        }
        rules = Array.isArray(data.rules) ? data.rules.slice() : rules;
        dirty = false;
        setStatus('Saved');
        renderRules();
        await preview();
    }

    function shortRunId(runId) {
        const id = String(runId || '');
        return id.length > 10 ? id.slice(0, 8) + '…' : id;
    }

    function packageIdFromDataDir(dataDir) {
        if (!dataDir) return '';
        const normalized = String(dataDir).replace(/\\/g, '/').replace(/\/+$/, '');
        const marker = '/config/';
        const idx = normalized.lastIndexOf(marker);
        if (idx < 0) return '';
        return (normalized.slice(idx + marker.length).split('/')[0] || '').trim();
    }

    function runOptionLabel(run) {
        const id = run.run_id || '';
        const name = (run.description || '').trim() || 'Analysis';
        return name + '  ID: ' + shortRunId(id);
    }

    async function fillRunSelect() {
        const sel = document.getElementById('clearance-preview-run');
        const pkgId = getConfigId();
        if (!sel || !pkgId) return;
        sel.innerHTML = '<option value="">Loading runs…</option>';
        try {
            const listRes = await fetch('/api/runs/list', { credentials: 'same-origin' });
            const listData = await listRes.json().catch(function () {
                return {};
            });
            const runs = Array.isArray(listData.runs) ? listData.runs : [];
            const candidates = runs.slice(0, 20);
            const matchedIds = {};
            await Promise.all(
                candidates.map(function (run) {
                    return fetch('/api/analysis/' + encodeURIComponent(run.run_id) + '/config', {
                        credentials: 'same-origin',
                    })
                        .then(function (r) {
                            return r.ok ? r.json() : null;
                        })
                        .then(function (cfg) {
                            if (packageIdFromDataDir(cfg && cfg.data_dir) === pkgId) {
                                matchedIds[run.run_id] = true;
                            }
                        })
                        .catch(function () {
                            return null;
                        });
                })
            );
            const packageRuns = runs.filter(function (run) {
                return matchedIds[run.run_id];
            });
            const chosen = packageRuns.length ? packageRuns : runs.slice(0, 15);
            if (!chosen.length) {
                sel.innerHTML = '<option value="">No analysis runs yet</option>';
                return;
            }
            sel.innerHTML = chosen
                .map(function (run, i) {
                    const selected = i === 0 ? ' selected' : '';
                    return (
                        '<option value="' +
                        escapeHtml(run.run_id) +
                        '"' +
                        selected +
                        '>' +
                        escapeHtml(runOptionLabel(run)) +
                        '</option>'
                    );
                })
                .join('');
        } catch (err) {
            sel.innerHTML = '<option value="">Could not load runs</option>';
        }
    }

    async function preview() {
        const configId = getConfigId();
        if (!configId) return;
        const runEl = document.getElementById('clearance-preview-run');
        const runId = runEl && runEl.value.trim();
        let url = '/api/config/packages/' + encodeURIComponent(configId) + '/clearance/playbook';
        if (runId) url += '?run_id=' + encodeURIComponent(runId);
        const res = await fetch(url);
        const data = await res.json().catch(function () {
            return {};
        });
        if (!res.ok) {
            setStatus(String(data.detail || 'Preview failed'), true);
            return;
        }
        renderPlaybook(data);
    }

    function hoistModals() {
        ['clearance-rule-modal', 'clearance-until-modal'].forEach(function (id) {
            const el = document.getElementById(id);
            if (el && el.parentElement !== document.body) {
                document.body.appendChild(el);
            }
        });
    }

    function bindOnce() {
        if (initialized) return;
        initialized = true;
        hoistModals();

        const addRule = document.getElementById('clearance-btn-add-rule');
        if (addRule) {
            addRule.addEventListener('click', function () {
                if (!locations.length) {
                    window.alert('Build race exports so this package has locations first.');
                    return;
                }
                openRuleModal(-1);
            });
        }
        const saveBtn = document.getElementById('clearance-btn-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', function () {
                save().catch(function (err) {
                    setStatus(err.message || String(err), true);
                });
            });
        }
        const previewBtn = document.getElementById('clearance-btn-preview');
        if (previewBtn) {
            previewBtn.addEventListener('click', function () {
                preview().catch(function (err) {
                    setStatus(err.message || String(err), true);
                });
            });
        }
        const runSel = document.getElementById('clearance-preview-run');
        if (runSel) {
            runSel.addEventListener('change', function () {
                preview().catch(function (err) {
                    setStatus(err.message || String(err), true);
                });
            });
        }

        const zoneSel = document.getElementById('clearance-rule-zone');
        if (zoneSel) {
            zoneSel.addEventListener('change', function () {
                const blockedSel = document.getElementById('clearance-rule-blocked');
                const current = blockedSel ? blockedSel.value : '';
                fillBlockedSelect(current, zoneSel.value);
            });
        }
        const chooseUntil = document.getElementById('clearance-btn-choose-until');
        if (chooseUntil) chooseUntil.addEventListener('click', openUntilModal);
        const searchEl = document.getElementById('clearance-until-search');
        if (searchEl) searchEl.addEventListener('input', renderUntilPicker);

        [
            ['clearance-rule-modal-close', 'clearance-rule-modal'],
            ['clearance-rule-modal-cancel', 'clearance-rule-modal'],
            ['clearance-rule-modal-backdrop', 'clearance-rule-modal'],
            ['clearance-until-modal-close', 'clearance-until-modal'],
            ['clearance-until-modal-cancel', 'clearance-until-modal'],
            ['clearance-until-modal-backdrop', 'clearance-until-modal'],
        ].forEach(function (pair) {
            const btn = document.getElementById(pair[0]);
            if (btn) {
                btn.addEventListener('click', function () {
                    hideModal(document.getElementById(pair[1]));
                });
            }
        });
        const applyRule = document.getElementById('clearance-rule-modal-apply');
        if (applyRule) applyRule.addEventListener('click', applyRuleModal);
        const applyUntil = document.getElementById('clearance-until-modal-apply');
        if (applyUntil) applyUntil.addEventListener('click', applyUntilModal);
    }

    async function initClearanceAuthoring() {
        bindOnce();
        const configId = getConfigId();
        if (!configId) return;
        if (configId === loadedConfigId) return;
        try {
            await loadDoc(configId);
        } catch (err) {
            setStatus(err.message || String(err), true);
        }
    }

    window.initClearanceAuthoring = initClearanceAuthoring;
    window.clearanceAuthoring = {
        isDirty: function () {
            return dirty;
        },
    };
})();
