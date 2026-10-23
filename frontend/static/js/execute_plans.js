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
        if (!activeId || activeId === row.published_plan_id) return true;
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
        if (!ta) return;
        cell.appendChild(
            ta.createIconButton(kind, title, function (ev) {
                ev.stopPropagation();
                var work = runAction(action, planId);
                if (work && work.catch) {
                    work.catch(function (err) {
                        setStatus(err.message || String(err), true);
                    });
                }
            })
        );
    }

    function render() {
        var tbody = qs("#rf-plans-tbody");
        if (!tbody) return;
        if (!plans.length) {
            tbody.innerHTML =
                '<tr><td colspan="5" class="placeholder">No Day Plans yet. Click <strong>Import</strong> to add a published ZIP.</td></tr>';
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
                "<td>" +
                esc(row.calendar_date || "—") +
                "</td>" +
                "<td>" +
                esc(weekdayLabel(row.weekday_code)) +
                "</td>" +
                '<td><span class="' +
                cls +
                '">' +
                esc(status) +
                "</span></td>";
            var actions = document.createElement("td");
            actions.className = "course-map-action-cell";
            var id = row.published_plan_id;
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
            } else {
                appendAction(actions, "activate", "Activate Day Plan", "activate", id);
                appendAction(actions, "archive", "Archive Day Plan", "archive", id);
            }
            tr.appendChild(actions);
            tbody.appendChild(tr);
        });
    }

    function loadPlans() {
        return jsonFetch("/api/execute/published-plans")
            .then(function (data) {
                plans = data.plans || [];
                activeId = data.active_published_plan_id || null;
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
            return item.published_plan_id === planId;
        })[0];
        if (action === "activate") {
            if (row && !confirmActivate(row)) return;
            return postAction("/api/execute/published-plans/activate", {
                published_plan_id: planId,
            }).then(function () {
                setStatus("Activated.");
                return loadPlans();
            });
        }
        if (action === "deactivate") {
            return postAction("/api/execute/published-plans/deactivate").then(
                function () {
                    setStatus("Deactivated.");
                    return loadPlans();
                }
            );
        }
        if (action === "archive") {
            if (row && !confirmArchive(row)) return;
            return postAction("/api/execute/published-plans/archive", {
                published_plan_id: planId,
            }).then(function () {
                setStatus("Archived. Records were kept.");
                return loadPlans();
            });
        }
        if (action === "restore") {
            return postAction("/api/execute/published-plans/restore", {
                published_plan_id: planId,
            }).then(function () {
                setStatus("Restored. Activate it to use it on race day.");
                return loadPlans();
            });
        }
        return Promise.resolve();
    }

    function importPackage(file) {
        if (!file) return;
        var body = new FormData();
        body.append("package", file);
        setStatus("Importing…");
        return fetch("/api/execute/published-plans/import", {
            method: "POST",
            body: body,
            credentials: "same-origin",
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) {
                        throw new Error(data.detail || "Import failed.");
                    }
                    return data;
                });
            })
            .then(function (data) {
                var label = data.calendar_date || "Day Plan";
                setStatus(
                    data.idempotent
                        ? label + " was already imported."
                        : "Imported " + label + ". Activate it to use it."
                );
                return loadPlans();
            })
            .catch(function (err) {
                setStatus(err.message || String(err), true);
            });
    }

    function bind() {
        var importBtn = qs("#rf-plans-import");
        var fileInput = qs("#rf-plans-file");
        if (importBtn && fileInput) {
            importBtn.addEventListener("click", function () {
                fileInput.click();
            });
            fileInput.addEventListener("change", function () {
                var file = fileInput.files && fileInput.files[0];
                fileInput.value = "";
                importPackage(file);
            });
        }
        loadPlans();
    }

    document.addEventListener("DOMContentLoaded", bind);
})();
