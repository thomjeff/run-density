"""
Unit tests for Runflow v2 Density Pipeline Module

Tests density analysis with day-scoped filtering and event-specific runner loading.
Verifies that v1 density calculations are preserved while supporting multi-day analysis.

Phase 4: Density Pipeline Refactor (Issue #498)
"""

import unittest
from pathlib import Path
from datetime import datetime
import pandas as pd
import tempfile
import shutil

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.core.v2.density import (
    get_event_distance_range_v2,
    load_all_runners_for_events,
    filter_runners_by_day,
    analyze_density_segments_v2,
)


class TestGetEventDistanceRangeV2(unittest.TestCase):
    """Test get_event_distance_range_v2 function."""
    
    def test_full_event_range(self):
        """Test extracting distance range for full event."""
        segment = pd.Series({
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
            "half_from_km": 0.0,
            "half_to_km": 0.5,
        })
        event = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        self.assertEqual(from_km, 0.0)
        self.assertEqual(to_km, 0.9)
    
    def test_half_event_range(self):
        """Test extracting distance range for half event."""
        segment = pd.Series({
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
            "half_from_km": 0.0,
            "half_to_km": 0.5,
        })
        event = Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        self.assertEqual(from_km, 0.0)
        self.assertEqual(to_km, 0.5)
    
    def test_10k_event_range(self):
        """Test extracting distance range for 10k event."""
        segment = pd.Series({
            "seg_id": "A1",
            "10k_from_km": 0.0,
            "10k_to_km": 0.3,
        })
        event = Event(name="10k", day=Day.SUN, start_time=460, runners_file="10k_runners.csv", gpx_file="10k.gpx", seg_ids=[])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        self.assertEqual(from_km, 0.0)
        self.assertEqual(to_km, 0.3)
    
    def test_case_insensitive_matching(self):
        """Test that column matching is case-insensitive."""
        segment = pd.Series({
            "seg_id": "A1",
            "10K_from_km": 0.0,  # Note: uppercase "10K"
            "10K_to_km": 0.3,
        })
        event = Event(name="10k", day=Day.SUN, start_time=460, runners_file="10k_runners.csv", gpx_file="10k.gpx", seg_ids=[])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        self.assertEqual(from_km, 0.0)
        self.assertEqual(to_km, 0.3)
    
    def test_missing_range_returns_defaults(self):
        """Test that missing range returns (0.0, 0.0)."""
        segment = pd.Series({
            "seg_id": "A1",
            "full_from_km": 0.0,
            "full_to_km": 0.9,
        })
        event = Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[])
        
        from_km, to_km = get_event_distance_range_v2(segment, event)
        self.assertEqual(from_km, 0.0)
        self.assertEqual(to_km, 0.0)


class TestLoadAllRunnersForEvents(unittest.TestCase):
    """Test load_all_runners_for_events function."""
    
    def setUp(self):
        """Set up temporary data directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_load_event_specific_files(self):
        """Test loading runners from event-specific CSV files."""
        # Create event-specific runner files
        full_runners = pd.DataFrame({
            "runner_id": ["F1", "F2"],
            "event": ["full", "full"],
            "pace": [5.0, 5.5],
            "distance": [42.2, 42.2],
            "start_offset": [0, 10]
        })
        full_runners.to_csv(self.data_dir / "full_runners.csv", index=False)
        
        half_runners = pd.DataFrame({
            "runner_id": ["H1", "H2"],
            "event": ["half", "half"],
            "pace": [4.5, 5.0],
            "distance": [21.1, 21.1],
            "start_offset": [0, 5]
        })
        half_runners.to_csv(self.data_dir / "half_runners.csv", index=False)
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
        ]
        
        result_df = load_all_runners_for_events(events, str(self.data_dir))
        
        self.assertEqual(len(result_df), 4)
        self.assertIn("Full", result_df["event"].values)
        self.assertIn("Half", result_df["event"].values)
        self.assertEqual(set(result_df["runner_id"].values), {"F1", "F2", "H1", "H2"})
    
    def test_fallback_to_v1_format(self):
        """Test fallback to v1 runners.csv format."""
        # Create v1 format runners.csv
        runners = pd.DataFrame({
            "runner_id": ["R1", "R2", "R3"],
            "event": ["Full", "Half", "10K"],
            "pace": [5.0, 4.5, 4.0],
            "distance": [42.2, 21.1, 10.0],
            "start_offset": [0, 0, 0]
        })
        runners.to_csv(self.data_dir / "runners.csv", index=False)
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
        ]
        
        result_df = load_all_runners_for_events(events, str(self.data_dir))
        
        # Should filter to only Full event runners
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df["event"].iloc[0], "Full")
        self.assertEqual(result_df["runner_id"].iloc[0], "R1")


class TestFilterRunnersByDay(unittest.TestCase):
    """Test filter_runners_by_day function."""
    
    def test_filter_sunday_runners(self):
        """Test filtering runners to Sunday events only."""
        runners_df = pd.DataFrame({
            "runner_id": ["F1", "H1", "E1"],
            "event": ["Full", "Half", "Elite"],
            "pace": [5.0, 4.5, 4.0],
            "distance": [42.2, 21.1, 5.0],
            "start_offset": [0, 0, 0]
        })
        
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
            Event(name="elite", day=Day.SAT, start_time=400, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=[]),
        ]
        
        filtered = filter_runners_by_day(runners_df, Day.SUN, events)
        
        self.assertEqual(len(filtered), 2)
        self.assertIn("Full", filtered["event"].values)
        self.assertIn("Half", filtered["event"].values)
        self.assertNotIn("Elite", filtered["event"].values)


class TestAnalyzeDensitySegmentsV2(unittest.TestCase):
    """Test analyze_density_segments_v2 function."""
    
    def setUp(self):
        """Set up test data."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)
        
        # Create minimal segments.csv
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "seg_label": ["Start", "Segment 2"],
            "full": ["y", "y"],
            "half": ["y", "n"],
            "10k": ["n", "n"],
            "full_from_km": [0.0, 0.9],
            "full_to_km": [0.9, 1.8],
            "half_from_km": [0.0, 0.0],
            "half_to_km": [0.9, 0.0],
            "width_m": [5.0, 5.0],
            "direction": ["forward", "forward"],
            "length_km": [0.9, 0.9],
        })
        segments_df.to_csv(self.data_dir / "segments.csv", index=False)
        
        # Create runner files
        full_runners = pd.DataFrame({
            "runner_id": ["F1", "F2"],
            "event": ["full", "full"],
            "pace": [5.0, 5.5],
            "distance": [42.2, 42.2],
            "start_offset": [0, 10]
        })
        full_runners.to_csv(self.data_dir / "full_runners.csv", index=False)
        
        half_runners = pd.DataFrame({
            "runner_id": ["H1"],
            "event": ["half"],
            "pace": [4.5],
            "distance": [21.1],
            "start_offset": [0]
        })
        half_runners.to_csv(self.data_dir / "half_runners.csv", index=False)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_analyze_single_day(self):
        """Test density analysis for a single day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
        ]
        
        # Create timeline
        timeline = DayTimeline(day=Day.SUN, t0=420 * 60, events=events)
        
        # Load segments and runners
        segments_df = pd.read_csv(self.data_dir / "segments.csv")
        all_runners_df = load_all_runners_for_events(events, str(self.data_dir))
        
        # Run analysis
        results = analyze_density_segments_v2(
            events=events,
            timelines=[timeline],
            segments_df=segments_df,
            all_runners_df=all_runners_df,
            density_csv_path=str(self.data_dir / "segments.csv")
        )
        
        # Verify results structure
        self.assertIn(Day.SUN, results)
        sun_results = results[Day.SUN]
        self.assertIn("summary", sun_results)
        self.assertIn("segments", sun_results)
        self.assertEqual(sun_results["day"], "sun")
        self.assertEqual(set(sun_results["events"]), {"full", "half"})


if __name__ == "__main__":
    unittest.main()

