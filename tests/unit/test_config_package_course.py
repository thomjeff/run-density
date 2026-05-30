"""Unit tests for config package course workspace (Issue #757)."""

import json
from pathlib import Path

import pytest

from app.core.config_package.storage import (
    create_config_package,
    load_config_course,
    resolve_config_package_path,
    save_config_course,
    validate_config_course_data,
)


def test_load_config_course_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package("Pkg", "")
    config_id = result["config_id"]
    (tmp_path / config_id / "course.json").unlink()

    with pytest.raises(FileNotFoundError, match="course.json"):
        load_config_course(config_id)


def test_load_config_course_missing_package(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    with pytest.raises(FileNotFoundError, match="Config package not found"):
        load_config_course("nonexistentPkg99")


def test_save_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package("Course RT", "round trip")
    config_id = result["config_id"]

    course = load_config_course(config_id)
    course["name"] = "Updated course"
    course["geometry"] = {
        "type": "LineString",
        "coordinates": [[-66.64, 45.95], [-66.63, 45.96]],
    }
    course["segments"] = [
        {
            "seg_id": "A1",
            "label": "Start",
            "from_km": 0,
            "to_km": 1,
            "events": ["full"],
        }
    ]

    save_config_course(config_id, course)
    reloaded = load_config_course(config_id)

    assert reloaded["id"] == config_id
    assert reloaded["config_id"] == config_id
    assert reloaded["name"] == "Updated course"
    assert reloaded["geometry"]["coordinates"][0] == [-66.64, 45.95]
    assert reloaded["segments"][0]["seg_id"] == "A1"
    assert "updated" in reloaded

    on_disk = json.loads(
        (resolve_config_package_path(config_id) / "course.json").read_text()
    )
    assert on_disk["config_id"] == config_id
    assert "events" not in on_disk


def test_validate_config_course_rejects_id_mismatch():
    with pytest.raises(ValueError, match="config_id"):
        validate_config_course_data({"id": "other-id", "segments": []}, "abc123")


def test_validate_config_course_rejects_bad_geometry():
    with pytest.raises(ValueError, match="LineString"):
        validate_config_course_data(
            {"geometry": {"type": "Point", "coordinates": [0, 0]}},
            "abc123",
        )


def test_save_creates_course_for_legacy_package_without_course_json(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    legacy_id = "legacyPkg757"
    legacy = tmp_path / legacy_id
    legacy.mkdir()
    (legacy / "segments.csv").write_text("seg_id\nA1\n")

    course = {
        "id": legacy_id,
        "name": "Legacy init",
        "segments": [],
        "locations": [],
    }
    save_config_course(legacy_id, course)
    assert (legacy / "course.json").is_file()
    loaded = load_config_course(legacy_id)
    assert loaded["name"] == "Legacy init"
