/* Execute Operations command surface (Issue #928). */
(function () {
    "use strict";

    var board = null;
    var tickTimer = null;
    var filterText = "";
    var zoneFilter = "";
    var focusedCol = "";
    var mapInstance = null;
    var mapFitted = false;
    var selectedLocId = null;
    var selectedDeviceId = null;
    var followDeviceId = null;
    var courseLayer = null;
    var gpsOverlay = null;
    var gpsTimer = null;
    var lastRefreshAt = 0;
    var pendingReopenId = null;
    var reopenError = null;
    var assignRows = [];
    var assignUnassigned = [];
    var assignEditDeviceId = null;
    var operatorName = "";
    var auditRows = [];
    var BOARD_REFRESH_MS = 5 * 60 * 1000;
    var GPS_REFRESH_MS = 10 * 1000;
    var STATUS_COLORS = {
        closed: "#64748b",
        reopen_next: "#3b82f6",
        reopened: "#10b981",
    };
    var layers = {
        courses: true,
        turnarounds: true,
        resources: true,
        sos: true,
        reopen: true,
        water: true,
        all: false,
    };
    var LAYER_CHIP_LABELS = {
        courses: "Courses",
        turnarounds: "Turn-arounds",
        resources: "Resources",
        sos: "SOS",
        reopen: "Reopen set",
        water: "Aid / extract",
    };

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

    function stripInMapView(strip) {
        if (!mapInstance || !mapFitted) return true;
        if (typeof mapInstance.getBounds !== "function") return true;
        var latlng = stripLatLon(strip);
        if (!latlng) return isWater(strip) && layers.water;
        var bounds = mapInstance.getBounds();
        if (!bounds || (bounds.isValid && !bounds.isValid())) return true;
        if (bounds.contains(latlng)) return true;
        return isWater(strip) && layers.water;
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
        ]
            .join(" ")
            .toLowerCase();
        return hay.indexOf(q) !== -1;
    }

    function allStrips() {
        var cols = (board && board.columns) || {};
        return []
            .concat(cols.closed || [])
            .concat(cols.reopen_next || [])
            .concat(cols.reopened || []);
    }

    function columnMap() {
        return (board && board.columns) || {};
    }

    function findStrip(locId) {
        var id = Number(locId);
        var rows = allStrips();
        for (var i = 0; i < rows.length; i++) {
            if (Number(rows[i].loc_id) === id) return rows[i];
        }
        return null;
    }

    function isTurnaround(strip) {
        var type = String((strip && strip.loc_type) || "").toLowerCase();
        if (
            type === "turnaround" ||
            type === "turn-around" ||
            type === "turn_around"
        ) {
            return true;
        }
        if (type === "water") return false;
        var label = String((strip && strip.loc_label) || "");
        if (/turn[\s-]?around/i.test(label)) return true;
        if (!/\bturn\b/i.test(label)) return false;
        return type === "official" || type === "course" || type === "";
    }

    function isWater(strip) {
        var type = String((strip && strip.loc_type) || "").toLowerCase();
        return (
            type === "water" ||
            type === "aid" ||
            type === "official" ||
            type === "extract" ||
            type === "first_aid" ||
            type === "first-aid" ||
            type === "extraction"
        );
    }

    function locationVisible(strip) {
        if (!stripMatches(strip)) return false;
        if (layers.all) return true;
        if (layers.turnarounds && isTurnaround(strip)) return true;
        if (layers.water && isWater(strip)) return true;
        if (!layers.reopen) return false;
        if (strip.status === "closed" || strip.status === "reopened") return true;
        if (strip.status === "reopen_next") {
            return focusedCol === "reopen_next" || !!zoneFilter;
        }
        return false;
    }

    function statusTitle(status) {
        if (status === "reopen_next") return "Reopen next";
        if (status === "reopened") return "Reopened";
        return "Closed";
    }

    function statusColor(status) {
        return STATUS_COLORS[status] || STATUS_COLORS.closed;
    }

    function gpsHeard(iso) {
        if (!iso) return "";
        var when = new Date(iso);
        if (isNaN(when.getTime())) return "";
        return when.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function phoneDigits(phone) {
        var digits = String(phone || "").replace(/\D/g, "");
        if (digits.length === 11 && digits.charAt(0) === "1") {
            return digits.slice(1);
        }
        return digits;
    }

    function formatPhone(phone) {
        var digits = phoneDigits(phone);
        if (digits.length === 10) {
            return (
                "(" +
                digits.slice(0, 3) +
                ") " +
                digits.slice(3, 6) +
                "-" +
                digits.slice(6)
            );
        }
        return String(phone || "").trim();
    }

    function phoneHrefNumber(phone) {
        var nanp = phoneDigits(phone);
        if (nanp.length === 10) return "+1" + nanp;
        var raw = String(phone || "")
            .replace(/[^\d+]/g, "")
            .replace(/(?!^)\+/g, "");
        return /\d/.test(raw) ? raw : "";
    }

    function phoneIconSvg(kind) {
        if (kind === "sms") {
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
            );
        }
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>'
        );
    }

    function phoneLink(phone) {
        var shown = formatPhone(phone);
        var hrefNum = phoneHrefNumber(phone);
        if (!hrefNum) return esc(shown);
        return (
            '<span class="rf-ex-phone">' +
            '<span class="rf-ex-phone-num">' +
            esc(shown) +
            "</span>" +
            '<a class="rf-ex-phone-icon" href="tel:' +
            esc(hrefNum) +
            '" aria-label="Call">' +
            phoneIconSvg("tel") +
            "</a>" +
            '<a class="rf-ex-phone-icon" href="sms:' +
            esc(hrefNum) +
            '" aria-label="Text">' +
            phoneIconSvg("sms") +
            "</a></span>"
        );
    }

    function formatSpeed(speed) {
        if (speed == null || speed === "") return "—";
        var n = Number(speed);
        if (!Number.isFinite(n)) return "—";
        return n.toFixed(1);
    }

    function formatCoord(lat, lon) {
        var a = Number(lat);
        var b = Number(lon);
        if (!Number.isFinite(a) || !Number.isFinite(b)) return "—";
        return a.toFixed(5) + ", " + b.toFixed(5);
    }

    function sosIcon() {
        return '<span class="rf-ex-sos-icon">SOS</span>';
    }

    function tileCloseButton(attr, disabled) {
        return (
            '<button type="button" class="rf-ex-tile-close" ' +
            attr +
            (disabled ? " disabled" : "") +
            ' aria-label="Close">×</button>'
        );
    }

    function resourceRows() {
        var byId = {};
        ((gpsOverlay && gpsOverlay.positions) || []).forEach(function (row) {
            byId[row.device_id] = Object.assign({}, row, { kind: "position" });
        });
        ((gpsOverlay && gpsOverlay.sos) || []).forEach(function (row) {
            var current = byId[row.device_id] || Object.assign({}, row);
            current.sos = true;
            current.attention = row.attention || "new";
            byId[row.device_id] = current;
        });
        return Object.keys(byId)
            .map(function (id) {
                return byId[id];
            })
            .sort(function (a, b) {
                return String(a.display_name || a.device_id).localeCompare(
                    String(b.display_name || b.device_id)
                );
            });
    }

    function findResource(deviceId) {
        var rows = resourceRows();
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].device_id === deviceId) return rows[i];
        }
        return null;
    }

    function counts() {
        var cols = columnMap();
        return {
            closed: (cols.closed || []).filter(stripMatches).length,
            reopen_next: (cols.reopen_next || []).filter(stripMatches).length,
            reopened: (cols.reopened || []).filter(stripMatches).length,
        };
    }

    function renderStripCounts() {
        var c = counts();
        ["closed", "reopen_next", "reopened"].forEach(function (id) {
            var el = qs('[data-count="' + id + '"]');
            if (el) el.textContent = String(c[id]);
            var btn = qs('.rf-ex-strip-btn[data-col="' + id + '"]');
            if (btn) {
                btn.setAttribute(
                    "aria-pressed",
                    focusedCol === id ? "true" : "false"
                );
            }
        });
        var sos = qs("#rf-execute-sos-count");
        var n = ((gpsOverlay && gpsOverlay.sos) || []).length;
        if (sos) {
            sos.hidden = n < 1;
            sos.textContent = "SOS " + n;
        }
    }

    function renderResources() {
        var list = qs("#rf-execute-resources");
        var tile = qs("#rf-execute-resource-tile");
        if (!list) return;
        var rows = resourceRows();
        if (!rows.length) {
            list.innerHTML =
                '<p class="rf-execute-empty">No units yet.</p>';
        } else {
            list.innerHTML = rows
                .map(function (row) {
                    var selected =
                        selectedDeviceId && row.device_id === selectedDeviceId
                            ? " is-selected"
                            : "";
                    var stale = !!row.stale;
                    var status = stale
                        ? "last seen " + (gpsHeard(row.received_at) || "")
                        : "live " + (gpsHeard(row.received_at) || "");
                    var dot =
                        "rf-ex-dot" +
                        (row.sos ? " is-sos" : stale ? " is-stale" : "");
                    return (
                        '<button type="button" class="rf-ex-resource' +
                        selected +
                        '" data-device="' +
                        esc(row.device_id) +
                        '">' +
                        '<span class="rf-ex-resource-name">' +
                        '<span class="' +
                        dot +
                        '" aria-hidden="true"></span>' +
                        esc(row.display_name || row.device_id || "unnamed") +
                        (row.sos ? " " + sosIcon() : "") +
                        "</span>" +
                        '<span class="rf-ex-resource-status">' +
                        esc(status.trim()) +
                        "</span></button>"
                    );
                })
                .join("");
        }
        var selected = selectedDeviceId
            ? findResource(selectedDeviceId)
            : null;
        if (!tile) return;
        if (!selected) {
            tile.hidden = true;
            tile.innerHTML = "";
            return;
        }
        tile.hidden = false;
        var following = followDeviceId === selected.device_id;
        tile.innerHTML =
            '<div class="rf-ex-tile-head">' +
            '<div class="rf-ex-tile-name">' +
            esc(selected.display_name || selected.device_id) +
            " " +
            (selected.sos ? sosIcon() : "") +
            "</div>" +
            tileCloseButton("data-close-resource") +
            "</div><dl>" +
            "<dt>" +
            (selected.stale ? "Last seen" : "Live") +
            "</dt><dd>" +
            esc(gpsHeard(selected.received_at) || "—") +
            "</dd>" +
            (selected.person_name
                ? "<dt>Person</dt><dd>" + esc(selected.person_name) + "</dd>"
                : "") +
            (selected.phone
                ? "<dt>Phone</dt><dd>" + phoneLink(selected.phone) + "</dd>"
                : "") +
            (selected.agency
                ? "<dt>Agency</dt><dd>" + esc(selected.agency) + "</dd>"
                : "") +
            "<dt>Speed</dt><dd>" +
            esc(formatSpeed(selected.speed)) +
            "</dd>" +
            "<dt>Coords</dt><dd>" +
            esc(formatCoord(selected.lat, selected.lon)) +
            "</dd></dl>" +
            '<div class="rf-ex-tile-actions">' +
            '<button type="button" class="btn btn-sm" data-locate-device="' +
            esc(selected.device_id) +
            '">Locate</button>' +
            '<button type="button" class="btn btn-sm" data-follow-device="' +
            esc(selected.device_id) +
            '">' +
            (following ? "Stop follow" : "Follow") +
            "</button></div>";
    }

    function renderFocusedList() {
        var box = qs("#rf-execute-board");
        if (!box) return;
        if (!focusedCol) {
            box.innerHTML = "";
            return;
        }
        var rows = ((board && board.columns && board.columns[focusedCol]) || [])
            .filter(locationVisible)
            .filter(stripInMapView);
        var items = rows.length
            ? rows
                  .map(function (strip) {
                      var selected =
                          selectedLocId != null &&
                          Number(strip.loc_id) === Number(selectedLocId)
                              ? " is-selected"
                              : "";
                      var next =
                          strip.status === "reopen_next" ? " is-next" : "";
                      return (
                          '<button type="button" class="rf-ex-strip' +
                          selected +
                          next +
                          '" data-loc-id="' +
                          esc(strip.loc_id) +
                          '"><span class="rf-ex-strip-line"><span class="rf-ex-id">' +
                          esc(strip.loc_id) +
                          '</span><span class="rf-ex-name">' +
                          esc(strip.loc_label) +
                          '</span></span><span class="rf-ex-strip-line rf-ex-strip-sub"><span class="rf-ex-time">est. ' +
                          esc(strip.loc_end || "—") +
                          "</span>" +
                          (zoneLabel(strip)
                              ? '<span class="rf-ex-meta">' +
                                esc(zoneLabel(strip)) +
                                "</span>"
                              : "") +
                          "</span></button>"
                      );
                  })
                  .join("")
            : '<p class="rf-execute-empty">None in the current map view.</p>';
        box.innerHTML =
            '<div class="rf-ex-focus-head">' +
            esc(statusTitle(focusedCol)) +
            "</div>" +
            items;
    }

    function renderSelectedLocation() {
        var box = qs("#rf-execute-selected");
        if (!box) return;
        var strip = selectedLocId != null ? findStrip(selectedLocId) : null;
        if (!strip) {
            box.hidden = true;
            box.innerHTML = "";
            return;
        }
        var pending = pendingReopenId === Number(strip.loc_id);
        var err =
            reopenError && Number(reopenError.locId) === Number(strip.loc_id)
                ? reopenError.message
                : "";
        var action = "";
        if (strip.status === "reopen_next") {
            action =
                '<button type="button" class="btn btn-sm btn-primary rf-ex-reopen" data-reopen="' +
                esc(strip.loc_id) +
                '"' +
                (pending || pendingReopenId ? " disabled" : "") +
                ">" +
                (pending ? "Reopening…" : "Confirm reopen") +
                "</button>";
        } else if (strip.status === "reopened") {
            action =
                "<p>Reopened " +
                esc(strip.reopened_at || "") +
                "</p>" +
                '<button type="button" class="btn btn-sm rf-ex-reopen" data-mark-closed="' +
                esc(strip.loc_id) +
                '"' +
                (pending || pendingReopenId ? " disabled" : "") +
                ">Mark closed</button>";
        }
        box.hidden = false;
        box.innerHTML =
            '<div class="rf-ex-tile-head">' +
            '<div class="rf-ex-tile-name">' +
            esc(strip.loc_id) +
            " · " +
            esc(strip.loc_label) +
            "</div>" +
            tileCloseButton("data-close-location", pending) +
            "</div><dl>" +
            "<dt>Status</dt><dd>" +
            esc(statusTitle(strip.status)) +
            "</dd>" +
            "<dt>Zone</dt><dd>" +
            esc(zoneLabel(strip) || "—") +
            "</dd>" +
            "<dt>Est.</dt><dd>" +
            esc(strip.loc_end || "—") +
            "</dd></dl>" +
            action +
            (err
                ? '<span class="rf-ex-strip-error">' + esc(err) + "</span>"
                : "");
    }

    function renderAttention() {
        var box = qs("#rf-execute-attention");
        if (!box) return;
        var rows = ((gpsOverlay && gpsOverlay.sos) || []).filter(function (row) {
            return row.attention === "new" || row.attention === "acknowledged";
        });
        if (!rows.length) {
            box.hidden = true;
            box.innerHTML = "";
            return;
        }
        box.hidden = false;
        box.innerHTML =
            '<h3 class="rf-ex-section-title">Attention</h3>' +
            rows
                .map(function (row) {
                    var isNew = row.attention !== "acknowledged";
                    var status = isNew ? "New" : "Acknowledged";
                    var who = row.acknowledged_by
                        ? " by " + row.acknowledged_by
                        : "";
                    var actions = isNew
                        ? '<button type="button" class="btn btn-sm" data-sos-ack="' +
                          esc(row.device_id) +
                          '">Acknowledge</button>'
                        : '<button type="button" class="btn btn-sm" data-sos-clear="' +
                          esc(row.device_id) +
                          '">Clear</button>';
                    return (
                        '<div class="rf-ex-att' +
                        (isNew ? " is-new" : "") +
                        '"><div class="rf-ex-att-head"><span>' +
                        esc(row.display_name || row.device_id) +
                        " " +
                        sosIcon() +
                        '</span><span class="rf-ex-att-status">' +
                        status +
                        who +
                        "</span></div>" +
                        '<div class="rf-ex-att-actions">' +
                        actions +
                        "</div></div>"
                    );
                })
                .join("");
    }

    function auditLabel(row) {
        if (row.action === "sos_acknowledge") return "Acknowledged SOS";
        if (row.action === "sos_clear") return "Cleared SOS from attention";
        if (row.action === "reopen") return "Confirmed reopen";
        if (row.action === "close") return "Marked closed";
        if (row.action === "assignment_upsert") return "Saved assignment";
        if (row.action === "assignment_delete") return "Removed assignment";
        return row.action || "Action";
    }

    function renderAudit() {
        var box = qs("#rf-execute-audit");
        if (!box) return;
        if (!auditRows.length) {
            box.hidden = false;
            box.innerHTML =
                '<h3 class="rf-ex-section-title">Activity</h3>' +
                '<p class="rf-ex-audit-empty">No activity yet.</p>';
            return;
        }
        box.hidden = false;
        box.innerHTML =
            '<h3 class="rf-ex-section-title">Activity</h3>' +
            '<ol class="rf-ex-audit-list">' +
            auditRows
                .map(function (row) {
                    var target = row.device_id || row.loc_id || "";
                    return (
                        "<li><strong>" +
                        esc(row.actor || "") +
                        "</strong> · " +
                        esc(auditLabel(row)) +
                        (target ? " · " + esc(target) : "") +
                        "</li>"
                    );
                })
                .join("") +
            "</ol>";
    }

    function renderOperator() {
        var input = qs("#rf-execute-operator");
        if (input && operatorName && input.value !== operatorName) {
            input.value = operatorName;
        }
    }

    function render(options) {
        if (!board) return;
        qs("#rf-execute-clock-time").textContent = board.now || "—";
        var label = qs("#rf-execute-plan-label");
        if (label) {
            label.textContent = [board.name, board.calendar_date]
                .filter(Boolean)
                .join(" · ");
        }
        syncRefreshCountdown();
        renderStripCounts();
        renderResources();
        renderFocusedList();
        renderSelectedLocation();
        renderAttention();
        renderAudit();
        renderOperator();
        updateLayersChip();
        syncZoneSelect();
        qs("#rf-execute-workspace").hidden = false;
        qs("#rf-execute-empty").hidden = true;
        qs("#rf-execute-error").hidden = true;
        paintStatusMap(selectedLocId, {
            preserveView: !(options && options.fitMap),
        });
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

    function showEmpty() {
        qs("#rf-execute-workspace").hidden = true;
        qs("#rf-execute-error").hidden = true;
        qs("#rf-execute-empty").hidden = false;
    }

    function showError(message) {
        qs("#rf-execute-workspace").hidden = true;
        qs("#rf-execute-empty").hidden = true;
        var box = qs("#rf-execute-error");
        box.hidden = false;
        qs("p", box).textContent = message || "Could not load Operations.";
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
        loadGpsOverlay();
        loadSession();
        loadAudit();
    }

    function loadBoard() {
        return fetch("/api/execute/ops/board", { credentials: "same-origin" })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    return { resp: resp, data: data };
                });
            })
            .then(function (pack) {
                if (pack.data && pack.data.empty) {
                    showEmpty();
                    return;
                }
                if (!pack.resp.ok) {
                    showError(pack.data.detail || "Could not load Operations.");
                    return;
                }
                applyBoard(pack.data);
            })
            .catch(function () {
                showError("Lost connection to Execute.");
            });
    }

    function loadGpsOverlay() {
        return fetch("/api/execute/gps/overlay", { credentials: "same-origin" })
            .then(function (resp) {
                if (!resp.ok) return null;
                return resp.json();
            })
            .then(function (data) {
                gpsOverlay = data;
                renderResources();
                renderStripCounts();
                renderAttention();
                renderAudit();
                paintStatusMap(selectedLocId, { preserveView: true });
                followIfNeeded();
            })
            .catch(function () {
                gpsOverlay = null;
            });
    }

    function loadSession() {
        return fetch("/api/execute/ops/session", { credentials: "same-origin" })
            .then(function (resp) {
                return resp.json();
            })
            .then(function (data) {
                operatorName = data.operator || "";
                renderOperator();
            })
            .catch(function () {
                operatorName = "";
            });
    }

    function loadAudit() {
        return fetch("/api/execute/ops/audit", { credentials: "same-origin" })
            .then(function (resp) {
                return resp.json();
            })
            .then(function (data) {
                auditRows = data.audit || [];
                renderAudit();
            })
            .catch(function () {
                auditRows = [];
            });
    }

    function saveOperator(ev) {
        ev.preventDefault();
        var input = qs("#rf-execute-operator");
        if (!input) return;
        fetch("/api/execute/ops/session", {
            method: "PUT",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ operator: input.value }),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) {
                        throw new Error(data.detail || "Could not save name.");
                    }
                    return data;
                });
            })
            .then(function (data) {
                operatorName = data.operator || "";
                renderOperator();
            })
            .catch(function () {
                return loadSession();
            });
    }

    function postSosAction(path, deviceId) {
        return fetch(path, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_id: deviceId }),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) {
                        throw new Error(data.detail || "SOS action failed.");
                    }
                    return data;
                });
            })
            .then(function () {
                return Promise.all([loadGpsOverlay(), loadAudit()]);
            });
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
        return fetch("/api/execute/ops/reopen", {
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

    function postClose(locId) {
        if (pendingReopenId) return Promise.resolve();
        pendingReopenId = Number(locId);
        reopenError = null;
        render();
        return fetch("/api/execute/ops/close", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ loc_id: Number(locId) }),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) {
                        throw new Error(data.detail || "Close failed. Try again.");
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
                    message: err.message || "Close failed. Try again.",
                };
                render();
            });
    }

    function stripLatLon(strip) {
        var lat = Number(strip && strip.lat);
        var lon = Number(strip && strip.lon);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
        return [lat, lon];
    }

    function visiblePins() {
        return allStrips()
            .filter(locationVisible)
            .map(function (strip) {
                var latlng = stripLatLon(strip);
                if (!latlng) return null;
                return { strip: strip, latlng: latlng };
            })
            .filter(Boolean);
    }

    function dockMapChrome(map) {
        if (!map || !window.L || map._rfChromeDocked) return;
        if (map.zoomControl) {
            map.zoomControl.remove();
        }
        if (window.L.control) {
            window.L.control.zoom({ position: "bottomright" }).addTo(map);
        }
        var tools = qs("#rf-execute-map-tools");
        if (tools && window.L.Control) {
            var Chrome = window.L.Control.extend({
                options: { position: "bottomright" },
                onAdd: function () {
                    return tools;
                },
            });
            map.addControl(new Chrome());
        }
        map._rfChromeDocked = true;
    }

    function ensureMapInstance(fallbackLatLng) {
        if (mapInstance) return mapInstance;
        if (typeof window.initMap === "function") {
            mapInstance = window.initMap("rf-execute-map");
            dockMapChrome(mapInstance);
            bindBasemap(mapInstance);
            bindMapViewSync(mapInstance);
            return mapInstance;
        }
        if (window.L) {
            mapInstance = window.L.map("rf-execute-map").setView(
                fallbackLatLng || [45.95, -66.64],
                14
            );
            dockMapChrome(mapInstance);
            bindMapViewSync(mapInstance);
        }
        return mapInstance;
    }

    function bindMapViewSync(map) {
        if (!map || map._rfViewBound) return;
        map._rfViewBound = true;
        map.on("moveend", function () {
            renderFocusedList();
        });
    }

    function paintCourseLayer(map) {
        if (courseLayer) {
            map.removeLayer(courseLayer);
            courseLayer = null;
        }
        if (!layers.courses) return null;
        var courses = (board && board.courses) || {};
        var group = window.L.featureGroup();
        Object.keys(courses).forEach(function (raceId) {
            var geo = courses[raceId];
            if (!geo) return;
            window.L.geoJSON(geo, {
                style: { color: "#38bdf8", weight: 3, opacity: 0.9 },
            }).addTo(group);
        });
        if (group.getLayers().length) {
            group.addTo(map);
            courseLayer = group;
        }
        return courseLayer;
    }

    function bindBasemap(map) {
        var toggle = qs("#basemap-toggle");
        if (!map || !toggle) return;
        if (window.L && window.L.DomEvent) {
            window.L.DomEvent.disableClickPropagation(toggle);
            window.L.DomEvent.disableScrollPropagation(toggle);
        }
        toggle.style.display = "flex";
        function applyPanelTheme(key) {
            var page = qs("#rf-execute-page");
            if (!page) return;
            var light = key === "carto" || key === "satellite";
            page.classList.toggle("rf-ex-theme-light", light);
            page.classList.toggle("rf-ex-theme-dark", !light);
        }
        function setBasemap(key) {
            if (typeof window.switchTileLayer === "function") {
                window.switchTileLayer(map, key);
            }
            var dark = qs("#btn-dark");
            var street = qs("#btn-street");
            var sat = qs("#btn-satellite");
            if (dark) dark.classList.toggle("active", key === "cartoDark");
            if (street) street.classList.toggle("active", key === "carto");
            if (sat) sat.classList.toggle("active", key === "satellite");
            applyPanelTheme(key);
        }
        var dark = qs("#btn-dark");
        var street = qs("#btn-street");
        var sat = qs("#btn-satellite");
        if (dark && !dark.dataset.bound) {
            dark.addEventListener("click", function () {
                setBasemap("cartoDark");
            });
            dark.dataset.bound = "1";
        }
        if (street && !street.dataset.bound) {
            street.addEventListener("click", function () {
                setBasemap("carto");
            });
            street.dataset.bound = "1";
        }
        if (sat && !sat.dataset.bound) {
            sat.addEventListener("click", function () {
                setBasemap("satellite");
            });
            sat.dataset.bound = "1";
        }
        setBasemap("cartoDark");
    }

    function ensureGpsPane(map) {
        if (!map.getPane("rfGps")) {
            map.createPane("rfGps");
            map.getPane("rfGps").style.zIndex = 650;
        }
    }

    function gpsPopupHtml(row, kind) {
        var label =
            kind === "sos"
                ? "SOS"
                : row.stale
                  ? "last seen"
                  : "live";
        return (
            '<div class="rf-ex-map-popup">' +
            '<div class="rf-ex-map-popup-id">' +
            esc(row.display_name || row.device_id || "") +
            "</div>" +
            "<div>" +
            esc(label) +
            (gpsHeard(row.received_at)
                ? " · " + esc(gpsHeard(row.received_at))
                : "") +
            "</div>" +
            (row.phone ? "<div>" + phoneLink(row.phone) + "</div>" : "") +
            "</div>"
        );
    }

    function addGpsChip(group, row, kind) {
        if (row.lat == null || row.lon == null || !window.L) return;
        var name = row.display_name || row.device_id || "unnamed";
        var cls = "rf-ex-gps-marker";
        if (kind === "sos") cls += " is-sos";
        else if (row.stale) cls += " is-stale";
        var html =
            '<div class="' +
            cls +
            '">' +
            (kind === "sos" ? "SOS · " : "") +
            esc(name) +
            "</div>";
        var icon = window.L.divIcon({
            className: "rf-ex-gps-icon",
            html: html,
            iconSize: [150, 26],
            iconAnchor: kind === "sos" ? [16, 36] : [16, 13],
        });
        window.L.marker([row.lat, row.lon], {
            icon: icon,
            pane: "rfGps",
            keyboard: false,
        })
            .bindPopup(gpsPopupHtml(row, kind), { maxWidth: 240 })
            .on("click", function () {
                selectDevice(row.device_id);
            })
            .addTo(group);
    }

    function paintGpsLayer(map) {
        if (map._rfGpsLayer) {
            map.removeLayer(map._rfGpsLayer);
            map._rfGpsLayer = null;
        }
        if (!gpsOverlay || !window.L) return;
        ensureGpsPane(map);
        var group = window.L.featureGroup();
        var drawn = {};
        if (layers.resources) {
            (gpsOverlay.positions || []).forEach(function (row) {
                drawn[row.device_id] = true;
                addGpsChip(
                    group,
                    row,
                    layers.sos && row.sos ? "sos" : "position"
                );
            });
        }
        if (layers.sos) {
            (gpsOverlay.sos || []).forEach(function (row) {
                if (drawn[row.device_id]) return;
                addGpsChip(group, row, "sos");
            });
        }
        if (group.getLayers().length) {
            group.addTo(map);
            map._rfGpsLayer = group;
        }
    }

    function paintTurnarounds(map) {
        if (map._rfTurnLayer) {
            map.removeLayer(map._rfTurnLayer);
            map._rfTurnLayer = null;
        }
        if (!layers.turnarounds || !window.L) return;
        var pins = (board && board.turnarounds) || [];
        var group = window.L.featureGroup();
        pins.forEach(function (pin) {
            if (pin.lat == null || pin.lon == null) return;
            window.L.marker([pin.lat, pin.lon], {
                icon: window.L.divIcon({
                    className: "rf-ex-gps-icon",
                    html: '<div class="rf-ex-turn-marker"></div>',
                    iconSize: [14, 12],
                    iconAnchor: [7, 12],
                }),
                keyboard: false,
            })
                .bindPopup(esc(pin.label || "Turn-around"))
                .addTo(group);
        });
        if (group.getLayers().length) {
            group.addTo(map);
            map._rfTurnLayer = group;
        }
    }

    function markerPopupHtml(strip) {
        var status = strip.status || "closed";
        var timeLine =
            status === "reopened"
                ? "Actual " + (strip.reopened_at || "—")
                : "est. " + (strip.loc_end || "—");
        return (
            '<div class="rf-ex-map-popup">' +
            '<div class="rf-ex-map-popup-id">' +
            esc(strip.loc_id) +
            " · " +
            esc(strip.loc_label) +
            "</div><div>" +
            esc(statusTitle(status)) +
            " · " +
            esc(timeLine) +
            "</div></div>"
        );
    }

    function paintStatusMap(focusId, options) {
        options = options || {};
        var pins = visiblePins();
        var courses = (board && board.courses) || {};
        var hasCourses = Object.keys(courses).some(function (id) {
            return !!courses[id];
        });
        var empty = qs("#rf-execute-map-empty");
        var mapEl = qs("#rf-execute-map");
        var legend = qs("#rf-execute-map-legend");
        var hasGps = !!(
            gpsOverlay &&
            ((gpsOverlay.positions && gpsOverlay.positions.length) ||
                (gpsOverlay.sos && gpsOverlay.sos.length))
        );
        var hasGeo =
            pins.length > 0 ||
            hasCourses ||
            hasGps ||
            ((board && board.turnarounds) || []).length > 0;
        if (empty) empty.hidden = hasGeo;
        if (mapEl) mapEl.hidden = !hasGeo;
        if (legend) legend.hidden = !hasGeo;
        if (!hasGeo) return;
        var map = ensureMapInstance(
            pins.length ? pins[0].latlng : [45.95, -66.64]
        );
        if (!map || !window.L) return;
        paintCourseLayer(map);
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
            marker.on("click", function () {
                selectLocation(locId);
            });
            marker.addTo(group);
            if (focused) focusMarker = marker;
        });
        group.addTo(map);
        map._rfStatusLayer = group;
        paintTurnarounds(map);
        paintGpsLayer(map);
        map.invalidateSize();
        if (options.preserveView && mapFitted) return;
        if (zoneFilter && group.getLayers().length) {
            var zoneBounds = group.getBounds();
            if (zoneBounds.isValid()) {
                if (zoneBounds.getNorthEast().equals(zoneBounds.getSouthWest())) {
                    map.setView(zoneBounds.getCenter(), 15);
                } else {
                    map.fitBounds(zoneBounds.pad(0.2));
                }
            }
        } else if (focusMarker) {
            map.setView(focusMarker.getLatLng(), Math.max(map.getZoom(), 15));
        } else if (courseLayer && courseLayer.getBounds().isValid()) {
            map.fitBounds(courseLayer.getBounds().pad(0.12));
        } else if (group.getLayers().length) {
            map.fitBounds(group.getBounds().pad(0.2));
        }
        mapFitted = true;
    }

    function followIfNeeded() {
        if (!followDeviceId || !mapInstance) return;
        var row = findResource(followDeviceId);
        if (!row || row.lat == null || row.lon == null) return;
        if (row.stale) return;
        mapInstance.setView([row.lat, row.lon], Math.max(mapInstance.getZoom(), 15));
    }

    function selectLocation(locId) {
        selectedLocId = locId == null || locId === "" ? null : Number(locId);
        if (board) render();
        var strip = selectedLocId != null ? findStrip(selectedLocId) : null;
        var latlng = stripLatLon(strip);
        if (latlng && mapInstance) {
            mapInstance.setView(latlng, Math.max(mapInstance.getZoom(), 15));
        }
    }

    function closeSelectedLocation() {
        if (pendingReopenId) return;
        selectedLocId = null;
        reopenError = null;
        if (board) render();
    }

    function closeSelectedResource() {
        selectedDeviceId = null;
        followDeviceId = null;
        renderResources();
    }

    function selectDevice(deviceId) {
        selectedDeviceId = deviceId || null;
        renderResources();
        var row = findResource(deviceId);
        if (row && row.lat != null && mapInstance) {
            mapInstance.setView(
                [row.lat, row.lon],
                Math.max(mapInstance.getZoom(), 15)
            );
        }
    }

    function planId() {
        return (board && board.plan_id) || "";
    }

    function assignStatus(message, isError) {
        var el = qs("#rf-execute-assign-status");
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

    function findAssignRow(deviceId) {
        var i;
        for (i = 0; i < assignRows.length; i++) {
            if (assignRows[i].device_id === deviceId) {
                return assignRows[i];
            }
        }
        return null;
    }

    function setAssignFormMode(mode, row) {
        var form = qs("#rf-execute-assign-form");
        var title = qs("#rf-execute-assign-form-title");
        var del = qs("#rf-execute-assign-delete");
        var save = qs("#rf-execute-assign-save");
        if (!form) return;
        if (mode === "edit" && row) {
            assignEditDeviceId = row.device_id;
            form.device_id.value = row.device_id || "";
            form.resource_name.value = row.resource_name || "";
            form.person_name.value = row.person_name || "";
            form.phone.value = row.phone || "";
            form.agency.value = row.agency || "";
            form.device_id.readOnly = true;
            if (title) title.textContent = "Edit assignment";
            if (save) save.textContent = "Save changes";
            if (del) del.disabled = false;
        } else {
            assignEditDeviceId = null;
            form.reset();
            form.device_id.readOnly = false;
            if (row && row.device_id) {
                form.device_id.value = row.device_id;
            }
            if (title) title.textContent = "Add assignment";
            if (save) save.textContent = "Save assignment";
            if (del) del.disabled = true;
        }
        renderAssignLists();
    }

    function mergeUnassigned(apiRows) {
        var assignedIds = {};
        var seen = {};
        var out = [];
        assignRows.forEach(function (row) {
            assignedIds[row.device_id] = true;
        });
        function add(row) {
            var id = String((row && row.device_id) || "").trim();
            if (!id || assignedIds[id] || seen[id]) return;
            seen[id] = true;
            out.push({
                device_id: id,
                received_at: row.received_at || "",
                stale: !!row.stale,
            });
        }
        (apiRows || []).forEach(add);
        ((gpsOverlay && gpsOverlay.positions) || []).forEach(add);
        ((gpsOverlay && gpsOverlay.sos) || []).forEach(add);
        out.sort(function (a, b) {
            return String(a.device_id).localeCompare(String(b.device_id));
        });
        return out;
    }

    function renderAssignLists() {
        var box = qs("#rf-execute-assign-list");
        var unseen = qs("#rf-execute-assign-unassigned");
        if (box) {
            if (!assignRows.length) {
                box.innerHTML =
                    '<tr><td class="rf-ex-assign-empty" colspan="4">' +
                    "No assignments on this Day Plan yet.</td></tr>";
            } else {
                box.innerHTML = assignRows
                    .map(function (row) {
                        var selected =
                            assignEditDeviceId === row.device_id
                                ? " is-selected"
                                : "";
                        return (
                            "<tr class=\"" +
                            selected.trim() +
                            "\" data-fill-device=\"" +
                            esc(row.device_id) +
                            "\">" +
                            "<td>" +
                            esc(row.resource_name || "unnamed") +
                            "</td><td>" +
                            esc(row.device_id) +
                            "</td><td>" +
                            esc(row.person_name || "—") +
                            "</td><td>" +
                            esc(row.agency || "—") +
                            "</td></tr>"
                        );
                    })
                    .join("");
            }
        }
        if (unseen) {
            if (!assignUnassigned.length) {
                unseen.innerHTML =
                    '<p class="rf-execute-empty">No unassigned devices are reporting GPS.</p>';
            } else {
                unseen.innerHTML = assignUnassigned
                    .map(function (row) {
                        var selected =
                            !assignEditDeviceId &&
                            qs("#rf-execute-assign-form") &&
                            qs("#rf-execute-assign-form").device_id.value ===
                                row.device_id
                                ? " is-selected"
                                : "";
                        var heard = gpsHeard(row.received_at);
                        return (
                            '<button type="button" class="rf-ex-assign-device' +
                            selected +
                            '" data-unassigned-device="' +
                            esc(row.device_id) +
                            '">' +
                            esc(row.device_id) +
                            (heard ? " · " + heard : "") +
                            "</button>"
                        );
                    })
                    .join("");
            }
        }
    }

    function loadAssignments() {
        var id = planId();
        if (!id) return Promise.resolve();
        return fetch(
            "/api/execute/plans/" + encodeURIComponent(id) + "/assignments",
            { credentials: "same-origin" }
        )
            .then(function (resp) {
                return resp.json();
            })
            .then(function (data) {
                assignRows = data.assignments || [];
                assignUnassigned = mergeUnassigned(data.unassigned || []);
                renderAssignLists();
            })
            .catch(function (err) {
                assignStatus(err.message || "Could not load assignments.", true);
            });
    }

    function openAssignments() {
        var panel = qs("#rf-execute-assign");
        var plan = qs("#rf-execute-assign-plan");
        if (panel) panel.hidden = false;
        if (plan) {
            plan.textContent = [board && board.name, board && board.calendar_date]
                .filter(Boolean)
                .join(" · ");
        }
        assignStatus("");
        setAssignFormMode("add");
        return loadAssignments();
    }

    function saveAssignment(ev) {
        ev.preventDefault();
        var id = planId();
        var form = qs("#rf-execute-assign-form");
        if (!id || !form) return;
        var body = {
            device_id: form.device_id.value,
            resource_name: form.resource_name.value,
            person_name: form.person_name.value,
            phone: form.phone.value,
            agency: form.agency.value,
        };
        fetch("/api/execute/plans/" + encodeURIComponent(id) + "/assignments", {
            method: "PUT",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) throw new Error(data.detail || "Save failed.");
                    return data;
                });
            })
            .then(function () {
                assignStatus("Saved for this Day Plan.");
                assignEditDeviceId = body.device_id;
                return loadAssignments()
                    .then(loadGpsOverlay)
                    .then(loadAudit)
                    .then(function () {
                        var row = findAssignRow(body.device_id);
                        if (row) setAssignFormMode("edit", row);
                    });
            })
            .catch(function (err) {
                assignStatus(err.message || "Save failed.", true);
            });
    }

    function deleteCurrentAssignment() {
        var id = planId();
        var form = qs("#rf-execute-assign-form");
        if (!id || !form || !form.device_id.value || !assignEditDeviceId) {
            return;
        }
        fetch(
            "/api/execute/plans/" +
                encodeURIComponent(id) +
                "/assignments/" +
                encodeURIComponent(form.device_id.value),
            { method: "DELETE", credentials: "same-origin" }
        )
            .then(function (resp) {
                return resp.json().then(function (data) {
                    if (!resp.ok) throw new Error(data.detail || "Remove failed.");
                    return data;
                });
            })
            .then(function () {
                assignStatus("Removed from this Day Plan.");
                setAssignFormMode("add");
                return loadAssignments().then(loadGpsOverlay).then(loadAudit);
            })
            .catch(function (err) {
                assignStatus(err.message || "Remove failed.", true);
            });
    }

    function onClick(ev) {
        var stripBtn = ev.target.closest(".rf-ex-strip-btn[data-col]");
        if (stripBtn) {
            var col = stripBtn.getAttribute("data-col");
            focusedCol = focusedCol === col ? "" : col;
            render();
            return;
        }
        if (ev.target.closest("#rf-execute-sos-count")) {
            var first = ((gpsOverlay && gpsOverlay.sos) || [])[0];
            if (first) selectDevice(first.device_id);
            return;
        }
        if (ev.target.closest("[data-close-location]")) {
            closeSelectedLocation();
            return;
        }
        if (ev.target.closest("[data-close-resource]")) {
            closeSelectedResource();
            return;
        }
        var reopen = ev.target.closest("[data-reopen]");
        if (reopen) {
            postReopen(reopen.getAttribute("data-reopen"));
            return;
        }
        var markClosed = ev.target.closest("[data-mark-closed]");
        if (markClosed) {
            postClose(markClosed.getAttribute("data-mark-closed"));
            return;
        }
        var sosAck = ev.target.closest("[data-sos-ack]");
        if (sosAck) {
            postSosAction(
                "/api/execute/ops/sos/ack",
                sosAck.getAttribute("data-sos-ack")
            );
            return;
        }
        var sosClear = ev.target.closest("[data-sos-clear]");
        if (sosClear) {
            postSosAction(
                "/api/execute/ops/sos/clear",
                sosClear.getAttribute("data-sos-clear")
            );
            return;
        }
        var locEl = ev.target.closest("[data-loc-id]");
        if (locEl) {
            selectLocation(locEl.getAttribute("data-loc-id"));
            return;
        }
        var deviceEl = ev.target.closest("[data-device]");
        if (deviceEl) {
            selectDevice(deviceEl.getAttribute("data-device"));
            return;
        }
        var locate = ev.target.closest("[data-locate-device]");
        if (locate) {
            selectDevice(locate.getAttribute("data-locate-device"));
            return;
        }
        var follow = ev.target.closest("[data-follow-device]");
        if (follow) {
            var did = follow.getAttribute("data-follow-device");
            followDeviceId = followDeviceId === did ? null : did;
            selectDevice(did);
            followIfNeeded();
            renderResources();
            return;
        }
        if (ev.target.id === "rf-execute-assign-open") {
            openAssignments();
            return;
        }
        if (ev.target.id === "rf-execute-assign-close") {
            qs("#rf-execute-assign").hidden = true;
            return;
        }
        if (ev.target.id === "rf-execute-assign-new") {
            assignStatus("");
            setAssignFormMode("add");
            return;
        }
        if (ev.target.id === "rf-execute-assign-delete") {
            deleteCurrentAssignment();
            return;
        }
        var unseen = ev.target.closest("[data-unassigned-device]");
        if (unseen) {
            assignStatus("");
            setAssignFormMode("add", {
                device_id: unseen.getAttribute("data-unassigned-device"),
            });
            return;
        }
        var fill = ev.target.closest("[data-fill-device]");
        if (fill) {
            assignStatus("");
            setAssignFormMode(
                "edit",
                findAssignRow(fill.getAttribute("data-fill-device")) || {
                    device_id: fill.getAttribute("data-fill-device"),
                }
            );
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

    function setLayersOpen(open) {
        var panel = qs("#rf-execute-layers-panel");
        var btn = qs("#rf-execute-layers-open");
        if (!panel || !btn) return;
        panel.hidden = !open;
        btn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function updateLayersChip() {
        var chip = qs("#rf-execute-layers-chip");
        if (!chip) return;
        var hidden = Object.keys(LAYER_CHIP_LABELS).filter(function (key) {
            return !layers[key];
        });
        var text = "";
        if (layers.all) {
            text = "All on";
        } else if (hidden.length === 1) {
            text = LAYER_CHIP_LABELS[hidden[0]] + " off";
        } else if (hidden.length > 1) {
            text = String(hidden.length) + " hidden";
        }
        chip.textContent = text;
        chip.hidden = !text;
    }

    function bindLayers() {
        var tools = qs("#rf-execute-map-tools");
        if (tools && window.L && window.L.DomEvent) {
            window.L.DomEvent.disableClickPropagation(tools);
            window.L.DomEvent.disableScrollPropagation(tools);
        }
        var root = qs("#rf-execute-layers");
        var btn = qs("#rf-execute-layers-open");
        if (root && btn && !root.dataset.bound) {
            root.addEventListener("click", function (ev) {
                ev.stopPropagation();
            });
            btn.addEventListener("click", function (ev) {
                ev.stopPropagation();
                setLayersOpen(btn.getAttribute("aria-expanded") !== "true");
            });
            document.addEventListener("click", function () {
                setLayersOpen(false);
            });
            document.addEventListener("keydown", function (ev) {
                if (ev.key === "Escape") setLayersOpen(false);
            });
            root.dataset.bound = "1";
        }
        document.querySelectorAll("[data-layer]").forEach(function (input) {
            if (input.dataset.bound) return;
            input.dataset.bound = "1";
            input.addEventListener("change", function (ev) {
                var key = ev.target.getAttribute("data-layer");
                if (Object.prototype.hasOwnProperty.call(layers, key)) {
                    layers[key] = !!ev.target.checked;
                    updateLayersChip();
                    if (board) render();
                }
            });
        });
        updateLayersChip();
    }

    function bind() {
        var root = qs("#rf-execute-page");
        if (!root) return;
        root.addEventListener("click", onClick);
        var form = qs("#rf-execute-assign-form");
        if (form) form.addEventListener("submit", saveAssignment);
        var operatorForm = qs("#rf-execute-operator-form");
        if (operatorForm) {
            operatorForm.addEventListener("submit", saveOperator);
        }
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
                if (board) render({ fitMap: true });
            });
        }
        var search = qs("#rf-execute-search");
        if (search) {
            search.addEventListener("input", function (ev) {
                filterText = String(ev.target.value || "").trim().toLowerCase();
                if (board) render();
            });
        }
        bindLayers();
        startTick();
        if (gpsTimer) clearInterval(gpsTimer);
        gpsTimer = setInterval(function () {
            if (board && !board.empty) loadGpsOverlay();
        }, GPS_REFRESH_MS);
        loadBoard();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
