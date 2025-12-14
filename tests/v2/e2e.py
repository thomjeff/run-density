"""
End-to-End Tests for Runflow v2 API

Phase 8: E2E Testing & Validation (Issue #502)

Tests complete v2 workflow: API → validation → pipeline → outputs
Validates day isolation, same-day interactions, and golden file regression.
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

# Configuration
# Base URL can be set via BASE_URL environment variable or pytest --base-url
# Defaults to http://localhost:8080 for local dev
# Use http://app:8080 when running in docker-compose network
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
TIMEOUT = 600  # 10 minutes for full analysis

# Expected segment ID patterns per day (for day isolation validation)
EXPECTED_SEG_IDS = {
    "sat": {"N1", "N2", "N3", "O1", "O2", "O3"},  # Saturday segments
    "sun": {"A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2",
            "F1", "F2", "G1", "G2", "H1", "H2", "I1", "I2", "J1", "J2", "K1", "K2",
            "L1", "L2", "M1", "M2"}  # Sunday segments (A1-M2)
}


class TestV2E2EScenarios:
    """E2E tests for v2 analysis scenarios."""
    
    def _make_analyze_request(self, base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to /runflow/v2/analyze and return response."""
        response = requests.post(
            f"{base_url}/runflow/v2/analyze",
            json=payload,
            timeout=TIMEOUT
        )
        
        assert response.status_code == 200, f"Request failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert "run_id" in data, "Response missing run_id"
        assert "status" in data, "Response missing status"
        assert data["status"] == "success", f"Analysis failed: {data}"
        
        return data
    
    def _get_run_directory(self, run_id: str) -> Path:
        """Get run directory path."""
        from app.utils.run_id import get_runflow_root
        runflow_root = get_runflow_root()
        return runflow_root / run_id
    
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
            "flow_md": day_dir / "reports" / "Flow.md",
            "bins_parquet": day_dir / "bins" / "bins.parquet",
            "metadata_json": day_dir / "metadata.json",
            
            # UI artifacts (v2 minimum contract)
            "meta_json": day_dir / "ui" / "meta.json",
            "segment_metrics_json": day_dir / "ui" / "segment_metrics.json",
            "flags_json": day_dir / "ui" / "flags.json",
            "flow_json": day_dir / "ui" / "flow.json",
            "schema_density_json": day_dir / "ui" / "schema_density.json",
            "health_json": day_dir / "ui" / "health.json",
            "segments_geojson": day_dir / "ui" / "segments.geojson",
            "captions_json": day_dir / "ui" / "captions.json",
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
        
        # Verify all expected files exist
        missing = []
        for name, path in expected_files.items():
            if not path.exists():
                missing.append(f"{name}: {path}")
        
        assert not missing, f"Missing output files for {day}:\n" + "\n".join(missing)
        
        return expected_files
    
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
        actual_events = bins_df["event"].unique().tolist()
        for event in actual_events:
            assert event.lower() in [e.lower() for e in expected_events], \
                f"Unexpected event '{event}' found in {day} bins (expected: {expected_events})"
        
        # Check seg_id in bins (if present)
        if "seg_id" in bins_df.columns:
            actual_seg_ids = set(bins_df["seg_id"].unique().tolist())
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
        if "seg_id" in flow_df.columns and expected_seg_ids:
            actual_seg_ids = set(flow_df["seg_id"].unique().tolist())
            unexpected_seg_ids = actual_seg_ids - expected_seg_ids
            assert not unexpected_seg_ids, \
                f"Unexpected seg_ids in {day} Flow.csv: {unexpected_seg_ids}"
        
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
                    # segment_metrics.json: keys are seg_ids
                    json_seg_ids = {k for k in json_data.keys() if k not in ["peak_density", "peak_rate", "segments_with_flags", "flagged_bins"]}
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
    
    def test_saturday_only_scenario(self, base_url, wait_for_server):
        """Test complete Saturday-only workflow (elite, open events)."""
        payload = {
            "events": [
                {"name": "elite", "day": "sat", "start_time": 480, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
                {"name": "open", "day": "sat", "start_time": 510, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"}
            ]
        }
        
        # Make API request
        response_data = self._make_analyze_request(base_url, payload)
        run_id = response_data["run_id"]
        
        # Verify outputs exist
        outputs = self._verify_outputs_exist(run_id, "sat", "saturday_only")
        
        # Verify day isolation (only elite and open events)
        self._verify_day_isolation(run_id, "sat", ["elite", "open"])
        
        # Verify same-day interactions (elite and open should interact)
        flow_csv_path = outputs["flow_csv"]
        flow_df = pd.read_csv(flow_csv_path)
        
        # Should have flow pairs between elite and open
        elite_open_pairs = flow_df[
            ((flow_df["event_a"].str.lower() == "elite") & (flow_df["event_b"].str.lower() == "open")) |
            ((flow_df["event_a"].str.lower() == "open") & (flow_df["event_b"].str.lower() == "elite"))
        ]
        assert len(elite_open_pairs) > 0, "No flow pairs found between elite and open events"
    
    def test_sunday_only_scenario(self, base_url, wait_for_server):
        """Test complete Sunday-only workflow (full, half, 10k events)."""
        payload = {
            "events": [
                {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
                {"name": "10k", "day": "sun", "start_time": 440, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
                {"name": "half", "day": "sun", "start_time": 460, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
            ]
        }
        
        # Make API request
        response_data = self._make_analyze_request(base_url, payload)
        run_id = response_data["run_id"]
        
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
    
    def test_mixed_day_scenario(self, base_url, wait_for_server):
        """Test mixed-day scenario (Saturday + Sunday) with isolation validation."""
        payload = {
            "events": [
                {"name": "elite", "day": "sat", "start_time": 480, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
                {"name": "open", "day": "sat", "start_time": 510, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"},
                {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
                {"name": "10k", "day": "sun", "start_time": 440, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
                {"name": "half", "day": "sun", "start_time": 460, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
            ]
        }
        
        # Make API request
        response_data = self._make_analyze_request(base_url, payload)
        run_id = response_data["run_id"]
        
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
        """Verify no cross-day contamination in bins, flow, density, locations."""
        # Use mixed-day scenario
        payload = {
            "events": [
                {"name": "elite", "day": "sat", "start_time": 480, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
                {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"}
            ]
        }
        
        response_data = self._make_analyze_request(base_url, payload)
        run_id = response_data["run_id"]
        run_dir = self._get_run_directory(run_id)
        
        # Check bins.parquet for cross-day contamination
        for day in ["sat", "sun"]:
            bins_path = run_dir / day / "bins" / "bins.parquet"
            assert bins_path.exists(), f"bins.parquet missing for {day}"
            bins_df = pd.read_parquet(bins_path)
            assert "event" in bins_df.columns, f"bins.parquet missing 'event' column for {day}"
            if day == "sat":
                # SAT bins should only have elite
                unexpected = bins_df[~bins_df["event"].str.lower().isin(["elite"])]
                assert len(unexpected) == 0, f"Found unexpected events in SAT bins: {unexpected['event'].unique()}"
            elif day == "sun":
                # SUN bins should only have full
                unexpected = bins_df[~bins_df["event"].str.lower().isin(["full"])]
                assert len(unexpected) == 0, f"Found unexpected events in SUN bins: {unexpected['event'].unique()}"
        
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
        """Verify same-day events can share bins and generate flow."""
        # Test with Sunday events (full, 10k, half)
        payload = {
            "events": [
                {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
                {"name": "10k", "day": "sun", "start_time": 440, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
                {"name": "half", "day": "sun", "start_time": 460, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
            ]
        }
        
        response_data = self._make_analyze_request(base_url, payload)
        run_id = response_data["run_id"]
        run_dir = self._get_run_directory(run_id)
        
        # Verify bins contain multiple events (same-day events share bins)
        bins_path = run_dir / "sun" / "bins" / "bins.parquet"
        assert bins_path.exists(), "bins.parquet missing for sun"
        bins_df = pd.read_parquet(bins_path)
        assert "event" in bins_df.columns, "bins.parquet missing 'event' column"
        events_in_bins = bins_df["event"].str.lower().unique().tolist()
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


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Base URL for API requests (default: http://localhost:8080 or BASE_URL env var)"
    )


@pytest.fixture(scope="class")
def base_url(request):
    """Base URL for API requests.
    
    Can be configured via:
    - --base-url pytest CLI argument
    - BASE_URL environment variable
    - Defaults to http://localhost:8080
    """
    # Check for CLI argument first
    base_url_arg = request.config.getoption("--base-url")
    if base_url_arg:
        return base_url_arg
    
    # Fall back to environment variable or default
    return os.getenv("BASE_URL", BASE_URL)


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
                    f"   3. If using docker-compose, use: BASE_URL=http://app:8080 pytest tests/v2/e2e.py\n"
                    f"   4. Or use: make e2e-v2 (one-command runner)"
                )
        time.sleep(1)
    pytest.fail("Server not available after 30 attempts")


class TestV2GoldenFileRegression:
    """Golden file regression tests."""
    
    @pytest.fixture(scope="class")
    def golden_base_path(self):
        """Path to golden files directory."""
        return Path(__file__).parent / "golden"
    
    def _normalize_markdown(self, content: str) -> str:
        """Normalize markdown content by removing metadata that changes between runs."""
        # Remove "Generated at" timestamps
        content = re.sub(r'Generated at:.*?\n', '', content)
        # Remove run_id references
        content = re.sub(r'Run ID:.*?\n', '', content)
        # Remove version/date blocks
        content = re.sub(r'Version:.*?\n', '', content)
        content = re.sub(r'Date:.*?\n', '', content)
        # Normalize whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        return content.strip()
    
    def _normalize_csv(self, content: str, filename: str) -> str:
        """Normalize CSV content using per-file sort keys."""
        try:
            from io import StringIO
            df = pd.read_csv(StringIO(content))
            
            if len(df) == 0:
                return df.to_csv(index=False, lineterminator='\n')
            
            # Per-file sort keys
            if filename == "Flow.csv":
                # Flow.csv: sort by seg_id, event_a, event_b, from_km_a
                sort_cols = []
                for col in ["seg_id", "event_a", "event_b", "from_km_a"]:
                    if col in df.columns:
                        sort_cols.append(col)
                if sort_cols:
                    df = df.sort_values(by=sort_cols)
            elif filename == "Locations.csv":
                # Locations.csv: sort by loc_id, event (or location_id, event_name)
                sort_cols = []
                for col in ["loc_id", "location_id", "event", "event_name"]:
                    if col in df.columns:
                        sort_cols.append(col)
                        break  # Use first available
                if sort_cols:
                    df = df.sort_values(by=sort_cols)
            else:
                # Generic fallback: sort by first 1-3 identifier columns
                id_cols = [col for col in df.columns if any(x in col.lower() for x in ["id", "seg_id", "loc_id", "name"])]
                if id_cols:
                    df = df.sort_values(by=id_cols[:3])
            
            # Convert back to CSV with consistent formatting
            return df.to_csv(index=False, lineterminator='\n')
        except Exception:
            # If normalization fails, return original
            return content
    
    def _normalize_json(self, content: str) -> str:
        """Normalize JSON content by parsing and dumping with sorted keys."""
        try:
            data = json.loads(content)
            return json.dumps(data, sort_keys=True, indent=2)
        except Exception:
            # If not JSON, return original
            return content
    
    def _normalize_geojson(self, content: str) -> str:
        """Normalize GeoJSON by sorting features by seg_id."""
        try:
            data = json.loads(content)
            if "features" in data and isinstance(data["features"], list):
                # Sort features by seg_id (or segment_id or id) in properties
                def get_seg_id(feature):
                    props = feature.get("properties", {})
                    return str(props.get("seg_id") or props.get("segment_id") or props.get("id") or "")
                
                data["features"].sort(key=get_seg_id)
            # Dump with sorted keys
            return json.dumps(data, sort_keys=True, indent=2)
        except Exception:
            return content
    
    def _normalize_parquet(self, file_path: Path) -> str:
        """Normalize parquet by loading, sorting, and returning hash or CSV representation.
        
        Returns a deterministic string representation for comparison.
        """
        try:
            df = pd.read_parquet(file_path)
            
            # Sort by stable keys (day, seg_id, t, bin_id depending on schema)
            sort_cols = []
            for col in ["day", "seg_id", "segment_id", "t", "bin_id", "start_km", "end_km"]:
                if col in df.columns:
                    sort_cols.append(col)
            
            if sort_cols:
                df = df.sort_values(by=sort_cols)
            
            # Sort columns alphabetically
            df = df.reindex(sorted(df.columns), axis=1)
            
            # Return CSV representation for comparison
            return df.to_csv(index=False, lineterminator='\n')
        except Exception as e:
            # If normalization fails, return error indicator
            return f"PARQUET_NORMALIZATION_ERROR: {e}"
    
    def _write_diff_artifacts(self, run_id: str, day: str, filename: str, 
                              actual_normalized: str, golden_normalized: str):
        """Write diff artifacts to deterministic location for debugging."""
        from app.utils.run_id import get_runflow_root
        
        runflow_root = get_runflow_root()
        artifacts_dir = runflow_root / run_id / "_test_artifacts" / day
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Write normalized files
        (artifacts_dir / f"{filename}.actual").write_text(actual_normalized, encoding="utf-8")
        (artifacts_dir / f"{filename}.golden").write_text(golden_normalized, encoding="utf-8")
        
        # Write unified diff for text/json files
        if filename.endswith(('.md', '.json', '.csv')):
            import difflib
            diff = difflib.unified_diff(
                golden_normalized.splitlines(keepends=True),
                actual_normalized.splitlines(keepends=True),
                fromfile=f"{filename}.golden",
                tofile=f"{filename}.actual",
                lineterm=''
            )
            (artifacts_dir / f"{filename}.diff").write_text(''.join(diff), encoding="utf-8")
    
    def _compare_outputs_to_golden(self, run_id: str, day: str, scenario: str, golden_base_path: Path) -> List[str]:
        """Compare actual outputs to golden files and return list of differences.
        
        Uses normalized comparisons to avoid false positives from:
        - Metadata timestamps
        - Run ID references
        - CSV row ordering
        - JSON key ordering
        - GeoJSON feature ordering
        - Parquet metadata differences
        """
        from app.utils.run_id import get_runflow_root
        
        runflow_root = get_runflow_root()
        run_dir = runflow_root / run_id
        day_dir = run_dir / day
        
        differences = []
        
        # Files to compare (Option A: Include UI artifacts)
        files_to_compare = []
        
        # Report files
        report_files = ["Density.md", "Flow.csv", "Flow.md"]
        if day == "sun":  # Locations.csv may not exist for SAT
            report_files.append("Locations.csv")
        for filename in report_files:
            files_to_compare.append(("reports", filename))
        
        # UI artifacts (golden regression covers UI contract)
        ui_files = [
            "meta.json",
            "segment_metrics.json",
            "flags.json",
            "flow.json",
            "schema_density.json",
            "health.json",
            "segments.geojson",
            "captions.json"
        ]
        for filename in ui_files:
            files_to_compare.append(("ui", filename))
        
        # Bins (optional but useful)
        files_to_compare.append(("bins", "bins.parquet"))
        
        for file_entry in files_to_compare:
            if isinstance(file_entry, tuple) and len(file_entry) == 2:
                # (subdir, filename) format
                subdir, filename = file_entry
                actual_path = day_dir / subdir / filename
                golden_path = golden_base_path / scenario / day / subdir / filename
            else:
                # Legacy format (backward compatibility)
                filename = file_entry
                actual_path = day_dir / "reports" / filename
                golden_path = golden_base_path / scenario / day / filename
            
            if not golden_path.exists():
                differences.append(f"⚠️  Golden file not found: {golden_path}")
                continue
            
            if not actual_path.exists():
                differences.append(f"❌ Actual file not found: {actual_path}")
                continue
            
            # Normalize content based on file type
            if filename.endswith('.md'):
                actual_content = actual_path.read_text(encoding="utf-8")
                golden_content = golden_path.read_text(encoding="utf-8")
                actual_normalized = self._normalize_markdown(actual_content)
                golden_normalized = self._normalize_markdown(golden_content)
            elif filename.endswith('.csv'):
                actual_content = actual_path.read_text(encoding="utf-8")
                golden_content = golden_path.read_text(encoding="utf-8")
                actual_normalized = self._normalize_csv(actual_content, filename)
                golden_normalized = self._normalize_csv(golden_content, filename)
            elif filename.endswith('.json') or filename.endswith('.geojson'):
                actual_content = actual_path.read_text(encoding="utf-8")
                golden_content = golden_path.read_text(encoding="utf-8")
                if filename.endswith('.geojson'):
                    actual_normalized = self._normalize_geojson(actual_content)
                    golden_normalized = self._normalize_geojson(golden_content)
                else:
                    actual_normalized = self._normalize_json(actual_content)
                    golden_normalized = self._normalize_json(golden_content)
            elif filename.endswith('.parquet'):
                actual_normalized = self._normalize_parquet(actual_path)
                golden_normalized = self._normalize_parquet(golden_path)
            else:
                # For unknown types, compare as-is
                actual_content = actual_path.read_text(encoding="utf-8")
                golden_content = golden_path.read_text(encoding="utf-8")
                actual_normalized = actual_content
                golden_normalized = golden_content
            
            if actual_normalized != golden_normalized:
                differences.append(f"⚠️  {day}/{filename}: Content differs from golden file (after normalization)")
                # Write diff artifacts
                self._write_diff_artifacts(run_id, day, filename, actual_normalized, golden_normalized)
        
        return differences
    
    def test_golden_file_regression_saturday_only(self, base_url, wait_for_server, golden_base_path):
        """Compare Saturday-only outputs against golden files."""
        # Run Saturday-only scenario
        payload = {
            "events": [
                {"name": "elite", "day": "sat", "start_time": 480, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
                {"name": "open", "day": "sat", "start_time": 510, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"}
            ]
        }
        
        response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        run_id = data["run_id"]
        
        # Compare outputs
        differences = self._compare_outputs_to_golden(
            run_id, "sat", "saturday_only", golden_base_path
        )
        
        if differences:
            pytest.fail(f"Golden file differences found:\n" + "\n".join(differences) + 
                       f"\n\nDiff artifacts written to: runflow/{run_id}/_test_artifacts/")
    
    def test_golden_file_regression_sunday_only(self, base_url, wait_for_server, golden_base_path):
        """Compare Sunday-only outputs against golden files."""
        # Run Sunday-only scenario
        payload = {
            "events": [
                {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
                {"name": "10k", "day": "sun", "start_time": 440, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
                {"name": "half", "day": "sun", "start_time": 460, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
            ]
        }
        
        response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        run_id = data["run_id"]
        
        # Compare outputs
        differences = self._compare_outputs_to_golden(
            run_id, "sun", "sunday_only", golden_base_path
        )
        
        if differences:
            pytest.fail(f"Golden file differences found:\n" + "\n".join(differences) +
                       f"\n\nDiff artifacts written to: runflow/{run_id}/_test_artifacts/")
    
    def test_golden_file_regression_mixed_day(self, base_url, wait_for_server, golden_base_path):
        """Compare mixed-day outputs against golden files."""
        # Run mixed-day scenario
        payload = {
            "events": [
                {"name": "elite", "day": "sat", "start_time": 480, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
                {"name": "open", "day": "sat", "start_time": 510, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"},
                {"name": "full", "day": "sun", "start_time": 420, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
                {"name": "10k", "day": "sun", "start_time": 440, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
                {"name": "half", "day": "sun", "start_time": 460, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
            ]
        }
        
        response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        run_id = data["run_id"]
        
        # Compare outputs for both days
        all_differences = []
        for day in ["sat", "sun"]:
            differences = self._compare_outputs_to_golden(
                run_id, day, "mixed_day", golden_base_path
            )
            all_differences.extend(differences)
        
        if all_differences:
            pytest.fail(f"Golden file differences found:\n" + "\n".join(all_differences) +
                       f"\n\nDiff artifacts written to: runflow/{run_id}/_test_artifacts/")
