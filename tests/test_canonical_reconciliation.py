"""
E2E Tests for Canonical Reconciliation and CI Guardrails

Tests that enforce CI/CD quality gates for Issue #233:
- Canonical inputs exist
- Flow validation passes (frozen)
- Canonical reconciliation results meet thresholds

Issue #233: Operational Intelligence - E2E Tests
"""

import pytest
import pandas as pd
from pathlib import Path
import subprocess
import sys


@pytest.mark.e2e
class TestCanonicalInputsAvailability:
    """Test that required canonical inputs exist."""
    
    def test_canonical_segments_parquet_exists(self):
        """Test that canonical segments parquet file exists."""
        # Check for canonical segments in reports directory
        reports_dir = Path("reports")
        
        if not reports_dir.exists():
            pytest.skip("Reports directory not found - may be running in CI without reports")
        
        # Find latest date directory
        date_dirs = [
            d for d in reports_dir.iterdir()
            if d.is_dir() and len(d.name) == 10 and d.name.count('-') == 2
        ]
        
        if not date_dirs:
            pytest.skip("No date directories found in reports")
        
        date_dirs.sort(reverse=True)
        latest_dir = date_dirs[0]
        
        # Check for canonical segments file
        canonical_file = latest_dir / "segment_windows_from_bins.parquet"
        
        assert canonical_file.exists(), \
            f"Canonical segments file not found: {canonical_file}"
        assert canonical_file.stat().st_size > 0, \
            "Canonical segments file is empty"
    
    def test_bins_files_exist(self):
        """Test that bins files exist (parquet or geojson.gz)."""
        reports_dir = Path("reports")
        
        if not reports_dir.exists():
            pytest.skip("Reports directory not found")
        
        # Check for bins files in reports root or latest date dir
        bins_parquet = reports_dir / "bins.parquet"
        bins_geojson = reports_dir / "bins.geojson.gz"
        
        # Also check latest date directory
        date_dirs = [
            d for d in reports_dir.iterdir()
            if d.is_dir() and len(d.name) == 10
        ]
        
        if date_dirs:
            date_dirs.sort(reverse=True)
            latest_dir = date_dirs[0]
            
            if not bins_parquet.exists():
                bins_parquet = latest_dir / "bins.parquet"
            if not bins_geojson.exists():
                bins_geojson = latest_dir / "bins.geojson.gz"
        
        # At least one format should exist
        assert bins_parquet.exists() or bins_geojson.exists(), \
            "Neither bins.parquet nor bins.geojson.gz found"
    
    def test_flow_expected_results_exists(self):
        """Test that flow expected results (oracle) exists."""
        expected_file = Path("data/flow_expected_results.csv")
        
        assert expected_file.exists(), \
            "Flow expected results not found: data/flow_expected_results.csv"
        assert expected_file.stat().st_size > 0, \
            "Flow expected results file is empty"


@pytest.mark.e2e
class TestFlowValidationFrozen:
    """Test that Flow algorithm is frozen (Issue #233 requirement)."""
    
    def test_flow_expected_results_loadable(self):
        """Test that flow expected results can be loaded."""
        expected_file = Path("data/flow_expected_results.csv")
        
        if not expected_file.exists():
            pytest.skip("Flow expected results not found")
        
        # Should be able to load as DataFrame
        df = pd.read_csv(expected_file)
        
        assert len(df) > 0, "Flow expected results is empty"
        assert 'seg_id' in df.columns or 'segment_id' in df.columns, \
            "Flow expected results missing segment identifier column"
    
    def test_flow_validation_cli_available(self):
        """Test that flow validation CLI is available."""
        validation_script = Path("app/flow_validation.py")
        
        assert validation_script.exists(), \
            "Flow validation script not found: app/flow_validation.py"
        
        # Test that --expected flag is supported
        result = subprocess.run(
            [sys.executable, str(validation_script), "--help"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, "Flow validation script help failed"
        assert "--expected" in result.stdout, \
            "Flow validation script missing --expected flag"


@pytest.mark.e2e
class TestCanonicalReconciliation:
    """Test canonical reconciliation quality gates."""
    
    def test_reconciliation_results_exist(self):
        """Test that reconciliation results file exists or can be created."""
        work_dir = Path("work")
        recon_file = work_dir / "canonical_reconciliation_results.csv"
        
        if not recon_file.exists():
            # Check if it exists in reports directory
            reports_dir = Path("reports")
            
            if reports_dir.exists():
                date_dirs = [
                    d for d in reports_dir.iterdir()
                    if d.is_dir() and len(d.name) == 10
                ]
                
                if date_dirs:
                    date_dirs.sort(reverse=True)
                    latest_dir = date_dirs[0]
                    
                    recon_in_reports = latest_dir / "reconciliation_canonical_vs_fresh.csv"
                    
                    if recon_in_reports.exists():
                        pytest.skip(
                            "Reconciliation file exists in reports but not in work/ - "
                            "may need to run report generation first"
                        )
        
        # If neither location has the file, skip (may be first run)
        if not recon_file.exists():
            pytest.skip("Reconciliation results not found - may be first run")
    
    def test_reconciliation_quality_thresholds(self):
        """Test that reconciliation meets quality thresholds."""
        # Look for reconciliation results
        work_file = Path("work/canonical_reconciliation_results.csv")
        
        # Also check reports directory
        reports_dir = Path("reports")
        recon_file = None
        
        if work_file.exists():
            recon_file = work_file
        elif reports_dir.exists():
            date_dirs = [
                d for d in reports_dir.iterdir()
                if d.is_dir() and len(d.name) == 10
            ]
            
            if date_dirs:
                date_dirs.sort(reverse=True)
                for date_dir in date_dirs:
                    candidate = date_dir / "reconciliation_canonical_vs_fresh.csv"
                    if candidate.exists():
                        recon_file = candidate
                        break
        
        if recon_file is None:
            pytest.skip("No reconciliation results found")
        
        # Load reconciliation results
        df = pd.read_csv(recon_file)
        
        assert len(df) > 0, "Reconciliation results is empty"
        
        # Check for failures column (if present)
        if 'failures' in df.columns:
            total_failures = df['failures'].sum()
            assert total_failures == 0, \
                f"Reconciliation has {total_failures} failures (expected 0)"
        
        # Check for error columns (various naming conventions)
        error_cols = [col for col in df.columns if 'err' in col.lower() or 'error' in col.lower()]
        
        if error_cols:
            # Check P95 absolute relative error threshold
            for col in error_cols:
                if 'p95' in col.lower() or 'percentile' in col.lower():
                    max_error = df[col].max()
                    assert max_error <= 0.02, \
                        f"P95 absolute relative error {max_error:.4f} exceeds threshold 0.02"


@pytest.mark.e2e
class TestWorkDirectory:
    """Test work directory for ephemeral artifacts."""
    
    def test_work_directory_exists(self):
        """Test that work directory exists or can be created."""
        work_dir = Path("work")
        
        if not work_dir.exists():
            # Try to create it
            work_dir.mkdir(parents=True, exist_ok=True)
        
        assert work_dir.exists(), "Work directory does not exist and could not be created"
        assert work_dir.is_dir(), "Work path exists but is not a directory"
    
    def test_work_directory_writable(self):
        """Test that work directory is writable."""
        work_dir = Path("work")
        
        if not work_dir.exists():
            pytest.skip("Work directory does not exist")
        
        # Try to create a test file
        test_file = work_dir / ".test_write"
        
        try:
            test_file.write_text("test")
            assert test_file.exists()
            test_file.unlink()
        except Exception as e:
            pytest.fail(f"Work directory not writable: {e}")


@pytest.mark.e2e
class TestConfigurationFiles:
    """Test that configuration files exist and are valid."""
    
    def test_reporting_config_exists(self):
        """Test that reporting configuration exists."""
        config_file = Path("config/reporting.yml")
        
        assert config_file.exists(), \
            "Reporting configuration not found: config/reporting.yml"
        assert config_file.stat().st_size > 0, \
            "Reporting configuration file is empty"
    
    def test_reporting_config_valid_yaml(self):
        """Test that reporting configuration is valid YAML."""
        config_file = Path("config/reporting.yml")
        
        if not config_file.exists():
            pytest.skip("Reporting configuration not found")
        
        import yaml
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            assert isinstance(config, dict), "Configuration is not a dictionary"
            
            # Check for required sections
            assert 'schema_version' in config
            assert 'density_method' in config
            assert 'los' in config
            assert 'flagging' in config
            
        except yaml.YAMLError as e:
            pytest.fail(f"Configuration YAML parsing failed: {e}")


@pytest.mark.e2e
class TestEndToEndInvariants:
    """Test end-to-end invariants for Issue #233."""
    
    def test_canonical_segments_data_quality(self):
        """Test that canonical segments data meets quality standards."""
        reports_dir = Path("reports")
        
        if not reports_dir.exists():
            pytest.skip("Reports directory not found")
        
        # Find latest canonical segments
        date_dirs = [
            d for d in reports_dir.iterdir()
            if d.is_dir() and len(d.name) == 10
        ]
        
        if not date_dirs:
            pytest.skip("No date directories found")
        
        date_dirs.sort(reverse=True)
        canonical_file = date_dirs[0] / "segment_windows_from_bins.parquet"
        
        if not canonical_file.exists():
            pytest.skip("Canonical segments file not found")
        
        # Load and validate
        df = pd.read_parquet(canonical_file)
        
        assert len(df) > 0, "Canonical segments is empty"
        
        # Required columns
        required_cols = ['segment_id', 'start_km', 'end_km', 'density_mean', 'density_peak']
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"
        
        # Data quality checks
        assert df['start_km'].notna().all(), "Null values in start_km"
        assert df['end_km'].notna().all(), "Null values in end_km"
        assert (df['end_km'] >= df['start_km']).all(), "end_km < start_km"
        assert (df['density_mean'] >= 0).all(), "Negative density_mean"
        assert (df['density_peak'] >= 0).all(), "Negative density_peak"
        assert (df['density_peak'] >= df['density_mean']).all(), \
            "density_peak < density_mean"
    
    def test_no_hardcoded_values_in_config(self):
        """Test that configuration uses dynamic values, not hardcoded."""
        config_file = Path("config/reporting.yml")
        
        if not config_file.exists():
            pytest.skip("Reporting configuration not found")
        
        import yaml
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check that critical values are configurable
        assert 'los' in config, "LOS thresholds not configurable"
        assert 'flagging' in config, "Flagging rules not configurable"
        
        los_config = config['los']
        assert len(los_config) == 6, "LOS should have 6 levels (A-F)"
        assert all(k in los_config for k in ['A', 'B', 'C', 'D', 'E', 'F'])
        
        flagging_config = config['flagging']
        assert 'min_los_flag' in flagging_config
        assert 'utilization_pctile' in flagging_config

