/**
 * Plan Progression map (#864 / #882): spatial race clock, Lead/Last on modeled km(t).
 *
 * Interpolates client-side from the whole-field snapshot + downsampled event GPX.
 * v1 paints Lead/Last only; the field payload is the full pack.
 */
(function () {
    let map = null;
    let setup = null;
    let field = [];
    let eventsById = {};
    let mainOffsetCap = {};
    let courseLayers = [];
    let markers = {};
    let clockSec = 0;
    let playing = false;
    let lastFrameTs = 0;
    let rafId = 0;
    let controlsBound = false;

    function currentDayAndRun() {
        const params = new URLSearchParams(window.location.search);
        const runId = (
            params.get("run_id") ||
            (window.runflowDay && window.runflowDay.run_id) ||
            localStorage.getItem("selected_run_id") ||
            ""
        ).trim();
        const day = (
            (window.runflowDay && window.runflowDay.selected) ||
            localStorage.getItem("selected_day") ||
            ""
        )
            .toLowerCase()
            .trim();
        return { runId: runId, day: day };
    }

    function eventLabel(id) {
        const raw = String(id || "");
        if (raw.toLowerCase() === "10k") return "10K";
        if (!raw) return "";
        return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
    }

    function formatClock(sec) {
        const s = Math.max(0, Math.floor(Number(sec) || 0));
        const hh = String(Math.floor(s / 3600)).padStart(2, "0");
        const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
        const ss = String(s % 60).padStart(2, "0");
        return hh + ":" + mm + ":" + ss;
    }

    function syncPlayPauseButton() {
        const btn = document.getElementById("progression-playpause");
        if (!btn) return;
        const label = playing ? "Pause" : "Play";
        btn.title = label;
        btn.setAttribute("aria-label", label);
        btn.classList.toggle("is-playing", playing);
    }

    function elapsedKmAt(t, gunSec, offsetSec, paceMinPerKm, finishKm) {
        const start = Number(gunSec) + Number(offsetSec || 0);
        if (t < start) return { status: "not_started", km: 0 };
        const km = (t - start) / (Number(paceMinPerKm) * 60);
        if (km >= finishKm) return { status: "finished", km: finishKm };
        return { status: "on_course", km: km };
    }

    function interpLatLon(polyline, targetKm) {
        if (!polyline || !polyline.length) return null;
        if (targetKm <= polyline[0][2]) return [polyline[0][0], polyline[0][1]];
        const last = polyline[polyline.length - 1];
        if (targetKm >= last[2]) return [last[0], last[1]];
        let lo = 0;
        let hi = polyline.length - 1;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (polyline[mid][2] < targetKm) lo = mid + 1;
            else hi = mid;
        }
        const j2 = Math.max(1, lo);
        const j = j2 - 1;
        const d0 = polyline[j][2];
        const d1 = polyline[j2][2];
        if (d1 <= d0) return [polyline[j][0], polyline[j][1]];
        const u = (targetKm - d0) / (d1 - d0);
        return [
            polyline[j][0] + u * (polyline[j2][0] - polyline[j][0]),
            polyline[j][1] + u * (polyline[j2][1] - polyline[j][1]),
        ];
    }

    function computeMainOffsetCaps() {
        const byEvent = {};
        for (let i = 0; i < field.length; i++) {
            const r = field[i];
            if (!byEvent[r.event]) byEvent[r.event] = [];
            byEvent[r.event].push(Number(r.start_offset_sec) || 0);
        }
        mainOffsetCap = {};
        Object.keys(byEvent).forEach(function (eventId) {
            const offs = byEvent[eventId].slice().sort(function (a, b) {
                return a - b;
            });
            const idx = Math.max(
                0,
                Math.min(offs.length - 1, Math.floor(0.99 * (offs.length - 1)))
            );
            mainOffsetCap[eventId] = offs[idx];
        });
    }

    function frontTailByEvent(t) {
        const groups = {};
        for (let i = 0; i < field.length; i++) {
            const r = field[i];
            const ev = eventsById[r.event];
            if (!ev) continue;
            const pos = elapsedKmAt(
                t,
                ev.gun_sec,
                r.start_offset_sec,
                r.pace_min_per_km,
                ev.finish_km
            );
            let g = groups[r.event];
            if (!g) {
                g = groups[r.event] = {
                    front: null,
                    tail: null,
                    frontGone: false,
                    tailGone: false,
                };
            }
            const inMainWave =
                Number(r.start_offset_sec) <= (mainOffsetCap[r.event] || 0);
            // Front: first finisher leaves the course — do not promote 2nd.
            if (pos.status === "finished") {
                g.frontGone = true;
                if (inMainWave) g.mainWaveFinished = true;
                continue;
            }
            if (pos.status !== "on_course") continue;
            const row = { runner: r, km: pos.km };
            if (!g.front || pos.km > g.front.km) g.front = row;
            // Tail: back of the started field. Late chips past the 99th-percentile
            // offset do not inherit the role (same no-successor idea as Front).
            if (inMainWave) {
                g.mainWaveOnCourse = true;
                if (!g.tail || pos.km < g.tail.km) g.tail = row;
            }
        }
        Object.keys(groups).forEach(function (eventId) {
            const g = groups[eventId];
            if (g.frontGone) g.front = null;
            // Main-wave tail has finished (and not merely "not started yet").
            if (!g.mainWaveOnCourse && g.mainWaveFinished) g.tail = null;
        });
        return groups;
    }

    function showEmpty(message) {
        const empty = document.getElementById("progression-empty");
        const root = document.getElementById("progression-root");
        const msg = document.getElementById("progression-empty-msg");
        if (root) root.style.display = "none";
        if (msg && message) msg.textContent = message;
        if (empty) empty.style.display = "";
    }

    function showRoot() {
        const empty = document.getElementById("progression-empty");
        const root = document.getElementById("progression-root");
        if (empty) empty.style.display = "none";
        if (root) root.style.display = "";
    }

    function ensureMap() {
        if (map) return map;
        map = window.initMap("progression-map", { zoomPosition: "topleft" });
        if (typeof window.enableBasemapToggle === "function") {
            window.enableBasemapToggle(map);
        }
        return map;
    }

    function drawCourses() {
        courseLayers.forEach(function (layer) {
            map.removeLayer(layer);
        });
        courseLayers = [];
        const bounds = [];
        (setup.events || []).forEach(function (ev) {
            const latlngs = (ev.polyline || []).map(function (p) {
                return [p[0], p[1]];
            });
            if (latlngs.length < 2) return;
            const line = L.polyline(latlngs, {
                color: ev.color,
                weight: 2,
                opacity: 0.55,
            }).addTo(map);
            courseLayers.push(line);
            latlngs.forEach(function (ll) {
                bounds.push(ll);
            });
        });
        if (bounds.length) {
            map.fitBounds(bounds, { padding: [28, 28] });
        }
    }

    function renderLegend() {
        const el = document.getElementById("progression-legend");
        if (!el) return;
        const bits = [];
        (setup.events || []).forEach(function (ev) {
            const label = eventLabel(ev.id);
            bits.push(
                '<span class="progression-legend-event" style="color:' +
                    ev.color +
                    '">' +
                    '<span class="progression-legend-item">' +
                    '<span class="progression-swatch is-lead"></span>' +
                    label +
                    " Lead</span>" +
                    '<span class="progression-legend-item">' +
                    '<span class="progression-swatch is-last"></span>' +
                    label +
                    " Last</span>" +
                    "</span>"
            );
        });
        el.innerHTML = bits.join("");
    }

    function markerKey(eventId, role) {
        return eventId + ":" + role;
    }

    function upsertMarker(key, latlng, color, filled, title) {
        let marker = markers[key];
        if (!marker) {
            marker = L.circleMarker(latlng, {
                radius: 9,
                color: filled ? "#fff" : color,
                weight: 3,
                fillColor: filled ? color : "#fff",
                fillOpacity: 1,
            }).addTo(map);
            markers[key] = marker;
        } else {
            marker.setLatLng(latlng);
            marker.setStyle({
                color: filled ? "#fff" : color,
                weight: 3,
                fillColor: filled ? color : "#fff",
                fillOpacity: 1,
            });
        }
        marker.bindTooltip(title, { direction: "top", offset: [0, -8] });
    }

    function hideUnused(activeKeys) {
        Object.keys(markers).forEach(function (key) {
            if (activeKeys[key]) return;
            map.removeLayer(markers[key]);
            delete markers[key];
        });
    }

    function paintAt(t) {
        clockSec = t;
        const clockEl = document.getElementById("progression-clock");
        if (clockEl) clockEl.textContent = formatClock(t);
        const scrub = document.getElementById("progression-scrub");
        if (scrub && document.activeElement !== scrub) {
            scrub.value = String(Math.round(t));
        }
        const groups = frontTailByEvent(t);
        const active = {};
        Object.keys(groups).forEach(function (eventId) {
            const ev = eventsById[eventId];
            const g = groups[eventId];
            const same =
                g.front &&
                g.tail &&
                g.front.runner.id === g.tail.runner.id;
            function place(role, row, filled) {
                const ll = interpLatLon(ev.polyline, row.km);
                if (!ll) return;
                const key = markerKey(eventId, role);
                active[key] = true;
                const title =
                    eventLabel(eventId) +
                    " " +
                    (same && g.front && g.tail
                        ? "Lead/Last"
                        : role === "front"
                          ? "Lead"
                          : "Last") +
                    " · " +
                    row.km.toFixed(2) +
                    " km";
                upsertMarker(key, ll, ev.color, filled, title);
            }
            if (same) {
                place("front", g.front, true);
            } else {
                if (g.front) place("front", g.front, true);
                if (g.tail) place("tail", g.tail, false);
            }
        });
        hideUnused(active);
    }

    function setPlaying(next) {
        playing = next;
        syncPlayPauseButton();
        if (playing) {
            lastFrameTs = 0;
            if (!rafId) rafId = requestAnimationFrame(tick);
        }
    }

    function tick(ts) {
        rafId = 0;
        if (!playing || !setup) return;
        if (!lastFrameTs) lastFrameTs = ts;
        const dt = (ts - lastFrameTs) / 1000;
        lastFrameTs = ts;
        const speedEl = document.getElementById("progression-speed");
        const speed = Number(speedEl && speedEl.value) || 30;
        let next = clockSec + dt * speed;
        if (next >= setup.t1_sec) {
            next = setup.t1_sec;
            paintAt(next);
            setPlaying(false);
            return;
        }
        paintAt(next);
        rafId = requestAnimationFrame(tick);
    }

    function bindControls() {
        if (controlsBound) return;
        controlsBound = true;
        const playPause = document.getElementById("progression-playpause");
        const reset = document.getElementById("progression-reset");
        const scrub = document.getElementById("progression-scrub");
        if (playPause) {
            playPause.addEventListener("click", function () {
                if (!setup) return;
                if (playing) {
                    setPlaying(false);
                    return;
                }
                if (clockSec >= setup.t1_sec) paintAt(setup.t0_sec);
                setPlaying(true);
            });
        }
        if (reset) {
            reset.addEventListener("click", function () {
                setPlaying(false);
                if (setup) paintAt(setup.t0_sec);
            });
        }
        if (scrub) {
            scrub.addEventListener("input", function () {
                setPlaying(false);
                paintAt(Number(scrub.value));
            });
        }
    }

    async function fetchJson(url) {
        const res = await fetch(url, { credentials: "same-origin" });
        const body = await res.json().catch(function () {
            return {};
        });
        if (!res.ok) {
            const detail = body.detail || body.error || res.statusText;
            const err = new Error(detail);
            err.status = res.status;
            throw err;
        }
        return body;
    }

    async function load() {
        const ctx = currentDayAndRun();
        if (!ctx.runId) {
            showEmpty("No analysis run selected. Choose a run to open Progression.");
            return;
        }
        const qs = ctx.day ? "?day=" + encodeURIComponent(ctx.day) : "";
        const base = "/api/runs/" + encodeURIComponent(ctx.runId) + "/progression/";
        let setupPayload;
        let fieldPayload;
        try {
            setupPayload = await fetchJson(base + "setup" + qs);
            fieldPayload = await fetchJson(base + "field" + qs);
        } catch (err) {
            const msg =
                err.status === 404
                    ? err.message ||
                      "No trajectory snapshot for this run/day. Re-run analysis."
                    : err.message || "Progression failed to load.";
            showEmpty(msg);
            return;
        }
        setup = setupPayload;
        field = fieldPayload.runners || [];
        eventsById = {};
        (setup.events || []).forEach(function (ev) {
            eventsById[ev.id] = ev;
        });
        computeMainOffsetCaps();
        showRoot();
        ensureMap();
        drawCourses();
        renderLegend();
        const scrub = document.getElementById("progression-scrub");
        if (scrub) {
            scrub.min = String(setup.t0_sec);
            scrub.max = String(setup.t1_sec);
            scrub.step = "1";
        }
        bindControls();
        syncPlayPauseButton();
        paintAt(setup.t0_sec);
    }

    let started = false;
    function start() {
        if (started) return;
        started = true;
        load();
    }

    document.addEventListener("DOMContentLoaded", function () {
        window.addEventListener("runflow:context-ready", start);
        setTimeout(start, 1600);
    });
})();
