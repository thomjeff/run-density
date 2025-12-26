# Runflow API User Guide

**Version:** v2.0.2+  
**Last Updated:** 2025-12-25  
**Audience:** Marathon race organizers, operational planners, analysis users

---

## Overview

The Runflow API allows you to analyze race day configurations by submitting event details, start times, and course data. The system generates comprehensive reports on runner density, flow patterns, and operational insights to inform race planning decisions.

**Key Capabilities:**
- Analyze multiple events across multiple days
- Configure all parameters via API request (no hardcoded values)
- Generate density, flow, and location reports
- Compare scenarios by changing event times or dates

---

## Quick Start

### 1. Prepare Your Data Files

Place all required files in the `/data` directory:

**Required Files:**
- `segments.csv` - Course segment definitions
- `flow.csv` - Event pair definitions and flow metadata
- `locations.csv` - Checkpoint and aid station locations
- `{event}_runners.csv` - Runner data for each event (e.g., `full_runners.csv`, `half_runners.csv`)
- `{event}.gpx` - GPX course file for each event (e.g., `full.gpx`, `half.gpx`)

**File Naming:**
- Event names must be lowercase (e.g., `full`, `half`, `10k`, `elite`, `open`)
- Runners files: `{event}_runners.csv` (e.g., `elite_runners.csv`)
- GPX files: `{event}.gpx` (e.g., `elite.gpx`)

### 2. Make an API Request

**Endpoint:** `POST http://localhost:8080/runflow/v2/analyze`

**Example Request:**
```json
{
  "description": "Saturday and Sunday race analysis",
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
    },
    {
      "name": "open",
      "day": "sat",
      "start_time": 510,
      "event_duration_minutes": 75,
      "runners_file": "open_runners.csv",
      "gpx_file": "open.gpx"
    },
    {
      "name": "full",
      "day": "sun",
      "start_time": 420,
      "event_duration_minutes": 390,
      "runners_file": "full_runners.csv",
      "gpx_file": "full.gpx"
    },
    {
      "name": "10k",
      "day": "sun",
      "start_time": 440,
      "event_duration_minutes": 120,
      "runners_file": "10k_runners.csv",
      "gpx_file": "10k.gpx"
    },
    {
      "name": "half",
      "day": "sun",
      "start_time": 460,
      "event_duration_minutes": 180,
      "runners_file": "half_runners.csv",
      "gpx_file": "half.gpx"
    }
  ]
}
```

**Example Response:**
```json
{
  "run_id": "hCjWfQNKMePnRkrN4GX9Rj",
  "status": "success",
  "days": ["sat", "sun"],
  "output_paths": {
    "sat": {
      "day": "sat",
      "reports": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sat/reports",
      "bins": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sat/bins",
      "maps": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sat/maps",
      "ui": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sat/ui",
      "metadata": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sat/metadata.json"
    },
    "sun": {
      "day": "sun",
      "reports": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sun/reports",
      "bins": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sun/bins",
      "maps": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sun/maps",
      "ui": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sun/ui",
      "metadata": "runflow/hCjWfQNKMePnRkrN4GX9Rj/sun/metadata.json"
    }
  }
}
```

### 3. Access Your Results

Results are organized by day under `runflow/{run_id}/{day}/`:

**Reports:**
- `{day}/reports/Density.md` - Density analysis report
- `{day}/reports/Flow.md` - Flow analysis report
- `{day}/reports/Flow.csv` - Flow data (CSV format)
- `{day}/reports/Locations.csv` - Location analysis

**Metadata:**
- `{day}/metadata.json` - Complete analysis metadata including request/response
- `analysis.json` - Configuration used for this analysis (single source of truth)

---

## Request Parameters

### Required Fields

All fields below are **required** (no defaults provided):

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `segments_file` | string | Name of segments CSV file | `"segments.csv"` |
| `flow_file` | string | Name of flow CSV file | `"flow.csv"` |
| `locations_file` | string | Name of locations CSV file | `"locations.csv"` |
| `events` | array | List of events to analyze (min 1) | See below |

### Event Object (Required for Each Event)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Event name (lowercase) | `"full"`, `"half"`, `"10k"`, `"elite"`, `"open"` |
| `day` | string | Day code | `"fri"`, `"sat"`, `"sun"`, `"mon"` |
| `start_time` | integer | Start time in minutes after midnight (300-1200) | `420` (7:00 AM), `480` (8:00 AM) |
| `event_duration_minutes` | integer | Event duration in minutes (1-500) | `390` (6.5 hours), `120` (2 hours) |
| `runners_file` | string | Name of runners CSV file | `"full_runners.csv"` |
| `gpx_file` | string | Name of GPX course file | `"full.gpx"` |

### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `description` | string | Optional description (max 254 chars) | `"Scenario: Moving 10k to Saturday"` |

---

## Understanding Start Times

Start times are specified as **minutes after midnight**:

| Time | Minutes | Example |
|------|---------|---------|
| 5:00 AM | 300 | `"start_time": 300` |
| 7:00 AM | 420 | `"start_time": 420` |
| 8:00 AM | 480 | `"start_time": 480` |
| 8:30 AM | 510 | `"start_time": 510` |
| 9:00 AM | 540 | `"start_time": 540` |
| 10:00 AM | 600 | `"start_time": 600` |

**Valid Range:** 300-1200 (5:00 AM - 8:00 PM)

---

## Understanding Event Names

Event names must be **lowercase** and match your data files:

**Common Event Names:**
- `full` - Full marathon
- `half` - Half marathon
- `10k` - 10K race
- `elite` - Elite 5K
- `open` - Open 5K

**File Naming Convention:**
- Runners file: `{event}_runners.csv` (e.g., `elite_runners.csv`)
- GPX file: `{event}.gpx` (e.g., `elite.gpx`)

**Important:** Event names in your request must match:
- Column names in `segments.csv` (e.g., `elite_from_km`, `elite_to_km`)
- Event names in `flow.csv` (`event_a`, `event_b` columns)
- File names for runners and GPX files

---

## Understanding flow.csv Requirements

**Critical:** `flow.csv` must contain pairs for **all requested events**, including same-event pairs.

**Example for Saturday events (`elite`, `open`):**
```csv
seg_id,event_a,event_b,...
N1,elite,elite,...
N2a,elite,elite,...
O1,open,open,...
O2a,open,open,...
```

**Why Same-Event Pairs?**
- Same-event pairs (e.g., `elite-elite`) analyze overtaking within a single event
- Required for accurate flow analysis
- Must be explicitly defined in `flow.csv`

**If flow.csv is missing pairs:**
- ❌ Request will **fail** with clear error message
- ❌ No automatic generation or fallback
- ✅ Error message indicates which events are missing pairs

---

## Common Use Cases

### Use Case 1: Analyze Current Race Configuration

**Goal:** Analyze the planned race day configuration

```json
{
  "description": "Current race plan - Saturday elite/open, Sunday full/half/10k",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {"name": "elite", "day": "sat", "start_time": 480, "event_duration_minutes": 45, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
    {"name": "open", "day": "sat", "start_time": 510, "event_duration_minutes": 75, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"},
    {"name": "full", "day": "sun", "start_time": 420, "event_duration_minutes": 390, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
    {"name": "10k", "day": "sun", "start_time": 440, "event_duration_minutes": 120, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
    {"name": "half", "day": "sun", "start_time": 460, "event_duration_minutes": 180, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
  ]
}
```

### Use Case 2: Test Scenario - Move 10K to Saturday

**Goal:** Analyze impact of moving 10K from Sunday to Saturday

```json
{
  "description": "Scenario: Move 10k to Saturday to reduce Sunday congestion",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {"name": "elite", "day": "sat", "start_time": 480, "event_duration_minutes": 45, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
    {"name": "open", "day": "sat", "start_time": 510, "event_duration_minutes": 75, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"},
    {"name": "10k", "day": "sat", "start_time": 540, "event_duration_minutes": 120, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
    {"name": "full", "day": "sun", "start_time": 420, "event_duration_minutes": 390, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
    {"name": "half", "day": "sun", "start_time": 460, "event_duration_minutes": 180, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
  ]
}
```

### Use Case 3: Adjust Start Times

**Goal:** Test impact of earlier start times

```json
{
  "description": "Scenario: Start all events 30 minutes earlier",
  "segments_file": "segments.csv",
  "flow_file": "flow.csv",
  "locations_file": "locations.csv",
  "events": [
    {"name": "elite", "day": "sat", "start_time": 450, "event_duration_minutes": 45, "runners_file": "elite_runners.csv", "gpx_file": "elite.gpx"},
    {"name": "open", "day": "sat", "start_time": 480, "event_duration_minutes": 75, "runners_file": "open_runners.csv", "gpx_file": "open.gpx"},
    {"name": "full", "day": "sun", "start_time": 390, "event_duration_minutes": 390, "runners_file": "full_runners.csv", "gpx_file": "full.gpx"},
    {"name": "10k", "day": "sun", "start_time": 410, "event_duration_minutes": 120, "runners_file": "10k_runners.csv", "gpx_file": "10k.gpx"},
    {"name": "half", "day": "sun", "start_time": 430, "event_duration_minutes": 180, "runners_file": "half_runners.csv", "gpx_file": "half.gpx"}
  ]
}
```

---

## Understanding Results

### Output Structure

Results are organized by day under `runflow/{run_id}/`:

```
runflow/
├── latest.json              # Pointer to most recent run_id
├── index.json               # History of all runs (metadata summary)
└── {run_id}/                # UUID-based run directory (e.g., hCjWfQNKMePnRkrN4GX9Rj)
    ├── analysis.json        # Configuration used for this analysis (single source of truth)
    ├── metadata.json        # Run-level metadata
    ├── sat/                  # Saturday results
    │   ├── metadata.json    # Saturday-specific metadata
    │   ├── reports/
    │   │   ├── Density.md    # Density analysis report
    │   │   ├── Flow.md       # Flow analysis report
    │   │   ├── Flow.csv      # Flow data (CSV format)
    │   │   └── Locations.csv # Location analysis
    │   ├── bins/
    │   │   ├── bins.parquet # Bin-level data (columnar format)
    │   │   ├── bins.geojson.gz # Compressed geospatial bins
    │   │   └── bin_summary.json # Summary statistics
    │   └── ui/               # Frontend artifacts
    │       ├── meta.json
    │       ├── segment_metrics.json
    │       ├── flags.json
    │       ├── flow.json
    │       ├── segments.geojson
    │       ├── schema_density.json
    │       ├── health.json
    │       ├── captions.json
    │       └── heatmaps/
    │           └── *.png (17 files)
    └── sun/                  # Sunday results
        ├── metadata.json
        ├── reports/
        ├── bins/
        └── ui/
```

### Key Files

**Root Level:**
- `latest.json` - Pointer to most recent run ID
- `index.json` - Historical index of all runs
- `analysis.json` - Complete configuration used for this analysis (single source of truth)

**Per-Day Reports:**
- `{day}/reports/Density.md` - Density analysis report (Markdown)
- `{day}/reports/Flow.md` - Flow analysis report (Markdown)
- `{day}/reports/Flow.csv` - Flow data (CSV format)
- `{day}/reports/Locations.csv` - Location analysis

**Per-Day Data:**
- `{day}/bins/bins.parquet` - Bin-level analysis data (columnar format)
- `{day}/bins/bins.geojson.gz` - Compressed geospatial bins
- `{day}/bins/bin_summary.json` - Summary statistics

**Per-Day Metadata:**
- `{day}/metadata.json` - Day-specific metadata including request/response payloads

### Key Reports

**Density.md:**
- Segment-by-segment density analysis
- Level of Service (LOS) classifications
- Peak density times and locations
- Operational insights

**Flow.md:**
- Event interaction analysis
- Overtaking patterns
- Convergence points
- Flow type classifications (overtake, co-presence, merge)

**Flow.csv:**
- Detailed flow data in CSV format
- Suitable for spreadsheet analysis
- Includes all segment pairs and metrics

**Locations.csv:**
- Checkpoint and aid station analysis
- Runner arrival patterns
- Location-specific insights

---

## Error Handling

The API uses **fail-fast** validation - all errors are returned immediately with clear messages.

### Common Errors

**400 Bad Request - Missing Required Field**
```json
{
  "status": "ERROR",
  "code": 400,
  "error": "Field required: segments_file"
}
```
**Solution:** Add missing required field to request.

**404 Not Found - File Missing**
```json
{
  "status": "ERROR",
  "code": 404,
  "error": "flow.csv file not found at data/flow.csv. flow.csv is required for flow analysis and must be provided in the request."
}
```
**Solution:** Ensure file exists in `/data` directory with correct name.

**422 Unprocessable Entity - Invalid Event Pairs**
```json
{
  "status": "ERROR",
  "code": 422,
  "error": "Requested events ['elite', 'open'] have no pairs defined in flow.csv. flow.csv contains pairs for: ['full', 'half', '10k']. All requested events must have at least one pair (including same-event pairs) in flow.csv."
}
```
**Solution:** Add required pairs to `flow.csv` (including same-event pairs like `elite-elite`, `open-open`).

**422 Unprocessable Entity - Invalid Start Time**
```json
{
  "status": "ERROR",
  "code": 422,
  "error": "Invalid start_time: 200. Must be between 300 and 1200 (5:00 AM - 8:00 PM)"
}
```
**Solution:** Adjust start time to valid range (300-1200 minutes).

---

## Best Practices

### 1. Use Descriptive Descriptions
```json
{
  "description": "Baseline: Current race configuration",
  ...
}
```

### 2. Verify flow.csv Before Requesting
- Ensure `flow.csv` contains pairs for all requested events
- Include same-event pairs (e.g., `elite-elite`, `open-open`)
- Verify event names match exactly (lowercase)

### 3. Compare Scenarios
- Save `run_id` from each scenario
- Compare results by reviewing `Density.md` and `Flow.md` side-by-side
- Use `metadata.json` to verify configuration differences

### 4. Check Error Messages
- All errors include specific guidance
- Error messages indicate exactly what's missing or invalid
- No silent failures - all issues are reported immediately

---

## API Reference

### Endpoint
```
POST /runflow/v2/analyze
```

### Request Headers
```
Content-Type: application/json
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success - Analysis completed |
| 400 | Bad Request - Missing required field |
| 404 | Not Found - File missing |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error - Processing failed |

### Response Format

**Success:**
```json
{
  "run_id": "string",
  "status": "success",
  "days": ["sat", "sun"],
  "output_paths": {
    "sat": { ... },
    "sun": { ... }
  }
}
```

**Error:**
```json
{
  "status": "ERROR",
  "code": 422,
  "error": "Error message with details"
}
```

---

## Getting Help

**Questions about:**
- **API usage?** → See this guide
- **Data file formats?** → See `docs/user-guide/data-file-formats.md`
- **Understanding results?** → See `docs/user-guide/understanding-results.md`
- **Migration from v1?** → See `docs/migration-guide-issue-553.md`

---

**Version:** v2.0.2+  
**Last Updated:** 2025-12-25  
**Issue:** #553

