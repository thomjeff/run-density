/**
 * Race-day Execute clock + playbook (Issue #830 v1).
 */
(function () {
    let snapshot = null;
    let tickTimer = null;
    let previewSec = null;

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function pad2(n) {
        return String(n).padStart(2, '0');
    }

    function formatHms(sec) {
        if (sec == null || isNaN(sec)) return '—';
        sec = Math.max(0, Math.floor(sec));
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = sec % 60;
        return pad2(h) + ':' + pad2(m) + ':' + pad2(s);
    }

    function wallSec() {
        const d = new Date();
        return d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds();
    }

    function parseTimeInput(value) {
        const text = String(value || '').trim();
        if (!text) return null;
        const parts = text.split(':');
        if (parts.length < 2) return null;
        const h = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const s = parts.length > 2 ? parseInt(parts[2], 10) : 0;
        if (isNaN(h) || isNaN(m)) return null;
        return h * 3600 + m * 60 + (isNaN(s) ? 0 : s);
    }

    function currentSec() {
        if (previewSec != null) return previewSec;
        return wallSec();
    }

    function resolveRunId() {
        const params = new URLSearchParams(window.location.search);
        return (
            (params.get('run_id') || '').trim() ||
            (window.runflowDay && window.runflowDay.run_id) ||
            localStorage.getItem('selected_run_id') ||
            ''
        ).trim();
    }

    function resolveDay() {
        const params = new URLSearchParams(window.location.search);
        return (
            (params.get('day') || '').trim() ||
            (window.runflowDay && window.runflowDay.selected) ||
            localStorage.getItem('selected_day') ||
            ''
        ).trim();
    }

    function statusFor(entry, now) {
        const reopen = entry.reopen_at_sec;
        if (reopen == null || now == null) return 'unknown';
        return now >= reopen ? 'open' : 'closed';
    }

    function renderClock() {
        const now = currentSec();
        const clockEl = document.getElementById('execute-clock');
        const metaEl = document.getElementById('execute-clock-meta');
        if (clockEl) clockEl.textContent = formatHms(now);
        if (!metaEl) return;
        const mode = previewSec != null ? 'Preview' : 'Wall clock';
        const win = snapshot && snapshot.window;
        let extra = mode;
        if (win && win.start_hhmmss) {
            extra += ' · guns ' + win.start_hhmmss;
            if (win.end_hhmmss) extra += ' → last reopen ' + win.end_hhmmss;
        }
        metaEl.textContent = extra;
    }

    function renderGuns() {
        const el = document.getElementById('execute-guns');
        if (!el) return;
        const guns = (snapshot && snapshot.guns) || [];
        if (!guns.length) {
            el.innerHTML = '';
            return;
        }
        el.innerHTML = guns
            .map(function (g) {
                return (
                    '<span class="execute-gun"><strong>' +
                    escapeHtml(g.event || '') +
                    '</strong> gun ' +
                    escapeHtml(g.start_hhmmss || '') +
                    '</span>'
                );
            })
            .join('');
    }

    function renderPlaybook() {
        const tbody = document.getElementById('execute-playbook-tbody');
        const empty = document.getElementById('execute-playbook-empty');
        if (!tbody) return;
        const entries = (snapshot && snapshot.entries) || [];
        const now = currentSec();
        if (!entries.length) {
            tbody.innerHTML = '';
            if (empty) empty.style.display = 'block';
            return;
        }
        if (empty) empty.style.display = 'none';
        let nextId = null;
        entries.forEach(function (e) {
            if (!nextId && statusFor(e, now) === 'closed') nextId = e.rule_id;
        });
        tbody.innerHTML = entries
            .map(function (e) {
                const status = statusFor(e, now);
                const label =
                    status === 'open' ? 'May reopen' : status === 'closed' ? 'Closed' : '—';
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
                const rowClass =
                    'execute-row-' +
                    status +
                    (e.rule_id === nextId ? ' execute-row-next' : '');
                return (
                    '<tr class="' +
                    rowClass +
                    '"><td class="execute-status-' +
                    status +
                    '">' +
                    escapeHtml(label) +
                    '</td><td>' +
                    escapeHtml(e.reopen_at || '—') +
                    '</td><td>' +
                    escapeHtml((e.blocked && (e.blocked.label || e.blocked.id)) || '') +
                    '</td><td>' +
                    until +
                    '</td><td style="font-size:0.85rem;">' +
                    escapeHtml(e.explanation || '') +
                    '</td></tr>'
                );
            })
            .join('');
    }

    function paint() {
        renderClock();
        renderPlaybook();
    }

    async function loadSnapshot() {
        const runId = resolveRunId();
        const clockEl = document.getElementById('execute-clock');
        if (!runId) {
            snapshot = null;
            if (clockEl) clockEl.textContent = '—:—:—';
            const meta = document.getElementById('execute-clock-meta');
            if (meta) meta.textContent = 'Select a run to load guns and the playbook.';
            renderGuns();
            renderPlaybook();
            return;
        }
        let url = '/api/execute/playbook?run_id=' + encodeURIComponent(runId);
        const day = resolveDay();
        if (day) url += '&day=' + encodeURIComponent(day);
        const res = await fetch(url, { credentials: 'same-origin' });
        const data = await res.json().catch(function () {
            return {};
        });
        if (!res.ok) {
            snapshot = { entries: [], guns: [], window: {} };
            const meta = document.getElementById('execute-clock-meta');
            if (meta) meta.textContent = String(data.detail || 'Could not load playbook');
            renderGuns();
            paint();
            return;
        }
        snapshot = data;
        renderGuns();
        paint();
    }

    function jumpToFirstGun() {
        const guns = (snapshot && snapshot.guns) || [];
        if (!guns.length) return;
        const sec = guns[0].start_sec;
        previewSec = sec;
        const inp = document.getElementById('execute-preview-time');
        if (inp) inp.value = formatHms(sec).slice(0, 8);
        paint();
    }

    function bind() {
        const wall = document.getElementById('execute-use-wall');
        if (wall) {
            wall.addEventListener('click', function () {
                previewSec = null;
                const inp = document.getElementById('execute-preview-time');
                if (inp) inp.value = '';
                paint();
            });
        }
        const jump = document.getElementById('execute-jump-gun');
        if (jump) jump.addEventListener('click', jumpToFirstGun);
        const inp = document.getElementById('execute-preview-time');
        if (inp) {
            inp.addEventListener('change', function () {
                previewSec = parseTimeInput(inp.value);
                paint();
            });
            inp.addEventListener('input', function () {
                previewSec = parseTimeInput(inp.value);
                paint();
            });
        }
        tickTimer = setInterval(paint, 1000);
        window.addEventListener('runflow:context-ready', function () {
            loadSnapshot().catch(function () {
                /* keep last snapshot */
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        bind();
        loadSnapshot().catch(function (err) {
            const meta = document.getElementById('execute-clock-meta');
            if (meta) meta.textContent = err.message || String(err);
        });
    });
})();
