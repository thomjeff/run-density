/**
 * Segment library + event recipes UI (config packages).
 * Issue #755 / #769
 */
(function () {
    'use strict';

    var EVENTS = ['full', 'half', '10k'];
    var libraryState = null;
    var orderGrid = {};

    function resolveConfigPackageId() {
        var params = new URLSearchParams(window.location.search);
        var raw = params.get('config_id');
        return raw ? raw.trim() : '';
    }

    function isConfigPackageWorkspace() {
        return !!resolveConfigPackageId() && !!document.getElementById('race-config-workspace');
    }

    function apiBase() {
        return '/api/config/packages/' + encodeURIComponent(resolveConfigPackageId());
    }

    function showCard(visible) {
        var card = document.getElementById('segment-recipes-card');
        if (!card) return;
        card.style.display = visible && isConfigPackageWorkspace() ? 'block' : 'none';
    }

    function formatApiError(res, data) {
        if (data && data.detail) {
            if (typeof data.detail === 'string') return data.detail;
            if (Array.isArray(data.detail)) {
                return data.detail.map(function (d) { return d.msg || JSON.stringify(d); }).join('; ');
            }
        }
        if (res && res.status === 404 && data && data.detail === 'Not Found') {
            return 'Segment library API is unavailable. Restart the app (make stop && make dev) and try again.';
        }
        return (res && res.status ? 'HTTP ' + res.status + ': ' : '') + 'Request failed';
    }

    function setStatus(msg, isError) {
        var el = document.getElementById('segment-recipes-status');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.style.color = isError ? '#c0392b' : '#27ae60';
        el.textContent = msg;
    }

    function renderTotals(lengths) {
        var wrap = document.getElementById('segment-recipes-totals');
        if (!wrap || !lengths) return;
        wrap.style.display = 'block';
        var full = document.getElementById('recipe-total-full');
        var half = document.getElementById('recipe-total-half');
        var ten = document.getElementById('recipe-total-10k');
        if (full) full.textContent = ' Full ' + (lengths.full != null ? lengths.full.toFixed(2) : '—') + ' km';
        if (half) half.textContent = ' · Half ' + (lengths.half != null ? lengths.half.toFixed(2) : '—') + ' km';
        if (ten) ten.textContent = ' · 10K ' + (lengths['10k'] != null ? lengths['10k'].toFixed(2) : '—') + ' km';
    }

    function renderWarnings(warnings) {
        var el = document.getElementById('segment-recipes-warnings');
        if (!el) return;
        if (!warnings || !warnings.length) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.textContent = 'Stitch warnings: ' + warnings.join(' · ');
    }

    function getOrder(chunkId, eventId) {
        var row = orderGrid[eventId] || {};
        var v = row[chunkId];
        return v == null || v === '' ? '' : String(v);
    }

    function setOrder(chunkId, eventId, value) {
        if (!orderGrid[eventId]) orderGrid[eventId] = {};
        var trimmed = String(value || '').trim();
        if (!trimmed) {
            orderGrid[eventId][chunkId] = null;
        } else {
            var n = parseInt(trimmed, 10);
            orderGrid[eventId][chunkId] = isNaN(n) || n < 1 ? null : n;
        }
        if (libraryState && libraryState.recipe_lengths_km) {
            recomputeTotalsLocal();
        }
    }

    function recomputeTotalsLocal() {
        if (!libraryState || !libraryState.chunks) return;
        var lengths = { full: 0, half: 0, '10k': 0 };
        EVENTS.forEach(function (ev) {
            var pairs = [];
            libraryState.chunks.forEach(function (ch) {
                var o = getOrder(ch.id, ev);
                if (o) pairs.push({ order: parseInt(o, 10), km: ch.length_km || 0 });
            });
            pairs.sort(function (a, b) { return a.order - b.order; });
            lengths[ev] = pairs.reduce(function (sum, p) { return sum + p.km; }, 0);
            lengths[ev] = Math.round(lengths[ev] * 100) / 100;
        });
        renderTotals(lengths);
    }

    function renderTable() {
        var tbody = document.getElementById('segment-recipes-tbody');
        var wrap = document.getElementById('segment-recipes-table-wrap');
        var empty = document.getElementById('segment-recipes-empty');
        var applyBtn = document.getElementById('btn-segment-recipes-apply');
        if (!tbody) return;

        if (!libraryState || !libraryState.has_library || !libraryState.chunks.length) {
            if (wrap) wrap.style.display = 'none';
            if (empty) empty.style.display = 'block';
            if (applyBtn) applyBtn.disabled = true;
            return;
        }

        if (empty) empty.style.display = 'none';
        if (wrap) wrap.style.display = 'block';
        if (applyBtn) applyBtn.disabled = false;

        orderGrid = libraryState.order_grid || orderGrid;
        tbody.innerHTML = '';
        libraryState.chunks.forEach(function (ch) {
            var tr = document.createElement('tr');
            var cells = [
                ch.id,
                ch.seg_id || '',
                (ch.seg_label || '').slice(0, 48),
                (ch.length_km != null ? Number(ch.length_km).toFixed(2) : '—')
            ];
            cells.forEach(function (text) {
                var td = document.createElement('td');
                td.textContent = text;
                tr.appendChild(td);
            });
            EVENTS.forEach(function (ev) {
                var td = document.createElement('td');
                var inp = document.createElement('input');
                inp.type = 'number';
                inp.min = '1';
                inp.max = '99';
                inp.step = '1';
                inp.className = 'segment-recipe-order-input';
                inp.style.width = '3rem';
                inp.dataset.chunkId = ch.id;
                inp.dataset.eventId = ev;
                inp.value = getOrder(ch.id, ev);
                inp.title = 'Order on ' + ev + ' course (leave empty if unused)';
                inp.addEventListener('input', function () {
                    setOrder(ch.id, ev, inp.value);
                });
                td.appendChild(inp);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function loadLibrary() {
        if (!isConfigPackageWorkspace()) {
            showCard(false);
            return Promise.resolve();
        }
        showCard(true);
        return fetch(apiBase() + '/segment-library', { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (data) { return { res: r, data: data }; });
            })
            .then(function (payload) {
                var r = payload.res;
                var data = payload.data;
                if (!r.ok) throw new Error(formatApiError(r, data));
                if (!data.ok) throw new Error(formatApiError(r, data));
                libraryState = data;
                orderGrid = data.order_grid || {};
                renderTable();
                renderTotals(data.recipe_lengths_km);
                renderWarnings(data.stitch_warnings);
                setStatus('');
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function seedReference() {
        setStatus('Loading reference library…');
        return fetch(apiBase() + '/segment-library/seed-reference', {
            method: 'POST',
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, ok: r.ok, data: d }; }); })
            .then(function (res) {
                if (!res.ok) throw new Error(formatApiError(res.res, res.data));
                var data = res.data;
                if (!data.ok) throw new Error(formatApiError(res.res, data));
                libraryState = data;
                orderGrid = data.order_grid || {};
                renderTable();
                renderTotals(data.recipe_lengths_km);
                renderWarnings(data.stitch_warnings);
                setStatus('Reference library loaded (' + (data.chunks || []).length + ' chunks).');
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function uploadGpx(files) {
        if (!files || !files.length) return Promise.resolve();
        var fd = new FormData();
        for (var i = 0; i < files.length; i++) {
            fd.append('files', files[i]);
        }
        setStatus('Uploading GPX…');
        return fetch(apiBase() + '/segment-library/upload', {
            method: 'POST',
            credentials: 'same-origin',
            body: fd
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, ok: r.ok, data: d }; }); })
            .then(function (res) {
                if (!res.ok) throw new Error(formatApiError(res.res, res.data));
                var data = res.data;
                if (!data.ok) throw new Error(formatApiError(res.res, data));
                libraryState = data;
                orderGrid = data.order_grid || {};
                renderTable();
                renderTotals(data.recipe_lengths_km);
                renderWarnings(data.stitch_warnings);
                var n = (data.chunks || []).length;
                setStatus(
                    n
                        ? 'Imported ' + n + ' segment(s). Set order numbers, then Save recipes & export.'
                        : 'GPX saved but no segments detected. Use Load reference library or name files like 01_start.gpx.'
                );
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function saveRecipes() {
        setStatus('Saving recipes and exporting segments.csv…');
        return fetch(apiBase() + '/segment-library/recipes', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_by_event: orderGrid, export_csv: true })
        })
            .then(function (r) { return r.json().then(function (d) { return { res: r, ok: r.ok, data: d }; }); })
            .then(function (res) {
                if (!res.ok) throw new Error(formatApiError(res.res, res.data));
                var data = res.data;
                if (!data.ok) throw new Error(formatApiError(res.res, data));
                if (data.library) {
                    libraryState = data.library;
                    orderGrid = data.library.order_grid || orderGrid;
                }
                if (data.apply) {
                    renderTotals(data.apply.recipe_lengths_km);
                    renderWarnings(data.apply.stitch_warnings);
                    setStatus(
                        'Saved — ' + (data.apply.segment_count || 0) + ' segments exported to segments.csv.'
                    );
                } else {
                    setStatus('Recipes saved.');
                }
                renderTable();
                if (data.course) {
                    document.dispatchEvent(new CustomEvent('segment-recipes-applied', {
                        detail: { course: data.course }
                    }));
                }
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function bindUi() {
        var seedBtn = document.getElementById('btn-segment-library-seed');
        var applyBtn = document.getElementById('btn-segment-recipes-apply');
        var fileInput = document.getElementById('segment-library-gpx-input');
        if (seedBtn) {
            seedBtn.addEventListener('click', function () {
                if (!window.confirm('Replace this package segment library with the built-in reference chunks?')) return;
                seedReference();
            });
        }
        if (applyBtn) {
            applyBtn.addEventListener('click', function () { saveRecipes(); });
        }
        if (fileInput) {
            fileInput.addEventListener('change', function () {
                uploadGpx(fileInput.files);
                fileInput.value = '';
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        bindUi();
        if (isConfigPackageWorkspace()) {
            loadLibrary();
        }
    });

    window.addEventListener('popstate', function () {
        if (isConfigPackageWorkspace()) loadLibrary();
        else showCard(false);
    });

    window.segmentRecipes = {
        load: loadLibrary,
        refresh: loadLibrary
    };
})();
