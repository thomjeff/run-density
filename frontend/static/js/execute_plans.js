/* Execute Plans (Issue #920). Follows Build → Packages list actions. */
(function () {
    "use strict";

    var WEEKDAYS = {
        mon: "Monday",
        tue: "Tuesday",
        wed: "Wednesday",
        thu: "Thursday",
        fri: "Friday",
        sat: "Saturday",
        sun: "Sunday",
    };
    var plans = [];
    var activeId = null;
    var assignPlanId = null;
    var sheetsPlanId = null;
    var rosterPlanId = null;

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function esc(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function setStatus(message, isError) {
        var el = qs("#rf-plans-status");
        if (!el) return;
        if (!message) {
            el.hidden = true;
            el.textContent = "";
            return;
        }
        el.hidden = false;
        el.textContent = message;
        el.style.color = isError ? "#b42318" : "";
    }

    function weekdayLabel(code) {
        var key = String(code || "").toLowerCase();
        return WEEKDAYS[key] || key || "—";
    }

    function shortPlanId(id) {
        return String(id || "").slice(0, 8);
    }

    function statusLabel(row) {
        if (row.archived) return "Archived";
        if (row.active) return "Active";
        return "Inactive";
    }

    function jsonFetch(url, options) {
        return fetch(url, options).then(function (resp) {
            return resp.json().then(function (data) {
                if (!resp.ok) {
                    throw new Error(data.detail || "Request failed.");
                }
                return data;
            });
        });
    }

    function confirmActivate(row) {
        if (!activeId || activeId === row.plan_id) return true;
        return window.confirm(
            "Activate this Day Plan and deactivate the current one? " +
                "Reopen records stay with each plan."
        );
    }

    function confirmArchive(row) {
        var extra = row.active
            ? " It will be deactivated."
            : "";
        return window.confirm(
            "Archive " +
                (row.name || row.calendar_date) +
                "?" +
                extra +
                " Records are kept and it can be restored later."
        );
    }

    function appendAction(cell, kind, title, action, planId) {
        var ta = window.TableActions;
        if (!ta) return null;
        var btn = ta.createIconButton(kind, title, function (ev) {
            ev.stopPropagation();
            var work = runAction(action, planId);
            if (work && work.catch) {
                work.catch(function (err) {
                    setStatus(err.message || String(err), true);
                });
            }
        });
        cell.appendChild(btn);
        return btn;
    }

    function participantCount(row) {
        return Number((row && row.participant_count) || 0);
    }

    function appendActivate(cell, row) {
        var ready = participantCount(row) > 0;
        var btn = appendAction(
            cell,
            "activate",
            ready
                ? "Activate Day Plan"
                : "Add participants before activating",
            "activate",
            row.plan_id
        );
        if (btn && !ready) btn.disabled = true;
    }

    function appendParticipants(cell, row) {
        appendAction(
            cell,
            "participants",
            participantCount(row) > 0 ? "Replace participants" : "Add participants",
            "participants",
            row.plan_id
        );
    }

    function render() {
        var tbody = qs("#rf-plans-tbody");
        if (!tbody) return;
        if (!plans.length) {
            tbody.innerHTML =
                '<tr><td colspan="7" class="placeholder">No Day Plans yet. Click <strong>Import</strong> to add a published ZIP and its participants.</td></tr>';
            return;
        }
        tbody.innerHTML = "";
        plans.forEach(function (row) {
            var tr = document.createElement("tr");
            var status = statusLabel(row);
            var cls =
                "rf-plans-status" +
                (row.active ? " is-active" : "") +
                (row.archived ? " is-archived" : "");
            tr.innerHTML =
                "<td>" +
                esc(row.name || "Day Plan") +
                "</td>" +
                '<td><span class="rf-plans-id" title="' +
                esc(row.plan_id) +
                '">' +
                esc(shortPlanId(row.plan_id)) +
                "</span></td>" +
                "<td>" +
                esc(row.calendar_date || "—") +
                "</td>" +
                "<td>" +
                esc(weekdayLabel(row.weekday_code)) +
                "</td>" +
                "<td>" +
                (participantCount(row) > 0
                    ? esc(participantCount(row))
                    : '<span class="text-secondary">None</span>') +
                "</td>" +
                '<td><span class="' +
                cls +
                '">' +
                esc(status) +
                "</span></td>";
            var actions = document.createElement("td");
            actions.className = "course-map-action-cell";
            var id = row.plan_id;
            if (row.archived) {
                appendAction(actions, "restore", "Restore Day Plan", "restore", id);
            } else if (row.active) {
                appendAction(
                    actions,
                    "deactivate",
                    "Deactivate Day Plan",
                    "deactivate",
                    id
                );
                appendAction(actions, "archive", "Archive Day Plan", "archive", id);
                appendParticipants(actions, row);
                appendAction(
                    actions,
                    "locations",
                    "Location sheets for volunteers",
                    "sheets",
                    id
                );
                appendAction(
                    actions,
                    "person",
                    "Assignments for this Day Plan",
                    "assign",
                    id
                );
            } else {
                appendActivate(actions, row);
                appendAction(actions, "archive", "Archive Day Plan", "archive", id);
                appendParticipants(actions, row);
                appendAction(
                    actions,
                    "locations",
                    "Location sheets for volunteers",
                    "sheets",
                    id
                );
                appendAction(
                    actions,
                    "person",
                    "Assignments for this Day Plan",
                    "assign",
                    id
                );
            }
            tr.appendChild(actions);
            tbody.appendChild(tr);
        });
    }

    function loadPlans() {
        return jsonFetch("/api/execute/plans")
            .then(function (data) {
                plans = data.plans || [];
                activeId = data.active_plan_id || null;
                render();
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function postAction(path, body) {
        return jsonFetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body ? JSON.stringify(body) : "{}",
        });
    }

    function runAction(action, planId) {
        var row = plans.filter(function (item) {
            return item.plan_id === planId;
        })[0];
        if (action === "activate") {
            if (row && !confirmActivate(row)) return;
            return postAction("/api/execute/plans/activate", {
                plan_id: planId,
            }).then(function () {
                setStatus("Activated.");
                if (window.runflowRefreshExecuteContext) {
                    window.runflowRefreshExecuteContext();
                }
                return loadPlans();
            });
        }
        if (action === "deactivate") {
            return postAction("/api/execute/plans/deactivate").then(
                function () {
                    setStatus("Deactivated.");
                    if (window.runflowRefreshExecuteContext) {
                        window.runflowRefreshExecuteContext();
                    }
                    return loadPlans();
                }
            );
        }
        if (action === "archive") {
            if (row && !confirmArchive(row)) return;
            return postAction("/api/execute/plans/archive", {
                plan_id: planId,
            }).then(function () {
                setStatus("Archived. Records were kept.");
                if (sheetsPlanId === planId) {
                    sheetsPlanId = null;
                    var panel = qs("#rf-plans-sheets");
                    if (panel) panel.hidden = true;
                }
                return loadPlans();
            });
        }
        if (action === "restore") {
            return postAction("/api/execute/plans/restore", {
                plan_id: planId,
            }).then(function () {
                setStatus("Restored. Activate it to use it on race day.");
                return loadPlans();
            });
        }
        if (action === "assign") {
            return openAssignments(planId);
        }
        if (action === "sheets") {
            return openSheets(planId);
        }
        if (action === "participants") {
            rosterPlanId = planId;
            var picker = qs("#rf-plans-roster-file");
            if (picker) picker.click();
        }
        return Promise.resolve();
    }

    function uploadRoster(planId, file) {
        if (!planId || !file) return Promise.resolve();
        var row = plans.filter(function (item) {
            return item.plan_id === planId;
        })[0];
        var label = (row && (row.name || row.calendar_date)) || "Day Plan";
        var body = new FormData();
        body.append("file", file);
        setStatus("Loading participants…");
        return jsonFetch(
            "/api/execute/plans/" + encodeURIComponent(planId) + "/participants",
            { method: "POST", body: body, credentials: "same-origin" }
        ).then(function (data) {
            var starts = (data.stats && data.stats.starts) || 0;
            setStatus(
                "Loaded " + starts + " participants for " + label + "."
            );
            return loadPlans();
        });
    }

    function assignStatus(message, isError) {
        var el = qs("#rf-plans-assign-status");
        if (!el) return;
        if (!message) {
            el.hidden = true;
            el.textContent = "";
            return;
        }
        el.hidden = false;
        el.textContent = message;
        el.style.color = isError ? "#b42318" : "";
    }

    function fillAssignForm(row) {
        var form = qs("#rf-plans-assign-form");
        if (!form) return;
        form.device_id.value = row.device_id || "";
        form.resource_name.value = row.resource_name || "";
        form.person_name.value = row.person_name || "";
        form.phone.value = row.phone || "";
        form.agency.value = row.agency || "";
    }

    function renderAssignList(rows) {
        var box = qs("#rf-plans-assign-list");
        if (!box) return;
        if (!rows || !rows.length) {
            box.innerHTML = "<p class=\"card-help\">No assignments yet.</p>";
            return;
        }
        box.innerHTML = rows
            .map(function (row) {
                return (
                    '<button type="button" class="rf-plans-assign-row" data-fill-device="' +
                    esc(row.device_id) +
                    '" data-fill-name="' +
                    esc(row.resource_name || "") +
                    '" data-fill-person="' +
                    esc(row.person_name || "") +
                    '" data-fill-phone="' +
                    esc(row.phone || "") +
                    '" data-fill-agency="' +
                    esc(row.agency || "") +
                    '"><span>' +
                    esc(row.device_id) +
                    "</span><span>" +
                    esc(row.resource_name || "unnamed") +
                    "</span><span>" +
                    esc(row.person_name || "") +
                    "</span></button>"
                );
            })
            .join("");
    }

    function sheetsStatus(message, isError) {
        var el = qs("#rf-plans-sheets-status");
        if (!el) return;
        if (!message) {
            el.hidden = true;
            el.textContent = "";
            return;
        }
        el.hidden = false;
        el.textContent = message;
        el.style.color = isError ? "#b42318" : "";
    }

    function copySheetUrl(path) {
        var url = window.location.origin + path;
        var done = function () {
            sheetsStatus("Copied " + url);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(url).then(done).catch(function () {
                window.prompt("Copy volunteer URL", url);
                done();
            });
        }
        window.prompt("Copy volunteer URL", url);
        done();
        return Promise.resolve();
    }

    function renderSheetList(rows) {
        var box = qs("#rf-plans-sheets-list");
        if (!box) return;
        if (!rows || !rows.length) {
            box.innerHTML =
                '<p class="card-help">No volunteer sheets in this Day Plan ZIP.</p>';
            return;
        }
        box.innerHTML = rows
            .map(function (row) {
                return (
                    '<div class="rf-plans-sheet-row">' +
                    "<span>" +
                    esc(row.loc_id) +
                    "</span><span>" +
                    esc(row.loc_label || "") +
                    '</span><a href="' +
                    esc(row.path) +
                    '" target="_blank" rel="noopener">' +
                    esc(row.path) +
                    "</a></div>"
                );
            })
            .join("");
        box.querySelectorAll(".rf-plans-sheet-row").forEach(function (rowEl, idx) {
            var path = rows[idx] && rows[idx].path;
            if (!path || !window.TableActions) return;
            rowEl.appendChild(
                window.TableActions.createIconButton(
                    "copy",
                    "Copy volunteer URL",
                    function (ev) {
                        ev.preventDefault();
                        copySheetUrl(path);
                    }
                )
            );
        });
    }

    function openSheets(planId) {
        sheetsPlanId = planId;
        var assign = qs("#rf-plans-assign");
        if (assign) assign.hidden = true;
        var panel = qs("#rf-plans-sheets");
        var title = qs("#rf-plans-sheets-title");
        var row = plans.filter(function (item) {
            return item.plan_id === planId;
        })[0];
        if (title) {
            title.textContent =
                "Location sheets · " +
                ((row && (row.name || row.calendar_date)) || "Day Plan");
        }
        if (panel) panel.hidden = false;
        sheetsStatus("");
        return jsonFetch(
            "/api/execute/plans/" + encodeURIComponent(planId) + "/locsheets"
        )
            .then(function (data) {
                renderSheetList(data.sheets || []);
            })
            .catch(function (err) {
                sheetsStatus(err.message || "Could not load location sheets.", true);
            });
    }

    function closeSheets() {
        sheetsPlanId = null;
        var panel = qs("#rf-plans-sheets");
        if (panel) panel.hidden = true;
    }

    function closeAssignments() {
        assignPlanId = null;
        var panel = qs("#rf-plans-assign");
        if (panel) panel.hidden = true;
    }

    function openAssignments(planId) {
        assignPlanId = planId;
        var sheets = qs("#rf-plans-sheets");
        if (sheets) sheets.hidden = true;
        var panel = qs("#rf-plans-assign");
        var title = qs("#rf-plans-assign-title");
        var row = plans.filter(function (item) {
            return item.plan_id === planId;
        })[0];
        if (title) {
            title.textContent =
                "Assignments · " +
                ((row && (row.name || row.calendar_date)) || "Day Plan");
        }
        if (panel) panel.hidden = false;
        assignStatus("");
        return jsonFetch(
            "/api/execute/plans/" + encodeURIComponent(planId) + "/assignments"
        )
            .then(function (data) {
                renderAssignList(data.assignments || []);
            })
            .catch(function (err) {
                assignStatus(err.message || "Could not load assignments.", true);
            });
    }

    function savePlanAssignment(ev) {
        ev.preventDefault();
        var form = qs("#rf-plans-assign-form");
        if (!form || !assignPlanId) return;
        var body = {
            device_id: form.device_id.value,
            resource_name: form.resource_name.value,
            person_name: form.person_name.value,
            phone: form.phone.value,
            agency: form.agency.value,
        };
        return jsonFetch(
            "/api/execute/plans/" +
                encodeURIComponent(assignPlanId) +
                "/assignments",
            {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            }
        )
            .then(function () {
                assignStatus("Saved for this Day Plan.");
                return openAssignments(assignPlanId);
            })
            .catch(function (err) {
                assignStatus(err.message || "Save failed.", true);
            });
    }

    function deletePlanAssignment() {
        var form = qs("#rf-plans-assign-form");
        if (!form || !assignPlanId || !form.device_id.value) return;
        return fetch(
            "/api/execute/plans/" +
                encodeURIComponent(assignPlanId) +
                "/assignments/" +
                encodeURIComponent(form.device_id.value),
            { method: "DELETE", credentials: "same-origin" }
        )
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) {
                        throw new Error(data.detail || "Remove failed.");
                    }
                    return data;
                });
            })
            .then(function () {
                form.reset();
                assignStatus("Removed from this Day Plan.");
                return openAssignments(assignPlanId);
            })
            .catch(function (err) {
                assignStatus(err.message || "Remove failed.", true);
            });
    }

    var importPreview = null;

    function importError(message) {
        var el = qs("#rf-plans-import-error");
        if (!el) return;
        el.hidden = !message;
        el.textContent = message || "";
    }

    function importNote(message) {
        var el = qs("#rf-plans-import-note");
        if (!el) return;
        el.hidden = !message;
        el.textContent = message || "";
    }

    function importPlanId(id) {
        var el = qs("#rf-plans-import-id");
        if (!el) return;
        el.hidden = !id;
        el.title = id || "";
        el.textContent = id ? "Plan ID " + shortPlanId(id) : "";
    }

    function weekdayHelp(code) {
        var el = qs("#rf-plans-import-weekday");
        if (!el) return;
        var day = WEEKDAYS[String(code || "").toLowerCase()];
        el.hidden = !day;
        el.textContent = day ? "This is a " + day + " plan. Pick a " + day + " date." : "";
    }

    function dateWeekday(value) {
        var parts = String(value || "").split("-");
        if (parts.length !== 3) return "";
        var d = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
        if (isNaN(d.getTime())) return "";
        return ["sun", "mon", "tue", "wed", "thu", "fri", "sat"][d.getUTCDay()];
    }

    function importFormReady() {
        var name = qs("#rf-plans-import-name");
        var date = qs("#rf-plans-import-date");
        var roster = qs("#rf-plans-import-roster");
        var submit = qs("#rf-plans-import-submit");
        var ok =
            !!importPreview &&
            !importPreview.archived &&
            !!(name && name.value.trim()) &&
            !!(date && date.value) &&
            dateWeekday(date.value) === importPreview.weekday_code &&
            !!(roster && roster.files && roster.files[0]);
        if (submit) submit.disabled = !ok;
        return ok;
    }

    function resetImportForm() {
        importPreview = null;
        var form = qs("#rf-plans-import-form");
        if (form) form.reset();
        ["#rf-plans-import-name", "#rf-plans-import-date"].forEach(function (sel) {
            var input = qs(sel);
            if (input) input.disabled = true;
        });
        importError("");
        importNote("");
        importPlanId("");
        weekdayHelp("");
        importFormReady();
    }

    function openImportModal() {
        resetImportForm();
        var modal = qs("#rf-plans-import-modal");
        if (modal) modal.hidden = false;
        var pkg = qs("#rf-plans-import-package");
        if (pkg) pkg.focus();
    }

    function closeImportModal() {
        var modal = qs("#rf-plans-import-modal");
        if (modal) modal.hidden = true;
        resetImportForm();
    }

    function previewPackage(file) {
        importPreview = null;
        importError("");
        importNote("");
        importPlanId("");
        importFormReady();
        if (!file) return Promise.resolve();
        var body = new FormData();
        body.append("package", file);
        return jsonFetch("/api/execute/plans/preview", {
            method: "POST",
            body: body,
            credentials: "same-origin",
        })
            .then(function (data) {
                importPreview = data;
                importPlanId(data.plan_id);
                var name = qs("#rf-plans-import-name");
                var date = qs("#rf-plans-import-date");
                if (name) {
                    name.disabled = false;
                    name.value = data.name || "";
                }
                if (date) {
                    date.disabled = false;
                    date.value = data.calendar_date || "";
                }
                weekdayHelp(data.weekday_code);
                if (data.archived) {
                    importNote(
                        "This Day Plan is archived. Restore it from the list before importing it again."
                    );
                } else if (data.already_imported) {
                    importNote(
                        "This Day Plan is already imported. Importing again updates its name and date and replaces its participant list."
                    );
                }
                importFormReady();
            })
            .catch(function (err) {
                importError(err.message || "Could not read this Day Plan ZIP.");
            });
    }

    function submitImport(ev) {
        ev.preventDefault();
        if (!importFormReady()) {
            var date = qs("#rf-plans-import-date");
            if (importPreview && date && date.value &&
                dateWeekday(date.value) !== importPreview.weekday_code) {
                importError(
                    "Pick a " + weekdayLabel(importPreview.weekday_code) + " date."
                );
            }
            return;
        }
        var pkg = qs("#rf-plans-import-package").files[0];
        var roster = qs("#rf-plans-import-roster").files[0];
        var body = new FormData();
        body.append("package", pkg);
        body.append("participants", roster);
        body.append("name", qs("#rf-plans-import-name").value.trim());
        body.append("calendar_date", qs("#rf-plans-import-date").value);
        body.append("activate", "true");
        var submit = qs("#rf-plans-import-submit");
        if (submit) submit.disabled = true;
        importError("");
        return jsonFetch("/api/execute/plans/import", {
            method: "POST",
            body: body,
            credentials: "same-origin",
        })
            .then(function (data) {
                closeImportModal();
                var starts = (data.participants && data.participants.starts) || 0;
                setStatus(
                    "Imported " +
                        (data.name || data.calendar_date || "Day Plan") +
                        " with " +
                        starts +
                        " participants. It is now active."
                );
                if (window.runflowRefreshExecuteContext) {
                    window.runflowRefreshExecuteContext();
                }
                return loadPlans();
            })
            .catch(function (err) {
                importError(err.message || "Import failed.");
                importFormReady();
            });
    }

    function bindImportModal() {
        var importBtn = qs("#rf-plans-import");
        if (importBtn) importBtn.addEventListener("click", openImportModal);
        var form = qs("#rf-plans-import-form");
        if (!form) return;
        form.addEventListener("submit", submitImport);
        form.addEventListener("input", function () {
            importError("");
            importFormReady();
        });
        var pkg = qs("#rf-plans-import-package");
        if (pkg) {
            pkg.addEventListener("change", function () {
                previewPackage(pkg.files && pkg.files[0]);
            });
        }
        var roster = qs("#rf-plans-import-roster");
        if (roster) roster.addEventListener("change", importFormReady);
        var cancel = qs("#rf-plans-import-cancel");
        if (cancel) cancel.addEventListener("click", closeImportModal);
        var modal = qs("#rf-plans-import-modal");
        if (modal) {
            modal.addEventListener("click", function (ev) {
                if (ev.target === modal) closeImportModal();
            });
        }
        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape" && modal && !modal.hidden) closeImportModal();
        });
        var rosterFile = qs("#rf-plans-roster-file");
        if (rosterFile) {
            rosterFile.addEventListener("change", function () {
                var file = rosterFile.files && rosterFile.files[0];
                var planId = rosterPlanId;
                rosterFile.value = "";
                rosterPlanId = null;
                uploadRoster(planId, file).catch(function (err) {
                    setStatus(err.message || String(err), true);
                });
            });
        }
    }

    function bind() {
        bindImportModal();
        var form = qs("#rf-plans-assign-form");
        if (form) form.addEventListener("submit", savePlanAssignment);
        var del = qs("#rf-plans-assign-delete");
        if (del) del.addEventListener("click", deletePlanAssignment);
        function bindClose(containerId, title, closeFn) {
            var box = qs(containerId);
            if (!box || !window.TableActions) return;
            if (box.querySelector(".course-map-action-btn")) return;
            box.appendChild(
                window.TableActions.createIconButton(
                    "close",
                    title,
                    function (ev) {
                        ev.preventDefault();
                        closeFn();
                    }
                )
            );
        }
        bindClose(
            "#rf-plans-sheets-actions",
            "Close location sheets",
            closeSheets
        );
        bindClose(
            "#rf-plans-assign-header-actions",
            "Close assignments",
            closeAssignments
        );
        var list = qs("#rf-plans-assign-list");
        if (list) {
            list.addEventListener("click", function (ev) {
                var fill = ev.target.closest("[data-fill-device]");
                if (!fill) return;
                fillAssignForm({
                    device_id: fill.getAttribute("data-fill-device"),
                    resource_name: fill.getAttribute("data-fill-name"),
                    person_name: fill.getAttribute("data-fill-person"),
                    phone: fill.getAttribute("data-fill-phone"),
                    agency: fill.getAttribute("data-fill-agency"),
                });
            });
        }
        loadPlans();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
