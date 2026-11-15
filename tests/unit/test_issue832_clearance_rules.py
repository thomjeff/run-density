"""Issue #832: clearance rules validation, cycles, static playbook."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.clearance.playbook import build_static_playbook
from app.core.config_package.clearance_rules import (
    detect_cycles,
    empty_clearance_doc,
    load_config_clearance_rules,
    save_config_clearance_rules,
    validate_clearance_doc,
)
from app.core.config_package.storage import create_config_package, save_config_course
from app.main import app


def test_validate_pair_and_group_and():
    doc = validate_clearance_doc(
        {
            "assets": [{"asset_id": "aid_tent", "label": "Aid tent", "loc_id": "16"}],
            "rules": [
                {"id": "r1", "blocked": "20", "until": ["12"]},
                {"id": "r2", "blocked": "aid_tent", "until": ["12", "16"]},
            ],
        },
        known_loc_ids={"12", "16", "20"},
    )
    assert len(doc["rules"]) == 2
    assert doc["rules"][1]["until"] == ["12", "16"]
    assert doc["rules"][0]["clear_when"] == "last_runner"


def test_cycles_rejected():
    with pytest.raises(ValueError, match="cycle"):
        validate_clearance_doc(
            {
                "rules": [
                    {"blocked": "1", "until": ["2"]},
                    {"blocked": "2", "until": ["1"]},
                ]
            },
            known_loc_ids={"1", "2"},
        )
    path = detect_cycles(
        [
            {"blocked": "a", "until": ["b"]},
            {"blocked": "b", "until": ["c"]},
            {"blocked": "c", "until": ["a"]},
        ]
    )
    assert path is not None
    assert "a" in path


def test_self_dependency_rejected():
    with pytest.raises(ValueError, match="itself"):
        validate_clearance_doc(
            {"rules": [{"blocked": "5", "until": ["5"]}]},
            known_loc_ids={"5"},
        )


def test_playbook_uses_max_last_runner():
    playbook = build_static_playbook(
        {
            "assets": [],
            "rules": [
                {
                    "id": "r1",
                    "blocked": "20",
                    "until": ["12", "16"],
                    "clear_when": "last_runner",
                }
            ],
        },
        [
            {"loc_id": 12, "last_runner": "10:00:00"},
            {"loc_id": 16, "last_runner": "10:15:30"},
            {"loc_id": 20, "last_runner": "09:00:00"},
        ],
    )
    step = playbook["steps"][0]
    assert step["reopen_not_before"] == "10:15:30"
    assert step["ready"] is True
    assert "12" in step["explanation"]


def test_playbook_missing_timing():
    playbook = build_static_playbook(
        {
            "assets": [],
            "rules": [
                {"blocked": "20", "until": ["12", "99"], "clear_when": "last_runner"}
            ],
        },
        [{"loc_id": 12, "last_runner": "10:00:00"}],
    )
    assert playbook["steps"][0]["reopen_not_before"] is None
    assert playbook["steps"][0]["ready"] is False


@pytest.fixture
def package_root(tmp_path, monkeypatch):
    root = tmp_path / "runflow"
    root.mkdir()
    monkeypatch.setenv("RUNFLOW_ROOT", str(root))
    monkeypatch.setattr("app.utils.run_id.get_runflow_root", lambda: root)
    monkeypatch.setattr(
        "app.core.config_package.storage.get_runflow_root", lambda: root
    )
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: root / "config",
    )
    return root


def test_save_load_clearance_api(package_root):
    created = create_config_package(
        "Clearance Pkg",
        event_day="sat",
        package_events=["10k"],
    )
    cid = created["config_id"]
    course = created.get("course") or {}
    # ensure known location ids exist on course
    course = {
        "name": "Clearance Pkg",
        "locations": [
            {"id": 12, "loc_label": "A", "lat": 1.0, "lon": 2.0, "loc_type": "water"},
            {"id": 16, "loc_label": "B", "lat": 1.1, "lon": 2.1, "loc_type": "aid"},
        ],
        "segments": [],
    }
    save_config_course(cid, course)

    client = TestClient(app)
    empty = client.get(f"/api/config/packages/{cid}/clearance-rules")
    assert empty.status_code == 200
    assert empty.json()["rules"] == []

    saved = client.put(
        f"/api/config/packages/{cid}/clearance-rules",
        json={
            "rules": [
                {
                    "id": "r1",
                    "blocked": "16",
                    "until": ["12"],
                    "clear_when": "last_runner",
                }
            ],
            "assets": [],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["rules"][0]["blocked"] == "16"

    loaded = load_config_clearance_rules(cid)
    assert loaded["rules"][0]["until"] == ["12"]

    cycle = client.put(
        f"/api/config/packages/{cid}/clearance-rules",
        json={
            "rules": [
                {"blocked": "12", "until": ["16"]},
                {"blocked": "16", "until": ["12"]},
            ],
            "assets": [],
        },
    )
    assert cycle.status_code == 400
    assert "cycle" in cycle.json()["detail"].lower()

    playbook = client.get(
        f"/api/config/packages/{cid}/clearance/playbook",
        params={"run_id": "missingrun", "day": "sat"},
    )
    assert playbook.status_code == 200
    assert playbook.json()["report_found"] is False
    assert playbook.json()["rule_count"] == 1


def test_empty_doc_shape():
    doc = empty_clearance_doc()
    assert doc["rules"] == []
    assert doc["assets"] == []
