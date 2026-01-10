"""
Integration tests for Runflow v2 pipeline module.

Tests the complete pipeline workflow from events to output generation,
including directory structure creation, analysis execution, and metadata generation.

Phase 3: Integration Tests (Issue #553)
"""

import pytest
import json
from pathlib import Path
import pandas as pd

from app.core.v2.models import Day, Event
from app.core.v2.analysis_config import generate_analysis_json
from app.config.loader import AnalysisConfigError, load_analysis_context
from app.core.v2.pipeline import (
    create_stubbed_pipeline,
    create_full_analysis_pipeline,
    create_metadata_json,
    create_combined_metadata,
)


class TestStubbedPipeline:
    """Test stubbed pipeline (directory structure creation)."""
    
    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        return [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="10k", day=Day.SUN, start_time=440, gpx_file="10k.gpx", runners_file="10k_runners.csv"),
            Event(name="elite", day=Day.SAT, start_time=480, gpx_file="elite.gpx", runners_file="elite_runners.csv"),
        ]
    
    def test_create_stubbed_pipeline_single_day(self, sample_events, tmp_path, monkeypatch):
        """Test stubbed pipeline creates correct directory structure for single day."""
        # Filter to single day
        sun_events = [e for e in sample_events if e.day == Day.SUN]
        
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        
        result = create_stubbed_pipeline(sun_events)
        
        assert "run_id" in result
        assert "days" in result
        assert "output_paths" in result
        assert len(result["days"]) == 1
        assert "sun" in result["days"]
        
        # Verify directory structure
        run_path = tmp_path / result["run_id"]
        assert run_path.exists()
        assert (run_path / "sun").exists()
        assert (run_path / "sun" / "reports").exists()
        assert (run_path / "sun" / "bins").exists()
        assert (run_path / "sun" / "maps").exists()
        assert (run_path / "sun" / "ui").exists()
        assert (run_path / "sun" / "metadata.json").exists()
    
    def test_create_stubbed_pipeline_multi_day(self, sample_events, tmp_path, monkeypatch):
        """Test stubbed pipeline creates correct directory structure for multiple days."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        
        result = create_stubbed_pipeline(sample_events)
        
        assert len(result["days"]) == 2
        assert "sat" in result["days"]
        assert "sun" in result["days"]
        
        # Verify both day directories exist
        run_path = tmp_path / result["run_id"]
        assert (run_path / "sat").exists()
        assert (run_path / "sun").exists()
        
        # Verify metadata.json exists for both days
        assert (run_path / "sat" / "metadata.json").exists()
        assert (run_path / "sun" / "metadata.json").exists()
    
    def test_stubbed_pipeline_metadata_structure(self, sample_events, tmp_path, monkeypatch):
        """Test that metadata.json has correct structure."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        
        result = create_stubbed_pipeline(sample_events)
        run_path = tmp_path / result["run_id"]
        
        # Check sun metadata
        sun_metadata_path = run_path / "sun" / "metadata.json"
        assert sun_metadata_path.exists()
        
        with open(sun_metadata_path, 'r') as f:
            metadata = json.load(f)
        
        assert metadata["run_id"] == result["run_id"]
        assert metadata["day"] == "sun"
        assert "created_at" in metadata
        assert "status" in metadata
        assert "events" in metadata
        assert "files_created" in metadata
        assert "file_counts" in metadata


class TestFullAnalysisPipeline:
    """Test full analysis pipeline with real data."""
    
    @pytest.fixture
    def setup_test_data(self, tmp_path):
        """Set up test data files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create segments.csv
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2", "B1"],
            "seg_label": ["Start", "Mid", "End"],
            "schema": ["on_course_open", "on_course_open", "on_course_open"],
            "width_m": [4.0, 5.0, 4.5],
            "direction": ["uni", "uni", "uni"],
            "full": ["y", "y", "n"],
            "10k": ["y", "y", "y"],
            "full_from_km": [0.0, 0.9, 0.0],
            "full_to_km": [0.9, 1.8, 0.0],
            "10k_from_km": [0.0, 0.9, 1.8],
            "10k_to_km": [0.9, 1.8, 2.7],
        })
        segments_df.to_csv(data_dir / "segments.csv", index=False)
        
        # Create flow.csv
        flow_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "event_a": ["full", "full"],
            "event_b": ["10k", "10k"],
        })
        flow_df.to_csv(data_dir / "flow.csv", index=False)
        
        # Create locations.csv
        locations_df = pd.DataFrame({
            "loc_id": ["L1", "L2"],
            "lat": [45.0, 45.1],
            "lon": [-75.0, -75.1],
            "seg_id": ["A1", "A2"],
            "full": ["y", "y"],
            "10k": ["y", "y"],
            "day": ["sun", "sun"],
        })
        locations_df.to_csv(data_dir / "locations.csv", index=False)
        
        # Create runner files
        full_runners = pd.DataFrame({
            "runner_id": ["1", "2"],
            "event": ["full", "full"],
            "pace": [4.0, 4.5],
            "distance": [42.2, 42.2],
            "start_offset": [0, 1],
        })
        full_runners.to_csv(data_dir / "full_runners.csv", index=False)

        tenk_runners = pd.DataFrame({
            "runner_id": ["10", "11"],
            "event": ["10k", "10k"],
            "pace": [4.8, 5.1],
            "distance": [10.0, 10.0],
            "start_offset": [0, 1],
        })
        tenk_runners.to_csv(data_dir / "10k_runners.csv", index=False)
        
        # Create GPX file
        (data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        (data_dir / "10k.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        
        return str(data_dir)
    
    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        return [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
            Event(name="10k", day=Day.SUN, start_time=440, gpx_file="10k.gpx", runners_file="10k_runners.csv"),
        ]
    
    def test_full_pipeline_creates_outputs(self, setup_test_data, sample_events, tmp_path, monkeypatch):
        """Test that full pipeline creates all expected output files."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)

        run_id = "test-full-pipeline"
        run_path = tmp_path / run_id
        run_path.mkdir()
        request_payload = {
            "description": "Test analysis",
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx",
                },
                {
                    "name": "10k",
                    "day": "sun",
                    "start_time": 440,
                    "event_duration_minutes": 120,
                    "runners_file": "10k_runners.csv",
                    "gpx_file": "10k.gpx",
                },
            ],
        }

        generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path,
            data_dir=setup_test_data,
        )
        load_analysis_context(run_path)

        result = create_full_analysis_pipeline(
            events=sample_events,
            segments_file="segments.csv",
            locations_file="locations.csv",
            flow_file="flow.csv",
            data_dir=setup_test_data,
            run_id=run_id,
        )
        
        assert "run_id" in result
        assert "days" in result
        assert "density_results" in result
        assert "flow_results" in result
        
        run_path = tmp_path / result["run_id"]
        sun_path = run_path / "sun"
        
        # Verify critical output files exist
        assert (sun_path / "reports" / "Density.md").exists()
        assert (sun_path / "reports" / "Flow.csv").exists()
        assert (sun_path / "reports" / "Flow.md").exists()
        assert (sun_path / "bins" / "bins.parquet").exists()
        assert (sun_path / "metadata.json").exists()
    
    def test_full_pipeline_analysis_json_required(self, setup_test_data, sample_events, tmp_path, monkeypatch):
        """Test that full pipeline requires analysis.json to exist."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)

        run_id = "missing-analysis-json"

        with pytest.raises(FileNotFoundError, match="analysis.json not found"):
            create_full_analysis_pipeline(
                events=sample_events,
                segments_file="segments.csv",
                locations_file="locations.csv",
                flow_file="flow.csv",
                data_dir=setup_test_data,
                run_id=run_id,
            )

    def test_full_pipeline_uses_analysis_json_paths(self, setup_test_data, sample_events, tmp_path, monkeypatch):
        """Test that analysis.json overrides provided file paths without fallback."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)

        alt_data_dir = tmp_path / "alt_data"
        alt_data_dir.mkdir()
        segments_df = pd.DataFrame({
            "seg_id": ["C1"],
            "seg_label": ["Alt"],
            "schema": ["on_course_open"],
            "width_m": [4.0],
            "direction": ["uni"],
            "full": ["y"],
            "10k": ["y"],
            "full_from_km": [0.0],
            "full_to_km": [1.0],
            "10k_from_km": [0.0],
            "10k_to_km": [1.0],
        })
        segments_df.to_csv(alt_data_dir / "segments.csv", index=False)

        flow_df = pd.DataFrame({
            "seg_id": ["C1"],
            "event_a": ["full"],
            "event_b": ["10k"],
        })
        flow_df.to_csv(alt_data_dir / "flow.csv", index=False)

        locations_df = pd.DataFrame({
            "loc_id": ["L1"],
            "lat": [45.0],
            "lon": [-75.0],
            "seg_id": ["C1"],
            "full": ["y"],
            "10k": ["y"],
            "day": ["sun"],
        })
        locations_df.to_csv(alt_data_dir / "locations.csv", index=False)

        full_runners = pd.DataFrame({
            "runner_id": ["1"],
            "event": ["full"],
            "pace": [4.0],
            "distance": [42.2],
            "start_offset": [0],
        })
        full_runners.to_csv(alt_data_dir / "full_runners.csv", index=False)

        tenk_runners = pd.DataFrame({
            "runner_id": ["10"],
            "event": ["10k"],
            "pace": [4.8],
            "distance": [10.0],
            "start_offset": [0],
        })
        tenk_runners.to_csv(alt_data_dir / "10k_runners.csv", index=False)

        (alt_data_dir / "full.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")
        (alt_data_dir / "10k.gpx").write_text("<?xml version='1.0'?><gpx></gpx>")

        run_id = "analysis-json-paths"
        run_path = tmp_path / run_id
        run_path.mkdir()
        request_payload = {
            "description": "Alt test",
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx",
                },
                {
                    "name": "10k",
                    "day": "sun",
                    "start_time": 440,
                    "event_duration_minutes": 120,
                    "runners_file": "10k_runners.csv",
                    "gpx_file": "10k.gpx",
                },
            ],
        }
        generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path,
            data_dir=str(alt_data_dir),
        )
        load_analysis_context(run_path)

        result = create_full_analysis_pipeline(
            events=sample_events,
            segments_file="missing.csv",
            locations_file="missing.csv",
            flow_file="missing.csv",
            data_dir="missing",
            run_id=run_id,
        )

        run_path = tmp_path / result["run_id"]
        assert (run_path / "sun" / "reports" / "Density.md").exists()

    def test_full_pipeline_invalid_segments_schema(self, setup_test_data, sample_events, tmp_path, monkeypatch):
        """Test that invalid segments schema fails fast."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)

        run_id = "invalid-segments"
        run_path = tmp_path / run_id
        run_path.mkdir()

        data_dir = Path(setup_test_data)
        segments_csv = data_dir / "segments.csv"
        segments_df = pd.read_csv(segments_csv)
        segments_df["schema"] = ""
        segments_df.to_csv(segments_csv, index=False)

        request_payload = {
            "description": "Bad schema",
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx",
                },
                {
                    "name": "10k",
                    "day": "sun",
                    "start_time": 440,
                    "event_duration_minutes": 120,
                    "runners_file": "10k_runners.csv",
                    "gpx_file": "10k.gpx",
                },
            ],
        }
        generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path,
            data_dir=setup_test_data,
        )

        with pytest.raises(AnalysisConfigError, match="segments.csv has empty values"):
            create_full_analysis_pipeline(
                events=sample_events,
                segments_file="segments.csv",
                locations_file="locations.csv",
                flow_file="flow.csv",
                data_dir=setup_test_data,
                run_id=run_id,
            )

    def test_full_pipeline_missing_flow_file(self, setup_test_data, sample_events, tmp_path, monkeypatch):
        """Test that missing flow file fails fast."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)

        run_id = "missing-flow"
        run_path = tmp_path / run_id
        run_path.mkdir()

        request_payload = {
            "description": "Missing flow",
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "missing_flow.csv",
            "events": [
                {
                    "name": "full",
                    "day": "sun",
                    "start_time": 420,
                    "event_duration_minutes": 390,
                    "runners_file": "full_runners.csv",
                    "gpx_file": "full.gpx",
                },
                {
                    "name": "10k",
                    "day": "sun",
                    "start_time": 440,
                    "event_duration_minutes": 120,
                    "runners_file": "10k_runners.csv",
                    "gpx_file": "10k.gpx",
                },
            ],
        }
        generate_analysis_json(
            request_payload=request_payload,
            run_id=run_id,
            run_path=run_path,
            data_dir=setup_test_data,
        )

        with pytest.raises(FileNotFoundError, match="flow.csv not found"):
            create_full_analysis_pipeline(
                events=sample_events,
                segments_file="segments.csv",
                locations_file="locations.csv",
                flow_file="flow.csv",
                data_dir=setup_test_data,
                run_id=run_id,
            )


class TestMetadataGeneration:
    """Test metadata generation functions."""
    
    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        return [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
        ]
    
    def test_create_metadata_json_structure(self, sample_events, tmp_path):
        """Test that create_metadata_json creates correct structure."""
        day_path = tmp_path / "sun"
        day_path.mkdir(parents=True)
        (day_path / "reports").mkdir()
        (day_path / "bins").mkdir()
        (day_path / "ui").mkdir()
        
        metadata = create_metadata_json(
            run_id="test123",
            day="sun",
            events=sample_events,
            day_path=day_path,
            participants_by_event={"full": 100},
        )
        
        assert metadata["run_id"] == "test123"
        assert metadata["day"] == "sun"
        assert "created_at" in metadata
        assert "status" in metadata
        assert "events" in metadata
        assert metadata["events"]["full"]["participants"] == 100
        assert "files_created" in metadata
        assert "file_counts" in metadata
    
    def test_create_combined_metadata_structure(self, tmp_path):
        """Test that create_combined_metadata creates correct structure."""
        per_day_metadata = {
            "sun": {
                "run_id": "test123",
                "day": "sun",
                "status": "PASS",
                "files_created": {"reports": ["Density.md"]},
            }
        }
        
        metadata = create_combined_metadata(
            run_id="test123",
            days=["sun"],
            per_day_metadata=per_day_metadata,
        )
        
        assert metadata["run_id"] == "test123"
        assert "days" in metadata
        assert "sun" in metadata["days"]
        assert "status" in metadata
        assert "files_created" in metadata
