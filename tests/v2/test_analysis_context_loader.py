import json
from pathlib import Path

import pytest

from app.config.loader import AnalysisConfigError, load_analysis_context


def _write_analysis_json(run_path: Path, payload: dict) -> None:
    analysis_path = run_path / "analysis.json"
    analysis_path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_segments_columns_raises(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    segments_csv = data_dir / "segments.csv"
    segments_csv.write_text(
        "seg_id,seg_label,width_m,direction\nA1,Start,4,uni\n",
        encoding="utf-8",
    )
    (data_dir / "flow.csv").write_text("seg_id,event_a,event_b\nA1,full,full\n", encoding="utf-8")
    (data_dir / "locations.csv").write_text("loc_id,lat,lon,seg_id\nL1,45.0,-75.0,A1\n", encoding="utf-8")
    (data_dir / "full_runners.csv").write_text("runner_id,event\n1,full\n", encoding="utf-8")
    (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>", encoding="utf-8")

    analysis_payload = {
        "data_dir": str(data_dir),
        "data_files": {
            "segments": "segments.csv",
            "flow": "flow.csv",
            "locations": "locations.csv",
            "runners": {"full": "full_runners.csv"},
            "gpx": {"full": "full.gpx"},
        },
        "events": [
            {
                "name": "full",
                "day": "sun",
                "start_time": 420,
                "event_duration_minutes": 180,
                "runners_file": "full_runners.csv",
                "gpx_file": "full.gpx",
            }
        ],
    }

    _write_analysis_json(tmp_path, analysis_payload)

    with pytest.raises(AnalysisConfigError, match="segments.csv missing required columns"):
        load_analysis_context(tmp_path)


def test_missing_event_fields_fail_fast(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    segments_csv = data_dir / "segments.csv"
    segments_csv.write_text(
        "seg_id,seg_label,schema,width_m,direction\nA1,Start,on_course_open,4,uni\n",
        encoding="utf-8",
    )
    (data_dir / "flow.csv").write_text("seg_id,event_a,event_b\nA1,full,full\n", encoding="utf-8")
    (data_dir / "locations.csv").write_text("loc_id,lat,lon,seg_id\nL1,45.0,-75.0,A1\n", encoding="utf-8")
    (data_dir / "full_runners.csv").write_text("runner_id,event\n1,full\n", encoding="utf-8")
    (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>", encoding="utf-8")

    analysis_payload = {
        "data_dir": str(data_dir),
        "data_files": {
            "segments": "segments.csv",
            "flow": "flow.csv",
            "locations": "locations.csv",
            "runners": {"full": "full_runners.csv"},
            "gpx": {"full": "full.gpx"},
        },
        "events": [
            {
                "name": "full",
                "day": "sun",
                "start_time": 420,
                "runners_file": "full_runners.csv",
                "gpx_file": "full.gpx",
            }
        ],
    }

    _write_analysis_json(tmp_path, analysis_payload)

    with pytest.raises(AnalysisConfigError, match="events\\[\\*\\]\\.event_duration_minutes"):
        load_analysis_context(tmp_path)
