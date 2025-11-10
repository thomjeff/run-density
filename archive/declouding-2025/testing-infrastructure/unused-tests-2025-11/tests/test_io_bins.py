"""
Unit Tests for Canonical Bins I/O Module

Tests bins loading, normalization, and metadata extraction.
Uses minimal fixtures to keep tests fast.

Issue #233: Operational Intelligence - Unit Tests
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from app.io_bins import (
    normalize_bins_dtypes,
    compute_bin_length,
    validate_bins_schema,
    get_bins_metadata
)


@pytest.mark.fast
class TestBinsNormalization:
    """Tests for bins data normalization."""
    
    def test_normalize_bins_dtypes_basic(self):
        """Test basic dtype normalization."""
        df = pd.DataFrame({
            'segment_id': ['A1', 'A1', 'B1'],
            'start_km': ['0.0', '0.1', '0.0'],  # String that should be float
            'end_km': ['0.1', '0.2', '0.1'],
            'density_mean': [0.5, 0.6, 0.7],
            'density_peak': [0.8, 0.9, 1.0],
            'n_bins': [10, 15, 20]
        })
        
        result = normalize_bins_dtypes(df)
        
        assert result['segment_id'].dtype == 'string'
        assert result['start_km'].dtype == 'float64'
        assert result['end_km'].dtype == 'float64'
        assert result['density_mean'].dtype == 'float64'
        assert result['density_peak'].dtype == 'float64'
        assert result['n_bins'].dtype == 'Int64'
    
    def test_normalize_bins_dtypes_missing_columns(self):
        """Test normalization with missing optional columns."""
        df = pd.DataFrame({
            'segment_id': ['A1'],
            'start_km': [0.0]
        })
        
        # Should not crash if optional columns missing
        result = normalize_bins_dtypes(df)
        
        assert result['segment_id'].dtype == 'string'
        assert result['start_km'].dtype == 'float64'
    
    def test_normalize_bins_dtypes_timestamps(self):
        """Test timestamp column conversion."""
        df = pd.DataFrame({
            'segment_id': ['A1'],
            't_start': ['2025-01-01 07:00:00'],
            't_end': ['2025-01-01 07:01:00']
        })
        
        result = normalize_bins_dtypes(df)
        
        assert pd.api.types.is_datetime64_any_dtype(result['t_start'])
        assert pd.api.types.is_datetime64_any_dtype(result['t_end'])


@pytest.mark.fast
class TestBinLengthComputation:
    """Tests for bin length computation."""
    
    def test_compute_bin_length_basic(self):
        """Test basic bin length computation."""
        df = pd.DataFrame({
            'start_km': [0.0, 0.1, 1.0],
            'end_km': [0.1, 0.2, 1.5]
        })
        
        result = compute_bin_length(df)
        
        assert 'bin_len_m' in result.columns
        assert result['bin_len_m'].tolist() == pytest.approx([100.0, 100.0, 500.0])
    
    def test_compute_bin_length_negative_handling(self):
        """Test that negative lengths are clipped to zero."""
        df = pd.DataFrame({
            'start_km': [0.2, 0.5],
            'end_km': [0.1, 0.3]  # End before start
        })
        
        result = compute_bin_length(df)
        
        # Should clip to 0, not allow negative
        assert all(result['bin_len_m'] >= 0)
    
    def test_compute_bin_length_missing_columns(self):
        """Test bin length computation with missing columns."""
        df = pd.DataFrame({
            'segment_id': ['A1']
        })
        
        result = compute_bin_length(df)
        
        # Should not crash, just skip computation
        assert 'bin_len_m' not in result.columns


@pytest.mark.fast
class TestBinsSchemaValidation:
    """Tests for bins schema validation."""
    
    def test_validate_bins_schema_valid(self):
        """Test validation with valid schema."""
        df = pd.DataFrame({
            'segment_id': ['A1'],
            'start_km': [0.0],
            'end_km': [0.1],
            'density_mean': [0.5],
            'density_peak': [0.8]
        })
        
        assert validate_bins_schema(df) is True
    
    def test_validate_bins_schema_missing_required(self):
        """Test validation with missing required columns."""
        df = pd.DataFrame({
            'segment_id': ['A1'],
            'start_km': [0.0]
            # Missing: end_km, density_mean, density_peak
        })
        
        assert validate_bins_schema(df) is False
    
    def test_validate_bins_schema_extra_columns(self):
        """Test validation with extra columns (should still pass)."""
        df = pd.DataFrame({
            'segment_id': ['A1'],
            'start_km': [0.0],
            'end_km': [0.1],
            'density_mean': [0.5],
            'density_peak': [0.8],
            'extra_col': ['extra']  # Extra column should be fine
        })
        
        assert validate_bins_schema(df) is True


@pytest.mark.fast
class TestBinsMetadata:
    """Tests for bins metadata extraction."""
    
    def test_get_bins_metadata_basic(self):
        """Test basic metadata extraction."""
        df = pd.DataFrame({
            'segment_id': ['A1', 'A1', 'B1'],
            'start_km': [0.0, 0.1, 0.0],
            'end_km': [0.1, 0.2, 0.5],
            'density_mean': [0.5, 0.6, 0.4],
            'density_peak': [0.8, 0.9, 0.7],
            'bin_len_m': [100.0, 100.0, 500.0]
        })
        
        metadata = get_bins_metadata(df)
        
        assert metadata['total_bins'] == 3
        assert metadata['unique_segments'] == 2
        assert metadata['density_range']['min_mean'] == pytest.approx(0.4)
        assert metadata['density_range']['max_peak'] == pytest.approx(0.9)
        assert metadata['distance_range']['min_km'] == pytest.approx(0.0)
        assert metadata['distance_range']['max_km'] == pytest.approx(0.5)
        assert metadata['bin_length_stats']['mean_m'] == pytest.approx(233.33, rel=0.01)
    
    def test_get_bins_metadata_with_timestamps(self):
        """Test metadata extraction with timestamp columns."""
        df = pd.DataFrame({
            'segment_id': ['A1'],
            'start_km': [0.0],
            'end_km': [0.1],
            'density_mean': [0.5],
            'density_peak': [0.8],
            't_start': pd.to_datetime(['2025-01-01 07:00:00']),
            't_end': pd.to_datetime(['2025-01-01 07:01:00'])
        })
        
        metadata = get_bins_metadata(df)
        
        assert 'time_range' in metadata
        assert metadata['time_range']['start'] is not None
        assert metadata['time_range']['end'] is not None
    
    def test_get_bins_metadata_empty_dataframe(self):
        """Test metadata extraction with empty DataFrame."""
        df = pd.DataFrame(columns=[
            'segment_id', 'start_km', 'end_km',
            'density_mean', 'density_peak'
        ])
        
        metadata = get_bins_metadata(df)
        
        assert metadata['total_bins'] == 0
        assert metadata['unique_segments'] == 0


@pytest.mark.fast
class TestBinsIntegration:
    """Integration tests for bins I/O workflow."""
    
    def test_full_normalization_workflow(self):
        """Test complete normalization and validation workflow."""
        # Create raw data as it might come from file
        raw_df = pd.DataFrame({
            'segment_id': ['A1', 'A1', 'B1'],
            'start_km': ['0.0', '0.1', '0.0'],  # String
            'end_km': ['0.1', '0.2', '0.5'],    # String
            'density_mean': [0.5, 0.6, 0.4],
            'density_peak': [0.8, 0.9, 0.7],
            'n_bins': [10, 15, 20]
        })
        
        # Normalize dtypes
        normalized = normalize_bins_dtypes(raw_df)
        
        # Compute bin length
        with_length = compute_bin_length(normalized)
        
        # Validate schema
        assert validate_bins_schema(with_length) is True
        
        # Extract metadata
        metadata = get_bins_metadata(with_length)
        
        assert metadata['total_bins'] == 3
        assert metadata['unique_segments'] == 2
        assert 'bin_len_m' in with_length.columns
        assert with_length['bin_len_m'].tolist() == pytest.approx([100.0, 100.0, 500.0])
    
    def test_data_quality_checks(self):
        """Test data quality after normalization."""
        df = pd.DataFrame({
            'segment_id': ['A1', 'A1'],
            'start_km': [0.0, 0.1],
            'end_km': [0.1, 0.2],
            'density_mean': [0.5, 0.6],
            'density_peak': [0.8, 0.9]
        })
        
        normalized = normalize_bins_dtypes(df)
        with_length = compute_bin_length(normalized)
        
        # Check no null values in critical columns
        assert not normalized['segment_id'].isnull().any()
        assert not normalized['start_km'].isnull().any()
        assert not normalized['end_km'].isnull().any()
        
        # Check bin lengths are positive
        assert all(with_length['bin_len_m'] > 0)
        
        # Check densities are non-negative
        assert all(normalized['density_mean'] >= 0)
        assert all(normalized['density_peak'] >= 0)

