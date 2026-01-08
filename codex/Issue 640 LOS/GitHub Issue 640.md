# LOS Classification Overlaps and Heatmap Scale Inconsistencies

## Problem Statement
This issue was revealed when working on Issue #603. The application has multiple inconsistencies in LOS (Level of Service) classification and heatmap visualization that create irregularities in the UI:

As I worked with Cursor on fixing an issue on Density, I noted inconsitencies in the LOS for segment A1. This issue was revealed when working on Issue 603 (Active Window on Density) now fixed.

It appears there are multiple LOS thresholds in code and the inconsitencies are showing up in the UI maps on Density Segment A1 when from D (run_id: `THoqXc4d7Q7z8kVXSrBQ2X`) to B (run_id: `SxdpZwRw6PTtpPNEkbGDdd`) while Segments for A1 shows D/B (like Density) in the Segment Analysis, but the Heatmap images show a lot of orange, suggesting a D (the same for both run_ids). The Density.md reports for both run_ids show a D for A1 that suggests there is something in the UI that is different from the back-end. 

_The issue is a end-user confusion._ 

Cursor reviewed the code and found:

1. **Dual LOS Columns with Different Thresholds**: `bins.parquet` contains two LOS columns (`los_class` and `los`) that use different threshold sources and can produce different classifications for the same density value.
2. **Heatmap Scale Mismatch**: Heatmap color scales are hardcoded and don't align with rulebook LOS thresholds, causing visual inconsistencies between heatmaps and LOS classifications.

And summarized its finding into the following issues. 

## Issue 1: LOS Classification Overlaps

### Current State

`bins.parquet` contains two LOS columns:

1. **`los_class`** (created first):
   - Source: `app/bins_accumulator.py` using `DEFAULT_LOS_THRESHOLDS`
   - Thresholds: Range-based `(min, max)` tuples
     - A: (0.00, 0.20)
     - B: (0.20, 0.40)
     - C: (0.40, 0.70)
     - D: (0.70, 1.20)
     - E: (1.20, 2.00)
     - F: (2.00, inf)
   - Created when: `build_bin_features()` is called (with `los_thresholds=None`)

2. **`los`** (added later):
   - Source: `app/new_flagging.py` via `rulebook.evaluate_flags()`
   - Thresholds: Rulebook YAML (`config/density_rulebook.yml`) with upper-bound values
     - A: <= 0.36
     - B: <= 0.54
     - C: <= 0.72
     - D: <= 1.08
     - E: <= 1.63
     - F: > 1.63
   - Created when: `apply_new_flagging()` is called during flagging

### Impact

- **Inconsistent Classifications**: Same density value can produce different LOS grades
  - Example: Density 0.469 → `los_class` = "C" (0.40-0.70 range) but `los` = "B" (<= 0.54)
- **Data Redundancy**: Two columns storing the same information with different values
- **UI Confusion**: Different parts of the UI may use different columns, showing inconsistent LOS values
- **Maintenance Burden**: Two places to update if LOS thresholds change

### Root Cause

- `build_bin_features()` is called with `los_thresholds=None` in `app/density_report.py:2410, 2502`
- This causes fallback to hardcoded `DEFAULT_LOS_THRESHOLDS` instead of rulebook thresholds
- Rulebook is the authoritative source (Issue #254), but `los_class` doesn't use it

## Issue 2: Heatmap Scale Inconsistencies

### Current State

Heatmap generation (`app/heatmap_generator.py:273`) uses hardcoded scale:

```python
norm = PowerNorm(gamma=0.5, vmin=0, vmax=2.0)
```

### Problems

1. **Fixed Scale**: `vmax=2.0` is hardcoded, but rulebook LOS thresholds go up to 999.0 for F
2. **No Alignment with LOS**: Heatmap scale doesn't align with rulebook LOS thresholds
3. **Per-Segment vs Global**: Scale is the same for all segments, but density ranges vary by segment
4. **Visual Mismatch**: Heatmap colors may not correspond to actual LOS classifications shown in tables

### Impact

- **Visual Inconsistencies**: Heatmap colors don't match LOS classifications in Segment Analysis table
- **Poor Contrast**: Segments with low density (0-0.5) get compressed into a small portion of the colorbar
- **Misleading Visualization**: Users may misinterpret density values because the scale doesn't match LOS thresholds
- **No Dynamic Scaling**: All segments use the same scale, even if their density ranges differ significantly

### Root Cause

- Heatmap scale is hardcoded instead of derived from rulebook LOS thresholds
- No consideration of actual data ranges per segment
- No alignment between heatmap visualization and LOS classification logic

## Expected Behavior

1. **Single LOS Column**: Use rulebook as SSOT, eliminate `los_class` or make it an alias
2. **Consistent Thresholds**: All LOS classifications should use rulebook thresholds
3. **Aligned Heatmap Scales**: Heatmap color scales should align with rulebook LOS thresholds
4. **Dynamic Scaling**: Consider per-segment density ranges or use rulebook-based scale breaks

## Proposed Solution

### Phase 1: Unify LOS Classification

1. **Update `build_bin_features()`** to use rulebook thresholds instead of `DEFAULT_LOS_THRESHOLDS`
   - Convert rulebook thresholds to range format for `los_classify()`
   - Or update `los_classify()` to accept rulebook format
2. **Remove `los_class` column** or make it an alias to `los`
3. **Update Issue #603 fix** to prefer `los` over `los_class` (rulebook is authoritative)

### Phase 2: Fix Heatmap Scales

1. **Derive scale from rulebook**: Use rulebook LOS thresholds to set colorbar breaks
   - A: 0.0 - 0.36
   - B: 0.36 - 0.54
   - C: 0.54 - 0.72
   - D: 0.72 - 1.08
   - E: 1.08 - 1.63
   - F: 1.63+
2. **Consider dynamic scaling**: Optionally use per-segment density ranges for better contrast
3. **Align colorbar with LOS**: Ensure heatmap colors match LOS classifications in tables

## Files to Review/Modify

### LOS Classification
- `app/bins_accumulator.py` - `DEFAULT_LOS_THRESHOLDS` and `los_classify()`
- `app/density_report.py` - `build_bin_features()` calls with `los_thresholds=None`
- `app/new_flagging.py` - `_apply_rulebook_evaluation()` creates `los` column
- `app/save_bins.py` - Saves both `los_class` and `los` to parquet
- `app/core/artifacts/frontend.py` - Issue #603 fix uses `los_class` (should prefer `los`)

### Heatmap Generation
- `app/heatmap_generator.py:273` - Hardcoded `vmax=2.0` scale
- `app/heatmap_generator.py:266` - LOS colormap creation
- `config/density_rulebook.yml` - LOS thresholds (SSOT)

## Testing Criteria

1. **LOS Consistency**: Verify `los_class` and `los` produce identical values (or remove `los_class`)
2. **Heatmap Alignment**: Verify heatmap colors align with LOS classifications in Segment Analysis table
3. **UI Consistency**: Verify all UI components show consistent LOS values
4. **Rulebook SSOT**: Verify all LOS classifications use rulebook thresholds

## Related Issues

- Issue #603: Active Window calculation (uses `los_class`, should use `los`)
- Issue #254: Rulebook-based flagging (established rulebook as SSOT)

## References

- `codex/issue603-los-columns-explanation.md` - Detailed analysis of dual LOS columns
- `codex/issue603-root-cause-analysis.md` - Active Window root cause analysis

Files for Reference:
**run_id: `THoqXc4d7Q7z8kVXSrBQ2X` before issue #603:**
<img width="708" height="422" alt="Image" src="https://github.com/user-attachments/assets/7035827e-4beb-4ec3-991d-06b71b17725c" />
<img width="708" height="422" alt="Image" src="https://github.com/user-attachments/assets/01708e7c-23a7-47ea-9889-7f67965f2fc7" />
<img width="708" height="422" alt="Image" src="https://github.com/user-attachments/assets/ca1091a0-a09f-4f6a-adf6-dce1149fe8f3" />
[/runflow/THoqXc4d7Q7z8kVXSrBQ2X.zip](https://github.com/user-attachments/files/24509110/THoqXc4d7Q7z8kVXSrBQ2X.zip)

**run_id: `ff` after issue #603:**
<img width="708" height="422" alt="Image" src="https://github.com/user-attachments/assets/5b9fa076-bc02-47a3-8601-d66fdb84a171" />
<img width="645" height="1400" alt="Image" src="https://github.com/user-attachments/assets/2755536a-eb83-4b30-9dbe-6d8440e7b9a4" />
<img width="645" height="1250" alt="Image" src="https://github.com/user-attachments/assets/6c06e567-6f09-4704-bc63-fad55e22ffd9" />
[runflow/SxdpZwRw6PTtpPNEkbGDdd.zip](https://github.com/user-attachments/files/24509121/SxdpZwRw6PTtpPNEkbGDdd.zip)