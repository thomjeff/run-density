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
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

# Configuration
# Base URL can be set via BASE_URL environment variable or pytest --base-url
# Defaults to http://localhost:8080 for local dev
# Use http://app:8080 when running in docker-compose network
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
TIMEOUT = 600  # 10 minutes for full analysis


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
        """Verify that expected output files exist for a day."""
        run_dir = self._get_run_directory(run_id)
        day_dir = run_dir / day
        
        expected_files = {
            "density_md": day_dir / "reports" / "Density.md",
            "flow_csv": day_dir / "reports" / "Flow.csv",
            "flow_md": day_dir / "reports" / "Flow.md",
            "bins_parquet": day_dir / "bins" / "bins.parquet",
            "segments_geojson": day_dir / "ui" / "segments.geojson",
            "metadata_json": day_dir / "metadata.json",
        }
        
        # Locations.csv may not exist for all days (e.g., SAT)
        locations_csv = day_dir / "reports" / "Locations.csv"
        if locations_csv.exists():
            expected_files["locations_csv"] = locations_csv
        
        # Verify all expected files exist
        missing = []
        for name, path in expected_files.items():
            if not path.exists():
                missing.append(f"{name}: {path}")
        
        assert not missing, f"Missing output files for {day}:\n" + "\n".join(missing)
        
        return expected_files
    
    def _verify_day_isolation(self, run_id: str, day: str, expected_events: List[str]):
        """Verify that outputs for a day only contain expected events."""
        run_dir = self._get_run_directory(run_id)
        day_dir = run_dir / day
        
        # Check bins.parquet for event names
        bins_path = day_dir / "bins" / "bins.parquet"
        if bins_path.exists():
            bins_df = pd.read_parquet(bins_path)
            if "event" in bins_df.columns:
                actual_events = bins_df["event"].unique().tolist()
                for event in actual_events:
                    assert event.lower() in [e.lower() for e in expected_events], \
                        f"Unexpected event '{event}' found in {day} bins (expected: {expected_events})"
        
        # Check Flow.csv for event pairs
        flow_csv_path = day_dir / "reports" / "Flow.csv"
        if flow_csv_path.exists():
            flow_df = pd.read_csv(flow_csv_path)
            if "event_a" in flow_df.columns and "event_b" in flow_df.columns:
                for _, row in flow_df.iterrows():
                    event_a = str(row["event_a"]).lower()
                    event_b = str(row["event_b"]).lower()
                    assert event_a in [e.lower() for e in expected_events], \
                        f"Unexpected event_a '{event_a}' in {day} Flow.csv"
                    assert event_b in [e.lower() for e in expected_events], \
                        f"Unexpected event_b '{event_b}' in {day} Flow.csv"
    
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
        
        return run_id
    
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
        
        return run_id
    
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
            if bins_path.exists():
                bins_df = pd.read_parquet(bins_path)
                if "event" in bins_df.columns:
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
        
        if sat_flow_path.exists():
            sat_flow_df = pd.read_csv(sat_flow_path)
            # SAT flow should not have "full" events
            has_full = (sat_flow_df["event_a"].str.lower() == "full") | (sat_flow_df["event_b"].str.lower() == "full")
            assert not has_full.any(), "Found 'full' event in SAT Flow.csv"
        
        if sun_flow_path.exists():
            sun_flow_df = pd.read_csv(sun_flow_path)
            # SUN flow should not have "elite" events
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
        if bins_path.exists():
            bins_df = pd.read_parquet(bins_path)
            if "event" in bins_df.columns:
                events_in_bins = bins_df["event"].str.lower().unique().tolist()
                # Should have at least 2 events in bins (they share segments)
                assert len([e for e in events_in_bins if e in ["full", "10k", "half"]]) >= 2, \
                    f"Expected multiple events in bins, found: {events_in_bins}"
        
        # Verify flow pairs exist between same-day events
        flow_csv_path = run_dir / "sun" / "reports" / "Flow.csv"
        if flow_csv_path.exists():
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
    """Wait for server to be ready."""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    pytest.skip("Server not available")


class TestV2GoldenFileRegression:
    """Golden file regression tests."""
    
    @pytest.fixture(scope="class")
    def golden_base_path(self):
        """Path to golden files directory."""
        return Path(__file__).parent / "golden"
    
    def _load_golden_file(self, scenario: str, day: str, filename: str) -> Optional[str]:
        """Load golden file content."""
        golden_path = self.golden_base_path / scenario / day / filename
        if golden_path.exists():
            return golden_path.read_text(encoding="utf-8")
        return None
    
    def _compare_files(self, actual_content: str, golden_content: str, filename: str) -> List[str]:
        """Compare actual vs golden file content and return differences."""
        differences = []
        
        if actual_content != golden_content:
            # For now, just flag as different
            # In the future, could do more sophisticated diffing
            differences.append(f"{filename}: Content differs from golden file")
        
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
            pytest.fail(f"Golden file differences found:\n" + "\n".join(differences))
    
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
            pytest.fail(f"Golden file differences found:\n" + "\n".join(differences))
    
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
            pytest.fail(f"Golden file differences found:\n" + "\n".join(all_differences))
    
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
    
    def _normalize_csv(self, content: str) -> str:
        """Normalize CSV content by loading into pandas and sorting deterministically."""
        try:
            from io import StringIO
            df = pd.read_csv(StringIO(content))
            # Sort by all columns to ensure deterministic order
            if len(df) > 0:
                df = df.sort_values(by=list(df.columns))
            # Convert back to CSV with consistent formatting
            return df.to_csv(index=False, lineterminator='\n')
        except Exception as e:
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
    
    def _compare_outputs_to_golden(self, run_id: str, day: str, scenario: str, golden_base_path: Path) -> List[str]:
        """Compare actual outputs to golden files and return list of differences.
        
        Uses normalized comparisons to avoid false positives from:
        - Metadata timestamps
        - Run ID references
        - CSV row ordering
        - JSON key ordering
        """
        from app.utils.run_id import get_runflow_root
        
        runflow_root = get_runflow_root()
        run_dir = runflow_root / run_id
        day_dir = run_dir / day
        
        differences = []
        
        # Files to compare
        files_to_compare = ["Density.md", "Flow.csv", "Flow.md"]
        if day == "sun":  # Locations.csv may not exist for SAT
            files_to_compare.append("Locations.csv")
        
        for filename in files_to_compare:
            actual_path = day_dir / "reports" / filename
            golden_path = golden_base_path / scenario / day / filename
            
            if not golden_path.exists():
                differences.append(f"⚠️  Golden file not found: {golden_path}")
                continue
            
            if not actual_path.exists():
                differences.append(f"❌ Actual file not found: {actual_path}")
                continue
            
            actual_content = actual_path.read_text(encoding="utf-8")
            golden_content = golden_path.read_text(encoding="utf-8")
            
            # Normalize content based on file type
            if filename.endswith('.md'):
                actual_normalized = self._normalize_markdown(actual_content)
                golden_normalized = self._normalize_markdown(golden_content)
            elif filename.endswith('.csv'):
                actual_normalized = self._normalize_csv(actual_content)
                golden_normalized = self._normalize_csv(golden_content)
            elif filename.endswith('.json'):
                actual_normalized = self._normalize_json(actual_content)
                golden_normalized = self._normalize_json(golden_content)
            else:
                # For unknown types, compare as-is
                actual_normalized = actual_content
                golden_normalized = golden_content
            
            if actual_normalized != golden_normalized:
                differences.append(f"⚠️  {day}/{filename}: Content differs from golden file (after normalization)")
        
        return differences

