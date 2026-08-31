/* Execute race-day board (Issue #893). UI → API → JSON only. */
(function () {
    "use strict";

    var board = null;
    var tickTimer = null;
    var filterText = "";
    var zoneFilter = "";
    var mapInstance = null;
    var mapFocusLocId = null;
    var lastRefreshAt = 0;
    var expanded = {
        closed: false,
        reopen_next: false,
        reopened: false,
    };
    var pendingReopenId = null;
    var reopenError = null;
    var unpausing = false;
    var COLUMN_PREVIEW = 10;
    var BOARD_REFRESH_MS = 5 * 60 * 1000;
    var STATUS_COLORS = {
        closed: "#4b5563",
        reopen_next: "#1d4ed8",
        reopened: "#047857",
    };

    var ICON_PIN =
        '<svg class="rf-ex-icon" width="13" height="13" viewBox="0 0 24 24" aria-hidden="true">' +
        '<path fill="currentColor" d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12zm0-9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"/></svg>';
    var ICON_ROUTE =
        '<svg class="rf-ex-icon" width="13" height="13" viewBox="0 0 24 24" aria-hidden="true">' +
        '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
        'd="M6 19v-6a3 3 0 0 1 3-3h6m0 0-2.2-2.2M15 10l-2.2 2.2"/></svg>';
    var ICON_CHECK =
        '<svg class="rf-ex-icon" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">' +
        '<circle cx="12" cy="12" r="10" fill="#047857"/>' +
        '<path d="M8 12.4l2.6 2.6L16.4 9" fill="none" stroke="#fff" stroke-width="2" ' +
        'stroke-linecap="round" stroke-linejoin="round"/></svg>';
    var ICON_MORE =
        '<svg class="rf-ex-icon" width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">' +
        '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
        'd="M6 9l6 6 6-6"/></svg>';
    var ICON_LESS =
        '<svg class="rf-ex-icon" width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">' +
        '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
        'd="M6 15l6-6 6 6"/></svg>';

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

    function zoneLabel(strip) {
        var z = strip && strip.zone;
        if (z == null || z === "") return "";
        var text = String(z).trim();
        if (!text) return "";
        if (text.charAt(0) === "z" || text.charAt(0) === "Z") {
            return "Z" + text.slice(1).trim();
        }
        return "Z" + text;
    }

    function zoneOptionLabel(code) {
        var rest = String(code || "").replace(/^[zZ]/, "").trim();
        return rest ? "Zone " + rest : "All Zones";
    }

    function resourceLine(resources) {
        if (!resources || !resources.length) return "";
        return resources
            .map(function (r) {
                return esc(r.code) + " " + esc(r.count);
            })
            .join(" · ");
    }

    function metaLine(strip) {
        var parts = [];
        var zone = zoneLabel(strip);
        if (zone) parts.push(esc(zone));
        var resources = resourceLine(strip.resources);
        if (resources) parts.push(resources);
        return parts.join(" · ");
    }

    function stripMatches(strip) {
        if (zoneFilter && zoneLabel(strip) !== zoneFilter) return false;
        if (!filterText) return true;
        var q = filterText.toLowerCase();
        var hay = [
            String(strip.loc_id || ""),
            strip.loc_label || "",
            strip.loc_type || "",
            zoneLabel(strip),
            zoneOptionLabel(zoneLabel(strip)),
            (strip.resources || [])
                .map(function (r) {
                    return r.code + " " + r.count;
                })
                .join(" "),
        ]
            .join(" ")
            .toLowerCase();
        return hay.indexOf(q) !== -1;
    }

    function renderStrip(strip, col, opts) {
        var isNext = col === "reopen_next";
        var isDone = col === "reopened";
        var isFirstNext = !!(opts && opts.firstNext);
        var pending = pendingReopenId === Number(strip.loc_id);
        var err =
            reopenError && Number(reopenError.locId) === Number(strip.loc_id)
                ? reopenError.message
                : "";
        var meta = metaLine(strip);
        var timeCell = isDone
            ? '<span class="rf-ex-time is-actual">' +
              esc(strip.reopened_at || "—") +
              "</span>"
            : '<span class="rf-ex-time' +
              (strip.estimate_passed ? " is-passed" : "") +
              '"><span class="rf-ex-time-label">est.</span>' +
              '<span class="rf-ex-time-value">' +
              esc(strip.loc_end || "—") +
              "</span></span>";
        var action = "";
        if (isNext) {
            action =
                '<button type="button" class="rf-ex-reopen" data-reopen="' +
                esc(strip.loc_id) +
                '"' +
                (pending || pendingReopenId ? " disabled" : "") +
                ">" +
                ICON_ROUTE +
                (pending ? " Reopening…" : " Reopen") +
                "</button>";
        } else if (isDone) {
            action = '<span class="rf-ex-done-icon">' + ICON_CHECK + "</span>";
        }
        var cls = "rf-ex-strip";
        if (isDone) cls += " is-done";
        if (isFirstNext) cls += " is-next";
        return (
            '<article class="' +
            cls +
            '" data-loc-id="' +
            esc(strip.loc_id) +
            '">' +
            '<span class="rf-ex-id">' +
            esc(strip.loc_id) +
            "</span>" +
            '<span class="rf-ex-name"><button type="button" class="rf-ex-map-link" data-map-loc="' +
            esc(strip.loc_id) +
            '">' +
            esc(strip.loc_label) +
            '</button><button type="button" class="rf-ex-pin" data-map-loc="' +
            esc(strip.loc_id) +
            '" aria-label="Open map">' +
            ICON_PIN +
            "</button></span>" +
            timeCell +
            action +
            '<span class="rf-ex-meta">' +
            (meta || "") +
            "</span>" +
            (err
                ? '<span class="rf-ex-strip-error">' + esc(err) + "</span>"
                : "") +
            "</article>"
        );
    }

    function resetColumnExpand() {
        expanded.closed = false;
        expanded.reopen_next = false;
        expanded.reopened = false;
    }

    function moreLabel(id, isExpanded) {
        if (isExpanded) return "Show less";
        if (id === "reopened") return "Show earlier";
        return "Show more";
    }

    function renderColumn(id, title, rows) {
        var visible = rows.filter(stripMatches);
        var shown = visible;
        var more = "";
        var collapseSearch = !filterText;
        var isExpanded = !!expanded[id];
        if (collapseSearch && visible.length > COLUMN_PREVIEW) {
            if (!isExpanded) shown = visible.slice(0, COLUMN_PREVIEW);
            more =
                '<button type="button" class="rf-ex-more" data-toggle-col="' +
                esc(id) +
                '" aria-expanded="' +
                (isExpanded ? "true" : "false") +
                '">' +
                (isExpanded ? ICON_LESS : ICON_MORE) +
                " " +
                moreLabel(id, isExpanded) +
                "</button>";
        }
        var body = shown.length
            ? shown
                  .map(function (row, index) {
                      return renderStrip(row, id, {
                          firstNext: id === "reopen_next" && index === 0,
                      });
                  })
                  .join("") + more
            : '<p class="rf-execute-empty">None.</p>';
        var el = qs('[data-col="' + id + '"]');
        if (!el) return;
        qs(".rf-execute-col-count", el).textContent = String(visible.length);
        qs(".rf-execute-col-body", el).innerHTML = body;
        qs(".rf-execute-col-head", el).setAttribute(
            "aria-label",
            title + ", " + visible.length + " locations"
        );
    }

    function gunInputsHtml(clock) {
        var guns = (clock && (clock.guns || clock.analysis_guns)) || {};
        return Object.keys(guns)
            .sort()
            .map(function (name) {
                var value = guns[name] || "";
                return (
                    "<label>" +
                    esc(name) +
                    ' <input type="time" data-gun="' +
                    esc(name) +
                    '" value="' +
                    esc(value) +
                    '"></label>'
                );
            })
            .join("");
    }

    function renderGuns(clock) {
        var box = qs("#rf-execute-guns");
        if (!box) return;
        if (!clock || clock.guns_accepted) {
            box.hidden = true;
            box.innerHTML = "";
            return;
        }
        box.hidden = false;
        box.innerHTML =
            "<p>Use planned start times for this run, or override them. " +
            "Display Est. Re-Open shifts if a gun changes. " +
            "Plan is not re-run.</p>" +
            '<div class="rf-execute-gun-list">' +
            gunInputsHtml(clock) +
            "</div>" +
            '<div class="rf-ex-confirm-actions">' +
            '<button type="button" class="btn btn-sm btn-primary" id="rf-ex-accept-guns">Accept planned guns</button>' +
            '<button type="button" class="btn btn-sm" id="rf-ex-save-guns">Save override</button>' +
            "</div>";
    }

    function render() {
        if (!board) return;
        qs("#rf-execute-clock-time").textContent = board.now || "—";
        syncRefreshCountdown();
        var cols = board.columns || {};
        renderColumn("closed", "Closed", cols.closed || []);
        renderColumn("reopen_next", "Reopen next", cols.reopen_next || []);
        renderColumn("reopened", "Reopened", cols.reopened || []);
        renderGuns(board.clock);
        syncExportLink();
        syncZoneSelect();
        qs("#rf-execute-workspace").hidden = false;
        qs("#rf-execute-empty").hidden = true;
        qs("#rf-execute-error").hidden = true;
        if (mapModalOpen()) paintStatusMap(mapFocusLocId);
    }

    function allStrips() {
        var cols = (board && board.columns) || {};
        return []
            .concat(cols.closed || [])
            .concat(cols.reopen_next || [])
            .concat(cols.reopened || []);
    }

    function syncZoneSelect() {
        var sel = qs("#rf-execute-zone");
        if (!sel) return;
        var zones = {};
        allStrips().forEach(function (strip) {
            var z = zoneLabel(strip);
            if (z) zones[z] = true;
        });
        var keys = Object.keys(zones).sort(function (a, b) {
            return a.localeCompare(b, undefined, { numeric: true });
        });
        var current = zoneFilter;
        sel.innerHTML = '<option value="">All Zones</option>';
        keys.forEach(function (z) {
            var opt = document.createElement("option");
            opt.value = z;
            opt.textContent = zoneOptionLabel(z);
            if (z === current) opt.selected = true;
            sel.appendChild(opt);
        });
        if (current && keys.indexOf(current) < 0) {
            zoneFilter = "";
            sel.value = "";
        }
    }

    function syncExportLink() {
        var link = qs("#rf-execute-export");
        if (!link) return;
        if (!runId()) {
            link.hidden = true;
            link.removeAttribute("href");
            return;
        }
        link.hidden = false;
        link.href = apiUrl("/api/execute/reopen.csv");
        link.setAttribute("download", "");
    }

    function showEmpty() {
        closeMapModal();
        qs("#rf-execute-workspace").hidden = true;
        qs("#rf-execute-error").hidden = true;
        qs("#rf-execute-empty").hidden = false;
        var link = qs("#rf-execute-export");
        if (link) link.hidden = true;
    }

    function showError(message) {
        closeMapModal();
        qs("#rf-execute-workspace").hidden = true;
        qs("#rf-execute-empty").hidden = true;
        var box = qs("#rf-execute-error");
        box.hidden = false;
        qs("p", box).textContent = message || "Could not load Reopen.";
    }

    function formatCountdown(ms) {
        var total = Math.max(0, Math.ceil(ms / 1000));
        var mm = String(Math.floor(total / 60)).padStart(2, "0");
        var ss = String(total % 60).padStart(2, "0");
        return mm + ":" + ss;
    }

    function syncRefreshCountdown() {
        var el = qs("#rf-execute-next-refresh");
        if (!el) return;
        if (!lastRefreshAt) {
            el.textContent = formatCountdown(BOARD_REFRESH_MS);
            return;
        }
        el.textContent = formatCountdown(
            BOARD_REFRESH_MS - (Date.now() - lastRefreshAt)
        );
    }

    function applyBoard(data) {
        board = data;
        lastRefreshAt = Date.now();
        render();
        if (board.clock && board.clock.paused && !unpausing) {
            unpausing = true;
            putClock({ paused: false, jump_to_now: true }).then(function () {
                unpausing = false;
            });
        }
    }

    function loadBoard() {
        if (!runId()) {
            showEmpty();
            return Promise.resolve();
        }
        return fetch(apiUrl("/api/execute/board"), { credentials: "same-origin" })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    return { resp: resp, data: data };
                });
            })
            .then(function (pack) {
                if (pack.resp.status === 404) {
                    showError(
                        pack.data.detail ||
                            "Locations report JSON is missing. Re-run analysis."
                    );
                    return;
                }
                if (!pack.resp.ok) {
                    showError(pack.data.detail || "Could not load Reopen.");
                    return;
                }
                resetColumnExpand();
                applyBoard(pack.data);
            })
            .catch(function () {
                showError("Lost connection to Execute.");
            });
    }

    function collectGuns() {
        var guns = {};
        document.querySelectorAll("[data-gun]").forEach(function (input) {
            if (input.value) guns[input.getAttribute("data-gun")] = input.value;
        });
        return guns;
    }

    function putClock(payload) {
        return fetch(apiUrl("/api/execute/clock"), {
            method: "PUT",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) throw new Error(data.detail || "Clock update failed");
                    applyBoard(data);
                });
            })
            .catch(function (err) {
                showError(err.message || "Clock update failed");
            });
    }

    function findStrip(locId) {
        var cols = (board && board.columns) || {};
        var lists = [cols.closed, cols.reopen_next, cols.reopened];
        var id = Number(locId);
        for (var i = 0; i < lists.length; i++) {
            var rows = lists[i] || [];
            for (var j = 0; j < rows.length; j++) {
                if (Number(rows[j].loc_id) === id) return rows[j];
            }
        }
        return null;
    }

    function postReopen(locId) {
        if (pendingReopenId) return Promise.resolve();
        var strip = findStrip(locId);
        var linked = ((strip && strip.linked) || []).map(function (row) {
            return Number(row.loc_id);
        });
        pendingReopenId = Number(locId);
        reopenError = null;
        render();
        return fetch(apiUrl("/api/execute/reopen"), {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                loc_id: Number(locId),
                linked_loc_ids: linked,
            }),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (resp.status === 409) {
                        pendingReopenId = null;
                        return loadBoard();
                    }
                    if (!resp.ok) {
                        throw new Error(data.detail || "Reopen failed. Try again.");
                    }
                    pendingReopenId = null;
                    reopenError = null;
                    applyBoard(data);
                });
            })
            .catch(function (err) {
                pendingReopenId = null;
                reopenError = {
                    locId: Number(locId),
                    message: err.message || "Reopen failed. Try again.",
                };
                render();
            });
    }

    function mapModalOpen() {
        var el = qs("#rf-execute-map-modal");
        return !!(el && !el.hidden);
    }

    function stripLatLon(strip) {
        var lat = Number(strip && strip.lat);
        var lon = Number(strip && strip.lon);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
        return [lat, lon];
    }

    function statusColor(status) {
        return STATUS_COLORS[status] || STATUS_COLORS.closed;
    }

    function statusTitle(status) {
        if (status === "reopen_next") return "Reopen next";
        if (status === "reopened") return "Reopened";
        return "Closed";
    }

    function markerPopupHtml(strip) {
        var status = strip.status || "closed";
        var timeLine =
            status === "reopened"
                ? "Actual " + (strip.reopened_at || "—")
                : "est. " + (strip.loc_end || "—");
        var meta = metaLine(strip);
        return (
            '<div class="rf-ex-map-popup">' +
            '<div class="rf-ex-map-popup-id">' +
            esc(strip.loc_id) +
            " · " +
            esc(strip.loc_label) +
            "</div>" +
            "<div>" +
            esc(statusTitle(status)) +
            " · " +
            esc(timeLine) +
            "</div>" +
            (meta ? '<div class="rf-ex-map-popup-meta">' + meta + "</div>" : "") +
            "</div>"
        );
    }

    function filteredPins() {
        return allStrips()
            .filter(stripMatches)
            .map(function (strip) {
                var latlng = stripLatLon(strip);
                if (!latlng) return null;
                return { strip: strip, latlng: latlng };
            })
            .filter(Boolean);
    }

    function ensureMapInstance(fallbackLatLng) {
        if (mapInstance) return mapInstance;
        if (typeof window.initMap === "function") {
            mapInstance = window.initMap("rf-execute-map", {
                zoomPosition: "topleft",
            });
            return mapInstance;
        }
        if (window.L) {
            mapInstance = window.L.map("rf-execute-map").setView(
                fallbackLatLng || [45.95, -66.64],
                14
            );
            if (typeof window.createCartoVoyagerLayer === "function") {
                window.createCartoVoyagerLayer().addTo(mapInstance);
            }
        }
        return mapInstance;
    }

    function paintStatusMap(focusId) {
        var pins = filteredPins();
        var empty = qs("#rf-execute-map-empty");
        var mapEl = qs("#rf-execute-map");
        var legend = qs("#rf-execute-map-legend");
        var hasPins = pins.length > 0;
        if (empty) empty.hidden = hasPins;
        if (mapEl) mapEl.hidden = !hasPins;
        if (legend) legend.hidden = !hasPins;
        if (!hasPins) {
            if (mapInstance) {
                mapInstance.remove();
                mapInstance = null;
                window.existingMap = null;
            }
            return;
        }
        var map = ensureMapInstance(pins[0].latlng);
        if (!map || !window.L) return;
        if (map._rfStatusLayer) {
            map.removeLayer(map._rfStatusLayer);
            map._rfStatusLayer = null;
        }
        var group = window.L.featureGroup();
        var focusMarker = null;
        pins.forEach(function (pin) {
            var status = pin.strip.status || "closed";
            var locId = Number(pin.strip.loc_id);
            var focused = focusId != null && locId === Number(focusId);
            var marker = window.L.circleMarker(pin.latlng, {
                radius: focused ? 12 : 8,
                color: focused ? "#182433" : "#ffffff",
                weight: focused ? 3 : 2,
                fillColor: statusColor(status),
                fillOpacity: 0.9,
                opacity: 1,
            });
            marker.bindPopup(markerPopupHtml(pin.strip), { maxWidth: 280 });
            marker.addTo(group);
            if (focused) focusMarker = marker;
        });
        group.addTo(map);
        map._rfStatusLayer = group;
        map.invalidateSize();
        if (focusMarker) {
            map.setView(focusMarker.getLatLng(), 16);
            focusMarker.openPopup();
        } else if (pins.length === 1) {
            map.setView(pins[0].latlng, 14);
        } else if (group.getLayers().length) {
            map.fitBounds(group.getBounds().pad(0.15));
        }
    }

    function closeMapModal() {
        var modalEl = qs("#rf-execute-map-modal");
        if (modalEl) modalEl.hidden = true;
        mapFocusLocId = null;
        if (mapInstance) {
            mapInstance.remove();
            mapInstance = null;
            window.existingMap = null;
        }
    }

    function openMapModal(locId) {
        mapFocusLocId = locId == null || locId === "" ? null : Number(locId);
        var strip = mapFocusLocId != null ? findStrip(mapFocusLocId) : null;
        var title = qs("#rf-execute-map-title");
        if (title) {
            title.textContent = strip
                ? strip.loc_id + " · " + strip.loc_label
                : "Reopen map";
        }
        var modalEl = qs("#rf-execute-map-modal");
        if (modalEl) modalEl.hidden = false;
        setTimeout(function () {
            paintStatusMap(mapFocusLocId);
        }, 50);
    }

    function onClick(ev) {
        if (ev.target.closest("[data-map-close]")) {
            ev.preventDefault();
            closeMapModal();
            return;
        }
        if (ev.target.closest("#rf-execute-map-open")) {
            ev.preventDefault();
            openMapModal(null);
            return;
        }
        var toggle = ev.target.closest("[data-toggle-col]");
        if (toggle) {
            ev.preventDefault();
            var col = toggle.getAttribute("data-toggle-col");
            if (Object.prototype.hasOwnProperty.call(expanded, col)) {
                expanded[col] = !expanded[col];
                render();
            }
            return;
        }
        var mapLink = ev.target.closest("[data-map-loc]");
        if (mapLink) {
            ev.preventDefault();
            openMapModal(mapLink.getAttribute("data-map-loc"));
            return;
        }
        var reopen = ev.target.closest("[data-reopen]");
        if (reopen) {
            postReopen(reopen.getAttribute("data-reopen"));
            return;
        }
        if (ev.target.id === "rf-ex-accept-guns") {
            putClock({
                guns_accepted: true,
                guns: (board.clock && board.clock.analysis_guns) || collectGuns(),
            });
            return;
        }
        if (ev.target.id === "rf-ex-save-guns") {
            putClock({ guns_accepted: true, guns: collectGuns() });
        }
    }

    function startTick() {
        if (tickTimer) clearInterval(tickTimer);
        tickTimer = setInterval(function () {
            if (!board) return;
            var parts = String(board.now || "00:00:00").split(":");
            var sec =
                Number(parts[0] || 0) * 3600 +
                Number(parts[1] || 0) * 60 +
                Number(parts[2] || 0) +
                1;
            var hh = String(Math.floor(sec / 3600) % 24).padStart(2, "0");
            var mm = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
            var ss = String(sec % 60).padStart(2, "0");
            board.now = hh + ":" + mm + ":" + ss;
            var clockEl = qs("#rf-execute-clock-time");
            if (clockEl) clockEl.textContent = board.now;
            syncRefreshCountdown();
            if (
                lastRefreshAt &&
                Date.now() - lastRefreshAt >= BOARD_REFRESH_MS &&
                !pendingReopenId
            ) {
                loadBoard();
            }
        }, 1000);
    }

    function bind() {
        var root = qs("#rf-execute-page");
        if (!root) return;
        root.addEventListener("click", onClick);
        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") closeMapModal();
        });
        var refreshBtn = qs("#rf-execute-refresh");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", function () {
                loadBoard();
            });
        }
        var zoneSel = qs("#rf-execute-zone");
        if (zoneSel) {
            zoneSel.addEventListener("change", function (ev) {
                zoneFilter = String(ev.target.value || "");
                resetColumnExpand();
                if (board) render();
            });
        }
        qs("#rf-execute-search").addEventListener("input", function (ev) {
            filterText = String(ev.target.value || "").trim().toLowerCase();
            if (board) render();
        });
        startTick();
        if (window.runflowDay && window.runflowDay.run_id) {
            loadBoard();
            return;
        }
        document.addEventListener("runflow:context-ready", loadBoard, { once: true });
        setTimeout(function () {
            if (!board) loadBoard();
        }, 400);
    }

    document.addEventListener("DOMContentLoaded", bind);
})();
