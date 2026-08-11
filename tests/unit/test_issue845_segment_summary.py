"""Issue #845–#848: segment-first Flow summary without breaking pair atoms."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.flow.segment_summary import (
    PACE_MIXING_READY,
    PACE_MIXING_UNAVAILABLE,
    build_segment_flow_summary,
    build_segment_flow_summary_from_day_dir,
    classify_pair_kind,
    event_mix_breakdown,
    pair_temporal_state,
    unique_role_unions,
)
from app.flow_report import export_fz_runners_parquet
from app.main import app

REFERENCE_RUN = Path(
    "/Users/jthompson/Documents/runflow/analysis/5sqk4pNRRJzLBphCnQbAwi/sun"
)


def test_classify_pair_kind_same_pass_corridor_same_event():
    assert classify_pair_kind("S8_full_half", "full", "half", "S8") == "same_pass"
    assert classify_pair_kind("S8_S12_half_full", "half", "full", "S8") == "corridor"
    assert classify_pair_kind("S8_S21_10k_full", "10k", "full", "S8") == "corridor"
    assert classify_pair_kind("S8_full_full", "full", "full", "S8") == "same_event"


def test_pair_temporal_states_pre_active_inactive():
    assert pair_temporal_state("08:10", "08:13", "09:56") == "not_yet_active"
    assert pair_temporal_state("08:42", "08:13", "09:56") == "active"
    assert pair_temporal_state("10:01", "08:13", "09:56") == "inactive"


def test_unique_unions_do_not_sum_or_include_corridor():
    rows = [
        {"flow_id": "S8_full_half", "event": "full", "runner_id": "1", "role": "overtaking"},
        {"flow_id": "S8_full_10k", "event": "full", "runner_id": "1", "role": "overtaking"},
        {"flow_id": "S8_full_10k", "event": "full", "runner_id": "2", "role": "overtaking"},
        {"flow_id": "S8_S12_half_full", "event": "full", "runner_id": "9", "role": "overtaking"},
        {"flow_id": "S8_full_full", "event": "full", "runner_id": "8", "role": "overtaking"},
        {"flow_id": "S8_full_half", "event": "half", "runner_id": "3", "role": "overtaking"},
    ]
    counts = unique_role_unions(
        rows,
        role="overtaking",
        allowed_flow_ids=["S8_full_half", "S8_full_10k", "S8_half_10k"],
    )
    assert counts == {"full": 2, "half": 1}


def test_mix_breakdown_is_union_not_sum():
    pairs = [
        {"flow_id": "S8_full_half", "event_a": "full", "event_b": "half"},
        {"flow_id": "S8_full_10k", "event_a": "full", "event_b": "10k"},
        {"flow_id": "S8_half_10k", "event_a": "half", "event_b": "10k"},
    ]
    rows = [
        {"flow_id": "S8_full_half", "event": "half", "runner_id": "h1", "role": "overtaking"},
        {"flow_id": "S8_half_10k", "event": "half", "runner_id": "h1", "role": "overtaking"},
        {"flow_id": "S8_full_half", "event": "half", "runner_id": "h2", "role": "overtaking"},
        {"flow_id": "S8_half_10k", "event": "half", "runner_id": "h3", "role": "overtaking"},
        {"flow_id": "S8_full_10k", "event": "full", "runner_id": "f1", "role": "overtaking"},
        {"flow_id": "S8_S12_half_full", "event": "half", "runner_id": "corridor", "role": "overtaking"},
        {"flow_id": "S8_full_half", "event": "full", "runner_id": "f9", "role": "overtaken"},
        {"flow_id": "S8_half_10k", "event": "10k", "runner_id": "k1", "role": "overtaken"},
        {"flow_id": "S8_full_10k", "event": "10k", "runner_id": "k1", "role": "overtaken"},
        {"flow_id": "S8_full_10k", "event": "10k", "runner_id": "k2", "role": "overtaken"},
    ]
    overtaking = event_mix_breakdown(
        rows,
        role="overtaking",
        events=["full", "half", "10k"],
        same_pass_pairs=pairs,
    )
    assert overtaking["half"]["vs"] == {"full": 2, "10k": 2}
    assert overtaking["half"]["in_two_or_more"] == 1
    assert overtaking["half"]["unique"] == 3
    assert overtaking["full"]["vs"] == {"half": 0, "10k": 1}
    assert overtaking["full"]["unique"] == 1
    assert overtaking["10k"]["unique"] == 0
    overtaken = event_mix_breakdown(
        rows,
        role="overtaken",
        events=["full", "half", "10k"],
        same_pass_pairs=pairs,
    )
    assert overtaken["full"]["vs"] == {"half": 1, "10k": 0}
    assert overtaken["10k"]["vs"] == {"full": 2, "half": 1}
    assert overtaken["10k"]["in_two_or_more"] == 1
    assert overtaken["10k"]["unique"] == 2


def test_parent_summary_gates_kpis_without_pair_keys_and_excludes_corridor_events():
    flow_segments = {
        "S8_full_half": {
            "seg_id": "S8",
            "segment_label": "Walking Bridge South to George",
            "event_a": "full",
            "event_b": "half",
            "total_a": 467,
            "total_b": 999,
            "worst_zone": {"zone_index": 1, "overtaking_a": 0, "overtaking_b": 423},
            "zones": [{}, {}],
        },
        "S8_full_10k": {
            "seg_id": "S8",
            "segment_label": "Walking Bridge South to George",
            "event_a": "full",
            "event_b": "10k",
            "total_a": 467,
            "total_b": 700,
            "worst_zone": {"zone_index": 2, "overtaking_a": 196, "overtaking_b": 0},
            "zones": [{}, {}, {}],
        },
        "S8_half_10k": {
            "seg_id": "S8",
            "segment_label": "Walking Bridge South to George",
            "event_a": "half",
            "event_b": "10k",
            "total_a": 999,
            "total_b": 700,
            "worst_zone": {"zone_index": 1, "overtaking_a": 230, "overtaking_b": 0},
            "zones": [{}, {}],
        },
        "S8_10k_full": {
            "seg_id": "S8",
            "flow_id": "S8_S12_10k_full",
            "segment_label": "Walking Bridge South to George / reverse",
            "event_a": "10k",
            "event_b": "full",
            "total_a": 700,
            "total_b": 467,
            "worst_zone": {"zone_index": 0, "overtaking_a": 0, "overtaking_b": 177},
            "zones": [{}],
        },
        "S8_full_full": {
            "seg_id": "S8",
            "event_a": "full",
            "event_b": "full",
            "total_a": 467,
            "total_b": 467,
            "worst_zone": {"zone_index": 0, "overtaking_a": 1, "overtaking_b": 1},
            "zones": [{}],
        },
    }
    overlaps = {
        "segments": [
            {"flow_id": "S8_full_half", "seg_id": "S8", "event_a": "full", "event_b": "half", "overlap_start": "08:29", "overlap_end": "09:56"},
            {"flow_id": "S8_full_10k", "seg_id": "S8", "event_a": "full", "event_b": "10k", "overlap_start": "08:13", "overlap_end": "09:52"},
            {"flow_id": "S8_half_10k", "seg_id": "S8", "event_a": "half", "event_b": "10k", "overlap_start": "08:29", "overlap_end": "09:52"},
            {"flow_id": "S8_S12_10k_full", "seg_id": "S8", "event_a": "10k", "event_b": "full", "overlap_start": "08:21", "overlap_end": "09:52"},
        ]
    }

    ungated = build_segment_flow_summary(
        flow_segments=flow_segments,
        overlaps_summary=overlaps,
        runner_rows=None,
    )
    parent = ungated["segments"][0]
    assert parent["events"] == ["full", "half", "10k"]
    assert parent["t0"] == "08:13"
    assert parent["t1"] == "09:56"
    assert parent["pace_mixing_status"] == PACE_MIXING_UNAVAILABLE
    assert parent["field_denominator"] == "starters_in_analysis_run"
    assert parent["field_sizes"] == {"full": 467, "half": 999, "10k": 700}
    assert len(parent["pairs"]["same_pass"]) == 3
    assert len(parent["pairs"]["corridor"]) == 1
    assert len(parent["pairs"]["same_event"]) == 1
    assert parent["highest_severity_pair"]["flow_id"] == "S8_full_half"
    assert ungated["narrative"] is None

    runner_rows = [
        {"flow_id": "S8_full_10k", "event": "full", "runner_id": "a", "role": "overtaking"},
        {"flow_id": "S8_full_half", "event": "half", "runner_id": "b", "role": "overtaking"},
        {"flow_id": "S8_S12_10k_full", "event": "full", "runner_id": "corridor", "role": "overtaking"},
        {"flow_id": "S8_full_full", "event": "full", "runner_id": "same", "role": "overtaking"},
        {"flow_id": "S8_full_10k", "event": "10k", "runner_id": "c", "role": "overtaken"},
    ]
    ready = build_segment_flow_summary(
        flow_segments=flow_segments,
        overlaps_summary=overlaps,
        runner_rows=runner_rows,
    )["segments"][0]
    assert ready["pace_mixing_status"] == PACE_MIXING_READY
    assert ready["unique_overtakers"] == {"full": 1, "half": 1, "10k": 0}
    assert ready["unique_overtaken"] == {"full": 0, "half": 0, "10k": 1}
    assert ready["share_of_starters_overtaking"]["full"] == 0.2
    assert ready["mix_breakdown"]["overtaking"]["full"]["vs"]["10k"] == 1
    assert ready["mix_breakdown"]["overtaking"]["half"]["vs"]["full"] == 1
    assert ready["mix_breakdown"]["overtaking"]["half"]["unique"] == 1
    assert ready["mix_breakdown"]["overtaken"]["10k"]["vs"]["full"] == 1
    assert "corridor" not in json.dumps(ready["mix_breakdown"])


def test_fz_runners_export_adds_pair_keys_without_dropping_legacy_columns(tmp_path):
    segments = [
        {
            "seg_id": "S8",
            "event_a": "full",
            "event_b": "half",
            "flow_id": "S8_full_half",
            "zones": [
                {
                    "zone_index": 0,
                    "metrics": {
                        "_a_bibs_overtakes": {"r1"},
                        "_a_bibs_overtaken": set(),
                        "_a_bibs_copresence": set(),
                        "_b_bibs_overtakes": set(),
                        "_b_bibs_overtaken": {"r2"},
                        "_b_bibs_copresence": set(),
                    },
                }
            ],
        }
    ]
    path = export_fz_runners_parquet(segments, str(tmp_path), run_id="test", day="sun")
    frame = pd.read_parquet(path)
    for col in ("seg_id", "zone_index", "runner_id", "event", "role", "side"):
        assert col in frame.columns
    assert {"flow_id", "event_a", "event_b"}.issubset(frame.columns)
    assert set(frame["flow_id"]) == {"S8_full_half"}


def test_existing_flow_segments_api_shape_unchanged():
    client = TestClient(app)
    routes = {route.path for route in app.routes}
    assert "/api/flow/segments" in routes
    assert "/api/flow/segment-parents" in routes
    response = client.get("/api/flow/segments")
    assert response.status_code in {200, 400, 404, 500}
    if response.status_code == 200:
        payload = response.json()
        assert "flow" in payload
        assert "summary" not in payload


def test_flow_html_defaults_to_segment_parent():
    source = Path("frontend/templates/pages/flow.html").read_text(encoding="utf-8")
    assert 'id="flow-parent-preview"' in source
    assert 'id="flow-parent-detail"' in source
    assert 'id="flow-legacy-wrap"' in source
    assert "flow-parent-tile" in source
    assert "flow-parent-mix-table" in source
    assert "renderMixMatrix" in source
    assert "flow-parent-chart-mix" not in source
    assert "Pair evidence" not in source
    assert source.count("usePointStyle: true") >= 2
    assert source.count("pointStyle: 'circle'") >= 2
    assert source.count("mode: 'index', intersect: false") >= 2
    assert "get('flow_parent')" in source
    assert "flag !== '0'" in source
    assert "flowParentPreviewEnabled" in source
    assert "selectParentSegment" in source
    assert "refreshFlowViews" in source
    assert "loadFlowData();" in source
    assert "loadOverlapData();" in source


@pytest.mark.skipif(not REFERENCE_RUN.is_dir(), reason="reference run artifacts not on this machine")
def test_s8_reference_run_builds_parent_without_shipping_naive_unions():
    summary = build_segment_flow_summary_from_day_dir(REFERENCE_RUN, "sun")
    s8 = next(seg for seg in summary["segments"] if seg["seg_id"] == "S8")
    assert s8["events"] == ["full", "half", "10k"]
    assert s8["t0"] == "08:13"
    assert s8["t1"] == "09:56"
    assert s8["pace_mixing_status"] == PACE_MIXING_UNAVAILABLE
    assert {p["flow_id"] for p in s8["pairs"]["same_pass"]} == {
        "S8_full_half",
        "S8_full_10k",
        "S8_half_10k",
    }
    assert {p["flow_id"] for p in s8["pairs"]["corridor"]} >= {
        "S8_S12_half_full",
        "S8_S12_10k_full",
        "S8_S21_half_full",
        "S8_S21_10k_full",
    }
    assert s8["occupancy"]
    assert s8["occupancy"][0]["minute"] <= "08:13"
    dumped = json.dumps(summary)
    assert "313" not in dumped


NEW_RUN = Path("/Users/jthompson/Documents/runflow/analysis/4WPc8TogaBYqRNVK7gswd7/sun")


@pytest.mark.skipif(not NEW_RUN.is_dir(), reason="new analysis run not on this machine")
def test_new_run_live_summary_has_windows_and_filtered_uniques():
    summary = build_segment_flow_summary_from_day_dir(NEW_RUN, "sun")
    s8 = next(seg for seg in summary["segments"] if seg["seg_id"] == "S8")
    assert s8["t0"] == "08:13"
    assert s8["t1"] == "09:56"
    assert s8["pace_mixing_status"] == PACE_MIXING_READY
    assert s8["unique_overtakers"]["full"] == 196
    assert s8["unique_overtakers"]["half"] == 520
    assert s8["unique_overtakers"]["10k"] == 0
    assert s8["mix_breakdown"]["overtaking"]["half"] == {
        "vs": {"full": 426, "10k": 230},
        "in_two_or_more": 136,
        "unique": 520,
    }
    assert s8["mix_breakdown"]["overtaking"]["full"]["vs"] == {"half": 0, "10k": 196}
    assert s8["mix_breakdown"]["overtaken"]["full"]["unique"] == 267
    assert s8["mix_breakdown"]["overtaken"]["10k"] == {
        "vs": {"full": 247, "half": 213},
        "in_two_or_more": 99,
        "unique": 361,
    }
    assert s8["occupancy"]
    assert {p["flow_id"] for p in s8["pairs"]["same_pass"]} == {
        "S8_full_half",
        "S8_full_10k",
        "S8_half_10k",
    }
