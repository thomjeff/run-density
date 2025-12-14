# Issue #515: Fix Saturday Density.md Bin Scoping - Summary

## Problem

Saturday Density.md report showed incorrect metrics:
- Showing: **19440 bins** and **22 segments**
- Expected: **< 19440 bins** and **6 segments** (N1, N2, N3, O1, O2, O3)

## Investigation: Two Versions of bins.parquet

### File Locations
1. `/{day}/bins/bins.parquet` - Original bin generation output
2. `/{day}/reports/bins.parquet` - Copied and filtered version for report generation

### Why Two Versions?

**Purpose**: The `generate_new_density_report_issue246()` function expects bins to be in the `reports/` directory, so bins are copied from `bins/` to `reports/` before report generation.

**File Size Anomaly** (from run `Hun6YkmUfgs5xEK2YCJgbM`):
- SAT bins/bins.parquet: 18K
- SAT reports/bins.parquet: 31K ⚠️ **LARGER than original!**
- SUN bins/bins.parquet: 175K
- SUN reports/bins.parquet: 199K ⚠️ **LARGER than original!**

This anomaly suggested the wrong data was being copied or filtering wasn't working correctly.

## Root Cause Identified ✅

**Location**: `app/core/v2/pipeline.py:329`

**Problem**: `segments_df` (containing ALL 22 segments) was passed to `generate_bins_v2()` without filtering by day.

```python
# ❌ BEFORE (line 329)
bins_dir = generate_bins_v2(
    ...
    segments_df=segments_df,  # Contains ALL segments, not filtered by day!
    ...
)
```

**Impact**:
1. Bin generation created bins for ALL segments (22 segments) for both SAT and SUN
2. SAT bins in `/{day}/bins/bins.parquet` contained SUN segments
3. When copied to `/{day}/reports/bins.parquet`, filtering tried to reduce it, but:
   - Original bins already contained wrong segments
   - Filtering couldn't fix data that shouldn't be there

## Fix Implemented ✅

**Location**: `app/core/v2/pipeline.py:311-335`

**Solution**: Filter `segments_df` by day events before passing to `generate_bins_v2()`:

```python
# ✅ AFTER
# Filter segments to this day's events (Issue #515: Fix bin scoping)
from app.core.v2.bins import filter_segments_by_events
day_segments_df = filter_segments_by_events(segments_df, day_events)
logger.info(f"Filtered segments for day {day.value}: {len(segments_df)} -> {len(day_segments_df)} segments")

bins_dir = generate_bins_v2(
    ...
    segments_df=day_segments_df,  # ✅ Filtered by day events
    ...
)
```

## Additional Enhancements

1. **Enhanced Logging** (`app/core/v2/reports.py`):
   - Log segments found in bins before filtering
   - Log expected day segments
   - Verify filtering worked correctly
   - Warn if unexpected segments found after filtering

2. **Documentation**:
   - Documented why two versions of bins.parquet exist
   - Explained the copy and filter process
   - Added comments explaining the safety check filtering

## Expected Results After Fix

1. **SAT bins** (`sat/bins/bins.parquet`):
   - Should contain only 6 segments: N1, N2, N3, O1, O2, O3
   - Bin count should be < 19440 (proportional to 6 segments vs 22)

2. **SAT reports** (`sat/reports/bins.parquet`):
   - Should match `sat/bins/bins.parquet` (since bins are now day-scoped at generation)
   - Filtering in reports.py remains as a safety check

3. **Density.md Executive Summary**:
   - Should show 6 segments (not 22)
   - Should show correct bin count for SAT segments only
   - Should show correct flagged bins/segments counts

## Testing Required

1. Run multi-day analysis (sat + sun events)
2. Verify SAT bins.parquet contains only SAT segments
3. Verify SAT Density.md shows 6 segments
4. Verify SAT bin count is < 19440
5. Verify SUN reports are unaffected

## Commits

1. `710592b` - Investigation: Document two bins.parquet versions issue
2. `bdabf74` - Investigation: Root cause identified
3. `bb90175` - Fix: Filter segments_df by day before bin generation
4. `4223372` - Enhance: Add logging and documentation

## Related Issues

- Issue #515: Bug: Saturday Density.md Executive Summary shows incorrect bin and segment counts
- Issue #514: Fix: Day-scoping bug in Density and Locations reports for Saturday events

