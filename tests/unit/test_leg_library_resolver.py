"""Tests for org-primary leg library resolution (Issue #780)."""

import pytest
import yaml

from app.core.config_package.leg_library_resolver import (
    LEG_SOURCE_ORG,
    LEG_SOURCE_PACKAGE,
    combined_manifest_for_apply,
    effective_leg_source,
    recipe_leg_ids_from_package,
    resolve_leg_library,
)
from app.core.config_package.legs import merge_leg_locations_into_course
from app.core.config_package.segment_recipes import (
    apply_package_recipes,
    get_package_segment_library_state,
    save_package_segment_manifest,
)
from app.core.config_package.storage import (
    create_config_package,
    export_config_package_segments,
    load_config_course,
)

_GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Org trail</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""


def _seed_org_leg(tmp_path, *, legs=None):
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    if legs is None:
        legs = [
            {
                "leg_id": "05",
                "label": "Org trail",
                "loc_label": "Water",
                "loc_type": "water",
                "resources": None,
            }
        ]
    manifest_legs = []
    for spec in legs:
        leg_id = spec["leg_id"]
        gpx_name = f"{leg_id}_org_trail.gpx"
        (org_dir / gpx_name).write_text(_GPX, encoding="utf-8")
        loc = {
            "loc_label": spec.get("loc_label", "Water"),
            "loc_type": spec.get("loc_type", "water"),
            "lat": 45.961,
            "lon": -66.642,
            "placement": "along",
            "zone": spec.get("zone", "A1"),
            "buffer": spec.get("buffer", 30),
            "notes": spec.get("notes", "Carry cups"),
        }
        resources = spec.get("resources")
        if resources is not None:
            loc["resources"] = resources
        manifest_legs.append(
            {
                "id": leg_id,
                "file": gpx_name,
                "seg_label": spec.get("label", "Org trail"),
                "start_label": "Start",
                "end_label": "End",
                "locations": [loc],
            }
        )
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump({"legs": manifest_legs}),
        encoding="utf-8",
    )


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )


def test_effective_leg_source_defaults_to_org():
    assert effective_leg_source({}) == LEG_SOURCE_ORG
    assert effective_leg_source({"recipes": {"full": []}}) == LEG_SOURCE_ORG


def test_effective_leg_source_legacy_package_with_legs():
    manifest = {"legs": [{"id": "01", "file": "01.gpx"}]}
    assert effective_leg_source(manifest) == LEG_SOURCE_PACKAGE


def test_effective_leg_source_explicit_org_overrides_empty_legs():
    manifest = {"leg_source": "org", "legs": []}
    assert effective_leg_source(manifest) == LEG_SOURCE_ORG


def test_resolve_leg_library_org_primary(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_leg(tmp_path)

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": ["05"]},
            "flow_overrides": [],
        },
    )

    lib_dir, leg_manifest, source, _pkg = resolve_leg_library(config_id)
    assert source == LEG_SOURCE_ORG
    assert lib_dir == tmp_path / "org" / "legs"
    assert leg_manifest["legs"][0]["id"] == "05"


def test_get_package_segment_library_state_lists_org_legs(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_leg(tmp_path)

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": ["05"]},
            "flow_overrides": [],
        },
    )

    state = get_package_segment_library_state(config_id)
    assert state["leg_source"] == LEG_SOURCE_ORG
    assert len(state["legs"]) == 1
    assert state["legs"][0]["id"] == "05"
    assert state["recipes"]["full"] == ["05"]


def test_apply_package_recipes_uses_org_legs(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_leg(tmp_path)

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": ["05"]},
            "flow_overrides": [],
        },
    )

    applied = apply_package_recipes(config_id, export_csv=False)
    assert applied["segment_count"] >= 1
    course = load_config_course(config_id)
    assert course.get("segment_library_applied") is True
    leg_ids = {s.get("leg_id") for s in course.get("segments") or []}
    assert "05" in leg_ids


def test_merge_org_leg_locations_carry_resources(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_leg(
        tmp_path,
        legs=[
            {
                "leg_id": "05",
                "label": "Org trail",
                "resources": {"water_volunteers": {"count": 4, "label": "Water crew"}},
            },
            {
                "leg_id": "06",
                "label": "Unused leg",
                "loc_label": "Aid",
                "loc_type": "aid",
            },
        ],
    )

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": ["05"]},
            "flow_overrides": [],
        },
    )

    apply_package_recipes(config_id, export_csv=False)
    course = load_config_course(config_id)
    water = next(
        loc for loc in (course.get("locations") or []) if loc.get("loc_type") == "water"
    )
    assert water.get("zone") == "A1"
    assert water.get("buffer") == 30
    assert water.get("notes") == "Carry cups"
    assert water["resources"]["water_volunteers"]["count"] == 4

    assert recipe_leg_ids_from_package(config_id) == {"05"}
    leg_sources = {
        loc.get("leg_id") for loc in course.get("locations") or [] if loc.get("source") == "leg"
    }
    assert leg_sources == {"05"}

    _lib_dir, combined = combined_manifest_for_apply(config_id)
    assert combined["recipes"]["full"] == ["05"]
    assert {leg["id"] for leg in combined["legs"]} == {"05", "06"}


def test_apply_preserves_half_recipe_km_order(tmp_path, monkeypatch):
    """Half-only legs must not inherit cumulative km from global segment row order."""
    _patch_roots(tmp_path, monkeypatch)
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    gpx = _GPX
    legs_spec = [
        ("12", "start.gpx", 2.71),
        ("06", "mid.gpx", 2.32),
        ("13", "connector.gpx", 0.03),
        ("09", "long.gpx", 5.77),
        ("14", "finish.gpx", 0.2),
    ]
    manifest_legs_list = []
    for leg_id, fname, _km in legs_spec:
        (org_dir / fname).write_text(gpx, encoding="utf-8")
        manifest_legs_list.append(
            {"id": leg_id, "file": fname, "seg_label": f"Leg {leg_id}"}
        )
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump({"legs": manifest_legs_list}),
        encoding="utf-8",
    )

    result = create_config_package("Pkg", "", event_day="sun", package_events=["half"])
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"half": ["12", "06", "13", "09", "14"]},
            "flow_overrides": [],
        },
    )

    apply_package_recipes(config_id, export_csv=True)
    course = load_config_course(config_id)
    assert course.get("segment_library_applied") is True
    by_leg = {s["leg_id"]: s for s in course["segments"]}
    # Leg 13 is 3rd in half recipe (after 12, 06), not after finish leg 14.
    assert by_leg["06"]["half_from_km"] < by_leg["13"]["half_from_km"]
    assert by_leg["13"]["half_to_km"] < by_leg["14"]["half_from_km"]
    assert by_leg["14"]["half_to_km"] == max(
        s["half_to_km"] for s in course["segments"] if s.get("half_to_km")
    )


def test_export_after_apply_org_primary_keeps_segments(tmp_path, monkeypatch):
    """Regression: export must not drop segments when legs live in org library."""
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_leg(tmp_path)

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": ["05"]},
            "flow_overrides": [],
        },
    )

    apply_package_recipes(config_id, export_csv=False)
    exported = export_config_package_segments(config_id)
    assert exported["segment_count"] >= 1
    course = load_config_course(config_id)
    assert len(course.get("segments") or []) >= 1
