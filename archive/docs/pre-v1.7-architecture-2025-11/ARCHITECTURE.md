# Run-Density System Architecture

This document provides comprehensive system design, core concepts, data flow, and module responsibilities for the run-density application.

## System Overview

Run-density analyzes crowd density and flow patterns for multi-event marathon races. It provides operational intelligence to identify congestion risks, optimize course design, and ensure runner safety.

### Core Capabilities
1. **Density Analysis**: Spatial crowding patterns (persons/m², LOS classification)
2. **Flow Analysis**: Event interactions, convergence, overtaking patterns
3. **Operational Intelligence**: Flagged bins requiring attention (CRITICAL/CAUTION/WATCH)
4. **Frontend Visualization**: Interactive maps and dashboards
5. **Report Generation**: Markdown and CSV exports for stakeholders

## Directory Structure

```
/app                    - Application code
  /io                   - Data loading modules
  /routes              - API route handlers
  /validation          - Validation frameworks
  
/config                - YAML configuration files
  density_rulebook.yml - LOS thresholds, schemas, flow capacity
  reporting.yml        - Report generation configuration
  
/data                  - CSV input files (gitignored except examples)
  runners.csv          - Runner pace and start offset data
  segments.csv         - Segment definitions, widths, flow types
  flow_expected_results.csv - Flow validation oracle
  
/docs                  - Documentation
  /user-guide          - End-user documentation (10 files)
  
/frontend              - HTML/CSS/JS frontend
  /assets              - Static assets
  /css                 - Stylesheets
  /js                  - JavaScript modules
  /pages               - HTML pages
  
/tests                 - Test suites
  test_*.py            - Unit and integration tests
  qa_regression_baseline.py - QA regression for Issue #243
  
/reports               - Generated reports (gitignored)
  /YYYY-MM-DD          - Daily report folders
    bins.parquet       - Bin-level density data
    bins.geojson.gz    - Geographic bin data
    segment_windows_from_bins.parquet - Temporal aggregations
    tooltips.json      - Operational intelligence for frontend
    *-Density.md       - Density analysis reports
    *-Flow.md          - Flow analysis reports
    *-Flow.csv         - Flow data exports
    
/cache                 - Analysis cache (gitignored)
/archive               - Historical files and deprecated docs
```

## Core Concepts

### Time Representation

**CRITICAL**: Start times are **minutes from midnight**, not hours or seconds.

```python
start_times = {
    'Full': 420,   # 07:00 AM = 7 * 60 minutes
    '10K': 440,    # 07:20 AM = 7 * 60 + 20 minutes  
    'Half': 460    # 07:40 AM = 7 * 60 + 40 minutes
}
```

**Time Calculations:**
```python
# Convert to seconds for calculations
event_start_sec = start_times[event] * 60.0

# Runner absolute start time
runner_start_time = event_start_sec + runner.start_offset_sec

# ALWAYS convert ALL events consistently - never mix units!
```

### Global Time Grid Architecture (Issue #243)

**Critical Design**: Single global clock-time grid for all events.

```python
# Global windows anchored to earliest event
t0 = race_day + timedelta(minutes=min(start_times.values()))
windows = [(t0 + i*Δ, t0 + (i+1)*Δ, i) for i in range(K)]

# Each event maps to correct starting index
start_idx = int(((event_min - earliest_start_min) * 60) // WINDOW_SECONDS)
```

**Why this matters:**
- Enables cross-event comparisons
- Prevents phantom late blocks (Issue #243)
- Ensures 10K runners appear at 07:20, not 08:12
- See `docs/GLOBAL_TIME_GRID_ARCHITECTURE.md` for details

### Terminology: Flow vs rate

**CRITICAL**: Different metrics with similar names - don't confuse them!

| Term | Scope | Units | Purpose | Files |
|------|-------|-------|---------|-------|
| **Flow** (capital F) | Event-level | Various | Convergence, overtaking, co-presence | flow.csv, flow_report.py |
| **rate** (lowercase) | Bin-level | persons/second | Throughput intensity | bins.csv, bins.parquet |

**Rate Calculation:**
```python
rate = density * width_m * mean_speed_mps
# Where: density = persons/m², width = meters, speed = m/s
# Result: persons/second (actual throughput)
```

See `docs/FLOW_VS_RATE_TERMINOLOGY.md` for complete distinction.

### Density Metrics

1. **Areal Density**: persons/m² (primary metric for LOS)
2. **Crowd Density**: persons/m (linear crowding)
3. **Mean Density**: Average across bins
4. **Peak Density**: Maximum density in window

### Level of Service (LOS)

Classification system from Fruin/Weidmann crowd dynamics:

| LOS | Density Range (p/m²) | Description |
|-----|---------------------|-------------|
| A | 0.00 - 0.50 | Free flow, no restrictions |
| B | 0.50 - 1.00 | Comfortable, room to maneuver |
| C | 1.00 - 1.50 | Moderate restrictions |
| D | 1.50 - 2.00 | Dense, limited maneuverability |
| E | 2.00 - 3.00 | Very dense, shuffling movement |
| F | 3.00+ | Extremely dense, stop-and-go |

**Configurable** via `config/density_rulebook.yml` per segment schema.

### Operational Intelligence

Automated flagging system for bins requiring attention:

**Severity Levels:**
- **CRITICAL**: Both high LOS (≥C) AND high utilization (top 5%)
- **CAUTION**: High LOS only
- **WATCH**: High utilization only
- **NONE**: No flags

**Utilization Threshold**: P95 of bin density distribution (typically top 5%)

## Module Architecture

### Analysis Engines

#### Flow Analysis (`app/flow.py`)
**Purpose**: Temporal analysis of event interactions

**Key Functions:**
- `analyze_temporal_flow_segments()` - Main analysis engine
- `detect_convergence()` - Find where events meet
- `count_overtakes()` - Actual pass detection

**Inputs:**
- runners.csv (pace, start_offset, event)
- segments.csv (flow_type, ranges per event)
- start_times (minutes from midnight)

**Outputs:**
- Convergence points (absolute and normalized)
- Overtaking counts with sample runner IDs
- Co-presence statistics

#### Density Analysis (`app/density.py`)
**Purpose**: Spatial crowding analysis

**Key Functions:**
- `analyze_density_segments()` - Main analysis engine  
- `calculate_density_windows()` - Time-series density
- `classify_los()` - Level of Service assignment

**Inputs:**
- runners.csv (pace, start_offset, event)
- segments.csv (width_m, length_m, schema_name)
- start_times (minutes from midnight)
- config/density_rulebook.yml (LOS thresholds)

**Outputs:**
- Areal and crowd density metrics
- Time series with LOS classification
- Sustained periods above thresholds

#### Bin Dataset Generation (`app/bins_accumulator.py`, `app/density_report.py`)
**Purpose**: Fine-grained spatial-temporal density analysis

**Key Functions:**
- `build_runner_window_mapping()` - Map runners to bins (Issue #243 fix)
- `build_bin_features()` - Generate bin metrics
- `generate_bin_features_with_coarsening()` - Performance optimization

**Outputs:**
- bins.parquet (8,800 bins: spatial × temporal grid)
- segment_windows_from_bins.parquet (1,760 windows: temporal aggregations)
- tooltips.json (operational intelligence for frontend)

**Metrics per Bin:**
- density (p/m²)
- rate (p/s) - throughput
- los_class (A-F)
- Timestamps (t_start, t_end)
- Spatial bounds (start_km, end_km)

### Report Generation

#### Density Reports (`app/density_report.py`)
**Functions:**
- `generate_density_report()` - Comprehensive analysis
- `generate_markdown_content()` - Unified density.md format
- `generate_operational_intelligence()` - Executive summary + bin detail

**Report Structure:**
1. Executive Summary (key metrics, flagged segments)
2. Per-Segment Analysis (temporal patterns)
3. Appendix: Bin-Level Detail (flagged segments only)

#### Flow Reports (`app/flow_report.py`)
**Functions:**
- `generate_temporal_flow_report()` - Markdown generation
- `export_temporal_flow_csv()` - CSV export

**Report Structure:**
1. Event start times table
2. Segment-by-segment convergence analysis
3. Overtaking statistics
4. Sample runner data

### API Layer (`app/main.py`)

**Core Endpoints:**
```python
# Analysis endpoints
POST /api/density-report        # Generate density analysis
POST /api/temporal-flow-report  # Generate flow analysis

# Data endpoints
GET /api/segments               # Segment data with operational intelligence
GET /api/tooltips               # Operational intelligence tooltips
GET /api/summary                # Dashboard summary data

# Frontend endpoints
GET /frontend/                  # Dashboard
GET /frontend/map.html          # Interactive map
GET /frontend/reports.html      # Reports page
```

### Operational Intelligence (`app/bin_intelligence.py`, `app/los.py`)

**Purpose**: Automated flagging and classification

**Key Functions:**
- `classify_los()` - Assign LOS levels A-F
- `flag_bins()` - Identify bins requiring attention
- `compute_p95_threshold()` - Calculate utilization threshold
- `summarize_flags_by_segment()` - Aggregate for reporting

**Flagging Logic:**
```python
# P95 utilization threshold
p95_threshold = bins['density'].quantile(0.95)

# Flagging criteria
if los >= 'C' and density > p95_threshold:
    severity = 'CRITICAL'
elif los >= 'C':
    severity = 'CAUTION'
elif density > p95_threshold:
    severity = 'WATCH'
else:
    severity = 'NONE'
```

## Data Flow

### High-Level Pipeline

```
Input Data (CSV)
    ↓
Analysis Engine (flow.py or density.py)
    ↓
Runner-Window Mapping (build_runner_window_mapping)
    ↓
Bin Feature Generation (bins_accumulator.py)
    ↓
Operational Intelligence (bin_intelligence.py, los.py)
    ↓
Report Generation (density_report.py, flow_report.py)
    ↓
Artifacts (MD, CSV, Parquet, JSON)
    ↓
Frontend (map, dashboard via API)
```

### Bin Dataset Pipeline (Issue #233)

```
1. Load Input Data
   - runners.csv → pace_data
   - segments.csv → segments_dict
   - start_times → event anchoring

2. Build Global Time Grid
   - t0 = earliest event start
   - windows = [(t_start, t_end, index), ...]

3. Map Runners to Windows (Event-First Loop - Issue #243)
   FOR each event ['Full', '10K', 'Half']:
     - Calculate start_idx for this event
     - Anchor runners to event start time
     - Map to correct global windows
     - Handle coarsening re-mapping (60s → 120s)

4. Generate Bin Features
   - Vectorized accumulation (counts, speeds)
   - Calculate density and rate
   - Classify LOS

5. Apply Operational Intelligence
   - Flag bins (LOS + utilization)
   - Assign severity levels
   - Generate tooltips.json

6. Export Artifacts
   - bins.parquet (machine-readable)
   - bins.geojson.gz (map visualization)
   - segment_windows_from_bins.parquet (temporal aggregations)
   - tooltips.json (frontend consumption)
```

## Key Algorithms

### Runner Position Calculation

```python
# For a runner at time t:
time_since_start = t - runner_start_time
runner_position_km = time_since_start / pace_sec_per_km

# Check if in segment
if from_km <= runner_position_km <= to_km:
    # Runner is in segment
    pos_m = (runner_position_km - from_km) * 1000.0
```

### Density Calculation

```python
# Bin area
area_m2 = bin_length_m * segment_width_m

# Density
density = runner_count / area_m2  # persons/m²

# Rate (throughput)
rate = density * segment_width_m * mean_speed_mps  # persons/second
```

### Coarsening with Re-Mapping (Issue #243 Fix)

When performance requires coarsening (60s → 120s windows):

```python
coarsening_factor = new_dt_seconds // old_dt_seconds  # e.g., 2

# Re-map runners to new window indices
for new_w_idx in range(len(new_windows)):
    old_start = new_w_idx * coarsening_factor
    old_end = old_start + coarsening_factor
    
    # Aggregate runners from multiple old windows
    aggregated_runners = []
    for old_idx in range(old_start, old_end):
        aggregated_runners.extend(old_mapping[old_idx])
    
    new_mapping[new_w_idx] = aggregated_runners
```

**Critical**: Without re-mapping, 10K runners at 07:20 would appear missing!

## Testing Architecture

### Test Types

1. **Unit Tests** (`tests/test_*.py`)
   - Pure functions, isolated logic
   - Fast execution (<1s total)
   - Coverage: los.py, io/loader.py, bin_intelligence.py

2. **Integration Tests** (`tests/test_*_integration.py`)
   - Module interactions
   - Small fixtures (5-10 bins)
   - Verify schemas and side effects

3. **E2E Tests** (`e2e.py`)
   - Full pipeline validation
   - Real artifacts generation
   - Both local and Cloud Run environments

4. **QA Regression** (`tests/qa_regression_baseline.py`)
   - Issue #243 fix verification
   - Event timing baseline
   - Density attenuation patterns

### Testing Commands

```bash
# Local E2E (comprehensive)
source test_env/bin/activate
python e2e.py --local

# Cloud Run E2E (production)
TEST_CLOUD_RUN=true python e2e.py --cloud

# Unit tests
pytest tests/test_*.py

# Specific test
pytest tests/test_density.py::test_specific_function

# QA regression baseline
python tests/qa_regression_baseline.py
```

### Test Environments

| Environment | URL | Purpose | Resources |
|-------------|-----|---------|-----------|
| **Local** | http://localhost:8080 | Development | Full system resources |
| **Cloud Run** | https://run-density-ln4r3sfkha-uc.a.run.app | Production | 1GB RAM / 1 CPU |
| **Test Client** | http://testserver:8080 | Unit tests | In-memory FastAPI |

## Configuration Management

### Constants (`app/constants.py`)

**Application-wide values:**
```python
# Event start times (minutes from midnight)
DEFAULT_START_TIMES = {'Full': 420, '10K': 440, 'Half': 460}

# Analysis parameters
DEFAULT_BIN_SIZE_KM = 0.1
DEFAULT_BIN_TIME_WINDOW_SECONDS = 60
DISTANCE_BIN_SIZE_KM = 0.03

# Performance limits
MAX_BIN_GENERATION_TIME_SECONDS = 90
BIN_MAX_FEATURES = 12000
HOTSPOT_SEGMENTS = ['A1', 'F1']

# URLs
CLOUD_RUN_URL = "https://run-density-ln4r3sfkha-uc.a.run.app"
LOCAL_RUN_URL = "http://localhost:8080"
```

**NEVER hardcode these values** - always import from constants.

### Configuration Files

#### `config/density_rulebook.yml`
**Purpose**: LOS thresholds, segment schemas, flow capacity

```yaml
schemas:
  start_corral:
    los_thresholds:
      A: {min: 0.0, max: 0.5}
      B: {min: 0.5, max: 1.0}
      # ... more levels
    flow_ref:
      warn: 300
      critical: 400
```

#### `config/reporting.yml`
**Purpose**: Report generation configuration

```yaml
reporting:
  los_high_threshold: "C"
  utilization_percentile: 95
  severity_rules:
    CRITICAL: ["LOS_HIGH", "UTILIZATION_HIGH"]
    CAUTION: ["LOS_HIGH"]
    WATCH: ["UTILIZATION_HIGH"]
```

## Frontend Architecture

### Pages
- **index.html**: Dashboard with KPIs and operational intelligence widget
- **map.html**: Interactive Leaflet map with LOS color-coding
- **reports.html**: Report downloads and metadata
- **health.html**: System health monitoring

### Data Flow
```
Backend APIs
  ↓
/api/segments (with OI fields)
/api/tooltips (flagged bins)
/api/summary (dashboard KPIs)
  ↓
Frontend JavaScript
  ↓
User Interface
```

### Map Integration
- Load tooltips.json for operational intelligence
- Apply LOS-based color-coding (Green A-B, Amber C-D, Red E-F)
- Display severity badges in tooltips (🚨 CRITICAL, ⚡ CAUTION, 👁️ WATCH)
- Interactive legend with LOS levels

## Performance Optimizations

### Vectorization (Issue #239)
**Pattern**: Replace nested loops with pandas/numpy operations

```python
# BAD: Nested loops
for runner in runners:
    for window in windows:
        if is_in_window(runner, window):
            # process

# GOOD: Vectorized
runner_starts = runners['runner_start_time'].values
time_at_seg_start = runner_starts + pace_sec_per_km * from_km
in_window_mask = (time_at_seg_start <= t_mid + 30) & (time_at_seg_end >= t_mid - 30)
valid_runners = runners[in_window_mask]
```

### Coarsening
When performance budget exceeded:
1. **Temporal-first**: Increase window size (60s → 120s)
2. **Spatial (if needed)**: Increase bin size (0.1km → 0.2km)
3. **Hotspot preservation**: Keep A1, F1 at original resolution
4. **Re-mapping**: Aggregate runners to new indices

## Critical Bugs Resolved

### Issue #243: 10K Runners Missing at Start Time
**Problem**: 10K runners appeared ~50 mins late (08:12 instead of 07:20)

**Root Cause:**
1. Window-first loop caused incorrect event indexing
2. Coarsening broke index mapping

**Solution:**
1. Event-first loop with correct start_idx calculation
2. Runner re-mapping during coarsening

**Verification**: `python tests/qa_regression_baseline.py`

### Issue #239: Implausibly Low Density Values
**Problem**: Density values 0.001-0.004 p/m² (1000× too low)

**Root Cause**: Placeholder `random.randint(0, 5)` instead of actual runner mapping

**Solution**: Implemented vectorized runner-to-bin mapping

## Development Principles

### 1. No Hardcoded Values
**Always use:**
- `app/constants.py` for application values
- `config/density_rulebook.yml` for LOS/flow thresholds  
- `config/reporting.yml` for report configuration

**Never hardcode** start times, thresholds, conflict lengths, tolerance values.

### 2. Permanent Code Only
- Modify existing modules, don't create temporary scripts
- If functionality will be reused, it belongs in permanent modules
- Clean up any temporary files at end of task

### 3. Correct Variable Names
See `@VARIABLE_NAMING_REFERENCE.md` for authoritative mappings:
- ✅ `seg_label` not `segment_label`
- ✅ `from_km` not `10K_from_km`
- ✅ `rate` not `flow` (for bin throughput)

### 4. Test Through APIs
- Always test via `/api/*` endpoints
- Never call analysis functions directly
- Use `e2e.py` for all testing
- Never manually construct curl commands

## CSV Export Standards

All CSV exports use **4 decimal places** for numeric values.

**Utility**: `app/csv_export_utils.py`
```bash
python app/csv_export_utils.py reports/2025-10-15
```

**Formatted Columns:**
- `density`: 4 decimals (e.g., 0.7490)
- `rate`: 4 decimals (e.g., 5.5284)
- `start_km`, `end_km`: 4 decimals (e.g., 0.8000)

See `docs/CSV_EXPORT_STANDARDS.md` for details.

## Related Documentation

### Essential Reading
- `@GUARDRAILS.md` - This file (AI development rules)
- `@OPERATIONS.md` - Deployment, monitoring, versioning
- `@VARIABLE_NAMING_REFERENCE.md` - Authoritative field names
- `@REFERENCE.md` - Quick lookups (schemas, terminology, standards)

### Specialized Topics
- `TEST_FRAMEWORK.md` - Comprehensive testing guide
- `GLOBAL_TIME_GRID_ARCHITECTURE.md` - Time window design (Issue #243)
- `FLOW_VS_RATE_TERMINOLOGY.md` - Flow vs rate distinction
- `CSV_EXPORT_STANDARDS.md` - Export formatting
- `DENSITY_ANALYSIS_README.md` - Density module deep-dive
- `MAP.md` - Frontend map integration

### User Documentation
- `docs/user-guide/` - 10 files for end users

---

**This architecture represents the current state of the system.** Update this document when:
- New modules are added
- Core concepts evolve
- Critical bugs are resolved
- Performance patterns change
- Directory structure is modified

