"""Unit tests for config package segments.csv export (Issue #758)."""

import csv
import io
from pathlib import Path

import pytest

from app.core.config_package.storage import export_config_package_segments
from app.core.course.export import build_segments_csv
from app.io.loader import load_segments


def test_build_segments_csv_pipeline_uses_stored_seg_id_and_2026_header():
    course = {
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 2], [3, 3]]},
        "segment_break_ids": {},
        "segments": [
            {
                "seg_id": "A1",
                "seg_label": "Shared start",
                "from_km": 0,
                "to_km": 1,
                "events": ["full", "half"],
                "width_m": 5,
                "schema": "on_course_open",
                "direction": "uni",
            },
            {
                "seg_id": "B1",
                "seg_label": "10K only",
                "from_km": 1,
                "to_km": 2,
                "events": ["10k"],
                "width_m": 1.5,
                "schema": "on_course_narrow",
                "direction": "bi",
            },
        ],
    }
    csv_content = build_segments_csv(course, fmt="pipeline")
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    assert "pin_start_label" not in reader.fieldnames
    assert rows[0]["seg_id"] == "A1"
    assert rows[1]["seg_id"] == "B1"
    assert rows[0]["full"] == "y" and rows[0]["half"] == "y" and rows[0]["10k"] == "n"
    assert rows[1]["full"] == "n" and rows[1]["10k"] == "y"
    assert float(rows[1]["10k_from_km"]) == pytest.approx(0.0)
    assert float(rows[1]["10k_to_km"]) == pytest.approx(1.0)
    assert float(rows[1]["full_from_km"]) == pytest.approx(0.0)
    assert float(rows[1]["full_to_km"]) == pytest.approx(0.0)


def test_export_config_package_segments_writes_and_validates(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    config_id = "pkg758test01"
    package = tmp_path / config_id
    package.mkdir()
    (package / "config.json").write_text(
        '{"config_id":"pkg758test01","label":"Test","legacy":false}',
        encoding="utf-8",
    )
    course = {
        "id": config_id,
        "config_id": config_id,
        "segments": [
            {
                "seg_id": "A1",
                "seg_label": "Leg A",
                "from_km": 0,
                "to_km": 0.5,
                "events": ["full"],
                "width_m": 5,
                "schema": "on_course_open",
                "direction": "uni",
            }
        ],
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
    }
    (package / "course.json").write_text(
        __import__("json").dumps(course),
        encoding="utf-8",
    )

    result = export_config_package_segments(config_id)
    segments_path = Path(result["path"])
    assert segments_path.is_file()
    assert result["segment_count"] == 1
    df = load_segments(str(segments_path))
    assert len(df) == 1
    assert df.iloc[0]["seg_id"] == "A1"


def test_export_backs_up_existing_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    config_id = "pkg758backup1"
    package = tmp_path / config_id
    package.mkdir()
    (package / "config.json").write_text("{}", encoding="utf-8")
    (package / "segments.csv").write_text("old,data\n1,2\n", encoding="utf-8")
    course = {
        "id": config_id,
        "segments": [
            {
                "seg_id": "C1",
                "seg_label": "New",
                "from_km": 0,
                "to_km": 1,
                "events": ["elite"],
                "width_m": 3,
                "schema": "on_course_open",
                "direction": "uni",
            }
        ],
    }
    (package / "course.json").write_text(
        __import__("json").dumps(course),
        encoding="utf-8",
    )

    result = export_config_package_segments(config_id)
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).is_file()
    assert "old,data" in Path(result["backup_path"]).read_text()


def test_export_rejects_empty_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    config_id = "pkg758empty1"
    package = tmp_path / config_id
    package.mkdir()
    (package / "course.json").write_text('{"id":"x","segments":[]}', encoding="utf-8")

    with pytest.raises(ValueError, match="no segments"):
        export_config_package_segments(config_id)
