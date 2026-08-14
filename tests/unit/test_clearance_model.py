"""Clearance / dependency model (Issue #832)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.clearance.model import (
    ClearanceValidationError,
    validate_clearance_doc,
)
from app.core.clearance.playbook import (
    attach_clearance_to_locations,
    build_clearance_playbook,
    load_location_last_runners,
)
from app.core.clearance.storage import load_config_clearance, save_config_clearance
from app.core.config_package.storage import create_config_package


def _pair_doc(**kwargs):
    base = {
        "version": 1,
        "assets": [],
        "rules": [
            {
                "id": "clr_bridge",
                "blocked": "5",
                "until": ["18"],
                "note": "Keep the bridge closed until the trail crossing is clear",
            }
        ],
    }
    base.update(kwargs)
    return base


def test_pair_and_group_normalize():
    doc = validate_clearance_doc(
        {
            "rules": [
                {
                    "id": "r1",
                    "blocked": "5",
                    "until": ["18", "19"],
                }
            ]
        }
    )
    assert doc["clear_when"] == "last_runner"
    assert doc["rules"][0]["until"][0]["id"] == "18"
    assert doc["rules"][0]["blocked"]["kind"] == "location"
    assert doc["assets"] == []


def test_assets_rejected():
    with pytest.raises(ClearanceValidationError, match="assets are not used"):
        validate_clearance_doc(
            {
                "assets": [{"asset_id": "hold_main", "label": "Main St hold"}],
                "rules": [{"id": "r1", "blocked": "5", "until": ["18"]}],
            }
        )
    with pytest.raises(ClearanceValidationError, match="assets are not used"):
        validate_clearance_doc(
            {"rules": [{"id": "r1", "blocked": "5", "until": ["asset:hold_main"]}]}
        )


def test_cycle_rejected():
    with pytest.raises(ClearanceValidationError, match="cycle"):
        validate_clearance_doc(
            {
                "rules": [
                    {"id": "a", "blocked": "1", "until": ["2"]},
                    {"id": "b", "blocked": "2", "until": ["1"]},
                ]
            }
        )


def test_self_wait_rejected():
    with pytest.raises(ClearanceValidationError, match="itself"):
        validate_clearance_doc({"rules": [{"id": "a", "blocked": "1", "until": ["1"]}]})


def test_unknown_location_rejected_when_known_set():
    with pytest.raises(ClearanceValidationError, match="unknown loc_id"):
        validate_clearance_doc(
            _pair_doc(),
            known_location_ids=["18", "19"],
        )


def test_duplicate_blocked_rejected():
    with pytest.raises(ClearanceValidationError, match="Multiple rules"):
        validate_clearance_doc(
            {
                "rules": [
                    {"id": "a", "blocked": "5", "until": ["18"]},
                    {"id": "b", "blocked": "5", "until": ["19"]},
                ]
            }
        )


def test_playbook_pair_uses_last_runner_at_point():
    doc = validate_clearance_doc(_pair_doc())
    playbook = build_clearance_playbook(
        doc,
        last_runners={"18": ("10:32:00", 10 * 3600 + 32 * 60), "5": ("09:00:00", 9 * 3600)},
        location_labels={"5": "Bridge", "18": "Trail"},
    )
    entry = playbook["entries"][0]
    assert entry["reopen_at"] == "10:32:00"
    assert entry["until"][0]["source"] == "last_runner"
    assert "10:32:00" in entry["explanation"]
    # Blocked location's own last_runner does not change reopen.
    assert entry["reopen_at"] != "09:00:00"


def test_playbook_group_and_is_max():
    doc = validate_clearance_doc(
        {
            "rules": [
                {"id": "g", "blocked": "5", "until": ["18", "19"]},
            ]
        }
    )
    playbook = build_clearance_playbook(
        doc,
        last_runners={
            "18": ("10:32:00", 10 * 3600 + 32 * 60),
            "19": ("10:45:00", 10 * 3600 + 45 * 60),
        },
    )
    assert playbook["entries"][0]["reopen_at"] == "10:45:00"


def test_playbook_location_until_ignores_that_location_reopen():
    """B waits on A; A waits on C. B reopens at A's last_runner, not A's reopen."""
    doc = validate_clearance_doc(
        {
            "rules": [
                {"id": "a_waits_c", "blocked": "1", "until": ["3"]},
                {"id": "b_waits_a", "blocked": "2", "until": ["1"]},
            ]
        }
    )
    playbook = build_clearance_playbook(
        doc,
        last_runners={
            "1": ("09:00:00", 9 * 3600),
            "3": ("11:00:00", 11 * 3600),
        },
    )
    by_id = {e["rule_id"]: e for e in playbook["entries"]}
    assert by_id["a_waits_c"]["reopen_at"] == "11:00:00"
    assert by_id["b_waits_a"]["reopen_at"] == "09:00:00"


def test_playbook_missing_last_runner():
    doc = validate_clearance_doc(_pair_doc())
    playbook = build_clearance_playbook(doc, last_runners={})
    assert playbook["entries"][0]["reopen_at"] is None
    assert playbook["entries"][0]["missing"]


def test_attach_clearance_to_location_rows():
    doc = validate_clearance_doc(_pair_doc())
    playbook = build_clearance_playbook(
        doc, last_runners={"18": ("10:00:00", 10 * 3600)}
    )
    rows = [{"loc_id": 5, "loc_label": "Bridge"}, {"loc_id": 18}]
    attach_clearance_to_locations(rows, playbook)
    assert rows[0]["clearance"]["reopen_at"] == "10:00:00"
    assert rows[1]["clearance"] is None


def test_load_location_last_runners_max_of_rows(tmp_path: Path):
    csv_path = tmp_path / "Locations.csv"
    csv_path.write_text(
        "loc_id,last_runner\n18,10:00:00\n18,10:32:00\n",
        encoding="utf-8",
    )
    times = load_location_last_runners(csv_path)
    assert times["18"][0] == "10:32:00"


def test_save_load_clearance_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    pkg = create_config_package("Clr", "", package_events=["full"])
    cid = pkg["config_id"]
    (tmp_path / cid / "locations.csv").write_text(
        "loc_id,loc_label,zone\n5,Bridge,2\n18,Trail,1\n",
        encoding="utf-8",
    )
    empty = load_config_clearance(cid)
    assert empty["rules"] == []
    save_config_clearance(cid, _pair_doc())
    loaded = load_config_clearance(cid)
    assert loaded["rules"][0]["blocked"]["id"] == "5"
    assert (tmp_path / cid / "clearance.json").is_file()


def test_package_locations_sorted_by_zone_then_id(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    from app.core.clearance.subjects import list_package_locations

    pkg = create_config_package("Clr", "", package_events=["full"])
    cid = pkg["config_id"]
    (tmp_path / cid / "locations.csv").write_text(
        "loc_id,loc_label,zone\n12,Late,2\n5,Bridge,2\n18,Trail,1\n3,Ungrouped,\n",
        encoding="utf-8",
    )
    rows = list_package_locations(cid)
    assert [r["id"] for r in rows] == ["18", "5", "12", "3"]


def test_save_rejects_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    pkg = create_config_package("Clr", "", package_events=["full"])
    cid = pkg["config_id"]
    with pytest.raises(ClearanceValidationError, match="cycle"):
        save_config_clearance(
            cid,
            {
                "rules": [
                    {"id": "a", "blocked": "1", "until": ["2"]},
                    {"id": "b", "blocked": "2", "until": ["1"]},
                ]
            },
        )
