"""Unit tests for Overview run progress (#825)."""

from __future__ import annotations

from app.core.v2.run_progress import (
    PHASE_TO_USER_STAGE,
    USER_STAGES,
    build_progress_payload,
    init_run_progress,
    mark_phase_complete,
    mark_phase_started,
    mark_run_complete,
    mark_run_failed,
    read_progress,
    resolve_progress_for_api,
)


def test_user_stages_order():
    assert [s["id"] for s in USER_STAGES] == [
        "inputs",
        "density",
        "flow",
        "junctions",
        "artifacts",
        "finish",
    ]


def test_phase_mapping_covers_catalog():
    assert PHASE_TO_USER_STAGE["phase_3_2_density_compute"] == "density"
    assert PHASE_TO_USER_STAGE["phase_4_3_junction_flow"] == "junctions"
    assert PHASE_TO_USER_STAGE["phase_6_4_persist_junction_flow"] == "junctions"
    assert PHASE_TO_USER_STAGE["phase_11_metadata"] == "finish"


def test_build_progress_advances_stages():
    payload = build_progress_payload(
        run_id="abc",
        status="running",
        completed_phases=["phase_1_pre_analysis", "phase_2_data_loading"],
        current_phase="phase_3_1_density_setup",
    )
    by_id = {s["id"]: s["state"] for s in payload["user_stages"]}
    assert by_id["inputs"] == "done"
    assert by_id["density"] == "current"
    assert payload["user_stage"] == "density"
    assert "Calculating density" in payload["message"]


def test_progress_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.v2.run_progress.get_run_directory",
        lambda run_id: tmp_path / run_id,
    )
    run_id = "testrun825"
    (tmp_path / run_id).mkdir()
    init_run_progress(run_id)
    data = read_progress(run_id)
    assert data is not None
    assert data["status"] == "running"
    assert data["user_stage"] == "inputs"

    mark_phase_started(run_id, "phase_3_2_density_compute")
    mark_phase_complete(run_id, "phase_1_pre_analysis")
    mark_phase_complete(run_id, "phase_2_data_loading")
    mark_phase_complete(run_id, "phase_3_2_density_compute")
    data = read_progress(run_id)
    assert "phase_3_2_density_compute" in data["completed_phases"]

    mark_run_complete(run_id)
    data = read_progress(run_id)
    assert data["status"] == "PASS"
    assert all(s["state"] == "done" for s in data["user_stages"])


def test_mark_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.v2.run_progress.get_run_directory",
        lambda run_id: tmp_path / run_id,
    )
    run_id = "fail825"
    (tmp_path / run_id).mkdir()
    init_run_progress(run_id)
    mark_run_failed(run_id, "boom")
    data = read_progress(run_id)
    assert data["status"] == "FAIL"
    assert data["error"] == "boom"


def test_resolve_fallback_from_metadata(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(
        "app.core.v2.run_progress.get_run_directory",
        lambda run_id: tmp_path / run_id,
    )
    run_id = "old825"
    d = tmp_path / run_id
    d.mkdir()
    (d / "metadata.json").write_text(json.dumps({"status": "PASS", "created_at": "t"}))
    payload = resolve_progress_for_api(run_id)
    assert payload["status"] == "PASS"
