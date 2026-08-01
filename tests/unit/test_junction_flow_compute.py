"""Unit tests for Junction Flow compute (Issue #818)."""

from __future__ import annotations

import pandas as pd

from app.core.junction_flow.compute import (
    MERGE_PARTNER_EVENTS,
    NODE_DWELL_SEC,
    StreamPresence,
    _unique_with_copresence,
    analyze_interaction,
    analyze_junctions_doc,
    prepare_runners_by_event,
)
import numpy as np


def test_constants():
    assert NODE_DWELL_SEC == 30.0
    assert MERGE_PARTNER_EVENTS == ("full", "half")


def test_prepare_runners_quintiles():
    df = pd.DataFrame(
        {
            "runner_id": [f"r{i}" for i in range(10)],
            "event": ["10k"] * 10,
            "pace": [4.0 + 0.2 * i for i in range(10)],
            "start_offset": [0] * 10,
            "distance": [10] * 10,
        }
    )
    by_event = prepare_runners_by_event(df)
    assert "10k" in by_event
    assert set(by_event["10k"]["quintile"].unique()) <= {1, 2, 3, 4, 5}


def test_copresence_requires_partner_within_dwell():
    primary = StreamPresence(
        role="joining",
        seg_id="S26",
        event="10k",
        runner_ids=np.array(["a", "b"]),
        node_times_sec=np.array([1000.0, 2000.0]),
        paces=np.array([5.0, 5.0]),
        quintiles=np.array([3, 3]),
    )
    partner = StreamPresence(
        role="through",
        seg_id="S9",
        event="full",
        runner_ids=np.array(["f1"]),
        node_times_sec=np.array([1010.0]),  # within 30s of a, not of b
        paces=np.array([5.0]),
        quintiles=np.array([1]),
    )
    stats = _unique_with_copresence(primary, partner, 0.0, 3000.0, dwell_sec=30.0)
    assert stats["with_partner"] == 1
    assert stats["without_partner"] == 1


def test_merge_empty_without_full_half_partners():
    runners = {
        "10k": pd.DataFrame(
            {
                "runner_id": ["r1"],
                "event": ["10k"],
                "pace": [5.0],
                "start_offset": [0.0],
                "quintile": [3],
            }
        )
    }
    nearby = {
        "S26": {
            "seg_id": "S26",
            "near_endpoint": "end",
            "event_kms": {"10k": {"from_km": 8.0, "to_km": 9.0}},
        },
        "S9": {
            "seg_id": "S9",
            "near_endpoint": "start",
            "event_kms": {"10k": {"from_km": 9.0, "to_km": 9.4}},
        },
    }
    ix = {
        "id": "m1",
        "type": "merge",
        "from_seg_id": "S26",
        "to_seg_ids": ["S9"],
        "events": ["10k"],
    }
    # Monkeypatch analyze path via analyze_interaction with empty full/half
    # build nearby without full/half event_kms — partner_parts empty
    result = analyze_interaction(ix, nearby, runners, {"10k": 480.0})
    assert result.type == "merge"
    assert "No full/half" in " ".join(result.notes) or result.unique_by_role_event == {}


def test_analyze_junctions_doc_empty():
    out = analyze_junctions_doc({"junctions": []}, {}, {})
    assert out["ok"] is True
    assert out["junctions"] == []
    assert out["method"]["node_dwell_sec"] == NODE_DWELL_SEC
