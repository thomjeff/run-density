# Output Directory Structure

**Version:** 2.0  
**Last Updated:** 2025-12-09
**Issue:** #N/A

This document describes the output directory structure for Runflow v2, which introduces **day-aware output partitioning** to support multi-day, multi-event analysis.

All outputs are organized under a unique `run_id` (UUID) and further partitioned by event `day` (e.g., `sat`, `sun`).

---

## Overview

All run outputs are organized under a single `runflow/` directory with UUID-based subdirectories for each analysis run. This structure provides:

- **Single Source of Truth:** All outputs in one location
- **Run Isolation:** Each run has its own UUID-based directory
- **Easy Tracking:** Pointer files (`latest.json`, `index.json`) for run discovery
- **Clean Architecture:** No date-based directories or scattered files

---

### Per-Run Directory

Each run is stored in `runflow/{run_id}/` where `run_id` is a short UUID generated using `shortuuid.uuid()`.

**UUID Characteristics:**
- **Format:** 22-character alphanumeric string
- **Example:** `kPJMRTxUE3rHPPcTbvWBYV`
- **Collision Probability:** Negligible for practical use cases
- **Sortability:** Not chronologically sortable (use `created_at` from metadata)

---

## Top-Level Structure

```
runflow/
├── latest.json                  # Pointer to most recent run_id
├── index.json                   # History of all runs (metadata summary)
└── {run_id}/                    # UUID-based run directory (e.g., kPJMRTxUE3rHPPcTbvWBYV)
    ├── {day}/                   # Day of event (e.g., sat, sun)
        ├── metadata.json        # Complete run metadata
        ├── reports/             # Human-readable reports
        │   ├── Density.md       # Density analysis (Markdown)
        │   ├── Flow.md          # Flow analysis (Markdown)
        │   └── Flow.csv         # Flow data (CSV)
        ├── bins/                # Bin-level analysis data
        │   ├── bins.parquet     # Binary dataset (columnar format)
        │   ├── bins.geojson.gz  # Compressed geospatial bins
        │   └── bin_summary.json # Summary statistics
        ├── maps/                # Map data (optional, if enabled)
        │   └── map_data.json
        └── ui/                  # Frontend artifacts
            ├── meta.json
            ├── segment_metrics.json
            ├── flags.json
            ├── flow.json
            ├── segments.geojson
            ├── schema_density.json
            ├── health.json
            ├── captions.json
            └── heatmaps/
                ├── A1.png
                ├── A2.png
                ├── ...
                └── M1.png (17 total)
```

## Notes

- Each `{day}/` folder is completely self-contained and can be analyzed independently.
- Bins, flows, and maps are **scoped to a single day** and include only the relevant events and segments.
- Filenames and structure are consistent across all days for programmatic access.

## File Descriptions

### Root Level Files

#### `latest.json`
Pointer file containing the UUID of the most recent analysis run containing one or more days, based on the input provided by the user via the API.

**Purpose:**  
- Allows APIs to quickly find the latest run without scanning directories
- Updated atomically after each successful run

**Format:**
```json
{
  "run_id": "kPJMRTxUE3rHPPcTbvWBYV"
}
```

**Usage:**
```bash
# Get latest run ID
cat runflow/latest.json | jq -r '.run_id'

# Navigate to latest run
cd runflow/$(cat runflow/latest.json | jq -r '.run_id')
```

---

#### `index.json`
Historical index of all analysis runs with summary metadata. Note that each run will have one or more days and the `file_counts` are per day.

**Purpose:**
- Provides chronological list of all runs
- Enables run discovery and comparison
- Stores lightweight metadata for each run

**Format:**
```json
[
  {
    "run_id": "kPJMRTxUE3rHPPcTbvWBYV",
    "created_at": "2025-11-05T00:06:01.689285Z",
    "runtime_env": "local_docker",
    "storage_target": "filesystem",
    "app_version": "v1.6.50",
    "git_sha": "unknown",
    "status": "complete",
    "days": {
      "sat": {
        "file_counts": {
          "reports": 3,
          "bins": 5,
          "maps": 1,
          "heatmaps": 17,
          "ui": 8
        }
      },
      "sun": {
        "file_counts": {
          "reports": 3,
          "bins": 5,
          "maps": 1,
          "heatmaps": 17,
          "ui": 8
        }
      }
    }
  },
  ...
]
```

**Note:** Runs are stored in chronological order (oldest first). Use `list(reversed(index_data))` to get newest first.

---

### `metadata.json`

Complete metadata for the analysis run. 

**Purpose:**
- Stores comprehensive run information
- Enables reproducibility and debugging
- Tracks environment and configuration

**Format:**
```json
{
  "run_id": "kPJMRTxUE3rHPPcTbvWBYV",
  "created_at": "2025-12-08T14:31:58.048920Z",
  "status": "PASS",
  "runtime_env": "local_docker",
  "storage_target": "filesystem",
  "app_version": "v1.8.5",
  "git_sha": "unknown",
  "days": {
    "sat": {
      "files_created": {
        "reports": [
          "Density.md",
          "Flow.csv",
          "Flow.md",
          "Locations.csv"
        ],
        "bins": [
          "bin_summary.json",
          "bins.geojson.gz",
          "bins.parquet",
          "segment_windows_from_bins.parquet",
          "segments_legacy_vs_canonical.csv"
        ],
        "maps": [
          "map_data.json"
       ],
        "heatmaps": [
          "A1.png",
          "A2.png",
          "M1.png"
        ],
        "ui": [
          "captions.json",
          "flags.json",
          "flow.json",
          "health.json",
          "meta.json",
          "schema_density.json",
          "segment_metrics.json",
          "segments.geojson"
        ]
      },
      "file_counts": {
        "reports": 4,
        "bins": 5,
        "maps": 1,
        "heatmaps": 3,
        "ui": 8
      },
      "output_verification": {
        "status": "PASS",
        "validated_at": "2025-12-08T14:32:05.724209+00:00",
        "validator_version": "1.0.0",
        "missing": [],
        "schema_errors": [],
        "invalid_artifacts": [],
        "checks": {
          "latest_json": {
            "status": "PASS",
            "run_id": "5ud6Xp75CxjTUkPptEjiDy"
          },
          "file_presence": {
            "status": "PASS",
            "missing": [],
            "found_counts": {
              "reports": 4,
              "bins": 3,
              "maps": 1,
              "heatmaps": 3,
              "ui": 8
            },
            "expected_counts": {
              "reports": 4,
              "bins": 3,
              "maps": 1,
              "heatmaps": 3,
              "ui": 8
            }
          },
          "api_consistency": {
            "status": "PASS",
            "apis_checked": 2,
            "errors": [],
            "all_paths_valid": true
          },
          "schema_validation": {
            "status": "PASS",
            "files_checked": 9,
            "errors": []
          }
        }
      }
    }
  "sun": {}
  }  
```

---

### `reports/` Directory

Human-readable analysis reports in Markdown and CSV formats. Note that sizes below are based on sun events = `full`, `half`, `10k`; sat will be smaller.

#### `Density.md`
- **Format:** Markdown
- **Size:** ~109 KB
- **Content:**
  - Executive summary
  - Segment-level density analysis
  - Bin-level details
  - Level of Service (LOS) ratings
  - Operational recommendations

#### `Flow.md`
- **Format:** Markdown
- **Size:** ~32 KB
- **Content:**
  - Flow analysis
  - Overtaking patterns
  - Convergence points
  - Event interactions

#### `Flow.csv`
- **Format:** CSV
- **Size:** ~10 KB
- **Content:** Tabular flow data for analysis tools

---

### `bins/` Directory

Bin-level analysis data for detailed operational intelligence.

#### `bins.parquet`
- **Format:** Apache Parquet (columnar binary)
- **Size:** Variable (~1-5 MB depending on run)
- **Content:** All bin-level density, rate, and LOS calculations
- **Columns:**
  - `seg_id`, `km_start`, `km_end`, `time_start`, `time_end`
  - `density_p_m2`, `rate_per_m_per_min`, `utilization`
  - `los`, `flag`, `participants`

**Usage:**
```python
import pandas as pd
bins = pd.read_parquet('runflow/{run_id}/bins/bins.parquet')
```

#### `bins.geojson.gz`
- **Format:** Compressed GeoJSON
- **Content:** Geospatial representation of bins
- **Use Case:** Mapping and visualization tools

#### `bin_summary.json`
- **Format:** JSON
- **Content:** Aggregate statistics across all bins

---

### `maps/` Directory

Optional map data (generated if map manifest enabled).

#### `map_data.json`
- **Format:** JSON
- **Content:** Interactive map configuration and data
- **Status:** Optional feature (may not be present in all runs)

---

### `ui/` Directory

Frontend artifacts used by the web dashboard.

#### Core Artifacts

| File | Purpose | Size |
|------|---------|------|
| `meta.json` | Run metadata summary | ~0.5 KB |
| `segment_metrics.json` | Segment-level metrics | ~5 KB |
| `flags.json` | Flagged segments and bins | ~3 KB |
| `flow.json` | Flow analysis data | ~150 KB |
| `segments.geojson` | Segment geometries | ~15 KB |
| `schema_density.json` | Density schema version | ~0.3 KB |
| `health.json` | System health status | ~0.5 KB |
| `captions.json` | Heatmap captions | ~10 KB |

---

#### `heatmaps/` Directory

PNG heatmap images for each flagged segment.

**Naming Convention:** `{seg_id}.png` (e.g., `A1.png`, `B1.png`)

**Characteristics:**
- **Format:** PNG (RGB)
- **Resolution:** Variable (based on bins and time windows)
- **Count:** 17 images (for flagged segments)
- **Total Size:** ~1.9 MB

**Example Files:**
- `A1.png` - Start to Queen/Regent
- `A2.png` - Queen/Regent to WSB mid-point
- `B1.png` - Friel to 10K Turn
- `F1.png` - Friel to Station Rd.
- `M1.png` - Trail/Aberdeen to Finish

---

## API Usage

### Getting Latest Run ID

```python
from app.utils.run_id import get_latest_run_id

run_id = get_latest_run_id()
# Returns: "kPJMRTxUE3rHPPcTbvWBYV"
```

### Accessing Run Directory

```python
from app.utils.run_id import get_run_directory

run_dir = get_run_directory(run_id)
# Returns: Path("/app/runflow/kPJMRTxUE3rHPPcTbvWBYV")
```

### Loading Run Metadata

```python
from app.storage import create_storage_from_env

storage = create_storage_from_env()
metadata = storage.read_json(f"runflow/{run_id}/metadata.json")
```

---

## API Endpoints

### Frontend APIs (use latest run)

All frontend APIs automatically use the latest run from `runflow/latest.json`. You may optionally include a day (e.g., sat, sun) to restrict results.

`GET /api/dashboard/summary` - Returns key metrics used in the UI dashboard (event counts, density alerts, flags, etc.).
`GET /api/density/segments` - Returns bin-level and summary density metrics per segment.
`GET /api/flow/segments` - Returns co-presence and overtake statistics between event pairs.
`GET /api/reports/list` - Returns the list of available reports for the run.

Optional Query Param:
    •   ?day=sun

### Reports API (specific run)
```bash
# Get list of reports from a specific run and day
curl http://localhost:8080/api/reports/list?run_id=kPJMRTxUE3rHPPcTbvWBYV&day=sat
```

Sample Response:
```json
[
  {
    "name": "Density.md",
    "path": "runflow/kPJMRTxUE3rHPPcTbvWBYV/sat/reports/Density.md",
    "mtime": 1731281799.0,
    "size": 111518
  },
  {
    "name": "Flow.md",
    "path": "runflow/kPJMRTxUE3rHPPcTbvWBYV/sat/reports/Flow.md",
    "mtime": 1731281799.0,
    "size": 49123
  }
]
```

---

## Troubleshooting

### "run_id not found" errors

**Cause:** `latest.json` is missing or corrupted

**Solution:**
```bash
# Check if latest.json exists
cat runflow/latest.json

# If missing, find most recent run directory
ls -lt runflow/ | head -5

# Manually create latest.json
echo '{"run_id": "YOUR_RUN_ID_HERE"}' > runflow/latest.json
```

### UI shows old data

**Cause:** APIs not reading from correct run_id

**Solution:**
```bash
# Verify latest.json points to correct run
cat runflow/latest.json

# Check if that run directory exists
ls -la runflow/$(cat runflow/latest.json | jq -r '.run_id')/

# Restart container to force reload
make stop && make dev
```

### Heatmaps not loading

**Cause:** Heatmaps not in correct location

**Solution:**
```bash
# Check heatmap location
run_id=$(cat runflow/latest.json | jq -r '.run_id')
ls -la runflow/$run_id/ui/heatmaps/

# Should show 17 PNG files (A1.png, A2.png, etc.)
```

---

## Implementation Details

### Run ID Generation

**Module:** `app/utils/run_id.py`

```python
import shortuuid

def generate_run_id() -> str:
    """Generate a short, unique run ID."""
    return shortuuid.uuid()  # 22 chars, alphanumeric
```

### Pointer File Updates

**Module:** `app/utils/metadata.py`

```python
def update_latest_pointer(run_id: str) -> None:
    """
    Update runflow/latest.json atomically.
    Uses temp file → rename for atomic write.
    """
    # Atomic write implementation...
```

---

## Related Documentation

- **Docker Development:** `docs/DOCKER_DEV.md`
- **Environment Detection:** `docs/architecture/env-detection.md`
- **Run ID Module:** `app/utils/run_id.py`
- **Storage Module:** `app/storage.py`


