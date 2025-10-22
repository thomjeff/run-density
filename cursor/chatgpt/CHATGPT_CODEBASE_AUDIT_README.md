# Codebase Audit Package for ChatGPT

**Date**: 2025-10-21  
**Purpose**: Comprehensive storage system audit for Cloud Run compatibility  
**Context**: Issues #293, #294, #298  

---

## Package Contents

### Core Application
- `app/` - All API routes, services, and core logic
- `analytics/` - Report generation and artifact export modules
- `e2e.py` - End-to-end testing script

### Storage Systems (Current State)
- `app/storage_service.py` - Modern, GCS-aware storage (✅ Working)
- `app/storage.py` - Legacy storage module (⚠️ Partially working)

### Configuration & Data
- `requirements.txt` - Python dependencies
- `requirements-core.txt` - Core dependencies
- `requirements-dev.txt` - Development dependencies
- `Dockerfile` - Container build configuration
- `data/` - Sample data files (runners.csv, segments.csv)
- `config/` - YAML configuration files

### CI/CD
- `.github/workflows/ci-pipeline.yml` - Deployment and testing pipeline

---

## Current Situation Analysis

### Problem: Cloud Run Routes Failing to Load Data

**Root Cause**: Routes are reading `latest.json` from GCS ✅ but then trying to read **other files** from local filesystem ❌

### What's Working ✅

1. **GCS has all files**:
   ```
   gs://run-density-reports/
     ├── artifacts/latest.json ✓
     ├── artifacts/2025-10-21/ui/ (7 files) ✓
     └── 2025-10-21/ (bins.parquet, Flow.csv, etc.) ✓
   ```

2. **StorageService reads latest.json from GCS**:
   ```
   INFO:app.storage_service:Using latest run_id from latest.json: 2025-10-21
   ```

3. **Local environment**: All routes work perfectly

### What's NOT Working ❌

**Cloud Run logs show**:
```
WARNING:app.routes.api_density:bins.parquet not found at reports/2025-10-21/bins.parquet
WARNING:app.routes.api_segments:segments.geojson not found in storage
WARNING:app.routes.api_dashboard:runners.csv not found in storage
```

**User sees**:
- Dashboard: "data not found for runners.csv"
- Segments: Empty table
- Density: Missing utilization, flags, worst bin
- Flow: Empty
- Reports: Empty

### Code Examples of the Problem

**api_density.py (line 50)**:
```python
# ❌ Assumes local filesystem
bins_path = Path(f"reports/{run_id}/bins.parquet")
if not bins_path.exists():
    logger.warning(f"bins.parquet not found at {bins_path}")
    return {}
bins_df = pd.read_parquet(bins_path)  # Fails in Cloud Run
```

**api_flow.py (lines 67-70)**:
```python
# ❌ Assumes local filesystem
reports_dir = Path("reports") / run_id
flow_csv_files = list(reports_dir.glob("*-Flow.csv"))
if not flow_csv_files:
    logger.warning(f"No Flow CSV files found in {reports_dir}")
```

---

## Inventory of Local Filesystem Dependencies

### Routes That Need Migration

| Route | File(s) Being Read | Current Access | Needs |
|-------|-------------------|----------------|-------|
| `api_density.py` | `reports/{run_id}/bins.parquet` | Local Path() | GCS read |
| `api_flow.py` | `reports/{run_id}/*-Flow.csv` | Local Path() | GCS read |
| `api_segments.py` | `artifacts/{run_id}/ui/segments.geojson` | Local Path() | GCS read |
| `api_dashboard.py` | `data/runners.csv` | Local Path() | GCS or local |
| `api_reports.py` | Various report files | storage.py module | Already migrated ✓ |

### Storage Systems Status

**storage_service.py** (Primary - GCS-aware):
- ✅ Has: `save_file()`, `load_file()`, `save_json()`, `load_json()`, `get_latest_run_id()`
- ❌ Missing: `read_parquet()`, `read_csv()`, `read_geojson()`, file listing/globbing

**storage.py** (Legacy):
- Has: `read_json()`, `read_text()`, `exists()`, `mtime()`, `ls()`
- Issues: Requires RUNFLOW_ENV, doesn't auto-detect Cloud Run
- Status: Partially replaced but still used by some routes

---

## Migration Strategy Needed

### Question 1: File Read Methods

Should `StorageService` be extended with:
```python
def read_parquet(self, file_path: str) -> pd.DataFrame:
    """Read parquet from GCS or local, return DataFrame."""
    
def read_csv(self, file_path: str) -> pd.DataFrame:
    """Read CSV from GCS or local, return DataFrame."""
    
def read_geojson(self, file_path: str) -> dict:
    """Read GeoJSON from GCS or local, return dict."""
    
def glob(self, pattern: str, directory: str = "") -> List[str]:
    """List files matching pattern in GCS or local."""
```

### Question 2: Data Directory Strategy

How should routes access `data/runners.csv`?
- **Option A**: Keep `data/` local in Docker image (simplest)
- **Option B**: Upload to GCS and read from there
- **Option C**: Hybrid - data/ stays local, reports/ from GCS

### Question 3: Reports Directory Access

For `reports/{run_id}/bins.parquet`:
- **Option A**: Download from GCS to `/tmp` at startup
- **Option B**: Stream from GCS on-demand
- **Option C**: Use `gcsfs` or `smart_open` for transparent GCS access

---

## Dependencies Available

From `requirements.txt`:
- ✅ `google-cloud-storage` - Available for GCS access
- ❓ `gcsfs` - Need to check if installed
- ❓ `smart_open` - Need to check if installed

---

## Questions for ChatGPT

1. **Should StorageService be extended** with data-type-specific read methods (parquet, csv, geojson)?
2. **What's the best pattern** for pandas reading from GCS (gcsfs, smart_open, or download-to-tmp)?
3. **Should data/ files be in GCS** or stay in Docker image?
4. **How should routes handle file listing/globbing** in GCS (e.g., `glob("*-Flow.csv")`)?
5. **Is there a library** we should add to requirements for transparent GCS access?

---

## Success Criteria

After fixing:
- ✅ All Cloud Run routes read from GCS when needed
- ✅ All Cloud Run UI pages load correct data
- ✅ No "file not found" warnings in Cloud Run logs
- ✅ Local environment still works (reads from local filesystem)
- ✅ Single unified storage interface across all routes

---

**This README will be included in the ZIP for ChatGPT's comprehensive audit.**

