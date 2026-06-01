"""Tests for segment library + event recipes export (2027 planning)."""

from pathlib import Path

import pytest

from app.core.course.segment_library import (
    build_course_segments_from_library,
    build_flow_csv_from_segments,
    export_library_to_course,
    load_chunk_library,
    load_manifest,
    parse_chunk_gpx,
    validate_recipe_stitch,
)

LIBRARY_DIR = Path(__file__).resolve().parents[2] / "cursor" / "plotaroute"
MANIFEST = LIBRARY_DIR / "manifest.yaml"


@pytest.fixture(scope="module")
def manifest():
    if not MANIFEST.is_file():
        pytest.skip("cursor/plotaroute/manifest.yaml not present")
    return load_manifest(MANIFEST)


@pytest.fixture(scope="module")
def chunks(manifest):
    return load_chunk_library(LIBRARY_DIR, manifest)


def test_plotaroute_chunks_load(manifest, chunks):
    assert len(chunks) >= 10
    assert chunks["01"]["length_km"] == pytest.approx(2.71, abs=0.05)
    assert chunks["02"]["length_km"] == pytest.approx(1.59, abs=0.05)


def test_10k_recipe_stitch(manifest, chunks):
    warnings = validate_recipe_stitch(
        LIBRARY_DIR, manifest["recipes"]["10k"], chunks, tolerance_m=120.0
    )
    assert not any("01" in w and "02" in w for w in warnings)


def test_multi_event_segment_rows(manifest, chunks):
    segments = build_course_segments_from_library(
        manifest, chunks, event_ids=["full", "half", "10k"]
    )
    assert len(segments) == len(manifest["chunks"])
    s1 = next(s for s in segments if s["seg_id"] == "S1")
    assert set(s1["events"]) == {"full", "half", "10k"}
    assert s1["10k_from_km"] == 0.0
    assert s1["10k_to_km"] == pytest.approx(2.71, abs=0.05)
    s2 = next(s for s in segments if s["seg_id"] == "S2")
    assert "half" not in s2["events"]
    assert s2["full_from_km"] == pytest.approx(2.71, abs=0.05)
    assert s2["10k_from_km"] == pytest.approx(2.71, abs=0.05)
    assert [s["seg_id"] for s in segments] == [f"S{i}" for i in range(1, len(segments) + 1)]


def test_10k_recipe_length(manifest, chunks):
    bundle = export_library_to_course(LIBRARY_DIR, MANIFEST, event_ids=["10k"])
    assert bundle["recipe_lengths_km"]["10k"] == pytest.approx(10.02, abs=0.2)


def test_flow_pairs_on_shared_segment(manifest, chunks):
    segments = build_course_segments_from_library(
        manifest, chunks, event_ids=["full", "half", "10k"]
    )
    csv_text = build_flow_csv_from_segments(segments, ["full", "half", "10k"])
    lines = [ln for ln in csv_text.strip().splitlines() if ln]
    assert lines[0].startswith("seg_id,")
    assert any(",10k,half," in ln or ",half,10k," in ln for ln in lines)
    assert any(ln.startswith("S1,") for ln in lines[1:])


def test_export_bundle_writes_csv():
    if not MANIFEST.is_file():
        pytest.skip("plotaroute library missing")
    bundle = export_library_to_course(LIBRARY_DIR, MANIFEST)
    assert "full,half,10k" in bundle["segments_csv"].splitlines()[0]
    assert "event_a" in bundle["flow_csv"]
