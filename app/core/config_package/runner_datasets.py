"""
Org-level runner datasets (Issue #879).

Immutable library objects live under ``runflow/org/runners/{dataset_id}/``.
Packages store ``runners_dataset_id`` and freeze-on-assign copies required
``{event}_runners.csv`` files into the package ``data_dir``.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from app.core.baseline.generator import generate_runner_file
from app.core.baseline.calculator import calculate_baseline_metrics
from app.core.baseline.validation import (
    validate_control_variables,
    validate_cutoff_time_format,
)
from app.core.config_package.runner_files import (
    RUNNERS_FILENAME_SUFFIX,
    dataset_files_map,
    ordered_dataset_events,
    summarize_runner_frames,
    validate_runner_csv_set,
)
from app.core.config_package.storage import (
    delete_config_package,
    load_config_manifest,
    normalize_package_events,
    resolve_config_package_path,
    save_config_manifest,
    validate_config_id,
)
from app.utils.run_id import generate_run_id, get_runflow_root

logger = logging.getLogger(__name__)

ORG_RUNNERS_DIRNAME = "runners"
DATASET_MANIFEST_NAME = "manifest.json"
_STAGING_PREFIX = "."
_PARTIAL_SUFFIX = ".partial"


def get_org_runners_dir() -> Path:
    return get_runflow_root() / "org" / ORG_RUNNERS_DIRNAME


def validate_dataset_id(dataset_id: str) -> str:
    """Dataset ids are path-safe short UUIDs (same alphabet as config_id)."""
    if not dataset_id or not isinstance(dataset_id, str):
        raise ValueError("dataset_id is required")
    normalized = dataset_id.strip()
    if not normalized:
        raise ValueError("dataset_id must not be empty")
    if normalized in (".", "..") or normalized.startswith(_STAGING_PREFIX):
        raise ValueError(f"Invalid dataset_id: {dataset_id}")
    if Path(normalized).name != normalized or "/" in normalized or "\\" in normalized:
        raise ValueError(f"Invalid dataset_id: {dataset_id}")
    if not normalized.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Invalid dataset_id: {dataset_id}")
    if len(normalized) < 10:
        raise ValueError("dataset_id must be at least 10 characters")
    return normalized


def get_dataset_dir(dataset_id: str) -> Path:
    return get_org_runners_dir() / validate_dataset_id(dataset_id)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_manifest(dataset_dir: Path) -> Dict[str, Any]:
    path = dataset_dir / DATASET_MANIFEST_NAME
    if not path.is_file():
        raise FileNotFoundError(f"Runner dataset manifest not found: {dataset_dir.name}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid runner dataset manifest: {dataset_dir.name}")
    return data


def _public_dataset(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    events = ordered_dataset_events(manifest.get("events") or [])
    files = manifest.get("files") or dataset_files_map(events)
    return {
        "dataset_id": manifest.get("dataset_id"),
        "label": manifest.get("label") or manifest.get("dataset_id"),
        "description": manifest.get("description") or "",
        "created": manifest.get("created"),
        "source_dataset_id": manifest.get("source_dataset_id"),
        "control_variables": manifest.get("control_variables"),
        "events": events,
        "files": files,
        "summary": manifest.get("summary") or {},
    }


def _summary_from_dataset_dir(
    dataset_dir: Path, events: Sequence[str]
) -> Dict[str, Any]:
    frames: List[Tuple[str, pd.DataFrame]] = []
    for event in ordered_dataset_events(events):
        path = dataset_dir / f"{event}{RUNNERS_FILENAME_SUFFIX}"
        if not path.is_file():
            continue
        df = pd.read_csv(path, dtype={"runner_id": "string"})
        frames.append((event, df))
    return summarize_runner_frames(frames)


def load_runner_dataset(dataset_id: str) -> Dict[str, Any]:
    did = validate_dataset_id(dataset_id)
    dataset_dir = get_dataset_dir(did)
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Runner dataset not found: {did}")
    manifest = _read_manifest(dataset_dir)
    public = _public_dataset(manifest)
    try:
        live = _summary_from_dataset_dir(dataset_dir, public["events"])
        if live:
            public["summary"] = live
    except (OSError, ValueError) as exc:
        logger.warning("Could not recompute runner dataset summary for %s: %s", did, exc)
    return public


def list_runner_datasets() -> List[Dict[str, Any]]:
    root = get_org_runners_dir()
    if not root.is_dir():
        return []
    rows: List[Dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith(_STAGING_PREFIX):
            continue
        try:
            rows.append(_public_dataset(_read_manifest(child)))
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Skipping invalid runner dataset %s: %s", child.name, exc)
            continue
    rows.sort(key=lambda r: ((r.get("label") or "").lower(), r.get("created") or ""))
    return rows


def dataset_covers_events(
    dataset: Mapping[str, Any], required_events: Sequence[str]
) -> bool:
    have = {str(e).strip().lower() for e in (dataset.get("events") or []) if str(e).strip()}
    need = [str(e).strip().lower() for e in required_events if str(e).strip()]
    if not need:
        return False
    return all(event in have for event in need)


def list_compatible_runner_datasets(
    required_events: Sequence[str],
) -> List[Dict[str, Any]]:
    return [
        row
        for row in list_runner_datasets()
        if dataset_covers_events(row, required_events)
    ]


def package_required_runner_events(config_id: str) -> List[str]:
    manifest = load_config_manifest(config_id)
    return normalize_package_events(manifest.get("package_events"))


def _write_dataset_tree(
    dataset_id: str,
    manifest: Dict[str, Any],
    files_by_event: Mapping[str, bytes],
) -> Path:
    root = get_org_runners_dir()
    root.mkdir(parents=True, exist_ok=True)
    dest = root / dataset_id
    if dest.exists():
        raise FileExistsError(f"Runner dataset path already exists: {dataset_id}")
    staging = root / f"{_STAGING_PREFIX}{dataset_id}{_PARTIAL_SUFFIX}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)
    try:
        for event, data in files_by_event.items():
            filename = f"{event}{RUNNERS_FILENAME_SUFFIX}"
            (staging / filename).write_bytes(data)
        with open(staging / DATASET_MANIFEST_NAME, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        staging.rename(dest)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if dest.exists() and dest.is_dir() and not (dest / DATASET_MANIFEST_NAME).is_file():
            shutil.rmtree(dest, ignore_errors=True)
        raise
    return dest


def create_runner_dataset(
    label: str,
    uploads: Sequence[Tuple[str, bytes]],
    *,
    description: str = "",
    source_dataset_id: Optional[str] = None,
    control_variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create an immutable runner dataset from CSV bytes.

    Cross-event duplicate ``runner_id`` values fail before any library folder
    is created (Issue #852).
    """
    clean_label = (label or "").strip()
    if not clean_label:
        raise ValueError("label is required")
    clean_description = (description or "").strip()
    if len(clean_description) > 255:
        raise ValueError("description must be at most 255 characters")

    source_id = None
    if source_dataset_id:
        source_id = validate_dataset_id(source_dataset_id)
        load_runner_dataset(source_id)

    by_event, frames, _file_names = validate_runner_csv_set(uploads)
    events = ordered_dataset_events(by_event.keys())
    dataset_id = generate_run_id()
    created = _now_iso()
    manifest: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "label": clean_label,
        "description": clean_description,
        "created": created,
        "source_dataset_id": source_id,
        "control_variables": control_variables,
        "events": events,
        "files": dataset_files_map(events),
        "summary": summarize_runner_frames(frames),
    }
    _write_dataset_tree(dataset_id, manifest, by_event)
    logger.info(
        "Created runner dataset %s (%s) events=%s source=%s",
        dataset_id,
        clean_label,
        ",".join(events),
        source_id,
    )
    return _public_dataset(manifest)


def _new_participant_count(base_participants: int, chg_participants: float) -> int:
    return int(base_participants * (1 + chg_participants))


def create_scenario_dataset(
    source_dataset_id: str,
    *,
    label: str,
    control_variables: Dict[str, Dict[str, Any]],
    description: str = "",
) -> Dict[str, Any]:
    """Generate a new immutable dataset from a source dataset + control variables."""
    source = load_runner_dataset(source_dataset_id)
    if not control_variables:
        raise ValueError("control_variables is required")
    validate_control_variables(control_variables)

    source_events = set(source["events"] or [])
    unknown = sorted(set(control_variables.keys()) - source_events)
    if unknown:
        raise ValueError(
            f"control_variables include events not in source dataset: {', '.join(unknown)}"
        )

    source_dir = get_dataset_dir(source["dataset_id"])
    used_runner_ids: set[str] = set()
    uploads: List[Tuple[str, bytes]] = []

    for event_name, control_vars in control_variables.items():
        filename = f"{event_name}{RUNNERS_FILENAME_SUFFIX}"
        runners_path = source_dir / filename
        if not runners_path.is_file():
            raise FileNotFoundError(
                f"Source dataset is missing {filename}"
            )
        baseline_df = pd.read_csv(runners_path)
        if "start_offset" not in baseline_df.columns:
            raise ValueError(
                f"{filename}: start_offset is required to create a scenario"
            )
        metrics = calculate_baseline_metrics(baseline_df)
        chg_participants = float(control_vars["chg_participants"])
        new_participants = _new_participant_count(
            int(metrics["base_participants"]), chg_participants
        )
        cutoff_mins = None
        cutoff_raw = control_vars.get("cutoff_mins")
        if cutoff_raw:
            if isinstance(cutoff_raw, str):
                cutoff_mins = validate_cutoff_time_format(cutoff_raw)
            else:
                cutoff_mins = float(cutoff_raw)
        distance = float(baseline_df["distance"].iloc[0])
        new_df = generate_runner_file(
            baseline_df=baseline_df,
            control_vars=control_vars,
            new_participants=new_participants,
            event_name=event_name,
            distance=distance,
            cutoff_mins=cutoff_mins,
            used_runner_ids=used_runner_ids,
        )
        used_runner_ids.update(new_df["runner_id"].astype(str).tolist())
        uploads.append((filename, new_df.to_csv(index=False).encode("utf-8")))

    return create_runner_dataset(
        label,
        uploads,
        description=description,
        source_dataset_id=source["dataset_id"],
        control_variables=control_variables,
    )


def assign_runner_dataset(config_id: str, dataset_id: str) -> Dict[str, Any]:
    """
    Atomically assign a dataset to a package and freeze required CSVs.

    Validates compatibility first. On failure, package-local runner files and
    ``runners_dataset_id`` are left unchanged.
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    manifest = load_config_manifest(cid)
    required = normalize_package_events(manifest.get("package_events"))
    if not required:
        raise ValueError("Package has no events; cannot assign a runner dataset")

    dataset = load_runner_dataset(dataset_id)
    if not dataset_covers_events(dataset, required):
        missing = [e for e in required if e not in set(dataset.get("events") or [])]
        raise ValueError(
            f"Runner dataset '{dataset.get('label')}' is missing required event "
            f"files: {', '.join(missing)}"
        )

    dataset_dir = get_dataset_dir(dataset["dataset_id"])
    dest_names = [f"{event}{RUNNERS_FILENAME_SUFFIX}" for event in required]
    for name in dest_names:
        src = dataset_dir / name
        if not src.is_file():
            raise ValueError(f"Dataset file missing: {name}")

    staging = package_path / f"{_STAGING_PREFIX}assign_runners_{dataset['dataset_id']}{_PARTIAL_SUFFIX}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)

    backups: List[Tuple[Path, Optional[bytes]]] = []
    manifest_path = package_path / "config.json"
    previous_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None
    copied = False
    try:
        for name in dest_names:
            shutil.copy2(dataset_dir / name, staging / name)
        for name in dest_names:
            dest = package_path / name
            backups.append((dest, dest.read_bytes() if dest.is_file() else None))
        copied = True
        for name in dest_names:
            shutil.copy2(staging / name, package_path / name)
        manifest["runners_dataset_id"] = dataset["dataset_id"]
        save_config_manifest(package_path, manifest)
    except Exception:
        if copied:
            for dest, original in backups:
                if original is None:
                    if dest.is_file():
                        dest.unlink()
                else:
                    dest.write_bytes(original)
            if previous_manifest is not None:
                manifest_path.write_bytes(previous_manifest)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    logger.info(
        "Assigned runner dataset %s to package %s (files=%s)",
        dataset["dataset_id"],
        cid,
        ",".join(dest_names),
    )
    return {
        "config_id": cid,
        "runners_dataset_id": dataset["dataset_id"],
        "copied_files": dest_names,
        "dataset": dataset,
        "manifest": load_config_manifest(cid),
    }


def assign_runner_dataset_or_delete_package(
    config_id: str, dataset_id: str
) -> Dict[str, Any]:
    """Assign a dataset to a newly created package; delete the package on failure."""
    try:
        return assign_runner_dataset(config_id, dataset_id)
    except Exception:
        delete_config_package(config_id)
        raise


def get_package_runner_assignment(config_id: str) -> Dict[str, Any]:
    cid = validate_config_id(config_id)
    manifest = load_config_manifest(cid)
    required = normalize_package_events(manifest.get("package_events"))
    assigned_id = manifest.get("runners_dataset_id")
    dataset = None
    if assigned_id:
        try:
            dataset = load_runner_dataset(str(assigned_id))
        except FileNotFoundError:
            dataset = {
                "dataset_id": assigned_id,
                "missing": True,
                "label": assigned_id,
            }
    compatible = list_compatible_runner_datasets(required)
    return {
        "config_id": cid,
        "required_events": required,
        "runners_dataset_id": assigned_id,
        "dataset": dataset,
        "compatible_datasets": compatible,
    }
