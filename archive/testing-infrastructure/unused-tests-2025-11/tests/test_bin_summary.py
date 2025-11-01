"""
Tests for bin_summary.py module

Tests the bin summary generation functionality including:
- Configuration loading
- Data filtering and flagging
- JSON output generation
- Error handling
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import numpy as np

from app.bin_summary import (
    BinSummaryConfig,
    load_flagging_config,
    format_time_for_display,
    load_bins_data,
    generate_bin_summary,
    save_bin_summary,
    generate_bin_summary_from_file
)


class TestBinSummary(unittest.TestCase):
    """Test cases for bin summary module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_bins_data = pd.DataFrame({
            "segment_id": ["A1", "A1", "A1", "A2", "A2"],
            "start_km": [0.0, 0.2, 0.4, 0.0, 0.2],
            "end_km": [0.2, 0.4, 0.6, 0.2, 0.4],
            "t_start": ["2025-10-23T07:00:00Z", "2025-10-23T07:02:00Z", "2025-10-23T07:04:00Z", 
                       "2025-10-23T07:00:00Z", "2025-10-23T07:02:00Z"],
            "t_end": ["2025-10-23T07:02:00Z", "2025-10-23T07:04:00Z", "2025-10-23T07:06:00Z",
                     "2025-10-23T07:02:00Z", "2025-10-23T07:04:00Z"],
            "density": [0.1, 0.8, 0.3, 0.2, 0.9],  # Mix of low and high density
            "rate": [1.0, 5.0, 2.0, 1.5, 6.0],
            "los_class": ["A", "C", "A", "A", "C"],
            "density_peak": [0.1, 0.8, 0.3, 0.2, 0.9],  # Required for bin intelligence
            "bin_len_m": [200.0, 200.0, 200.0, 200.0, 200.0]  # Required for length filtering
        })
    
    def test_format_time_for_display(self):
        """Test time formatting function."""
        # Test valid ISO string
        result = format_time_for_display("2025-10-23T07:30:00Z")
        self.assertEqual(result, "07:30")
        
        # Test invalid format
        result = format_time_for_display("invalid-time")
        self.assertEqual(result, "invalid-time")
    
    def test_load_bins_data(self):
        """Test bin data loading."""
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            self.sample_bins_data.to_parquet(tmp.name)
            
            try:
                result = load_bins_data(tmp.name)
                self.assertEqual(len(result), 5)
                self.assertIn("segment_id", result.columns)
                self.assertIn("density", result.columns)
            finally:
                Path(tmp.name).unlink()
    
    def test_load_bins_data_missing_file(self):
        """Test error handling for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_bins_data("nonexistent.parquet")
    
    def test_load_bins_data_missing_columns(self):
        """Test error handling for missing required columns."""
        invalid_data = pd.DataFrame({"segment_id": ["A1"], "density": [0.1]})
        
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            invalid_data.to_parquet(tmp.name)
            
            try:
                with self.assertRaises(ValueError):
                    load_bins_data(tmp.name)
            finally:
                Path(tmp.name).unlink()
    
    @patch('app.bin_summary.load_reporting')
    def test_load_flagging_config(self, mock_load_reporting):
        """Test flagging configuration loading."""
        # Mock successful config loading
        mock_load_reporting.return_value = {
            "flagging": {
                "min_los_flag": "C",
                "utilization_pctile": 95,
                "require_min_bin_len_m": 10.0
            }
        }
        
        config = load_flagging_config()
        self.assertEqual(config.min_los_flag, "C")
        self.assertEqual(config.utilization_pctile, 95)
        self.assertEqual(config.require_min_bin_len_m, 10.0)
    
    @patch('app.bin_summary.load_reporting')
    def test_load_flagging_config_fallback(self, mock_load_reporting):
        """Test fallback to defaults when config not found."""
        mock_load_reporting.side_effect = FileNotFoundError("Config not found")
        
        config = load_flagging_config()
        self.assertEqual(config.min_los_flag, "C")  # Default value
        self.assertEqual(config.utilization_pctile, 95)  # Default value
    
    def test_generate_bin_summary(self):
        """Test bin summary generation."""
        from app.bin_intelligence import FlaggingConfig
        
        # Create flagging config
        flagging_config = FlaggingConfig(
            min_los_flag="C",
            utilization_pctile=95,
            require_min_bin_len_m=10.0,
            density_field="density"
        )
        
        # Generate summary
        summary = generate_bin_summary(self.sample_bins_data, flagging_config)
        
        # Verify structure
        self.assertIn("generated_at", summary)
        self.assertIn("summary", summary)
        self.assertIn("segments", summary)
        
        # Verify summary metadata
        self.assertEqual(summary["summary"]["total_bins"], 5)
        self.assertGreaterEqual(summary["summary"]["flagged_bins"], 0)
        
        # Verify segments structure
        self.assertIn("A1", summary["segments"])
        self.assertIn("A2", summary["segments"])
        
        # Verify segment metadata
        a1_segment = summary["segments"]["A1"]
        self.assertIn("meta", a1_segment)
        self.assertIn("bins", a1_segment)
        self.assertEqual(a1_segment["meta"]["total_bins"], 3)
    
    def test_save_bin_summary(self):
        """Test saving bin summary to JSON."""
        summary = {
            "generated_at": "2025-10-23T18:00:00Z",
            "summary": {"total_bins": 5, "flagged_bins": 2, "segments_with_flags": 1},
            "segments": {"A1": {"meta": {"total_bins": 3, "flagged_bins": 1}, "bins": []}}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            try:
                save_bin_summary(summary, tmp.name)
                
                # Verify file was created and contains valid JSON
                with open(tmp.name, 'r') as f:
                    loaded = json.load(f)
                
                self.assertEqual(loaded["summary"]["total_bins"], 5)
                self.assertEqual(loaded["summary"]["flagged_bins"], 2)
            finally:
                Path(tmp.name).unlink()
    
    def test_generate_bin_summary_from_file(self):
        """Test end-to-end file processing."""
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as input_file:
            self.sample_bins_data.to_parquet(input_file.name)
            
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as output_file:
                try:
                    summary = generate_bin_summary_from_file(
                        input_path=input_file.name,
                        output_path=output_file.name,
                        strict_mode=True
                    )
                    
                    # Verify summary was generated
                    self.assertIn("summary", summary)
                    self.assertEqual(summary["summary"]["total_bins"], 5)
                    
                    # Verify file was created
                    self.assertTrue(Path(output_file.name).exists())
                    
                finally:
                    Path(input_file.name).unlink()
                    Path(output_file.name).unlink()
    
    def test_strict_mode_error_handling(self):
        """Test strict mode error handling."""
        with self.assertRaises(FileNotFoundError):
            generate_bin_summary_from_file(
                input_path="nonexistent.parquet",
                output_path="output.json",
                strict_mode=True
            )
    
    def test_lenient_mode_error_handling(self):
        """Test lenient mode error handling."""
        summary = generate_bin_summary_from_file(
            input_path="nonexistent.parquet",
            output_path="output.json",
            strict_mode=False
        )
        
        # Should return error summary in lenient mode
        self.assertIn("error", summary)
        self.assertEqual(summary["summary"]["total_bins"], 0)


if __name__ == "__main__":
    unittest.main()
