"""
Analysis configuration loader.

Loads analysis.json once, validates required fields, and resolves runtime paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


class AnalysisConfigError(ValueError):
    """Raised when analysis.json is missing required fields or invalid."""


@dataclass(frozen=True)
class AnalysisContext:
    analysis_config: Dict[str, Any]
    run_path: Path
    analysis_json_path: Path
    data_files: Dict[str, Any]
    data_dir: Path
    segments_csv_path: Path
    flow_csv_path: Path
    locations_csv_path: Optional[Path]

    def runners_csv_path(self, event_name: str) -> Path:
        runners = self.data_files.get("runners", {})
        event_key = event_name.lower()
        runners_path = runners.get(event_key) or runners.get(event_name)
        if not runners_path:
            raise AnalysisConfigError(
                f"analysis.json missing data_files.runners entry for event '{event_name}'."
            )
        return _resolve_path(str(runners_path), self.data_dir)

    def gpx_path(self, event_name: str) -> Path:
        gpx_files = self.data_files.get("gpx", {})
        event_key = event_name.lower()
        gpx_path = gpx_files.get(event_key) or gpx_files.get(event_name)
        if not gpx_path:
            raise AnalysisConfigError(
                f"analysis.json missing data_files.gpx entry for event '{event_name}'."
            )
        return _resolve_path(str(gpx_path), self.data_dir)


def load_analysis_context(run_path: Path) -> AnalysisContext:
    """Load analysis.json, validate required fields, and resolve absolute paths."""
    analysis_json_path = run_path / "analysis.json"
    if not analysis_json_path.exists():
        raise FileNotFoundError(f"analysis.json not found at {analysis_json_path}")

    with analysis_json_path.open("r", encoding="utf-8") as handle:
        analysis_config = json.load(handle)

    return build_analysis_context(analysis_config, run_path, analysis_json_path)


def build_analysis_context(
    analysis_config: Dict[str, Any],
    run_path: Path,
    analysis_json_path: Optional[Path] = None,
) -> AnalysisContext:
    """Validate analysis_config and return a resolved AnalysisContext."""
    if analysis_json_path is None:
        analysis_json_path = run_path / "analysis.json"

    data_dir_value = analysis_config.get("data_dir")
    if not data_dir_value:
        raise AnalysisConfigError("analysis.json missing required field: data_dir")
    data_dir = Path(data_dir_value).resolve()

    data_files = analysis_config.get("data_files")
    if not isinstance(data_files, dict):
        raise AnalysisConfigError("analysis.json missing required field: data_files")

    segments_path = _resolve_required_path(data_files, "segments", data_dir)
    flow_path = _resolve_required_path(data_files, "flow", data_dir)
    locations_path = _resolve_optional_path(data_files, "locations", data_dir)

    events = analysis_config.get("events", [])
    if not events:
        raise AnalysisConfigError("analysis.json missing required field: events")

    for event in events:
        _require_field(event, "name", "events[*]")
        _require_field(event, "day", "events[*]")
        _require_field(event, "start_time", "events[*]")
        _require_field(event, "event_duration_minutes", "events[*]")
        _require_field(event, "runners_file", "events[*]")
        _require_field(event, "gpx_file", "events[*]")

    runners = data_files.get("runners")
    if not isinstance(runners, dict) or not runners:
        raise AnalysisConfigError("analysis.json missing required field: data_files.runners")

    gpx = data_files.get("gpx")
    if not isinstance(gpx, dict) or not gpx:
        raise AnalysisConfigError("analysis.json missing required field: data_files.gpx")

    _validate_segments_csv_fields(segments_path)

    for event in events:
        event_name = event.get("name")
        if event_name:
            _validate_event_file_mapping(runners, "runners", event_name)
            _validate_event_file_mapping(gpx, "gpx", event_name)

    return AnalysisContext(
        analysis_config=analysis_config,
        run_path=run_path,
        analysis_json_path=analysis_json_path,
        data_files=data_files,
        data_dir=data_dir,
        segments_csv_path=segments_path,
        flow_csv_path=flow_path,
        locations_csv_path=locations_path,
    )


def _resolve_required_path(data_files: Dict[str, Any], key: str, data_dir: Path) -> Path:
    value = data_files.get(key)
    if not value:
        raise AnalysisConfigError(f"analysis.json missing required field: data_files.{key}")
    return _resolve_path(value, data_dir)


def _resolve_optional_path(data_files: Dict[str, Any], key: str, data_dir: Path) -> Optional[Path]:
    value = data_files.get(key)
    if not value:
        return None
    return _resolve_path(value, data_dir)


def _resolve_path(path_value: str, data_dir: Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == data_dir.name:
        return candidate.resolve()
    return (data_dir / candidate).resolve()


def _require_field(container: Dict[str, Any], field: str, scope: str) -> None:
    if container.get(field) in (None, ""):
        raise AnalysisConfigError(f"analysis.json missing required field: {scope}.{field}")


def _validate_segments_csv_fields(segments_path: Path) -> None:
    if not segments_path.exists():
        raise FileNotFoundError(f"segments.csv not found at {segments_path}")
    df = pd.read_csv(segments_path, nrows=0)
    required_columns = {"seg_id", "seg_label", "schema", "width_m", "direction"}
    missing = required_columns - set(df.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise AnalysisConfigError(
            f"segments.csv missing required columns: {missing_list}"
        )


def _validate_event_file_mapping(mapping: Dict[str, Any], mapping_name: str, event_name: str) -> None:
    normalized_event = event_name.lower()
    if normalized_event not in mapping and event_name not in mapping:
        raise AnalysisConfigError(
            f"analysis.json missing data_files.{mapping_name} entry for event '{event_name}'"
        )
