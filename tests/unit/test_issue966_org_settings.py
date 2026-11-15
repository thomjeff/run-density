"""Issue #966: org Settings SSOT, package seed, Day Plan–scoped incident agencies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config_package.org_settings import (
    default_org_settings,
    load_org_settings,
    org_resource_codes,
    save_org_settings,
)
from app.core.config_package.storage import create_config_package
from app.core.execute.incidents import catalog
from app.main import app


@pytest.fixture
def org_root(tmp_path, monkeypatch):
    root = tmp_path / "runflow"
    root.mkdir()
    monkeypatch.setenv("RUNFLOW_ROOT", str(root))
    monkeypatch.setattr("app.utils.run_id.get_runflow_root", lambda: root)
    monkeypatch.setattr(
        "app.core.config_package.org_settings.get_runflow_root", lambda: root
    )
    monkeypatch.setattr(
        "app.core.config_package.storage.get_runflow_root", lambda: root
    )
    return root


def test_default_settings_include_quad_resources():
    settings = default_org_settings()
    codes = [r["code"] for r in settings["resources"]]
    assert codes == ["fpf", "yssr", "awp", "vol"]
    assert settings["display_timezone"]


def test_load_save_org_settings(org_root):
    assert not (org_root / "org" / "settings.json").is_file()
    loaded = load_org_settings()
    assert [r["code"] for r in loaded["resources"]] == ["fpf", "yssr", "awp", "vol"]

    saved = save_org_settings(
        {
            "resources": [
                {"code": "fpf", "label": "FPF"},
                {"code": "yssr", "label": "YSSR"},
                {"code": "ofc", "label": "Officials"},
            ],
            "display_timezone": "America/Toronto",
        }
    )
    path = org_root / "org" / "settings.json"
    assert path.is_file()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert [r["code"] for r in on_disk["resources"]] == ["fpf", "yssr", "ofc"]
    assert saved["display_timezone"] == "America/Toronto"
    assert org_resource_codes() == ["fpf", "yssr", "ofc"]


def test_create_package_seeds_from_org_settings(org_root, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: org_root / "config",
    )
    save_org_settings(
        {
            "resources": [
                {"code": "fpf", "label": "FPF"},
                {"code": "vol", "label": "VOL"},
            ]
        }
    )
    result = create_config_package(
        "Seed Test",
        event_day="sat",
        package_events=["10k"],
    )
    assert [r["code"] for r in result["manifest"]["resources"]] == ["fpf", "vol"]


def test_org_settings_api(org_root):
    client = TestClient(app)
    listed = client.get("/api/org/settings")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["ok"] is True
    assert "resources" in body["settings"]

    patched = client.patch(
        "/api/org/settings",
        json={
            "resources": [
                {"code": "fpf", "label": "FPF"},
                {"code": "awp", "label": "AWP"},
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    codes = [r["code"] for r in patched.json()["settings"]["resources"]]
    assert codes == ["fpf", "awp"]


def test_incident_catalog_filters_by_day_plan_resources():
    full = catalog()
    full_reporter_ids = {item["id"] for item in full["reporter_agencies"]}
    assert "awp" in full_reporter_ids
    assert "participant" in full_reporter_ids

    sat = catalog(resources_available=["fpf", "yssr", "vol"])
    sat_ids = {item["id"] for item in sat["reporter_agencies"]}
    assert "awp" not in sat_ids
    assert "fpf" in sat_ids
    assert "yssr" in sat_ids
    assert "participant" in sat_ids
    assert "spectator" in sat_ids

    agencies = {item["id"] for item in sat["agencies"]}
    assert "fpf" in agencies
    assert "yssr" in agencies
    # Care partners that are not org resource codes remain available.
    assert "sja" in agencies
    assert "anb" in agencies


def test_build_nav_includes_settings():
    base = Path(__file__).resolve().parents[2] / "frontend" / "templates" / "base.html"
    text = base.read_text(encoding="utf-8")
    packages = text.find('data-rf-build-view="packages"')
    settings = text.find('data-rf-build-view="settings"')
    assert packages != -1 and settings != -1
    assert packages < settings


def test_package_modals_are_assemble_only():
    page = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "templates"
        / "pages"
        / "race_configuration.html"
    )
    text = page.read_text(encoding="utf-8")
    assert "race-config-new-resources-list" not in text
    assert "race-config-edit-resources-list" not in text
    assert 'id="race-config-hub-settings"' in text
    assert "Packages assemble courses and runners only" in text
