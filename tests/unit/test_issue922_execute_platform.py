"""Issue #922: plan_id identity and purpose-built Execute runtime."""

from __future__ import annotations

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    active_day_context,
    import_published_plan,
    listed_plans,
    validate_manifest,
)
from app.core.execute.participants import load_store, persist_store
from app.core.execute.store_identity import with_plan_id
from app.storage import Storage


def _package(calendar_date: str, weekday_code: str) -> bytes:
    plan_id = str(uuid4())
    locations = {
        "locations": [
            {
                "loc_id": 2,
                "loc_label": "Queen",
                "zone": 1,
                "lat": 45.96,
                "lon": -66.64,
                "loc_end": "08:50:00",
            }
        ],
        "resources_available": [],
    }
    course = {"type": "FeatureCollection", "features": []}
    loc_bytes = json.dumps(locations).encode("utf-8")
    course_bytes = json.dumps(course).encode("utf-8")
    from app.core.execute.published_plan import sha256_bytes

    manifest = {
        "schema_version": 1,
        "plan_id": plan_id,
        "revision": 1,
        "published_at": "2026-10-23T12:00:00+00:00",
        "calendar_date": calendar_date,
        "weekday_code": weekday_code,
        "name": f"Test {calendar_date}",
        "timezone": "America/Halifax",
        "source_run_id": "should-not-be-operator-key",
        "races": [
            {
                "id": "elite",
                "name": "5K Elite",
                "course": "courses/elite.geojson",
            }
        ],
        "files": [
            {"path": "locations.json", "sha256": sha256_bytes(loc_bytes)},
            {
                "path": "courses/elite.geojson",
                "sha256": sha256_bytes(course_bytes),
            },
        ],
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("locations.json", loc_bytes)
        zf.writestr("courses/elite.geojson", course_bytes)
    return buffer.getvalue()


def test_import_rejects_published_plan_id_alias():
    with pytest.raises(PublishedPlanError, match="plan_id"):
        validate_manifest(
            {
                "schema_version": 1,
                "published_plan_id": str(uuid4()),
                "revision": 1,
                "calendar_date": "2026-10-24",
                "races": [{"id": "elite"}],
                "files": [{"path": "x", "sha256": "a"}],
            }
        )


def test_leftover_registry_exposes_plan_id(tmp_path: Path):
    leftover_id = str(uuid4())
    leftover = tmp_path / "execute" / "published_plans"
    leftover.mkdir(parents=True)
    (leftover / "registry.json").write_text(
        json.dumps(
            {
                "active_published_plan_id": leftover_id,
                "plans": {
                    leftover_id: {
                        "published_plan_id": leftover_id,
                        "revision": 1,
                        "calendar_date": "2026-10-24",
                        "weekday_code": "sat",
                        "name": "Leftover",
                        "archived": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    listing = listed_plans(root=tmp_path)
    assert listing["active_plan_id"] == leftover_id
    assert listing["plans"][0]["plan_id"] == leftover_id
    assert "published_plan_id" not in listing["plans"][0]
    assert (tmp_path / "execute" / "plans").is_dir()
    assert not (tmp_path / "execute" / "published_plans").exists()
    saved = json.loads(
        (tmp_path / "execute" / "plans" / "registry.json").read_text(
            encoding="utf-8"
        )
    )
    assert "active_published_plan_id" not in saved
    assert leftover_id in saved["plans"]
    assert "published_plan_id" not in saved["plans"][leftover_id]
    assert saved["plans"][leftover_id]["plan_id"] == leftover_id


def test_active_context_uses_plan_id_not_run_id(tmp_path: Path, monkeypatch):
    from app.utils import run_id as run_id_mod

    monkeypatch.setattr(run_id_mod, "get_runflow_root", lambda: tmp_path)
    archive = _package("2026-10-24", "sat")
    plan_id = import_published_plan(archive, root=tmp_path)["plan_id"]
    activate_published_plan(plan_id, root=tmp_path)
    ctx = active_day_context(root=tmp_path)
    assert ctx["active"] is True
    assert ctx["plan_id"] == plan_id
    assert ctx["calendar_date"] == "2026-10-24"
    assert "run_id" not in ctx
    listing = listed_plans(root=tmp_path)
    assert listing["active_plan_id"] == plan_id
    assert listing["plans"][0]["plan_id"] == plan_id


def test_participants_store_lives_under_imported_plan(tmp_path: Path):
    archive = _package("2026-10-24", "sat")
    plan_id = import_published_plan(archive, root=tmp_path)["plan_id"]
    activate_published_plan(plan_id, root=tmp_path)
    dest = tmp_path / "execute" / "plans" / plan_id / "r1"
    storage = Storage(root=str(dest))
    persist_store(
        storage,
        "sat",
        {"schema_version": 1, "run_id": plan_id, "day": "sat", "rows": []},
    )
    loaded = load_store(storage, run_id=plan_id, day="sat")
    normalized = with_plan_id(loaded, plan_id)
    assert normalized["plan_id"] == plan_id
    assert "run_id" not in normalized
    assert (dest / "sat" / "execution" / "participants.json").is_file()
    assert not (tmp_path / "analysis").exists()


def _route_paths(routes) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
        nested = getattr(route, "routes", None)
        if nested:
            paths.update(_route_paths(nested))
        original = getattr(route, "original_router", None)
        if original is not None and hasattr(original, "routes"):
            paths.update(_route_paths(original.routes))
    return paths


def test_execute_app_is_not_main_and_omits_analysis_routes():
    from app.execute_app import app as execute_app

    paths = _route_paths(execute_app.routes)
    assert "/execute" in paths
    assert "/execute/plans" in paths
    assert "/execute/help" in paths
    assert "/locsheets/{plan_id}/{loc_id}" in paths
    assert "/api/execute/plans/{plan_id}/locsheets" in paths
    assert "/ready" in paths
    assert "/api/auth/check" in paths
    assert "/api/execute/gps/osmand" in paths
    assert "/api/execute/gps/overlay" in paths
    assert "/density" not in paths
    assert "/overview" not in paths
    assert "/config" not in paths
    assert "/runflow/v2/analyze" not in paths
    assert "/api/plan/plans" not in paths
    assert "/api/execute/board" not in paths
    client = TestClient(execute_app)
    assert client.get("/ready").status_code == 200
    assert client.get("/density").status_code == 404
    assert client.get("/api/plan/plans").status_code == 404
    # Fresh interpreter: other tests may have imported app.main already.
    import subprocess

    probe = (
        "import sys; import app.execute_app; "
        "assert 'app.core.density.compute' not in sys.modules; "
        "assert 'app.routes.v2.analyze' not in sys.modules; "
        "assert 'app.main' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_execute_dockerfile_is_not_app_main():
    root = Path(__file__).resolve().parents[2]
    dockerfile = root / "Dockerfile.execute"
    if not dockerfile.is_file():
        pytest.skip("Dockerfile.execute not mounted")
    text = dockerfile.read_text(encoding="utf-8")
    assert "app.execute_app:app" in text
    assert "app.main:app" not in text
    assert "execute_constants.py" in text
    assert "COPY app /app/app" not in text
    assert "COPY frontend /app/frontend" not in text
    assert "app/core/density" not in text
    assert "app/main.py" not in text
    assert "pages/overview.html" not in text
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "Dockerfile.execute" in compose
    assert "postgres:15" in compose
    assert "execute-db" in compose
    assert "container_name: runflow-execute" in compose
    assert "execute-runtime-data:/app/runflow" in compose
