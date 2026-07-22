/**
 * Shared Analysis Inputs + Analysis Outputs renderers (Issue #796 Overview).
 * Used by /overview (Tabler). Classic dashboard keeps its own renderers.
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

    function renderAnalysisInputsView(data) {
        var section = document.getElementById('analysis-inputs-section');
        var content = document.getElementById('analysis-inputs-content');
        if (!section || !content) return;

        section.style.display = 'block';

        var days = data.days || [];
        var inputs = data.analysis_inputs || {};

        var html = ''
            + '<div class="rf-overview-meta">'
            + '<strong>Run ID:</strong> ' + escapeHtml(data.run_id || '—') + '<br>'
            + '<strong>Description:</strong> ' + escapeHtml(data.description || 'N/A')
            + '</div>'
            + '<h4 class="rf-overview-subhead">Events</h4>'
            + '<div class="scrollable-table-container"><table class="table-sticky-header"><thead><tr>'
            + '<th>Day</th><th>Event</th><th>Participants</th><th>Start Time</th>'
            + '<th>First Finisher</th><th>Last Finisher</th><th>Duration</th>'
            + '</tr></thead><tbody>';

        var eventRows = 0;
        days.forEach(function (day) {
            var row = inputs[day] || {};
            var evs = row.events || [];
            if (!evs.length) {
                html += '<tr><td>' + escapeHtml(day) + '</td>'
                    + '<td colspan="6">—</td></tr>';
                eventRows += 1;
                return;
            }
            evs.forEach(function (ev, idx) {
                html += '<tr>';
                if (idx === 0) {
                    html += '<td rowspan="' + evs.length + '">' + escapeHtml(day) + '</td>';
                }
                html += '<td>' + escapeHtml(ev.event || '—') + '</td>'
                    + '<td>' + (ev.participants != null ? escapeHtml(ev.participants) : '—') + '</td>'
                    + '<td>' + escapeHtml(ev.start_time || '—') + '</td>'
                    + '<td>' + escapeHtml(ev.first_finisher || '—') + '</td>'
                    + '<td>' + escapeHtml(ev.last_finisher || '—') + '</td>'
                    + '<td>' + escapeHtml(ev.duration || '—') + '</td>'
                    + '</tr>';
                eventRows += 1;
            });
        });
        if (!eventRows) {
            html += '<tr><td colspan="7" class="placeholder">—</td></tr>';
        }
        html += '</tbody></table></div>';
        content.innerHTML = html;
    }

    function renderRunDetailView(data) {
        var section = document.getElementById('run-detail-section');
        var content = document.getElementById('run-detail-content');
        if (!section || !content) return;

        section.style.display = 'block';

        var days = data.days || [];
        var metrics = data.metrics || {};

        var metricRows = [
            { key: 'participants', label: 'Total Participants' },
            { key: 'events', label: 'Events', format: function (val) {
                return Array.isArray(val) ? val.join(', ') : val;
            } },
            { key: 'day_first_finisher', label: 'First Finisher', format: function (val) { return val || '—'; } },
            { key: 'day_last_finisher', label: 'Last Finisher', format: function (val) { return val || '—'; } },
            { key: 'day_duration', label: 'Day Duration', format: function (val) { return val || '—'; } },
            { key: 'segments_with_flags', label: 'Segments with Flags' },
            { key: 'peak_density', label: 'Peak Density (P/m²)' },
            { key: 'peak_rate', label: 'Peak Rate (P/s)' },
            { key: 'overtaking_segments', label: 'Overtaking Segments' },
            { key: 'co_presence_segments', label: 'Co-Presence Segments' },
            { key: 'flagged_bins', label: 'Flagged Bins', format: function (val) {
                return (val !== undefined && val !== null && !Number.isNaN(Number(val))
                    ? Number(val).toLocaleString() : '—');
            } },
            { key: 'operational_status', label: 'Operational Status' },
            { key: 'event_groups', label: 'Runner Experience Scores (RES)', format: function (val) {
                if (!val || typeof val !== 'object' || Object.keys(val).length === 0) return '—';
                return Object.entries(val).map(function (pair) {
                    var res = (pair[1] && pair[1].res) || 0;
                    return pair[0] + ': ' + Number(res).toFixed(2);
                }).join(', ') || '—';
            } }
        ];

        var html = ''
            + '<div class="scrollable-table-container"><table class="table-sticky-header"><thead><tr>'
            + '<th>Metric</th>'
            + days.map(function (d) { return '<th>' + escapeHtml(d) + '</th>'; }).join('')
            + '</tr></thead><tbody>';

        metricRows.forEach(function (row) {
            html += '<tr><td>' + escapeHtml(row.label) + '</td>';
            days.forEach(function (day) {
                var dayMetrics = metrics[day] || {};
                var value = dayMetrics[row.key];
                if (row.format) value = row.format(value, dayMetrics);
                else if (typeof value === 'number') value = value.toLocaleString();

                if (row.key === 'peak_density' && dayMetrics.peak_density_los) {
                    var los = dayMetrics.peak_density_los;
                    html += '<td>' + escapeHtml(value || '—')
                        + ' <span class="badge-los badge-' + escapeHtml(los) + '">'
                        + escapeHtml(los) + '</span></td>';
                } else {
                    html += '<td>' + escapeHtml(value || '—') + '</td>';
                }
            });
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        content.innerHTML = html;
    }

    function loadRunSummary(runId, fetchJson) {
        return fetchJson('/api/runs/' + encodeURIComponent(runId) + '/summary')
            .then(function (data) {
                try { renderAnalysisInputsView(data); } catch (e) { console.error(e); }
                try { renderRunDetailView(data); } catch (e) { console.error(e); }
                return data;
            });
    }

    global.RunOverview = {
        renderAnalysisInputsView: renderAnalysisInputsView,
        renderRunDetailView: renderRunDetailView,
        loadRunSummary: loadRunSummary,
        escapeHtml: escapeHtml
    };
})(window);
