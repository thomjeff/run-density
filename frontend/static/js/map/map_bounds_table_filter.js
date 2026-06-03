/**
 * Map viewport → table row filter (Issue #634 pattern used on Segments / Locations pages).
 */
(function () {
    'use strict';

    function create(options) {
        var debounceMs = options.debounceMs || 150;
        var programmaticDelay = options.programmaticDelay || 600;
        var isProgrammatic = false;
        var timeout = null;
        var allItems = [];
        var attachedMap = null;
        var debouncedHandler = null;

        function getMap() {
            return options.getMap ? options.getMap() : null;
        }

        function filterNow() {
            if (isProgrammatic) return;
            var map = getMap();
            if (!map) {
                if (options.onFilter) options.onFilter(allItems.slice(), { total: allItems.length, visible: allItems.length });
                return;
            }
            var bounds = map.getBounds();
            if (!bounds || !bounds.isValid()) return;
            var visible = allItems.filter(function (item) {
                try {
                    return options.isItemInBounds(item, bounds);
                } catch (e) {
                    return true;
                }
            });
            if (options.onFilter) {
                options.onFilter(visible, {
                    total: allItems.length,
                    visible: visible.length
                });
            }
        }

        function debouncedFilter() {
            if (timeout) clearTimeout(timeout);
            timeout = setTimeout(filterNow, debounceMs);
        }

        function setAllItems(items) {
            allItems = items || [];
            filterNow();
        }

        function setProgrammatic(flag) {
            isProgrammatic = !!flag;
        }

        function runProgrammatic(fn) {
            isProgrammatic = true;
            try {
                if (typeof fn === 'function') fn();
            } finally {
                setTimeout(function () {
                    isProgrammatic = false;
                    filterNow();
                }, programmaticDelay);
            }
        }

        function attach(map) {
            if (!map) return;
            if (attachedMap && attachedMap !== map) detach(attachedMap);
            if (attachedMap === map) return;
            debouncedHandler = debouncedFilter;
            map.on('moveend', debouncedHandler);
            map.on('zoomend', debouncedHandler);
            attachedMap = map;
        }

        function detach(map) {
            var target = map || attachedMap;
            if (!target || !debouncedHandler) return;
            target.off('moveend', debouncedHandler);
            target.off('zoomend', debouncedHandler);
            if (attachedMap === target) attachedMap = null;
        }

        return {
            setAllItems: setAllItems,
            filterNow: filterNow,
            attach: attach,
            detach: detach,
            setProgrammatic: setProgrammatic,
            runProgrammatic: runProgrammatic
        };
    }

    window.MapBoundsTableFilter = { create: create };
})();
