/* Execute Operations Map (Issue #917). Reads published plan + Reopen board. */
(function () {
    "use strict";

    var mapInstance = null;
    var STATUS_COLORS = {
        closed: "#c62828",
        reopen_next: "#ef6c00",
        reopened: "#6b7280",
    };

    function $(id) {
        return document.getElementById(id);
    }

    function statusLabel(status) {
        if (status === "reopen_next") return "Reopen next";
        if (status === "reopened") return "Reopened";
        return "Closed";
    }

    function setStatus(text) {
        var el = $("rf-ops-map-status");
        if (el) el.textContent = text || "";
    }

    function importPackage(file, activateAfter) {
        if (!file) return;
        var body = new FormData();
        body.append("package", file);
        return fetch("/api/execute/published-plans/import", {
            method: "POST",
            body: body,
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) throw new Error(data.detail || "Import failed");
                    return data;
                });
            })
            .then(function (data) {
                if (!activateAfter) return data;
                return fetch("/api/execute/published-plans/activate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        published_plan_id: data.published_plan_id,
                    }),
                }).then(function (res) {
                    return res.json().then(function (act) {
                        if (!res.ok) throw new Error(act.detail || "Activate failed");
                        return act;
                    });
                });
            })
            .then(function () {
                setStatus("Imported.");
                return loadMap();
            })
            .catch(function (err) {
                setStatus(err.message || String(err));
            });
    }

    function bindImport(id, activateAfter) {
        var input = $(id);
        if (!input) return;
        input.addEventListener("change", function () {
            var file = input.files && input.files[0];
            importPackage(file, activateAfter);
            input.value = "";
        });
    }

    function ensureMap() {
        if (mapInstance) return mapInstance;
        mapInstance = initMap("rf-ops-map");
        return mapInstance;
    }

    function renderSnapshot(data) {
        var empty = $("rf-ops-map-empty");
        var workspace = $("rf-ops-map-workspace");
        if (data.empty) {
            empty.hidden = false;
            workspace.hidden = true;
            return;
        }
        empty.hidden = true;
        workspace.hidden = false;
        $("rf-ops-map-name").textContent = data.name || "Day plan";
        $("rf-ops-map-date").textContent = data.calendar_date || "";
        var map = ensureMap();
        map.eachLayer(function (layer) {
            if (layer instanceof L.TileLayer) return;
            map.removeLayer(layer);
        });
        var bounds = [];
        Object.keys(data.courses || {}).forEach(function (raceId) {
            var geo = data.courses[raceId];
            if (!geo) return;
            var layer = L.geoJSON(geo, {
                style: { color: "#2563eb", weight: 3, opacity: 0.7 },
            }).addTo(map);
            if (layer.getBounds && layer.getBounds().isValid()) {
                bounds.push(layer.getBounds());
            }
        });
        (data.locations || []).forEach(function (pin) {
            if (pin.lat == null || pin.lon == null) return;
            var color = STATUS_COLORS[pin.status] || STATUS_COLORS.closed;
            var marker = L.circleMarker([pin.lat, pin.lon], {
                radius: 7,
                color: "#fff",
                weight: 1,
                fillColor: color,
                fillOpacity: 0.95,
            }).addTo(map);
            marker.bindPopup(
                "<div><strong>" +
                    (pin.loc_id || "") +
                    " · " +
                    (pin.loc_label || "") +
                    "</strong><br>Zone " +
                    (pin.zone || "—") +
                    "<br>Planned loc_end " +
                    (pin.loc_end || "—") +
                    "<br>" +
                    statusLabel(pin.status) +
                    "</div>"
            );
            bounds.push(L.latLng(pin.lat, pin.lon));
        });
        if (bounds.length) {
            var group = L.latLngBounds(bounds);
            map.fitBounds(group, { padding: [24, 24] });
        }
        setTimeout(function () {
            map.invalidateSize();
        }, 80);
    }

    function loadMap() {
        return fetch("/api/execute/map")
            .then(function (res) {
                return res.json();
            })
            .then(renderSnapshot)
            .catch(function (err) {
                setStatus(err.message || String(err));
                $("rf-ops-map-empty").hidden = false;
                $("rf-ops-map-workspace").hidden = true;
            });
    }

    bindImport("rf-ops-map-import", true);
    bindImport("rf-ops-map-import-more", false);
    loadMap();
})();
