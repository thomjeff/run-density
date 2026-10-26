"""
End-to-End Tests for Runflow v2 API

Phase 8: E2E Testing & Validation (Issue #502)

Tests complete v2 workflow: API → validation → pipeline → outputs
Validates day isolation and same-day interactions.
"""

import pytest
import requests
import json
import time
import os
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import pandas as pd
from app.config.loader import load_analysis_context, AnalysisConfigError

# ============================================================================
# E2E Test Configuration - Issue #655: SSOT Configuration
# ============================================================================
# Centralized configuration for all test scenarios.
# Modify these values to change data files used across all tests.
# This aligns with SSOT principles where configuration is centralized.

# Base URL can be set via BASE_URL environment variable or pytest --base-url
# Defaults to http://localhost:8080 for local dev
# Use http://app:8080 when running in docker-compose network
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
TIMEOUT = 600  # 10 minutes for full analysis

# Data directory configuration (matches Postman structure)
# Base directory for data files (can be overridden via environment variable)
DATA_DIR = os.getenv("DATA_DIR", "/app/runflow/config")
DATA_SUBDIR = "e2e"  # Subdirectory containing test data files

# ============================================================================
# Data file configuration (SSOT - Issue #655, Issue #680)
# ============================================================================
# Centralized configuration for all E2E test scenarios.
# To change test data files, modify these values:
#   - segments_file: Change to use different segments (e.g., "segments.csv" or "segments_616.csv")
#   - flow_file: Change to use different flow data (e.g., "flow.csv" or "flow_616.csv")
#   - locations_file: Change locations file, or set to None if not needed
#
# All tests will automatically use these values via _build_base_payload().
# This ensures SSOT - single place to configure test data files.
E2E_CONFIG = {
    "data_dir": f"{DATA_DIR}/{DATA_SUBDIR}",  # Full path: base_dir/subdir
    "segments_file": "segments.csv",  # Segments CSV file
    "flow_file": "flow.csv",  # Flow CSV file
    "locations_file": "locations.csv",  # Locations CSV file (optional, can be None)
}

# ============================================================================
# Event Configuration (SSOT)
# ============================================================================
# Centralized event definitions with all metadata.
# Modify these values to change event configurations across all tests.
EVENT_CONFIG = {
    "elite": {
        "day": "sat",
        "start_time": 480,
        "event_duration_minutes": 45,
        "runners_file": "elite_runners.csv",
        "gpx_file": "elite.gpx"
    },
    "open": {
        "day": "sat",
        "start_time": 510,
        "event_duration_minutes": 75,
        "runners_file": "open_runners.csv",
        "gpx_file": "open.gpx"
    },
    "full": {
        "day": "sun",
        "start_time": 420,
        "event_duration_minutes": 390,
        "runners_file": "full_runners.csv",
        "gpx_file": "full.gpx"
    },
    "10k": {
        "day": "sun",
        "start_time": 460,
        "event_duration_minutes": 120,
        "runners_file": "10k_runners.csv",
        "gpx_file": "10k.gpx"
    },
    "half": {
        "day": "sun",
        "start_time": 440,
        "event_duration_minutes": 180,
        "runners_file": "half_runners.csv",
        "gpx_file": "half.gpx"
    },
}

# Predefined event groups for common scenarios
EVENT_GROUPS = {
    "sat": {
        "sat-elite": "elite",
        "sat-open": "open"
    },
    "sun": {
        "sun-all": "full, 10k, half"
    },
    "sat_sun": {
        "sat-elite": "elite",
        "sat-open": "open",
        "sun-all": "full, 10k, half"
    }
}

# Expected segment ID patterns per day (for day isolation validation)
EXPECTED_SEG_IDS = {
    "sat": {"N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "O1", "O2", "O3","O4","O5","O6","O7","O8","O9"},
    "sun": {"A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "D1", "D2",
            "E1", "E2", "F1", "G1", "H1", "I1", "J1", "J2", "J3", "J4", "J5", "K1",
            "L1", "L2", "M1", "M2"}
}


class TestV2E2EScenarios:
    """E2E tests for v2 analysis scenarios."""
    
    @staticmethod
    def _build_base_payload(
        description: str,
        event_names: List[str],
        event_group: Optional[Dict[str, str]] = None,
        enable_audit: str = "n"  # Default to "n", user can override with "y"
    ) -> Dict[str, Any]:
        """
        Build base payload using centralized E2E configuration (Issue #655: SSOT).
        
        Args:
            description: Test scenario description
            event_names: List of event names (e.g., ["elite", "open"])
            event_group: Optional event grouping dictionary (or use EVENT_GROUPS)
            enable_audit: Audit enablement flag ("n" default, "y" to enable)
            
        Returns:
            Complete payload dictionary ready for API request
            
        Example:
            payload = _build_base_payload(
                "Saturday test",
                ["elite", "open"],
                EVENT_GROUPS["sat"]
            )
        """
        # Build events from names using centralized config
        events = []
        for name in event_names:
            if name not in EVENT_CONFIG:
                raise ValueError(
                    f"Event '{name}' not found in EVENT_CONFIG. "
                    f"Available events: {list(EVENT_CONFIG.keys())}"
                )
            config = EVENT_CONFIG[name]
            events.append({
                "name": name,
                "day": config["day"],
                "start_time": config["start_time"],
                "event_duration_minutes": config["event_duration_minutes"],
                "runners_file": config["runners_file"],
                "gpx_file": config["gpx_file"]
            })
        
        payload = {
            "description": description,
            "data_dir": E2E_CONFIG["data_dir"],
            "segments_file": E2E_CONFIG["segments_file"],
            "flow_file": E2E_CONFIG["flow_file"],
            "locations_file": E2E_CONFIG.get("locations_file"),
            "enableAudit": enable_audit,
        }
        
        if event_group:
            payload["event_group"] = event_group
        
        payload["events"] = events
        return payload
    
    def _make_analyze_request(self, base_url: str, payload: Dict[str, Any], timeout: int = None) -> Dict[str, Any]:
        """Make POST request to /runflow/v2/analyze and return response.
        
        Issue #554: API now returns immediately and runs analysis in background.
        This method only returns the immediate response with run_id.
        """
        if timeout is None:
            timeout = TIMEOUT
        response = requests.post(
            f"{base_url}/runflow/v2/analyze",
            json=payload,
            timeout=timeout
        )
        
        assert response.status_code == 200, f"Request failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert "run_id" in data, "Response missing run_id"
        assert "status" in data, "Response missing status"
        assert data["status"] == "success", f"Analysis failed: {data}"
        
        return data
    
    def _wait_for_analysis_completion(self, run_id: str, days: List[str], max_wait_seconds: int = 600) -> None:
        """Wait for background analysis to complete by polling for metadata.json files.
        
        Issue #554: After API returns immediately, we need to wait for background analysis.
        Issue #620: Also verify report files exist to avoid race conditions with filesystem sync.
        
        Args:
            run_id: Run ID to wait for
            days: List of day codes (e.g., ["sat", "sun"])
            max_wait_seconds: Maximum time to wait (default 10 minutes = 600 seconds)
        """
        run_dir = self._get_run_directory(run_id)
        start_time = time.time()
        poll_interval = 2  # Check every 2 seconds
        last_log_time = start_time
        expected_max_seconds = 600  # 10 minutes expected
        
        while time.time() - start_time < max_wait_seconds:
            # Check if all day metadata.json files exist (indicates completion)
            all_complete = True
            for day in days:
                metadata_path = run_dir / day / "metadata.json"
                if not metadata_path.exists():
                    all_complete = False
                    break
                
                # Issue #620: Also verify critical report files exist to avoid race conditions
                density_path = run_dir / day / "reports" / "Density.md"
                flow_path = run_dir / day / "reports" / "Flow.csv"
                if not density_path.exists() or not flow_path.exists():
                    all_complete = False
                    break
            
            if all_complete:
                # Add small delay to ensure filesystem sync completes
                time.sleep(0.5)
                elapsed = time.time() - start_time
                
                # Warn if analysis took longer than expected
                if elapsed > expected_max_seconds:
                    print(f"⚠️  Analysis completed in {elapsed:.1f}s (expected < {expected_max_seconds}s)")
                else:
                    print(f"✅ Analysis completed in {elapsed:.1f}s")
                return
            
            # Log progress every 30 seconds
            if time.time() - last_log_time >= 30:
                elapsed = time.time() - start_time
                print(f"⏳ Waiting for analysis to complete... ({elapsed:.0f}s elapsed)")
                last_log_time = time.time()
            
            time.sleep(poll_interval)
        
        # Timeout - check what's missing
        missing = []
        for day in days:
            metadata_path = run_dir / day / "metadata.json"
            if not metadata_path.exists():
                missing.append(f"{day}/metadata.json")
        
        raise TimeoutError(
            f"Analysis did not complete within {max_wait_seconds}s. "
            f"Missing metadata files: {missing}"
        )
    
    def test_debug_ping(self, base_url, wait_for_server):
        """Debug test to verify coverage instrumentation is working.
        
        This simple test hits a minimal route in main.py to confirm
        that server-side code execution is being captured by coverage.
        """
        response = requests.get(f"{base_url}/debug", timeout=10)
        assert response.status_code == 200, f"Debug ping failed with {response.status_code}: {response.text}"
        data = response.json()
        assert data == {"ping": "pong"}, f"Unexpected response: {data}"
    
    def _get_run_directory(self, run_id: str) -> Path:
        """Get run directory path."""
        # Issue #682: Use centralized get_run_directory() for correct path
        from app.utils.run_id import get_run_directory
        return get_run_directory(run_id)

    def _require_analysis_context(self, run_id: str, payload: Dict[str, Any]) -> None:
        """Load analysis.json via new loader and validate required config fields."""
        run_dir = self._get_run_directory(run_id)
        try:
            analysis_context = load_analysis_context(run_dir)
        except FileNotFoundError as exc:
            raise AssertionError(f"analysis.json missing for run_id {run_id}") from exc
        except AnalysisConfigError as exc:
            raise AssertionError(f"analysis.json invalid for run_id {run_id}: {exc}") from exc

        analysis_config = analysis_context.analysis_config
        assert analysis_config.get("data_dir"), "analysis.json missing data_dir"
        assert analysis_config.get("segments_file") == payload.get("segments_file"), \
            "analysis.json segments_file does not match request payload"
        assert analysis_config.get("flow_file") == payload.get("flow_file"), \
            "analysis.json flow_file does not match request payload"
        if payload.get("locations_file") is not None:
            assert analysis_config.get("locations_file") == payload.get("locations_file"), \
                "analysis.json locations_file does not match request payload"

        data_files = analysis_config.get("data_files", {})
        for required_key in ("segments", "flow"):
            assert data_files.get(required_key), f"analysis.json missing data_files.{required_key}"
        if payload.get("locations_file") is not None:
            assert data_files.get("locations"), "analysis.json missing data_files.locations"

        runners_map = data_files.get("runners", {})
        gpx_map = data_files.get("gpx", {})
        for event in payload.get("events", []):
            name = event.get("name")
            assert name, "Event name missing in request payload"
            assert runners_map.get(name) or runners_map.get(name.lower()), \
                f"analysis.json missing data_files.runners entry for event '{name}'"
            assert gpx_map.get(name) or gpx_map.get(name.lower()), \
                f"analysis.json missing data_files.gpx entry for event '{name}'"
    
    def _verify_outputs_exist(self, run_id: str, day: str, scenario: str = None) -> Dict[str, Path]:
        """Verify that expected output files exist for a day.
        
        Includes all v2 UI artifacts required by the dashboard.
        """
        run_dir = self._get_run_directory(run_id)
        day_dir = run_dir / day
        
        expected_files = {
            # Report files
            "density_md": day_dir / "reports" / "Density.md",
            "flow_csv": day_dir / "reports" / "Flow.csv",
            # Issue #600: Flow.md deprecated (only Flow.csv used)
            # Issue #627: {day}_fz.parquet may not exist if no zones detected (optional)
            "flow_zones_parquet": day_dir / "reports" / f"{day}_fz.parquet",
            "bins_parquet": day_dir / "bins" / "bins.parquet",
            "metadata_json": day_dir / "metadata.json",
            
            # UI artifacts (v2 minimum contract)
            # Issue #574: UI artifacts organized in subdirectories
            "meta_json": day_dir / "ui" / "metadata" / "meta.json",
            "segment_metrics_json": day_dir / "ui" / "metrics" / "segment_metrics.json",
            "flags_json": day_dir / "ui" / "metrics" / "flags.json",
            "flow_json": day_dir / "ui" / "geospatial" / "flow.json",
            "schema_density_json": day_dir / "ui" / "metadata" / "schema_density.json",
            "health_json": day_dir / "ui" / "metadata" / "health.json",
            "segments_geojson": day_dir / "ui" / "geospatial" / "segments.geojson",
            "captions_json": day_dir / "ui" / "visualizations" / "captions.json",
        }
        
        # Locations.csv may not exist for all days (e.g., SAT)
        locations_csv = day_dir / "reports" / "Locations.csv"
        if locations_csv.exists():
            expected_files["locations_csv"] = locations_csv
        
        # Verify heatmaps directory exists and contains at least one PNG
        heatmaps_dir = day_dir / "ui" / "heatmaps"
        if heatmaps_dir.exists():
            png_files = list(heatmaps_dir.glob("*.png"))
            if len(png_files) > 0:
                expected_files["heatmaps_dir"] = heatmaps_dir
        
        # Verify all expected files exist (except optional files)
        missing = []
        optional_files = ["flow_zones_parquet"]  # Issue #627: {day}_fz.parquet is optional if no zones
        for name, path in expected_files.items():
            if not path.exists():
                if name not in optional_files:
                    missing.append(f"{name}: {path}")
        
        assert not missing, f"Missing output files for {day}:\n" + "\n".join(missing)
        
        return expected_files
    
    def _verify_audit_files(self, run_id: str, day: str) -> Path:
        """Verify that audit Parquet file exists and is valid.
        
        Issue #607: Audit files are now stored as single Parquet file per day.
        
        Args:
            run_id: Run ID to check
            day: Day code (e.g., "sat", "sun")
            
        Returns:
            Path to the audit Parquet file
            
        Raises:
            AssertionError if audit file is missing or invalid
        """
        run_dir = self._get_run_directory(run_id)
        day_dir = run_dir / day
        audit_dir = day_dir / "audit"
        
        # Determine day name for filename (sat or sun)
        day_name = day.lower()[:3]  # "saturday" -> "sat", "sunday" -> "sun"
        audit_parquet = audit_dir / f"audit_{day_name}.parquet"
        
        assert audit_parquet.exists(), f"Audit Parquet file missing for {day}: {audit_parquet}"
        
        # Verify Parquet file is readable and has expected columns
        try:
            audit_df = pd.read_parquet(audit_parquet)
            assert len(audit_df) > 0, f"Audit Parquet file is empty for {day}"
            
            # Verify expected columns exist
            expected_cols = [
                "seg_id", "event_a", "event_b", "runner_id_a", "runner_id_b",
                "pass_flag_raw", "pass_flag_strict", "overlap_dwell_sec"
            ]
            missing_cols = [col for col in expected_cols if col not in audit_df.columns]
            assert not missing_cols, f"Audit Parquet missing columns for {day}: {missing_cols}"
            
            # Issue #612: Check for multi-zone columns (optional - may not exist in all rows)
            zone_cols = ["zone_index", "cp_km", "zone_source"]
            has_zone_cols = all(col in audit_df.columns for col in zone_cols)
            if has_zone_cols:
                print(f"✅ Audit Parquet includes multi-zone columns for {day}")
            else:
                # Not an error - zone columns are optional if no zones detected
                missing_zone_cols = [col for col in zone_cols if col not in audit_df.columns]
                if missing_zone_cols:
                    print(f"ℹ️  Audit Parquet missing zone columns for {day} (optional): {missing_zone_cols}")
            
            print(f"✅ Audit Parquet file verified for {day}: {len(audit_df)} rows, {audit_parquet.stat().st_size / 1024 / 1024:.1f} MB")
            
        except Exception as e:
            raise AssertionError(f"Failed to read/validate audit Parquet for {day}: {e}")
        
        return audit_parquet
    
    def _verify_flow_csv_multi_zone(self, flow_csv_path: Path, day: str) -> None:
        """Verify zone-level structure in Flow.csv.
        
        Issue #629: Validates that Flow.csv contains zone-level fields:
        - zone_index (required for zone-level structure)
        - cp_km, cp_type, zone_source (zone identification)
        - zone_start_km_a, zone_end_km_a, zone_start_km_b, zone_end_km_b (zone boundaries)
        - Zone-level metrics (overtaking_a, copresence_a, etc.)
        
        Args:
            flow_csv_path: Path to Flow.csv file
            day: Day code for logging
        """
        flow_df = pd.read_csv(flow_csv_path)
        
        # Check for zone-level columns (Issue #629)
        expected_cols = [
            "seg_id", "zone_index", "cp_km", "cp_type", "zone_source",
            "zone_start_km_a", "zone_end_km_a", "zone_start_km_b", "zone_end_km_b",
            "overtaking_a", "overtaking_b", "copresence_a", "copresence_b",
            "unique_encounters", "participants_involved", "has_convergence"
        ]
        missing_cols = [col for col in expected_cols if col not in flow_df.columns]
        assert not missing_cols, f"Flow.csv missing zone-level columns for {day}: {missing_cols}"
        
        # Validate zone_index (should be non-negative integers)
        assert all(flow_df["zone_index"] >= 0), f"Invalid zone_index values in {day} Flow.csv"
        
        # Validate zone boundaries (zone_end should be >= zone_start)
        assert all(flow_df["zone_end_km_a"] >= flow_df["zone_start_km_a"]), \
            f"Invalid zone boundaries (zone_end_km_a < zone_start_km_a) in {day} Flow.csv"
        assert all(flow_df["zone_end_km_b"] >= flow_df["zone_start_km_b"]), \
            f"Invalid zone boundaries (zone_end_km_b < zone_start_km_b) in {day} Flow.csv"
        
        # Validate cp_km (should be numeric or None)
        cp_km_valid = flow_df["cp_km"].apply(lambda x: pd.isna(x) or (isinstance(x, (int, float)) and x >= 0))
        assert cp_km_valid.all(), f"Invalid cp_km values in {day} Flow.csv"
        
        # Validate that rows are ordered by seg_id, then zone_index
        for seg_id in flow_df["seg_id"].unique():
            seg_rows = flow_df[flow_df["seg_id"] == seg_id]
            zone_indices = seg_rows["zone_index"].values
            assert all(zone_indices[i] <= zone_indices[i+1] for i in range(len(zone_indices)-1)), \
                f"Zones not ordered by zone_index for {seg_id} in {day} Flow.csv"
        
        print(f"✅ Flow.csv zone-level structure validated for {day}: {len(flow_df)} zones")
    
    def _verify_flow_zones_parquet(self, run_id: str, day: str) -> Optional[Path]:
        """Verify {day}_fz.parquet exists and has valid structure.
        
        Issue #627: Validates {day}_fz.parquet file structure (renamed from flow_zones.parquet).
        
        Args:
            run_id: Run ID to check
            day: Day code (e.g., "sat", "sun")
            
        Returns:
            Path to {day}_fz.parquet if it exists, None otherwise
        """
        run_dir = self._get_run_directory(run_id)
        day_dir = run_dir / day
        zones_parquet = day_dir / "reports" / f"{day}_fz.parquet"
        
        if not zones_parquet.exists():
            # Optional file - return None if missing
            return None
        
        try:
            zones_df = pd.read_parquet(zones_parquet)
            
            # Verify expected columns
            expected_cols = [
                "seg_id", "event_a", "event_b", "zone_index", "cp_km",
                "cp_type", "zone_source", "zone_start_km_a", "zone_end_km_a",
                "zone_start_km_b", "zone_end_km_b", "overtaking_a", "overtaking_b",
                "copresence_a", "copresence_b", "unique_encounters", "participants_involved"
            ]
            missing_cols = [col for col in expected_cols if col not in zones_df.columns]
            assert not missing_cols, f"{day}_fz.parquet missing columns for {day}: {missing_cols}"
            
            # Validate zone_index (should be non-negative integers)
            assert all(zones_df["zone_index"] >= 0), f"Invalid zone_index values in {day} {day}_fz.parquet"
            
            # Validate cp_type values
            valid_cp_types = {"true_pass", "bin_peak"}
            invalid_types = set(zones_df["cp_type"].unique()) - valid_cp_types
            assert not invalid_types, f"Invalid cp_type values in {day} {day}_fz.parquet: {invalid_types}"
            
            print(f"✅ {day}_fz.parquet verified for {day}: {len(zones_df)} zones, {zones_parquet.stat().st_size / 1024:.1f} KB")
            
        except Exception as e:
            raise AssertionError(f"Failed to read/validate {day}_fz.parquet for {day}: {e}")
        
        return zones_parquet
    
    def _verify_zones_cross_validation(self, flow_csv_path: Path, zones_parquet_path: Path, day: str) -> None:
        """Cross-validate {day}_fz.parquet with Flow.csv.
        
        Issue #627: Validates that:
        - Segments in Flow.csv with zones have corresponding rows in {day}_fz.parquet
        - worst_zone_index in Flow.csv matches a valid zone_index in {day}_fz.parquet
        - convergence_points_json aligns with zones data
        
        Args:
            flow_csv_path: Path to Flow.csv
            zones_parquet_path: Path to {day}_fz.parquet
            day: Day code for logging
        """
        import json
        
        flow_df = pd.read_csv(flow_csv_path)
        zones_df = pd.read_parquet(zones_parquet_path)
        
        # Group zones by segment and event pair
        zones_by_segment = {}
        for _, zone_row in zones_df.iterrows():
            key = (zone_row["seg_id"], zone_row["event_a"], zone_row["event_b"])
            if key not in zones_by_segment:
                zones_by_segment[key] = []
            zones_by_segment[key].append(zone_row)
        
        # Validate each segment in Flow.csv
        for _, flow_row in flow_df.iterrows():
            seg_id = flow_row.get("seg_id", "")
            event_a = flow_row.get("event_a", "")
            event_b = flow_row.get("event_b", "")
            key = (seg_id, event_a, event_b)
            
            worst_zone_idx = flow_row.get("worst_zone_index")
            cp_json_str = flow_row.get("convergence_points_json", "")
            
            # If segment has zones in {day}_fz.parquet, validate alignment
            if key in zones_by_segment:
                zones = zones_by_segment[key]
                
                # Validate worst_zone_index points to a valid zone
                if pd.notna(worst_zone_idx):
                    worst_idx = int(worst_zone_idx)
                    zone_indices = [int(z["zone_index"]) for z in zones]
                    assert worst_idx in zone_indices, \
                        f"worst_zone_index {worst_idx} not found in zones for {seg_id} {event_a} vs {event_b}"
                
                # Validate convergence_points_json matches zone count (approximately)
                if pd.notna(cp_json_str) and str(cp_json_str).strip():
                    try:
                        cp_data = json.loads(cp_json_str)
                        # CPs should match or be close to zone count (deduplication may reduce count)
                        assert len(cp_data) >= len(zones) or len(cp_data) <= len(zones) + 2, \
                            f"CP count ({len(cp_data)}) doesn't align with zone count ({len(zones)}) for {seg_id}"
                    except json.JSONDecodeError:
                        pass  # Already validated in _verify_flow_csv_zone_level
        
        print(f"✅ Zones cross-validation passed for {day}")
    
    def _verify_day_isolation(self, run_id: str, day: str, expected_events: List[str]):
        """Verify that outputs for a day only contain expected events.
        
        This is a mandatory, schema-aware check that validates:
        - bins.parquet contains only expected events
        - Flow.csv contains only expected event pairs
        - segments.geojson contains only expected seg_ids for the day
        - UI JSONs contain only day-scoped seg_ids
        """
        run_dir = self._get_run_directory(run_id)
        day_dir = run_dir / day
        
        # Expected seg_ids for this day
        expected_seg_ids = EXPECTED_SEG_IDS.get(day, set())
        
        # 1. Check bins.parquet for event names (MANDATORY)
        bins_path = day_dir / "bins" / "bins.parquet"
        assert bins_path.exists(), f"bins.parquet missing for {day}"
        bins_df = pd.read_parquet(bins_path)
        assert "event" in bins_df.columns, f"bins.parquet missing 'event' column for {day}"
        
        # Issue #535: event column is a list (bins can belong to multiple events)
        # Flatten all events from all bins to get unique event set
        # Note: PyArrow list columns are read as numpy arrays by pandas
        import numpy as np
        all_events = set()
        for event_list in bins_df["event"]:
            # Handle numpy arrays (PyArrow list columns)
            if isinstance(event_list, np.ndarray):
                if event_list.size > 0:
                    all_events.update([str(e).lower() for e in event_list.tolist() if str(e).strip()])
            elif isinstance(event_list, list):
                all_events.update([e.lower() if isinstance(e, str) else str(e).lower() for e in event_list if str(e).strip()])
            elif pd.notna(event_list) and not isinstance(event_list, np.ndarray):
                # Handle single value (backward compatibility)
                all_events.add(str(event_list).lower())
        
        actual_events = sorted(all_events)
        expected_events_lower = [e.lower() for e in expected_events]
        
        # Check that all events in bins are expected for this day
        for event in actual_events:
            assert event in expected_events_lower, \
                f"Unexpected event '{event}' found in {day} bins (expected: {expected_events})"
        
        # Verify that bins contain at least some events (not all empty)
        assert len(actual_events) > 0, f"No events found in {day} bins"
        
        # Check seg_id/segment_id in bins (if present)
        # Issue #535: bins.parquet uses 'segment_id', but some files use 'seg_id'
        seg_id_col = None
        if "seg_id" in bins_df.columns:
            seg_id_col = "seg_id"
        elif "segment_id" in bins_df.columns:
            seg_id_col = "segment_id"
        
        if seg_id_col:
            actual_seg_ids = set(bins_df[seg_id_col].unique().tolist())
            if expected_seg_ids:
                unexpected_seg_ids = actual_seg_ids - expected_seg_ids
                assert not unexpected_seg_ids, \
                    f"Unexpected seg_ids in {day} bins: {unexpected_seg_ids} (expected: {expected_seg_ids})"
        
        # 2. Check Flow.csv for event pairs (MANDATORY)
        flow_csv_path = day_dir / "reports" / "Flow.csv"
        assert flow_csv_path.exists(), f"Flow.csv missing for {day}"
        flow_df = pd.read_csv(flow_csv_path)
        assert "event_a" in flow_df.columns and "event_b" in flow_df.columns, \
            f"Flow.csv missing event_a/event_b columns for {day}"
        for _, row in flow_df.iterrows():
            event_a = str(row["event_a"]).lower()
            event_b = str(row["event_b"]).lower()
            assert event_a in [e.lower() for e in expected_events], \
                f"Unexpected event_a '{event_a}' in {day} Flow.csv"
            assert event_b in [e.lower() for e in expected_events], \
                f"Unexpected event_b '{event_b}' in {day} Flow.csv"
        
        # Check seg_id in Flow.csv
        # Note: Flow.csv may contain sub-segments (N2a, N2b, F2, F3) which should normalize to base segments (N2, F1)
        if "seg_id" in flow_df.columns and expected_seg_ids:
            def normalize_seg_id(seg_id_str):
                """Normalize segment ID: N2a -> N2, F2 -> F1, N2 -> N2
                Handles both letter suffixes (N2a -> N2) and numeric suffixes (F2 -> F1)
                """
                seg_str = str(seg_id_str)
                # First strip trailing letters (N2a -> N2, A1a -> A1)
                base = seg_str.rstrip('abcdefghijklmnopqrstuvwxyz')
                # If it ends with a number > 1, try to normalize to base segment
                # e.g., F2, F3 -> F1; G2, G3 -> G1; K2 -> K1
                # Note: C1, C2, E1, E2 don't have base segments, so they'll stay as-is
                if len(base) >= 2 and base[-1].isdigit() and base[-1] != '1':
                    # Try base segment with '1' suffix (F2 -> F1)
                    base_with_1 = base[:-1] + '1'
                    if base_with_1 in expected_seg_ids:
                        return base_with_1
                return base
            
            actual_seg_ids = set(flow_df["seg_id"].unique().tolist())
            # Normalize actual seg_ids to base segments for comparison
            normalized_actual_seg_ids = {normalize_seg_id(seg_id) for seg_id in actual_seg_ids}
            unexpected_seg_ids = normalized_actual_seg_ids - expected_seg_ids
            assert not unexpected_seg_ids, \
                f"Unexpected seg_ids in {day} Flow.csv: {unexpected_seg_ids} (normalized from {actual_seg_ids})"
        
        # 3. Check segments.geojson for seg_ids (MANDATORY)
        segments_geojson_path = day_dir / "ui" / "segments.geojson"
        assert segments_geojson_path.exists(), f"segments.geojson missing for {day}"
        with open(segments_geojson_path, 'r') as f:
            geojson_data = json.load(f)
        assert "features" in geojson_data, f"segments.geojson missing 'features' for {day}"
        
        actual_seg_ids = set()
        for feature in geojson_data["features"]:
            props = feature.get("properties", {})
            seg_id = props.get("seg_id") or props.get("segment_id") or props.get("id")
            if seg_id:
                actual_seg_ids.add(str(seg_id))
        
        if expected_seg_ids:
            unexpected_seg_ids = actual_seg_ids - expected_seg_ids
            assert not unexpected_seg_ids, \
                f"Unexpected seg_ids in {day} segments.geojson: {unexpected_seg_ids} (expected: {expected_seg_ids})"
        
        # 4. Check UI JSONs for day-scoped seg_ids (MANDATORY)
        ui_json_files = [
            ("segment_metrics.json", "segment_metrics"),
            ("schema_density.json", "segments"),
            ("flags.json", "flags"),
        ]
        
        for filename, key in ui_json_files:
            json_path = day_dir / "ui" / filename
            if json_path.exists():
                with open(json_path, 'r') as f:
                    json_data = json.load(f)
                
                # Extract seg_ids from JSON structure
                json_seg_ids = set()
                if filename == "segment_metrics.json":
                    # segment_metrics.json: keys are seg_ids, but exclude metadata keys
                    metadata_keys = [
                        "peak_density", "peak_rate", "segments_with_flags", "flagged_bins",
                        "co_presence_segments", "overtaking_segments"
                    ]
                    json_seg_ids = {k for k in json_data.keys() if k not in metadata_keys}
                elif filename == "schema_density.json":
                    # schema_density.json: segments array with seg_id
                    if "segments" in json_data:
                        json_seg_ids = {str(s.get("seg_id", "")) for s in json_data["segments"] if s.get("seg_id")}
                elif filename == "flags.json":
                    # flags.json: array with segment_id or seg_id
                    if isinstance(json_data, list):
                        json_seg_ids = {str(f.get("segment_id") or f.get("seg_id", "")) for f in json_data if f.get("segment_id") or f.get("seg_id")}
                
                if expected_seg_ids and json_seg_ids:
                    unexpected_seg_ids = json_seg_ids - expected_seg_ids
                    assert not unexpected_seg_ids, \
                        f"Unexpected seg_ids in {day} {filename}: {unexpected_seg_ids}"
    
    def test_sat(self, base_url, wait_for_server, enable_audit):
        """Test complete Saturday workflow (elite, open events) with configurable audit."""
        payload = self._build_base_payload(
            description="Saturday only scenario test",
            event_names=["elite", "open"],
            event_group=EVENT_GROUPS["sat"],
            enable_audit=enable_audit
        )
        
        # Make API request (Issue #554: returns immediately, analysis runs in background)
        response_data = self._make_analyze_request(base_url, payload, timeout=60)
        run_id = response_data["run_id"]
        days = response_data.get("days", ["sat"])
        self._require_analysis_context(run_id, payload)
        
        # Wait for background analysis to complete (Issue #554)
        self._wait_for_analysis_completion(run_id, days, max_wait_seconds=600)
        
        # Verify outputs exist
        outputs = self._verify_outputs_exist(run_id, "sat", "saturday_only")
        
        # Issue #607: Verify audit Parquet file exists (if audit enabled)
        if enable_audit == "y":
            audit_path = self._verify_audit_files(run_id, "sat")
        else:
            # Audit disabled - verify it doesn't exist
            run_dir = self._get_run_directory(run_id)
            audit_path = run_dir / "sat" / "audit" / "audit_sat.parquet"
            assert not audit_path.exists(), f"Audit file should not exist when audit is disabled: {audit_path}"
        
        # Verify day isolation (only elite and open events)
        self._verify_day_isolation(run_id, "sat", ["elite", "open"])
        
        # Verify same-day interactions
        # Note: Elite and Open use different segments (N1-N3 vs O1-O3), so they won't have
        # cross-event flow pairs unless they share segments. Verify that each event has flow pairs.
        flow_csv_path = outputs["flow_csv"]
        flow_df = pd.read_csv(flow_csv_path)
        
        # Verify that both elite and open events have flow pairs (may be same-event pairs)
        elite_pairs = flow_df[
            (flow_df["event_a"].str.lower() == "elite") | (flow_df["event_b"].str.lower() == "elite")
        ]
        open_pairs = flow_df[
            (flow_df["event_a"].str.lower() == "open") | (flow_df["event_b"].str.lower() == "open")
        ]
        assert len(elite_pairs) > 0, "No flow pairs found for elite event"
        assert len(open_pairs) > 0, "No flow pairs found for open event"
        
        # Issue #612: Verify multi-zone columns in Flow.csv
        self._verify_flow_csv_multi_zone(flow_csv_path, "sat")
        
        # Issue #612: Verify flow_zones.parquet if it exists
        zones_path = self._verify_flow_zones_parquet(run_id, "sat")
        if zones_path:
            # Cross-validation: Check that zones align with Flow.csv
            self._verify_zones_cross_validation(flow_csv_path, zones_path, "sat")
    
    def test_sun(self, base_url, wait_for_server):
        """Test complete Sunday workflow (full, half, 10k events) with audit enabled."""
        payload = self._build_base_payload(
            description="Sunday only scenario test with audit",
            event_names=["full", "10k", "half"],
            event_group=EVENT_GROUPS["sun"],
            enable_audit="y"  # Explicitly enable for this test
        )
        
        # Make API request (Issue #554: returns immediately, analysis runs in background)
        response_data = self._make_analyze_request(base_url, payload, timeout=60)
        run_id = response_data["run_id"]
        days = response_data.get("days", ["sun"])
        self._require_analysis_context(run_id, payload)
        
        # Wait for background analysis to complete (Issue #554)
        self._wait_for_analysis_completion(run_id, days, max_wait_seconds=600)
        
        # Verify outputs exist
        outputs = self._verify_outputs_exist(run_id, "sun", "sunday_only")
        
        # Verify day isolation (only full, 10k, half events)
        self._verify_day_isolation(run_id, "sun", ["full", "10k", "half"])
        
        # Verify same-day interactions (should have flow pairs between all three events)
        flow_csv_path = outputs["flow_csv"]
        flow_df = pd.read_csv(flow_csv_path)
        
        # Should have flow pairs between all event combinations
        event_pairs = [
            ("full", "10k"), ("full", "half"), ("10k", "half")
        ]
        for event_a, event_b in event_pairs:
            pairs = flow_df[
                ((flow_df["event_a"].str.lower() == event_a) & (flow_df["event_b"].str.lower() == event_b)) |
                ((flow_df["event_a"].str.lower() == event_b) & (flow_df["event_b"].str.lower() == event_a))
            ]
            assert len(pairs) > 0, f"No flow pairs found between {event_a} and {event_b}"
        
        # Issue #612: Verify multi-zone columns in Flow.csv
        self._verify_flow_csv_multi_zone(flow_csv_path, "sun")
        
        # Issue #612: Verify flow_zones.parquet if it exists
        zones_path = self._verify_flow_zones_parquet(run_id, "sun")
        if zones_path:
            # Cross-validation: Check that zones align with Flow.csv
            self._verify_zones_cross_validation(flow_csv_path, zones_path, "sun")
    
    def test_sat_sun(self, base_url, wait_for_server, enable_audit):
        """Test sat+sun analysis in single run_id with configurable audit."""
        payload = self._build_base_payload(
            description="Sat+Sun analysis test",
            event_names=["elite", "open", "full", "10k", "half"],
            event_group=EVENT_GROUPS["sat_sun"],
            enable_audit=enable_audit
        )
        
        # Make API request (Issue #554: returns immediately, analysis runs in background)
        response_data = self._make_analyze_request(base_url, payload, timeout=60)
        run_id = response_data["run_id"]
        days = response_data.get("days", ["sat", "sun"])
        self._require_analysis_context(run_id, payload)
        
        # Wait for background analysis to complete (Issue #554)
        self._wait_for_analysis_completion(run_id, days, max_wait_seconds=600)
        
        # Verify outputs exist for both days
        sat_outputs = self._verify_outputs_exist(run_id, "sat", "sat_sun")
        sun_outputs = self._verify_outputs_exist(run_id, "sun", "sat_sun")
        
        # Issue #607: Verify audit Parquet files exist (if audit enabled)
        if enable_audit == "y":
            sat_audit_path = self._verify_audit_files(run_id, "sat")
            sun_audit_path = self._verify_audit_files(run_id, "sun")
        else:
            # Audit disabled - verify files don't exist
            run_dir = self._get_run_directory(run_id)
            sat_audit_path = run_dir / "sat" / "audit" / "audit_sat.parquet"
            sun_audit_path = run_dir / "sun" / "audit" / "audit_sun.parquet"
            assert not sat_audit_path.exists(), f"Audit file should not exist when audit is disabled: {sat_audit_path}"
            assert not sun_audit_path.exists(), f"Audit file should not exist when audit is disabled: {sun_audit_path}"
        
        # Verify flags.json exists and is not empty (Issue #528)
        assert "flags_json" in sat_outputs, "SAT flags.json missing"
        assert "flags_json" in sun_outputs, "SUN flags.json missing"
        
        sat_flags = json.loads(sat_outputs["flags_json"].read_text())
        sun_flags = json.loads(sun_outputs["flags_json"].read_text())
        
        # Flags should be a list (may be empty if no flags, but should exist)
        assert isinstance(sat_flags, list), f"SAT flags.json should be a list, got {type(sat_flags)}"
        assert isinstance(sun_flags, list), f"SUN flags.json should be a list, got {type(sun_flags)}"
        
        print(f"✅ SAT flags.json: {len(sat_flags)} flagged segments")
        print(f"✅ SUN flags.json: {len(sun_flags)} flagged segments")
    
    def test_mixed_day_scenario(self, base_url, wait_for_server):
        """Test mixed-day scenario (Saturday + Sunday) with isolation validation and audit enabled."""
        payload = self._build_base_payload(
            description="Mixed day scenario test with audit",
            event_names=["elite", "open", "full", "10k", "half"],
            event_group=EVENT_GROUPS["sat_sun"],
            enable_audit="y"
        )
        
        # Make API request (Issue #554: returns immediately, analysis runs in background)
        response_data = self._make_analyze_request(base_url, payload, timeout=60)
        run_id = response_data["run_id"]
        days = response_data.get("days", ["sat", "sun"])
        self._require_analysis_context(run_id, payload)
        
        # Wait for background analysis to complete (Issue #554)
        self._wait_for_analysis_completion(run_id, days, max_wait_seconds=600)
        
        # Verify outputs exist for both days
        sat_outputs = self._verify_outputs_exist(run_id, "sat", "mixed_day")
        sun_outputs = self._verify_outputs_exist(run_id, "sun", "mixed_day")
        
        # Verify day isolation
        self._verify_day_isolation(run_id, "sat", ["elite", "open"])
        self._verify_day_isolation(run_id, "sun", ["full", "10k", "half"])
        
        # Verify cross-day isolation (no SAT events in SUN outputs, and vice versa)
        # Check Flow.csv for cross-day contamination
        sat_flow_df = pd.read_csv(sat_outputs["flow_csv"])
        sun_flow_df = pd.read_csv(sun_outputs["flow_csv"])
        
        # SAT flow should not contain SUN events
        sat_events_in_sun = sun_flow_df[
            (sun_flow_df["event_a"].str.lower().isin(["elite", "open"])) |
            (sun_flow_df["event_b"].str.lower().isin(["elite", "open"]))
        ]
        assert len(sat_events_in_sun) == 0, f"Found SAT events in SUN Flow.csv: {sat_events_in_sun}"
        
        # SUN flow should not contain SAT events
        sun_events_in_sat = sat_flow_df[
            (sat_flow_df["event_a"].str.lower().isin(["full", "10k", "half"])) |
            (sat_flow_df["event_b"].str.lower().isin(["full", "10k", "half"]))
        ]
        assert len(sun_events_in_sat) == 0, f"Found SUN events in SAT Flow.csv: {sun_events_in_sat}"
    
    def test_cross_day_isolation(self, base_url, wait_for_server):
        """Verify no cross-day contamination in bins, flow, density, locations with audit enabled."""
        # Use mixed-day scenario
        payload = self._build_base_payload(
            description="Cross-day isolation test with audit",
            event_names=["elite", "full"],
            enable_audit="y"
        )
        
        # Make API request (Issue #554: returns immediately, analysis runs in background)
        response_data = self._make_analyze_request(base_url, payload, timeout=60)
        run_id = response_data["run_id"]
        days = response_data.get("days", ["sat", "sun"])
        self._require_analysis_context(run_id, payload)
        
        # Wait for background analysis to complete (Issue #554)
        self._wait_for_analysis_completion(run_id, days, max_wait_seconds=600)
        
        run_dir = self._get_run_directory(run_id)
        
        # Check bins.parquet for cross-day contamination
        for day in ["sat", "sun"]:
            bins_path = run_dir / day / "bins" / "bins.parquet"
            assert bins_path.exists(), f"bins.parquet missing for {day}"
            bins_df = pd.read_parquet(bins_path)
            assert "event" in bins_df.columns, f"bins.parquet missing 'event' column for {day}"
            
            # Issue #535: event column is a list - check all events in bins
            # Note: PyArrow list columns are read as numpy arrays by pandas
            import numpy as np
            all_events = set()
            for event_list in bins_df["event"]:
                # Handle numpy arrays (PyArrow list columns)
                if isinstance(event_list, np.ndarray):
                    if event_list.size > 0:
                        all_events.update([str(e).lower() for e in event_list.tolist() if str(e).strip()])
                elif isinstance(event_list, list):
                    all_events.update([e.lower() if isinstance(e, str) else str(e).lower() for e in event_list if str(e).strip()])
                elif pd.notna(event_list) and not isinstance(event_list, np.ndarray):
                    all_events.add(str(event_list).lower())
            
            if day == "sat":
                # SAT bins should only have elite (and possibly open if both events are present)
                unexpected = all_events - {"elite", "open"}
                assert not unexpected, f"Found unexpected events in SAT bins: {unexpected} (expected: elite, open)"
            elif day == "sun":
                # SUN bins should only have full
                unexpected = all_events - {"full"}
                assert not unexpected, f"Found unexpected events in SUN bins: {unexpected} (expected: full)"
        
        # Check Flow.csv (already done in test_mixed_day_scenario, but verify here too)
        sat_flow_path = run_dir / "sat" / "reports" / "Flow.csv"
        sun_flow_path = run_dir / "sun" / "reports" / "Flow.csv"
        
        assert sat_flow_path.exists(), "SAT Flow.csv missing"
        sat_flow_df = pd.read_csv(sat_flow_path)
        has_full = (sat_flow_df["event_a"].str.lower() == "full") | (sat_flow_df["event_b"].str.lower() == "full")
        assert not has_full.any(), "Found 'full' event in SAT Flow.csv"
        
        assert sun_flow_path.exists(), "SUN Flow.csv missing"
        sun_flow_df = pd.read_csv(sun_flow_path)
        has_elite = (sun_flow_df["event_a"].str.lower() == "elite") | (sun_flow_df["event_b"].str.lower() == "elite")
        assert not has_elite.any(), "Found 'elite' event in SUN Flow.csv"
    
    def test_same_day_interactions(self, base_url, wait_for_server):
        """Verify same-day events can share bins and generate flow with audit enabled."""
        # Test with Sunday events (full, 10k, half)
        payload = self._build_base_payload(
            description="Sunday only scenario test with audit",
            event_names=["full", "10k", "half"],
            enable_audit="y"
        )
        
        # Make API request (Issue #554: returns immediately, analysis runs in background)
        response_data = self._make_analyze_request(base_url, payload, timeout=60)
        run_id = response_data["run_id"]
        days = response_data.get("days", ["sun"])
        self._require_analysis_context(run_id, payload)
        
        # Wait for background analysis to complete (Issue #554)
        self._wait_for_analysis_completion(run_id, days, max_wait_seconds=600)
        
        run_dir = self._get_run_directory(run_id)
        
        # Verify bins contain multiple events (same-day events share bins)
        bins_path = run_dir / "sun" / "bins" / "bins.parquet"
        assert bins_path.exists(), "bins.parquet missing for sun"
        bins_df = pd.read_parquet(bins_path)
        assert "event" in bins_df.columns, "bins.parquet missing 'event' column"
        
        # Issue #535: event column is a list - flatten to get all unique events
        # Note: PyArrow list columns are read as numpy arrays by pandas
        import numpy as np
        all_events = set()
        for event_list in bins_df["event"]:
            # Handle numpy arrays (PyArrow list columns)
            if isinstance(event_list, np.ndarray):
                if event_list.size > 0:
                    all_events.update([str(e).lower() for e in event_list.tolist() if str(e).strip()])
            elif isinstance(event_list, list):
                all_events.update([e.lower() if isinstance(e, str) else str(e).lower() for e in event_list if str(e).strip()])
            elif pd.notna(event_list) and not isinstance(event_list, np.ndarray):
                all_events.add(str(event_list).lower())
        
        events_in_bins = sorted(all_events)
        # Should have at least 2 events in bins (they share segments)
        assert len([e for e in events_in_bins if e in ["full", "10k", "half"]]) >= 2, \
            f"Expected multiple events in bins, found: {events_in_bins}"
        
        # Verify flow pairs exist between same-day events
        flow_csv_path = run_dir / "sun" / "reports" / "Flow.csv"
        assert flow_csv_path.exists(), "Flow.csv missing for sun"
        flow_df = pd.read_csv(flow_csv_path)
        # Should have flow pairs between full-10k, full-half, 10k-half
        pairs_found = 0
        for event_a, event_b in [("full", "10k"), ("full", "half"), ("10k", "half")]:
            pairs = flow_df[
                ((flow_df["event_a"].str.lower() == event_a) & (flow_df["event_b"].str.lower() == event_b)) |
                ((flow_df["event_a"].str.lower() == event_b) & (flow_df["event_b"].str.lower() == event_a))
            ]
            if len(pairs) > 0:
                pairs_found += 1
        
        assert pairs_found >= 2, f"Expected flow pairs between same-day events, found {pairs_found}"

    def test_data_dir_without_custom_path(self, base_url, wait_for_server):
        """Test that analysis works without data_dir (should use default).
        
        Issue #680: Verify backward compatibility when data_dir is not provided.
        """
        payload = self._build_base_payload(
            description="Test without custom data_dir (backward compatibility)",
            event_names=["elite"],
            enable_audit="n"
        )
        
        # Explicitly remove data_dir to test default behavior
        if "data_dir" in payload:
            del payload["data_dir"]
        
        response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        assert "run_id" in data, "Response missing run_id"
        assert data["status"] == "success", f"Analysis failed: {data}"

    def test_data_dir_with_custom_path(self, base_url, wait_for_server):
        """Test that analysis works with custom data_dir path.
        
        Issue #680: Verify custom data_dir is accepted and used.
        """
        # Use the same data directory as default (data/) to test the feature
        # In real scenarios, this could be any accessible directory
        custom_data_dir = "data"  # Using default for test, but feature allows any path
        
        payload = self._build_base_payload(
            description="Test with custom data_dir",
            event_names=["elite"],
            enable_audit="n"
        )
        
        # Override with custom data_dir
        payload["data_dir"] = custom_data_dir
        
        response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        assert "run_id" in data, "Response missing run_id"
        assert data["status"] == "success", f"Analysis failed: {data}"
        
        # Verify data_dir is stored in analysis.json
        run_id = data["run_id"]
        # Issue #682: Use centralized get_run_directory() for correct path
        run_dir = self._get_run_directory(run_id)
        analysis_json_path = run_dir / "analysis.json"
        assert analysis_json_path.exists(), "analysis.json not found"
        
        with open(analysis_json_path, 'r') as f:
            analysis_json = json.load(f)
        
        assert analysis_json.get("data_dir") == custom_data_dir, \
            f"data_dir in analysis.json ({analysis_json.get('data_dir')}) does not match request ({custom_data_dir})"

    def test_data_dir_invalid_path(self, base_url, wait_for_server):
        """Test that invalid data_dir path fails with clear error.
        
        Issue #680: Verify fail-fast behavior for invalid data_dir paths.
        """
        payload = self._build_base_payload(
            description="Test with invalid data_dir",
            event_names=["elite"],
            enable_audit="n"
        )
        
        # Use a non-existent directory
        payload["data_dir"] = "/nonexistent/directory/path/that/does/not/exist"
        
        response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload, timeout=30)
        assert response.status_code == 404, \
            f"Expected 404 for invalid data_dir, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "ERROR", "Response should have ERROR status"
        assert "data directory not found" in data.get("error", "").lower() or \
               "not found" in data.get("error", "").lower(), \
            f"Error message should mention directory not found: {data.get('error')}"


# pytest_addoption and base_url fixture moved to conftest.py


@pytest.fixture(scope="class")
def wait_for_server(base_url):
    """Wait for server to be ready with clear failure message."""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException as e:
            if attempt == max_attempts - 1:
                # Final attempt failed - provide clear error message
                pytest.fail(
                    f"❌ Server not reachable at BASE_URL={base_url}\n"
                    f"   Error: {e}\n"
                    f"   Instructions:\n"
                    f"   1. Start server: make dev (or docker-compose up)\n"
                    f"   2. Verify server is running: curl {base_url}/health\n"
                    f"   3. If using docker-compose, use: BASE_URL=http://app:8080 pytest tests/e2e.py\n"
                    f"   4. Or use: make e2e-v2 (one-command runner)"
                )
        time.sleep(1)
    pytest.fail("Server not available after 30 attempts")