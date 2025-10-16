# Flow Expected Results Documentation

## Overview

The `flow_expected_results.csv` file serves as the **authoritative baseline** for validating flow analysis results. This file contains the expected behavior and results for all segment-event combinations, providing a reference point for automated testing and manual validation of flow analysis reports.

## Purpose

### Primary Use Cases
1. **Automated Testing**: Compare actual flow analysis results against expected values
2. **Regression Detection**: Identify when changes to the algorithm affect results
3. **Validation Framework**: Ensure flow analysis produces consistent, expected outcomes
4. **Documentation**: Provide context for why certain results are expected

### When to Use
- **After code changes**: Validate that modifications don't break expected behavior
- **During development**: Ensure new features maintain existing functionality
- **Before releases**: Comprehensive validation of all segment-event combinations
- **Debugging**: Compare actual vs expected results to identify issues

## File Structure

The expected results file contains **32 columns** organized into **7 logical groups**:

### 1. Core Identification (4 columns)
**Purpose**: Uniquely identify each segment-event combination

| Column | Description | Example |
|--------|-------------|---------|
| `seg_id` | Segment identifier | `A1`, `F1`, `M1` |
| `segment_label` | Human-readable segment name | `Start to Queen/Regent` |
| `event_a` | First event in comparison | `Full`, `Half`, `10K` |
| `event_b` | Second event in comparison | `Full`, `Half`, `10K` |

### 2. Segment Boundaries (4 columns)
**Purpose**: Define the spatial extent of each event within the segment

| Column | Description | Example |
|--------|-------------|---------|
| `from_km_a` | Start kilometer for event A | `0`, `2.7`, `20.85` |
| `to_km_a` | End kilometer for event A | `0.9`, `5.0`, `21.1` |
| `from_km_b` | Start kilometer for event B | `0`, `5.8`, `9.75` |
| `to_km_b` | End kilometer for event B | `0.9`, `8.1`, `10.0` |

### 3. Convergence Analysis (8 columns)
**Purpose**: Define convergence detection and spatial/temporal overlap logic

| Column | Description | Example |
|--------|-------------|---------|
| `convergence_point_km` | Absolute convergence point | `1.33`, `20.75`, `None` |
| `convergence_point_fraction` | Normalized convergence point (0.0-1.0) | `0.48`, `0.0`, `None` |
| `has_convergence` | Overall convergence flag | `TRUE`, `FALSE` |
| `convergence_zone_start` | Start of convergence zone (fraction) | `0.42`, `0.3`, `None` |
| `convergence_zone_end` | End of convergence zone (fraction) | `0.53`, `0.7`, `None` |
| `spatial_zone_exists` | Spatial overlap exists | `TRUE`, `FALSE` |
| `temporal_overlap_exists` | Temporal overlap exists | `TRUE`, `FALSE` |
| `true_pass_exists` | Actual overtaking occurs | `TRUE`, `FALSE` |
| `has_convergence_policy` | Policy-based convergence flag | `TRUE`, `FALSE` |
| `no_pass_reason_code` | Reason when no passes occur | `SPATIAL_ONLY_NO_TEMPORAL` |

### 4. Counting Results (8 columns)
**Purpose**: Expected overtaking and copresence counts

| Column | Description | Example |
|--------|-------------|---------|
| `total_a` | Total runners in event A | `368`, `912`, `618` |
| `total_b` | Total runners in event B | `368`, `912`, `618` |
| `overtaking_a` | Event A runners who overtake | `0`, `9`, `694` |
| `overtaking_b` | Event B runners who overtake | `0`, `9`, `451` |
| `copresence_a` | Event A runners in copresence | `0`, `9`, `912` |
| `copresence_b` | Event B runners in copresence | `0`, `9`, `555` |
| `pct_a` | Percentage of event A overtaking | `0.0`, `1.0`, `76.1` |
| `pct_b` | Percentage of event B overtaking | `0.0`, `1.5`, `73.0` |

### 5. Analysis Parameters (3 columns)
**Purpose**: Configuration parameters used in the analysis

| Column | Description | Example |
|--------|-------------|---------|
| `conflict_length_m` | Conflict zone length in meters | `100`, `150`, `200` |
| `width_m` | Segment width in meters | `3.0`, `1.5`, `5.0` |
| `flow_type` | Type of flow interaction | `overtake`, `merge`, `none` |

### 6. Validation Data (2 columns)
**Purpose**: Sample runner IDs for manual verification

| Column | Description | Example |
|--------|-------------|---------|
| `sample_a` | Sample runner IDs from event A | `"1628, 1631, 1632, ... (9 total)"` |
| `sample_b` | Sample runner IDs from event B | `"1598, 1602, 1603, ... (9 total)"` |

### 7. Expected Behavior (1 column)
**Purpose**: Narrative explanation of expected results

| Column | Description | Example |
|--------|-------------|---------|
| `notes` | Expected behavior explanation | `"Minimal given start_time gaps between Half and 10K. If convergence: Fast Half and Slow 10K (pace) or 10K with high start_offset."` |

## Usage Patterns

### Automated Validation
```python
import pandas as pd

# Load expected and actual results
expected = pd.read_csv('docs/flow_expected_results.csv')
actual = pd.read_csv('reports/analysis/2025-09-07/0000-1500/2025-09-07-1559-Flow.csv')

# Compare key metrics
comparison = expected.merge(actual, on=['seg_id', 'event_a', 'event_b'], suffixes=('_expected', '_actual'))

# Check for discrepancies
discrepancies = comparison[
    (comparison['overtaking_a_expected'] != comparison['overtaking_a_actual']) |
    (comparison['overtaking_b_expected'] != comparison['overtaking_b_actual'])
]

print(f"Found {len(discrepancies)} discrepancies")
```

### Manual Validation
1. **Load the expected results file**
2. **Filter to specific segment**: `seg_id == 'M1'`
3. **Check expected counts**: Compare `overtaking_a/b` with actual results
4. **Read the narrative**: Review `notes` column for context
5. **Validate samples**: Check `sample_a/b` runner IDs against actual data

### Regression Testing
```bash
# Generate current flow analysis
python3 -c "
from app.flow import analyze_temporal_flow_segments
results = analyze_temporal_flow_segments('data/runners.csv', 'data/segments_new.csv', {'Full': 420, '10K': 440, 'Half': 460})
"

# Compare against expected results
python3 -c "
import pandas as pd
expected = pd.read_csv('docs/flow_expected_results.csv')
# ... comparison logic ...
"
```

## Key Segments to Monitor

### High-Impact Segments
- **F1 Half vs 10K**: High overtaking rates (76.1%, 73.0%) - requires Flow Runner Audit
- **M1 Full vs Half**: Moderate overtaking (17.9%, 10.5%) - validate runner 1640 inclusion
- **M1 Half vs 10K**: Low overtaking (1.0%, 1.5%) - verify start_offset impact

### Zero-Overtake Segments
- **A1, A2, A3**: Early segments with no expected overtaking
- **H1**: Bi-directional flow segments
- **J1, J4, J5**: Turn segments with no convergence

### Spatial-Only Segments
- **B2, F1, I1, K1, L1**: Segments with spatial zones but no temporal overlap
- **Reason Code**: `SPATIAL_ONLY_NO_TEMPORAL`

## Maintenance Guidelines

### When to Update
1. **Algorithm Changes**: Update expected counts when overtaking logic changes
2. **Parameter Changes**: Update when `conflict_length_m` or other parameters change
3. **Data Changes**: Update when `runners.csv` or `segments_new.csv` structure changes
4. **New Segments**: Add new segment-event combinations as they're discovered

### Update Process
1. **Generate new analysis** with current algorithm
2. **Compare against expected results** to identify changes
3. **Validate changes** are intentional and correct
4. **Update expected results** with new values
5. **Update notes** to reflect new expected behavior
6. **Test the updated file** with validation scripts

### Version Control
- **Commit changes** when updating expected results
- **Document reasons** for changes in commit messages
- **Tag releases** when expected results are stable
- **Archive old versions** for historical reference

## Integration with Testing

### End-to-End Testing
The expected results file integrates with the comprehensive testing framework:

```python
# In app/end_to_end_testing.py
def validate_flow_results():
    expected = pd.read_csv('docs/flow_expected_results.csv')
    actual = generate_current_flow_analysis()
    
    discrepancies = compare_results(expected, actual)
    
    if len(discrepancies) > 0:
        print(f"⚠️ Found {len(discrepancies)} discrepancies")
        return False
    else:
        print("✅ All flow results match expected values")
        return True
```

### Continuous Integration
- **Automated validation** on every code change
- **Regression detection** when expected results change
- **Quality gates** preventing deployment of broken analysis

## Troubleshooting

### Common Issues
1. **Count Mismatches**: Check if algorithm parameters changed
2. **Missing Segments**: Verify all segment-event combinations are included
3. **Sample Data Issues**: Ensure sample runner IDs are still valid
4. **Notes Outdated**: Update narrative explanations when behavior changes

### Debugging Process
1. **Identify the discrepancy** (which segment, which metric)
2. **Check the notes** for expected behavior explanation
3. **Validate sample data** against current runner data
4. **Review algorithm parameters** for changes
5. **Update expected results** if change is intentional

---

**Last Updated**: 2025-09-07  
**File Location**: `docs/flow_expected_results.csv`  
**Related Files**: `docs/Application Architecture.md`, `docs/Application Fundamentals.md`
