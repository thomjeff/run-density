# Issue #455 - Phase 3 GCS Implementation Review Request

**Date:** 2025-11-04  
**Status:** Local filesystem ✅ COMPLETE | GCS upload ❌ NEEDS IMPLEMENTATION  
**Branch:** `issue-455-uuid-write-path` (25 commits)

## Executive Summary

Issue #455 successfully implemented UUID-based write paths for **local filesystem storage** (35 files in correct structure). However, GCS uploads are still using **legacy paths** instead of the new `runflow/<uuid>/` structure.

**Purpose of this document:** Request ChatGPT review of current implementation and guidance for elegantly implementing GCS uploads with the same structure.

---

## Issue #455 Scope (Updated)

### New Write Structure (Clarified 2025-11-04)

All runs will now be saved under the following structure on **local filesystem OR GCS**, depending on `detect_storage_target()`:

**Filesystem Mode** (e2e-local-docker):
```
/users/jthompson/documents/runflow/<run_id>/
├── metadata.json
├── reports/
│   ├── Density.md
│   ├── Flow.csv
│   └── Flow.md
├── bins/
│   ├── bins.geojson.gz
│   ├── bins.parquet
│   ├── segment_windows_from_bins.parquet
│   └── bin_summary.json
├── maps/
│   └── map_data.json
├── heatmaps/
│   └── *.png
└── ui/
    ├── captions.json
    ├── flow.json
    ├── health.json
    ├── meta.json
    ├── schema_density.json
    ├── segment_metrics.json
    ├── segments.geojson
    └── flags.json
```

**GCS Mode** (e2e-staging-docker, e2e-prod-gcp):
```
gs://runflow/<run_id>/
├── metadata.json
├── reports/
│   ├── Density.md
│   ├── Flow.csv
│   └── Flow.md
├── bins/
│   ├── bins.geojson.gz
│   ├── bins.parquet
│   ├── segment_windows_from_bins.parquet
│   └── bin_summary.json
├── maps/
│   └── map_data.json
├── heatmaps/
│   └── *.png
└── ui/
    ├── captions.json
    ├── flow.json
    ├── health.json
    ├── meta.json
    ├── schema_density.json
    ├── segment_metrics.json
    ├── segments.geojson
    └── flags.json
```

**Key Points:**
- Same structure in both modes, only root differs
- Bucket name changes: `run-density-reports` → `runflow`
- Use `detect_storage_target()` from `app/utils/env.py` to determine mode

---

## Current Status

### ✅ Local Filesystem Implementation - COMPLETE

**Test Run:** `SV6qfmg7rFvE5UnMPfGwnU`  
**Files Created:** 35 files in correct structure  
**Metadata:** Accurate file_counts tracking  
**Tests:** `make e2e-local-docker` - PASSING

**Example Output:**
```
/Users/jthompson/Documents/runflow/SV6qfmg7rFvE5UnMPfGwnU/
├── metadata.json (ui: 8, reports: 3, bins: 5, maps: 1, heatmaps: 17)
├── reports/
│   ├── Density.md
│   ├── Flow.csv
│   └── Flow.md
├── bins/ (5 files)
├── maps/ (1 file)
├── heatmaps/ (17 PNG files)
└── ui/ (8 JSON/GeoJSON files)
```

### ❌ GCS Implementation - INCOMPLETE

**Test Run:** `HiWXoRTvqwa3wg7Ck7bXUP`  
**Issue:** Files uploaded to **legacy GCS paths**, not runflow structure

**Current GCS Paths (WRONG):**
```
gs://run-density-reports/bins/bins.parquet                           ❌
gs://run-density-reports/bins/segment_windows_from_bins.parquet      ❌
gs://run-density-reports/artifacts/HiWXoRTvqwa3wg7Ck7bXUP/ui/*.json   ❌
gs://run-density-reports//app/runflow/.../ui/captions.json           ❌ (has /app/ prefix!)
```

**Expected GCS Paths:**
```
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/bins.parquet                ✅
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/segment_windows_from_bins.parquet ✅
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/ui/*.json                         ✅
```

**Root Cause:** GCS upload functions (`gcs_uploader.py`, `storage_service.py`) are using legacy path construction logic.

---

## Architecture Foundation: Environment Detection

**Reference:** `docs/architecture/env-detection.md` (Issue #451)

### Canonical Detection Functions (`app/utils/env.py`)

```python
def detect_runtime_environment() -> Literal["local_docker", "cloud_run"]:
    """Detect where container is running"""
    if os.getenv('K_SERVICE'):
        return "cloud_run"
    else:
        return "local_docker"

def detect_storage_target() -> Literal["filesystem", "gcs"]:
    """
    Detect storage target based on environment.
    
    Priority Order (Issue #447):
    1. GCS_UPLOAD=true → Use GCS (explicit override for staging)
    2. K_SERVICE or GOOGLE_CLOUD_PROJECT → Use GCS (Cloud Run auto-detect)
    3. Default → Use filesystem (local development)
    """
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        return "gcs"
    elif os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        return "gcs"
    else:
        return "filesystem"
```

**Current Usage:**
- ✅ `app/utils/metadata.py` - Uses canonical functions
- ❌ `app/storage_service.py` - Has own `_detect_environment()` (legacy)
- ❌ `app/storage.py` - Has `create_storage_from_env()` (legacy)
- ❌ `app/gcs_uploader.py` - No detection, hardcoded paths
- ❌ `app/routes/api_e2e.py` - Has own `_detect_environment()` (legacy)

---

## Local Filesystem Implementation Details

### Strategy: Dual-Mode Functions

Functions were updated to detect runflow vs legacy mode and branch accordingly:

```python
# Pattern used throughout:
if run_id and not is_legacy_date_format(run_id):
    # Runflow mode - use new structure
    path = get_runflow_file_path(run_id, category, filename)
    # Skip legacy storage_service calls
else:
    # Legacy mode - use old structure
    path = get_report_paths(...)
    storage_service.save_file(...)
```

### Key Functions Added to `report_utils.py`

```python
def get_runflow_root() -> Path:
    """Get runflow root directory based on environment"""
    storage_target = detect_storage_target()
    if storage_target == "filesystem":
        return Path(RUNFLOW_ROOT_LOCAL)  # /users/jthompson/documents/runflow
    else:
        return Path(RUNFLOW_ROOT_CONTAINER)  # /app/runflow

def get_run_folder_path(run_id: str) -> Path:
    """Get path to specific run directory"""
    return get_runflow_root() / run_id

def get_runflow_category_path(run_id: str, category: str) -> Path:
    """Get path to category subdirectory (reports, bins, maps, heatmaps, ui)"""
    category_path = get_run_folder_path(run_id) / category
    category_path.mkdir(parents=True, exist_ok=True)
    return category_path

def get_runflow_file_path(run_id: str, category: str, filename: str) -> Path:
    """Get full path to a file in runflow structure"""
    return get_runflow_category_path(run_id, category) / filename
```

**Note:** These functions return `Path` objects pointing to **local filesystem** only. They don't handle GCS paths yet.

---

## Files Modified for Local Filesystem

### 1. `app/report_utils.py`
**Changes:**
- Added `get_runflow_root()`, `get_run_folder_path()`, `get_runflow_category_path()`, `get_runflow_file_path()`
- Modified `get_date_folder_path()` to detect runflow paths and return as-is
- Modified `get_standard_filename()` to accept `use_runflow` flag for timestamp-free names

**Runflow Detection:**
```python
if "runflow" in str(base_path):
    # Already a runflow path, return as-is
    return base_path
```

### 2. `app/density_report.py`
**Changes:**
- Added `run_id` parameter to all report generation functions
- Override `output_dir` for bins to `runflow/<run_id>/bins/` when in runflow mode
- Use `get_runflow_file_path()` for reports when `run_id` present
- **Skip `storage_service.save_file()` calls** when in runflow mode (direct filesystem writes)
- Call `create_run_metadata()` and `write_metadata_json()` at end

**Example:**
```python
def _generate_legacy_report_format(..., run_id: Optional[str] = None):
    # ...
    if run_id:
        # Runflow mode
        report_path = get_runflow_file_path(run_id, "reports", "Density.md")
        report_path.write_text(markdown_content)
        # Skip storage_service.save_file() - already written directly
    else:
        # Legacy mode
        md_path, csv_path = get_report_paths(...)
        storage_service.save_file(filename, content, date_str)
```

### 3. `app/flow_report.py`
**Changes:**
- Added `run_id` parameter to `generate_temporal_flow_report()`
- Override `output_dir` to `runflow/<run_id>/reports/` when in runflow mode
- **Skip `storage_service.save_file()` calls** when in runflow mode
- Call `create_run_metadata()` and `write_metadata_json()` at end

**Example:**
```python
def generate_temporal_flow_report(..., run_id: Optional[str] = None):
    if run_id:
        reports_dir = get_runflow_category_path(run_id, "reports")
        output_file = reports_dir / "Flow.md"
        # Write directly, skip storage_service
    else:
        # Legacy mode with storage_service
```

### 4. `app/core/artifacts/frontend.py`
**Changes:**
- Modified `export_ui_artifacts()` to use `get_runflow_category_path()` for UUID runs
- Uses `is_legacy_date_format(run_id)` to detect legacy vs runflow mode
- Modified `_load_bins_df()` to load bins from correct location

**Path Selection:**
```python
def export_ui_artifacts(run_dir: Path, run_id: str):
    if is_legacy_date_format(run_id):
        # Legacy: artifacts/{run_id}/ui/
        artifacts_path = Path("artifacts") / run_id / "ui"
    else:
        # Runflow: runflow/{run_id}/ui/
        artifacts_path = get_runflow_category_path(run_id, "ui")
```

### 5. `app/heatmap_generator.py`
**Changes:**
- Modified `generate_heatmaps_for_run()` to use runflow paths for UUID runs
- Modified `load_bin_data()` to load from `runflow/<run_id>/bins/` for UUID runs

**Path Selection:**
```python
def generate_heatmaps_for_run(run_id: str, ...):
    if is_legacy_date_format(run_id):
        heatmap_dir = Path("artifacts") / run_id / "heatmaps"
        bins_path = reports_root / run_id / "bins.parquet"
    else:
        heatmap_dir = get_runflow_category_path(run_id, "heatmaps")
        bins_path = get_runflow_category_path(run_id, "bins") / "bins.parquet"
```

### 6. `app/core/artifacts/heatmaps.py`
**Changes:**
- Modified `export_heatmaps_and_captions()` to use runflow paths for UUID runs
- Modified `load_bin_data()` to load from correct location

### 7. `app/main.py`
**Changes:**
- Added optional `run_id` parameter to `DensityReportRequest` and `TemporalFlowReportRequest`
- Generate `run_id` if not provided in request
- Pass `run_id` to both density and flow report functions

**Combined Run Support:**
```python
@app.post("/api/density-report")
async def generate_density_report_endpoint(request: DensityReportRequest):
    run_id = request.run_id or generate_run_id()
    result = generate_density_report(..., run_id=run_id)
    return {"run_id": run_id, ...}

@app.post("/api/temporal-flow-report")
async def generate_temporal_flow_report_endpoint(request: TemporalFlowReportRequest):
    run_id = request.run_id or generate_run_id()
    result = generate_temporal_flow_report(..., run_id=run_id)
    return {"run_id": run_id, ...}
```

### 8. `app/routes/api_e2e.py`
**Changes:**
- Modified `export_ui_artifacts_endpoint()` to prioritize `runflow/` over `reports/`
- Call `create_run_metadata()` and `write_metadata_json()` after UI export

### 9. `e2e.py`
**Changes:**
- Modified `test_density_report()` to return `run_id`
- Modified `test_temporal_flow_report()` to accept and pass `run_id` for combined runs
- Updated UI artifact export to prioritize `runflow/` directories
- Refresh metadata after UI export

---

## GCS Upload Issues

### Current GCS Upload Modules

#### 1. `app/gcs_uploader.py`

**Function:** `upload_bin_artifacts(local_dir, bucket_name)`
```python
def upload_bin_artifacts(local_dir: str, bucket_name: str = "run-density-reports") -> bool:
    """
    Upload bin artifacts specifically to GCS with date-based prefix.
    """
    # Extract date from directory path for prefix
    date_folder = os.path.basename(local_dir)  # ❌ Gets "bins" not date!
    
    # Upload with date-based prefix
    return upload_dir_to_gcs(local_dir, bucket_name, date_folder)  # ❌ Wrong prefix
```

**Called from:** `app/density_report.py:878`
```python
def _upload_bin_artifacts_to_gcs(daily_folder_path: str) -> None:
    """Upload bin artifacts to GCS if enabled."""
    gcs_upload_enabled = os.getenv("GCS_UPLOAD", "true").lower() in {"1", "true", "yes", "on"}
    if gcs_upload_enabled:
        bucket_name = os.getenv("GCS_BUCKET", "run-density-reports")
        upload_success = upload_bin_artifacts(daily_folder_path, bucket_name)
```

**Issues:**
- Hardcoded bucket `run-density-reports` (should be `runflow`)
- Uses `date_folder` for prefix (legacy)
- Doesn't respect runflow structure
- Still called from `density_report.py` even in runflow mode

#### 2. `app/storage_service.py`

**Function:** `save_artifact_json(file_path, data)`
```python
def save_artifact_json(self, file_path: str, data: Dict[str, Any]) -> str:
    """
    Save JSON data to artifacts directory.
    """
    if self.config.use_cloud_storage:
        # Upload to GCS
        gcs_path = f"gs://{self.config.bucket_name}/{file_path}"
        # ❌ file_path might have /app/runflow/ prefix
        return self.save_json_to_gcs(gcs_path, data)
    else:
        # Save locally
        return self.save_json(file_path, data)
```

**Issues:**
- Takes `file_path` as-is, leading to paths like `gs://run-density-reports//app/runflow/...`
- No path normalization for GCS
- Uses `self.config.bucket_name` which is still `run-density-reports`

#### 3. `app/storage.py`

**Function:** `create_storage_from_env()`
```python
def create_storage_from_env() -> Storage:
    # Auto-detect Cloud Run environment
    if os.getenv('GCS_UPLOAD', '').lower() == 'true':
        is_cloud = True
    else:
        is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    
    env = "cloud" if is_cloud else "local"
    
    if env == "local":
        # ...
        return Storage(mode="local", root=root)
    else:
        # Cloud Run mode - use GCS with defaults
        bucket = os.getenv("GCS_BUCKET", "run-density-reports")  # ❌ Legacy bucket
        prefix = os.getenv("GCS_PREFIX", "artifacts")            # ❌ Legacy prefix
        return Storage(mode="gcs", bucket=bucket, prefix=prefix)
```

**Issues:**
- Uses legacy bucket `run-density-reports`
- Uses legacy prefix `artifacts`
- Doesn't use canonical `detect_storage_target()` from `env.py`

---

## Observed GCS Upload Behavior (e2e-staging-docker)

**Run ID:** `HiWXoRTvqwa3wg7Ck7bXUP`

**Local Container Paths (Correct):**
```
/app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/bins.parquet                        ✅
/app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/segment_windows_from_bins.parquet  ✅
/app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/reports/Density.md                      ✅
/app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/reports/Flow.csv                         ✅
/app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/ui/captions.json                         ✅
```

**GCS Upload Paths (Wrong):**
```
gs://run-density-reports/bins/bins.parquet                                   ❌
gs://run-density-reports/bins/segment_windows_from_bins.parquet              ❌
gs://run-density-reports/artifacts/HiWXoRTvqwa3wg7Ck7bXUP/ui/flags.json     ❌
gs://run-density-reports//app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/ui/captions.json ❌
```

**Expected GCS Paths:**
```
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/bins.parquet                        ✅
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/segment_windows_from_bins.parquet  ✅
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/reports/Density.md                      ✅
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/reports/Flow.csv                         ✅
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/ui/captions.json                         ✅
```

**Log Evidence:**
```
INFO:app.gcs_uploader:Uploaded: /app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/bins/bins.parquet 
    → gs://run-density-reports/bins/bins.parquet
    
   📤 Uploading captions to: gs://run-density-reports//app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/ui/captions.json
INFO:app.storage_service:Saved file to GCS: /app/runflow/HiWXoRTvqwa3wg7Ck7bXUP/ui/captions.json
```

---

## Questions for ChatGPT

### A) Review of Local Filesystem Implementation

**Question:** Is the current local filesystem implementation clean and maintainable?

**Specific Points:**
1. Is the dual-mode pattern (`if run_id: ... else: ...`) in each function appropriate?
2. Are we correctly skipping `storage_service` calls in runflow mode?
3. Is the path construction logic (`get_runflow_file_path()` etc.) robust?
4. Any concerns about the current approach before we replicate it for GCS?

### B) Guidance for GCS Implementation

**Question:** What's the most elegant way to implement GCS uploads with the runflow structure?

**Specific Points:**

1. **Architecture Pattern:**
   - Should we refactor `gcs_uploader.py` to accept `run_id` and build GCS paths similar to local?
   - Should we create a `get_gcs_path()` companion to `get_runflow_file_path()`?
   - Should we consolidate GCS logic into a single module?

2. **Path Construction:**
   - How to handle the dual root pattern:
     - Local: `/users/jthompson/documents/runflow/<run_id>/`
     - GCS: `gs://runflow/<run_id>/`
   - Should `get_runflow_file_path()` be refactored to return different prefixes based on `detect_storage_target()`?
   - Or keep separate functions: `get_local_runflow_path()` vs `get_gcs_runflow_path()`?

3. **Module Refactoring:**
   - Should we refactor `storage_service.py` to use `detect_storage_target()` from `env.py`?
   - Should we refactor `storage.py` `create_storage_from_env()` to use canonical functions?
   - Should we refactor `api_e2e.py` `_detect_environment()` to use canonical functions?
   - Or keep legacy detection for backward compatibility?

4. **Bucket Configuration:**
   - New bucket: `runflow` (vs old `run-density-reports`)
   - Should we update `constants.py` with new GCS constants?
   - Should we add environment variable `GCS_BUCKET_RUNFLOW`?

5. **Upload Points:**
   - Where are all the GCS upload calls currently?
     - `density_report.py`: `_upload_bin_artifacts_to_gcs()`
     - `storage_service.py`: `save_artifact_json()`
     - `storage.py`: `Storage.save()`
   - Should these all call a centralized upload function?
   - Should we pass `run_id` to all upload functions?

6. **Backward Compatibility:**
   - Do we need to support legacy GCS paths during transition?
   - Should legacy runs continue uploading to `gs://run-density-reports/`?
   - Or migrate everything to new bucket immediately?

7. **Testing Strategy:**
   - After GCS changes, how to validate parity between local and GCS?
   - Should we create a comparison script that downloads GCS files and compares?
   - What's the simplest way to verify `e2e-staging-docker` produces correct GCS structure?

### C) Minimal Change Approach

**Question:** What's the **minimal set of changes** to achieve GCS parity with local filesystem?

**Goals:**
- Keep changes surgical (avoid over-refactoring)
- Maintain current architecture where possible
- Ensure both modes produce identical structure
- Enable easy validation

**Constraints:**
- Issue #455 already has 25 commits
- Want to complete Phase 3 and move to Phase 4
- Need working solution for staging and production

---

## Reference Files

**Environment Detection:**
- `docs/architecture/env-detection.md` - Detection standards (Issue #451)
- `app/utils/env.py` - Canonical detection functions

**Path Construction:**
- `app/utils/constants.py` - Storage constants
- `app/report_utils.py` - Runflow path utilities

**Report Generation:**
- `app/density_report.py` - Density reports + bins
- `app/flow_report.py` - Flow reports
- `app/save_bins.py` - Bin generation

**Artifact Generation:**
- `app/core/artifacts/frontend.py` - UI artifacts
- `app/core/artifacts/heatmaps.py` - Heatmaps + captions
- `app/heatmap_generator.py` - Heatmap generation

**GCS Upload (Current):**
- `app/gcs_uploader.py` - GCS upload utilities
- `app/storage_service.py` - Storage service (reports)
- `app/storage.py` - Storage class (artifacts)

**Testing:**
- `e2e.py` - E2E test script
- `Makefile` - Test targets (`e2e-local-docker`, `e2e-staging-docker`)

---

## Success Criteria

After implementing GCS changes, we should see:

**Local Mode (e2e-local-docker):**
```
/Users/jthompson/Documents/runflow/<run_id>/
├── metadata.json
├── reports/ (3 files)
├── bins/ (5 files)
├── maps/ (1 file)
├── heatmaps/ (17 files)
└── ui/ (8 files)
```

**GCS Mode (e2e-staging-docker):**
```
gs://runflow/<run_id>/
├── metadata.json
├── reports/ (3 files)
├── bins/ (5 files)
├── maps/ (1 file)
├── heatmaps/ (17 files)
└── ui/ (8 files)
```

**Validation:**
- Same 35 files in both modes
- Same directory structure
- Same filenames
- File contents identical (except environment-specific metadata)
- `metadata.json` shows same file_counts

---

## Request Summary

**What we need from ChatGPT:**

1. ✅ **Validate** current local filesystem implementation is sound
2. 🎯 **Recommend** architectural approach for GCS implementation
3. 📋 **Outline** minimal changes needed to achieve parity
4. 🔧 **Suggest** specific functions/modules to modify
5. 📊 **Propose** validation strategy for GCS vs local comparison

**Constraints:**
- Respect existing architecture (don't over-refactor)
- Use canonical `detect_storage_target()` from `env.py`
- New bucket: `gs://runflow/` 
- Surgical changes, not rewrite
- Enable Issue #455 completion

---

## Current Branch State

**Branch:** `issue-455-uuid-write-path`  
**Commits:** 25 (4 Phase 2 cherry-picks + 21 Phase 3)  
**PR:** #457 (draft mode, no CI trigger)  
**Status:** Local ✅ COMPLETE | GCS ❌ PENDING

**Ready for ChatGPT review and guidance.**

