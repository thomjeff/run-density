"""Unit tests for config package flow.csv and per-event GPX export (#769)."""

import json
import shutil
from pathlib import Path

import yaml

from app.core.config_package.segment_recipes import (
    export_package_flow_and_gpx_files,
    get_event_route_preview,
)
from app.core.config_package.storage import export_config_package_segments

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_GPX = _REPO_ROOT / "cursor" / "plotaroute" / "01_start_friel.gpx"


def _write_minimal_library(package: Path, config_id: str) -> None:
    if not _REFERENCE_GPX.is_file():
        import pytest

        pytest.skip("cursor/plotaroute/01_start_friel.gpx not present")
    lib = package / "segment_library"
    lib.mkdir()
    shutil.copy2(_REFERENCE_GPX, lib / "01_start_friel.gpx")
    manifest = {
        "chunks": [
            {
                "id": "01",
                "file": "01_start_friel.gpx",
                "seg_label": "Start to Friel",
                "width_m": 3,
                "schema": "on_course_open",
                "direction": "uni",
            }
        ],
        "recipes": {"full": ["01"]},
    }
    (lib / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")
    (package / "config.json").write_text(
        json.dumps(
            {
                "config_id": config_id,
                "label": "Test",
                "package_events": ["full"],
            }
        ),
        encoding="utf-8",
    )
    course = {
        "id": config_id,
        "config_id": config_id,
        "segments": [
            {
                "seg_id": "S1",
                "seg_label": "Start to Friel",
                "from_km": 0,
                "to_km": 2.71,
                "events": ["full"],
                "width_m": 3,
                "schema": "on_course_open",
                "direction": "uni",
                "full_from_km": 0,
                "full_to_km": 2.71,
            }
        ],
        "locations": [],
    }
    (package / "course.json").write_text(json.dumps(course), encoding="utf-8")


def test_export_package_flow_and_gpx_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    config_id = "pkg769flow01"
    package = tmp_path / config_id
    package.mkdir()
    _write_minimal_library(package, config_id)

    result = export_package_flow_and_gpx_files(config_id)
    assert result["flow_exported"] is True
    assert (package / "flow.csv").is_file()
    assert (package / "full.gpx").is_file()
    assert any(g["event_id"] == "full" for g in result["gpx_files"])


def test_get_event_route_preview_returns_coordinates(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    config_id = "pkg769prev01"
    package = tmp_path / config_id
    package.mkdir()
    _write_minimal_library(package, config_id)

    preview = get_event_route_preview(config_id, "full")
    assert preview["event_id"] == "full"
    assert len(preview["coordinates"]) >= 2
    assert preview["leg_count"] == 1


def test_export_config_package_segments_includes_flow_gpx(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    config_id = "pkg769full01"
    package = tmp_path / config_id
    package.mkdir()
    _write_minimal_library(package, config_id)

    result = export_config_package_segments(config_id)
    assert (package / "segments.csv").is_file()
    assert (package / "flow.csv").is_file()
    assert (package / "full.gpx").is_file()
    assert result["flow_gpx"]["flow_exported"] is True
