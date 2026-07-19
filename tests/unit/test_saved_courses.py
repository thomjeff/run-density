"""Tests for global org courses and package course assignment."""

import json

import yaml

from app.core.config_package.saved_courses import (
    allocate_next_course_id,
    build_package_race_exports,
    delete_org_course,
    get_package_course_assignments,
    get_org_course_route_preview,
    list_org_courses,
    normalize_course_id,
    rename_org_course,
    renumber_org_courses_to_numeric,
    save_org_course,
    update_org_course,
    set_package_course_assignments,
)
from app.core.config_package.segment_recipes import save_package_segment_manifest
from app.core.config_package.storage import create_config_package, resolve_config_package_path

_GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Org trail</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.utils.run_id.get_runflow_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.core.config_package.saved_courses.get_runflow_root",
        lambda: tmp_path,
    )


def _seed_org_legs(tmp_path, leg_ids=("05", "06")):
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    manifest_legs = []
    for leg_id in leg_ids:
        gpx_name = f"{leg_id}_trail.gpx"
        (org_dir / gpx_name).write_text(_GPX, encoding="utf-8")
        manifest_legs.append(
            {
                "id": leg_id,
                "file": gpx_name,
                "seg_label": f"Leg {leg_id}",
                "start_label": "Start",
                "end_label": "End",
            }
        )
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump({"legs": manifest_legs}),
        encoding="utf-8",
    )


def test_normalize_course_id_from_name():
    assert normalize_course_id("", distance="10k", name="University Ave") == "10k-university-ave"
    assert normalize_course_id("", distance="10k", name="10K River Trail") == "10k-river-trail"
    assert normalize_course_id("3") == "03"
    assert normalize_course_id("12") == "12"


def test_allocate_next_course_id_skips_legacy_slugs(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    courses_dir = tmp_path / "org" / "courses"
    courses_dir.mkdir(parents=True)
    (courses_dir / "10k-university").mkdir()
    (courses_dir / "03").mkdir()
    (courses_dir / "manifest.yaml").write_text(
        yaml.safe_dump({"courses": [{"id": "10k-university"}, {"id": "02"}]}),
        encoding="utf-8",
    )
    assert allocate_next_course_id() == "04"


def test_save_org_course_allocates_numeric_id_when_unspecified(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path)

    saved = save_org_course(
        name="10K University",
        distance="10k",
        recipe=["05", "06"],
    )
    assert saved["saved_course"]["id"] == "01"
    assert (tmp_path / "org" / "courses" / "01").is_dir()

    saved2 = save_org_course(
        name="10K River Trail",
        distance="10k",
        recipe=["06", "05"],
    )
    assert saved2["saved_course"]["id"] == "02"


def test_save_org_course_writes_frozen_exports(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path)

    saved = save_org_course(
        name="10K University",
        distance="10k",
        recipe=["05", "06"],
        course_id="10k-university",
    )
    assert saved["saved_course"]["id"] == "10k-university"
    assert saved["saved_course"]["distance"] == "10k"

    course_dir = tmp_path / "org" / "courses" / "10k-university"
    assert (course_dir / "segments.csv").is_file()
    assert (course_dir / "flow.csv").is_file()
    assert (course_dir / "locations.csv").is_file()
    assert (course_dir / "10k.gpx").is_file()
    assert (course_dir / "leg_library" / "05_trail.gpx").is_file()
    meta = json.loads((course_dir / "saved_course.json").read_text(encoding="utf-8"))
    assert meta["name"] == "10K University"
    assert meta["analysis_data_dir"] == "runflow/org/courses/10k-university"

    listed = list_org_courses()
    assert len(listed) == 1
    assert listed[0]["analyze_ready"] is True

    saved2 = save_org_course(
        name="10K River Trail",
        distance="10k",
        recipe=["06", "05"],
        course_id="10k-river-trail",
    )
    assert saved2["saved_course"]["id"] == "10k-river-trail"
    assert len(list_org_courses()) == 2
    assert len(list_org_courses(distance="10k")) == 2

    delete_org_course("10k-university")
    assert len(list_org_courses()) == 1
    assert not course_dir.is_dir()


def test_save_org_course_includes_paired_legs_in_snapshot(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    for leg_id in ("20", "21", "14"):
        (org_dir / f"{leg_id}_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "20",
                        "file": "20_trail.gpx",
                        "seg_label": "Leg 20",
                        "paired_with": "21",
                    },
                    {
                        "id": "21",
                        "file": "21_trail.gpx",
                        "seg_label": "Leg 21",
                        "paired_with": "20",
                    },
                    {"id": "14", "file": "14_trail.gpx", "seg_label": "Leg 14"},
                ]
            }
        ),
        encoding="utf-8",
    )

    saved = save_org_course(
        name="10K River Trail",
        distance="10k",
        recipe=["20", "14"],
        course_id="10k-river-trail",
    )
    assert not any("unknown leg" in w for w in saved.get("stitch_warnings") or [])
    assert not any("inactive" in w for w in saved.get("stitch_warnings") or [])

    lib_manifest = yaml.safe_load(
        (tmp_path / "org" / "courses" / "10k-river-trail" / "leg_library" / "manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    snap_ids = {leg["id"] for leg in lib_manifest["legs"]}
    assert snap_ids == {"20", "21", "14"}

    preview = get_org_course_route_preview("10k-river-trail")
    assert preview["recipe"] == ["20", "14"]
    assert len(preview["coordinates"]) >= 2
    assert len(preview["recipe_legs"]) == 2
    assert preview["recipe_legs"][0]["order"] == 1
    assert preview["recipe_legs"][0]["id"] == "20"


def test_update_org_course_recipe(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path, leg_ids=("05", "06", "07"))

    save_org_course(
        name="10K River Trail",
        distance="10k",
        recipe=["05", "06"],
        course_id="10k-river-trail",
    )
    updated = update_org_course("10k-river-trail", recipe=["05", "07"])
    assert updated["saved_course"]["recipe"] == ["05", "07"]
    assert updated["saved_course"]["id"] == "10k-river-trail"

    meta = json.loads(
        (
            tmp_path / "org" / "courses" / "10k-river-trail" / "saved_course.json"
        ).read_text(encoding="utf-8")
    )
    assert meta["recipe"] == ["05", "07"]
    preview = get_org_course_route_preview("10k-river-trail")
    assert preview["recipe"] == ["05", "07"]


def test_renumber_org_courses_to_numeric(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path)

    save_org_course(
        name="10K River Trail",
        distance="10k",
        recipe=["05", "06"],
        course_id="10k-river-trail",
    )
    save_org_course(
        name="10K University",
        distance="10k",
        recipe=["06", "05"],
        course_id="10k-university",
    )

    result = renumber_org_courses_to_numeric()
    assert result["ok"] is True
    assert len(result["renamed"]) == 2
    ids = {row["id"] for row in result["courses"]}
    assert ids == {"01", "02"}
    assert not (tmp_path / "org" / "courses" / "10k-river-trail").exists()
    assert (tmp_path / "org" / "courses" / "01" / "saved_course.json").is_file()
    meta = json.loads(
        (tmp_path / "org" / "courses" / "01" / "saved_course.json").read_text(encoding="utf-8")
    )
    assert meta["id"] == "01"
    assert meta["analysis_data_dir"] == "runflow/org/courses/01"


def test_package_assign_and_build_race_exports(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path, leg_ids=("05", "06", "07"))

    save_org_course(
        name="Full A",
        distance="full",
        recipe=["05", "06"],
        course_id="full-a",
    )
    save_org_course(
        name="Half A",
        distance="half",
        recipe=["05", "07"],
        course_id="half-a",
    )
    save_org_course(
        name="10K University",
        distance="10k",
        recipe=["05", "06"],
        course_id="10k-university",
    )

    result = create_config_package(
        "FM2027",
        "",
        event_day="sun",
        package_events=["full", "half", "10k"],
    )
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": [], "half": [], "10k": []},
            "flow_overrides": [],
        },
    )

    assigned = set_package_course_assignments(
        config_id,
        {
            "full": "full-a",
            "half": "half-a",
            "10k": "10k-university",
        },
    )
    assert assigned["assigned_courses"]["10k"] == "10k-university"
    assert get_package_course_assignments(config_id)["resolved"]["full"]["name"] == "Full A"

    built = build_package_race_exports(config_id)
    assert built["ok"] is True
    package_path = resolve_config_package_path(config_id)
    assert (package_path / "segments.csv").is_file()
    assert (package_path / "flow.csv").is_file()
    assert (package_path / "full.gpx").is_file()
    assert (package_path / "half.gpx").is_file()
    assert (package_path / "10k.gpx").is_file()


def test_build_race_exports_uses_saved_course_location_types(tmp_path, monkeypatch):
    """Stale package course rows must not override saved course leg snapshots."""
    import csv

    _patch_roots(tmp_path, monkeypatch)
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    gpx_name = "33_trail.gpx"
    (org_dir / gpx_name).write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "33",
                        "file": gpx_name,
                        "seg_label": "University",
                        "start_label": "Start",
                        "end_label": "End",
                        "locations": [
                            {
                                "loc_label": "University at George",
                                "loc_type": "course",
                                "lat": 45.955,
                                "lon": -66.634,
                                "placement": "along",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    save_org_course(
        name="10K University",
        distance="10k",
        recipe=["33"],
        course_id="02",
    )

    result = create_config_package(
        "Race build loc types",
        "",
        event_day="sun",
        package_events=["10k"],
    )
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"10k": []},
            "flow_overrides": [],
        },
    )
    set_package_course_assignments(config_id, {"10k": "02"})
    build_package_race_exports(config_id)

    package_path = resolve_config_package_path(config_id)
    course_path = package_path / "course.json"
    course = json.loads(course_path.read_text(encoding="utf-8"))
    stale = course["locations"][0]
    stale["loc_type"] = "traffic"
    stale["seg_id"] = ""
    course_path.write_text(json.dumps(course, indent=2), encoding="utf-8")

    build_package_race_exports(config_id)

    rows = list(csv.DictReader((package_path / "locations.csv").open(encoding="utf-8")))
    george = [r for r in rows if r.get("loc_label") == "University at George"]
    assert len(george) == 1
    assert george[0].get("loc_type") == "course"
    assert george[0].get("seg_id")
