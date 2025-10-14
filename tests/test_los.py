"""
Unit Tests for LOS Classification Module

Tests Level of Service classification logic, ranking, and utility functions.
Fast unit tests with no external dependencies.

Issue #233: Operational Intelligence - Unit Tests
"""

import pytest
import pandas as pd

from app.los import (
    los_from_density,
    los_rank,
    meets_los_threshold,
    classify_bins_los,
    get_los_description,
    get_los_color,
    get_worst_los,
    filter_by_los_threshold,
    DEFAULT_LOS_THRESHOLDS
)


@pytest.mark.fast
class TestLOSClassification:
    """Tests for basic LOS classification."""
    
    def test_los_from_density_boundaries(self):
        """Test LOS classification at threshold boundaries."""
        # Test exact thresholds
        assert los_from_density(0.0) == 'A'
        assert los_from_density(0.5) == 'B'
        assert los_from_density(1.0) == 'C'
        assert los_from_density(1.5) == 'D'
        assert los_from_density(2.0) == 'E'
        assert los_from_density(3.0) == 'F'
    
    def test_los_from_density_between_thresholds(self):
        """Test LOS classification between thresholds."""
        assert los_from_density(0.3) == 'A'   # Below B
        assert los_from_density(0.75) == 'B'  # Between B and C
        assert los_from_density(1.2) == 'C'   # Between C and D
        assert los_from_density(1.7) == 'D'   # Between D and E
        assert los_from_density(2.5) == 'E'   # Between E and F
        assert los_from_density(5.0) == 'F'   # Above F
    
    def test_los_from_density_edge_cases(self):
        """Test LOS classification edge cases."""
        # Negative density should default to A
        assert los_from_density(-1.0) == 'A'
        
        # Very high density
        assert los_from_density(10.0) == 'F'
        
        # Zero density
        assert los_from_density(0.0) == 'A'
    
    def test_los_from_density_custom_thresholds(self):
        """Test LOS classification with custom thresholds."""
        custom = {'A': 0.0, 'B': 1.0, 'C': 2.0, 'D': 3.0, 'E': 4.0, 'F': 5.0}
        
        assert los_from_density(0.5, custom) == 'A'
        assert los_from_density(1.0, custom) == 'B'
        assert los_from_density(2.5, custom) == 'C'


@pytest.mark.fast
class TestLOSRanking:
    """Tests for LOS ranking and comparison."""
    
    def test_los_rank_values(self):
        """Test LOS rank numeric values."""
        assert los_rank('A') == 0
        assert los_rank('B') == 1
        assert los_rank('C') == 2
        assert los_rank('D') == 3
        assert los_rank('E') == 4
        assert los_rank('F') == 5
    
    def test_los_rank_invalid(self):
        """Test LOS rank with invalid input."""
        assert los_rank('G') == -1
        assert los_rank('') == -1
        assert los_rank('Z') == -1
    
    def test_meets_los_threshold(self):
        """Test LOS threshold comparison."""
        # Equal to threshold
        assert meets_los_threshold('C', 'C') is True
        
        # Worse than threshold (should flag)
        assert meets_los_threshold('D', 'C') is True
        assert meets_los_threshold('E', 'C') is True
        assert meets_los_threshold('F', 'C') is True
        
        # Better than threshold (should not flag)
        assert meets_los_threshold('B', 'C') is False
        assert meets_los_threshold('A', 'C') is False
        
        # Edge cases
        assert meets_los_threshold('A', 'A') is True
        assert meets_los_threshold('F', 'F') is True


@pytest.mark.fast
class TestLOSDataFrameOperations:
    """Tests for DataFrame-level LOS operations."""
    
    def test_classify_bins_los(self):
        """Test classifying bins in DataFrame."""
        df = pd.DataFrame({
            'density_peak': [0.3, 0.75, 1.2, 1.7, 2.5, 5.0]
        })
        
        result = classify_bins_los(df, density_field='density_peak')
        
        assert 'los' in result.columns
        assert 'los_rank' in result.columns
        assert list(result['los']) == ['A', 'B', 'C', 'D', 'E', 'F']
        assert list(result['los_rank']) == [0, 1, 2, 3, 4, 5]
    
    def test_filter_by_los_threshold(self):
        """Test filtering DataFrame by LOS threshold."""
        df = pd.DataFrame({
            'density_peak': [0.3, 0.75, 1.2, 1.7, 2.5, 5.0],
            'los': ['A', 'B', 'C', 'D', 'E', 'F'],
            'los_rank': [0, 1, 2, 3, 4, 5]
        })
        
        # Filter for LOS >= C
        result = filter_by_los_threshold(df, 'C')
        
        assert len(result) == 4  # C, D, E, F
        assert set(result['los']) == {'C', 'D', 'E', 'F'}
    
    def test_get_worst_los(self):
        """Test finding worst LOS in DataFrame."""
        df = pd.DataFrame({
            'los': ['A', 'B', 'C', 'D', 'E', 'F'],
            'los_rank': [0, 1, 2, 3, 4, 5]
        })
        
        assert get_worst_los(df) == 'F'
        
        # Test with subset
        df_subset = df[df['los_rank'] <= 2]
        assert get_worst_los(df_subset) == 'C'
        
        # Test with empty DataFrame
        df_empty = pd.DataFrame(columns=['los', 'los_rank'])
        assert get_worst_los(df_empty) == 'A'


@pytest.mark.fast
class TestLOSUtilities:
    """Tests for LOS utility functions."""
    
    def test_get_los_description(self):
        """Test LOS description retrieval."""
        assert 'Free flow' in get_los_description('A')
        assert 'Stable flow' in get_los_description('B')
        assert 'Stable flow' in get_los_description('C')
        assert 'Unstable flow' in get_los_description('D')
        assert 'Very unstable' in get_los_description('E')
        assert 'Breakdown' in get_los_description('F')
    
    def test_get_los_color(self):
        """Test LOS color code retrieval."""
        # Test default colors
        assert get_los_color('A') == '#4CAF50'  # Green
        assert get_los_color('B') == '#8BC34A'  # Light green
        assert get_los_color('C') == '#FFC107'  # Amber
        assert get_los_color('D') == '#FF9800'  # Orange
        assert get_los_color('E') == '#FF5722'  # Red-orange
        assert get_los_color('F') == '#F44336'  # Red
        
        # Test custom colors
        custom = {'A': '#000000', 'F': '#FFFFFF'}
        assert get_los_color('A', custom) == '#000000'
        assert get_los_color('F', custom) == '#FFFFFF'
        
        # Test unknown LOS
        assert get_los_color('Z') == '#808080'  # Gray


@pytest.mark.fast
class TestLOSIntegration:
    """Integration tests for LOS classification workflow."""
    
    def test_full_classification_workflow(self):
        """Test complete LOS classification workflow."""
        # Create sample data
        df = pd.DataFrame({
            'segment_id': ['A1', 'A1', 'B1', 'B1', 'C1', 'C1'],
            'density_peak': [0.2, 0.8, 1.1, 1.4, 2.2, 4.5]
        })
        
        # Classify
        result = classify_bins_los(df)
        
        # Filter for high density (>= C)
        flagged = filter_by_los_threshold(result, 'C')
        
        # Should have 4 bins flagged (C, C, E, F)
        assert len(flagged) == 4
        
        # Verify worst LOS
        worst = get_worst_los(flagged)
        assert worst == 'F'
    
    def test_los_classification_consistency(self):
        """Test that LOS classification is consistent."""
        # Same density should always give same LOS
        density = 1.5
        
        result1 = los_from_density(density)
        result2 = los_from_density(density)
        result3 = los_from_density(density)
        
        assert result1 == result2 == result3 == 'D'

