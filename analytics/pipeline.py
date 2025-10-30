"""Unified analytics pipeline orchestration.

This module provides a single entry point for running the density analysis
pipeline end-to-end.  The :func:`run_density_pipeline` function stitches
together the existing analytics components to produce the full suite of
reports, UI artifacts, heatmaps, and optional cloud uploads.

The goal is to centralize the workflow without modifying the individual
modules.  Each step prints user-friendly progress logs so operators can
follow the pipeline execution in local and Cloud Run environments.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.constants import DEFAULT_START_TIMES
from app.density_report import generate_density_report
from app.flow_report import generate_temporal_flow_report
from app.storage_service import (
    StorageConfig,
    StorageService,
    get_storage_service,
    initialize_storage_service,
)

from analytics.export_frontend_artifacts import (
    calculate_flow_segment_counts,
    export_ui_artifacts,
)
from analytics.export_heatmaps import export_heatmaps_and_captions


def _prepare_storage(use_cloud: bool) -> StorageService:
    """Initialize and return a configured :class:`StorageService`."""

    config = StorageConfig(use_cloud_storage=use_cloud)
    storage = initialize_storage_service(config)

    environment = "cloud" if storage.config.use_cloud_storage else "local"
    print(f"🔐 Storage configured for {environment} mode")

    # Ensure the local reports directory exists for downstream consumers
    Path(storage.config.local_reports_dir).mkdir(parents=True, exist_ok=True)

    return storage


def _extract_run_id_from_path(path: Path, default: str) -> str:
    """Return the run identifier inferred from a report path."""

    name = path.stem
    for suffix in ("-Density", "-Flow"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return default


def _copy_reports_to_run_folder(source: Path, destination: Path) -> None:
    """Copy generated report assets into a run-specific directory."""

    if source.resolve() == destination.resolve():
        return

    print(f"🗂️  Preparing run directory at {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _locate_latest_report(candidates: List[Path]) -> Optional[Path]:
    """Return the newest report path from a list of candidates."""

    existing = [p for p in candidates if p and p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def run_density_pipeline(run_id: str, use_cloud: bool = False) -> Dict[str, Any]:
    """Execute the full density analytics pipeline.

    Args:
        run_id: Identifier for the analytics run (e.g., ``2025-10-30-1025``).
        use_cloud: When ``True`` the pipeline saves outputs via GCS.

    Returns:
        Dictionary summarizing the pipeline execution for downstream tooling.
    """

    print("🚀 Starting density analytics pipeline…")
    print(f"🆔 Run ID: {run_id}")
    print(f"☁️  Cloud uploads enabled: {use_cloud}")

    storage = _prepare_storage(use_cloud)
    environment = "cloud" if storage.config.use_cloud_storage else "local"
    reports_base = Path(storage.config.local_reports_dir)

    summary: Dict[str, Any] = {
        "run_id": run_id,
        "environment": environment,
        "density": {},
        "flow": {},
    }

    density_result: Dict[str, Any] = {}
    flow_result: Dict[str, Any] = {}

    print("📈 Running density analysis…")
    try:
        density_result = generate_density_report(
            pace_csv="data/runners.csv",
            density_csv="data/segments.csv",
            start_times=DEFAULT_START_TIMES,
            output_dir=str(reports_base),
        )
        summary["density"] = {
            "ok": density_result.get("ok", False),
            "report_path": density_result.get("report_path"),
        }
        print("✅ Density analysis complete")
    except Exception as exc:  # pragma: no cover - defensive logging path
        print(f"⚠️ Density analysis failed: {exc}")
        summary["density"] = {"ok": False, "error": str(exc)}

    print("🌊 Running temporal flow analysis…")
    try:
        flow_result = generate_temporal_flow_report(
            pace_csv="data/runners.csv",
            segments_csv="data/segments.csv",
            start_times=DEFAULT_START_TIMES,
            output_dir=str(reports_base),
            density_results=density_result.get("analysis_results"),
            environment=environment,
        )
        summary["flow"] = {
            "ok": flow_result.get("ok", False),
            "report_path": flow_result.get("report_path"),
        }
        print("✅ Temporal flow analysis complete")
    except Exception as exc:  # pragma: no cover - defensive logging path
        print(f"⚠️ Temporal flow analysis failed: {exc}")
        summary["flow"] = {"ok": False, "error": str(exc)}

    candidate_paths: List[Path] = []
    for key in ("report_path",):
        report_path = density_result.get(key)
        if report_path:
            candidate_paths.append(Path(report_path))
        report_path = flow_result.get(key)
        if report_path:
            candidate_paths.append(Path(report_path))

    latest_report = _locate_latest_report(candidate_paths)
    if latest_report:
        inferred_run_id = _extract_run_id_from_path(latest_report, run_id)
        print(f"🕒 Latest report detected: {latest_report.name} → run_id={inferred_run_id}")
    else:
        inferred_run_id = run_id
        print("⚠️ Could not infer run ID from reports; using provided identifier")

    run_reports_dir = reports_base / inferred_run_id
    if latest_report:
        _copy_reports_to_run_folder(latest_report.parent, run_reports_dir)
    else:
        run_reports_dir.mkdir(parents=True, exist_ok=True)

    summary["final_run_id"] = inferred_run_id
    summary["reports_dir"] = str(run_reports_dir)

    try:
        print("📊 Calculating flow segment counts…")
        overtaking_segments, co_presence_segments = calculate_flow_segment_counts(
            reports_base, inferred_run_id
        )
    except Exception as exc:
        print(f"⚠️ Flow segment count calculation failed: {exc}")
        overtaking_segments, co_presence_segments = 0, 0

    summary["flow_segment_counts"] = {
        "overtaking": overtaking_segments,
        "co_presence": co_presence_segments,
    }

    artifacts_dir: Optional[Path] = None
    if run_reports_dir.exists():
        print("🧩 Generating UI artifacts…")
        try:
            artifacts_dir = export_ui_artifacts(
                run_reports_dir,
                inferred_run_id,
                overtaking_segments,
                co_presence_segments,
                environment=environment,
            )
            print(f"✅ UI artifacts ready at {artifacts_dir}")
        except Exception as exc:
            print(f"⚠️ UI artifact export failed: {exc}")
    else:
        print(f"⚠️ Reports directory missing: {run_reports_dir}")

    heatmap_counts: Tuple[int, int] = (0, 0)
    if run_reports_dir.exists():
        print("🌡️  Generating heatmaps and captions…")
        try:
            storage_service = get_storage_service()
            heatmap_counts = export_heatmaps_and_captions(
                inferred_run_id, run_reports_dir, storage_service
            )
            print(
                "✅ Heatmap generation complete: "
                f"{heatmap_counts[0]} heatmaps, {heatmap_counts[1]} captions"
            )
        except Exception as exc:
            print(f"⚠️ Heatmap generation skipped: {exc}")

    summary["artifacts_dir"] = str(artifacts_dir) if artifacts_dir else None
    summary["heatmaps"] = {
        "generated": heatmap_counts[0],
        "captions": heatmap_counts[1],
    }

    summary_path = f"artifacts/{inferred_run_id}/ui/pipeline_summary.json"
    try:
        action = "Uploading" if storage.config.use_cloud_storage else "Saving"
        print(f"📦 {action} pipeline summary to {summary_path}…")
        storage.save_artifact_json(summary_path, summary)
        print("✅ Pipeline summary persisted")
    except Exception as exc:  # pragma: no cover - defensive logging path
        print(f"⚠️ Failed to persist pipeline summary: {exc}")

    print("🎉 Density analytics pipeline complete")
    return summary


__all__ = ["run_density_pipeline"]

