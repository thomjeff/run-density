/**
 * Plan Progression map (#864 / #882 / #881): spatial race clock, Lead/Last,
 * and a course-active wallboard on the same analysis t.
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

    function formatClockHm(sec) {
        const s = Math.max(0, Math.floor(Number(sec) || 0));
        const hh = String(Math.floor(s / 3600)).padStart(2, "0");
        const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
        return hh + ":" + mm;
    }

    function clockPct(t) {
        if (!setup) return 0;
        const span = Number(setup.t1_sec) - Number(setup.t0_sec);
        if (span <= 0) return 0;
        const u = (Number(t) - Number(setup.t0_sec)) / span;
        return Math.max(0, Math.min(100, u * 100));
    }

    function axisTickStep(spanSec) {
        if (spanSec > 6 * 3600) return 3600;
        if (spanSec > 90 * 60) return 1800;
        if (spanSec > 30 * 60) return 900;
        return 300;
    }

    function axisTicks(t0, t1) {
        const span = t1 - t0;
        const step = axisTickStep(span);
        const ticks = [];
        let t = Math.ceil(t0 / step) * step;
        while (t <= t1) {
            ticks.push(t);
            t += step;
        }
        if (!ticks.length || ticks[0] - t0 > step * 0.35) {
            ticks.unshift(t0);
        }
        if (t1 - ticks[ticks.length - 1] > step * 0.35) {
            ticks.push(t1);
        }
        return ticks;
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

    function renderWallboard() {
        const root = document.getElementById("progression-wallboard");
        if (!root || !setup) return;
        const events = (setup.events || []).filter(function (ev) {
            return (
                ev.active_start_sec != null &&
                ev.active_end_sec != null &&
                Number(ev.active_end_sec) > Number(ev.active_start_sec)
            );
        });
        if (!events.length) {
            root.hidden = true;
            root.innerHTML = "";
            return;
        }
        const t0 = Number(setup.t0_sec);
        const t1 = Number(setup.t1_sec);
        const ticks = axisTicks(t0, t1);
        const tickHtml = ticks
            .map(function (t, i) {
                const edge =
                    i === 0
                        ? " is-edge-start"
                        : i === ticks.length - 1
                          ? " is-edge-end"
                          : "";
                return (
                    '<span class="progression-wallboard-tick" style="left:' +
                    clockPct(t).toFixed(3) +
                    '%">' +
                    '<span class="progression-wallboard-tick-mark"></span>' +
                    '<span class="progression-wallboard-tick-label' +
                    edge +
                    '">' +
                    formatClockHm(t) +
                    "</span></span>"
                );
            })
            .join("");
        const labelsHtml = events
            .map(function (ev) {
                return (
                    '<div class="progression-wallboard-label">' +
                    eventLabel(ev.id) +
                    "</div>"
                );
            })
            .join("");
        const tracksHtml = events
            .map(function (ev) {
                const startPct = clockPct(ev.active_start_sec);
                const endPct = clockPct(ev.active_end_sec);
                const width = Math.max(0, endPct - startPct);
                const label = eventLabel(ev.id);
                const title =
                    label +
                    " on course " +
                    formatClockHm(ev.active_start_sec) +
                    "–" +
                    formatClockHm(ev.active_end_sec);
                return (
                    '<div class="progression-wallboard-track" data-event="' +
                    ev.id +
                    '" style="color:' +
                    ev.color +
                    '" title="' +
                    title +
                    '">' +
                    '<span class="progression-wallboard-bar" style="left:' +
                    startPct.toFixed(3) +
                    "%;width:" +
                    width.toFixed(3) +
                    '%"></span>' +
                    '<span class="progression-wallboard-dot is-start" style="left:' +
                    startPct.toFixed(3) +
                    '%" title="First modeled start"></span>' +
                    '<span class="progression-wallboard-dot is-end" style="left:' +
                    endPct.toFixed(3) +
                    '%" title="Last modeled finish"></span>' +
                    "</div>"
                );
            })
            .join("");
        root.innerHTML =
            '<div class="progression-wallboard-body">' +
            '<div class="progression-wallboard-labels">' +
            labelsHtml +
            "</div>" +
            '<div class="progression-wallboard-time" id="progression-wallboard-seek">' +
            '<div class="progression-wallboard-stack">' +
            tracksHtml +
            "</div>" +
            '<div class="progression-wallboard-axis">' +
            tickHtml +
            "</div>" +
            '<div class="progression-wallboard-playhead" id="progression-wallboard-playhead"></div>' +
            "</div></div>" +
            '<p class="progression-wallboard-key">' +
            '<span class="progression-wallboard-key-item">' +
            '<span class="progression-swatch is-lead"></span>First modeled start</span>' +
            '<span class="progression-wallboard-key-item">' +
            '<span class="progression-swatch is-last"></span>Last modeled finish</span>' +
            "</p>";
        root.hidden = false;
    }

    function syncWallboard(t) {
        const playhead = document.getElementById("progression-wallboard-playhead");
        if (playhead) playhead.style.left = clockPct(t).toFixed(3) + "%";
        const root = document.getElementById("progression-wallboard");
        if (!root) return;
        root.querySelectorAll(".progression-wallboard-track[data-event]").forEach(
            function (row) {
                const ev = eventsById[row.getAttribute("data-event")];
                if (!ev) return;
                const onCourse =
                    t >= Number(ev.active_start_sec) &&
                    t <= Number(ev.active_end_sec);
                row.classList.toggle("is-on-course", onCourse);
            }
        );
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
        syncWallboard(t);
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
        const wallboard = document.getElementById("progression-wallboard");
        if (wallboard) {
            wallboard.addEventListener("click", function (ev) {
                const seek = document.getElementById("progression-wallboard-seek");
                if (!setup || !seek || !seek.contains(ev.target)) return;
                const rect = seek.getBoundingClientRect();
                if (!rect.width) return;
                const u = Math.max(
                    0,
                    Math.min(1, (ev.clientX - rect.left) / rect.width)
                );
                const next = Math.round(
                    Number(setup.t0_sec) +
                        u * (Number(setup.t1_sec) - Number(setup.t0_sec))
                );
                setPlaying(false);
                paintAt(next);
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
        renderWallboard();
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
