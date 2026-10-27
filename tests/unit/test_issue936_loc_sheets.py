"""Issue #936: volunteer location sheets on Execute."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    archive_published_plan,
    import_published_plan,
    list_plan_loc_sheets,
    loc_sheet_token,
    resolve_public_loc_sheet,
    restore_published_plan,
    sha256_bytes,
)
from app.core.plan.publish_day_plan import build_published_plan_files
from app.execute_app import app

SHEET_HTML = b"<html><body>Queen volunteer sheet</body></html>"


def _zip_from_files(files: dict) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, payload in files.items():
            if isinstance(payload, dict):
                payload = json.dumps(payload).encode("utf-8")
            zf.writestr(name, payload)
    return buffer.getvalue()


def _package(
    *,
    calendar_date: str = "2026-10-24",
    weekday_code: str = "sat",
    plan_id: str | None = None,
    with_sheet: bool = True,
) -> bytes:
    plan_id = plan_id or str(uuid4())
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
    course = {
        "type": "FeatureCollection",
        "features": [],
    }
    loc_bytes = json.dumps(locations).encode("utf-8")
    course_bytes = json.dumps(course).encode("utf-8")
    files_meta = [
        {"path": "locations.json", "sha256": sha256_bytes(loc_bytes)},
        {
            "path": "courses/elite.geojson",
            "sha256": sha256_bytes(course_bytes),
        },
    ]
    packed = {
        "manifest.json": {
            "schema_version": 1,
            "plan_id": plan_id,
            "revision": 1,
            "published_at": "2026-10-22T12:00:00+00:00",
            "calendar_date": calendar_date,
            "weekday_code": weekday_code,
            "name": f"Test {calendar_date}",
            "timezone": "America/Halifax",
            "source_run_id": "srcRun936",
            "races": [
                {
                    "id": "elite",
                    "name": "5K Elite",
                    "start_time": 480,
                    "course": "courses/elite.geojson",
                }
            ],
            "files": files_meta,
        },
        "locations.json": loc_bytes,
        "courses/elite.geojson": course_bytes,
    }
    if with_sheet:
        files_meta.append(
            {
                "path": "loc_sheets/2.html",
                "sha256": sha256_bytes(SHEET_HTML),
            }
        )
        packed["loc_sheets/2.html"] = SHEET_HTML
    return _zip_from_files(packed)


def _write_publish_tree(tmp_path: Path, run_id: str = "srcRun936") -> Path:
    run_dir = tmp_path / "analysis" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "analysis.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "name": "elite",
                        "day": "sat",
                        "start_time": 480,
                        "event_duration_minutes": 30,
                    }
                ],
                "config_id": "cfg",
            }
        ),
        encoding="utf-8",
    )
    loc_dir = run_dir / "sat" / "computation"
    loc_dir.mkdir(parents=True)
    (loc_dir / "locations_report.json").write_text(
        json.dumps(
            {
                "locations": [
                    {
                        "loc_id": 2,
                        "loc_label": "Queen",
                        "onepage": "y",
                        "zone": 1,
                        "lat": 45.96,
                        "lon": -66.64,
                        "loc_end": "08:50:00",
                    },
                    {
                        "loc_id": 3,
                        "loc_label": "Skip",
                        "onepage": "n",
                    },
                    {
                        "loc_id": 4,
                        "loc_label": "Report none",
                        "onepage": "none",
                    },
                ],
                "resources_available": [],
            }
        ),
        encoding="utf-8",
    )
    html_dir = run_dir / "sat" / "reports" / "loc_sheets" / "html"
    html_dir.mkdir(parents=True)
    (html_dir / "2.html").write_bytes(SHEET_HTML)
    (html_dir / "3.html").write_text("<html>do not pack</html>", encoding="utf-8")
    (html_dir / "4.html").write_text("<html>report none</html>", encoding="utf-8")
    return run_dir


def test_loc_sheet_token_rejects_path_traversal():
    with pytest.raises(PublishedPlanError, match="not found"):
        loc_sheet_token("../etc/passwd")
    with pytest.raises(PublishedPlanError, match="not found"):
        loc_sheet_token("2.html")
    assert loc_sheet_token(2) == "2"


def test_publish_packs_onepage_html_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_publish_tree(tmp_path)
    monkeypatch.setattr("app.utils.run_id.get_runflow_root", lambda: tmp_path)
    files = build_published_plan_files(
        run_id="srcRun936",
        day="sat",
        calendar_date="2026-10-24",
        name="EOC Sat",
    )
    assert files["loc_sheets/2.html"] == SHEET_HTML
    assert files["loc_sheets/4.html"] == b"<html>report none</html>"
    assert "loc_sheets/3.html" not in files
    manifest = json.loads(files["manifest.json"].decode("utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    assert "loc_sheets/2.html" in paths
    assert "loc_sheets/4.html" in paths
    assert "loc_sheets/3.html" not in paths
    checksum = next(
        item["sha256"]
        for item in manifest["files"]
        if item["path"] == "loc_sheets/2.html"
    )
    assert checksum == sha256_bytes(SHEET_HTML)


def test_import_serves_sheet_without_activating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    archive = _package()
    plan_id = import_published_plan(archive, root=tmp_path)["plan_id"]
    path = resolve_public_loc_sheet(plan_id, "2", root=tmp_path)
    assert path.is_file()
    assert path.read_bytes() == SHEET_HTML
    listing = list_plan_loc_sheets(plan_id, root=tmp_path)
    assert listing["archived"] is False
    assert listing["sheets"] == [
        {
            "loc_id": "2",
            "loc_label": "Queen",
            "path": f"/locsheets/{plan_id}/2",
        }
    ]


def test_archive_404_restore_serves_again(tmp_path: Path):
    archive = _package()
    plan_id = import_published_plan(archive, root=tmp_path)["plan_id"]
    archive_published_plan(plan_id, root=tmp_path)
    with pytest.raises(PublishedPlanError, match="not found"):
        resolve_public_loc_sheet(plan_id, "2", root=tmp_path)
    assert list_plan_loc_sheets(plan_id, root=tmp_path)["sheets"] == []
    restore_published_plan(plan_id, root=tmp_path)
    path = resolve_public_loc_sheet(plan_id, "2", root=tmp_path)
    assert path.read_bytes() == SHEET_HTML


def test_sheet_is_independent_of_active_plan(tmp_path: Path):
    first = _package()
    second = _package(calendar_date="2026-10-25", weekday_code="sun")
    first_id = import_published_plan(first, root=tmp_path)["plan_id"]
    second_id = import_published_plan(second, root=tmp_path)["plan_id"]
    activate_published_plan(second_id, root=tmp_path)
    path = resolve_public_loc_sheet(first_id, "2", root=tmp_path)
    assert path.read_bytes() == SHEET_HTML


def test_missing_html_or_unknown_loc_404s(tmp_path: Path):
    archive = _package(with_sheet=False)
    plan_id = import_published_plan(archive, root=tmp_path)["plan_id"]
    with pytest.raises(PublishedPlanError, match="not found"):
        resolve_public_loc_sheet(plan_id, "2", root=tmp_path)
    other = import_published_plan(_package(), root=tmp_path)["plan_id"]
    dest = tmp_path / "execute" / "plans" / other / "r1" / "loc_sheets"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "9.html").write_text("<html>orphan</html>", encoding="utf-8")
    with pytest.raises(PublishedPlanError, match="not found"):
        resolve_public_loc_sheet(other, "9", root=tmp_path)
    resolve_public_loc_sheet(other, "2", root=tmp_path)


def test_http_public_get_and_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    client = TestClient(app)
    archive = _package()
    imported = client.post(
        "/api/execute/plans/import",
        files={"package": ("sat.zip", archive, "application/zip")},
    )
    assert imported.status_code == 200
    plan_id = imported.json()["plan_id"]
    public = client.get(f"/locsheets/{plan_id}/2")
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("text/html")
    assert public.content == SHEET_HTML
    index = client.get(f"/api/execute/plans/{plan_id}/locsheets")
    assert index.status_code == 200
    body = index.json()
    assert body["ok"] is True
    assert body["sheets"][0]["path"] == f"/locsheets/{plan_id}/2"
    client.post("/api/execute/plans/archive", json={"plan_id": plan_id})
    assert client.get(f"/locsheets/{plan_id}/2").status_code == 404
    assert client.get(f"/api/execute/plans/{plan_id}/locsheets").json()[
        "sheets"
    ] == []
    client.post("/api/execute/plans/restore", json={"plan_id": plan_id})
    assert client.get(f"/locsheets/{plan_id}/2").status_code == 200
    assert client.get(f"/locsheets/{plan_id}/../2").status_code == 404
    assert client.get("/locsheets/not-a-uuid/2").status_code == 404
