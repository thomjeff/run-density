"""
Issue #798 Phase 4: path settings / host↔container mapping.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.utils import path_mapper as pm


@pytest.fixture(autouse=True)
def _clear_path_env(monkeypatch):
    for key in ("RUNFLOW_ROOT", "RUNFLOW_ROOT_HOST", "RUNFLOW_ROOT_CONTAINER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RUNFLOW_ROOT_CONTAINER", "/app/runflow")


def test_defaults_have_no_users_home_literal():
    assert "/Users/" not in pm.DEFAULT_RUNFLOW_ROOT
    assert pm.DEFAULT_RUNFLOW_ROOT_CONTAINER == "/app/runflow"


def test_to_runtime_path_rewrites_host_prefix(monkeypatch, tmp_path):
    host = tmp_path / "host-runflow"
    host.mkdir()
    monkeypatch.setenv("RUNFLOW_ROOT_HOST", str(host))
    monkeypatch.setenv("RUNFLOW_ROOT_CONTAINER", "/app/runflow")
    monkeypatch.setattr(pm, "is_container_runtime", lambda: True)

    src = str(host / "analysis" / "abc")
    assert pm.to_runtime_path(src) == "/app/runflow/analysis/abc"


def test_to_runtime_path_noop_for_relative_and_unrelated(monkeypatch):
    monkeypatch.setenv("RUNFLOW_ROOT_HOST", "/Users/example/Documents/runflow")
    monkeypatch.setattr(pm, "is_container_runtime", lambda: True)

    assert pm.to_runtime_path("data") == "data"
    assert pm.to_runtime_path("/tmp/other") == "/tmp/other"
    assert pm.to_runtime_path("/app/runflow/analysis/x") == "/app/runflow/analysis/x"
    assert pm.to_runtime_path("") == ""
    assert pm.to_runtime_path(None) == ""


def test_to_runtime_path_noop_outside_container(monkeypatch, tmp_path):
    host = tmp_path / "host-runflow"
    monkeypatch.setenv("RUNFLOW_ROOT_HOST", str(host))
    monkeypatch.setattr(pm, "is_container_runtime", lambda: False)
    assert pm.to_runtime_path(str(host / "x")) == str(host / "x")


def test_resolve_runflow_root_prefers_existing_container(monkeypatch, tmp_path):
    container = tmp_path / "container-runflow"
    container.mkdir()
    host = tmp_path / "host-runflow"
    host.mkdir()
    monkeypatch.setenv("RUNFLOW_ROOT_CONTAINER", str(container))
    monkeypatch.setenv("RUNFLOW_ROOT", str(host))
    assert pm.resolve_runflow_root() == container


def test_resolve_runflow_root_falls_back_to_host(monkeypatch, tmp_path):
    missing = tmp_path / "missing-container"
    host = tmp_path / "host-runflow"
    host.mkdir()
    monkeypatch.setenv("RUNFLOW_ROOT_CONTAINER", str(missing))
    monkeypatch.setenv("RUNFLOW_ROOT", str(host))
    assert pm.resolve_runflow_root() == host


def test_no_users_jthompson_in_runtime_sources():
    """Guard: app/, scripts/, compose, Makefile must not embed the personal host path."""
    root = Path(__file__).resolve().parents[2]
    needles = ("/Users/jthompson",)
    scan_paths = [
        root / "app",
        root / "scripts",
        root / "docker-compose.yml",
        root / "Makefile",
        root / "dev.env",
    ]
    offenders = []
    for path in scan_paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in needles:
                if needle in text:
                    offenders.append(str(path.relative_to(root)))
        else:
            for file in path.rglob("*"):
                if not file.is_file():
                    continue
                if file.suffix not in {".py", ".yml", ".yaml", ".md", ".env", ".txt", ""} and file.name not in {
                    "Makefile",
                    "docker-compose.yml",
                }:
                    if file.suffix not in {".py", ".yml", ".yaml"}:
                        continue
                text = file.read_text(encoding="utf-8", errors="ignore")
                for needle in needles:
                    if needle in text:
                        offenders.append(str(file.relative_to(root)))
    assert not offenders, f"Personal host path still present in: {offenders}"
