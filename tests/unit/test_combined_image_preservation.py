"""Regression guards for the Create image (Build + Plan).

Create is Dockerfile / app.main. Execute is a separate image. These tests fail
if Create loses Build/Plan or still mounts Execute operator routes (#938).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _repo_root() -> Path:
    env = os.environ.get("RUNFLOW_REPO_ROOT")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parents[2])
    candidates.append(Path.cwd())
    for candidate in candidates:
        if (candidate / "Dockerfile").is_file():
            return candidate
    pytest.skip("Dockerfile not mounted; file-contract checks need RUNFLOW_REPO_ROOT")


CRITICAL_PATHS = (
    "/health",
    "/ready",
    "/dashboard",
    "/overview",
    "/density",
    "/flow",
    "/junctions",
    "/motion",
    "/progression",
    "/locations",
    "/course-mapping",
)

EXECUTE_GONE_PATHS = (
    "/execute",
    "/execute/map",
    "/execute/plans",
    "/execute/participants",
    "/execute/incidents",
)


def _collect_route_paths(routes: Iterable) -> List[str]:
    paths: List[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if path is not None:
            paths.append(path)
        original = getattr(route, "original_router", None)
        if original is not None and hasattr(original, "routes"):
            paths.extend(_collect_route_paths(original.routes))
        nested = getattr(route, "routes", None)
        if nested:
            paths.extend(_collect_route_paths(nested))
    return paths


def test_combined_dockerfile_keeps_app_main_entrypoint():
    text = (_repo_root() / "Dockerfile").read_text(encoding="utf-8")
    assert "app.main:app" in text
    assert "gunicorn" in text
    assert "app.cloud_app:app" not in text


def test_cloud_dockerfile_stays_separate_skinny_entry():
    text = (_repo_root() / "Dockerfile.cloud").read_text(encoding="utf-8")
    assert "app.cloud_app:app" in text
    assert "app.main:app" not in text


def test_compose_still_builds_combined_image():
    text = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")
    assert "dockerfile: Dockerfile" in text
    assert "app.main:app" in text
    assert "container_name: runflow-create" in text
    assert "run-density-dev" not in text
    assert "sqlalchemy" not in text.lower()


def test_combined_requirements_have_no_database_runtime():
    candidates = [
        Path("/app/requirements.txt"),
        Path(__file__).resolve().parents[2] / "requirements.txt",
        Path.cwd() / "requirements.txt",
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        pytest.skip("requirements.txt not available")
    text = path.read_text(encoding="utf-8").lower()
    assert "sqlalchemy" not in text
    assert "psycopg" not in text
    assert "asyncpg" not in text


def test_app_registers_build_plan_not_execute_routes():
    paths = set(_collect_route_paths(app.routes))
    missing = [path for path in CRITICAL_PATHS if path not in paths]
    assert missing == [], f"Missing Create routes: {missing}"
    assert "/api/plan/plans" in paths
    assert "/api/execute/ops/board" not in paths
    assert "/api/execute/board" not in paths
    leftover = [path for path in EXECUTE_GONE_PATHS if path in paths]
    assert leftover == [], f"Create still mounts Execute routes: {leftover}"


def test_critical_routes_respond_without_500():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json().get("ok") is True

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json().get("ok") is True

    login = client.get("/", follow_redirects=False)
    assert login.status_code == 200

    for path in CRITICAL_PATHS:
        if path in {"/health", "/ready"}:
            continue
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (200, 302, 303), (
            f"{path} returned {response.status_code}"
        )

    for path in EXECUTE_GONE_PATHS:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 404, (
            f"{path} returned {response.status_code}, expected 404 on Create"
        )
