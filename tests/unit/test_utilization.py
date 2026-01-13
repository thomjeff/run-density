"""
Unit tests for utilization percentile computation.

Issue #556: Missing rate_per_m_per_min Column Causes Flagging Failure
"""

import pytest
import pandas as pd
import numpy as np
from app.utilization import ensure_rpm, add_utilization_percentile


class TestEnsureRpm:
    """Test ensure_rpm function."""
    
    def test_computes_rpm_when_missing(self):
        """Test that rate_per_m_per_min is computed when missing."""
        df = pd.DataFrame({
            'rate': [5.0, 10.0, 15.0],
            'width_m': [3.0, 3.0, 3.0]
        })
        
        result = ensure_rpm(df)
        
        assert 'rate_per_m_per_min' in result.columns
        expected = (df['rate'] / df['width_m']) * 60.0
        np.testing.assert_array_almost_equal(result['rate_per_m_per_min'].values, expected.values)
    
    def test_leaves_existing_rpm_untouched(self):
        """Test that existing rate_per_m_per_min is not recomputed."""
        df = pd.DataFrame({
            'rate': [5.0, 10.0],
            'width_m': [3.0, 3.0],
            'rate_per_m_per_min': [100.0, 200.0]  # Pre-existing values
        })
        
        result = ensure_rpm(df)
        
        assert result['rate_per_m_per_min'].tolist() == [100.0, 200.0]
    
    def test_raises_when_required_columns_missing(self):
        """Test that ValueError is raised when rate or width_m is missing."""
        df = pd.DataFrame({
            'rate': [5.0, 10.0]
            # Missing width_m
        })
        
        with pytest.raises(ValueError, match="Columns 'rate' and 'width_m' required"):
            ensure_rpm(df)


class TestAddUtilizationPercentile:
    """Test add_utilization_percentile function."""
    
    def test_computes_rpm_before_checking_columns(self):
        """Test that ensure_rpm is called before checking for rate_per_m_per_min column.
        
        Issue #556: This test ensures the fix works - rate_per_m_per_min should be
        computed from rate and width_m if missing, rather than raising an error.
        """
        df = pd.DataFrame({
            'rate': [5.0, 10.0, 15.0, 20.0],
            'width_m': [3.0, 3.0, 3.0, 3.0],
            'window_idx': [0, 0, 1, 1]
            # rate_per_m_per_min is missing - should be computed
        })
        
        result = add_utilization_percentile(df, cohort="window")
        
        # Should have computed rate_per_m_per_min
        assert 'rate_per_m_per_min' in result.columns
        assert 'util_percentile' in result.columns
        
        # Verify percentiles are computed (should be 0-100 range)
        assert result['util_percentile'].min() >= 0
        assert result['util_percentile'].max() <= 100
    
    def test_raises_when_window_idx_missing(self):
        """Test that ValueError is raised when window_idx is missing for window cohort."""
        df = pd.DataFrame({
            'rate': [5.0, 10.0],
            'width_m': [3.0, 3.0]
            # Missing window_idx
        })
        
        with pytest.raises(ValueError, match="Missing columns for cohort='window'"):
            add_utilization_percentile(df, cohort="window")
    
    def test_works_with_existing_rpm(self):
        """Test that function works when rate_per_m_per_min already exists."""
        df = pd.DataFrame({
            'rate': [5.0, 10.0],
            'width_m': [3.0, 3.0],
            'rate_per_m_per_min': [100.0, 200.0],
            'window_idx': [0, 0]
        })
        
        result = add_utilization_percentile(df, cohort="window")
        
        assert 'util_percentile' in result.columns
        # Should use existing rate_per_m_per_min values
        assert result['rate_per_m_per_min'].tolist() == [100.0, 200.0]
    
    def test_global_cohort_works(self):
        """Test that global cohort works without window_idx."""
        df = pd.DataFrame({
            'rate': [5.0, 10.0, 15.0],
            'width_m': [3.0, 3.0, 3.0]
        })
        
        result = add_utilization_percentile(df, cohort="global")
        
        assert 'util_percentile' in result.columns
        assert 'rate_per_m_per_min' in result.columns

