"""Unit tests for config package storage (Issue #756)."""

import json
from pathlib import Path

import pytest

from app.core.config_package.storage import (
    create_config_package,
    delete_config_package,
    import_runner_files_from_package,
    list_config_packages,
    load_config_manifest,
    normalize_package_events,
    package_readiness,
    resolve_config_package_path,
    update_config_package_metadata,
    upload_runner_files_to_package,
    validate_config_id,
)


def test_validate_config_id_rejects_path_traversal():
    with pytest.raises(ValueError):
        validate_config_id("../etc")
    with pytest.raises(ValueError):
        validate_config_id("foo/bar")


def test_validate_config_id_accepts_uuid_and_legacy_slug():
    assert validate_config_id("p0ZoB1FwH6yT2dKx") == "p0ZoB1FwH6yT2dKx"
    assert validate_config_id("2026_final") == "2026_final"


def test_create_config_package_requires_events(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    with pytest.raises(ValueError, match="at least one event"):
        create_config_package("No events", "", event_day="sun", package_events=[])


def test_normalize_package_events_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown event"):
        normalize_package_events(["full", "ultra"])


def test_create_config_package_writes_manifest_and_course(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "2027 Test Package",
        "FM 2027 draft scenario",
        event_day="sun",
        package_events=["full", "half", "10k"],
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id

    assert package_path.is_dir()
    manifest = json.loads((package_path / "config.json").read_text())
    assert manifest["label"] == "2027 Test Package"
    assert manifest["description"] == "FM 2027 draft scenario"
    assert manifest["event_day"] == "sun"
    assert manifest["package_events"] == ["full", "half", "10k"]
    assert manifest["config_id"] == config_id
    assert (package_path / "course.json").is_file()

    course = json.loads((package_path / "course.json").read_text())
    assert course["config_id"] == config_id


def test_create_config_package_custom_resources(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "With OFC",
        "",
        event_day="sun",
        package_events=["10k"],
        resources=[
            {"code": "fpf", "label": "FPF"},
            {"code": "ofc", "label": "Officials"},
        ],
    )
    manifest = json.loads((tmp_path / result["config_id"] / "config.json").read_text())
    assert manifest["resources"] == [
        {"code": "fpf", "label": "FPF"},
        {"code": "ofc", "label": "Officials"},
    ]


def test_list_includes_legacy_folder_with_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    legacy = tmp_path / "2026_final"
    legacy.mkdir()
    (legacy / "segments.csv").write_text("seg_id\nA1\n")

    packages = list_config_packages()
    ids = [p["config_id"] for p in packages]
    assert "2026_final" in ids
    entry = next(p for p in packages if p["config_id"] == "2026_final")
    assert entry["legacy"] is True


def test_update_config_package_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Original", "First desc", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    updated = update_config_package_metadata(config_id, "Renamed", "New desc", "sun")
    assert updated["label"] == "Renamed"
    manifest = load_config_manifest(config_id)
    assert manifest["label"] == "Renamed"
    assert manifest["description"] == "New desc"
    assert manifest["event_day"] == "sun"

    with pytest.raises(ValueError, match="event_day must be one of"):
        update_config_package_metadata(config_id, "Renamed", "New desc", "tuesday")
    course = json.loads((tmp_path / config_id / "course.json").read_text())
    assert course["name"] == "Renamed"
    assert course["description"] == "New desc"


def test_delete_config_package_removes_directory_and_index(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "To delete", "gone", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    assert package_path.is_dir()

    deleted = delete_config_package(config_id)
    assert deleted["deleted"] is True
    assert not package_path.exists()

    index = json.loads((tmp_path / "index.json").read_text())
    assert config_id not in [p.get("config_id") for p in index.get("packages", [])]

    with pytest.raises(FileNotFoundError):
        resolve_config_package_path(config_id)


def test_package_readiness_detects_missing_files(tmp_path):
    pkg = tmp_path / "pkg1"
    pkg.mkdir()
    (pkg / "segments.csv").write_text("x")
    readiness = package_readiness(pkg)
    assert "flow.csv" in readiness["missing"]
    assert readiness["analyze_ready"] is False


_RUNNERS_CSV = """event,runner_id,pace,distance,start_offset
10k,1001,5.5,10,0
10k,1002,6.0,10,12
"""


def test_import_runner_files_from_package_copies_selected_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    source = create_config_package(
        "Source", "", event_day="sun", package_events=["10k", "full"]
    )["config_id"]
    target = create_config_package(
        "Target", "", event_day="sun", package_events=["10k", "full"]
    )["config_id"]
    source_path = tmp_path / source
    (source_path / "10k_runners.csv").write_text(_RUNNERS_CSV, encoding="utf-8")
    (source_path / "full_runners.csv").write_text(
        "event,runner_id,pace,distance,start_offset\nfull,9,4.5,42.2,0\n",
        encoding="utf-8",
    )

    copied = import_runner_files_from_package(target, source, ["10k_runners.csv"])
    assert copied == ["10k_runners.csv"]
    assert (tmp_path / target / "10k_runners.csv").is_file()
    assert not (tmp_path / target / "full_runners.csv").exists()


def test_upload_runner_files_to_package_validates_and_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    target = create_config_package(
        "Target", "", event_day="sun", package_events=["10k"]
    )["config_id"]

    saved = upload_runner_files_to_package(
        target,
        [("10k_runners.csv", _RUNNERS_CSV.encode("utf-8"))],
    )
    assert saved == ["10k_runners.csv"]
    assert "1001" in (tmp_path / target / "10k_runners.csv").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="_runners.csv"):
        upload_runner_files_to_package(target, [("bad.csv", _RUNNERS_CSV.encode("utf-8"))])
