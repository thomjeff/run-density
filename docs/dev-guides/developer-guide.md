# Developer Guide - Runflow v2

**Version:** v2.0.2+  
**Last Updated:** 2025-12-25  
**Audience:** Developers and architects working in the codebase

---

## Overview

This guide provides essential information for developers working on the Runflow v2 codebase, including development environment setup, data sources, testing, and architecture.

---

## Development Environment

### Docker-Based Development (Recommended)

**Quick Start:**
```bash
make dev      # Start development container
make test     # Run smoke tests
make e2e      # Run E2E tests
make stop     # Stop container
```

**See:** `docs/dev-guides/docker-dev.md` for complete Docker workflow guide.

### Key Commands

| Command | Purpose |
|---------|---------|
| `make dev` | Start container with hot-reload |
| `make test` | Quick smoke tests (< 5 seconds) |
| `make e2e` | Full E2E test suite |
| `make stop` | Stop and remove container |

### Container Structure

```
/app                    # Application root (inside container)
  /app/                # Application code (mounted from ./app)
  /data/               # Input files (mounted from ./data)
  /config/              # Configuration files (mounted from ./config)
  /runflow/             # Output directory (mounted from ./runflow)
```

**Hot Reload:** Changes to files in `./app` automatically trigger server restart.

---

## Frontend Architecture

**Current Stack:** Flask + Jinja2 + Vanilla JavaScript + Leaflet

The application uses server-side rendering with Jinja2 templates and vanilla JavaScript for the web UI.

### Stack Components

- **Templates:** Jinja2 templates in `frontend/templates/pages/`
- **JavaScript:** Vanilla JavaScript in `frontend/static/js/`
- **Mapping:** Leaflet (via CDN: `https://unpkg.com/leaflet@1.9.4/`)
- **Styling:** Tailwind CSS
- **No Build Tooling:** No webpack, vite, or npm dependencies

### Implementation Guidelines

**✅ DO:**
- Use Jinja2 templates in `frontend/templates/pages/`
- Write vanilla JavaScript in `frontend/static/js/`
- Use Leaflet for mapping (not react-leaflet)
- Fetch data via FastAPI endpoints (`/api/*`)
- Extract shared JS to reusable modules (e.g., `base_map.js`)

**❌ DON'T:**
- Add React, Vue, Svelte, or any SPA framework
- Create `package.json` or install Node dependencies
- Reference TypeScript (.tsx) files
- Use build tools (webpack, vite, rollup)
- Suggest `pnpm dev` or `npm start` commands

### Code Organization

```
frontend/
  templates/
    pages/
      segments.html       # Jinja2 template
      density.html
      ...
  static/
    js/
      map/
        base_map.js       # Shared Leaflet initialization
        segments.js       # Segments-specific logic
        heatmap.js        # Density heatmap logic
    css/
      main.css
```

**Rationale:**
- Server-side rendering keeps cold-start times minimal (<2s)
- No client-side build artifacts to serve
- Simpler deployment pipeline (single Docker image)
- Consistent with existing pages (dashboard, density, flow, health, reports)

---

## Architecture Overview

### v2 Architecture Principles

**Issue #553 Core Principles:**
1. **No Hardcoded Values** - All configuration comes from API request
2. **analysis.json as Single Source of Truth** - Generated from request, used throughout pipeline
3. **Fail-Fast Validation** - Clear errors, no silent fallbacks
4. **Dynamic Event Discovery** - Event names discovered from data, not hardcoded lists

### Global Time Grid Architecture

**Critical Design Principle:** All events share a single global clock-time grid, anchored to the earliest event start time. This enables:
- Cross-event comparisons on the same time axis
- Accurate temporal flow analysis (co-presence, overtaking)
- Unified timeline visualizations

**Implementation:**
- Global time windows created from earliest event start
- Each event maps to its appropriate starting index in the global grid
- Runner times anchored to their event's start time (not global start)
- Coarsening requires re-mapping runners to new window indices

**Key Points:**
- Events don't all start at the same time, but share the same time axis
- Window indices are calculated per-event based on start time offset
- Coarsening (60s → 120s) requires aggregating runners from multiple old windows into new windows

**Historical Context:** Issue #243 fixed incorrect window index mapping that caused events to appear at wrong times. The fix ensures events appear at their correct clock times in the global grid.

### Key Components

**API Layer:**
- `app/routes/v2/analyze.py` - Main v2 analysis endpoint
- `app/api/models/v2.py` - Pydantic request/response models
- `app/core/v2/validation.py` - Comprehensive validation layer

**Configuration:**
- `app/core/v2/analysis_config.py` - `analysis.json` generation and helpers
- `analysis.json` - Single source of truth for runtime configuration

**Core Pipeline:**
- `app/core/v2/pipeline.py` - Main analysis pipeline
- `app/core/v2/density.py` - Density analysis
- `app/core/v2/flow.py` - Flow analysis (fail-fast, no fallbacks)
- `app/core/v2/reports.py` - Report generation
- `app/core/v2/bins.py` - Bin generation

**Utilities:**
- `app/utils/constants.py` - Application constants (deprecated constants removed)
- `app/utils/metadata.py` - Metadata generation
- `app/io/loader.py` - Dynamic file loading

---

## Data Sources and Naming Conventions

### Data Directory

**Location:** `/data` (or `DATA_ROOT` environment variable)

**Files:**
- `segments.csv` - Course segment definitions
- `flow.csv` - Event pair definitions and flow metadata
- `locations.csv` - Checkpoint and aid station locations
- `{event}_runners.csv` - Runner data per event (e.g., `elite_runners.csv`)
- `{event}.gpx` - GPX course files per event (e.g., `elite.gpx`)

### Event Names

**Convention:** All event names must be **lowercase**

**Valid Examples:**
- `full`, `half`, `10k`, `elite`, `open`

**File Naming:**
- Runners: `{event}_runners.csv` (e.g., `elite_runners.csv`)
- GPX: `{event}.gpx` (e.g., `elite.gpx`)

**Column Naming in segments.csv:**
- `{event}_from_km`, `{event}_to_km`, `{event}_length` (e.g., `elite_from_km`)

### Dynamic Event Discovery

**Issue #553:** Event columns are discovered dynamically from `segments.csv`, not hardcoded.

**Implementation:**
```python
# app/io/loader.py
def load_segments(segments_file: str, data_dir: str = "data") -> pd.DataFrame:
    # Dynamically discovers event columns
    # No hardcoded event name lists
```

**Benefits:**
- New events can be added without code changes
- Supports any event name (not limited to predefined list)
- Reduces maintenance burden

---

## analysis.json - Single Source of Truth

### Structure

`analysis.json` is generated at the start of each analysis run and serves as the single source of truth for all configuration.

**Location:** `runflow/{run_id}/analysis.json`

**Structure:**
```json
{
  "description": "Optional description",
  "data_dir": "data",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "runners": 2487,
  "events": [
    {
      "name": "elite",
      "day": "sat",
      "start_time": 480,
      "event_duration_minutes": 45,
      "runners_file": "elite_runners.csv",
      "gpx_file": "elite.gpx",
      "runners": 39
    }
  ],
  "event_days": ["sat", "sun"],
  "event_names": ["elite", "open", "full", "10k", "half"],
  "start_times": {
    "elite": 480,
    "open": 510,
    "full": 420,
    "10k": 440,
    "half": 460
  },
  "data_files": {
    "segments": "data/segments.csv",
    "flow": "data/flow.csv",
    "locations": "data/locations.csv",
    "runners": {
      "elite": "data/elite_runners.csv"
    },
    "gpx": {
      "elite": "data/elite.gpx"
    }
  }
}
```

**Required fields (fail-fast):**
- `data_dir`, `segments_file`, `flow_file`, `data_files`, `events` must be present in `analysis.json`.
- `data_files` must include `segments`, `flow`, `locations`, plus `runners` and `gpx` entries for every event.
- Each `events[*]` entry must include `name`, `day`, `start_time`, `event_duration_minutes`, `runners_file`, and `gpx_file`.

Missing or invalid fields cause the analysis config loader (`app/config/loader.py`) to fail fast before the pipeline runs.

### Helper Functions

**Accessing analysis.json:**
```python
from app.core.v2.analysis_config import (
    load_analysis_json,
    get_event_names,
    get_start_time,
    get_flow_file,
    get_segments_file,
    get_runners_file
)

# Load full config
analysis_config = load_analysis_json(run_path)

# Get specific values
event_names = get_event_names(run_path)
start_time = get_start_time("elite", analysis_config)
flow_file = get_flow_file(analysis_config=analysis_config)
```

---

## Testing

**See:** `docs/testing/testing-guide.md` for comprehensive testing documentation.

### Quick Reference

**E2E Tests:**
```bash
make e2e          # Run sat+sun E2E test
make e2e-full     # Run all E2E test scenarios
pytest tests/v2/e2e.py -v
```

**Unit Tests:**
```bash
pytest tests/v2/ -v
pytest tests/v2/test_validation.py -v
```

**Test Organization:**
- `tests/v2/e2e.py` - End-to-end tests
- `tests/v2/test_*.py` - Unit and integration tests
- `tests/v2/golden/` - Golden file baselines for regression

**Related Documentation:**
- **Testing Guide:** `docs/testing/testing-guide.md` - Complete testing documentation
- **UI Testing:** `docs/testing/ui-testing-checklist.md` - Manual UI testing procedures

---

## Code Patterns

### No Hardcoded Values

**❌ WRONG:**
```python
events = ['full', 'half', '10k']  # Hardcoded list
start_time = 420  # Hardcoded start time
flow_file = 'data/flow.csv'  # Hardcoded path
```

**✅ CORRECT:**
```python
# Get from analysis.json
analysis_config = load_analysis_json(run_path)
event_names = get_event_names(run_path)
start_time = get_start_time('full', analysis_config)
flow_file = get_flow_file(analysis_config=analysis_config)
```

### Dynamic Event Discovery

**❌ WRONG:**
```python
if event in ['full', 'half', '10k']:  # Hardcoded list
    # process event
```

**✅ CORRECT:**
```python
# Discover events dynamically from segments.csv
segments_df = load_segments(segments_file, data_dir)
event_columns = [col for col in segments_df.columns if col.endswith('_from_km')]
event_names = [col.replace('_from_km', '') for col in event_columns]

if event in event_names:  # Dynamic check
    # process event
```

### Fail-Fast Validation

**❌ WRONG:**
```python
# Silent fallback
if not flow_file.exists():
    flow_file = 'data/default_flow.csv'  # Silent fallback
```

**✅ CORRECT:**
```python
# Fail-fast with clear error
if not flow_file.exists():
    raise FileNotFoundError(
        f"flow.csv file not found at {flow_file}. "
        "flow.csv is required for flow analysis. "
        "No fallback is allowed per Issue #553."
    )
```

---

## Removed Constants

The following constants have been **removed** (Issue #553):

- `EVENT_DAYS`
- `SATURDAY_EVENTS`
- `SUNDAY_EVENTS`
- `ALL_EVENTS`
- `EVENT_DURATION_MINUTES` (deprecated, kept for v1 API only)
- `DEFAULT_PACE_CSV`
- `DEFAULT_SEGMENTS_CSV`
- `DEFAULT_START_TIMES` (already removed in Issue #512)

**Replacement:** All values now come from API request → `analysis.json` → helper functions.

---

## Flow Analysis - No Fallbacks

**Critical:** Flow analysis uses **fail-fast behavior only** (Issue #553).

**No Fallback Logic:**
- ❌ No auto-generation of event pairs
- ❌ No fallback to start-time ordering
- ❌ No silent recovery

**Required Behavior:**
- ✅ `flow.csv` must exist
- ✅ `flow.csv` must contain pairs for all requested events
- ✅ Same-event pairs must be defined (e.g., `elite-elite`, `open-open`)
- ✅ Request fails immediately with clear error if requirements not met

**Implementation:**
```python
# app/core/v2/flow.py
def analyze_temporal_flow_segments_v2(...):
    # Load flow.csv - fail if missing
    if not flow_path.exists():
        raise FileNotFoundError("flow.csv file not found...")
    
    # Extract pairs - fail if none found
    flow_csv_pairs = extract_event_pairs_from_flow_csv(flow_df, events)
    if not flow_csv_pairs:
        raise ValueError("No valid event pairs found...")
    
    # Validate all events have pairs - fail if missing
    missing_events = requested_event_names - flow_csv_event_names
    if missing_events:
        raise ValueError(f"Requested events {missing_events} have no pairs...")
```

---

## Output Structure

### Day-Partitioned Outputs

**Structure:**
```
runflow/
├── latest.json              # Pointer to most recent run_id
├── index.json               # History of all runs
└── {run_id}/                # UUID-based run directory
    ├── analysis.json        # Configuration (single source of truth)
    ├── metadata.json        # Run-level metadata
    ├── sat/                 # Saturday results
    │   ├── metadata.json
    │   ├── reports/
    │   ├── bins/
    │   └── ui/
    └── sun/                 # Sunday results
        ├── metadata.json
        ├── reports/
        ├── bins/
        └── ui/
```

**Key Points:**
- Each day has its own directory
- Reports are day-scoped (no cross-day contamination)
- `metadata.json` exists at both run-level and day-level
- `analysis.json` is the single source of truth for configuration

**See:** `docs/user-guide/api-user-guide.md` (Understanding Results section) for complete output structure details.

---

## Import Patterns

### Required Pattern (v2.0.2+)

**All imports MUST use absolute paths with `app.` prefix:**

```python
# ✅ CORRECT
from app.core.v2.flow import analyze_temporal_flow_segments_v2
from app.core.v2.analysis_config import load_analysis_json
from app.utils.constants import DEFAULT_STEP_KM
```

**❌ FORBIDDEN:**
```python
# Relative imports
from .flow import analyze_temporal_flow_segments_v2
from ..core.v2 import flow

# Try/except fallbacks
try:
    from .module import function
except ImportError:
    from module import function
```

---

## Common Development Tasks

### Adding a New Event

**No code changes required!** Just:
1. Add event to API request
2. Ensure `segments.csv` has columns: `{event}_from_km`, `{event}_to_km`, `{event}_length`
3. Ensure `flow.csv` contains pairs for new event (including same-event pair)
4. Add `{event}_runners.csv` and `{event}.gpx` files

### Changing Start Times

**No code changes required!** Just update `start_time` in API request.

### Adding Validation Rule

**Location:** `app/core/v2/validation.py`

```python
def validate_new_rule(payload: Dict[str, Any]) -> None:
    """Validate new rule."""
    if not payload.get('new_field'):
        raise ValidationError(
            code=422,
            message="Field required: new_field"
        )
```

Add to `validate_api_payload()` function.

---

## Logging Standards

### Logging Patterns (Mandatory)

**Success Messages (stdout via logger.info):**
```python
logger.info("✅ Density Report completed — Output: runflow/{run_id}/sat/reports/Density.md")
logger.info("✅ Heatmaps generated — Count: 17 PNG files — Location: runflow/{run_id}/sat/ui/heatmaps/")
logger.info("✅ UI Artifacts exported — Location: runflow/{run_id}/sat/ui/")
```

**Error Messages (stderr via logger.error):**
```python
logger.error("❌ Density Report FAILED — Error: data/runners.csv not found — Run: {run_id}")
logger.error("❌ Schema Validation FAILED — Error: segment_metrics.json missing 'segments' field — Run: {run_id}")
```

**Warning Messages (stdout via logger.warning):**
```python
logger.warning("⚠️ Optional file missing — File: runflow/{run_id}/maps/map_data.json")
logger.warning("⚠️ Required file missing — File: bins/bin_summary.json — Status: PARTIAL")
```

### Logger Configuration

```python
import logging
import sys

# Configure root logger
logging.basicConfig(
    format='%(levelname)s:%(name)s:%(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)  # INFO, WARNING
    ]
)

# Add stderr handler for errors
error_handler = logging.StreamHandler(sys.stderr)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('[ERROR] %(name)s: %(message)s'))
logging.getLogger().addHandler(error_handler)
```

**Result:**
- ✅ All `logger.error(...)` → stderr with `[ERROR]` prefix
- ✅ All `logger.info(...)` → stdout
- ✅ All `logger.warning(...)` → stdout with `WARNING:` prefix

### Benefits

1. **Observability** - Clear success/failure in logs
2. **Debuggability** - Errors include context (run_id, file, stage)
3. **Automation** - Structured format easy to parse
4. **Ops-Friendly** - stderr routing for monitoring tools

**Strategy:** All new code must follow these patterns. Existing code updated opportunistically during maintenance.

---

## Debugging

### Check analysis.json

```bash
# View analysis.json for latest run
cat runflow/$(cat runflow/latest.json | jq -r '.run_id')/analysis.json | jq
```

### Check Logs

```bash
# View container logs
docker logs run-density-dev --tail 100

# Filter for errors
docker logs run-density-dev | grep -i "error\|exception"
```

### Verify File Paths

```python
from app.core.v2.analysis_config import get_flow_file, get_segments_file
from pathlib import Path

run_path = Path('runflow/{run_id}')
analysis_config = load_analysis_json(run_path)

flow_file = get_flow_file(analysis_config=analysis_config)
print(f"Flow file: {flow_file}")
print(f"Exists: {Path(flow_file).exists()}")
```

---

## Reference Documentation

- **API User Guide:** `docs/user-guide/api-user-guide.md`
- **Output Structure:** `docs/user-guide/api-user-guide.md` (Understanding Results section)
- **Data Sources:** `docs/dev-guides/CANONICAL_DATA_SOURCES.md`
- **Quick Reference:** `docs/reference/QUICK_REFERENCE.md`
- **AI Developer Guide:** `docs/dev-guides/ai-developer-guide.md`
- **Docker Dev:** `docs/dev-guides/docker-dev.md`

---

**Version:** v2.0.2+  
**Last Updated:** 2025-12-25  
**Issue:** #553
