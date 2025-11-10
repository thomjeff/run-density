"""
Integration Tests for Canonical Density Report Generation

Tests the complete report generation workflow with real canonical bins data.
These tests verify end-to-end integration of modules and data flow.

Issue #233: Operational Intelligence - Integration Tests
"""

import pytest
import pandas as pd
import json
from pathlib import Path
import tempfile
import shutil

from app.io_bins import load_bins, get_bins_metadata
from app.los import classify_bins_los
from app.bin_intelligence import (
    FlaggingConfig,
    apply_bin_flagging,
    get_flagged_bins,
    summarize_segment_flags,
    get_flagging_statistics
)
from app.canonical_density_report import (
    generate_executive_summary,
    generate_appendices,
    generate_tooltips_json
)


@pytest.fixture
def canonical_bins_df():
    """Fixture providing canonical bins data for testing."""
    # Use actual canonical bins from reports/2025-09-19/
    try:
        df = load_bins(reports_dir="reports")
        if df is not None and len(df) > 0:
            return df
    except Exception:
        pass
    
    # Fallback: Create synthetic canonical bins data
    return pd.DataFrame({
        'segment_id': ['A1', 'A1', 'A1', 'B1', 'B1', 'C1', 'C1', 'C1'],
        'seg_label': ['Segment A1', 'Segment A1', 'Segment A1',
                     'Segment B1', 'Segment B1',
                     'Segment C1', 'Segment C1', 'Segment C1'],
        'start_km': [0.0, 0.1, 0.2, 0.0, 0.1, 0.0, 0.1, 0.2],
        'end_km': [0.1, 0.2, 0.3, 0.1, 0.2, 0.1, 0.2, 0.3],
        'density_mean': [0.4, 0.5, 0.6, 0.8, 0.9, 1.2, 1.5, 1.8],
        'density_peak': [0.6, 0.8, 0.9, 1.1, 1.3, 1.6, 2.0, 2.5],
        'n_bins': [5, 6, 7, 8, 9, 10, 11, 12],
        't_start': pd.to_datetime(['2025-01-01 07:00:00'] * 8),
        't_end': pd.to_datetime(['2025-01-01 07:01:00'] * 8),
        'bin_len_m': [100.0] * 8
    })


@pytest.fixture
def temp_output_dir():
    """Fixture providing temporary output directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.mark.int
class TestCanonicalBinsLoading:
    """Integration tests for canonical bins loading."""
    
    def test_load_real_canonical_bins(self):
        """Test loading real canonical bins from reports directory."""
        df = load_bins(reports_dir="reports")
        
        if df is not None:
            # Should have canonical bins data
            assert len(df) > 0
            assert 'segment_id' in df.columns
            assert 'density_peak' in df.columns
            assert 'start_km' in df.columns
            assert 'end_km' in df.columns
            
            # Should have bin_len_m computed
            assert 'bin_len_m' in df.columns
            assert all(df['bin_len_m'] >= 0)
    
    def test_bins_metadata_extraction(self, canonical_bins_df):
        """Test metadata extraction from canonical bins."""
        metadata = get_bins_metadata(canonical_bins_df)
        
        assert metadata['total_bins'] > 0
        assert metadata['unique_segments'] > 0
        assert metadata['density_range']['min_mean'] is not None
        assert metadata['density_range']['max_peak'] is not None


@pytest.mark.int
class TestBinFlaggingIntegration:
    """Integration tests for bin flagging with real data."""
    
    def test_full_flagging_pipeline(self, canonical_bins_df):
        """Test complete flagging pipeline with canonical bins."""
        config = FlaggingConfig(
            min_los_flag='C',
            utilization_pctile=95,
            require_min_bin_len_m=10.0
        )
        
        # Apply flagging
        result = apply_bin_flagging(canonical_bins_df, config)
        
        # Verify all expected columns exist
        assert 'los' in result.columns
        assert 'los_rank' in result.columns
        assert 'severity' in result.columns
        assert 'severity_rank' in result.columns
        assert 'is_flagged' in result.columns
        assert 'flag_reason' in result.columns
        
        # Verify data integrity
        assert len(result) > 0
        assert result['los'].isin(['A', 'B', 'C', 'D', 'E', 'F']).all()
        assert result['severity'].isin(['NONE', 'WATCH', 'CAUTION', 'CRITICAL']).all()
    
    def test_segment_rollup_integration(self, canonical_bins_df):
        """Test segment rollup with real canonical bins."""
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=80)
        
        # Apply flagging
        flagged_df = apply_bin_flagging(canonical_bins_df, config)
        
        # Get flagged bins
        flagged = get_flagged_bins(flagged_df)
        
        if len(flagged) > 0:
            # Summarize by segment
            summary = summarize_segment_flags(flagged_df)
            
            # Verify summary structure
            assert len(summary) > 0
            assert 'segment_id' in summary.columns
            assert 'worst_los' in summary.columns
            assert 'severity' in summary.columns
            assert 'flagged_bin_count' in summary.columns
            
            # Verify worst bin selection
            for _, row in summary.iterrows():
                assert row['flagged_bin_count'] > 0
                assert row['severity'] in ['WATCH', 'CAUTION', 'CRITICAL']


@pytest.mark.int
class TestReportGeneration:
    """Integration tests for report generation."""
    
    def test_executive_summary_generation(self, canonical_bins_df, temp_output_dir):
        """Test executive summary generation with real data."""
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=90)
        
        # Apply flagging
        flagged_df = apply_bin_flagging(canonical_bins_df, config)
        
        # Get statistics
        stats = get_flagging_statistics(flagged_df)
        
        # Summarize by segment
        summary = summarize_segment_flags(flagged_df)
        
        # Generate executive summary
        output_path = Path(temp_output_dir) / "executive-summary.md"
        
        test_config = {
            'schema_version': '1.1.0',
            'density_method': 'segments_from_bins'
        }
        
        success = generate_executive_summary(summary, test_config, stats, str(output_path))
        
        assert success is True
        assert output_path.exists()
        
        # Verify content
        content = output_path.read_text()
        assert 'Density Executive Summary' in content
        assert 'Schema Version' in content
        assert 'segments_from_bins' in content
        assert 'Key Metrics' in content
    
    def test_appendices_generation(self, canonical_bins_df, temp_output_dir):
        """Test appendix generation with flagged bins."""
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=80)
        
        # Apply flagging
        flagged_df = apply_bin_flagging(canonical_bins_df, config)
        
        # Get flagged bins
        flagged = get_flagged_bins(flagged_df)
        
        if len(flagged) > 0:
            # Generate appendices
            appendix_dir = Path(temp_output_dir) / "appendix"
            
            test_config = {
                'schema_version': '1.1.0',
                'density_method': 'segments_from_bins'
            }
            
            success = generate_appendices(flagged, test_config, str(appendix_dir))
            
            assert success is True
            assert appendix_dir.exists()
            
            # Verify appendix files created
            appendix_files = list(appendix_dir.glob('*.md'))
            assert len(appendix_files) > 0
            
            # Verify content of first appendix
            first_appendix = appendix_files[0]
            content = first_appendix.read_text()
            assert 'Appendix:' in content
            assert 'Bin-Level Detail' in content
    
    def test_tooltips_json_generation(self, canonical_bins_df, temp_output_dir):
        """Test tooltips JSON generation with flagged bins."""
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=85)
        
        # Apply flagging
        flagged_df = apply_bin_flagging(canonical_bins_df, config)
        
        # Get flagged bins
        flagged = get_flagged_bins(flagged_df)
        
        if len(flagged) > 0:
            # Generate tooltips JSON
            output_path = Path(temp_output_dir) / "tooltips.json"
            
            test_config = {
                'schema_version': '1.1.0',
                'density_method': 'segments_from_bins'
            }
            
            success = generate_tooltips_json(flagged, test_config, str(output_path))
            
            assert success is True
            assert output_path.exists()
            
            # Verify JSON structure
            with open(output_path, 'r') as f:
                data = json.load(f)
            
            assert 'tooltips' in data
            assert 'schema_version' in data
            assert 'density_method' in data
            assert len(data['tooltips']) > 0
            
            # Verify tooltip structure
            first_tooltip = data['tooltips'][0]
            assert 'segment_id' in first_tooltip
            assert 'los' in first_tooltip
            assert 'severity' in first_tooltip
            assert 'density_peak' in first_tooltip


@pytest.mark.int
class TestEndToEndWorkflow:
    """End-to-end integration tests for complete workflow."""
    
    def test_complete_report_generation_workflow(self, canonical_bins_df, temp_output_dir):
        """Test complete workflow from bins to reports."""
        # Configuration
        config = FlaggingConfig(
            min_los_flag='C',
            utilization_pctile=95,
            require_min_bin_len_m=10.0
        )
        
        test_config = {
            'schema_version': '1.1.0',
            'density_method': 'segments_from_bins'
        }
        
        # Step 1: Apply flagging
        flagged_df = apply_bin_flagging(canonical_bins_df, config)
        assert len(flagged_df) > 0
        
        # Step 2: Get statistics
        stats = get_flagging_statistics(flagged_df)
        assert stats['total_bins'] > 0
        
        # Step 3: Get flagged bins
        flagged = get_flagged_bins(flagged_df)
        
        # Step 4: Summarize by segment
        summary = summarize_segment_flags(flagged_df)
        
        # Step 5: Generate executive summary
        summary_path = Path(temp_output_dir) / "executive-summary.md"
        summary_success = generate_executive_summary(summary, test_config, stats, str(summary_path))
        assert summary_success is True
        
        # Step 6: Generate appendices (if flagged bins exist)
        if len(flagged) > 0:
            appendix_dir = Path(temp_output_dir) / "appendix"
            appendix_success = generate_appendices(flagged, test_config, str(appendix_dir))
            assert appendix_success is True
            
            # Step 7: Generate tooltips JSON
            tooltips_path = Path(temp_output_dir) / "tooltips.json"
            tooltips_success = generate_tooltips_json(flagged, test_config, str(tooltips_path))
            assert tooltips_success is True
        
        # Verify all outputs exist
        assert summary_path.exists()
        assert summary_path.stat().st_size > 0
    
    def test_workflow_with_no_flagged_bins(self):
        """Test workflow gracefully handles case with no flagged bins."""
        # Create data with no bins meeting thresholds
        df = pd.DataFrame({
            'segment_id': ['A1'] * 3,
            'start_km': [0.0, 0.1, 0.2],
            'end_km': [0.1, 0.2, 0.3],
            'density_peak': [0.2, 0.3, 0.4],  # All low density
            'bin_len_m': [100.0] * 3
        })
        
        config = FlaggingConfig(min_los_flag='C', utilization_pctile=99)
        
        # Apply flagging
        flagged_df = apply_bin_flagging(df, config)
        
        # Should have no flagged bins
        flagged = get_flagged_bins(flagged_df)
        assert len(flagged) == 0
        
        # Stats should reflect no flags
        stats = get_flagging_statistics(flagged_df)
        assert stats['flagged_bins'] == 0
        
        # Summary should be empty
        summary = summarize_segment_flags(flagged_df)
        assert len(summary) == 0
    
    def test_data_consistency_through_pipeline(self, canonical_bins_df):
        """Test that data remains consistent through the pipeline."""
        config = FlaggingConfig(min_los_flag='C')
        
        # Apply flagging
        flagged_df = apply_bin_flagging(canonical_bins_df, config)
        
        # Verify no bins lost
        assert len(flagged_df) == len(canonical_bins_df)
        
        # Verify original columns preserved
        for col in ['segment_id', 'start_km', 'end_km', 'density_peak']:
            if col in canonical_bins_df.columns:
                assert col in flagged_df.columns
                assert (flagged_df[col] == canonical_bins_df[col]).all()
        
        # Verify new columns added
        assert 'los' in flagged_df.columns
        assert 'severity' in flagged_df.columns
        assert 'is_flagged' in flagged_df.columns

