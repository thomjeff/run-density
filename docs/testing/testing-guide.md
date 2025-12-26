# Testing Guide - Runflow v2

**Version:** v2.0.2+  
**Last Updated:** 2025-12-26  
**Audience:** Developers writing and maintaining tests

This guide provides a comprehensive overview of the testing strategy, test organization, and how to run tests in the Runflow v2 codebase.

---

## Testing Strategy

### Test Pyramid

```
        /\
       /E2E\          ← End-to-End Tests (tests/v2/e2e.py)
      /------\
     /Integration\    ← Integration Tests (test_api.py, test_flow.py, etc.)
    /------------\
   /   Unit Tests  \  ← Unit Tests (test_validation.py, test_models.py, etc.)
  /----------------\
```

**Philosophy:**
- **Unit Tests** - Fast, isolated, test individual functions
- **Integration Tests** - Test module interactions and data flow
- **E2E Tests** - Test complete workflows from API request to output generation

### Test Types

1. **Unit Tests** - Test individual functions in isolation
2. **Integration Tests** - Test module interactions (e.g., validation → pipeline → reports)
3. **E2E Tests** - Test complete API workflows with real data
4. **UI Tests** - Manual testing checklist for UI verification

---

## Test Organization

### Directory Structure

```
tests/
└── v2/                          # All v2 tests
    ├── __init__.py
    ├── conftest.py              # Pytest fixtures and configuration
    ├── e2e.py                   # End-to-end tests
    ├── test_analysis_config.py  # analysis.json generation tests
    ├── test_analysis_json_validation.py  # analysis.json content validation
    ├── test_api.py              # API endpoint tests
    ├── test_bins.py             # Bin generation tests
    ├── test_density.py          # Density analysis tests
    ├── test_flow.py             # Flow analysis tests
    ├── test_hardcoded_values.py # No hardcoded values validation
    ├── test_loader.py           # Data loading tests
    ├── test_models.py           # Pydantic model tests
    ├── test_timeline.py         # Timeline generation tests
    ├── test_validation.py       # Validation function tests
    └── test_validation_errors.py # Error handling tests
```

### Test File Naming Convention

- `test_*.py` - Unit and integration tests
- `e2e.py` - End-to-end tests (special case)
- `conftest.py` - Pytest configuration and fixtures

---

## Test Files Overview

### E2E Tests (`e2e.py`)

**Purpose:** Test complete workflows from API request to output generation

**Test Classes:**
- `TestV2E2EScenarios` - Multi-day analysis scenarios
  - `test_saturday_only_scenario` - Saturday-only analysis
  - `test_sunday_only_scenario` - Sunday-only analysis
  - `test_sat_sun_scenario` - Multi-day analysis (both days)

**Key Features:**
- Tests complete API workflow
- Validates day isolation (no cross-day contamination)
- Validates output file generation

**Running:**
```bash
make e2e          # Run sat+sun E2E test
make e2e-full     # Run all E2E test scenarios
pytest tests/v2/e2e.py -v
```

### Unit Tests

#### `test_validation.py`
**Purpose:** Test validation functions

**Test Classes:**
- `TestValidateDayCodes` - Day code validation
- `TestValidateStartTimes` - Start time range validation
- `TestValidateEventNames` - Event name validation
- `TestValidateFileExistence` - File existence checks
- `TestValidateSegmentSpans` - Segment range validation
- `TestValidateRunnerUniqueness` - Runner ID uniqueness
- `TestValidateApiPayload` - Complete API payload validation

#### `test_analysis_config.py`
**Purpose:** Test `analysis.json` generation and helper functions

**Test Classes:**
- `TestGenerateAnalysisJson` - JSON generation
- `TestLoadAnalysisJson` - JSON loading
- `TestHelperFunctions` - Helper function tests
- `TestCountRunnersInFile` - Runner counting

#### `test_models.py`
**Purpose:** Test Pydantic models

**Test Classes:**
- `TestDay` - Day model validation
- `TestRunner` - Runner model validation
- `TestSegment` - Segment model validation
- `TestEvent` - Event model validation

#### `test_validation_errors.py`
**Purpose:** Test error handling and error response format

**Test Classes:**
- `TestValidationErrorHandling` - Error response validation

### Integration Tests

#### `test_api.py`
**Purpose:** Test API endpoints

**Test Classes:**
- `TestV2AnalyzeEndpoint` - `/runflow/v2/analyze` endpoint tests
- `TestV2Models` - Request/response model validation

#### `test_flow.py`
**Purpose:** Test flow analysis logic

**Test Classes:**
- `TestGetSharedSegments` - Shared segment detection
- `TestGenerateEventPairsV2` - Event pair generation
- `TestLoadFlowMetadata` - Flow metadata loading

#### `test_density.py`
**Purpose:** Test density analysis logic

**Test Classes:**
- `TestGetEventDistanceRangeV2` - Distance range calculation
- `TestLoadAllRunnersForEvents` - Runner loading
- `TestFilterRunnersByDay` - Day filtering
- `TestAnalyzeDensitySegmentsV2` - Density analysis

#### `test_bins.py`
**Purpose:** Test bin generation logic

**Test Classes:**
- `TestCalculateRunnerArrivalTime` - Arrival time calculation
- `TestEnforceCrossDayGuard` - Cross-day guard enforcement
- `TestFilterSegmentsByEvents` - Segment filtering
- `TestResolveSegmentSpans` - Segment span resolution
- `TestCreateBinsForSegmentV2` - Bin creation
- `TestGenerateBinsPerDay` - Day-partitioned bin generation

#### `test_loader.py`
**Purpose:** Test data loading functions

**Test Classes:**
- `TestLoadEventsFromPayload` - Event loading from API payload
- `TestLoadRunnersForEvent` - Runner file loading
- `TestGroupEventsByDay` - Day grouping

#### `test_timeline.py`
**Purpose:** Test timeline generation

**Test Classes:**
- `TestGetDayStart` - Day start time calculation
- `TestGenerateDayTimelines` - Timeline generation
- `TestNormalizeTimeToDay` - Time normalization
- `TestDayTimeline` - Day timeline structure

#### `test_hardcoded_values.py`
**Purpose:** Ensure no hardcoded values (Issue #553)

**Test Classes:**
- `TestNoHardcodedStartTimes` - Start time validation
- `TestStartTimeValidation` - Start time validation rules
- `TestFlowOrderingUsesFlowCsv` - Flow ordering validation
- `TestNoHardcodedRunnerCounts` - Runner count validation
- `TestConstantsUsage` - Constants usage validation

#### `test_analysis_json_validation.py`
**Purpose:** Validate `analysis.json` content matches request

**Test Classes:**
- `TestAnalysisJsonValidation` - JSON content validation

---

## Running Tests

### Quick Start

```bash
# Start development container
make dev

# Run all tests
pytest tests/v2/ -v

# Run specific test file
pytest tests/v2/test_validation.py -v

# Run specific test class
pytest tests/v2/test_validation.py::TestValidateStartTimes -v

# Run specific test method
pytest tests/v2/test_validation.py::TestValidateStartTimes::test_valid_start_times -v
```

### E2E Tests

```bash
# Run sat+sun E2E test (recommended)
make e2e

# Run full E2E test suite
make e2e-full

# Run Saturday-only E2E test
make e2e-sat

# Run Sunday-only E2E test
make e2e-sun

# Run with coverage
make e2e-coverage-lite DAY=both
```

### Test Coverage

```bash
# Run with coverage
pytest tests/v2/ --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

---

## Writing Tests

### Test Structure

```python
import pytest
from app.core.v2.validation import validate_start_times, ValidationError

class TestValidateStartTimes:
    """Test start time validation."""
    
    def test_valid_start_times(self):
        """Test valid start times pass validation."""
        events = [
            {"name": "elite", "start_time": 480},
            {"name": "open", "start_time": 510}
        ]
        # Should not raise
        validate_start_times(events)
    
    def test_invalid_start_time_too_early(self):
        """Test start time before 5:00 AM fails."""
        events = [{"name": "elite", "start_time": 299}]
        with pytest.raises(ValidationError) as exc_info:
            validate_start_times(events)
        assert "must be between 300 and 1200" in str(exc_info.value)
```

### Best Practices

1. **Test Names** - Use descriptive names: `test_valid_start_times`, not `test_1`
2. **Test Classes** - Group related tests in classes
3. **Docstrings** - Document what each test validates
4. **Arrange-Act-Assert** - Clear test structure
5. **Isolation** - Each test should be independent
6. **Fast Tests** - Unit tests should run quickly (< 1 second each)
7. **No Hardcoded Values** - Use fixtures and test data, not hardcoded values

### Fixtures

Use `conftest.py` for shared fixtures:

```python
# tests/v2/conftest.py
import pytest

@pytest.fixture
def sample_payload():
    """Sample API payload for testing."""
    return {
        "description": "Test analysis",
        "segments_file": "segments.csv",
        "flow_file": "flow.csv",
        "locations_file": "locations.csv",
        "events": [
            {
                "name": "elite",
                "day": "sat",
                "start_time": 480,
                "event_duration_minutes": 45,
                "runners_file": "elite_runners.csv",
                "gpx_file": "elite.gpx"
            }
        ]
    }
```

---

## Test Maintenance

### When to Add Tests

- ✅ New feature added
- ✅ Bug fixed (add regression test)
- ✅ Refactoring (ensure behavior unchanged)
- ✅ Edge case discovered

### When to Update Tests

- ✅ Output format changes
- ✅ API contract changes
- ✅ Validation rules change

### Test Cleanup

**Periodic cleanup tasks:**
- Remove obsolete tests
- Consolidate duplicate tests
- Remove unused fixtures
- Update test documentation

---

## Troubleshooting

### Tests Failing

1. **Check container is running:**
   ```bash
   docker ps | grep run-density-dev
   ```

2. **Check logs:**
   ```bash
   docker logs run-density-dev --tail 100
   ```

3. **Run tests with verbose output:**
   ```bash
   pytest tests/v2/test_validation.py -v -s
   ```

4. **Run single test:**
   ```bash
   pytest tests/v2/test_validation.py::TestValidateStartTimes::test_valid_start_times -v
   ```

---

## Related Documentation

- **UI Testing:** `docs/testing/ui-testing-checklist.md` - Manual UI testing procedures
- **Developer Guide:** `docs/dev-guides/developer-guide-v2.md` - Testing section
- **Docker Dev:** `docs/dev-guides/docker-dev.md` - Running tests in Docker

---

**Version:** v2.0.2+  
**Last Updated:** 2025-12-26  
**Issue:** #553

