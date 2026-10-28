"""Issue #942: drop leftover {day} from Create loc-sheet public URLs."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.cloud_middleware import _is_public_locsheet_path
from app.execute_app import app as execute_app
from app.main import app as create_app
from app.utils.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TIMESTAMP_COOKIE_NAME,
    SESSION_VALUE,
)
from app.utils.loc_sheets_list import loc_sheet_html_path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHEET_HTML = "<html><body>Create loc sheet 942</body></html>"
RUN_ID = "testRun942LocSheetXXXXXX"


def _write_sheet(tmp_path: Path, *, day: str = "sun", loc_id: str = "2") -> Path:
    html_dir = tmp_path / "analysis" / RUN_ID / day / "reports" / "loc_sheets" / "html"
    html_dir.mkdir(parents=True)
    path = html_dir / f"{loc_id}.html"
    path.write_text(SHEET_HTML, encoding="utf-8")
    comp_dir = tmp_path / "analysis" / RUN_ID / day / "computation"
    comp_dir.mkdir(parents=True)
    (comp_dir / "locations_results.json").write_text(
        json.dumps(
            {
                "locations": [
                    {"loc_id": loc_id, "loc_label": "Water Stop", "onepage": "y"}
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _create_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr("app.utils.run_id.get_runflow_root", lambda: tmp_path)
    return TestClient(create_app)


def _authed(client: TestClient) -> TestClient:
    client.cookies.set(SESSION_COOKIE_NAME, SESSION_VALUE)
    client.cookies.set(SESSION_TIMESTAMP_COOKIE_NAME, str(time.time()))
    return client


def _collect_paths(routes) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path is not None:
            paths.add(path)
        original = getattr(route, "original_router", None)
        if original is not None and hasattr(original, "routes"):
            paths.update(_collect_paths(original.routes))
        nested = getattr(route, "routes", None)
        if nested:
            paths.update(_collect_paths(nested))
    return paths


def test_create_public_url_has_no_day_and_reads_disk_day_folder(
    tmp_path: Path, monkeypatch
):
    disk_path = _write_sheet(tmp_path)
    assert "/sun/reports/loc_sheets/html/2.html" in str(disk_path)
    client = _create_client(tmp_path, monkeypatch)

    response = client.get(f"/locsheets/{RUN_ID}/2")
    assert response.status_code == 200
    assert "Create loc sheet 942" in response.text
    assert "/sun/" not in str(response.url)


def test_create_derives_day_from_run(tmp_path: Path, monkeypatch):
    _write_sheet(tmp_path, day="sat")
    client = _create_client(tmp_path, monkeypatch)

    assert client.get(f"/locsheets/{RUN_ID}/2").status_code == 200
    assert client.get(f"/locsheets/{RUN_ID}/missing").status_code == 404


def test_legacy_create_three_segment_redirects(tmp_path: Path, monkeypatch):
    _write_sheet(tmp_path)
    client = _create_client(tmp_path, monkeypatch)

    response = client.get(f"/locsheets/{RUN_ID}/sun/2", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == f"/locsheets/{RUN_ID}/2"

    followed = client.get(f"/locsheets/{RUN_ID}/sun/2", follow_redirects=True)
    assert followed.status_code == 200
    assert "Create loc sheet 942" in followed.text


def test_create_index_drops_day_query(tmp_path: Path, monkeypatch):
    _write_sheet(tmp_path)
    client = _authed(_create_client(tmp_path, monkeypatch))

    response = client.get(f"/locsheets?run_id={RUN_ID}&day=sun", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/locsheets?run_id={RUN_ID}"

    canonical = client.get(f"/locsheets?run_id={RUN_ID}", follow_redirects=False)
    assert canonical.status_code == 200
    assert f"/locsheets/{RUN_ID}/2" in canonical.text
    assert f"/locsheets/{RUN_ID}/sun/2" not in canonical.text
    assert "Use the day selector" not in canonical.text


def test_create_route_table_and_execute_urls_unchanged():
    create_paths = _collect_paths(create_app.routes)
    assert "/locsheets/{run_id}/{loc_id}" in create_paths
    assert "/locsheets/{run_id}/{day}/{loc_id}" in create_paths

    execute_paths = _collect_paths(execute_app.routes)
    assert "/locsheets/{plan_id}/{loc_id}" in execute_paths
    assert "/locsheets/{run_id}/{loc_id}" not in execute_paths
    assert "/locsheets/{run_id}/{day}/{loc_id}" not in execute_paths


def test_locations_and_base_skip_create_two_segment_urls():
    locations = (
        REPO_ROOT / "frontend" / "templates" / "pages" / "locations.html"
    ).read_text(encoding="utf-8")
    assert (
        "path = `/locsheets/${encodeURIComponent(run_id)}/${encodeURIComponent(lid)}`;"
        in locations
    )
    assert (
        "`/locsheets/${encodeURIComponent(run_id)}/${encodeURIComponent(day)}/${encodeURIComponent(lid)}`"
        not in locations
    )
    # Cloud short weekday URLs stay
    assert (
        "path = `/locsheets/${encodeURIComponent(day)}/${encodeURIComponent(lid)}`;"
        in locations
    )

    base = (REPO_ROOT / "frontend" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )
    assert "/^\\/locsheets\\/[^/]+\\/[^/]+(?:\\/[^/]+)?$/" in base


def test_disk_helper_keeps_day_folder(tmp_path: Path):
    run_dir = tmp_path / "analysis" / RUN_ID
    path = loc_sheet_html_path(run_dir, "sun", "2")
    assert path == run_dir / "sun" / "reports" / "loc_sheets" / "html" / "2.html"


def test_cloud_middleware_allows_two_segment_and_legacy(monkeypatch):
    monkeypatch.setenv("PUBLIC_LOCSHEETS", "true")
    assert _is_public_locsheet_path(f"/locsheets/{RUN_ID}/2", "GET") is True
    assert _is_public_locsheet_path("/locsheets/sun/2", "GET") is True
    assert _is_public_locsheet_path(f"/locsheets/{RUN_ID}/sun/2", "GET") is True
    assert _is_public_locsheet_path("/locsheets", "GET") is False
    monkeypatch.setenv("PUBLIC_LOCSHEETS", "false")
    assert _is_public_locsheet_path(f"/locsheets/{RUN_ID}/2", "GET") is False


def test_dockerfile_cloud_stays():
    assert (REPO_ROOT / "Dockerfile.cloud").is_file()
    text = (REPO_ROOT / "Dockerfile.cloud").read_text(encoding="utf-8")
    assert "app.cloud_app:app" in text
