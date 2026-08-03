"""
Run analysis progress for Overview (#825).

Maps engineer pipeline phases to race-director user stages and persists
runflow/analysis/{run_id}/progress.json for lightweight polling.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.run_id import get_run_directory

logger = logging.getLogger(__name__)

PROGRESS_FILENAME = "progress.json"

# Ordered user-facing stages (product copy).
USER_STAGES: List[Dict[str, str]] = [
    {"id": "inputs", "label": "Checking inputs"},
    {"id": "density", "label": "Calculating density"},
    {"id": "flow", "label": "Analyzing flow"},
    {"id": "junctions", "label": "Analyzing junctions"},
    {"id": "artifacts", "label": "Building maps and reports"},
    {"id": "finish", "label": "Finishing up"},
]

# Pipeline phase_name → user stage id.
PHASE_TO_USER_STAGE: Dict[str, str] = {
    "phase_1_pre_analysis": "inputs",
    "phase_2_data_loading": "inputs",
    "phase_3_1_density_setup": "density",
    "phase_3_2_density_compute": "density",
    "phase_4_1_flow_build_segments": "flow",
    "phase_4_2_flow_compute": "flow",
    "phase_4_3_junction_flow": "junctions",
    "phase_5_1_bin_generation": "artifacts",
    "phase_5_2_bin_validation": "artifacts",
    "phase_6_1_persist_density": "artifacts",
    "phase_6_2_persist_flow": "artifacts",
    "phase_6_3_persist_locations": "artifacts",
    "phase_6_4_persist_junction_flow": "junctions",
    "phase_7_ui_artifacts": "artifacts",
    "phase_8_derived_metrics": "artifacts",
    "phase_9_map_data": "artifacts",
    "phase_10_reports": "artifacts",
    "phase_11_metadata": "finish",
}

STAGE_PHASES: Dict[str, List[str]] = {}
for _phase, _stage in PHASE_TO_USER_STAGE.items():
    STAGE_PHASES.setdefault(_stage, []).append(_phase)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def progress_path(run_id: str) -> Path:
    return get_run_directory(run_id) / PROGRESS_FILENAME


def _empty_stage_states() -> List[Dict[str, Any]]:
    return [
        {"id": s["id"], "label": s["label"], "state": "pending"}
        for s in USER_STAGES
    ]


def build_progress_payload(
    *,
    run_id: str,
    status: str,
    completed_phases: Optional[List[str]] = None,
    current_phase: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
    junctions_note: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a progress.json document from completed pipeline phase names."""
    completed = list(completed_phases or [])
    completed_set = set(completed)

    stages = _empty_stage_states()
    stage_by_id = {s["id"]: s for s in stages}

    # Mark stages fully done when all of their phases are complete
    # (or when a later stage has already started/completed — resilient to
    # phases that log without going through PerformanceMonitor).
    stage_order = [s["id"] for s in USER_STAGES]
    highest_touched = -1
    for phase in completed:
        sid = PHASE_TO_USER_STAGE.get(phase)
        if sid in stage_order:
            highest_touched = max(highest_touched, stage_order.index(sid))
    if current_phase and current_phase in PHASE_TO_USER_STAGE:
        highest_touched = max(
            highest_touched, stage_order.index(PHASE_TO_USER_STAGE[current_phase])
        )

    for idx, sid in enumerate(stage_order):
        phases = STAGE_PHASES.get(sid, [])
        if phases and all(p in completed_set for p in phases):
            stage_by_id[sid]["state"] = "done"
        elif idx < highest_touched:
            # Earlier stage implied complete if we've moved past it
            stage_by_id[sid]["state"] = "done"

    current_stage_id = None
    if status == "running":
        if current_phase and current_phase in PHASE_TO_USER_STAGE:
            current_stage_id = PHASE_TO_USER_STAGE[current_phase]
        else:
            for sid in stage_order:
                if stage_by_id[sid]["state"] != "done":
                    current_stage_id = sid
                    break
        if current_stage_id:
            stage_by_id[current_stage_id]["state"] = "current"
    elif status == "PASS":
        for s in stages:
            s["state"] = "done"
        current_stage_id = "finish"
    elif status == "FAIL":
        # Leave completed stages; mark current as failed via message
        if current_phase and current_phase in PHASE_TO_USER_STAGE:
            current_stage_id = PHASE_TO_USER_STAGE[current_phase]
            stage_by_id[current_stage_id]["state"] = "current"

    if junctions_note and stage_by_id.get("junctions", {}).get("state") == "done":
        stage_by_id["junctions"]["note"] = junctions_note

    done_count = sum(1 for s in stages if s["state"] == "done")
    total = len(stages)
    step_index = min(done_count + (1 if status == "running" else 0), total)
    if status == "PASS":
        step_index = total

    user_stage_label = None
    if current_stage_id:
        user_stage_label = stage_by_id[current_stage_id]["label"]

    if message is None:
        if status == "running" and user_stage_label:
            message = f"Step {step_index} of {total} — {user_stage_label}"
        elif status == "PASS":
            message = "Analysis complete"
        elif status == "FAIL":
            message = "Analysis could not finish"
        else:
            message = "Preparing your results"

    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at or _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "current_phase": current_phase,
        "completed_phases": completed,
        "user_stage": current_stage_id,
        "user_stage_label": user_stage_label,
        "user_stages": stages,
        "step_index": step_index,
        "step_total": total,
        "percent": int(round(100.0 * done_count / total)) if total else 0,
        "message": message,
        "error": error,
    }


def write_progress(run_id: str, payload: Dict[str, Any]) -> Path:
    path = progress_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)
    return path


def read_progress(run_id: str) -> Optional[Dict[str, Any]]:
    path = progress_path(run_id)
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to read progress for %s: %s", run_id, e)
        return None


def init_run_progress(run_id: str) -> Dict[str, Any]:
    """Create initial running progress.json when analysis is accepted."""
    payload = build_progress_payload(
        run_id=run_id,
        status="running",
        completed_phases=[],
        current_phase="phase_1_pre_analysis",
        message="Step 1 of 6 — Checking inputs",
    )
    write_progress(run_id, payload)
    return payload


def _merge_from_disk(run_id: str) -> Dict[str, Any]:
    existing = read_progress(run_id) or {}
    return {
        "completed_phases": list(existing.get("completed_phases") or []),
        "started_at": existing.get("started_at"),
        "junctions_note": None,
    }


def mark_phase_started(run_id: Optional[str], phase_name: str) -> None:
    if not run_id or phase_name not in PHASE_TO_USER_STAGE:
        return
    try:
        base = _merge_from_disk(run_id)
        payload = build_progress_payload(
            run_id=run_id,
            status="running",
            completed_phases=base["completed_phases"],
            current_phase=phase_name,
            started_at=base["started_at"],
        )
        write_progress(run_id, payload)
    except Exception as e:
        logger.warning("progress mark_phase_started failed for %s: %s", run_id, e)


def mark_phase_complete(run_id: Optional[str], phase_name: str) -> None:
    if not run_id or phase_name not in PHASE_TO_USER_STAGE:
        return
    try:
        base = _merge_from_disk(run_id)
        completed = base["completed_phases"]
        if phase_name not in completed:
            completed.append(phase_name)
        payload = build_progress_payload(
            run_id=run_id,
            status="running",
            completed_phases=completed,
            current_phase=phase_name,
            started_at=base["started_at"],
        )
        write_progress(run_id, payload)
    except Exception as e:
        logger.warning("progress mark_phase_complete failed for %s: %s", run_id, e)


def mark_run_complete(run_id: Optional[str]) -> None:
    if not run_id:
        return
    try:
        base = _merge_from_disk(run_id)
        # Ensure all known phases appear complete for UI
        all_phases = list(PHASE_TO_USER_STAGE.keys())
        completed = list(dict.fromkeys(base["completed_phases"] + all_phases))
        payload = build_progress_payload(
            run_id=run_id,
            status="PASS",
            completed_phases=completed,
            current_phase="phase_11_metadata",
            started_at=base["started_at"],
            message="Analysis complete",
        )
        write_progress(run_id, payload)
    except Exception as e:
        logger.warning("progress mark_run_complete failed for %s: %s", run_id, e)


def mark_run_failed(run_id: Optional[str], error: str) -> None:
    if not run_id:
        return
    try:
        base = _merge_from_disk(run_id)
        payload = build_progress_payload(
            run_id=run_id,
            status="FAIL",
            completed_phases=base["completed_phases"],
            current_phase=None,
            started_at=base["started_at"],
            message="Analysis could not finish",
            error=(error or "Unknown error")[:500],
        )
        write_progress(run_id, payload)
    except Exception as e:
        logger.warning("progress mark_run_failed failed for %s: %s", run_id, e)


def resolve_progress_for_api(run_id: str) -> Dict[str, Any]:
    """
    Return progress for GET /api/runs/{run_id}/progress.

    Fallbacks when progress.json is missing:
    - metadata.json status PASS → synthetic complete
    - analysis.json present, no metadata → running at stage 1
    - else 404-shaped None (caller raises)
    """
    existing = read_progress(run_id)
    if existing:
        return existing

    run_path = get_run_directory(run_id)
    if not run_path.is_dir():
        raise FileNotFoundError(f"Run {run_id} not found")

    meta_path = run_path / "metadata.json"
    if meta_path.is_file():
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            status = str(meta.get("status") or "PASS").upper()
            if status in ("PASS", "PARTIAL"):
                return build_progress_payload(
                    run_id=run_id,
                    status="PASS",
                    completed_phases=list(PHASE_TO_USER_STAGE.keys()),
                    message="Analysis complete",
                    started_at=meta.get("created_at"),
                )
            if status == "FAIL":
                return build_progress_payload(
                    run_id=run_id,
                    status="FAIL",
                    completed_phases=[],
                    error="Analysis failed",
                    started_at=meta.get("created_at"),
                )
        except (OSError, json.JSONDecodeError):
            pass

    if (run_path / "analysis.json").is_file():
        return build_progress_payload(
            run_id=run_id,
            status="running",
            completed_phases=[],
            current_phase="phase_1_pre_analysis",
            message="Step 1 of 6 — Checking inputs",
        )

    raise FileNotFoundError(f"Run {run_id} not found")
