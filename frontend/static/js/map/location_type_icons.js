/**
 * Shared location-type icons for Build → Plan → Execute (Issue #929).
 *
 * Type glyphs/colors are one layer; Reopen / Case status is a separate ring.
 * Stay on LOCATION_TYPE_CHOICES: aid, extract, official, traffic, water
 * (legacy "course" → traffic).
 */
(function (global) {
    'use strict';

    var COLORS = {
        aid: '#e74c3c',
        extract: '#9c27b0',
        official: '#f1c40f',
        traffic: '#27ae60',
        water: '#3498db',
        unknown: '#95a5a6',
    };

    var LABELS = {
        aid: 'Aid',
        extract: 'Extract',
        official: 'Official',
        traffic: 'Traffic',
        water: 'Water',
        unknown: 'Location',
    };

    function normalizeType(raw) {
        var t = String(raw || '')
            .trim()
            .toLowerCase()
            .replace(/-/g, '_');
        if (t === 'course') return 'traffic';
        if (t === 'first_aid' || t === 'firstaid') return 'aid';
        if (t === 'extraction') return 'extract';
        if (COLORS[t]) return t;
        return 'unknown';
    }

    function color(raw) {
        return COLORS[normalizeType(raw)] || COLORS.unknown;
    }

    function label(raw) {
        return LABELS[normalizeType(raw)] || LABELS.unknown;
    }

    function glyphSvg(raw, fill) {
        var t = normalizeType(raw);
        var c = fill || color(t);
        if (t === 'water') {
            return (
                '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">' +
                '<path fill="' +
                c +
                '" d="M12 2.5C12 2.5 5.5 10.2 5.5 14.2a6.5 6.5 0 0 0 13 0C18.5 10.2 12 2.5 12 2.5z"/>' +
                '</svg>'
            );
        }
        if (t === 'aid') {
            return (
                '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">' +
                '<rect x="3" y="3" width="18" height="18" rx="3" fill="' +
                c +
                '"/>' +
                '<rect x="10.2" y="6.5" width="3.6" height="11" fill="#fff"/>' +
                '<rect x="6.5" y="10.2" width="11" height="3.6" fill="#fff"/>' +
                '</svg>'
            );
        }
        if (t === 'extract') {
            return (
                '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">' +
                '<path fill="' +
                c +
                '" d="M12 2.8 21.2 21.2H2.8L12 2.8z"/>' +
                '<rect x="10.8" y="9.2" width="2.4" height="6.2" fill="#fff"/>' +
                '<rect x="10.8" y="16.4" width="2.4" height="2.2" fill="#fff"/>' +
                '</svg>'
            );
        }
        if (t === 'official') {
            return (
                '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">' +
                '<circle cx="12" cy="12" r="9.2" fill="' +
                c +
                '"/>' +
                '<circle cx="12" cy="12" r="4.2" fill="#fff"/>' +
                '</svg>'
            );
        }
        // traffic / unknown: solid disc (off-course traffic uses hollow ring via options)
        return (
            '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">' +
            '<circle cx="12" cy="12" r="9.2" fill="' +
            c +
            '"/>' +
            '</svg>'
        );
    }

    /**
     * @param {string} locType
     * @param {{
     *   size?: number,
     *   statusColor?: string|null,
     *   offCourse?: boolean,
     *   focused?: boolean,
     *   className?: string
     * }} [opts]
     */
    function markerHtml(locType, opts) {
        opts = opts || {};
        var size = opts.size || 18;
        var t = normalizeType(locType);
        var typeColor = color(t);
        var statusColor = opts.statusColor || null;
        var offCourse = !!opts.offCourse && t === 'traffic';
        var focused = !!opts.focused;
        var ring = statusColor || (focused ? '#182433' : '#ffffff');
        var ringWidth = focused || statusColor ? 3 : 2;
        var inner = offCourse
            ? '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true">' +
              '<circle cx="12" cy="12" r="8" fill="#fff" stroke="' +
              typeColor +
              '" stroke-width="3"/>' +
              '</svg>'
            : glyphSvg(t, typeColor);
        return (
            '<div class="rf-loc-type-marker' +
            (opts.className ? ' ' + opts.className : '') +
            '" style="width:' +
            size +
            'px;height:' +
            size +
            'px;border-radius:50%;box-sizing:border-box;border:' +
            ringWidth +
            'px solid ' +
            ring +
            ';background:#fff;overflow:hidden;display:flex;align-items:center;justify-content:center;">' +
            '<div style="width:70%;height:70%;line-height:0;">' +
            inner +
            '</div></div>'
        );
    }

    function leafletDivIcon(L, locType, opts) {
        opts = opts || {};
        var size = opts.size || 18;
        if (!L || !L.divIcon) return null;
        return L.divIcon({
            className: 'rf-loc-type-icon' + (opts.className ? ' ' + opts.className : ''),
            html: markerHtml(locType, opts),
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
        });
    }

    function legendItems() {
        return ['water', 'aid', 'extract', 'official', 'traffic'].map(function (t) {
            return { type: t, label: LABELS[t], color: COLORS[t], html: markerHtml(t, { size: 16 }) };
        });
    }

    global.LocationTypeIcons = {
        COLORS: COLORS,
        LABELS: LABELS,
        normalizeType: normalizeType,
        color: color,
        label: label,
        glyphSvg: glyphSvg,
        markerHtml: markerHtml,
        leafletDivIcon: leafletDivIcon,
        legendItems: legendItems,
    };
})(typeof window !== 'undefined' ? window : this);
