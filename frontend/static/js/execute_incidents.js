/* Execute Incidents queue + case (Issues #912 / #914). UI → API → JSON only. */
(function () {
    "use strict";

    var catalog = {};
    var locations = [];
    var lists = { active: [], closed: [], counts: { active: 0, closed: 0 } };
    var current = null;
    var savedForm = null;
    var ui = {
        activeOpen: true,
        closedOpen: false,
        tiles: {
            details: false,
            outcome: false,
        },
        queueQ: "",
        locOpen: false,
        xferOpen: false,
        moreCare: false,
        savePhase: "saved",
        saving: null,
        noteDrafts: {},
        pendingNav: null,
    };

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

    function catalogLabel(group, id) {
        var wanted = String(id || "");
        var hit = (catalog[group] || []).find(function (item) {
            return item.id === wanted;
        });
        return hit ? hit.label : wanted;
    }

    function reporterAgencyId(raw) {
        var wanted = String(raw || "").trim();
        if (!wanted) return "";
        var lower = wanted.toLowerCase().replace(/ /g, "_");
        var hit = (catalog.reporter_agencies || []).find(function (item) {
            return (
                item.id === wanted ||
                item.id === lower ||
                item.label === wanted ||
                String(item.label || "").toLowerCase() === wanted.toLowerCase()
            );
        });
        return hit ? hit.id : "";
    }

    function chevron(open) {
        return open ? "▼" : "▶";
    }

    function isClosed(incident) {
        return !!(incident && incident.incident_status === "closed");
    }

    function ro(incident) {
        return isClosed(incident) ? " readonly" : "";
    }

    function dis(incident) {
        return isClosed(incident) ? " disabled" : "";
    }

    function lifecycleOf(row) {
        var life = row && row.lifecycle;
        if (life && life.id) return life;
        if (row && row.incident_status === "closed") {
            return { id: "closed", label: "Closed", display: "Closed" };
        }
        if (row && String(row.assigned_to || "").trim()) {
            var agency = catalogLabel("agencies", row.assigned_to);
            return {
                id: "assigned",
                label: "Assigned",
                agency_label: agency,
                display: "Assigned · " + agency,
            };
        }
        return { id: "open", label: "Open", display: "Open" };
    }

    function lifecycleDisplay(row) {
        var life = lifecycleOf(row);
        return life.display || life.label || "Open";
    }

    function badgesHtml(row) {
        var life = lifecycleOf(row);
        var html =
            '<span class="rf-hs-status is-' +
            esc(life.id || "open") +
            '">' +
            esc(lifecycleDisplay(row)) +
            "</span>";
        if (row && row.called_911 === "yes") {
            html += '<span class="rf-hs-911-badge">911 called</span>';
        }
        return html;
    }

    function called911Control(incident) {
        return (
            '<div class="rf-hs-911-live">' +
            fieldLabel("hs-911", "911 called?") +
            '<select id="hs-911" class="form-select form-select-sm" style="max-width:10rem;"' +
            dis(incident) +
            ">" +
            '<option value="">Not yet recorded</option><option value="no"' +
            (incident.called_911 === "no" ? " selected" : "") +
            '>No</option><option value="yes"' +
            (incident.called_911 === "yes" ? " selected" : "") +
            ">Yes</option></select></div>"
        );
    }

    function liveBadgeRow(incident) {
        var snapshot = {
            incident_status: incident.incident_status,
            assigned_to: qs("#hs-assigned")
                ? val("hs-assigned")
                : incident.assigned_to,
            called_911: qs("#hs-911") ? val("hs-911") : incident.called_911,
        };
        return badgesHtml(snapshot);
    }

    function fieldLabel(forId, text) {
        return (
            '<label class="rf-hs-label" for="' +
            esc(forId) +
            '">' +
            text +
            "</label>"
        );
    }

    function participantsHref() {
        var url = "/execute/participants?run_id=" + encodeURIComponent(runId());
        var day = dayCode();
        if (day) url += "&day=" + encodeURIComponent(day);
        return url;
    }

    function checks(name, items, selected, incident) {
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
                        dis(incident) +
                        "> " +
                        esc(item.label) +
                        "</label>"
                    );
                })
                .join("") +
            "</div>"
        );
    }

    function itemById(group, id) {
        return (catalog[group] || []).find(function (item) {
            return item.id === id;
        });
    }

    function checkLine(name, item, picked, incident) {
        if (!item) return "";
        return (
            "<label><input type=\"checkbox\" name=\"" +
            esc(name) +
            "\" value=\"" +
            esc(item.id) +
            "\"" +
            (picked[item.id] ? " checked" : "") +
            dis(incident) +
            "> " +
            esc(item.label) +
            "</label>"
        );
    }

    function currentProblemIds(incident) {
        if (qs('input[name="incident_types"]')) return selected("incident_types");
        return (incident && incident.incident_types) || [];
    }

    function suggestedCareIds(problemIds) {
        var seen = {};
        var out = [];
        var map = catalog.care_suggestions || {};
        (problemIds || []).forEach(function (pid) {
            (map[pid] || []).forEach(function (cid) {
                if (seen[cid]) return;
                seen[cid] = true;
                out.push(cid);
            });
        });
        return out;
    }

    function careOptionsInner(pickedList, incident) {
        var picked = {};
        (pickedList || []).forEach(function (id) {
            picked[id] = true;
        });
        var suggested = suggestedCareIds(currentProblemIds(incident));
        var shared = catalog.shared_care_types || [];
        var shown = {};
        var html = "";
        if (suggested.length) {
            html +=
                '<div class="rf-hs-label">Suggested from reported problem</div>' +
                '<div class="rf-hs-check">';
            suggested.forEach(function (id) {
                shown[id] = true;
                html += checkLine(
                    "care_types",
                    itemById("care_types", id),
                    picked,
                    incident
                );
            });
            html += "</div>";
        }
        html +=
            '<div class="rf-hs-label" style="margin-top:0.45rem;">Always available</div>' +
            '<div class="rf-hs-check">';
        shared.forEach(function (id) {
            if (shown[id]) return;
            shown[id] = true;
            html += checkLine(
                "care_types",
                itemById("care_types", id),
                picked,
                incident
            );
        });
        Object.keys(picked).forEach(function (id) {
            if (shown[id] || !itemById("care_types", id)) return;
            shown[id] = true;
            html += checkLine(
                "care_types",
                itemById("care_types", id),
                picked,
                incident
            );
        });
        html += "</div>";
        var moreItems = (catalog.care_types || []).filter(function (item) {
            return !shown[item.id];
        });
        if (moreItems.length) {
            html +=
                '<button type="button" class="btn btn-sm rf-hs-xfer-btn" id="hs-care-more">' +
                (ui.moreCare ? "Hide extra care options" : "More care options") +
                "</button>" +
                '<div id="hs-care-more-list" class="rf-hs-check"' +
                (ui.moreCare ? "" : " hidden") +
                ">";
            moreItems.forEach(function (item) {
                html += checkLine("care_types", item, picked, incident);
            });
            html += "</div>";
        }
        html +=
            '<div id="hs-care-other-wrap" class="rf-hs-other-wrap"' +
            (picked.other_care ? "" : " hidden") +
            ">" +
            fieldLabel("hs-care-note", "Other care reported") +
            '<input id="hs-care-note" class="form-control form-control-sm" maxlength="160" placeholder="Short description" value="' +
            esc(
                qs("#hs-care-note")
                    ? val("hs-care-note")
                    : (incident && incident.care_note) || ""
            ) +
            '"' +
            ro(incident) +
            "></div>";
        return html;
    }

    function refreshCareOptions() {
        var wrap = qs("#hs-care-options");
        if (!wrap || !current) return;
        wrap.innerHTML = careOptionsInner(selected("care_types"), current);
    }

    function applyProblemExclusive(target) {
        var boxes = document.querySelectorAll('input[name="incident_types"]');
        if (!target || !boxes.length) return;
        if (target.value === "not_yet_known" && target.checked) {
            Array.prototype.forEach.call(boxes, function (el) {
                if (el.value !== "not_yet_known") el.checked = false;
            });
        } else if (target.checked && target.value !== "not_yet_known") {
            Array.prototype.forEach.call(boxes, function (el) {
                if (el.value === "not_yet_known") el.checked = false;
            });
        }
    }

    function applyCareExclusive(target) {
        var exclusive = {};
        (catalog.exclusive_care_types || []).forEach(function (id) {
            exclusive[id] = true;
        });
        var boxes = document.querySelectorAll('input[name="care_types"]');
        if (!target || !boxes.length) return;
        if (target.checked && exclusive[target.value]) {
            Array.prototype.forEach.call(boxes, function (el) {
                if (el !== target) el.checked = false;
            });
        } else if (target.checked) {
            Array.prototype.forEach.call(boxes, function (el) {
                if (exclusive[el.value]) el.checked = false;
            });
        }
    }

    function selected(name) {
        return Array.prototype.map.call(
            document.querySelectorAll('input[name="' + name + '"]:checked'),
            function (el) {
                return el.value;
            }
        );
    }

    function val(id) {
        var el = qs("#" + id);
        return el ? el.value : "";
    }

    function sortedCopy(items) {
        return (items || []).slice().sort();
    }

    function payloadKey(payload) {
        var data = payload || {};
        return JSON.stringify({
            description: String(data.description || ""),
            reported_by_name: String(data.reported_by_name || ""),
            reported_by_agency: String(data.reported_by_agency || ""),
            assigned_to: String(data.assigned_to || ""),
            assigned_note: String(data.assigned_note || ""),
            location_text: String(data.location_text || ""),
            location_loc_id: String(data.location_loc_id || ""),
            incident_types: sortedCopy(data.incident_types),
            incident_type_other: String(data.incident_type_other || ""),
            care_types: sortedCopy(data.care_types),
            care_note: String(data.care_note || ""),
            called_911: String(data.called_911 || ""),
            outcome: String(data.outcome || ""),
            completed_by_name: String(data.completed_by_name || ""),
            completed_by_agency: String(data.completed_by_agency || ""),
        });
    }

    function captureDraft() {
        if (!current || !qs("#hs-note")) return;
        ui.noteDrafts[current.incident_id] = qs("#hs-note").value;
    }

    function currentDraft() {
        if (!current) return "";
        if (qs("#hs-note")) return qs("#hs-note").value;
        return ui.noteDrafts[current.incident_id] || "";
    }

    function isDirty() {
        if (!current || isClosed(current) || !qs("#hs-desc") || !savedForm) return false;
        return payloadKey(formPayload()) !== payloadKey(savedForm);
    }

    function fieldChanged(now, prev, key) {
        var a = now[key];
        var b = prev[key];
        if (
            Object.prototype.toString.call(a) === "[object Array]" ||
            Object.prototype.toString.call(b) === "[object Array]"
        ) {
            return JSON.stringify(sortedCopy(a)) !== JSON.stringify(sortedCopy(b));
        }
        return String(a || "") !== String(b || "");
    }

    function dirtyFieldLabels() {
        if (!savedForm) return [];
        var now = formPayload();
        var pairs = [
            ["reported_by_name", "Reporter's name"],
            ["reported_by_agency", "Reporter role / organization"],
            ["assigned_to", "Care agency"],
            ["assigned_note", "Assignment details"],
            ["location_text", "Location"],
            ["location_loc_id", "Location"],
            ["description", "Initial report"],
            ["incident_types", "Reported problem"],
            ["incident_type_other", "Other reported problem"],
            ["care_types", "Care provided"],
            ["care_note", "Other care reported"],
            ["called_911", "911 called"],
            ["outcome", "Outcome"],
            ["completed_by_name", "Closed by"],
            ["completed_by_agency", "Roles/Organization"],
        ];
        var out = [];
        var seen = {};
        pairs.forEach(function (pair) {
            if (!fieldChanged(now, savedForm, pair[0]) || seen[pair[1]]) return;
            seen[pair[1]] = true;
            out.push(pair[1]);
        });
        return out;
    }

    function hasPendingWork() {
        return isDirty() || !!String(currentDraft() || "").trim();
    }

    function summaryFromIncident(incident) {
        var bits = [];
        ((incident && incident.incident_types) || []).forEach(function (id) {
            bits.push(catalogLabel("incident_types", id));
        });
        return bits.filter(Boolean).join(" · ");
    }

    function missingSaveFields() {
        var missing = [];
        if (!val("hs-report-name").trim()) missing.push("Reporter's name");
        if (!val("hs-report-agency").trim()) missing.push("Reporter role / organization");
        if (!val("hs-loc").trim()) missing.push("Location");
        if (!val("hs-desc").trim()) missing.push("Initial report");
        return missing;
    }

    function missingCloseFields() {
        var missing = [];
        if (!val("hs-outcome").trim()) missing.push("Outcome");
        if (!val("hs-by-name").trim()) missing.push("Closed by");
        if (!val("hs-by-agency").trim()) {
            missing.push("Roles/Organization");
        }
        return missing;
    }

    function canCloseCase() {
        return !missingCloseFields().length;
    }

    function expandTile(name) {
        ui.tiles[name] = true;
        var body = qs('[data-tile-body="' + name + '"]');
        if (body) body.hidden = false;
        var btn = qs('[data-tile="' + name + '"]');
        if (btn) {
            btn.setAttribute("aria-expanded", "true");
            var mark = btn.querySelector(".rf-hs-chevron");
            if (mark) mark.textContent = chevron(true);
        }
        updateSaveStatus();
    }

    function requireSaveFields() {
        var missing = missingSaveFields();
        if (!missing.length) return "";
        return "Required to save: " + missing.join(", ") + ".";
    }

    function detailsSummary(incident) {
        if (!qs('input[name="incident_types"]')) return summaryFromIncident(incident);
        var bits = [];
        selected("incident_types").forEach(function (id) {
            bits.push(catalogLabel("incident_types", id));
        });
        return bits.filter(Boolean).join(" · ");
    }

    function updateSaveStatus() {
        var status = qs("#hs-save-status");
        var retry = qs("#hs-save-retry");
        var flag = qs("#hs-id-unsaved");
        var noteStatus = qs("#hs-note-status");
        var addBtn = qs("#hs-save-note");
        var draft = String(currentDraft() || "").trim();
        var dirty = isDirty();
        var phase = ui.savePhase;
        if (phase !== "saving" && phase !== "error") {
            phase = dirty ? "unsaved" : "saved";
            ui.savePhase = phase;
        }
        if (status) {
            if (phase === "saving") status.textContent = "Saving…";
            else if (phase === "error") status.textContent = "Not saved";
            else if (phase === "unsaved") status.textContent = "Unsaved changes";
            else if (draft) status.textContent = "Case details saved · Note not added";
            else {
                var when =
                    (current && (current.updated_at_label || current.opened_at_label)) || "";
                status.textContent = when ? "Saved · " + when : "Saved";
            }
        }
        if (retry) retry.hidden = phase !== "error";
        if (flag) flag.hidden = phase !== "unsaved" && phase !== "error";
        if (noteStatus) {
            noteStatus.textContent = draft ? "Note not added" : "";
            noteStatus.classList.toggle("is-pending", !!draft);
        }
        if (addBtn) {
            addBtn.textContent = "Add to case log";
            addBtn.disabled = !draft || phase === "saving";
        }
        var saveBtn = qs("#hs-save");
        if (saveBtn) saveBtn.disabled = phase === "saving";
        var closeBtn = qs("#hs-close");
        var closeHint = qs("#hs-close-hint");
        var closeMissing = missingCloseFields();
        if (closeBtn) {
            closeBtn.disabled = !!closeMissing.length;
            closeBtn.title = closeMissing.length
                ? "Still needed: " + closeMissing.join(", ") + "."
                : "";
        }
        if (closeHint) {
            closeHint.hidden = !closeMissing.length;
            closeHint.textContent = closeMissing.length
                ? "Still needed: " + closeMissing.join(", ") + "."
                : "";
        }
        var summary = qs("#hs-details-summary");
        if (summary) {
            summary.textContent = detailsSummary(current);
            summary.hidden = !!ui.tiles.details || !summary.textContent;
        }
        var badges = qs("#hs-id-badges");
        if (badges && current) badges.innerHTML = liveBadgeRow(current);
    }

    function optionsHtml(items, currentId, emptyLabel) {
        var opts =
            '<option value="">' +
            esc(emptyLabel == null ? "Not yet recorded" : emptyLabel) +
            "</option>";
        (items || []).forEach(function (item) {
            opts +=
                '<option value="' +
                esc(item.id) +
                '"' +
                (String(currentId || "") === item.id ? " selected" : "") +
                ">" +
                esc(item.label) +
                "</option>";
        });
        return opts;
    }

    function matchesQueue(row, needle) {
        if (!needle) return true;
        var hay =
            String(row.display_bib || row.bib || "") +
            " " +
            nameOf(row) +
            " " +
            String(row.sub_event || "") +
            " " +
            String(row.location_text || "") +
            " " +
            catalogLabel("agencies", row.assigned_to);
        return hay.toLowerCase().indexOf(needle) !== -1;
    }

    function queueCareLine(row) {
        var loc = String(row.location_text || "").trim() || "Location not recorded";
        var agency = catalogLabel("agencies", row.assigned_to);
        if (!String(row.assigned_to || "").trim()) agency = "Care agency not recorded";
        return loc + " · " + agency;
    }

    function stripHtml(row, extra) {
        var selectedId = current && current.incident_id;
        var stamp =
            row.incident_status === "closed"
                ? row.closed_at_label || "Closed"
                : row.updated_at_label || row.opened_at_label || "";
        var when =
            row.incident_status === "closed"
                ? "Closed" + (stamp && stamp !== "Closed" ? " · " + stamp : "")
                : stamp
                  ? "Last update " + stamp
                  : "No updates yet";
        return (
            '<button type="button" class="rf-hs-strip' +
            (selectedId && selectedId === row.incident_id ? " is-selected" : "") +
            '" data-open="' +
            esc(row.incident_id) +
            '">' +
            '<div class="rf-hs-strip-name">' +
            '<span class="rf-hs-strip-bib">' +
            bibLabel(row) +
            "</span> " +
            esc(nameOf(row)) +
            "</div>" +
            '<div class="rf-hs-meta">' +
            esc(queueCareLine(row)) +
            (extra ? " · " + extra : "") +
            "</div>" +
            '<div class="rf-hs-strip-badges">' +
            badgesHtml(row) +
            "</div>" +
            '<div class="rf-hs-meta">' +
            esc(when) +
            "</div></button>"
        );
    }

    function queueSection(kind, title, open, rows, extraFn) {
        var needle = String(ui.queueQ || "").trim().toLowerCase();
        var filtered = (rows || []).filter(function (row) {
            return matchesQueue(row, needle);
        });
        var body;
        if (!filtered.length) {
            body =
                '<p class="rf-hs-empty" style="border:0;margin:0;">' +
                esc(
                    needle
                        ? kind === "active"
                            ? "No active cases match this search"
                            : "No closed cases match this search"
                        : kind === "active"
                          ? "No active cases"
                          : "No closed cases"
                ) +
                "</p>";
        } else {
            body = filtered
                .map(function (row) {
                    return stripHtml(row, extraFn ? extraFn(row) : "");
                })
                .join("");
        }
        return (
            '<section class="rf-hs-card">' +
            '<button type="button" class="rf-hs-col-head is-' +
            esc(kind) +
            '" data-fold="' +
            esc(kind) +
            '" aria-expanded="' +
            (open ? "true" : "false") +
            '"><span><span class="rf-hs-chevron">' +
            chevron(open) +
            "</span> " +
            esc(title) +
            '</span><span class="rf-hs-col-count">' +
            (needle
                ? filtered.length + " / " + (rows || []).length
                : lists.counts && lists.counts[kind] != null
                  ? lists.counts[kind]
                  : (rows || []).length) +
            "</span></button>" +
            '<div data-fold-body="' +
            esc(kind) +
            '"' +
            (open ? "" : " hidden") +
            ">" +
            body +
            "</div></section>"
        );
    }

    function renderQueue() {
        var closedExtra = function (row) {
            return catalogLabel("outcomes", row.outcome);
        };
        qs("#rf-hs-queue").innerHTML =
            '<div class="rf-hs-queue-tools">' +
            '<input id="hs-queue-q" class="form-control form-control-sm rf-hs-queue-filter" placeholder="Find bib or name…" value="' +
            esc(ui.queueQ) +
            '" aria-label="Find bib or name">' +
            (ui.queueQ
                ? '<button type="button" class="btn btn-sm" id="hs-queue-clear">Clear search</button>'
                : "") +
            "</div>" +
            '<a class="rf-hs-queue-start" href="' +
            esc(participantsHref()) +
            '">Start a case</a>' +
            queueSection("active", "Active cases", ui.activeOpen, lists.active) +
            queueSection(
                "closed",
                "Closed cases",
                ui.closedOpen,
                lists.closed,
                closedExtra
            );
        var filter = qs("#hs-queue-q");
        if (filter && ui.queueQ) {
            filter.focus();
            filter.setSelectionRange(ui.queueQ.length, ui.queueQ.length);
        }
    }

    function tile(name, title, inner, summary) {
        var open = !!ui.tiles[name];
        return (
            '<div class="rf-hs-fold">' +
            '<button type="button" class="rf-hs-tile-head" data-tile="' +
            esc(name) +
            '" aria-expanded="' +
            (open ? "true" : "false") +
            '"><span>' +
            esc(title) +
            (name === "details"
                ? '<span id="hs-details-summary" class="rf-hs-fold-summary"' +
                  (open || !summary ? " hidden" : "") +
                  ">" +
                  esc(summary || "") +
                  "</span>"
                : "") +
            '</span><span class="rf-hs-chevron">' +
            chevron(open) +
            "</span></button>" +
            '<div class="rf-hs-tile-body" data-tile-body="' +
            esc(name) +
            '"' +
            (open ? "" : " hidden") +
            ">" +
            inner +
            "</div></div>"
        );
    }

    function healthHtml(incident) {
        var conditions = incident.medical_conditions || [];
        var note = String(incident.medical_note || "").trim();
        if (!conditions.length && !note) return "";
        var chips = conditions
            .map(function (token) {
                return '<span class="rf-hs-chip">' + esc(token) + "</span>";
            })
            .join("");
        return (
            '<div class="rf-hs-idbar-health">' +
            (chips ? '<div class="rf-hs-chip-row">' + chips + "</div>" : "") +
            (note ? '<div class="rf-hs-idbar-note">' + esc(note) + "</div>" : "") +
            "</div>"
        );
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
            "<div style=\"flex:1;min-width:12rem;\"><div class=\"rf-hs-idbar-name\">" +
            esc(nameOf(incident)) +
            "</div><div class=\"rf-hs-meta\">" +
            esc(meta || "—") +
            "</div>" +
            healthHtml(incident) +
            warn +
            "</div>" +
            '<span id="hs-id-unsaved" class="rf-hs-save-flag" hidden>Unsaved changes</span>' +
            '<span id="hs-id-badges" class="rf-hs-idbar-badges">' +
            badgesHtml(incident) +
            "</span></div>"
        );
    }

    function agencyHtml(incident) {
        var locked = isClosed(incident);
        var assigned = String(incident.assigned_to || "").trim();
        var html = assigned
            ? '<div class="rf-hs-label" style="margin-top:0.7rem;">Care agency currently attending</div>'
            : '<div style="margin-top:0.7rem;">' +
              fieldLabel("hs-assigned", "Care agency currently attending") +
              "</div>";
        if (!assigned) {
            html +=
                '<select id="hs-assigned" class="form-select form-select-sm" aria-label="Care agency currently attending"' +
                dis(incident) +
                ">" +
                optionsHtml(
                    catalog.agencies,
                    "",
                    "Care agency not yet recorded"
                ) +
                "</select>";
            if (!locked) {
                html +=
                    fieldLabel("hs-assign-note", "Assignment details (optional)") +
                    '<input id="hs-assign-note" class="form-control form-control-sm" placeholder="Optional details">' +
                    '<button type="button" class="btn btn-sm rf-hs-xfer-btn" id="hs-assign">Record care agency</button>';
            }
            return html;
        }
        html +=
            '<div class="rf-hs-agency-now" id="hs-assigned-now">' +
            esc(catalogLabel("agencies", assigned)) +
            "</div>";
        if (locked) return html;
        html +=
            '<button type="button" class="btn btn-sm rf-hs-xfer-btn" id="hs-xfer-open">Record care handoff</button>' +
            '<div id="hs-xfer-panel" class="rf-hs-xfer-panel"' +
            (ui.xferOpen ? "" : " hidden") +
            ">" +
            fieldLabel("hs-xfer-to", "Agency taking over care") +
            '<select id="hs-xfer-to" class="form-select form-select-sm">' +
            optionsHtml(catalog.agencies, "", "Not yet recorded") +
            "</select>" +
            fieldLabel("hs-xfer-note", "Handoff details (optional)") +
            '<input id="hs-xfer-note" class="form-control form-control-sm" placeholder="Optional details">' +
            '<div class="rf-hs-xfer-actions">' +
            '<button type="button" class="btn btn-sm" id="hs-xfer-cancel">Cancel</button>' +
            '<button type="button" class="btn btn-sm btn-primary" id="hs-xfer-confirm">Confirm transfer</button>' +
            "</div></div>";
        return html;
    }

    function locHits(query) {
        var needle = String(query || "").trim().toLowerCase();
        var list = locations || [];
        if (!needle) return list.slice(0, 12);
        return list
            .filter(function (row) {
                var label = String(row.loc_label || "").toLowerCase();
                var zone = String(row.zone || "").toLowerCase();
                return label.indexOf(needle) !== -1 || zone.indexOf(needle) !== -1;
            })
            .slice(0, 12);
    }

    function locDisplayLabel(row) {
        var label = String((row && row.loc_label) || "").trim();
        var zone = String((row && row.zone) || "").trim();
        if (zone && /^\d+$/.test(zone)) {
            var trailing = new RegExp("\\s+" + zone + "$");
            if (trailing.test(label)) {
                label = label.replace(trailing, "").replace(/[,\s]+$/, "");
            }
            label = label ? label + " · Zone " + zone : "Zone " + zone;
        } else if (zone && label.toLowerCase().indexOf(zone.toLowerCase()) === -1) {
            label = label ? label + " · " + zone : zone;
        }
        return label;
    }

    function locMenuHtml(query) {
        var hits = locHits(query);
        if (!hits.length) {
            return '<div class="rf-hs-meta" style="padding:0.45rem 0.65rem;">No course location matches — the typed description is kept.</div>';
        }
        return hits
            .map(function (row) {
                return (
                    '<button type="button" class="rf-hs-typeahead-item" data-loc-id="' +
                    esc(row.loc_id == null ? "" : row.loc_id) +
                    '" data-loc-label="' +
                    esc(row.loc_label || "") +
                    '">' +
                    esc(locDisplayLabel(row)) +
                    "</button>"
                );
            })
            .join("");
    }

    function showLocMenu(open) {
        if (isClosed(current)) open = false;
        ui.locOpen = !!open;
        var menu = qs("#hs-loc-menu");
        if (!menu) return;
        if (!open) {
            menu.hidden = true;
            menu.innerHTML = "";
            return;
        }
        menu.innerHTML = locMenuHtml(val("hs-loc"));
        menu.hidden = false;
    }

    function noteKindLabel(note, incident) {
        var text = String((note && note.text) || "").trim();
        if (note.kind === "transfer") {
            return text.indexOf("Assigned ") === 0
                ? "Care agency"
                : "Transfer of care";
        }
        if (note.kind === "system") return "System";
        var desc = String((incident && incident.description) || "").trim();
        if (desc && text === desc) return "Initial report";
        return "Update";
    }

    function parseActivityNote(note) {
        var headline = String((note && note.text) || "").trim();
        var detail = String((note && note.detail) || "").trim();
        if (!detail && note && note.kind === "transfer") {
            var splitAt = headline.indexOf(". ");
            if (splitAt > 0) {
                detail = headline.slice(splitAt + 2).trim();
                headline = headline.slice(0, splitAt + 1);
            }
        }
        return { headline: headline, detail: detail };
    }

    function activityNeedsPopup(note) {
        var parsed = parseActivityNote(note);
        return parsed.detail.length > 0 || parsed.headline.length > 88;
    }

    function hideActivityModal() {
        var modal = qs("#hs-activity-modal");
        if (modal) modal.hidden = true;
    }

    function showActivityModal(note, incident) {
        var parsed = parseActivityNote(note);
        var modal = qs("#hs-activity-modal");
        var title = qs("#hs-activity-title");
        var when = qs("#hs-activity-when");
        var headline = qs("#hs-activity-headline");
        var detail = qs("#hs-activity-detail");
        if (!modal) return;
        if (title) title.textContent = noteKindLabel(note, incident);
        if (when) when.textContent = note.saved_at_label || note.saved_at || "";
        if (headline) headline.textContent = parsed.headline;
        if (detail) {
            detail.textContent = parsed.detail;
            detail.hidden = !parsed.detail;
        }
        modal.hidden = false;
        var closeBtn = qs("#hs-activity-close");
        if (closeBtn) closeBtn.focus();
    }

    function notesHtml(incident) {
        var notes = (incident.notes || []).slice().reverse();
        if (!notes.length) return '<p class="rf-hs-meta">No notes yet.</p>';
        return notes
            .map(function (note, index) {
                var parsed = parseActivityNote(note);
                var kind =
                    note.kind === "system"
                        ? " is-system"
                        : note.kind === "transfer"
                          ? " is-transfer"
                          : "";
                var openable = activityNeedsPopup(note);
                var tag = openable ? "button" : "div";
                var extra =
                    tag === "button"
                        ? ' type="button" data-activity="' +
                          index +
                          '"'
                        : "";
                return (
                    "<" +
                    tag +
                    ' class="rf-hs-note' +
                    kind +
                    (openable ? " is-openable" : "") +
                    '"' +
                    extra +
                    '><div class="rf-hs-note-head"><time>' +
                    esc(note.saved_at_label || note.saved_at) +
                    "</time> · " +
                    esc(noteKindLabel(note, incident)) +
                    "</div>" +
                    '<div class="rf-hs-note-line">' +
                    esc(parsed.headline) +
                    (openable
                        ? ' <span class="rf-hs-note-more">Details</span>'
                        : "") +
                    "</div>" +
                    (parsed.detail
                        ? '<div class="rf-hs-note-print">' +
                          esc(parsed.detail) +
                          "</div>"
                        : "") +
                    "</" +
                    tag +
                    ">"
                );
            })
            .join("");
    }

    function renderCase(incident) {
        captureDraft();
        var same =
            current && incident && current.incident_id === incident.incident_id;
        if (!same) {
            ui.tiles.details = false;
            ui.tiles.outcome = false;
            ui.xferOpen = false;
            ui.moreCare = false;
            ui.savePhase = "saved";
        }
        current = incident || null;
        var pane = qs("#rf-hs-case");
        if (!incident) {
            qs("#rf-hs-sub").textContent = "";
            savedForm = null;
            pane.innerHTML =
                '<div class="rf-hs-case-empty">' +
                "<p>Select an active case to add an update, or start a new case from Participants.</p>" +
                '<p class="rf-hs-meta">Find the participant by bib or name, then select Start case.</p>' +
                '<a class="btn btn-sm btn-primary" href="' +
                esc(participantsHref()) +
                '">Start a case</a></div>';
            return;
        }
        qs("#rf-hs-sub").textContent = "";
        var locLinked = String(incident.location_loc_id || "").trim();
        var locked = isClosed(incident);
        var draft = ui.noteDrafts[incident.incident_id] || "";
        pane.innerHTML =
            '<div class="rf-hs-case-stack' +
            (locked ? " is-closed" : "") +
            '">' +
            identityHtml(incident) +
            '<div class="rf-hs-case-work">' +
            '<div class="rf-hs-summary">' +
            '<h3 class="rf-hs-work-title">Incident report</h3>' +
            '<div class="rf-hs-reporter-row">' +
            "<div>" +
            fieldLabel("hs-report-name", "Reporter's name") +
            '<input id="hs-report-name" class="form-control form-control-sm" placeholder="Name" value="' +
            esc(incident.reported_by_name || "") +
            '"' +
            ro(incident) +
            "></div>" +
            "<div>" +
            fieldLabel("hs-report-agency", "Reporter role / organization") +
            '<select id="hs-report-agency" class="form-select form-select-sm"' +
            dis(incident) +
            ">" +
            optionsHtml(
                catalog.reporter_agencies,
                incident.reported_by_agency,
                "Not yet recorded"
            ) +
            "</select></div></div>" +
            agencyHtml(incident) +
            '<div style="margin-top:0.85rem;">' +
            fieldLabel("hs-loc", "Location") +
            "</div>" +
            '<div class="rf-hs-typeahead">' +
            '<input id="hs-loc" class="form-control form-control-sm" autocomplete="off" value="' +
            esc(incident.location_text || "") +
            '" placeholder="Search course locations or describe where the participant is"' +
            ro(incident) +
            ">" +
            '<input type="hidden" id="hs-loc-id" value="' +
            esc(locLinked) +
            '">' +
            '<div id="hs-loc-menu" class="rf-hs-typeahead-menu" hidden></div></div>' +
            '<div style="margin-top:0.7rem;">' +
            fieldLabel("hs-desc", "Initial report") +
            "</div>" +
            '<textarea id="hs-desc" class="form-control form-control-sm" rows="3" placeholder="What happened and what assistance was requested?"' +
            ro(incident) +
            ">" +
            esc(incident.description || "") +
            "</textarea>" +
            called911Control(incident) +
            tile(
                "details",
                "Reported problem",
                '<div class="rf-hs-label">Reported problem — select all that apply</div>' +
                    checks(
                        "incident_types",
                        catalog.incident_types,
                        incident.incident_types,
                        incident
                    ) +
                    '<div id="hs-type-other-wrap" class="rf-hs-other-wrap"' +
                    ((incident.incident_types || []).indexOf("other") === -1
                        ? " hidden"
                        : "") +
                    ">" +
                    fieldLabel("hs-type-other", "Other reported problem") +
                    '<input id="hs-type-other" class="form-control form-control-sm" maxlength="120" placeholder="Short description" value="' +
                    esc(incident.incident_type_other || "") +
                    '"' +
                    ro(incident) +
                    "></div>",
                summaryFromIncident(incident)
            ) +
            tile(
                "outcome",
                "Close case",
                fieldLabel("hs-outcome", "Outcome (required)") +
                    '<select id="hs-outcome" class="form-select form-select-sm"' +
                    dis(incident) +
                    ">" +
                    optionsHtml(
                        catalog.outcomes,
                        incident.outcome,
                        "Choose an outcome…"
                    ) +
                    "</select>" +
                    '<div class="rf-hs-label" style="margin-top:0.85rem;">Care provided — reported by the care team</div>' +
                    '<p class="rf-hs-meta">Select the care reported to the EOC. Leave details unrecorded if they are not known.</p>' +
                    '<div id="hs-care-options">' +
                    careOptionsInner(incident.care_types, incident) +
                    "</div>" +
                    '<div class="rf-hs-reporter-row" style="margin-top:0.85rem;">' +
                    "<div>" +
                    fieldLabel("hs-by-name", "Closed by (required)") +
                    '<input id="hs-by-name" class="form-control form-control-sm" placeholder="Name" value="' +
                    esc(incident.completed_by_name || "") +
                    '"' +
                    ro(incident) +
                    "></div>" +
                    "<div>" +
                    fieldLabel("hs-by-agency", "Roles/Organization") +
                    '<select id="hs-by-agency" class="form-select form-select-sm"' +
                    dis(incident) +
                    ">" +
                    optionsHtml(
                        catalog.reporter_agencies,
                        reporterAgencyId(incident.completed_by_agency),
                        "Not yet recorded"
                    ) +
                    "</select></div></div>" +
                    (locked
                        ? ""
                        : '<button type="button" class="btn btn-sm btn-primary" style="margin-top:0.75rem;" id="hs-close">Close case</button>' +
                          '<p id="hs-close-hint" class="rf-hs-meta rf-hs-close-hint" hidden></p>')
            ) +
            "</div>" +
            '<div class="rf-hs-activity-col">' +
            '<h3 class="rf-hs-work-title">Case log</h3>' +
            (locked
                ? ""
                : '<div class="rf-hs-note-add">' +
                  fieldLabel("hs-note", "Add an update") +
                  '<textarea id="hs-note" class="form-control form-control-sm" rows="4">' +
                  esc(draft) +
                  "</textarea>" +
                  '<div class="rf-hs-note-add-row">' +
                  '<span id="hs-note-status" class="rf-hs-meta"></span>' +
                  '<button type="button" class="btn btn-sm btn-primary" id="hs-save-note">Add to case log</button></div></div>') +
            notesHtml(incident) +
            "</div></div>" +
            '<div class="rf-hs-case-foot">' +
            '<div class="rf-hs-save-status" role="status" aria-live="polite">' +
            '<span id="hs-save-status"></span> ' +
            '<button type="button" class="btn btn-sm" id="hs-save-retry" hidden>Retry</button></div>' +
            '<div class="rf-hs-actions">' +
            '<button type="button" class="btn btn-sm" id="hs-print">Print</button>' +
            (locked
                ? ""
                : '<button type="button" class="btn btn-sm" id="hs-save">Save case</button>' +
                  '<button type="button" class="btn btn-sm" id="hs-review-close">Review &amp; close case</button>') +
            "</div></div></div>";
        savedForm = formPayload();
        ui.savePhase = "saved";
        updateSaveStatus();
    }

    function formPayload() {
        var payload = {
            description: val("hs-desc"),
            reported_by_name: val("hs-report-name"),
            reported_by_agency: val("hs-report-agency"),
            location_text: val("hs-loc"),
            location_loc_id: val("hs-loc-id"),
            incident_types: selected("incident_types"),
            incident_type_other: val("hs-type-other"),
            care_types: selected("care_types"),
            care_note: val("hs-care-note"),
            called_911: val("hs-911"),
            outcome: val("hs-outcome"),
            completed_by_name: val("hs-by-name"),
            completed_by_agency: val("hs-by-agency"),
            assigned_to: qs("#hs-assigned")
                ? val("hs-assigned")
                : String((current && current.assigned_to) || ""),
            assigned_note: val("hs-assign-note"),
        };
        return payload;
    }

    function setIncidentQuery(id) {
        var params = new URLSearchParams(window.location.search);
        if (id) params.set("incident_id", id);
        else params.delete("incident_id");
        var next = window.location.pathname + "?" + params.toString();
        window.history.replaceState({}, "", next);
    }

    function showWorkspace() {
        qs("#rf-hs-title").textContent = "Incidents";
        qs("#rf-hs-workspace").hidden = false;
        qs("#rf-hs-empty").hidden = true;
    }

    function applyLists(body) {
        catalog = body.catalog || catalog;
        lists = {
            active: body.active || [],
            closed: body.closed || [],
            counts: body.counts || { active: 0, closed: 0 },
        };
        renderQueue();
    }

    function loadLocations() {
        return jsonFetch(apiUrl("/api/execute/locations"), {
            credentials: "same-origin",
        })
            .then(function (body) {
                locations = body.locations || [];
            })
            .catch(function () {
                locations = [];
            });
    }

    function loadLists() {
        return jsonFetch(apiUrl("/api/execute/incidents"), {
            credentials: "same-origin",
        }).then(function (body) {
            applyLists(body);
        });
    }

    function loadCase(id) {
        return jsonFetch(apiUrl("/api/execute/incidents/" + encodeURIComponent(id)), {
            credentials: "same-origin",
        }).then(function (body) {
            catalog = body.catalog || catalog;
            renderCase(body.incident);
            renderQueue();
        });
    }

    function refreshAfterMutation(incident) {
        catalog = catalog || {};
        renderCase(incident);
        return loadLists();
    }

    function persistForm(payload) {
        if (!current || isClosed(current)) return Promise.resolve(current);
        var body = payload || formPayload();
        if (!payload && !isDirty()) return Promise.resolve(current);
        return jsonFetch(
            apiUrl("/api/execute/incidents/" + encodeURIComponent(current.incident_id)),
            {
                method: "PUT",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            }
        ).then(function (resp) {
            current = resp.incident;
            return resp.incident;
        });
    }

    function saveWithStatus(payload) {
        if (ui.saving) return ui.saving;
        showError("");
        var required = requireSaveFields();
        if (required) {
            ui.savePhase = "unsaved";
            updateSaveStatus();
            return Promise.reject(new Error(required));
        }
        ui.savePhase = "saving";
        updateSaveStatus();
        captureDraft();
        ui.saving = persistForm(payload)
            .then(function (incident) {
                ui.saving = null;
                ui.savePhase = "saved";
                if (!incident) {
                    updateSaveStatus();
                    return incident;
                }
                return refreshAfterMutation(incident);
            })
            .catch(function (err) {
                ui.saving = null;
                ui.savePhase = "error";
                updateSaveStatus();
                throw err;
            });
        return ui.saving;
    }

    function saveForm() {
        if (!current || isClosed(current)) return Promise.resolve(current);
        if (!isDirty()) {
            ui.savePhase = "saved";
            updateSaveStatus();
            return Promise.resolve(current);
        }
        return saveWithStatus();
    }

    function saveNote() {
        var text = String(val("hs-note") || "").trim();
        if (!current || isClosed(current) || !text) return Promise.resolve();
        if (ui.saving) return ui.saving;
        var incidentId = current.incident_id;
        captureDraft();
        showError("");
        ui.savePhase = "saving";
        updateSaveStatus();
        ui.saving = (isDirty() ? persistForm() : Promise.resolve(current))
            .then(function () {
                return jsonFetch(
                    apiUrl(
                        "/api/execute/incidents/" +
                            encodeURIComponent(incidentId) +
                            "/notes"
                    ),
                    {
                        method: "POST",
                        credentials: "same-origin",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ text: text }),
                    }
                );
            })
            .then(function (body) {
                ui.saving = null;
                ui.noteDrafts[incidentId] = "";
                var composer = qs("#hs-note");
                if (composer) composer.value = "";
                ui.savePhase = "saved";
                return refreshAfterMutation(body.incident);
            })
            .catch(function (err) {
                ui.saving = null;
                ui.savePhase = "error";
                updateSaveStatus();
                throw err;
            });
        return ui.saving;
    }

    function assignCare() {
        showError("");
        if (!current || isClosed(current)) return Promise.resolve();
        var to = val("hs-assigned");
        if (!to) {
            showError("Pick the care agency currently attending.");
            return Promise.resolve();
        }
        var payload = formPayload();
        payload.assigned_to = to;
        if (ui.saving) return ui.saving;
        ui.savePhase = "saving";
        updateSaveStatus();
        captureDraft();
        ui.saving = persistForm(payload)
            .then(function (incident) {
                ui.saving = null;
                ui.savePhase = "saved";
                return refreshAfterMutation(incident);
            })
            .catch(function (err) {
                ui.saving = null;
                ui.savePhase = "error";
                updateSaveStatus();
                throw err;
            });
        return ui.saving;
    }

    function recordTransfer() {
        showError("");
        if (!current || isClosed(current)) return Promise.resolve();
        var to = val("hs-xfer-to");
        if (!to) {
            showError("Pick the agency taking over care.");
            return Promise.resolve();
        }
        if (String(current.assigned_to || "") === to) {
            showError("Already assigned to that care agency.");
            return Promise.resolve();
        }
        var incidentId = current.incident_id;
        var extra = val("hs-xfer-note");
        captureDraft();
        var afterFields = isDirty() ? persistForm() : Promise.resolve(current);
        ui.savePhase = "saving";
        updateSaveStatus();
        return afterFields
            .then(function () {
                return jsonFetch(
                    apiUrl(
                        "/api/execute/incidents/" +
                            encodeURIComponent(incidentId) +
                            "/transfer"
                    ),
                    {
                        method: "POST",
                        credentials: "same-origin",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ to_agency: to, text: extra }),
                    }
                );
            })
            .then(function (body) {
                ui.xferOpen = false;
                ui.savePhase = "saved";
                return refreshAfterMutation(body.incident);
            })
            .catch(function (err) {
                ui.savePhase = "error";
                updateSaveStatus();
                throw err;
            });
    }

    function reviewClose() {
        if (!current || isClosed(current)) return;
        expandTile("outcome");
        var outcome = qs("#hs-outcome");
        if (outcome) {
            outcome.focus();
            if (outcome.scrollIntoView) outcome.scrollIntoView({ block: "nearest" });
        }
    }

    function hideNavModal() {
        var modal = qs("#hs-nav-modal");
        if (modal) modal.hidden = true;
        ui.pendingNav = null;
    }

    function showNavModal(kind, id) {
        ui.pendingNav = { type: kind, id: id };
        var modal = qs("#hs-nav-modal");
        var title = qs("#hs-nav-title");
        var detail = qs("#hs-nav-detail");
        var saveBtn = qs("#hs-nav-save");
        var discardBtn = qs("#hs-nav-discard");
        if (!modal) return;
        var bits = [];
        var fields = dirtyFieldLabels();
        var draft = String(currentDraft() || "").trim();
        if (fields.length) bits.push("Unsaved: " + fields.join(", "));
        if (draft) bits.push("Update not added to the case log");
        if (kind === "switch" && draft) {
            bits.push("The update stays a draft until you add it to the case log");
        }
        if (!bits.length) bits.push("Unsaved work");
        if (title) {
            title.textContent =
                kind === "close" ? "Resolve before closing" : "Unsaved work on this case";
        }
        if (detail) detail.textContent = bits.join(". ") + ".";
        if (saveBtn) {
            saveBtn.textContent =
                kind === "close"
                    ? draft
                        ? "Add note, save & close"
                        : "Save & close"
                    : "Save case changes & switch";
        }
        if (discardBtn) {
            discardBtn.textContent = kind === "close" ? "Discard & close" : "Discard changes";
        }
        modal.hidden = false;
        if (saveBtn) saveBtn.focus();
    }

    function proceedSwitch(id) {
        hideNavModal();
        setIncidentQuery(id);
        return loadCase(id);
    }

    function openCase(id) {
        if (!id) return Promise.resolve();
        if (current && current.incident_id === id) return Promise.resolve();
        captureDraft();
        if (current && hasPendingWork()) {
            showNavModal("switch", id);
            return Promise.resolve();
        }
        return proceedSwitch(id);
    }

    function performClose() {
        if (!current || isClosed(current)) return Promise.resolve();
        return jsonFetch(
            apiUrl(
                "/api/execute/incidents/" +
                    encodeURIComponent(current.incident_id) +
                    "/close"
            ),
            { method: "POST", credentials: "same-origin" }
        ).then(function (body) {
            ui.noteDrafts[current.incident_id] = "";
            hideNavModal();
            return refreshAfterMutation(body.incident);
        });
    }

    function closeIncident() {
        if (!current || isClosed(current)) return Promise.resolve();
        if (!canCloseCase()) {
            expandTile("outcome");
            showError(
                "To close, choose an outcome, Closed by, and Roles/Organization."
            );
            return Promise.resolve();
        }
        captureDraft();
        if (String(currentDraft() || "").trim()) {
            showNavModal("close");
            return Promise.resolve();
        }
        if (isDirty()) {
            return saveForm().then(function () {
                return performClose();
            });
        }
        return performClose();
    }

    function navStay() {
        hideNavModal();
        return Promise.resolve();
    }

    function navDiscard() {
        var pending = ui.pendingNav;
        if (!pending) return Promise.resolve();
        if (current) ui.noteDrafts[current.incident_id] = "";
        savedForm = formPayload();
        if (pending.type === "switch") return proceedSwitch(pending.id);
        if (pending.type === "close") {
            savedForm = null;
            return performClose();
        }
        hideNavModal();
        return Promise.resolve();
    }

    function navSave() {
        var pending = ui.pendingNav;
        if (!pending) return Promise.resolve();
        var work =
            pending.type === "close" && String(currentDraft() || "").trim()
                ? saveNote()
                : saveForm();
        return work.then(function () {
            if (pending.type === "switch") return proceedSwitch(pending.id);
            return performClose();
        });
    }

    function pickLocation(label, locId) {
        var input = qs("#hs-loc");
        var hidden = qs("#hs-loc-id");
        if (input) input.value = label;
        if (hidden) hidden.value = locId || "";
        showLocMenu(false);
        if (ui.savePhase !== "saving") ui.savePhase = "unsaved";
        updateSaveStatus();
    }

    function bind() {
        if (!runId()) {
            qs("#rf-hs-empty").hidden = false;
            return;
        }
        showWorkspace();
        var workspace = qs("#rf-hs-workspace");
        workspace.addEventListener("click", function (ev) {
            var locBtn = ev.target.closest("[data-loc-label]");
            if (locBtn) {
                pickLocation(
                    locBtn.getAttribute("data-loc-label") || "",
                    locBtn.getAttribute("data-loc-id") || ""
                );
                return;
            }
            var fold = ev.target.closest("[data-fold]");
            if (fold) {
                var kind = fold.getAttribute("data-fold");
                if (kind === "active") ui.activeOpen = !ui.activeOpen;
                if (kind === "closed") ui.closedOpen = !ui.closedOpen;
                renderQueue();
                return;
            }
            var tileBtn = ev.target.closest("[data-tile]");
            if (tileBtn) {
                var name = tileBtn.getAttribute("data-tile");
                ui.tiles[name] = !ui.tiles[name];
                var body = qs('[data-tile-body="' + name + '"]');
                if (body) body.hidden = !ui.tiles[name];
                tileBtn.setAttribute("aria-expanded", ui.tiles[name] ? "true" : "false");
                var mark = tileBtn.querySelector(".rf-hs-chevron");
                if (mark) mark.textContent = chevron(ui.tiles[name]);
                updateSaveStatus();
                return;
            }
            var activityBtn = ev.target.closest("[data-activity]");
            if (activityBtn && current) {
                var notes = (current.notes || []).slice().reverse();
                var note = notes[Number(activityBtn.getAttribute("data-activity"))];
                if (note) showActivityModal(note, current);
                return;
            }
            var openBtn = ev.target.closest("[data-open]");
            if (openBtn) {
                var id = openBtn.getAttribute("data-open");
                openCase(id).catch(function (err) {
                    showError(err.message || String(err));
                });
                return;
            }
            var targetId = ev.target && ev.target.id;
            var work = Promise.resolve();
            if (targetId === "hs-queue-clear") {
                ui.queueQ = "";
                renderQueue();
                return;
            }
            if (targetId === "hs-print") {
                window.print();
                return;
            }
            if (targetId === "hs-review-close") {
                reviewClose();
                return;
            }
            if (targetId === "hs-care-more") {
                ui.moreCare = !ui.moreCare;
                refreshCareOptions();
                return;
            }
            if (targetId === "hs-xfer-open") {
                ui.xferOpen = true;
                var panel = qs("#hs-xfer-panel");
                if (panel) panel.hidden = false;
                return;
            }
            if (targetId === "hs-xfer-cancel") {
                ui.xferOpen = false;
                var closed = qs("#hs-xfer-panel");
                if (closed) closed.hidden = true;
                return;
            }
            if (targetId === "hs-save") work = saveForm();
            else if (targetId === "hs-save-retry") work = saveForm();
            else if (targetId === "hs-save-note") work = saveNote();
            else if (targetId === "hs-assign") work = assignCare();
            else if (targetId === "hs-xfer-confirm") work = recordTransfer();
            else if (targetId === "hs-close") work = closeIncident();
            else return;
            work.catch(function (err) {
                showError(err.message || String(err));
            });
        });
        workspace.addEventListener("change", function (ev) {
            if (ev.target && ev.target.name === "incident_types") {
                applyProblemExclusive(ev.target);
                var wrap = qs("#hs-type-other-wrap");
                if (wrap) {
                    wrap.hidden =
                        selected("incident_types").indexOf("other") === -1;
                }
                refreshCareOptions();
            }
            if (ev.target && ev.target.name === "care_types") {
                applyCareExclusive(ev.target);
                var careOther = qs("#hs-care-other-wrap");
                if (careOther) {
                    careOther.hidden =
                        selected("care_types").indexOf("other_care") === -1;
                }
            }
            if (ev.target && ev.target.id !== "hs-queue-q" && ev.target.id !== "hs-xfer-to") {
                if (ui.savePhase !== "saving") ui.savePhase = "unsaved";
                updateSaveStatus();
            }
        });
        workspace.addEventListener("input", function (ev) {
            if (ev.target && ev.target.id === "hs-queue-q") {
                ui.queueQ = ev.target.value;
                renderQueue();
                return;
            }
            if (ev.target && ev.target.id === "hs-loc") {
                var hidden = qs("#hs-loc-id");
                if (hidden) hidden.value = "";
                showLocMenu(true);
            }
            if (ev.target && (ev.target.id === "hs-note" || ev.target.id === "hs-xfer-note")) {
                updateSaveStatus();
                return;
            }
            if (ui.savePhase !== "saving") ui.savePhase = "unsaved";
            updateSaveStatus();
        });
        workspace.addEventListener("focusin", function (ev) {
            if (ev.target && ev.target.id === "hs-loc") showLocMenu(true);
        });
        workspace.addEventListener("keydown", function (ev) {
            if (ev.target && ev.target.id === "hs-loc" && ev.key === "Escape") {
                showLocMenu(false);
            }
            if (ev.target && ev.target.id === "hs-loc" && ev.key === "Enter") {
                ev.preventDefault();
                var hits = locHits(val("hs-loc"));
                if (hits.length) {
                    pickLocation(hits[0].loc_label || "", hits[0].loc_id == null ? "" : String(hits[0].loc_id));
                } else {
                    showLocMenu(false);
                }
            }
            if (
                ev.target &&
                ev.target.id === "hs-note" &&
                ev.key === "Enter" &&
                (ev.metaKey || ev.ctrlKey)
            ) {
                ev.preventDefault();
                saveNote().catch(function (err) {
                    showError(err.message || String(err));
                });
            }
        });
        document.addEventListener("mousedown", function (ev) {
            if (!ev.target.closest(".rf-hs-typeahead")) showLocMenu(false);
        });
        var activityModal = qs("#hs-activity-modal");
        if (activityModal) {
            activityModal.addEventListener("click", function (ev) {
                var activityId = ev.target && ev.target.id;
                if (activityId === "hs-activity-close" || activityId === "hs-activity-modal") {
                    hideActivityModal();
                }
            });
        }
        document.addEventListener("keydown", function (ev) {
            if (ev.key !== "Escape") return;
            var openActivity = qs("#hs-activity-modal");
            if (openActivity && !openActivity.hidden) {
                hideActivityModal();
                ev.preventDefault();
            }
        });
        var navModal = qs("#hs-nav-modal");
        if (navModal) {
            navModal.addEventListener("click", function (ev) {
                var navId = ev.target && ev.target.id;
                var navWork = Promise.resolve();
                if (navId === "hs-nav-stay") navWork = navStay();
                else if (navId === "hs-nav-discard") navWork = navDiscard();
                else if (navId === "hs-nav-save") navWork = navSave();
                else return;
                navWork.catch(function (err) {
                    showError(err.message || String(err));
                });
            });
        }
        window.addEventListener("beforeunload", function (ev) {
            captureDraft();
            if (!hasPendingWork()) return;
            ev.preventDefault();
            ev.returnValue = "";
        });
        var startId = incidentId();
        Promise.all([loadLocations(), loadLists()])
            .then(function () {
                if (startId) return loadCase(startId);
                renderCase(null);
                return null;
            })
            .catch(function (err) {
                showError(err.message || String(err));
            });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
