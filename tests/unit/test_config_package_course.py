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
    result = create_config_package("Pkg", "", package_events=["full"])
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
    result = create_config_package("Course RT", "round trip", package_events=["full"])
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


def test_save_preserves_recipe_kms_from_stale_client(tmp_path, monkeypatch):
    """A stale client save must not revert recipe-applied per-event kms or drop the flag."""
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package("Recipe Pkg", "", package_events=["full", "half"])
    config_id = result["config_id"]

    # Simulate recipe apply: course on disk has flag + correct per-event kms.
    course = load_config_course(config_id)
    course["segment_library_applied"] = True
    course["segments"] = [
        {
            "seg_id": "S10",
            "label": "Gibson",
            "leg_id": "09",
            "from_km": 23.9,
            "to_km": 29.67,
            "events": ["full", "half"],
            "full_from_km": 23.9,
            "full_to_km": 29.67,
            "half_from_km": 5.06,
            "half_to_km": 10.83,
        }
    ]
    save_config_course(config_id, course)

    # Stale browser snapshot: no flag, old corrupted kms, but a new label edit.
    stale = load_config_course(config_id)
    stale.pop("segment_library_applied", None)
    stale["segments"][0].update(
        {"half_from_km": 6.62, "half_to_km": 12.39, "label": "Gibson (edited)"}
    )
    save_config_course(config_id, stale)

    reloaded = load_config_course(config_id)
    seg = reloaded["segments"][0]
    assert reloaded["segment_library_applied"] is True
    assert seg["half_from_km"] == 5.06
    assert seg["half_to_km"] == 10.83
    assert seg["label"] == "Gibson (edited)"


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
