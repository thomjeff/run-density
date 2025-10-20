# Issue #283 - Request for CI Parity Script

## Request

ChatGPT offered:
> If you want, I can also provide a tiny `verify_artifact_parity.py` script (drop-in for CI) that reads the built folder and exits non-zero on any mismatch—handy for quick local runs.

**Yes, please provide this script!**

## Requirements

Based on the Final Acceptance Checklist, the script should verify:

### 1. Report vs Artifacts Parity
- Parse `Density.md` Executive Summary for:
  - Flagged bins count
  - Segments with flags count
- Parse `flags.json` for:
  - Sum of `flagged_bins` (or `flagged_bin_count` for backwards compat)
  - Unique `segment_id` (or `seg_id`) count
  - **Exact set of segment IDs**
- Parse `segment_metrics.json` for same validation
- **Assert:** Report and artifacts match exactly

### 2. Units Consistency
- Verify `rate` field is present in bins (p/s)
- If `rate_per_m_per_min` exists, verify conversion formula:
  ```python
  abs(rate - (rate_per_m_per_min/60)*width_m) <= 1e-6 * max(1, rate)
  ```
- Check display labels in report use "p/s"

### 3. Data Contracts
- Verify `flags.json` is non-empty
- Verify `segment_metrics.json` is non-empty
- Check canonical field names are present

### 4. Exit Codes
- Exit 0 on success (all checks pass)
- Exit non-zero on any mismatch
- Print clear error messages indicating which check failed

## Usage Scenarios

This script should work for:

1. **Local development:**
   ```bash
   python verify_artifact_parity.py reports/2025-10-20
   ```

2. **CI/CD pipeline:**
   ```bash
   python verify_artifact_parity.py $ARTIFACTS_ROOT
   ```

3. **Post E2E tests:**
   ```bash
   python e2e.py --local
   python verify_artifact_parity.py reports/$(date +%Y-%m-%d)
   ```

## Suggested Location

Place at: `tests/verify_artifact_parity.py`

This keeps it with other test/validation scripts and makes it easy to import from tests.

---

**This script would be invaluable for:**
- ✅ Fast local validation during Issue #283 implementation
- ✅ CI/CD gate enforcement
- ✅ Regression testing after future changes
- ✅ Quick sanity check after report generation

**Ready to receive and integrate this script!**

