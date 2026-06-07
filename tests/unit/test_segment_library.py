"""Tests for segment library + event recipes export (2027 planning)."""

from pathlib import Path

import pytest

from app.core.course.segment_library import (
    build_course_segments_from_library,
    build_flow_csv_from_segments,
    export_library_to_course,
    load_leg_library,
    load_manifest,
    manifest_legs,
    parse_leg_gpx,
    validate_recipe_stitch,
)

LIBRARY_DIR = Path(__file__).resolve().parents[2] / "cursor" / "reference-legs"
MANIFEST = LIBRARY_DIR / "manifest.yaml"


@pytest.fixture(scope="module")
def manifest():
    if not MANIFEST.is_file():
        pytest.skip("cursor/reference-legs/manifest.yaml not present")
    return load_manifest(MANIFEST)


@pytest.fixture(scope="module")
def legs_by_id(manifest):
    return load_leg_library(LIBRARY_DIR, manifest)


def test_reference_legs_load(manifest, legs_by_id):
    assert len(legs_by_id) >= 10
    assert legs_by_id["01"]["length_km"] == pytest.approx(2.71, abs=0.05)
    assert legs_by_id["02"]["length_km"] == pytest.approx(1.59, abs=0.05)


def test_10k_recipe_stitch(manifest, legs_by_id):
    warnings = validate_recipe_stitch(
        LIBRARY_DIR, manifest["recipes"]["10k"], legs_by_id, tolerance_m=120.0
    )
    assert not any("01" in w and "02" in w for w in warnings)


def test_multi_event_segment_rows(manifest, legs_by_id):
    segments = build_course_segments_from_library(
        manifest, legs_by_id, event_ids=["full", "half", "10k"]
    )
    recipe_ids = set()
    for seq in (manifest.get("recipes") or {}).values():
        recipe_ids.update(seq)
    assert len(segments) == len(recipe_ids)
    assert "09" not in {s["leg_id"] for s in segments}
    assert "10" not in {s["leg_id"] for s in segments}
    assert segments[0]["leg_id"] == "01"
    s1 = next(s for s in segments if s["seg_id"] == "S1")
    assert set(s1["events"]) == {"full", "half", "10k"}
    assert s1["10k_from_km"] == 0.0
    assert s1["10k_to_km"] == pytest.approx(2.71, abs=0.05)
    s2 = next(s for s in segments if s["seg_id"] == "S2")
    assert "half" not in s2["events"]
    assert s2["full_from_km"] == pytest.approx(2.71, abs=0.05)
    assert s2["10k_from_km"] == pytest.approx(2.71, abs=0.05)
    assert [s["seg_id"] for s in segments] == [f"S{i}" for i in range(1, len(segments) + 1)]


def test_10k_recipe_length(manifest, legs_by_id):
    bundle = export_library_to_course(LIBRARY_DIR, MANIFEST, event_ids=["10k"])
    assert bundle["recipe_lengths_km"]["10k"] == pytest.approx(10.02, abs=0.2)


def test_build_course_segments_skips_unassigned_legs(manifest, legs_by_id):
    segments = build_course_segments_from_library(
        manifest, legs_by_id, event_ids=["full", "half", "10k"]
    )
    leg_ids = {s["leg_id"] for s in segments}
    assert "09" not in leg_ids
    assert "10" not in leg_ids
    for seg in segments:
        assert seg.get("events")


def test_flow_pairs_on_shared_segment(manifest, legs_by_id):
    segments = build_course_segments_from_library(
        manifest, legs_by_id, event_ids=["full", "half", "10k"]
    )
    csv_text = build_flow_csv_from_segments(segments, ["full", "half", "10k"])
    lines = [ln for ln in csv_text.strip().splitlines() if ln]
    assert lines[0].startswith("flow_id,seg_id,")
    assert any(",10k,half," in ln or ",half,10k," in ln for ln in lines)
    assert any(",S1," in ln for ln in lines[1:])


def test_export_bundle_writes_csv():
    if not MANIFEST.is_file():
        pytest.skip("reference leg library missing")
    bundle = export_library_to_course(LIBRARY_DIR, MANIFEST)
    assert "full,half,10k" in bundle["segments_csv"].splitlines()[0]
    assert "event_a" in bundle["flow_csv"]


def test_build_course_segments_follows_recipe_order_not_manifest_order(manifest, legs_by_id):
    """Leg ids after 15 in manifest must not push recipe-middle legs to the end."""
    recipes = {
        "full": ["01", "02", "03", "16", "04"],
        "half": [],
        "10k": [],
    }
    manifest = dict(manifest)
    manifest["recipes"] = recipes
    legs = dict(legs_by_id)
    legs["03"] = {**legs["03"], "length_km": 5.57}
    legs["16"] = {
        **legs["03"],
        "id": "16",
        "length_km": 5.57,
        "file": "16_stub.gpx",
    }
    segments = build_course_segments_from_library(
        manifest, legs, event_ids=["full", "half", "10k"]
    )
    full_leg_order = [s["leg_id"] for s in segments if "full" in s.get("events", [])]
    assert full_leg_order == ["01", "02", "03", "16", "04"]
    leg16 = next(s for s in segments if s["leg_id"] == "16")
    assert leg16["seg_id"] == "S4"
    assert leg16["full_from_km"] == pytest.approx(9.87, abs=0.05)
    assert leg16["full_to_km"] == pytest.approx(15.44, abs=0.05)
    leg04 = next(s for s in segments if s["leg_id"] == "04")
    assert leg04["full_from_km"] == pytest.approx(15.44, abs=0.05)
