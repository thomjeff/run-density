# Application Architecture

This document covers the core architectural concepts, modules, and testing approaches for the run-density application.

## 1. Flow vs. Density Analysis

### Flow Analysis (`app/flow.py`)
**Purpose**: Temporal analysis of runner interactions and overtaking patterns

**Key Inputs**:
- `runners.csv` - Individual runner pace data and start offsets
- `segments_new.csv` - Segment definitions with flow types (overtake, merge, nan)
- `start_times` - Event start times in minutes from midnight
- Configuration parameters (tolerance, conflict length, overlap duration)

**Core Calculations**:
- **Convergence Detection**: Finds where runners from different events interact
- **Overtaking Analysis**: Counts actual passes between events
- **Temporal Overlaps**: Identifies when runners are present simultaneously
- **Sample Data Collection**: Captures runner IDs involved in interactions

**Output**: Structured data with convergence points, overtaking counts, and sample runners

### Density Analysis (`app/density.py`)
**Purpose**: Spatial analysis of runner density and crowding patterns

**Key Inputs**:
- `runners.csv` - Individual runner pace data and start offsets
- `segments_new.csv` - Segment definitions with width measurements
- `start_times` - Event start times in minutes from midnight
- Configuration parameters (bin size, thresholds, step size)

**Core Calculations**:
- **Areal Density**: Runners per square meter
- **Linear Density**: Runners per meter of course width
- **Time Series Analysis**: Density changes over time
- **Threshold Analysis**: Identifying crowded periods

**Output**: Density metrics, time series data, and crowding alerts

### Key Differences
| Aspect | Flow Analysis | Density Analysis |
|--------|---------------|------------------|
| **Focus** | Runner interactions | Spatial crowding |
| **Input** | Flow types, overtake flags | Width measurements |
| **Output** | Convergence points, overtakes | Density metrics, thresholds |
| **Time Scale** | Event interactions | Continuous monitoring |
| **Primary Use** | Safety, course design | Crowd management |

## 2. Reporting Modules

### Temporal Flow Reports (`app/temporal_flow_report.py`)
**Purpose**: Generate human-readable and machine-readable flow analysis reports

**Functions**:
- `generate_temporal_flow_report()` - Creates markdown report
- `export_temporal_flow_csv()` - Creates CSV data export
- `format_bib_range()` - Formats runner ID samples

**Input**: Flow analysis results from `app/flow.py`
**Output**: 
- Markdown files: `*_Temporal_Flow_Report.md`
- CSV files: `temporal_flow_analysis_*.csv`

**Key Features**:
- Event start times table
- Segment-by-segment analysis
- Convergence point visualization (absolute and normalized)
- Overtaking statistics with percentages
- Sample runner data for verification

### Density Reports (`app/density_report.py`)
**Purpose**: Generate human-readable density analysis reports

**Functions**:
- `generate_density_report()` - Creates comprehensive density analysis
- `format_density_summary()` - Formats density metrics
- `generate_time_series_charts()` - Creates temporal visualizations

**Input**: Density analysis results from `app/density.py`
**Output**: 
- Markdown files: `*_Density_Analysis_Report.md`

**Key Features**:
- Per-event density views
- Threshold-based alerts
- Time series analysis
- Segment-specific density patterns

### API Integration (`app/main.py`)
**Purpose**: Web API endpoints for report generation

**Endpoints**:
- `/api/temporal-flow-report` - Generates flow reports via API
- `/api/density-report` - Generates density reports via API
- `/api/temporal-flow` - Raw flow data
- `/api/density` - Raw density data

**Usage Pattern**:
```python
# Generate reports via API
response = client.post('/api/temporal-flow-report', json={
    'paceCsv': 'data/runners.csv',
    'segmentsCsv': 'data/segments_new.csv',
    'startTimes': {'10K': 420, 'Half': 440, 'Full': 460}
})
```

## 3. Reusable Modules and Principles

### Principles for Reusable Modules
1. **Single Responsibility**: Each module has one clear purpose
2. **Configuration-Driven**: Use constants and parameters, not hardcoded values
3. **Input Validation**: Validate inputs and provide clear error messages
4. **Consistent Interfaces**: Standard parameter patterns across modules
5. **Documentation**: Clear docstrings and type hints
6. **Testing**: Comprehensive test coverage for all functions

### Current Reusable Modules

#### Core Analysis Modules
- **`app/flow.py`** - Temporal flow analysis engine
- **`app/density.py`** - Density analysis engine
- **`app/overlap.py`** - Overlap and convergence detection algorithms

#### Utility Modules
- **`app/constants.py`** - Application-wide constants and configuration
- **`app/conversion_audit.py`** - Data conversion validation utilities
- **`app/flow_validation.py`** - Flow analysis validation framework

#### Report Generation
- **`app/temporal_flow_report.py`** - Flow report generation
- **`app/density_report.py`** - Density report generation

#### API and Integration
- **`app/main.py`** - FastAPI web interface
- **`app/density_api.py`** - Density-specific API endpoints

### Module Dependencies
```
main.py
├── flow.py → overlap.py, constants.py
├── density.py → constants.py
├── temporal_flow_report.py → flow.py, constants.py
├── density_report.py → density.py, constants.py
└── end_to_end_testing.py → all modules
```

## 4. Testing Approach and Utilities

### Testing Philosophy
1. **End-to-End Focus**: Test through API endpoints, not direct module calls
2. **Real Report Generation**: Generate actual markdown and CSV files
3. **Comprehensive Coverage**: Test all major functionality paths
4. **Validation Framework**: Automated quality checks for reports
5. **Regression Prevention**: Catch breaking changes early

### Current Testing Utilities

#### Primary Testing Module (`app/end_to_end_testing.py`)
**Purpose**: Comprehensive testing of all application functionality

**Functions**:
- `test_api_endpoints()` - Tests all API endpoints
- `test_report_generation()` - Tests report generation modules
- `test_report_content_quality()` - Validates report content
- `run_comprehensive_tests()` - Runs all tests in sequence

**Usage**:
```bash
# Run all tests
python3 -m app.end_to_end_testing

# Run specific test components
python3 -c "from app.end_to_end_testing import test_api_endpoints; test_api_endpoints()"
```

#### Validation Framework (`app/flow_validation.py`)
**Purpose**: Automated validation of flow analysis results

**Classes**:
- `FlowValidationFramework` - Main validation engine
- Validation checks for data integrity, convergence detection, sample data quality

**Usage**:
```python
from app.flow_validation import FlowValidationFramework

validator = FlowValidationFramework()
results = validator.validate_flow_analysis(segments)
```

#### Conversion Audit (`app/conversion_audit.py`)
**Purpose**: Validate data conversion between schemas

**Functions**:
- `audit_segments_overview()` - Overview of segment data
- `audit_conversion_pairs()` - Validate event pair generation
- `run_comprehensive_conversion_audit()` - Complete audit process

### Testing Workflow

#### 1. Development Testing
```bash
# Quick validation during development
python3 -c "
from app.flow import analyze_temporal_flow_segments
results = analyze_temporal_flow_segments('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
print(f'Analyzed {len(results.get(\"segments\", []))} segments')
"
```

#### 2. Comprehensive Testing
```bash
# Full end-to-end test suite
source test_env/bin/activate
python3 -m app.end_to_end_testing
```

#### 3. Report Validation
```bash
# Validate generated reports
python3 -c "
from app.end_to_end_testing import test_report_content_quality
results = test_report_content_quality()
print(f'Quality Score: {results[\"overall_quality\"]}')
"
```

### Test Data Requirements
- **`data/runners.csv`** - Must contain realistic pace and start_offset data
- **`data/segments_new.csv`** - Must have proper width_m and flow_type values
- **Start Times** - Always use `{'10K': 420, 'Half': 440, 'Full': 460}`

### Quality Metrics
- **API Endpoints**: All must return 200 status codes
- **Report Generation**: Must produce valid markdown and CSV files
- **Content Quality**: No NaN values, proper formatting, realistic data
- **Performance**: Reports should generate within reasonable time limits

## Integration Patterns

### Module Integration
```python
# Standard pattern for analysis modules
def analyze_data(input_file, segments_file, start_times, **config):
    # Load and validate inputs
    # Perform analysis
    # Return structured results
    return results

# Standard pattern for report modules  
def generate_report(analysis_results, output_dir=None):
    # Process analysis results
    # Generate markdown and CSV
    # Return file paths
    return report_paths
```

### Configuration Management
```python
# Use constants for all configuration
from app.constants import (
    DEFAULT_MIN_OVERLAP_DURATION,
    TEMPORAL_OVERLAP_TOLERANCE_SECONDS,
    CONFLICT_LENGTH_SHORT_SEGMENT_M
)

# Pass configuration as parameters
results = analyze_temporal_flow_segments(
    pace_csv, segments_csv, start_times,
    min_overlap_duration=DEFAULT_MIN_OVERLAP_DURATION
)
```

---

*This document should be updated whenever new modules are added or architectural patterns change.*
