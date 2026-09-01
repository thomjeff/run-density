/* Execute Incidents queue + form (Issue #911). UI → API → JSON only. */
(function () {
    "use strict";

    var catalog = {};
    var current = null;

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function runId() {
        var params = new URLSearchParams(window.location.search);
        return (
            params.get("run_id") ||
            (window.runflowDay && window.runflowDay.run_id) ||
            localStorage.getItem("selected_run_id") ||
            ""
        ).trim();
    }

    function dayCode() {
        return (
            (window.runflowDay && window.runflowDay.selected) ||
            localStorage.getItem("selected_day") ||
            ""
        ).trim();
    }

    function incidentId() {
        return new URLSearchParams(window.location.search).get("incident_id") || "";
    }

    function apiUrl(path) {
        var url = path + "?run_id=" + encodeURIComponent(runId());
        var day = dayCode();
        if (day) url += "&day=" + encodeURIComponent(day);
        return url;
    }

    function esc(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function showError(msg) {
        var el = qs("#rf-hs-error");
        if (!el) return;
        if (!msg) {
            el.hidden = true;
            el.textContent = "";
            return;
        }
        el.hidden = false;
        el.textContent = msg;
    }

    function jsonFetch(url, options) {
        return fetch(url, options).then(function (resp) {
            return resp.json().then(function (body) {
                if (!resp.ok) {
                    var detail = body.detail;
                    if (Array.isArray(detail)) detail = detail[0] && detail[0].msg;
                    throw new Error(detail || "Request failed.");
                }
                return body;
            });
        });
    }

    function bibLabel(row) {
        var bib = String(row.display_bib || row.bib || "").trim();
        if (!bib) return '<span class="rf-hs-missing">No bib</span>';
        return esc(bib);
    }

    function nameOf(row) {
        return (String(row.given_name || "") + " " + String(row.family_name || "")).trim() || "—";
    }

    function checks(name, items, selected) {
        var picked = {};
        (selected || []).forEach(function (id) {
            picked[id] = true;
        });
        return (
            '<div class="rf-hs-check">' +
            (items || [])
                .map(function (item) {
                    return (
                        "<label><input type=\"checkbox\" name=\"" +
                        esc(name) +
                        "\" value=\"" +
                        esc(item.id) +
                        "\"" +
                        (picked[item.id] ? " checked" : "") +
                        "> " +
                        esc(item.label) +
                        "</label>"
                    );
                })
                .join("") +
            "</div>"
        );
    }

    function selected(name) {
        return Array.prototype.map
            .call(document.querySelectorAll('input[name="' + name + '"]:checked'), function (el) {
                return el.value;
            });
    }

    function val(id) {
        var el = qs("#" + id);
        return el ? el.value : "";
    }

    function renderLists(body) {
        catalog = body.catalog || catalog;
        var active = body.active || [];
        var closed = body.closed || [];
        qs("#rf-hs-title").textContent = "Incidents";
        qs("#rf-hs-sub").textContent = "";
        qs("#rf-hs-form").hidden = true;
        qs("#rf-hs-lists").hidden = false;
        function rows(list, extra) {
            if (!list.length) {
                return '<p class="rf-hs-empty" style="border:0;">None</p>';
            }
            return list
                .map(function (row) {
                    return (
                        '<button type="button" class="rf-hs-strip" data-open="' +
                        esc(row.incident_id) +
                        '">' +
                        '<div class="rf-hs-strip-bib">' +
                        bibLabel(row) +
                        "</div>" +
                        "<div><div class=\"rf-hs-strip-name\">" +
                        esc(nameOf(row)) +
                        '</div><div class="rf-hs-meta">' +
                        esc(row.sub_event || "—") +
                        (extra ? " · " + extra(row) : "") +
                        "</div></div>" +
                        '<span class="rf-hs-meta">' +
                        (row.incident_status === "closed"
                            ? esc(row.closed_at_label || "Closed")
                            : "Open") +
                        "</span></button>"
                    );
                })
                .join("");
        }
        qs("#rf-hs-lists").innerHTML =
            '<div class="rf-hs-board">' +
            '<section class="rf-hs-card">' +
            '<header class="rf-hs-col-head is-active"><span>Active</span>' +
            '<span class="rf-hs-col-count">' +
            (body.counts && body.counts.active != null ? body.counts.active : active.length) +
            "</span></header>" +
            rows(active) +
            "</section>" +
            '<section class="rf-hs-card">' +
            '<header class="rf-hs-col-head is-closed"><span>Closed</span>' +
            '<span class="rf-hs-col-count">' +
            (body.counts && body.counts.closed != null ? body.counts.closed : closed.length) +
            "</span></header>" +
            rows(closed, function (row) {
                var outcome = (catalog.outcomes || []).find(function (item) {
                    return item.id === row.outcome;
                });
                return outcome ? outcome.label : "";
            }) +
            "</section></div>";
    }

    function identityHtml(incident) {
        var bib = String(incident.display_bib || incident.bib || "").trim();
        var bibHtml = bib
            ? '<div class="rf-hs-idbar-bib">' + esc(bib) + "</div>"
            : '<div class="rf-hs-idbar-bib"><span class="rf-hs-missing">No bib</span></div>';
        var meta = [incident.age, incident.sex, incident.sub_event]
            .filter(function (part) {
                return String(part || "").trim();
            })
            .join(" · ");
        var warn = bib
            ? ""
            : '<p class="rf-hs-warn" style="margin:0.4rem 0 0;">Race Roster has no bib for this start.</p>';
        return (
            '<div class="rf-hs-card rf-hs-idbar">' +
            bibHtml +
            "<div><div class=\"rf-hs-idbar-name\">" +
            esc(nameOf(incident)) +
            '</div><div class="rf-hs-meta">' +
            esc(meta || "—") +
            "</div>" +
            warn +
            "</div></div>"
        );
    }

    function renderForm(incident) {
        current = incident;
        catalog = catalog || {};
        qs("#rf-hs-lists").hidden = true;
        qs("#rf-hs-form").hidden = false;
        qs("#rf-hs-title").textContent = "Incident";
        qs("#rf-hs-sub").textContent =
            (incident.incident_status === "closed" ? "Closed" : "Active") +
            (incident.opened_at_label ? " · opened " + incident.opened_at_label : "");
        var notes = (incident.notes || [])
            .map(function (note) {
                return (
                    '<div class="rf-hs-note"><time>' +
                    esc(note.saved_at_label || note.saved_at) +
                    "</time> · " +
                    esc(note.text) +
                    "</div>"
                );
            })
            .join("");
        var outcomes = (catalog.outcomes || [])
            .map(function (item) {
                return (
                    '<option value="' +
                    esc(item.id) +
                    '"' +
                    (incident.outcome === item.id ? " selected" : "") +
                    ">" +
                    esc(item.label) +
                    "</option>"
                );
            })
            .join("");
        qs("#rf-hs-form").innerHTML =
            identityHtml(incident) +
            '<div class="rf-hs-form-grid">' +
            '<div class="rf-hs-card rf-hs-form-section"><h3>Incident type</h3>' +
            '<div class="rf-hs-label">Location</div>' +
            '<input id="hs-loc" class="form-control form-control-sm" value="' +
            esc(incident.location_text || "") +
            '">' +
            '<div class="rf-hs-label" style="margin-top:0.55rem;">Type</div>' +
            checks("incident_types", catalog.incident_types, incident.incident_types) +
            '<div class="rf-hs-label" style="margin-top:0.55rem;">Type notes</div>' +
            '<input id="hs-type-note" class="form-control form-control-sm" value="' +
            esc(incident.incident_type_note || "") +
            '"></div>' +
            '<div class="rf-hs-card rf-hs-form-section"><h3>Care</h3>' +
            checks("care_types", catalog.care_types, incident.care_types) +
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.45rem;margin-top:0.55rem;">' +
            '<div><div class="rf-hs-label">Care transferred?</div>' +
            '<select id="hs-xfer" class="form-select form-select-sm">' +
            '<option value=""></option><option value="no"' +
            (incident.care_transferred === "no" ? " selected" : "") +
            '>No</option><option value="yes"' +
            (incident.care_transferred === "yes" ? " selected" : "") +
            ">Yes</option></select></div>" +
            '<div><div class="rf-hs-label">911 called?</div>' +
            '<select id="hs-911" class="form-select form-select-sm">' +
            '<option value=""></option><option value="no"' +
            (incident.called_911 === "no" ? " selected" : "") +
            '>No</option><option value="yes"' +
            (incident.called_911 === "yes" ? " selected" : "") +
            ">Yes</option></select></div></div>" +
            '<div class="rf-hs-label" style="margin-top:0.55rem;">Transferred to</div>' +
            checks("transferred_to", catalog.transferred_to, incident.transferred_to) +
            "</div>" +
            '<div class="rf-hs-card rf-hs-form-section"><h3>Outcome</h3>' +
            '<select id="hs-outcome" class="form-select form-select-sm">' +
            '<option value=""></option>' +
            outcomes +
            "</select>" +
            '<p class="rf-hs-meta" style="margin:0.45rem 0 0;">DNF is an incident outcome, not a Participants action.</p>' +
            '<div class="rf-hs-label" style="margin-top:0.7rem;">Completed by</div>' +
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.45rem;">' +
            '<input id="hs-by-name" class="form-control form-control-sm" placeholder="Name" value="' +
            esc(incident.completed_by_name || "") +
            '">' +
            '<input id="hs-by-agency" class="form-control form-control-sm" placeholder="Agency" value="' +
            esc(incident.completed_by_agency || "") +
            '"></div></div></div>' +
            '<div class="rf-hs-card rf-hs-form-section" style="margin-top:0.75rem;"><h3>Notes</h3>' +
            (notes || '<p class="rf-hs-meta">No notes yet.</p>') +
            '<div style="display:flex;gap:0.5rem;margin-top:0.55rem;">' +
            '<input id="hs-note" class="form-control form-control-sm" placeholder="Add a note…">' +
            '<button type="button" class="btn btn-sm" id="hs-save-note">Save note</button></div></div>' +
            '<div class="rf-hs-actions">' +
            '<button type="button" class="btn btn-sm" id="hs-back">Back to lists</button>' +
            '<button type="button" class="btn btn-sm" id="hs-save">Save</button>' +
            (incident.incident_status === "closed"
                ? ""
                : '<button type="button" class="btn btn-sm btn-primary" id="hs-close">Close incident</button>') +
            "</div>";
    }

    function formPayload() {
        return {
            location_text: val("hs-loc"),
            incident_types: selected("incident_types"),
            incident_type_note: val("hs-type-note"),
            care_types: selected("care_types"),
            care_transferred: val("hs-xfer"),
            called_911: val("hs-911"),
            transferred_to: selected("transferred_to"),
            outcome: val("hs-outcome"),
            completed_by_name: val("hs-by-name"),
            completed_by_agency: val("hs-by-agency"),
        };
    }

    function setIncidentQuery(id) {
        var params = new URLSearchParams(window.location.search);
        if (id) params.set("incident_id", id);
        else params.delete("incident_id");
        var next = window.location.pathname + "?" + params.toString();
        window.history.replaceState({}, "", next);
    }

    function loadLists() {
        return jsonFetch(apiUrl("/api/execute/incidents"), {
            credentials: "same-origin",
        }).then(function (body) {
            catalog = body.catalog || {};
            renderLists(body);
        });
    }

    function loadForm(id) {
        return jsonFetch(apiUrl("/api/execute/incidents/" + encodeURIComponent(id)), {
            credentials: "same-origin",
        }).then(function (body) {
            catalog = body.catalog || catalog;
            renderForm(body.incident);
        });
    }

    function saveForm() {
        if (!current) return Promise.resolve();
        return jsonFetch(
            apiUrl("/api/execute/incidents/" + encodeURIComponent(current.incident_id)),
            {
                method: "PUT",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(formPayload()),
            }
        ).then(function (body) {
            renderForm(body.incident);
        });
    }

    function saveNote() {
        var text = val("hs-note");
        if (!current || !text.trim()) return Promise.resolve();
        return jsonFetch(
            apiUrl(
                "/api/execute/incidents/" +
                    encodeURIComponent(current.incident_id) +
                    "/notes"
            ),
            {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: text }),
            }
        ).then(function (body) {
            renderForm(body.incident);
        });
    }

    function closeIncident() {
        if (!current) return Promise.resolve();
        return saveForm().then(function () {
            return jsonFetch(
                apiUrl(
                    "/api/execute/incidents/" +
                        encodeURIComponent(current.incident_id) +
                        "/close"
                ),
                { method: "POST", credentials: "same-origin" }
            );
        }).then(function () {
            setIncidentQuery("");
            return loadLists();
        });
    }

    function bind() {
        if (!runId()) {
            qs("#rf-hs-empty").hidden = false;
            return;
        }
        qs("#rf-hs-lists").addEventListener("click", function (ev) {
            var btn = ev.target.closest("[data-open]");
            if (!btn) return;
            var id = btn.getAttribute("data-open");
            setIncidentQuery(id);
            loadForm(id).catch(function (err) {
                showError(err.message || String(err));
            });
        });
        qs("#rf-hs-form").addEventListener("click", function (ev) {
            var id = ev.target && ev.target.id;
            var work = Promise.resolve();
            if (id === "hs-back") {
                setIncidentQuery("");
                work = loadLists();
            } else if (id === "hs-save") work = saveForm();
            else if (id === "hs-save-note") work = saveNote();
            else if (id === "hs-close") work = closeIncident();
            else return;
            work.catch(function (err) {
                showError(err.message || String(err));
            });
        });
        var id = incidentId();
        var start = id ? loadForm(id) : loadLists();
        start.catch(function (err) {
            showError(err.message || String(err));
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
