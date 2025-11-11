# Output Structure Documentation

**Version:** 1.0  
**Last Updated:** 2025-11-11  
**Issue:** #466 (Phase 2 Architecture Refinement)

This document describes the unified output structure for the run-density application after Phase 2 architecture refinement.

---

## Overview

All run outputs are organized under a single `runflow/` directory with UUID-based subdirectories for each analysis run. This structure provides:

- **Single Source of Truth:** All outputs in one location
- **Run Isolation:** Each run has its own UUID-based directory
- **Easy Tracking:** Pointer files (`latest.json`, `index.json`) for run discovery
- **Clean Architecture:** No date-based directories or scattered files

---

## Directory Structure

```
runflow/
├── latest.json              # Pointer to most recent run_id
├── index.json               # History of all runs (metadata summary)
└── {run_id}/                # UUID-based run directory (e.g., kPJMRTxUE3rHPPcTbvWBYV)
    ├── metadata.json        # Complete run metadata
    ├── reports/             # Human-readable reports
    │   ├── Density.md       # Density analysis (Markdown)
    │   ├── Flow.md          # Temporal flow analysis (Markdown)
    │   └── Flow.csv         # Temporal flow data (CSV)
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

---

## File Descriptions

### Root Level Files

#### `latest.json`
Pointer file containing the UUID of the most recent analysis run.

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
Historical index of all analysis runs with summary metadata.

**Purpose:**
- Provides chronological list of all runs
- Enables run discovery and comparison
- Stores lightweight metadata for each run

**Format:**
```json
[
  {
    "run_id": "kPJMRTxUE3rHPPcTbvWBYV",
    "created_at": "2025-11-11T01:19:36Z",
    "runtime_env": "local_docker",
    "storage_target": "filesystem",
    "app_version": "v1.8.3",
    "git_sha": "77f07bb",
    "file_counts": {
      "reports": 3,
      "ui_artifacts": 8,
      "heatmaps": 17
    },
    "status": "complete"
  },
  ...
]
```

**Note:** Runs are stored in chronological order (oldest first). Use `list(reversed(index_data))` to get newest first.

---

### Per-Run Directory

Each run is stored in `runflow/{run_id}/` where `run_id` is a short UUID generated using `shortuuid.uuid()`.

**UUID Characteristics:**
- **Format:** 22-character alphanumeric string
- **Example:** `kPJMRTxUE3rHPPcTbvWBYV`
- **Collision Probability:** Negligible for practical use cases
- **Sortability:** Not chronologically sortable (use `created_at` from metadata)

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
  "created_at": "2025-11-11T01:19:36Z",
  "runtime_env": "local_docker",
  "storage_target": "filesystem",
  "app_version": "v1.8.3",
  "git_sha": "77f07bb",
  "config": {
    "enable_bin_dataset": true,
    "bin_size_km": 0.2,
    "bin_dt_s": 120
  },
  "file_counts": {
    "reports": 3,
    "ui_artifacts": 8,
    "heatmaps": 17,
    "bins": 19440
  },
  "status": "complete"
}
```

---

### `reports/` Directory

Human-readable analysis reports in Markdown and CSV formats.

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
  - Temporal flow analysis
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

All frontend APIs automatically use the latest run from `runflow/latest.json`:

- `GET /api/dashboard/summary` - Dashboard metrics
- `GET /api/density/segments` - Density analysis
- `GET /api/flow/segments` - Flow analysis
- `GET /api/reports/list` - Available reports

### Reports API (specific run)

```bash
# Get reports from latest run
curl http://localhost:8080/api/reports/list

# Response includes paths with run_id:
{
  "name": "Density.md",
  "path": "runflow/kPJMRTxUE3rHPPcTbvWBYV/reports/Density.md",
  "mtime": 1731281799.0,
  "size": 111518
}
```

---

## Migration Notes

### Phase 1 → Phase 2 Changes

**Before (Phase 1):**
```
├── artifacts/{run_id}/ui/
├── reports/{date}/
└── runflow/{run_id}/
```

**After (Phase 2):**
```
└── runflow/{run_id}/
    ├── reports/
    └── ui/
```

**Key Changes:**
1. **Consolidated:** Everything under `runflow/{run_id}/`
2. **No Date Directories:** UUID-based organization only
3. **Single `latest.json`:** Unified pointer file at `runflow/latest.json`

---

## Best Practices

### For Developers

1. **Always use `get_latest_run_id()`** instead of scanning directories
2. **Use `get_run_directory()`** to construct paths programmatically
3. **Never hardcode run IDs** in application logic
4. **Check `latest.json`** before accessing UI artifacts

### For Operators

1. **Cleanup old runs:** Periodically delete old `runflow/{run_id}/` directories
2. **Monitor disk usage:** Each run generates ~2-5 MB of data
3. **Backup `index.json`:** Preserves run history metadata
4. **Keep `latest.json`:** Required for UI operation

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

---

**Last Updated:** 2025-11-11  
**Updated By:** AI Assistant (Issue #466 - Phase 2 Step 5)  
**Architecture:** Local-only, UUID-based runflow structure

