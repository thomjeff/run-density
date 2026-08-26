/**
 * Plan → Overview: choose a package, set start times, run analysis (Issue #904).
 */
(function () {
    'use strict';

    var runAnalysisSetup = null;
    var selectedPackageId = '';
    var selectedPackageLabel = '';

    function eventLabel(name) {
        var n = String(name || '').toLowerCase();
        if (n === '10k') return '10K';
        if (!n) return 'Event';
        return n.charAt(0).toUpperCase() + n.slice(1);
    }

    function minutesToTime(m) {
        m = parseInt(m, 10);
        if (isNaN(m) || m < 0) return '';
        var h = Math.floor(m / 60);
        var min = m % 60;
        return String(h).padStart(2, '0') + ':' + String(min).padStart(2, '0');
    }

    function timeToMinutes(timeStr) {
        if (!timeStr) return null;
        var parts = String(timeStr).trim().split(':');
        if (parts.length < 2) return null;
        var h = parseInt(parts[0], 10);
        var m = parseInt(parts[1], 10);
        if (isNaN(h) || isNaN(m)) return null;
        return h * 60 + m;
    }

    function setStatus(msg, isError) {
        var el = document.getElementById('rf-plan-analysis-status') ||
            document.getElementById('package-run-analysis-status');
        if (!el) return;
        el.textContent = msg || '';
        el.style.color = isError ? '#d63939' : '#667382';
    }

    function showModal(id, show) {
        var modal = document.getElementById(id);
        if (!modal) return;
        if (show && modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
        modal.hidden = !show;
        modal.setAttribute('aria-hidden', show ? 'false' : 'true');
    }

    function showRunAnalysisModal(show) {
        showModal('run-analysis-modal', show);
    }

    function showPackagePicker(show) {
        showModal('package-picker-modal', show);
    }

    function setRunAnalysisModalError(msg) {
        var el = document.getElementById('run-analysis-modal-error');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.style.display = 'block';
        el.textContent = msg;
    }

    function renderRunAnalysisEventRows(events) {
        var tbody = document.getElementById('run-analysis-events-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        (events || []).forEach(function (ev) {
            var tr = document.createElement('tr');
            var nameTd = document.createElement('td');
            nameTd.textContent = eventLabel(ev.name || ev.id || '');
            nameTd.dataset.eventName = ev.name;
            tr.appendChild(nameTd);

            var startTd = document.createElement('td');
            var startInput = document.createElement('input');
            startInput.type = 'time';
            startInput.className = 'config-package-input';
            startInput.dataset.eventName = ev.name;
            startInput.required = true;
            var suggested =
                ev.suggested_start_time_label ||
                (ev.suggested_start_time != null ? minutesToTime(ev.suggested_start_time) : '');
            if (suggested) startInput.value = suggested;
            startTd.appendChild(startInput);
            tr.appendChild(startTd);

            var durTd = document.createElement('td');
            var durInput = document.createElement('input');
            durInput.type = 'number';
            durInput.min = '1';
            durInput.max = '500';
            durInput.className = 'config-package-input';
            durInput.style.width = '5rem';
            durInput.dataset.eventName = ev.name;
            durInput.required = true;
            if (ev.suggested_event_duration_minutes != null) {
                durInput.value = String(ev.suggested_event_duration_minutes);
            }
            durTd.appendChild(durInput);
            tr.appendChild(durTd);

            tbody.appendChild(tr);
        });
    }

    function collectRunAnalysisEvents(eventDay) {
        var tbody = document.getElementById('run-analysis-events-tbody');
        if (!tbody) return [];
        var events = [];
        tbody.querySelectorAll('tr').forEach(function (tr) {
            var name = tr.querySelector('td[data-event-name]');
            var startInput = tr.querySelector('input[type="time"]');
            var durInput = tr.querySelector('input[type="number"]');
            if (!name || !startInput || !durInput) return;
            var eventName = name.dataset.eventName;
            var startMinutes = timeToMinutes(startInput.value);
            var duration = parseInt(durInput.value, 10);
            if (!eventName) return;
            if (startMinutes == null || startMinutes < 300 || startMinutes > 1200) {
                throw new Error(
                    eventLabel(eventName) + ': start time must be between 05:00 and 20:00'
                );
            }
            if (isNaN(duration) || duration < 1 || duration > 500) {
                throw new Error(
                    eventLabel(eventName) + ': duration must be between 1 and 500 minutes'
                );
            }
            events.push({
                name: eventName,
                day: eventDay,
                start_time: startMinutes,
                event_duration_minutes: duration,
            });
        });
        return events;
    }

    function packageApiBase(configId) {
        var id = String(configId || selectedPackageId || '').trim();
        if (!id) return '';
        return '/api/config/packages/' + encodeURIComponent(id);
    }

    function syncPickerContinue() {
        var btn = document.getElementById('package-picker-continue');
        var sel = document.getElementById('package-picker-select');
        var idEl = document.getElementById('package-picker-id');
        if (!btn || !sel) return;
        var opt = sel.options[sel.selectedIndex];
        var ready = !!(opt && opt.value && opt.dataset.ready === '1');
        btn.disabled = !ready;
        if (idEl) {
            idEl.textContent = opt && opt.value ? 'ID: ' + opt.value : '';
        }
        if (!sel.value) {
            btn.title = 'Choose a package';
        } else if (!ready) {
            btn.title = 'Package is not analysis-ready — assign courses, Build race exports, and runners on Build → Packages';
        } else {
            btn.title = 'Enter start times for each event';
        }
    }

    function populatePackagePicker(packages, preferredId) {
        var sel = document.getElementById('package-picker-select');
        if (!sel) return;
        sel.innerHTML = '';
        var blank = document.createElement('option');
        blank.value = '';
        blank.textContent = packages.length ? 'Select a package…' : 'No packages yet';
        sel.appendChild(blank);
        packages.forEach(function (pkg) {
            var opt = document.createElement('option');
            opt.value = pkg.config_id;
            var ready = !!(pkg.readiness && pkg.readiness.analyze_ready);
            opt.dataset.ready = ready ? '1' : '0';
            opt.dataset.label = pkg.label || pkg.config_id;
            opt.textContent =
                (pkg.label || pkg.config_id) +
                '  ·  ' +
                pkg.config_id +
                (ready ? '' : '  (not ready)');
            sel.appendChild(opt);
        });
        if (preferredId && sel.querySelector('option[value="' + preferredId + '"]')) {
            sel.value = preferredId;
        }
        selectedPackageId = sel.value;
        var opt = sel.options[sel.selectedIndex];
        selectedPackageLabel = opt ? (opt.dataset.label || '') : '';
        syncPickerContinue();
    }

    function loadPackagesThen(cb) {
        fetch('/api/config/packages', { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) throw new Error('Failed to list packages');
                cb(payload.data.packages || []);
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function openPackagePicker() {
        var err = document.getElementById('package-picker-error');
        if (err) {
            err.style.display = 'none';
            err.textContent = '';
        }
        loadPackagesThen(function (packages) {
            var stored = '';
            try {
                stored = (sessionStorage.getItem('rf_plan_package_id') || '').trim();
            } catch (e) { /* ignore */ }
            var params = new URLSearchParams(window.location.search);
            var pick = (params.get('config_id') || '').trim() || stored;
            populatePackagePicker(packages, pick);
            showPackagePicker(true);
        });
    }

    function openRunAnalysisModal() {
        var base = packageApiBase();
        if (!base) return;
        setRunAnalysisModalError('');
        setStatus('Loading analysis setup…');
        fetch(base + '/analyze-setup', { credentials: 'same-origin' })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    throw new Error(
                        (payload.data && payload.data.detail) || 'Failed to load analysis setup'
                    );
                }
                var setup = payload.data;
                if (!setup.readiness || !setup.readiness.analyze_ready) {
                    throw new Error(
                        'Package is not analysis-ready yet. Assign courses, Build race exports, and runners on Build → Packages.'
                    );
                }
                runAnalysisSetup = setup;
                var pkgEl = document.getElementById('run-analysis-package-label');
                if (pkgEl) {
                    pkgEl.textContent = 'Package: ' + (selectedPackageLabel || selectedPackageId);
                }
                var dayEl = document.getElementById('run-analysis-event-day');
                if (dayEl) {
                    dayEl.textContent =
                        'Race day: ' + String(setup.event_day || 'sun').toUpperCase();
                }
                renderRunAnalysisEventRows(setup.events || []);
                showRunAnalysisModal(true);
                setStatus('');
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function submitRunAnalysisModal() {
        var base = packageApiBase();
        if (!base || !runAnalysisSetup) return;
        setRunAnalysisModalError('');
        var events;
        try {
            events = collectRunAnalysisEvents(runAnalysisSetup.event_day || 'sun');
        } catch (err) {
            setRunAnalysisModalError(err.message || String(err));
            return;
        }
        if (!events.length) {
            setRunAnalysisModalError('Add at least one event schedule.');
            return;
        }
        showRunAnalysisModal(false);
        setStatus('Starting analysis…');
        fetch(base + '/run-analysis', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description: runAnalysisSetup.description || '',
                enable_audit: 'n',
                events: events,
            }),
        })
            .then(function (r) {
                return r.json().then(function (d) {
                    return { ok: r.ok, data: d };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    throw new Error(
                        (payload.data && (payload.data.error || payload.data.detail)) ||
                            'Analysis start failed'
                    );
                }
                var runId = payload.data.run_id;
                var eventDay = String(
                    (runAnalysisSetup && runAnalysisSetup.event_day) || ''
                )
                    .toLowerCase()
                    .trim();
                if (runId) {
                    localStorage.setItem('selected_run_id', runId);
                    if (eventDay) localStorage.setItem('selected_day', eventDay);
                    try {
                        localStorage.setItem('rf_workspace', 'plan');
                    } catch (e) { /* ignore */ }
                    var dest =
                        '/overview?run_id=' +
                        encodeURIComponent(runId) +
                        (eventDay ? '&day=' + encodeURIComponent(eventDay) : '');
                    window.location.href = dest;
                    return;
                }
                setStatus('Analysis started.');
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function openRunAnalysisForPackage(configId, label) {
        selectedPackageId = String(configId || '').trim();
        selectedPackageLabel = label || selectedPackageId;
        try {
            if (selectedPackageId) {
                sessionStorage.setItem('rf_plan_package_id', selectedPackageId);
            }
        } catch (e) { /* ignore */ }
        openRunAnalysisModal();
    }

    function bindUi() {
        if (!document.getElementById('run-analysis-modal')) return;
        var newBtn = document.getElementById('rf-plan-new-analysis');
        if (newBtn) {
            newBtn.addEventListener('click', openPackagePicker);
        }
        var pickerSel = document.getElementById('package-picker-select');
        if (pickerSel) {
            pickerSel.addEventListener('change', function () {
                selectedPackageId = pickerSel.value;
                var opt = pickerSel.options[pickerSel.selectedIndex];
                selectedPackageLabel = opt ? (opt.dataset.label || '') : '';
                try {
                    if (selectedPackageId) {
                        sessionStorage.setItem('rf_plan_package_id', selectedPackageId);
                    }
                } catch (e) { /* ignore */ }
                syncPickerContinue();
            });
        }
        var pickerContinue = document.getElementById('package-picker-continue');
        if (pickerContinue) {
            pickerContinue.addEventListener('click', function () {
                showPackagePicker(false);
                openRunAnalysisModal();
            });
        }
        ['package-picker-close', 'package-picker-cancel'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.addEventListener('click', function () {
                    showPackagePicker(false);
                });
            }
        });
        var pickerBackdrop = document.querySelector(
            '#package-picker-modal .course-location-modal-backdrop'
        );
        if (pickerBackdrop) {
            pickerBackdrop.addEventListener('click', function () {
                showPackagePicker(false);
            });
        }
        var pkgBtn = document.getElementById('btn-run-package-analysis');
        if (pkgBtn) {
            pkgBtn.addEventListener('click', function () {
                var id = '';
                if (window.SavedCoursesPanel && typeof window.SavedCoursesPanel.configId === 'function') {
                    id = window.SavedCoursesPanel.configId();
                }
                if (!id) {
                    var params = new URLSearchParams(window.location.search);
                    id = (params.get('config_id') || '').trim();
                }
                var nameEl = document.getElementById('course-map-name-text');
                var label = nameEl ? String(nameEl.textContent || '').trim() : id;
                openRunAnalysisForPackage(id, label);
            });
        }
        var runSubmit = document.getElementById('btn-run-analysis-submit');
        if (runSubmit) {
            runSubmit.addEventListener('click', submitRunAnalysisModal);
        }
        ['run-analysis-modal-close', 'run-analysis-modal-cancel'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.addEventListener('click', function () {
                    showRunAnalysisModal(false);
                    runAnalysisSetup = null;
                });
            }
        });
        var runBackdrop = document.querySelector(
            '#run-analysis-modal .course-location-modal-backdrop'
        );
        if (runBackdrop) {
            runBackdrop.addEventListener('click', function () {
                showRunAnalysisModal(false);
                runAnalysisSetup = null;
            });
        }
    }

    document.addEventListener('DOMContentLoaded', bindUi);

    window.PlanRunAnalysis = {
        openForPackage: openRunAnalysisForPackage,
        openPicker: openPackagePicker,
    };
})();
