# Local Filesystem Implementation Example

This document shows the pattern we used successfully for local filesystem runflow implementation.

## Pattern: Dual-Mode Functions

Functions detect whether they're in runflow or legacy mode and branch accordingly.

### Example 1: `density_report.py` - Report Generation

```python
def _generate_legacy_report_format(
    daily_folder_path: str,
    date_str: str,
    # ... other params ...
    run_id: Optional[str] = None  # ✅ Added run_id parameter
) -> str:
    """
    Generate legacy markdown report format.
    """
    # ... generate markdown_content ...
    
    # ✅ Dual-mode path selection
    if run_id:
        # Runflow mode: Use UUID-based paths
        report_path = get_runflow_file_path(run_id, "reports", "Density.md")
        report_path.write_text(markdown_content)
        print(f"✅ Report saved to: {report_path}")
        # ✅ Skip storage_service - already written directly
    else:
        # Legacy mode: Use date-based paths
        md_path, csv_path = get_report_paths(date_str, "md")
        storage_service = StorageService()
        storage_service.save_file(
            filename=f"{date_str}_Density.md",
            content=markdown_content,
            date=date_str
        )
        print(f"📊 Density report saved: {md_path}")
    
    return markdown_content
```

**Key Points:**
- Added `run_id: Optional[str] = None` parameter
- Check `if run_id:` to detect mode
- Runflow mode: Use `get_runflow_file_path()`, write directly, skip `storage_service`
- Legacy mode: Use old path logic, use `storage_service`

---

### Example 2: `density_report.py` - Bin Output Directory

```python
def generate_density_report(
    # ... params ...
    run_id: Optional[str] = None  # ✅ Added run_id parameter
) -> Dict[str, Any]:
    """Generate density report with bins, maps, and heatmaps."""
    
    # ✅ Override bins output directory for runflow mode
    if run_id:
        output_dir = str(get_runflow_category_path(run_id, "bins"))
        print(f"Issue #455: Using runflow structure for run_id={run_id}, bins_dir={output_dir}")
    else:
        output_dir = None  # save_bins.py will use default
    
    # Generate bins
    daily_folder_path, bin_metadata, bin_data = _generate_and_save_bins(
        # ... params ...
        output_dir=output_dir  # ✅ Pass runflow bins directory
    )
    
    # ... rest of function ...
    
    # ✅ Write metadata at the end
    if run_id:
        run_folder = get_run_folder_path(run_id)
        metadata = create_run_metadata(run_id, run_folder, status="complete")
        write_metadata_json(run_folder, metadata)
        print(f"Issue #455: Written metadata.json to {run_folder}/metadata.json")
    
    return result
```

**Key Points:**
- Override `output_dir` to redirect bins to `runflow/<run_id>/bins/`
- Write `metadata.json` at the end to capture all generated files
- Print debug logs with "Issue #455" prefix for traceability

---

### Example 3: `frontend.py` - UI Artifacts

```python
def export_ui_artifacts(run_dir: Path, run_id: str):
    """Export UI artifacts for dashboard."""
    
    # ✅ Detect runflow vs legacy mode
    if is_legacy_date_format(run_id):
        # Legacy: artifacts/{run_id}/ui/
        artifacts_path = Path("artifacts") / run_id / "ui"
    else:
        # Runflow: runflow/{run_id}/ui/
        artifacts_path = get_runflow_category_path(run_id, "ui")
    
    artifacts_path.mkdir(parents=True, exist_ok=True)
    
    # Generate UI files
    schema_path = artifacts_path / "schema_density.json"
    schema_path.write_text(json.dumps(schema, indent=2))
    
    # ... generate other UI files ...
    
    print(f"✅ UI artifacts exported to: {artifacts_path}")
```

**Key Points:**
- Use `is_legacy_date_format(run_id)` to detect legacy vs runflow
- Use `get_runflow_category_path(run_id, "ui")` for runflow paths
- Direct filesystem writes (no storage_service)

---

### Example 4: `heatmap_generator.py` - Heatmap Paths

```python
def generate_heatmaps_for_run(
    run_id: str,
    # ... params ...
):
    """Generate heatmaps for a run."""
    
    # ✅ Detect mode and set paths accordingly
    if is_legacy_date_format(run_id):
        # Legacy: artifacts/{run_id}/heatmaps/
        heatmap_dir = Path("artifacts") / run_id / "heatmaps"
        bins_path = reports_root / run_id / "bins.parquet"
    else:
        # Runflow: runflow/{run_id}/heatmaps/
        heatmap_dir = get_runflow_category_path(run_id, "heatmaps")
        bins_path = get_runflow_category_path(run_id, "bins") / "bins.parquet"
    
    heatmap_dir.mkdir(parents=True, exist_ok=True)
    
    # Load bins
    bins_df = pd.read_parquet(bins_path)
    
    # Generate heatmaps
    for segment_id in segments:
        heatmap_path = heatmap_dir / f"{segment_id}.png"
        # ... generate and save heatmap ...
    
    print(f"🔥 Generated {len(heatmaps)} heatmaps for {run_id}")
    return heatmap_paths
```

**Key Points:**
- Both heatmap output and bins input paths change based on mode
- Use `get_runflow_category_path()` for both reading and writing

---

## Path Construction Utilities

### `report_utils.py` Functions

```python
def get_runflow_root() -> Path:
    """Get runflow root directory based on environment."""
    storage_target = detect_storage_target()
    
    if storage_target == "filesystem":
        # Local mode: /users/jthompson/documents/runflow
        return Path(RUNFLOW_ROOT_LOCAL)
    else:
        # GCS mode: /app/runflow (container staging area)
        return Path(RUNFLOW_ROOT_CONTAINER)

def get_run_folder_path(run_id: str) -> Path:
    """Get path to specific run directory."""
    return get_runflow_root() / run_id

def get_runflow_category_path(run_id: str, category: str) -> Path:
    """Get path to category subdirectory."""
    category_path = get_run_folder_path(run_id) / category
    category_path.mkdir(parents=True, exist_ok=True)
    return category_path

def get_runflow_file_path(run_id: str, category: str, filename: str) -> Path:
    """Get full path to a file in runflow structure."""
    return get_runflow_category_path(run_id, category) / filename
```

**Key Points:**
- Single source of truth for path construction
- Uses `detect_storage_target()` to switch between local and container roots
- Automatically creates directories
- Returns `Path` objects for type safety

---

## What Worked Well

### ✅ Successful Patterns

1. **Optional `run_id` Parameter:**
   - Functions work in both modes without breaking existing calls
   - Caller controls whether to use runflow or legacy mode

2. **Path Utilities:**
   - Centralized in `report_utils.py`
   - Easy to understand and maintain
   - Single place to change path logic

3. **Direct Filesystem Writes:**
   - Skipping `storage_service` in runflow mode avoids complexity
   - Simple `Path.write_text()` or `df.to_parquet()` calls
   - No intermediate abstractions

4. **Detection Helpers:**
   - `is_legacy_date_format(run_id)` clearly identifies mode
   - Easy to read: `if is_legacy_date_format(run_id): ... else: ...`

5. **Metadata Tracking:**
   - Single call to `create_run_metadata()` at the end
   - Automatically counts files in each category
   - Accurate file_counts in `metadata.json`

---

## What Needs GCS Equivalent

### ❌ Missing for GCS Mode

1. **GCS Path Construction:**
   - Need equivalent to `get_runflow_file_path()` that returns GCS paths
   - Example: `gs://runflow/<run_id>/bins/bins.parquet`
   - Currently: Local paths being passed to GCS functions incorrectly

2. **GCS Upload Integration:**
   - Currently: `gcs_uploader.py` uses hardcoded bucket and legacy prefixes
   - Need: Pass `run_id` and construct correct GCS paths
   - Need: Upload to `gs://runflow/<run_id>/` not `gs://run-density-reports/`

3. **Dual-Root Handling:**
   - Local: `/users/jthompson/documents/runflow/<run_id>/`
   - GCS: `gs://runflow/<run_id>/`
   - Need: Unified approach that switches based on `detect_storage_target()`

4. **Storage Service Refactor:**
   - Currently: `storage_service.py` doesn't know about runflow structure
   - Need: Update to construct GCS paths correctly
   - Need: Use `detect_storage_target()` from `env.py`

---

## Proposed GCS Pattern (To Validate with ChatGPT)

### Option A: Extend Path Utilities

```python
def get_runflow_storage_path(run_id: str, category: str, filename: str) -> str:
    """
    Get storage path (local or GCS) based on environment.
    
    Returns:
        - Filesystem mode: "/users/.../runflow/<run_id>/bins/bins.parquet"
        - GCS mode: "gs://runflow/<run_id>/bins/bins.parquet"
    """
    storage_target = detect_storage_target()
    
    if storage_target == "filesystem":
        # Return local path
        return str(get_runflow_file_path(run_id, category, filename))
    else:
        # Return GCS path
        bucket = os.getenv("GCS_BUCKET_RUNFLOW", "runflow")
        return f"gs://{bucket}/{run_id}/{category}/{filename}"
```

Then in upload code:
```python
if run_id:
    # Runflow mode
    gcs_path = get_runflow_storage_path(run_id, "bins", "bins.parquet")
    upload_file_to_gcs(local_file, gcs_path)
else:
    # Legacy mode
    # ... existing logic ...
```

### Option B: Separate GCS Functions

```python
def get_gcs_runflow_path(run_id: str, category: str, filename: str) -> str:
    """Build GCS path for runflow structure."""
    bucket = os.getenv("GCS_BUCKET_RUNFLOW", "runflow")
    return f"gs://{bucket}/{run_id}/{category}/{filename}"

def upload_runflow_file(local_path: Path, run_id: str, category: str, filename: str):
    """Upload a file to runflow GCS structure."""
    gcs_path = get_gcs_runflow_path(run_id, category, filename)
    # Upload local_path to gcs_path
    # ...
```

Then in code:
```python
if run_id:
    # Write locally first
    local_path = get_runflow_file_path(run_id, "bins", "bins.parquet")
    df.to_parquet(local_path)
    
    # Upload to GCS if enabled
    if detect_storage_target() == "gcs":
        upload_runflow_file(local_path, run_id, "bins", "bins.parquet")
```

---

## Questions for ChatGPT on GCS Implementation

1. **Which pattern is cleaner:** Option A (unified function) or Option B (separate functions)?

2. **Should we write locally first then upload, or write directly to GCS?**
   - Current approach: Write to `/app/runflow/` then upload
   - Alternative: Write directly to GCS (no local copy)

3. **How to handle the "write many, upload once" pattern?**
   - Currently: Generate all files locally, then call `upload_dir_to_gcs()`
   - Problem: `upload_dir_to_gcs()` uses wrong bucket/prefix
   - Solution: ???

4. **Should we refactor existing GCS functions or create new ones?**
   - Refactor `gcs_uploader.py` functions to accept `run_id`?
   - Create new `gcs_runflow_uploader.py` module?
   - Add runflow logic to existing functions?

5. **How to validate GCS uploads in e2e tests?**
   - Download from GCS and compare to local?
   - Check file existence with `gsutil ls`?
   - Compare file counts and sizes?

---

## Success Criteria Reminder

After GCS implementation, `make e2e-staging-docker` should produce:

```
gs://runflow/HiWXoRTvqwa3wg7Ck7bXUP/
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
│   └── A1.png ... M1.png (17 files)
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

Identical to local filesystem structure, just different root.

