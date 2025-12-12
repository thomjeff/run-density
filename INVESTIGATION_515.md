# Investigation: Two Versions of bins.parquet (Issue #515)

## Problem Statement

Using run_id `Hun6YkmUfgs5xEK2YCJgbM`, there are two versions of `bins.parquet`:
1. `/{day}/bins/bins.parquet` - Original bin generation output
2. `/{day}/reports/bins.parquet` - Copied and filtered version for report generation

## File Size Analysis

### SAT (Saturday)
- `sat/bins/bins.parquet`: **18K** (original)
- `sat/reports/bins.parquet`: **31K** (filtered) ⚠️ **LARGER than original!**

### SUN (Sunday)
- `sun/bins/bins.parquet`: **175K** (original)
- `sun/reports/bins.parquet`: **199K** (filtered) ⚠️ **LARGER than original!**

## Code Flow Analysis

### 1. Bin Generation (`app/core/v2/bins.py::generate_bins_v2()`)
- **Location**: Lines 81-280
- **Output**: Saves to `/{day}/bins/` directory
- **Process**: 
  - Calls v1 `_generate_bin_dataset_with_retry()` 
  - Saves bins to day-partitioned `bins_dir`
  - **Question**: Are bins already day-scoped at generation, or do they contain all segments?

### 2. Report Generation (`app/core/v2/reports.py::generate_density_report_v2()`)
- **Location**: Lines 209-278
- **Process**:
  1. **Copy** bins from `/{day}/bins/` to `/{day}/reports/` (lines 224-231)
  2. **Load** bins from reports directory (line 234)
  3. **Filter** bins by day segments (lines 246-253)
  4. **Save** filtered bins back to reports directory (line 265)

## Key Questions

1. **Why is the filtered version LARGER than the original?**
   - Expected: Filtered should be smaller (fewer segments)
   - Actual: Filtered is larger
   - **Hypothesis**: Wrong file being copied, or bins in `/{day}/bins/` already contain wrong data

2. **Are bins in `/{day}/bins/` already day-scoped?**
   - `generate_bins_v2()` receives `segments_df` and `runners_df` filtered by day
   - But v1 `_generate_bin_dataset_with_retry()` might generate bins for all segments in `segments_df`
   - Need to verify what segments are passed to bin generation

3. **Is the filtering logic working correctly?**
   - Filtering happens at line 249: `bins_df[bins_df['seg_id'].astype(str).isin(day_segment_ids)]`
   - Need to verify `day_segment_ids` contains only SAT segments for SAT report

## Investigation Steps

1. ✅ Check file sizes (done - shows anomaly)
2. ⏳ Inspect actual segment IDs in both files
3. ⏳ Check what segments are passed to `generate_bins_v2()`
4. ⏳ Verify filtering logic is using correct day segments
5. ⏳ Check if wrong bins directory is being read

## Potential Root Causes

### Hypothesis 1: Wrong bins directory being copied
- Code at line 211: `bins_dir = runflow_root / run_id / day.value / "bins"`
- If `day.value` is wrong, could copy from wrong day's bins
- **Check**: Verify `day.value` is correct when copying

### Hypothesis 2: Bins generation includes all segments
- `generate_bins_v2()` might not filter segments before passing to v1 function
- v1 function generates bins for all segments in `segments_df`
- **Check**: Verify `segments_df` passed to `generate_bins_v2()` is day-filtered

### Hypothesis 3: Filtering logic bug
- `day_segment_ids` might contain wrong segments
- Filter might not be working correctly
- **Check**: Log actual segment IDs being filtered

## Next Steps

1. Add logging to verify:
   - What segments are in `/{day}/bins/bins.parquet`
   - What segments are in `/{day}/reports/bins.parquet` before filtering
   - What `day_segment_ids` contains
   - What segments remain after filtering

2. Check if bins in `/{day}/bins/` are already incorrectly scoped

3. Verify the copy operation is reading from the correct day's bins directory

