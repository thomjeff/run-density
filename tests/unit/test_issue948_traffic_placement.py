"""Issue #948: location type ``course`` merged into ``traffic`` with placement."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

from app.core.config_package.legs import (
    _normalize_locations,
    refresh_location_seg_ids_from_segments,
    validate_locations_for_export,
)
from app.core.execute.board import build_strip
from app.core.execute.layers import is_off_course_row, is_turnaround
from app.core.locations.loc_types import is_off_course, normalize_type_and_placement
from app.core.locations.schema import location_to_csv_row, normalize_location_record
from app.utils.constants import LOCATION_TYPE_CHOICES

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("raw_type", "raw_placement", "expected"),
    [
        ("course", None, ("traffic", "along")),
        ("course", "off", ("traffic", "along")),
        ("course", "start", ("traffic", "start")),
        ("", None, ("traffic", "along")),
        ("bogus", "along", ("traffic", "along")),
        ("traffic", "along", ("traffic", "along")),
        ("traffic", "off", ("traffic", "off")),
        ("traffic", False, ("traffic", "off")),
        ("traffic", None, ("traffic", "off")),
        ("aid", "along", ("aid", "off")),
        ("extract", None, ("extract", "off")),
        ("water", None, ("water", "along")),
        ("official", "end", ("official", "end")),
    ],
)
def test_normalize_type_and_placement(raw_type, raw_placement, expected):
    assert normalize_type_and_placement(raw_type, raw_placement) == expected


def test_course_is_not_a_location_type():
    assert "course" not in LOCATION_TYPE_CHOICES
    assert "traffic" in LOCATION_TYPE_CHOICES


def test_off_course_rules():
    assert is_off_course({"loc_type": "traffic", "placement": "off"})
    assert is_off_course({"loc_type": "extract"})
    assert not is_off_course({"loc_type": "traffic", "placement": "along"})
    assert not is_off_course({"loc_type": "course"})
    assert not is_off_course({"loc_type": "aid", "placement": "off"})


def _leg_loc(**extra):
    loc = {"loc_label": "Trail at Douglas", "lat": 45.95, "lon": -66.64}
    loc.update(extra)
    return loc


def test_leg_locations_fold_course_into_on_course_traffic():
    rows = _normalize_locations(
        [
            _leg_loc(loc_type="course", placement="along", proxy_loc_id="9"),
            _leg_loc(loc_type="traffic", placement="off", seg_id="S1"),
            _leg_loc(loc_type="traffic", placement="along", proxy_leg_loc_key="01:2"),
        ],
        assign_keys=False,
    )
    legacy, off, on = rows
    assert (legacy["loc_type"], legacy["placement"]) == ("traffic", "along")
    assert "proxy_loc_id" not in legacy
    assert off["placement"] == "off"
    assert off.get("seg_id", "") == ""
    assert on["placement"] == "along"
    assert "proxy_leg_loc_key" not in on


def test_seg_refresh_and_export_validation_follow_placement():
    segments = [{"seg_id": "S1", "leg_id": "12", "events": ["10k"]}]
    locations = [
        {
            "id": 1,
            "loc_label": "On",
            "loc_type": "traffic",
            "placement": "along",
            "leg_id": "12",
        },
        {
            "id": 2,
            "loc_label": "Off",
            "loc_type": "traffic",
            "placement": "off",
            "leg_id": "12",
            "seg_id": "S1",
            "proxy_loc_id": "1",
        },
    ]
    refresh_location_seg_ids_from_segments(locations, segments)
    assert locations[0]["seg_id"] == "S1"
    assert locations[1]["seg_id"] == ""
    course = {"segments": segments, "locations": locations}
    assert validate_locations_for_export(course) == []
    locations[1]["seg_id"] = "S1"
    errors = validate_locations_for_export(course)
    assert any("off-course traffic" in e for e in errors)


def test_package_records_and_csv_use_traffic():
    rec = normalize_location_record(
        {"loc_label": "Trail at Fulton", "loc_type": "course", "seg_id": "S1"}, []
    )
    assert (rec["loc_type"], rec["placement"]) == ("traffic", "along")
    assert location_to_csv_row({"loc_label": "X"}, [])["loc_type"] == "traffic"


def test_location_report_models_on_course_traffic():
    src = (REPO / "app" / "location_report.py").read_text(encoding="utf-8")
    assert "skip_arrival_modeling = loc_type ==" not in src
    assert "skip_arrival_modeling = no_seg and (" in src
    assert "if loc_type == LEGACY_COURSE_TYPE:" in src


def test_older_runs_show_course_as_traffic():
    from app.routes.api_locations import _normalize_location_api_row

    assert _normalize_location_api_row({"loc_type": "course"})["loc_type"] == "traffic"
    assert _normalize_location_api_row({"loc_type": "water"})["loc_type"] == "water"
    src = (REPO / "app" / "one_pager.py").read_text(encoding="utf-8")
    assert "if loc_type.strip().lower() == LEGACY_COURSE_TYPE:" in src


def _strip(row):
    return build_strip(
        row,
        loc_end_minutes=None,
        now_hhmmss="07:00:00",
        status="closed",
        reopened_entry=None,
        linked=[],
        available=[],
        run_id="r1",
    )


def test_execute_strips_mark_off_course_traffic():
    legacy = _strip(
        {"loc_id": 1, "loc_label": "Trail at Douglas", "loc_type": "course"}
    )
    on = _strip({"loc_id": 2, "loc_label": "Queen at King", "loc_type": "traffic"})
    off = _strip(
        {
            "loc_id": 3,
            "loc_label": "Union at Friel",
            "loc_type": "traffic",
            "proxy_loc_id": 1,
        }
    )
    assert legacy["loc_type"] == "traffic" and legacy["off_course"] is False
    assert on["off_course"] is False
    assert off["off_course"] is True
    assert is_off_course_row({"loc_type": "extract"})


def test_turnaround_label_rule_covers_on_course_traffic():
    assert is_turnaround({"loc_type": "traffic", "loc_label": "10K Turn"})
    assert not is_turnaround(
        {"loc_type": "traffic", "loc_label": "Turn onto Queen", "proxy_loc_id": 4}
    )


def test_execute_map_layers_and_ring():
    js = (REPO / "frontend" / "static" / "js" / "execute_board.js").read_text(
        encoding="utf-8"
    )
    html = (REPO / "frontend" / "templates" / "pages" / "execute.html").read_text(
        encoding="utf-8"
    )
    assert "pin.strip.off_course" in js
    assert "is-off-course" in html


def test_build_editor_offers_on_and_off_course():
    js = (REPO / "frontend" / "static" / "js" / "map" / "segment_recipes.js").read_text(
        encoding="utf-8"
    )
    assert "'On course'" in js and "'Off course'" in js
    assert "|| 'course'" not in js
    assert "offCourseUsesProxyTiming(loc.loc_type, loc.placement)" in js
    for name in ("course_mapping.js", "saved_courses.js", "locations.js"):
        text = (REPO / "frontend" / "static" / "js" / "map" / name).read_text(
            encoding="utf-8"
        )
        assert "course: '#" not in text and "'course': '#" not in text


def _write_root(root: Path) -> None:
    legs = root / "org" / "legs"
    legs.mkdir(parents=True)
    (legs / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "12",
                        "locations": [
                            _leg_loc(loc_type="course", placement="along"),
                            _leg_loc(loc_type="traffic", placement="off"),
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    pkg = root / "config" / "PKG1"
    pkg.mkdir(parents=True)
    (pkg / "course.json").write_text(
        json.dumps({"locations": [_leg_loc(loc_type="course", seg_id="S1")]}),
        encoding="utf-8",
    )
    with (pkg / "passes.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["pass_id", "loc_label", "loc_type", "seg_id"])
        writer.writerow([1, "Trail at Douglas", "course", "S1"])
        writer.writerow([2, "Union at Friel", "traffic", ""])


def _run_migration(root: Path, *args: str) -> dict:
    out = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "migrate_course_to_traffic.py"),
            "--root",
            str(root),
            *args,
        ],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def test_migration_dry_run_then_apply(tmp_path):
    _write_root(tmp_path)
    dry = _run_migration(tmp_path)
    assert dry["applied"] is False
    assert dry["locations"] == 3
    manifest = tmp_path / "org" / "legs" / "manifest.yaml"
    assert "course" in manifest.read_text(encoding="utf-8")

    done = _run_migration(tmp_path, "--apply")
    assert done["applied"] is True
    legs = yaml.safe_load(manifest.read_text(encoding="utf-8"))["legs"]
    first, second = legs[0]["locations"]
    assert (first["loc_type"], first["placement"]) == ("traffic", "along")
    assert (second["loc_type"], second["placement"]) == ("traffic", "off")
    course = json.loads((tmp_path / "config" / "PKG1" / "course.json").read_text())
    assert course["locations"][0]["loc_type"] == "traffic"
    rows = list(csv.DictReader((tmp_path / "config" / "PKG1" / "passes.csv").open()))
    assert [r["loc_type"] for r in rows] == ["traffic", "traffic"]
    with tarfile.open(done["backup"]) as tar:
        assert "org/legs/manifest.yaml" in tar.getnames()
    assert _run_migration(tmp_path)["locations"] == 0
