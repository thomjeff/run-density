# Application Fundamentals

This document contains the core concepts and knowledge that anyone working on the run-density application must understand. These are the fundamental principles that govern how the system works.

## Time and Data Concepts

### Start Times - Event Start Offsets

**CRITICAL**: Event start times are stored as **minutes from midnight**, not absolute times or seconds.

```python
start_times = {
    'Full': 420,  # 7:00 AM (7 * 60 = 420 minutes from midnight)
    '10K': 440,   # 7:20 AM (7 * 60 + 20 = 440 minutes from midnight)
    'Half': 460   # 7:40 AM (7 * 60 + 40 = 460 minutes from midnight)
}
```

**What NOT to Use:**
- ❌ Hours as decimals (7.0, 7.33, 7.67)
- ❌ Seconds from midnight (25200, 26400, 27600)
- ❌ Any other time format

### Runner Data Structure (runners.csv)

The `runners.csv` file contains individual runner information with two critical columns:

1. **`pace`**: Minutes per kilometer for each runner
2. **`start_offset`**: Additional delay in **seconds** from the event start time

### Time Calculation Formula

For any runner, their absolute start time is calculated as:

```
Absolute Start Time = (Event Start Time in seconds) + (Runner's start_offset in seconds)
```

Where:
- Event Start Time in seconds = `start_times[event] * 60`
- Runner's start_offset = value from `start_offset` column

**Example:**
- 10K event starts at 420 minutes from midnight = 25,200 seconds
- Runner with start_offset of 30 seconds
- Absolute start time = 25,200 + 30 = 25,230 seconds from midnight

## Data Files and Naming

### Primary Data Files
- **`data/runners.csv`** - Runner pace data and start offsets
- **`data/segments_new.csv`** - Consolidated segment information (width, flow types)
- **`data/flow.csv`** - Legacy flow segment data
- **`data/density.csv`** - Density analysis configuration

### Report Output Files
- **`reports/analysis/*_Temporal_Flow_Report.md`** - Human-readable flow analysis
- **`reports/analysis/temporal_flow_analysis_*.csv`** - Machine-readable flow data
- **`reports/analysis/*_Density_Analysis_Report.md`** - Human-readable density analysis

## Core Analysis Principles

### Distance Normalization

**CRITICAL**: Events have different distance ranges (cumulative kilometers run). Convergence points must be normalized to account for this difference.

- **Normalized Convergence Point**: A value between 0.0 and 1.0 representing position within a segment
- **Absolute Convergence Point**: The actual kilometer mark where convergence occurs
- **Both values are required** for complete understanding

### Overtaking Detection

**Non-negotiable requirement**: Overtakes must be counted precisely - only runners who actually overtake (real temporal overlaps), not those appearing in theoretical intersection points.

- **True Pass Detection**: Identifies when one runner actually passes another
- **Co-presence Detection**: Fallback for when runners are present at the same time but may not be overtaking
- **Convergence Points**: Only reported when actual overtakes occur

### Flow Types

Segments are classified by their flow characteristics:
- **`overtake`**: Segments where runners from different events can overtake each other
- **`merge`**: Segments where events merge together
- **`nan`**: Segments without specific flow characteristics

## Configuration Constants

### Analysis Parameters
- **Default Step Size**: 0.03 km for distance calculations
- **Default Time Window**: 300 seconds (5 minutes)
- **Default Min Overlap Duration**: 5.0 seconds
- **Default Conflict Length**: 100.0 meters

### Dynamic Conflict Lengths
Conflict zones are sized based on segment characteristics:
- **Short Segments (≤ 1.0 km)**: 100m conflict zone
- **Medium Segments (1.0-2.0 km)**: 150m conflict zone  
- **Long Segments (> 2.0 km)**: 200m conflict zone

### Tolerance Values
- **Temporal Overlap Tolerance**: 5.0 seconds
- **True Pass Detection Tolerance**: 2.0 seconds (reduced for accuracy)

## Data Flow Architecture

### Module Separation
- **`app/flow.py`** - Temporal flow calculations and analysis
- **`app/density.py`** - Density calculations and analysis
- **`app/overlap.py`** - Overlap and convergence detection algorithms
- **`app/temporal_flow_report.py`** - Flow report generation
- **`app/density_report.py`** - Density report generation

### API Endpoints
- **`/api/temporal-flow`** - Raw temporal flow data
- **`/api/temporal-flow-report`** - Generated flow reports (MD + CSV)
- **`/api/density`** - Raw density data
- **`/api/density-report`** - Generated density reports

## Critical Development Rules

### No Hardcoded Values
**ABSOLUTE RULE**: Never use hardcoded values unless explicitly directed. Always use:
- Configuration constants from `app/constants.py`
- Dynamic calculations based on data
- Parameterized functions with default values

### Permanent vs Temporary Code
- **ALWAYS** modify permanent modules instead of creating temporary scripts
- **ASK** if unsure whether code should be permanent or temporary
- **PRINCIPLE**: If functionality will be used repeatedly, it belongs in permanent modules

### Testing Requirements
- **ALWAYS** test with the correct start times: `{'10K': 420, 'Half': 440, 'Full': 460}`
- **ALWAYS** generate actual markdown and CSV reports, not just JSON data
- **ALWAYS** test through API endpoints, not direct module calls

## Historical Context

These fundamentals were established through extensive testing and debugging:
- Reports were working correctly on 2025-09-04 with these exact values
- Multiple attempts to use other formats have failed
- These concepts represent lessons learned from real-world usage

---

*This document should be updated whenever new fundamental concepts are discovered or existing ones are refined.*
