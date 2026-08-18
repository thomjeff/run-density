"""Issue #879: immutable org runner datasets and atomic package assignment."""

from __future__ import annotations

import pytest

from app.core.config_package.runner_datasets import (
    assign_runner_dataset,
    assign_runner_dataset_or_delete_package,
    create_runner_dataset,
    create_scenario_dataset,
    get_package_runner_assignment,
    list_compatible_runner_datasets,
    list_runner_datasets,
    load_runner_dataset,
)
from app.core.config_package.storage import (
    create_config_package,
    load_config_manifest,
    upload_runner_files_to_package,
)


def _csv(event: str, ids: list[str], *, distance: float = 10.0) -> bytes:
    lines = ["event,runner_id,pace,distance,start_offset"]
    for i, rid in enumerate(ids):
        pace = 5.0 + i * 0.2
        lines.append(f"{event},{rid},{pace},{distance},0")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _zero_controls(*events: str) -> dict:
    blank = {
        "chg_participants": 0.0,
        "chg_p00": 0.0,
        "chg_p05": 0.0,
        "chg_p25": 0.0,
        "chg_p50": 0.0,
        "chg_p75": 0.0,
        "chg_p95": 0.0,
        "chg_p100": 0.0,
    }
    return {event: dict(blank) for event in events}


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.runner_datasets.get_runflow_root",
        lambda: tmp_path,
    )


def test_create_dataset_writes_immutable_library(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    created = create_runner_dataset(
        "2026 race week",
        [
            ("10k_runners.csv", _csv("10k", ["a1", "a2"])),
            ("half_runners.csv", _csv("half", ["b1", "b2"], distance=21.1)),
        ],
        description="actuals",
    )
    assert created["label"] == "2026 race week"
    assert created["events"] == ["half", "10k"]
    assert created["source_dataset_id"] is None
    assert created["files"]["10k"] == "10k_runners.csv"
    dest = tmp_path / "org" / "runners" / created["dataset_id"]
    assert (dest / "manifest.json").is_file()
    assert (dest / "10k_runners.csv").is_file()
    listed = list_runner_datasets()
    assert len(listed) == 1
    assert listed[0]["dataset_id"] == created["dataset_id"]
    tenk = created["summary"]["10k"]
    assert tenk["participants"] == 2
    assert tenk["p00"] == pytest.approx(5.0)
    assert tenk["p50"] == pytest.approx(5.1)
    assert tenk["p100"] == pytest.approx(5.2)
    assert "p05" in tenk and "p25" in tenk and "p75" in tenk and "p95" in tenk
    loaded = load_runner_dataset(created["dataset_id"])
    assert loaded["summary"]["10k"]["participants"] == 2
    assert loaded["summary"]["half"]["participants"] == 2


def test_create_dataset_rejects_cross_event_duplicate_ids(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Duplicate runner_id"):
        create_runner_dataset(
            "Bad field",
            [
                ("10k_runners.csv", _csv("10k", ["same", "a2"])),
                ("half_runners.csv", _csv("half", ["same", "b2"], distance=21.1)),
            ],
        )
    runners_root = tmp_path / "org" / "runners"
    if runners_root.is_dir():
        assert list(runners_root.iterdir()) == []


def test_create_dataset_rejects_event_column_mismatch(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="event column must be"):
        create_runner_dataset(
            "Mismatch",
            [("10k_runners.csv", _csv("half", ["a1"]))],
        )


def test_scenario_creates_new_dataset_and_preserves_source(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    source = create_runner_dataset(
        "Actuals",
        [("10k_runners.csv", _csv("10k", ["a1", "a2", "a3"]))],
    )
    source_path = tmp_path / "org" / "runners" / source["dataset_id"] / "10k_runners.csv"
    before = source_path.read_bytes()
    scenario = create_scenario_dataset(
        source["dataset_id"],
        label="Actuals +0",
        control_variables=_zero_controls("10k"),
    )
    assert scenario["dataset_id"] != source["dataset_id"]
    assert scenario["source_dataset_id"] == source["dataset_id"]
    assert source_path.read_bytes() == before
    new_path = tmp_path / "org" / "runners" / scenario["dataset_id"] / "10k_runners.csv"
    assert new_path.is_file()


def test_compatible_filter_requires_all_package_events(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    partial = create_runner_dataset(
        "10k+half",
        [
            ("10k_runners.csv", _csv("10k", ["a1"])),
            ("half_runners.csv", _csv("half", ["b1"], distance=21.1)),
        ],
    )
    full = create_runner_dataset(
        "10k+half+full",
        [
            ("10k_runners.csv", _csv("10k", ["c1"])),
            ("half_runners.csv", _csv("half", ["d1"], distance=21.1)),
            ("full_runners.csv", _csv("full", ["e1"], distance=42.2)),
        ],
    )
    extra = create_runner_dataset(
        "with elite extra",
        [
            ("10k_runners.csv", _csv("10k", ["f1"])),
            ("half_runners.csv", _csv("half", ["g1"], distance=21.1)),
            ("full_runners.csv", _csv("full", ["h1"], distance=42.2)),
            ("elite_runners.csv", _csv("elite", ["i1"], distance=5.0)),
        ],
    )
    compatible = {
        row["dataset_id"]
        for row in list_compatible_runner_datasets(["10k", "half", "full"])
    }
    assert partial["dataset_id"] not in compatible
    assert full["dataset_id"] in compatible
    assert extra["dataset_id"] in compatible


def test_assign_copies_required_files_and_records_provenance(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    pkg = create_config_package(
        "Race", "", event_day="sun", package_events=["10k", "half", "full"]
    )
    dataset = create_runner_dataset(
        "Field",
        [
            ("10k_runners.csv", _csv("10k", ["a1"])),
            ("half_runners.csv", _csv("half", ["b1"], distance=21.1)),
            ("full_runners.csv", _csv("full", ["c1"], distance=42.2)),
            ("elite_runners.csv", _csv("elite", ["d1"], distance=5.0)),
        ],
    )
    result = assign_runner_dataset(pkg["config_id"], dataset["dataset_id"])
    package_dir = tmp_path / "config" / pkg["config_id"]
    assert result["copied_files"] == [
        "10k_runners.csv",
        "half_runners.csv",
        "full_runners.csv",
    ]
    assert (package_dir / "10k_runners.csv").is_file()
    assert not (package_dir / "elite_runners.csv").exists()
    manifest = load_config_manifest(pkg["config_id"])
    assert manifest["runners_dataset_id"] == dataset["dataset_id"]


def test_assign_rejects_incomplete_dataset_without_changing_package(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    pkg = create_config_package(
        "Race", "", event_day="sun", package_events=["10k", "half", "full"]
    )
    package_dir = tmp_path / "config" / pkg["config_id"]
    original = _csv("10k", ["keep1"])
    (package_dir / "10k_runners.csv").write_bytes(original)

    complete = create_runner_dataset(
        "Complete",
        [
            ("10k_runners.csv", _csv("10k", ["a1"])),
            ("half_runners.csv", _csv("half", ["b1"], distance=21.1)),
            ("full_runners.csv", _csv("full", ["c1"], distance=42.2)),
        ],
    )
    assign_runner_dataset(pkg["config_id"], complete["dataset_id"])
    after_ok = (package_dir / "10k_runners.csv").read_bytes()

    partial = create_runner_dataset(
        "Partial",
        [
            ("10k_runners.csv", _csv("10k", ["z1"])),
            ("half_runners.csv", _csv("half", ["z2"], distance=21.1)),
        ],
    )
    with pytest.raises(ValueError, match="missing required event"):
        assign_runner_dataset(pkg["config_id"], partial["dataset_id"])

    manifest = load_config_manifest(pkg["config_id"])
    assert manifest["runners_dataset_id"] == complete["dataset_id"]
    assert (package_dir / "10k_runners.csv").read_bytes() == after_ok
    assignment = get_package_runner_assignment(pkg["config_id"])
    assert assignment["runners_dataset_id"] == complete["dataset_id"]
    compatible_ids = {row["dataset_id"] for row in assignment["compatible_datasets"]}
    assert partial["dataset_id"] not in compatible_ids
    assert complete["dataset_id"] in compatible_ids


def test_assign_rolls_back_when_manifest_save_fails(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    pkg = create_config_package(
        "Race", "", event_day="sun", package_events=["10k"]
    )
    package_dir = tmp_path / "config" / pkg["config_id"]
    existing = _csv("10k", ["keep"])
    (package_dir / "10k_runners.csv").write_bytes(existing)
    dataset = create_runner_dataset(
        "Field",
        [("10k_runners.csv", _csv("10k", ["new1"]))],
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("manifest write failed")

    monkeypatch.setattr(
        "app.core.config_package.runner_datasets.save_config_manifest",
        _boom,
    )
    with pytest.raises(RuntimeError, match="manifest write failed"):
        assign_runner_dataset(pkg["config_id"], dataset["dataset_id"])

    assert (package_dir / "10k_runners.csv").read_bytes() == existing
    manifest = load_config_manifest(pkg["config_id"])
    assert "runners_dataset_id" not in manifest


def test_package_upload_rejects_cross_file_duplicate_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    target = create_config_package(
        "Target", "", event_day="sun", package_events=["10k", "half"]
    )["config_id"]
    upload_runner_files_to_package(
        target, [("10k_runners.csv", _csv("10k", ["shared", "a2"]))]
    )
    with pytest.raises(ValueError, match="Duplicate runner_id"):
        upload_runner_files_to_package(
            target,
            [("half_runners.csv", _csv("half", ["shared", "b2"], distance=21.1))],
        )
    assert not (tmp_path / target / "half_runners.csv").exists()


def test_create_package_with_dataset_freezes_files(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    dataset = create_runner_dataset(
        "Field",
        [
            ("10k_runners.csv", _csv("10k", ["a1"])),
            ("half_runners.csv", _csv("half", ["b1"], distance=21.1)),
        ],
    )
    pkg = create_config_package(
        "New race", "", event_day="sun", package_events=["10k", "half"]
    )
    assigned = assign_runner_dataset_or_delete_package(
        pkg["config_id"], dataset["dataset_id"]
    )
    package_dir = tmp_path / "config" / pkg["config_id"]
    assert assigned["runners_dataset_id"] == dataset["dataset_id"]
    assert (package_dir / "10k_runners.csv").is_file()
    assert (package_dir / "half_runners.csv").is_file()
    assert load_config_manifest(pkg["config_id"])["runners_dataset_id"] == dataset[
        "dataset_id"
    ]


def test_incompatible_dataset_on_create_deletes_package(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    dataset = create_runner_dataset(
        "Partial",
        [("10k_runners.csv", _csv("10k", ["a1"]))],
    )
    pkg = create_config_package(
        "New race", "", event_day="sun", package_events=["10k", "half"]
    )
    config_id = pkg["config_id"]
    with pytest.raises(ValueError, match="missing required event"):
        assign_runner_dataset_or_delete_package(config_id, dataset["dataset_id"])
    assert not (tmp_path / "config" / config_id).exists()
