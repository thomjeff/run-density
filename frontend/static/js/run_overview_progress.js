/**
 * Issue #825: Overview analysis progress card (race-director facing).
 */
(function (global) {
    'use strict';

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatElapsed(startedAt) {
        if (!startedAt) return '';
        var start = Date.parse(startedAt);
        if (!isFinite(start)) return '';
        var sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
        var m = Math.floor(sec / 60);
        var s = sec % 60;
        return m + ':' + String(s).padStart(2, '0');
    }

    function stageIcon(state) {
        if (state === 'done') return '✓';
        if (state === 'current') return '…';
        return '○';
    }

    function renderProgressCard(data) {
        var card = document.getElementById('rf-overview-progress');
        if (!card) return;

        var status = (data && data.status) || '';
        if (status === 'PASS') {
            card.style.display = 'block';
            card.className = 'card rf-overview-progress rf-overview-progress--done';
            card.innerHTML =
                '<h3 style="margin-bottom:0.35rem;">Analysis complete</h3>' +
                '<p class="text-secondary mb-0">Results are ready below.</p>';
            return;
        }
        if (status === 'FAIL') {
            card.style.display = 'block';
            card.className = 'card rf-overview-progress rf-overview-progress--fail';
            card.innerHTML =
                '<h3 style="margin-bottom:0.35rem;">Analysis could not finish</h3>' +
                '<p class="text-secondary">' +
                escapeHtml((data && data.error) || 'Something went wrong while preparing results.') +
                '</p>' +
                '<p class="mb-0"><a href="/config">Open Build</a> to adjust the package and try again.</p>';
            return;
        }
        if (status !== 'running') {
            card.style.display = 'none';
            card.innerHTML = '';
            return;
        }

        var percent = Math.max(0, Math.min(100, Number(data.percent) || 0));
        if (data.step_index && data.step_total) {
            percent = Math.round((100 * (Number(data.step_index) - 1)) / Number(data.step_total));
            // Show some fill while on step 1
            if (percent < 8) percent = 8;
        }
        var elapsed = formatElapsed(data.started_at);
        var stages = data.user_stages || [];
        var listHtml = stages
            .map(function (st) {
                var cls = 'rf-progress-stage rf-progress-stage--' + (st.state || 'pending');
                var note = st.note
                    ? ' <span class="text-secondary">(' + escapeHtml(st.note) + ')</span>'
                    : '';
                return (
                    '<li class="' +
                    cls +
                    '"><span class="rf-progress-stage-icon" aria-hidden="true">' +
                    stageIcon(st.state) +
                    '</span> ' +
                    escapeHtml(st.label) +
                    note +
                    '</li>'
                );
            })
            .join('');

        card.style.display = 'block';
        card.className = 'card rf-overview-progress';
        card.innerHTML =
            '<h3 style="margin-bottom:0.35rem;">Preparing your results</h3>' +
            '<p class="text-secondary" style="margin-bottom:0.75rem;">' +
            escapeHtml(data.message || 'Working…') +
            (elapsed ? ' <span class="rf-progress-elapsed">· Running ' + escapeHtml(elapsed) + '</span>' : '') +
            '</p>' +
            '<div class="rf-progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' +
            percent +
            '"><div class="rf-progress-bar-fill" style="width:' +
            percent +
            '%;"></div></div>' +
            '<ul class="rf-progress-stages">' +
            listHtml +
            '</ul>' +
            '<p class="text-secondary small mb-0">This usually takes a few minutes. You can leave this page open.</p>';
    }

    function hideProgressCard() {
        var card = document.getElementById('rf-overview-progress');
        if (!card) return;
        card.style.display = 'none';
        card.innerHTML = '';
    }

    /**
     * Poll progress until PASS/FAIL. onComplete(status) when terminal.
     * Returns a stop() function.
     */
    function watchRunProgress(runId, fetchJson, onComplete) {
        var stopped = false;
        var started = Date.now();
        var timer = null;
        var seenRunning = false;

        function delayMs() {
            return Date.now() - started > 120000 ? 4000 : 2000;
        }

        function tick() {
            if (stopped || !runId) return;
            fetchJson('/api/runs/' + encodeURIComponent(runId) + '/progress')
                .then(function (data) {
                    if (stopped) return;
                    renderProgressCard(data);
                    var status = data && data.status;
                    if (status === 'running') {
                        seenRunning = true;
                        timer = setTimeout(tick, delayMs());
                        return;
                    }
                    if (status === 'PASS' || status === 'FAIL') {
                        if (status === 'PASS' && !seenRunning) {
                            hideProgressCard();
                            if (typeof onComplete === 'function') onComplete(status, data);
                            return;
                        }
                        if (typeof onComplete === 'function') onComplete(status, data);
                        if (status === 'PASS') {
                            setTimeout(function () {
                                if (!stopped) hideProgressCard();
                            }, 3000);
                        }
                        return;
                    }
                    // Unknown — keep polling briefly if we never saw running
                    if (!seenRunning && Date.now() - started < 15000) {
                        timer = setTimeout(tick, delayMs());
                    } else {
                        hideProgressCard();
                    }
                })
                .catch(function () {
                    if (stopped) return;
                    // Run may not exist yet; retry a few times
                    if (Date.now() - started < 30000) {
                        timer = setTimeout(tick, delayMs());
                    }
                });
        }

        tick();
        return function stop() {
            stopped = true;
            if (timer) clearTimeout(timer);
        };
    }

    global.RunOverviewProgress = {
        watchRunProgress: watchRunProgress,
        renderProgressCard: renderProgressCard,
        hideProgressCard: hideProgressCard,
    };
})(window);
