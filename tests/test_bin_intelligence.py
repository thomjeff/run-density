"""
Unit Tests for Bin Intelligence Module

Tests operational intelligence flagging logic, severity assignment,
and segment-level rollup.

Issue #233: Operational Intelligence - Unit Tests
"""

import pytest
import pandas as pd

from app.bin_intelligence import (
    FlaggingConfig,
    compute_utilization_threshold,
    classify_flag_reason,
    classify_severity,
    get_severity_rank,
    apply_bin_flagging,
    get_flagged_bins,
    summarize_segment_flags,
    get_flagging_statistics
)


@pytest.mark.fast
class TestFlaggingConfig:
    """Tests for flagging configuration."""
    
    def test_flagging_config_defaults(self):
        """Test default flagging configuration."""
        config = FlaggingConfig()
        
        assert config.min_los_flag == 'C'
        assert config.utilization_pctile == 95
        assert config.require_min_bin_len_m == 10.0
        assert config.density_field == 'density_peak'
    
    def test_flagging_config_custom(self):
        """Test custom flagging configuration."""
        config = FlaggingConfig(
            min_los_flag='D',
            utilization_pctile=90,
            require_min_bin_len_m=20.0
        )
        
        assert config.min_los_flag == 'D'
        assert config.utilization_pctile == 90
        assert config.require_min_bin_len_m == 20.0
    
    def test_flagging_config_validation(self):
        """Test configuration validation."""
        # Invalid LOS should raise error
        with pytest.raises(ValueError):
            FlaggingConfig(min_los_flag='Z')
        
        # Invalid percentile should raise error
        with pytest.raises(ValueError):
            FlaggingConfig(utilization_pctile=150)
        
        # Negative min length should raise error
        with pytest.raises(ValueError):
            FlaggingConfig(require_min_bin_len_m=-10.0)


@pytest.mark.fast
class TestUtilizationThreshold:
    """Tests for utilization threshold computation."""
    
    def test_compute_utilization_threshold_basic(self):
        """Test basic P95 computation."""
        df = pd.DataFrame({
            'density_peak': [0.1, 0.2, 0.3, 0.4, 0.5,
                            0.6, 0.7, 0.8, 0.9, 1.0]  # 10 values
        })
        
        p95 = compute_utilization_threshold(df, 'density_peak', 95)
        
        # P95 of this dataset should be 0.95
        assert p95 == pytest.approx(0.95, rel=0.01)
    
    def test_compute_utilization_threshold_percentiles(self):
        """Test different percentiles."""
        df = pd.DataFrame({
            'density_peak': list(range(1, 101))  # 1 to 100
        })
        
        p50 = compute_utilization_threshold(df, 'density_peak', 50)
        p75 = compute_utilization_threshold(df, 'density_peak', 75)
        p95 = compute_utilization_threshold(df, 'density_peak', 95)
        
        assert p50 < p75 < p95
        assert p50 == pytest.approx(50.5, rel=0.1)
        assert p95 == pytest.approx(95.0, rel=0.1)
    
    def test_compute_utilization_threshold_missing_field(self):
        """Test with missing density field."""
        df = pd.DataFrame({
            'other_field': [1, 2, 3]
        })
        
        result = compute_utilization_threshold(df, 'density_peak', 95)
        
        # Should return inf if field missing
        assert result == float('inf')


@pytest.mark.fast
class TestFlagClassification:
    """Tests for flag reason and severity classification."""
    
    def test_classify_flag_reason_all_cases(self):
        """Test all flag reason combinations."""
        assert classify_flag_reason(True, True) == 'BOTH'
        assert classify_flag_reason(True, False) == 'LOS_HIGH'
        assert classify_flag_reason(False, True) == 'UTILIZATION_HIGH'
        assert classify_flag_reason(False, False) == 'NONE'
    
    def test_classify_severity_all_cases(self):
        """Test all severity classifications."""
        assert classify_severity('BOTH') == 'CRITICAL'
        assert classify_severity('LOS_HIGH') == 'CAUTION'
        assert classify_severity('UTILIZATION_HIGH') == 'WATCH'
        assert classify_severity('NONE') == 'NONE'
    
    def test_get_severity_rank(self):
        """Test severity ranking."""
        assert get_severity_rank('CRITICAL') == 3
        assert get_severity_rank('CAUTION') == 2
        assert get_severity_rank('WATCH') == 1
        assert get_severity_rank('NONE') == 0
        
        # Unknown severity should return 0
        assert get_severity_rank('UNKNOWN') == 0
    
    def test_severity_ranking_order(self):
        """Test that severity ranks are properly ordered."""
        critical = get_severity_rank('CRITICAL')
        caution = get_severity_rank('CAUTION')
        watch = get_severity_rank('WATCH')
        none = get_severity_rank('NONE')
        
        assert critical > caution > watch > none


@pytest.mark.fast
class TestBinFlagging:
    """Tests for bin flagging logic."""
    
    def test_apply_bin_flagging_basic(self):
        """Test basic bin flagging."""
        df = pd.DataFrame({
            'segment_id': ['A1'] * 5,
            'start_km': [0.0, 0.1, 0.2, 0.3, 0.4],
            'end_km': [0.1, 0.2, 0.3, 0.4, 0.5],
            'density_peak': [0.3, 0.8, 1.2, 1.7, 2.5],  # A, B, C, D, E
            'bin_len_m': [100.0] * 5
        })
        
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=80)
        
        result = apply_bin_flagging(df, config)
        
        assert 'los' in result.columns
        assert 'severity' in result.columns
        assert 'is_flagged' in result.columns
        assert 'flag_reason' in result.columns
    
    def test_apply_bin_flagging_los_only(self):
        """Test flagging with LOS threshold only."""
        df = pd.DataFrame({
            'segment_id': ['A1'] * 3,
            'start_km': [0.0, 0.1, 0.2],
            'end_km': [0.1, 0.2, 0.3],
            'density_peak': [0.5, 1.0, 1.5],  # B, C, D
            'bin_len_m': [100.0] * 3
        })
        
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=99)
        
        result = apply_bin_flagging(df, config)
        
        # Should have 2 bins flagged (C and D)
        flagged = result[result['is_flagged']]
        assert len(flagged) == 2
        assert set(flagged['los']) == {'C', 'D'}
    
    def test_apply_bin_flagging_utilization_only(self):
        """Test flagging with utilization threshold only."""
        df = pd.DataFrame({
            'segment_id': ['A1'] * 10,
            'start_km': [i * 0.1 for i in range(10)],
            'end_km': [(i + 1) * 0.1 for i in range(10)],
            'density_peak': [i * 0.05 for i in range(10)],  # 0.0 to 0.45 (all < LOS C)
            'bin_len_m': [100.0] * 10
        })
        
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=90)
        
        result = apply_bin_flagging(df, config)
        
        # Should have 1 bin flagged (top 10%)
        flagged = result[result['is_flagged']]
        assert len(flagged) == 1
        assert flagged.iloc[0]['flag_reason'] == 'UTILIZATION_HIGH'
    
    def test_apply_bin_flagging_both_conditions(self):
        """Test flagging with both LOS and utilization."""
        df = pd.DataFrame({
            'segment_id': ['A1'] * 5,
            'start_km': [0.0, 0.1, 0.2, 0.3, 0.4],
            'end_km': [0.1, 0.2, 0.3, 0.4, 0.5],
            'density_peak': [0.5, 1.0, 1.5, 2.0, 3.0],  # B, C, D, E, F
            'bin_len_m': [100.0] * 5
        })
        
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=80)
        
        result = apply_bin_flagging(df, config)
        
        # Last bin (3.0) should be BOTH
        critical_bins = result[result['severity'] == 'CRITICAL']
        assert len(critical_bins) == 1
        assert critical_bins.iloc[0]['density_peak'] == 3.0


@pytest.mark.fast
class TestFlaggedBinsRetrieval:
    """Tests for retrieving flagged bins."""
    
    def test_get_flagged_bins_all(self):
        """Test getting all flagged bins."""
        df = pd.DataFrame({
            'is_flagged': [True, False, True, False, True],
            'severity': ['CRITICAL', 'NONE', 'CAUTION', 'NONE', 'WATCH']
        })
        
        flagged = get_flagged_bins(df)
        
        assert len(flagged) == 3
        assert set(flagged['severity']) == {'CRITICAL', 'CAUTION', 'WATCH'}
    
    def test_get_flagged_bins_filtered(self):
        """Test getting flagged bins filtered by severity."""
        df = pd.DataFrame({
            'is_flagged': [True, True, True, False],
            'severity': ['CRITICAL', 'CAUTION', 'WATCH', 'NONE']
        })
        
        critical_only = get_flagged_bins(df, severity_filter=['CRITICAL'])
        assert len(critical_only) == 1
        
        high_severity = get_flagged_bins(df, severity_filter=['CRITICAL', 'CAUTION'])
        assert len(high_severity) == 2


@pytest.mark.fast
class TestSegmentSummary:
    """Tests for segment-level rollup."""
    
    def test_summarize_segment_flags_basic(self):
        """Test basic segment summary."""
        df = pd.DataFrame({
            'segment_id': ['A1', 'A1', 'B1', 'B1'],
            'start_km': [0.0, 0.1, 0.0, 0.1],
            'end_km': [0.1, 0.2, 0.1, 0.2],
            'density_peak': [1.0, 1.5, 2.0, 2.5],
            'los': ['C', 'D', 'E', 'E'],
            'severity': ['CAUTION', 'CAUTION', 'CAUTION', 'CRITICAL'],
            'severity_rank': [2, 2, 2, 3],
            'flag_reason': ['LOS_HIGH', 'LOS_HIGH', 'LOS_HIGH', 'BOTH'],
            'is_flagged': [True, True, True, True]
        })
        
        summary = summarize_segment_flags(df)
        
        assert len(summary) == 2  # Two segments
        assert 'worst_los' in summary.columns
        assert 'severity' in summary.columns
        assert 'flagged_bin_count' in summary.columns
    
    def test_summarize_segment_flags_worst_bin_selection(self):
        """Test that worst bin is selected correctly."""
        df = pd.DataFrame({
            'segment_id': ['A1', 'A1', 'A1'],
            'start_km': [0.0, 0.1, 0.2],
            'end_km': [0.1, 0.2, 0.3],
            'density_peak': [1.0, 1.5, 2.0],
            'los': ['C', 'D', 'E'],
            'severity': ['CAUTION', 'CAUTION', 'CRITICAL'],
            'severity_rank': [2, 2, 3],
            'flag_reason': ['LOS_HIGH', 'LOS_HIGH', 'BOTH'],
            'is_flagged': [True, True, True]
        })
        
        summary = summarize_segment_flags(df)
        
        assert len(summary) == 1
        # Should select bin with highest severity (CRITICAL)
        assert summary.iloc[0]['severity'] == 'CRITICAL'
        assert summary.iloc[0]['worst_los'] == 'E'
        assert summary.iloc[0]['flagged_bin_count'] == 3


@pytest.mark.fast
class TestFlaggingStatistics:
    """Tests for flagging statistics."""
    
    def test_get_flagging_statistics(self):
        """Test flagging statistics extraction."""
        df = pd.DataFrame({
            'is_flagged': [True, True, False, False, True],
            'severity': ['CRITICAL', 'CAUTION', 'NONE', 'NONE', 'WATCH'],
            'severity_rank': [3, 2, 0, 0, 1],
            'flag_reason': ['BOTH', 'LOS_HIGH', 'NONE', 'NONE', 'UTILIZATION_HIGH'],
            'los': ['F', 'D', 'A', 'B', 'C'],
            'los_rank': [5, 3, 0, 1, 2],
            'density_peak': [3.0, 1.5, 0.3, 0.5, 1.2]
        })
        
        stats = get_flagging_statistics(df)
        
        assert stats['total_bins'] == 5
        assert stats['flagged_bins'] == 3
        assert stats['flagged_percentage'] == 60.0
        assert stats['worst_severity'] == 'CRITICAL'
        assert stats['worst_los'] == 'F'


@pytest.mark.fast
class TestFlaggingIntegration:
    """Integration tests for complete flagging workflow."""
    
    def test_full_flagging_workflow(self):
        """Test complete flagging workflow from raw data to summary."""
        # Create sample data
        df = pd.DataFrame({
            'segment_id': ['A1'] * 10,
            'start_km': [i * 0.1 for i in range(10)],
            'end_km': [(i + 1) * 0.1 for i in range(10)],
            'density_peak': [0.2, 0.4, 0.6, 0.8, 1.0,
                            1.2, 1.5, 1.8, 2.5, 3.5],
            'bin_len_m': [100.0] * 10
        })
        
        # Apply flagging
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=80)
        flagged_df = apply_bin_flagging(df, config)
        
        # Get statistics
        stats = get_flagging_statistics(flagged_df)
        
        # Get flagged bins
        flagged = get_flagged_bins(flagged_df)
        
        # Summarize by segment
        summary = summarize_segment_flags(flagged_df)
        
        # Assertions
        assert stats['total_bins'] == 10
        assert stats['flagged_bins'] > 0
        assert len(flagged) == stats['flagged_bins']
        assert len(summary) == 1  # One segment
        assert summary.iloc[0]['flagged_bin_count'] == stats['flagged_bins']

