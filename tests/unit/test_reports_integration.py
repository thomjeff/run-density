"""
Integration tests for Runflow v2 reports module.

Tests report generation functions including Density.md, Flow.md, Flow.csv, and Locations.csv.

Phase 3: Integration Tests (Issue #553)
"""

import pytest
import tempfile
from pathlib import Path
import pandas as pd

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline, generate_day_timelines
from app.core.v2.reports import (
    generate_reports_per_day,
    generate_density_report_v2,
    generate_flow_report_v2,
    generate_locations_report_v2,
    get_day_output_path,
)


class TestReportGeneration:
    """Test report generation functions."""
    
    @pytest.fixture
    def setup_test_data(self, tmp_path):
        """Set up test data files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        # Create segments.csv
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "full": ["y", "y"],
            "full_from_km": [0.0, 0.9],
            "full_to_km": [0.9, 1.8],
        })
        segments_df.to_csv(data_dir / "segments.csv", index=False)
        
        # Create flow.csv
        flow_df = pd.DataFrame({
            "seg_id": ["A1"],
            "event_a": ["full"],
            "event_b": ["full"],
        })
        flow_df.to_csv(data_dir / "flow.csv", index=False)
        
        # Create locations.csv
        locations_df = pd.DataFrame({
            "loc_id": ["L1"],
            "lat": [45.0],
            "lon": [-75.0],
            "seg_id": ["A1"],
            "full": ["y"],
            "day": ["sun"],
        })
        locations_df.to_csv(data_dir / "locations.csv", index=False)
        
        return str(data_dir)
    
    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        return [
            Event(name="full", day=Day.SUN, start_time=420, gpx_file="full.gpx", runners_file="full_runners.csv"),
        ]
    
    @pytest.fixture
    def sample_timelines(self, sample_events):
        """Create sample timelines."""
        return generate_day_timelines(sample_events)
    
    @pytest.fixture
    def sample_density_results(self):
        """Create sample density results."""
        return {
            Day.SUN: {
                "segments": pd.DataFrame({
                    "seg_id": ["A1"],
                    "density": [10.5],
                }),
                "runners": pd.DataFrame({
                    "runner_id": ["1"],
                    "pace": [4.0],
                }),
            }
        }
    
    @pytest.fixture
    def sample_flow_results(self):
        """Create sample flow results."""
        return {
            Day.SUN: {
                "flow_segments": pd.DataFrame({
                    "seg_id": ["A1"],
                    "event_a": ["full"],
                    "event_b": ["full"],
                }),
            }
        }
    
    def test_get_day_output_path(self, tmp_path, monkeypatch):
        """Test get_day_output_path generates correct paths."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        
        path = get_day_output_path("test123", Day.SUN, "reports")
        
        assert path == tmp_path / "test123" / "sun" / "reports"
    
    def test_generate_density_report_v2(self, setup_test_data, sample_events, sample_timelines, 
                                       sample_density_results, tmp_path, monkeypatch):
        """Test density report generation."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        run_id = "test123"
        run_path = tmp_path / run_id / "sun" / "reports"
        run_path.mkdir(parents=True, exist_ok=True)
        
        result = generate_density_report_v2(
            run_id=run_id,
            day=Day.SUN,
            events=sample_events,
            timeline=sample_timelines[0],
            density_results=sample_density_results[Day.SUN],
            segments_file_path="segments.csv",
        )
        
        assert result is not None
        assert (tmp_path / run_id / "sun" / "reports" / "Density.md").exists()
    
    def test_generate_flow_report_v2(self, setup_test_data, sample_events, sample_timelines,
                                     sample_flow_results, tmp_path, monkeypatch):
        """Test flow report generation."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        run_id = "test123"
        run_path = tmp_path / run_id / "sun" / "reports"
        run_path.mkdir(parents=True, exist_ok=True)
        
        result = generate_flow_report_v2(
            run_id=run_id,
            day=Day.SUN,
            events=sample_events,
            timeline=sample_timelines[0],
            flow_results=sample_flow_results[Day.SUN],
            flow_file_path="flow.csv",
        )
        
        assert result is not None
        assert (tmp_path / run_id / "sun" / "reports" / "Flow.md").exists()
        assert (tmp_path / run_id / "sun" / "reports" / "Flow.csv").exists()
    
    def test_generate_locations_report_v2(self, setup_test_data, sample_events, tmp_path, monkeypatch):
        """Test locations report generation."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        run_id = "test123"
        run_path = tmp_path / run_id / "sun" / "reports"
        run_path.mkdir(parents=True, exist_ok=True)
        
        # Load locations
        locations_df = pd.read_csv(Path(setup_test_data) / "locations.csv")
        
        result = generate_locations_report_v2(
            run_id=run_id,
            day=Day.SUN,
            events=sample_events,
            locations_df=locations_df,
            locations_file_path="locations.csv",
        )
        
        assert result is not None
        assert (tmp_path / run_id / "sun" / "reports" / "Locations.csv").exists()
    
    def test_generate_reports_per_day(self, setup_test_data, sample_events, sample_timelines,
                                      sample_density_results, sample_flow_results, tmp_path, monkeypatch):
        """Test complete report generation per day."""
        monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
        monkeypatch.setenv("DATA_ROOT", setup_test_data)
        
        run_id = "test123"
        
        # Load segments and runners
        segments_df = pd.read_csv(Path(setup_test_data) / "segments.csv")
        runners_df = pd.DataFrame({
            "runner_id": ["1"],
            "event": ["full"],
            "pace": [4.0],
            "distance": [42.2],
            "start_offset": [0],
        })
        locations_df = pd.read_csv(Path(setup_test_data) / "locations.csv")
        
        result = generate_reports_per_day(
            run_id=run_id,
            events=sample_events,
            timelines=sample_timelines,
            density_results=sample_density_results,
            flow_results=sample_flow_results,
            segments_df=segments_df,
            all_runners_df=runners_df,
            locations_df=locations_df,
            data_dir=setup_test_data,
            segments_file_path="segments.csv",
            flow_file_path="flow.csv",
            locations_file_path="locations.csv",
        )
        
        assert Day.SUN in result
        assert "density" in result[Day.SUN]
        assert "flow_md" in result[Day.SUN]
        assert "flow_csv" in result[Day.SUN]
        assert "locations" in result[Day.SUN]
        
        # Verify all report files exist
        assert (tmp_path / run_id / "sun" / "reports" / "Density.md").exists()
        assert (tmp_path / run_id / "sun" / "reports" / "Flow.md").exists()
        assert (tmp_path / run_id / "sun" / "reports" / "Flow.csv").exists()
        assert (tmp_path / run_id / "sun" / "reports" / "Locations.csv").exists()


