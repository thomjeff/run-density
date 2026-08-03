/**
 * Issue #810: Collapse paired reverse-leg location rows for map + table.
 * Outbound = earlier first_runner; return = later.
 */
(function (global) {
    'use strict';

    function timeToSeconds(value) {
        if (value == null || value === '' || value === 'NA') return null;
        const text = String(value).trim();
        const parts = text.split(':');
        if (parts.length < 2) return null;
        const h = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const s = parts.length >= 3 ? parseInt(parts[2], 10) : 0;
        if (Number.isNaN(h) || Number.isNaN(m)) return null;
        return h * 3600 + m * 60 + (Number.isNaN(s) ? 0 : s);
    }

    function pickMinTime(values) {
        let best = null;
        let bestSec = null;
        values.forEach((v) => {
            const sec = timeToSeconds(v);
            if (sec == null) return;
            if (bestSec == null || sec < bestSec) {
                bestSec = sec;
                best = v;
            }
        });
        return best;
    }

    function pickMaxTime(values) {
        let best = null;
        let bestSec = null;
        values.forEach((v) => {
            const sec = timeToSeconds(v);
            if (sec == null) return;
            if (bestSec == null || sec > bestSec) {
                bestSec = sec;
                best = v;
            }
        });
        return best;
    }

    function mergeByEventMaps(maps) {
        const merged = {};
        (maps || []).forEach((raw) => {
            let map = raw;
            if (typeof map === 'string') {
                try { map = JSON.parse(map); } catch (e) { map = null; }
            }
            if (!map || typeof map !== 'object') return;
            Object.keys(map).forEach((ev) => {
                const w = map[ev] || {};
                if (!merged[ev]) {
                    merged[ev] = {
                        first_runner: w.first_runner,
                        peak_start: w.peak_start,
                        peak_end: w.peak_end,
                        last_runner: w.last_runner,
                    };
                    return;
                }
                const cur = merged[ev];
                cur.first_runner = pickMinTime([cur.first_runner, w.first_runner]);
                cur.peak_start = pickMinTime([cur.peak_start, w.peak_start]);
                cur.peak_end = pickMaxTime([cur.peak_end, w.peak_end]);
                cur.last_runner = pickMaxTime([cur.last_runner, w.last_runner]);
            });
        });
        return Object.keys(merged).length ? merged : null;
    }

    function effectiveKey(loc) {
        const key = loc && (loc.pass_key != null ? loc.pass_key : loc.location_key);
        const text = key != null ? String(key).trim() : '';
        if (text && text.toLowerCase() !== 'nan' && text.toLowerCase() !== 'null') return text;
        return '';
    }

    function assignPasses(group) {
        const ordered = [...group].sort((a, b) => {
            const fa = timeToSeconds(a.first_runner);
            const fb = timeToSeconds(b.first_runner);
            const sa = fa == null ? Number.MAX_SAFE_INTEGER : fa;
            const sb = fb == null ? Number.MAX_SAFE_INTEGER : fb;
            if (sa !== sb) return sa - sb;
            const pa = Number(a.pass_id != null ? a.pass_id : a.loc_id);
            const pb = Number(b.pass_id != null ? b.pass_id : b.loc_id);
            return pa - pb;
        });
        return ordered.map((row, i) => {
            const copy = { ...row };
            copy.pass = i === 0 ? 'outbound' : 'return';
            const peer = i === 0 ? ordered[1] : ordered[0];
            const peerPass = peer ? (peer.pass_id != null ? peer.pass_id : peer.loc_id) : '';
            copy.same_pass_as = peerPass;
            copy.same_location_as = peerPass;
            return copy;
        });
    }

    /**
     * @param {Array} locations flat API rows
     * @returns {Array} location-centric rows (paired collapsed)
     */
    function collapseLocationsByKey(locations) {
        if (!Array.isArray(locations)) return [];
        const byKey = new Map();
        const singles = [];

        locations.forEach((loc) => {
            const key = effectiveKey(loc);
            if (!key) {
                singles.push({
                    ...loc,
                    paired: false,
                    primary_loc_id: loc.loc_id,
                    loc_ids: [loc.loc_id],
                    passes: [{ ...loc, pass: '' }],
                });
                return;
            }
            if (!byKey.has(key)) byKey.set(key, []);
            byKey.get(key).push(loc);
        });

        const groups = [...singles];
        byKey.forEach((group, key) => {
            if (group.length === 1) {
                const loc = group[0];
                groups.push({
                    ...loc,
                    location_key: key,
                    paired: false,
                    primary_loc_id: loc.loc_id,
                    loc_ids: [loc.loc_id],
                    passes: [{ ...loc, pass: '' }],
                });
                return;
            }
            const passes = assignPasses(group);
            const primary = passes[0];
            // Human loc_id is shared; fall back to primary row's loc_id
            const humanLocId = primary.loc_id;
            const merged = {
                ...primary,
                pass_key: key,
                location_key: key,
                loc_id: humanLocId,
                primary_loc_id: humanLocId,
                loc_ids: [humanLocId],
                pass_ids: passes.map((p) => (p.pass_id != null ? p.pass_id : p.loc_id)),
                paired: true,
                passes,
                first_runner: pickMinTime(passes.map((p) => p.first_runner)),
                last_runner: pickMaxTime(passes.map((p) => p.last_runner)),
                loc_start: pickMinTime(passes.map((p) => p.loc_start)),
                loc_end: pickMaxTime(passes.map((p) => p.loc_end)),
                peak_start: pickMinTime(passes.map((p) => p.peak_start)),
                peak_end: pickMaxTime(passes.map((p) => p.peak_end)),
                by_event: mergeByEventMaps(passes.map((p) => p.by_event)),
                flag: passes.some((p) => p.flag === true || p.flag === 'true' || p.flag === 'Y'),
                onepage: passes.some((p) => String(p.onepage || '').toLowerCase() === 'y')
                    ? 'y'
                    : primary.onepage,
            };
            // Prefer max resource counts across passes
            passes.forEach((p) => {
                Object.keys(p).forEach((k) => {
                    if (!k.endsWith('_count') && !k.endsWith('_mins')) return;
                    const n = Number(p[k]) || 0;
                    const cur = Number(merged[k]) || 0;
                    if (n > cur) merged[k] = p[k];
                });
            });
            groups.push(merged);
        });

        groups.sort((a, b) => Number(a.primary_loc_id || a.loc_id) - Number(b.primary_loc_id || b.loc_id));
        return groups;
    }

    global.LocationPairing = {
        collapseLocationsByKey,
        timeToSeconds,
        effectiveKey,
    };
})(typeof window !== 'undefined' ? window : globalThis);
