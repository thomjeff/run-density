# Issue #254: Rulebook Centralization - Before/After Metrics

## Summary

Fixed critical bug where rate thresholds defaulted to 0.0, causing 41% of bins to be incorrectly flagged. After implementing centralized rulebook logic, flagging now works correctly based on actual operational thresholds.

## Before Fix (Broken)

**Configuration:**
- `rate_warn_threshold = 0.0` (hardcoded)
- `rate_critical_threshold = 0.0` (hardcoded)
- Any bin with `rate > 0` triggered critical flag

**Results:**
- Total bins: 19,440
- Flagged: 7,972 (41.0%)
  - Critical: 7,972 (41.0%)
  - Watch: 0 (0.0%)
- All flagged bins: reason = "both" (incorrect)
- LOS A bins with 2.75 p/m/min flagged as critical (WRONG!)

**Issue:**
- All non-empty bins flagged regardless of actual conditions
- All empty bins (density=0) were unflagged
- Misleading operational intelligence

## After Fix (Correct)

**Configuration:**
- Thresholds loaded from `config/density_rulebook.yml`
- Schema-specific: `start_corral`, `on_course_narrow`, `on_course_open`
- Correct unit conversions: `rate (p/s) → rate_per_m_per_min`

**Results:**
- Total bins: 19,440
- Flagged: 0 (0.0%)
  - Critical: 0 (0.0%)
  - Watch: 0 (0.0%)
- Empty bins: 11,468 (59.0%)
- Occupied bins: 7,972 (41.0%)

**Occupied Bin Analysis:**
- Max density: 0.755 p/m² (< LOS D threshold of 2.3)
- Max rate: 135.7 p/m/min (< narrow warn threshold of 300)
- LOS distribution: 99.8% LOS A, 0.2% LOS B
- Schema: 100% using `on_course_open` (no rate thresholds)

**Validation:**
- ✅ No bins meet watch/critical criteria
- ✅ Thresholds working as designed
- ✅ 0% flagging is CORRECT for this data

## Rulebook Thresholds

**Density (LOS-based):**
- Watch: LOS D (density ≥ 2.3 p/m²)
- Critical: LOS E (density ≥ 3.0 p/m²)

**Rate (schema-specific, p/m/min):**
- `start_corral`: warn 500, critical 600
- `on_course_narrow`: warn 300, critical 400
- `on_course_open`: no rate thresholds

## Code Changes

### Files Created:
1. `app/rulebook.py` - Centralized rulebook logic (281 lines)
2. `tests/test_rulebook_flags.py` - 15 unit tests (all passing)

### Files Refactored:
1. `app/new_flagging.py` - Now uses `rulebook.evaluate_flags()`
2. `app/save_bins.py` - Removed hardcoded `NewFlaggingConfig`
3. `app/map_api.py` - Added `rulebook_version` to manifest

### Test Results:
- Unit tests: 15/15 passed ✅
- E2E tests: All passed ✅
- Flagging rate: 41% → 0% (correct behavior)

## Acceptance Criteria ✅

- [x] Rate thresholds loaded from `density_rulebook.yml` per schema
- [x] No more `rate_warn=0` or `rate_crit=0` defaults
- [x] Low density + low rate → `severity=none` ✅
- [x] Flagging based on actual operational thresholds
- [x] `rulebook_version` added to `/api/map/manifest`
- [x] All unit tests passing (15/15)
- [x] All E2E tests passing
- [x] Post-fix metrics show correct behavior

## Next Steps

1. Add `segment_type` column to `segments.csv` to enable schema-specific thresholds
2. Validate with real event data containing actual choke points
3. Consider adding lower thresholds for `on_course_open` if needed for operational planning

## Conclusion

The bug is **fixed** and working as designed. The 41% flagging was caused by broken thresholds, not by actual operational issues. The current data shows excellent crowd management (99.8% LOS A), which correctly results in 0% flagging.

