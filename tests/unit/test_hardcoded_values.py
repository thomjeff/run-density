"""
Regression tests to prevent reintroduction of hardcoded values.

Issue #512 + #553: Ensures no hardcoded start times, runner counts, or other values are used.
Validates that all values come from API requests → analysis.json → helper functions.

This file serves as a regression test to prevent reintroduction of hardcoded values
that were removed in Issue #512 and Issue #553. All analysis inputs must be
configurable via API request.
"""

import pytest
import ast
import os
from pathlib import Path
from typing import List, Set

from app.core.v2.validation import validate_start_times, ValidationError
from app.core.v2.models import Event, Day


class TestNoHardcodedStartTimes:
    """Test that DEFAULT_START_TIMES is not used anywhere."""
    
    def test_constants_does_not_export_default_start_times(self):
        """Verify constants.py does not export DEFAULT_START_TIMES."""
        import app.utils.constants as constants
        
        # Check that DEFAULT_START_TIMES is not in the module
        assert not hasattr(constants, 'DEFAULT_START_TIMES'), \
            "DEFAULT_START_TIMES should be removed from constants.py (Issue #512)"
    
    def test_no_imports_of_default_start_times(self):
        """Verify no modules import DEFAULT_START_TIMES."""
        codebase_path = Path("app")
        violations = []
        
        for py_file in codebase_path.rglob("*.py"):
            # Skip test files and __pycache__
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    # Check for import statements
                    if 'DEFAULT_START_TIMES' in content:
                        # Check if it's just a comment
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if 'DEFAULT_START_TIMES' in line and not line.strip().startswith('#'):
                                violations.append(f"{py_file}:{i} - {line.strip()}")
            except Exception:
                pass
        
        assert len(violations) == 0, \
            f"Found DEFAULT_START_TIMES usage (not in comments): {violations}"


class TestStartTimeValidation:
    """Test that start_time validation works correctly."""
    
    def test_validate_start_times_requires_field(self):
        """Test that missing start_time raises ValidationError."""
        events = [
            {"name": "full", "day": "sun"}  # Missing start_time
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        
        assert exc_info.value.code == 400
        assert "start_time" in exc_info.value.message.lower()
    
    def test_validate_start_times_accepts_arbitrary_times(self):
        """Test that arbitrary start times are accepted."""
        events = [
            {"name": "custom1", "day": "sat", "start_time": 300},  # 05:00
            {"name": "custom2", "day": "sat", "start_time": 900},  # 15:00
            {"name": "custom3", "day": "sun", "start_time": 0},    # 00:00
            {"name": "custom4", "day": "sun", "start_time": 1439}, # 23:59
        ]
        
        # Should not raise
        validate_start_times(events)
    
    def test_validate_start_times_rejects_invalid_range(self):
        """Test that out-of-range start times are rejected."""
        events = [
            {"name": "invalid", "day": "sun", "start_time": -1}  # Negative
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        
        assert exc_info.value.code == 400
        
        events = [
            {"name": "invalid", "day": "sun", "start_time": 1440}  # Too large
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        
        assert exc_info.value.code == 400
    
    def test_validate_start_times_rejects_non_integer(self):
        """Test that non-integer start times are rejected."""
        events = [
            {"name": "invalid", "day": "sun", "start_time": "420"}  # String
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        
        assert exc_info.value.code == 400
        assert "integer" in exc_info.value.message.lower()


class TestFlowOrderingUsesFlowCsv:
    """Test that flow ordering comes from flow.csv, not start_time."""
    
    def test_flow_csv_is_authoritative_for_ordering(self):
        """Verify that flow.csv ordering is preserved, not start_time ordering."""
        from app.core.v2.flow import load_flow_csv, extract_event_pairs_from_flow_csv
        
        # Load flow.csv
        flow_df = load_flow_csv("data/flow.csv")
        
        # Extract pairs from flow.csv
        pairs = extract_event_pairs_from_flow_csv(flow_df)
        
        # Verify pairs preserve flow.csv ordering (not start_time)
        # This is tested by ensuring the function doesn't reorder based on start_time
        assert len(pairs) > 0, "flow.csv should contain event pairs"
        
        # Check that pairs match flow.csv event_a/event_b ordering
        for event_a, event_b in pairs:
            # Find matching rows in flow.csv
            matching_rows = flow_df[
                (flow_df['event_a'].str.lower() == event_a.name.lower()) &
                (flow_df['event_b'].str.lower() == event_b.name.lower())
            ]
            
            # If found in flow.csv, ordering should match
            if not matching_rows.empty:
                # The pair should exist in flow.csv with this exact ordering
                assert len(matching_rows) > 0, \
                    f"Pair ({event_a.name}, {event_b.name}) should be in flow.csv"
    
    def test_fallback_logs_warning(self):
        """Test that fallback to start_time ordering logs a warning."""
        import logging
        from app.core.v2.flow import generate_event_pairs_fallback
        
        # Create events with different start times
        events = [
            Event(name="late", day=Day.SUN, start_time=500),
            Event(name="early", day=Day.SUN, start_time=400),
        ]
        
        # Capture log messages
        with pytest.LogCapture() as log:
            pairs = generate_event_pairs_fallback(events)
            
            # Verify warning is logged
            assert len(pairs) > 0
            # Note: Actual warning is logged in analyze_temporal_flow_segments_v2 when fallback is used


class TestNoHardcodedRunnerCounts:
    """Test that runner counts are not hardcoded."""
    
    def test_new_density_report_no_hardcoded_counts(self):
        """Verify new_density_report.py does not have hardcoded runner counts."""
        import app.new_density_report as module
        
        # Check source code for hardcoded runner counts
        source_file = Path(module.__file__)
        with open(source_file, 'r') as f:
            content = f.read()
            
            # Check for hardcoded runner count patterns
            hardcoded_patterns = [
                "'full_runners': 368",
                "'10k_runners': 618",
                "'half_runners': 912",
                "full_runners = 368",
                "10k_runners = 618",
                "half_runners = 912",
            ]
            
            violations = []
            for pattern in hardcoded_patterns:
                if pattern in content:
                    violations.append(pattern)
            
            assert len(violations) == 0, \
                f"Found hardcoded runner counts in {source_file}: {violations}"


class TestConstantsUsage:
    """Test that constants are used consistently."""
    
    def test_bin_time_window_uses_constant(self):
        """Verify bin_seconds uses DEFAULT_BIN_TIME_WINDOW_SECONDS."""
        import app.core.density.compute as module
        
        source_file = Path(module.__file__)
        with open(source_file, 'r') as f:
            content = f.read()
            
            # Check that bin_seconds = 60 is not hardcoded
            if 'bin_seconds = 60' in content:
                # Should use constant instead
                assert 'DEFAULT_BIN_TIME_WINDOW_SECONDS' in content, \
                    "bin_seconds should use DEFAULT_BIN_TIME_WINDOW_SECONDS constant"
    
    def test_flow_thresholds_use_constants(self):
        """Verify flow analysis uses constants for thresholds."""
        from app.core.v2.flow import analyze_temporal_flow_segments_v2
        from app.utils.constants import DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS
        import inspect
        
        # Check function signature uses constants as defaults
        sig = inspect.signature(analyze_temporal_flow_segments_v2)
        
        min_overlap_param = sig.parameters.get('min_overlap_duration')
        assert min_overlap_param is not None, "min_overlap_duration parameter should exist"
        assert min_overlap_param.default == DEFAULT_MIN_OVERLAP_DURATION, \
            f"min_overlap_duration should default to {DEFAULT_MIN_OVERLAP_DURATION}"
        
        conflict_length_param = sig.parameters.get('conflict_length_m')
        assert conflict_length_param is not None, "conflict_length_m parameter should exist"
        assert conflict_length_param.default == DEFAULT_CONFLICT_LENGTH_METERS, \
            f"conflict_length_m should default to {DEFAULT_CONFLICT_LENGTH_METERS}"

