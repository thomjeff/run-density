/* Execute Participants table (Issue #911). UI → API → JSON only. */
(function () {
    "use strict";

    var PAGE_SIZES = [25, 50, 100];
    var pageSize = 25;
    var INCIDENT_ICON =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
        '<polyline points="14 2 14 8 20 8"/>' +
        '<line x1="12" y1="18" x2="12" y2="12"/>' +
        '<line x1="9" y1="15" x2="15" y2="15"/>' +
        "</svg>";
    var allRows = [];
    var conditionLabels = [];
    var selectedConditions = {};
    var noBibOnly = false;
    var query = "";
    var page = 1;
    var expandedId = "";
    var menuOpen = false;
    var sortKey = "bib";
    var sortDir = "asc";
    var searchTimer = null;
    var activeByReg = {};

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function runId() {
        var ctx = window.runflowExecuteContext;
        if (ctx && ctx.active && ctx.run_id) return String(ctx.run_id).trim();
        var params = new URLSearchParams(window.location.search);
        return (
            params.get("run_id") ||
            (window.runflowDay && window.runflowDay.run_id) ||
            localStorage.getItem("selected_run_id") ||
            ""
        ).trim();
    }

    function dayCode() {
        var ctx = window.runflowExecuteContext;
        if (ctx && ctx.active && ctx.weekday_code) {
            return String(ctx.weekday_code).trim();
        }
        return (
            (window.runflowDay && window.runflowDay.selected) ||
            localStorage.getItem("selected_day") ||
            ""
        ).trim();
    }

    function apiUrl(path) {
        var url = path + "?run_id=" + encodeURIComponent(runId());
        var day = dayCode();
        if (day) url += "&day=" + encodeURIComponent(day);
        return url;
    }

    function incidentsHref(incidentId) {
        var url = "/execute/incidents?run_id=" + encodeURIComponent(runId());
        var day = dayCode();
        if (day) url += "&day=" + encodeURIComponent(day);
        if (incidentId) url += "&incident_id=" + encodeURIComponent(incidentId);
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

    function selectedList() {
        return conditionLabels.filter(function (label) {
            return selectedConditions[label];
        });
    }

    function hasFilters() {
        return !!(query.trim() || selectedList().length || noBibOnly);
    }

    function rowSearchHay(row) {
        return [
            row.bib,
            row.given_name,
            row.family_name,
            String(row.given_name || "") + " " + String(row.family_name || ""),
            row.phone,
            row.email,
            row.sub_event,
        ]
            .join(" ")
            .toLowerCase();
    }

    function matchesQuery(row, needle) {
        if (!needle) return true;
        return rowSearchHay(row).indexOf(needle) !== -1;
    }

    function matchesConditions(row) {
        var wanted = selectedList();
        if (!wanted.length) return true;
        var hay = (row.medical_conditions || []).join(" ").toLowerCase();
        return wanted.some(function (label) {
            return hay.indexOf(label.toLowerCase()) !== -1;
        });
    }

    function bibKey(row) {
        var bib = String(row.bib || "").trim();
        if (!bib) return [0, 0, ""];
        var n = parseInt(bib, 10);
        if (!isNaN(n) && String(n) === bib) return [1, n, ""];
        return [1, Number.MAX_SAFE_INTEGER, bib.toLowerCase()];
    }

    function compareRows(a, b) {
        var dir = sortDir === "desc" ? -1 : 1;
        var av;
        var bv;
        if (sortKey === "name") {
            av = (a.family_name || "") + " " + (a.given_name || "");
            bv = (b.family_name || "") + " " + (b.given_name || "");
            return av.localeCompare(bv) * dir;
        }
        if (sortKey === "event") {
            return String(a.sub_event || "").localeCompare(String(b.sub_event || "")) * dir;
        }
        if (sortKey === "age") {
            av = parseInt(a.age, 10);
            bv = parseInt(b.age, 10);
            if (isNaN(av) && isNaN(bv)) return 0;
            if (isNaN(av)) return 1;
            if (isNaN(bv)) return -1;
            return (av - bv) * dir;
        }
        av = bibKey(a);
        bv = bibKey(b);
        if (av[0] !== bv[0]) return (av[0] - bv[0]) * dir;
        if (av[1] !== bv[1]) return (av[1] - bv[1]) * dir;
        if (av[2] !== bv[2]) return (av[2] < bv[2] ? -1 : 1) * dir;
        return ((a.family_name || "") + " " + (a.given_name || "")).localeCompare(
            (b.family_name || "") + " " + (b.given_name || "")
        );
    }

    function filteredRows() {
        var needle = query.trim().toLowerCase();
        var rows = allRows.filter(function (row) {
            if (noBibOnly && String(row.bib || "").trim()) return false;
            return matchesQuery(row, needle) && matchesConditions(row);
        });
        rows.sort(compareRows);
        return rows;
    }

    function chipsHtml(list) {
        var items = list || [];
        if (!items.length) return '<span class="rf-hs-meta">—</span>';
        return items
            .map(function (token) {
                return '<span class="rf-hs-chip">' + esc(token) + "</span>";
            })
            .join("");
    }

    function setMenu(open) {
        menuOpen = !!open;
        var menu = qs("#rf-hs-cond-menu");
        var btn = qs("#rf-hs-cond-btn");
        if (!menu || !btn) return;
        menu.hidden = !menuOpen;
        btn.setAttribute("aria-expanded", menuOpen ? "true" : "false");
    }

    function renderConditionMenu() {
        var menu = qs("#rf-hs-cond-menu");
        var btn = qs("#rf-hs-cond-btn");
        if (!menu || !btn) return;
        var n = selectedList().length;
        btn.innerHTML =
            "Conditions" +
            (n ? ' <span class="rf-hs-filter-count">' + n + "</span>" : "");
        btn.classList.toggle("is-on", n > 0);
        if (!conditionLabels.length) {
            menu.innerHTML =
                '<p class="rf-hs-meta" style="padding:0.55rem 0.75rem;margin:0;">None disclosed on this roster</p>';
            return;
        }
        menu.innerHTML =
            '<div class="rf-hs-filter-head">Match any selected</div>' +
            conditionLabels
                .map(function (label) {
                    return (
                        "<label><input type=\"checkbox\" data-cond=\"" +
                        esc(label) +
                        "\"" +
                        (selectedConditions[label] ? " checked" : "") +
                        "> " +
                        esc(label) +
                        "</label>"
                    );
                })
                .join("");
    }

    function renderToolbar() {
        var nobib = qs("#rf-hs-nobib");
        var clear = qs("#rf-hs-clear");
        var qClear = qs("#rf-hs-q-clear");
        if (nobib) {
            nobib.setAttribute("aria-pressed", noBibOnly ? "true" : "false");
            nobib.classList.toggle("is-on", noBibOnly);
        }
        if (clear) clear.hidden = !hasFilters();
        if (qClear) qClear.hidden = !query.trim();
    }

    function renderChips() {
        var root = qs("#rf-hs-chips");
        if (!root) return;
        var wanted = selectedList();
        if (!wanted.length) {
            root.hidden = true;
            root.innerHTML = "";
            return;
        }
        root.hidden = false;
        root.innerHTML = wanted
            .map(function (label) {
                return (
                    '<span class="rf-hs-chip-x">' +
                    esc(label) +
                    ' <button type="button" data-clear-cond="' +
                    esc(label) +
                    '" aria-label="Remove filter">×</button></span>'
                );
            })
            .join("");
    }

    function sortMark(key) {
        if (sortKey !== key) return "";
        return sortDir === "desc" ? " ↓" : " ↑";
    }

    function pageButtons(pageCount) {
        if (pageCount <= 1) return "";
        var start = Math.max(1, page - 2);
        var end = Math.min(pageCount, start + 4);
        start = Math.max(1, end - 4);
        var html =
            '<button type="button" data-page="' +
            (page - 1) +
            '" ' +
            (page <= 1 ? "disabled" : "") +
            ">‹</button>";
        var i;
        for (i = start; i <= end; i += 1) {
            html +=
                '<button type="button" data-page="' +
                i +
                '" class="' +
                (i === page ? "is-current" : "") +
                '">' +
                i +
                "</button>";
        }
        html +=
            '<button type="button" data-page="' +
            (page + 1) +
            '" ' +
            (page >= pageCount ? "disabled" : "") +
            ">›</button>";
        return html;
    }

    function pageSizeSelect() {
        return (
            '<label class="rf-hs-pagesize">Rows <select id="rf-hs-pagesize" aria-label="Rows per page">' +
            PAGE_SIZES.map(function (n) {
                return (
                    "<option value=\"" +
                    n +
                    "\"" +
                    (n === pageSize ? " selected" : "") +
                    ">" +
                    n +
                    "</option>"
                );
            }).join("") +
            "</select></label>"
        );
    }

    function detailHtml(row) {
        var warn = String(row.bib || "").trim()
            ? ""
            : '<p class="rf-hs-warn">Race Roster has no bib for this start. Type the number on the shirt when you start a case.</p>';
        var active = activeByReg[String(row.reg_id)];
        var caseActions =
            '<div class="rf-hs-detail-actions">' +
            '<button type="button" class="btn btn-sm" data-create="' +
            esc(row.reg_id) +
            '">' +
            (active ? "Start another case" : "Start case") +
            "</button>" +
            (active
                ? ' <a class="btn btn-sm" href="' +
                  esc(incidentsHref(active.incident_id)) +
                  '">View active case</a>'
                : "") +
            "</div>";
        return (
            '<tr class="rf-hs-detail"><td colspan="7">' +
            warn +
            '<div class="rf-hs-detail-grid">' +
            "<div><div class=\"rf-hs-label\">Emergency contact</div><div>" +
            esc(row.emerg_name || "—") +
            (row.emerg_phone ? " · " + esc(row.emerg_phone) : "") +
            "</div></div>" +
            "<div><div class=\"rf-hs-label\">Phone / email</div><div>" +
            esc(row.phone || "—") +
            " · " +
            esc(row.email || "—") +
            "</div></div>" +
            "<div><div class=\"rf-hs-label\">Disclosed conditions</div><div class=\"rf-hs-chip-row\">" +
            chipsHtml(row.medical_conditions) +
            "</div></div>" +
            "<div><div class=\"rf-hs-label\">Details</div><div>" +
            esc(row.medical_note || "—") +
            "</div>" +
            '<div class="rf-hs-meta" style="margin-top:0.25rem;">Avoid giving or doing: ' +
            esc(row.medical_avoid || "—") +
            "</div></div></div>" +
            caseActions +
            "</td></tr>"
        );
    }

    function chevron(open) {
        return (
            '<span class="rf-hs-chevron' +
            (open ? " is-open" : "") +
            '" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="m9 6 6 6-6 6"/></svg></span>'
        );
    }

    function condCell(row) {
        var n = (row.medical_conditions || []).length;
        if (!n) return '<span class="rf-hs-meta">—</span>';
        return '<span class="rf-hs-cond-n">' + n + "</span>";
    }

    function renderTable() {
        var root = qs("#rf-hs-results");
        var status = qs("#rf-hs-status");
        if (!root) return;
        renderConditionMenu();
        renderToolbar();
        renderChips();
        var rows = filteredRows();
        var pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
        if (page > pageCount) page = pageCount;
        var start = (page - 1) * pageSize;
        var slice = rows.slice(start, start + pageSize);
        if (status) {
            status.textContent = allRows.length
                ? rows.length === allRows.length
                    ? allRows.length + " starts"
                    : rows.length + " of " + allRows.length
                : "";
        }
        if (!allRows.length) {
            root.innerHTML =
                '<div class="rf-hs-empty-inline"><h3>Import the night-before CSV</h3>' +
                "<p>The roster appears here after expo bibs are in the export.</p></div>";
            return;
        }
        if (!rows.length) {
            root.innerHTML =
                '<div class="rf-hs-empty-inline"><h3>No matching starts</h3>' +
                "<p>Clear a filter, or search by name if the bib was never tied in Race Roster.</p></div>";
            return;
        }
        var body = slice
            .map(function (row) {
                var bib = String(row.bib || "").trim();
                var open = expandedId === String(row.reg_id);
                var bibCell = bib
                    ? '<span class="rf-hs-bib">' + esc(bib) + "</span>"
                    : '<span class="rf-hs-missing">No bib</span>';
                var main =
                    "<tr data-reg=\"" +
                    esc(row.reg_id) +
                    "\" class=\"" +
                    (open ? "is-open" : "") +
                    "\" title=\"Show medical and emergency details\">" +
                    "<td class=\"rf-hs-td-chevron\">" +
                    chevron(open) +
                    "</td>" +
                    "<td>" +
                    bibCell +
                    "</td>" +
                    '<td><div class="rf-hs-name">' +
                    esc(row.given_name) +
                    " " +
                    esc(row.family_name) +
                    "</div></td>" +
                    "<td>" +
                    esc(row.sub_event || "—") +
                    "</td>" +
                    "<td class=\"rf-hs-td-age\">" +
                    esc(row.age || "—") +
                    (row.sex ? " · " + esc(row.sex) : "") +
                    "</td>" +
                    "<td>" +
                    condCell(row) +
                    "</td>" +
                    '<td class="course-map-action-cell">' +
                    (function () {
                        var active = activeByReg[String(row.reg_id)];
                        if (active) {
                            return (
                                '<a class="course-map-action-btn" href="' +
                                esc(incidentsHref(active.incident_id)) +
                                '" title="View active case" aria-label="View active case">' +
                                INCIDENT_ICON +
                                "</a>"
                            );
                        }
                        return (
                            '<button type="button" class="course-map-action-btn" data-create="' +
                            esc(row.reg_id) +
                            '" title="Start case" aria-label="Start case">' +
                            INCIDENT_ICON +
                            "</button>"
                        );
                    })() +
                    "</td></tr>";
                return open ? main + detailHtml(row) : main;
            })
            .join("");
        var from = start + 1;
        var to = start + slice.length;
        root.innerHTML =
            '<div class="rf-hs-table-scroll"><table class="rf-hs-table">' +
            "<thead><tr>" +
            "<th class=\"rf-hs-th-chevron\"></th>" +
            '<th data-sort="bib">Bib' +
            sortMark("bib") +
            "</th>" +
            '<th data-sort="name">Name' +
            sortMark("name") +
            "</th>" +
            '<th data-sort="event">Event' +
            sortMark("event") +
            "</th>" +
            '<th data-sort="age">Age' +
            sortMark("age") +
            "</th>" +
            "<th>Conditions</th><th class=\"course-map-action-cell\">Actions</th></tr></thead>" +
            "<tbody>" +
            body +
            "</tbody></table></div>" +
            '<div class="rf-hs-pager"><span class="rf-hs-meta">' +
            from +
            "–" +
            to +
            " of " +
            rows.length +
            "</span><div class=\"rf-hs-pager-end\">" +
            pageSizeSelect() +
            '<div class="rf-hs-pages">' +
            pageButtons(pageCount) +
            "</div></div></div>";
    }

    function resetFilters() {
        query = "";
        selectedConditions = {};
        noBibOnly = false;
        page = 1;
        expandedId = "";
        var input = qs("#rf-hs-q");
        if (input) input.value = "";
        renderTable();
    }

    function loadActiveCases() {
        return fetch(apiUrl("/api/execute/incidents"), {
            credentials: "same-origin",
        })
            .then(function (resp) {
                return resp.json();
            })
            .then(function (body) {
                activeByReg = {};
                ((body && body.active) || []).forEach(function (row) {
                    var reg = String(row.reg_id || "");
                    if (reg && !activeByReg[reg]) activeByReg[reg] = row;
                });
            })
            .catch(function () {
                activeByReg = {};
            });
    }

    function loadRoster() {
        showError("");
        return fetch(apiUrl("/api/execute/participants"), {
            credentials: "same-origin",
        })
            .then(function (resp) {
                return resp.json().then(function (body) {
                    if (!resp.ok) throw new Error(body.detail || "Lookup failed.");
                    return body;
                });
            })
            .then(function (body) {
                allRows = body.participants || [];
                conditionLabels = body.conditions || [];
                page = 1;
                return loadActiveCases();
            })
            .then(function () {
                renderTable();
            })
            .catch(function (err) {
                showError(err.message || String(err));
            });
    }

    function createIncident(regId) {
        showError("");
        return fetch(apiUrl("/api/execute/incidents"), {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reg_id: regId }),
        })
            .then(function (resp) {
                return resp.json().then(function (body) {
                    if (!resp.ok) throw new Error(body.detail || "Could not create incident.");
                    return body;
                });
            })
            .then(function (body) {
                var id = body.incident && body.incident.incident_id;
                var url = "/execute/incidents?run_id=" + encodeURIComponent(runId());
                var day = dayCode();
                if (day) url += "&day=" + encodeURIComponent(day);
                if (id) url += "&incident_id=" + encodeURIComponent(id);
                window.location.href = url;
            })
            .catch(function (err) {
                showError(err.message || String(err));
            });
    }

    function importCsv(file) {
        showError("");
        var data = new FormData();
        data.append("file", file);
        return fetch(apiUrl("/api/execute/participants/import"), {
            method: "POST",
            credentials: "same-origin",
            body: data,
        })
            .then(function (resp) {
                return resp.json().then(function (body) {
                    if (!resp.ok) {
                        var detail = body.detail;
                        if (Array.isArray(detail)) detail = detail[0] && detail[0].msg;
                        throw new Error(detail || "Import failed.");
                    }
                    return body;
                });
            })
            .then(function () {
                resetFilters();
                return loadRoster();
            })
            .catch(function (err) {
                showError(err.message || String(err));
            });
    }

    function startWorkspace() {
        if (!runId()) {
            qs("#rf-hs-empty").hidden = false;
            return;
        }
        qs("#rf-hs-empty").hidden = true;
        qs("#rf-hs-workspace").hidden = false;
        qs("#rf-hs-import").addEventListener("click", function () {
            qs("#rf-hs-file").click();
        });
        qs("#rf-hs-file").addEventListener("change", function (ev) {
            var file = ev.target.files && ev.target.files[0];
            ev.target.value = "";
            if (file) importCsv(file);
        });
        qs("#rf-hs-q").addEventListener("input", function (ev) {
            query = ev.target.value || "";
            page = 1;
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(renderTable, 80);
        });
        qs("#rf-hs-q").addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") {
                ev.preventDefault();
                if (query) {
                    query = "";
                    ev.target.value = "";
                    page = 1;
                    renderTable();
                }
            }
        });
        qs("#rf-hs-q-clear").addEventListener("click", function () {
            query = "";
            qs("#rf-hs-q").value = "";
            page = 1;
            renderTable();
            qs("#rf-hs-q").focus();
        });
        qs("#rf-hs-nobib").addEventListener("click", function () {
            noBibOnly = !noBibOnly;
            page = 1;
            renderTable();
        });
        qs("#rf-hs-clear").addEventListener("click", function () {
            resetFilters();
        });
        qs("#rf-hs-cond-btn").addEventListener("click", function (ev) {
            ev.stopPropagation();
            setMenu(!menuOpen);
        });
        qs("#rf-hs-cond-menu").addEventListener("click", function (ev) {
            ev.stopPropagation();
        });
        qs("#rf-hs-cond-menu").addEventListener("change", function (ev) {
            var box = ev.target.closest("input[data-cond]");
            if (!box) return;
            var label = box.getAttribute("data-cond");
            if (box.checked) selectedConditions[label] = true;
            else delete selectedConditions[label];
            page = 1;
            renderTable();
        });
        document.addEventListener("click", function () {
            if (menuOpen) setMenu(false);
        });
        qs("#rf-hs-chips").addEventListener("click", function (ev) {
            var clear = ev.target.closest("[data-clear-cond]");
            if (!clear) return;
            delete selectedConditions[clear.getAttribute("data-clear-cond")];
            page = 1;
            renderTable();
        });
        qs("#rf-hs-results").addEventListener("change", function (ev) {
            if (ev.target.id !== "rf-hs-pagesize") return;
            pageSize = parseInt(ev.target.value, 10) || 25;
            page = 1;
            renderTable();
        });
        qs("#rf-hs-results").addEventListener("click", function (ev) {
            var viewCase = ev.target.closest("a[href]");
            if (
                viewCase &&
                viewCase.closest(".course-map-action-cell, .rf-hs-detail-actions")
            ) {
                ev.stopPropagation();
                return;
            }
            var create = ev.target.closest("[data-create]");
            if (create) {
                ev.preventDefault();
                ev.stopPropagation();
                createIncident(create.getAttribute("data-create"));
                return;
            }
            var sortTh = ev.target.closest("th[data-sort]");
            if (sortTh) {
                var key = sortTh.getAttribute("data-sort");
                if (sortKey === key) sortDir = sortDir === "asc" ? "desc" : "asc";
                else {
                    sortKey = key;
                    sortDir = "asc";
                }
                page = 1;
                renderTable();
                return;
            }
            var pageBtn = ev.target.closest("[data-page]");
            if (pageBtn && !pageBtn.disabled) {
                page = parseInt(pageBtn.getAttribute("data-page"), 10) || 1;
                expandedId = "";
                renderTable();
                return;
            }
            var row = ev.target.closest("tr[data-reg]");
            if (!row) return;
            var id = row.getAttribute("data-reg");
            expandedId = expandedId === id ? "" : id;
            renderTable();
        });
        loadRoster();
    }

    function bind() {
        if (window.runflowExecuteContext && window.runflowExecuteContext.resolved) {
            startWorkspace();
            return;
        }
        document.addEventListener(
            "runflow:execute-context",
            startWorkspace,
            { once: true }
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
