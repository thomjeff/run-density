# Analysis: Why Two Versions of bins.parquet Exist

## Current Situation

For each day, there are two versions of `bins.parquet`:
1. `/{day}/bins/bins.parquet` - Contains ALL segments (28 segments, 23600 rows)
2. `/{day}/reports/bins.parquet` - Contains filtered segments (6 SAT segments, 4160 rows)

## Root Cause

The v1 bin generation function (`_generate_bin_dataset_with_retry`) uses `density_results` to determine which segments to process. Even though we:
1. Filter `segments_df` before passing to `generate_bins_v2()` (Issue #515 fix)
2. Pass `day_density` (day-scoped density results) to bin generation

The v1 function still generates bins for ALL segments because it iterates through all segments in `density_results`, not just the filtered `segments_df`.

## Why We Copy to Reports

The `generate_new_density_report_issue246()` function (via `load_parquet_sources()`) expects bins to be in the `reports_dir` (which is `/{day}/reports/`). This is a hardcoded requirement in the v1 report generation code.

## Options to Eliminate Duplication

### Option 1: Filter density_results Before Bin Generation ✅ RECOMMENDED
**Approach**: Filter `density_results` to only include segments for the day before passing to bin generation.

**Pros**:
- Bins will only contain day-specific segments from the start
- No need to filter in reports (though we can keep it as a safety check)
- Eliminates duplication (bins/ and reports/ will be identical)

**Cons**:
- Requires understanding the structure of `density_results` and filtering it correctly
- Need to ensure filtering doesn't break v1 bin generation logic

**Implementation**:
```python
# In pipeline.py, before calling generate_bins_v2():
# Filter day_density to only include day segments
day_segment_ids = set(day_segments_df['seg_id'].unique())
if 'segments' in day_density:
    day_density_filtered = {
        'segments': {
            seg_id: seg_data 
            for seg_id, seg_data in day_density['segments'].items()
            if seg_id in day_segment_ids
        },
        # ... preserve other keys
    }
    day_density = day_density_filtered
```

### Option 2: Modify load_parquet_sources to Accept Alternative Path
**Approach**: Modify `load_parquet_sources()` to accept an optional `bins_dir` parameter.

**Pros**:
- No duplication - bins stay in `/{day}/bins/`
- Reports read directly from bins directory

**Cons**:
- Requires modifying v1 report generation code
- May break other code that depends on bins being in reports_dir
- More invasive change

### Option 3: Generate Bins Directly to Reports Directory
**Approach**: Change `generate_bins_v2()` to save bins directly to `/{day}/reports/` instead of `/{day}/bins/`.

**Pros**:
- No duplication
- Bins are where reports expect them

**Cons**:
- Breaks the v2 directory structure convention (`/{day}/bins/` is expected)
- May break other code that reads from `/{day}/bins/`
- Less clean separation of concerns

### Option 4: Accept Duplication (Current Approach)
**Approach**: Keep both versions, document why.

**Pros**:
- No code changes needed
- Clear separation: raw bins vs filtered bins
- `/{day}/bins/` serves as archive of all segments
- `/{day}/reports/` contains day-scoped data for reports

**Cons**:
- Duplication (2x storage for bins)
- Confusing for users
- Need to maintain filtering logic in reports

## Recommendation

**Option 1** is the best approach because:
1. It fixes the root cause (bins containing all segments)
2. Eliminates duplication (bins/ and reports/ will be identical after filtering)
3. Maintains clean directory structure
4. Keeps filtering in reports as a safety check

## Next Steps

1. Investigate the structure of `density_results` to understand how to filter it
2. Implement filtering of `density_results` before bin generation
3. Verify bins only contain day-specific segments after fix
4. Remove or simplify filtering logic in reports (keep as safety check)

