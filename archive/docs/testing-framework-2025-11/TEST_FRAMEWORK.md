# Test Framework Documentation

## Overview

The Run-Density test framework provides a comprehensive, reusable testing system for validating temporal flow and density analysis functionality. It's designed to be:

- **Test ID-based**: Each test has a unique identifier for easy execution
- **API-integrated**: Can be called from REST endpoints
- **Frontend-ready**: Designed for future UI integration
- **Maintainable**: Structured for easy addition of new tests
- **Reliable**: Provides consistent, repeatable results

## Architecture

### Directory Structure

```
tests/
├── __init__.py                 # Test framework package
├── test_runner.py             # Main test runner and CLI interface
├── temporal_flow_tests.py     # Temporal flow test suite
└── density_tests.py           # Density analysis test suite

app/
└── test_api.py                # FastAPI endpoints for test execution

run_tests.sh                   # Shell script for easy test execution
```

### Core Components

1. **TestRunner**: Main orchestrator that manages test execution
2. **TestResult**: Standardized result data structure
3. **Test Suites**: Modular test collections (temporal_flow_tests, density_tests)
4. **API Integration**: REST endpoints for programmatic access
5. **CLI Interface**: Command-line interface for manual testing

## Available Tests

### Temporal Flow Tests

| Test ID | Description | Purpose |
|---------|-------------|---------|
| `temporal_flow_convergence` | Validates convergence segment detection | Ensures all 11 expected convergence segments are correctly identified |
| `temporal_flow_comprehensive` | Comprehensive validation of all 36 segments | Validates complete temporal flow analysis against expected results |
| `temporal_flow_smoke` | Basic functionality smoke test | Quick validation that temporal flow analysis runs without errors |

### Density Tests

| Test ID | Description | Purpose |
|---------|-------------|---------|
| `density_comprehensive` | Comprehensive density analysis test | Validates density calculations for all segments |
| `density_validation` | Density calculation validation | Ensures density calculations meet mathematical constraints |
| `density_smoke` | Basic density functionality test | Quick validation that density analysis runs without errors |

## Usage

### Command Line Interface

#### List Available Tests
```bash
python tests/test_runner.py --list-tests
./run_tests.sh --list
```

#### Run Specific Test
```bash
python tests/test_runner.py --test-id temporal_flow_convergence
./run_tests.sh temporal_flow_convergence
```

#### Run All Tests
```bash
python tests/test_runner.py --run-all
./run_tests.sh --all
```

#### Run Test Categories
```bash
./run_tests.sh --smoke           # Run smoke tests only
./run_tests.sh --comprehensive   # Run comprehensive tests only
```

#### Save Test Reports
```bash
python tests/test_runner.py --test-id temporal_flow_convergence --save-report
./run_tests.sh temporal_flow_convergence --save-report
```

### API Endpoints

#### List Tests
```http
GET /api/tests/list
```

#### Run Specific Test
```http
POST /api/tests/run
Content-Type: application/json

{
  "test_id": "temporal_flow_convergence",
  "save_report": false
}
```

#### Run All Tests
```http
POST /api/tests/run-all?save_report=false
```

#### Quick Health Checks
```http
GET /api/tests/temporal-flow/quick-check
GET /api/tests/density/quick-check
GET /api/tests/comprehensive/validation
```

### Test Results

#### TestResult Structure
```json
{
  "test_id": "temporal_flow_convergence",
  "status": "PASS|FAIL|ERROR",
  "message": "Human-readable test result message",
  "details": {
    "total_segments_processed": 36,
    "expected_convergence": 11,
    "actual_convergence": 11,
    "passed_segments": ["A1b", "A1c", "B1", ...],
    "failed_segments": [],
    "start_times_used": {"Full": 0, "10K": 20, "Half": 40}
  },
  "execution_time": 26.37,
  "timestamp": "2025-09-04T10:30:00"
}
```

#### Test Report Structure
```json
{
  "summary": {
    "total_tests": 6,
    "passed": 6,
    "failed": 0,
    "errors": 0,
    "success_rate": 100.0,
    "timestamp": "2025-09-04T10:30:00"
  },
  "results": [...]
}
```

## Configuration

### Start Times
The test framework uses the correct start times in seconds:
- **Full**: 420 seconds (7:00 AM)
- **10K**: 440 seconds (7:20 AM) 
- **Half**: 460 seconds (7:40 AM)

### Test Data
Tests use the following data files:
- `data/your_pace_data.csv` - Runner pace data
- `data/segments.csv` - Segment definitions
- `comprehensive_segments_test_report_fixed.csv` - Expected results for validation

## Adding New Tests

### 1. Create Test Function
```python
def test_new_functionality(self) -> TestResult:
    """Test ID: new_functionality_test"""
    try:
        # Test implementation
        result = some_analysis_function()
        
        # Validation logic
        if result.is_valid():
            return TestResult(
                test_id="new_functionality_test",
                status="PASS",
                message="New functionality works correctly",
                details={"result": result.to_dict()}
            )
        else:
            return TestResult(
                test_id="new_functionality_test",
                status="FAIL",
                message="New functionality failed validation",
                details={"issues": result.get_issues()}
            )
    except Exception as e:
        return TestResult(
            test_id="new_functionality_test",
            status="ERROR",
            message=f"Test execution failed: {str(e)}",
            details={"error": str(e)}
        )
```

### 2. Register Test
```python
# In test_runner.py register_tests() method
self.test_registry.update({
    "new_functionality_test": new_test_suite.test_new_functionality,
})
```

### 3. Add API Endpoint (Optional)
```python
# In test_api.py
@test_router.get("/new-functionality/quick-check")
async def new_functionality_quick_check():
    """Quick check of new functionality"""
    try:
        result = test_runner.run_test("new_functionality_test")
        return {
            "test_id": "new_functionality_test",
            "status": result.status,
            "message": result.message,
            "execution_time": result.execution_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")
```

## Best Practices

### Test Design
1. **Single Responsibility**: Each test should validate one specific aspect
2. **Clear Naming**: Test IDs should be descriptive and follow naming conventions
3. **Comprehensive Validation**: Include both positive and negative test cases
4. **Detailed Results**: Provide meaningful details for debugging failures

### Error Handling
1. **Graceful Failures**: Tests should handle errors gracefully and provide useful error messages
2. **Timeout Protection**: Long-running tests should have reasonable timeouts
3. **Resource Cleanup**: Tests should clean up any resources they create

### Performance
1. **Efficient Execution**: Tests should run as quickly as possible while maintaining thoroughness
2. **Parallel Execution**: Consider parallel execution for independent tests
3. **Resource Management**: Monitor memory and CPU usage during test execution

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: Run Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run smoke tests
        run: ./run_tests.sh --smoke
      - name: Run comprehensive tests
        run: ./run_tests.sh --comprehensive --save-report
      - name: Upload test reports
        uses: actions/upload-artifact@v2
        with:
          name: test-reports
          path: results/test_runs/
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed and paths are correct
2. **Data File Issues**: Verify that required data files exist and are accessible
3. **Permission Issues**: Ensure test files have proper execution permissions
4. **Memory Issues**: Monitor memory usage for large test suites

### Debug Mode
```bash
# Run with verbose output
python tests/test_runner.py --test-id temporal_flow_convergence --verbose

# Run with debug logging
PYTHONPATH=. python -m pytest tests/ -v
```

## Future Enhancements

1. **Test History**: Track test execution history and trends
2. **Performance Benchmarking**: Add performance regression testing
3. **Visual Test Reports**: Generate HTML test reports with charts
4. **Test Dependencies**: Support for test dependencies and ordering
5. **Parallel Execution**: Run independent tests in parallel
6. **Test Data Management**: Better management of test data and fixtures
7. **Integration Testing**: End-to-end integration tests
8. **Load Testing**: Performance and load testing capabilities

## Support

For issues with the test framework:
1. Check the test logs in `results/test_runs/`
2. Verify data file integrity
3. Ensure all dependencies are installed
4. Check the API health endpoint: `GET /api/tests/health`
