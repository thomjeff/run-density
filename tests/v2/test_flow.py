"""
Unit tests for Runflow v2 Flow Pipeline Module

Tests flow analysis with day-scoped filtering and event-specific runner loading.
Verifies that v1 flow calculations are preserved while supporting multi-day analysis.

Phase 5: Flow Pipeline Refactor (Issue #499)
"""

import unittest
from pathlib import Path
import pandas as pd
import tempfile
import shutil

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.core.v2.flow import (
    get_shared_segments,
    generate_event_pairs_v2,
    load_flow_metadata,
    analyze_temporal_flow_segments_v2,
)


class TestGetSharedSegments(unittest.TestCase):
    """Test get_shared_segments function."""
    
    def test_find_shared_segments(self):
        """Test finding segments common to both events."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1", "A2", "A3", "B1"],
            "full": ["y", "y", "n", "y"],
            "half": ["y", "n", "y", "n"],
            "10k": ["n", "n", "n", "y"],
        })
        
        event_a = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[])
        event_b = Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[])
        
        shared = get_shared_segments(event_a, event_b, segments_df)
        
        # Only A1 is used by both full and half
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared.iloc[0]["seg_id"], "A1")
    
    def test_cross_day_pair_raises_error(self):
        """Test that cross-day pairs raise ValueError."""
        segments_df = pd.DataFrame({
            "seg_id": ["A1"],
            "full": ["y"],
            "half": ["y"],
        })
        
        event_a = Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[])
        event_b = Event(name="half", day=Day.SAT, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[])
        
        with self.assertRaises(ValueError) as context:
            get_shared_segments(event_a, event_b, segments_df)
        
        self.assertIn("Cross-day", str(context.exception))


class TestGenerateEventPairsV2(unittest.TestCase):
    """Test generate_event_pairs_v2 function."""
    
    def test_single_day_pairs(self):
        """Test generating pairs for events on the same day."""
        events = [
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
            Event(name="half", day=Day.SUN, start_time=440, runners_file="half_runners.csv", gpx_file="half.gpx", seg_ids=[]),
            Event(name="10k", day=Day.SUN, start_time=460, runners_file="10k_runners.csv", gpx_file="10k.gpx", seg_ids=[]),
        ]
        
        pairs = generate_event_pairs_v2(events)
        
        # Should generate 3 unique pairs: (full, half), (full, 10k), (half, 10k)
        self.assertEqual(len(pairs), 3)
        
        pair_names = {(a.name, b.name) for a, b in pairs}
        self.assertIn(("full", "half"), pair_names)
        self.assertIn(("full", "10k"), pair_names)
        self.assertIn(("half", "10k"), pair_names)
    
    def test_no_cross_day_pairs(self):
        """Test that cross-day pairs are not generated."""
        events = [
            Event(name="elite", day=Day.SAT, start_time=400, runners_file="elite_runners.csv", gpx_file="elite.gpx", seg_ids=[]),
            Event(name="full", day=Day.SUN, start_time=420, runners_file="full_runners.csv", gpx_file="full.gpx", seg_ids=[]),
        ]
        
        pairs = generate_event_pairs_v2(events)
        
        # Should generate 0 pairs (different days)
        self.assertEqual(len(pairs), 0)
    
    def test_empty_events_raises_error(self):
        """Test that empty events list raises ValueError."""
        with self.assertRaises(ValueError):
            generate_event_pairs_v2([])


class TestLoadFlowMetadata(unittest.TestCase):
    """Test load_flow_metadata function."""
    
    def setUp(self):
        """Set up temporary data directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_load_existing_flow_file(self):
        """Test loading existing flow.csv file."""
        flow_df = pd.DataFrame({
            "seg_id": ["A1", "A2"],
            "event_a": ["Full", "Half"],
            "event_b": ["Half", "10K"],
            "flow_type": ["overtake", "merge"],
            "notes": ["Test", "Test2"]
        })
        flow_df.to_csv(self.data_dir / "flow.csv", index=False)
        
        result = load_flow_metadata("flow.csv", str(self.data_dir))
        
        self.assertEqual(len(result), 2)
        self.assertIn("flow_type", result.columns)
    
    def test_missing_flow_file_returns_empty(self):
        """Test that missing flow.csv returns empty DataFrame."""
        result = load_flow_metadata("flow.csv", str(self.data_dir))
        
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()

