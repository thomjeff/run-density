/**
 * Course Mapping page: map, Street/Satellite toggle, course New/Open/Save.
 * Issue #732: Course storage under {data_dir}/courses/{id}.
 */

document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('course-mapping-map');
    if (!container) return;

    const loadingEl = container.querySelector('.map-loading');
    const toggleEl = document.getElementById('basemap-toggle');

    // Course state; data_dir is always from app utils constants (runflow root)
    let currentCourseId = null;
    let currentCourse = null;

    function updateCourseUI() {
        const saveBtn = document.getElementById('btn-save-course');
        const label = document.getElementById('current-course-label');
        if (saveBtn) saveBtn.disabled = !currentCourseId;
        if (label) label.textContent = currentCourseId ? 'Course: ' + currentCourseId : '';
    }

    function setCourse(id, course) {
        currentCourseId = id;
        currentCourse = course;
        updateCourseUI();
    }

    try {
        const map = initMap('course-mapping-map');

        // Add Satellite tile layer (Issue #732: Street ↔ Satellite)
        const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: '© Esri',
            maxZoom: 19
        });
        if (!map._layers) map._layers = {};
        map._layers.satellite = satelliteLayer;

        // Hide loading, show toggle
        if (loadingEl) loadingEl.remove();
        if (toggleEl) toggleEl.style.display = 'flex';

        const btnStreet = document.getElementById('btn-street');
        const btnSatellite = document.getElementById('btn-satellite');

        function setBasemap(layerKey) {
            map.eachLayer(function (layer) {
                if (layer instanceof L.TileLayer) map.removeLayer(layer);
            });
            const layer = map._layers[layerKey];
            if (layer) layer.addTo(map);
            if (btnStreet) btnStreet.classList.toggle('active', layerKey === 'carto');
            if (btnSatellite) btnSatellite.classList.toggle('active', layerKey === 'satellite');
        }

        if (btnStreet) btnStreet.addEventListener('click', function () { setBasemap('carto'); });
        if (btnSatellite) btnSatellite.addEventListener('click', function () { setBasemap('satellite'); });

        window.courseMappingMap = map;

        // ——— Course API ———
        const btnNew = document.getElementById('btn-new-course');
        const btnOpen = document.getElementById('btn-open-course');
        const courseList = document.getElementById('course-list');
        const btnLoad = document.getElementById('btn-load-course');
        const btnSave = document.getElementById('btn-save-course');

        if (btnNew) {
            btnNew.addEventListener('click', async function () {
                try {
                    const res = await fetch('/api/courses', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (data.ok && data.course) {
                        setCourse(data.id, data.course);
                        console.log('Created course:', data.id);
                    }
                } catch (e) {
                    console.error('Create course failed:', e);
                    alert('Failed to create course: ' + e.message);
                }
            });
        }

        if (btnOpen) {
            btnOpen.addEventListener('click', async function () {
                try {
                    const res = await fetch('/api/courses');
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (!data.ok || !data.courses) return;
                    if (courseList) {
                        courseList.innerHTML = '<option value="">Select a course...</option>';
                        data.courses.forEach(function (c) {
                            const opt = document.createElement('option');
                            opt.value = c.id;
                            opt.textContent = c.id + (c.updated ? ' (' + c.updated.slice(0, 10) + ')' : '');
                            courseList.appendChild(opt);
                        });
                        courseList.style.display = 'inline-block';
                    }
                    if (btnLoad) btnLoad.style.display = 'inline-block';
                } catch (e) {
                    console.error('List courses failed:', e);
                    alert('Failed to list courses: ' + e.message);
                }
            });
        }

        function loadCourseById(id) {
            if (!id) return;
            fetch('/api/courses/' + encodeURIComponent(id))
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.ok && data.course) {
                        setCourse(data.course.id, data.course);
                        if (courseList) courseList.style.display = 'none';
                        if (btnLoad) btnLoad.style.display = 'none';
                        console.log('Loaded course:', data.course.id);
                    }
                })
                .catch(function (e) {
                    console.error('Load course failed:', e);
                    alert('Failed to load course: ' + e.message);
                });
        }

        if (btnLoad) {
            btnLoad.addEventListener('click', function () {
                if (courseList && courseList.value) loadCourseById(courseList.value);
            });
        }

        if (btnSave) {
            btnSave.addEventListener('click', async function () {
                if (!currentCourseId || !currentCourse) return;
                try {
                    const res = await fetch('/api/courses/' + encodeURIComponent(currentCourseId), {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ course: currentCourse })
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    if (data.ok && data.course) {
                        currentCourse = data.course;
                        updateCourseUI();
                        console.log('Saved course:', currentCourseId);
                    }
                } catch (e) {
                    console.error('Save course failed:', e);
                    alert('Failed to save course: ' + e.message);
                }
            });
        }

        updateCourseUI();
    } catch (e) {
        console.error('Course mapping map init failed:', e);
        if (loadingEl) loadingEl.textContent = 'Failed to load map';
    }
});
