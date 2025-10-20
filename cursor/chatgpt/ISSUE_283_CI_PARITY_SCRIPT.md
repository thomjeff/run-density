# Issue #283 - CI Parity Script (from ChatGPT)

## Drop-in CI Parity Script

ChatGPT has provided a comprehensive validation script that checks:
- ✅ Flagged bins counts match between report and artifacts
- ✅ Segment counts match between report and artifacts
- ✅ **Exact segment ID sets** match (not just counts)
- ✅ Canonical field names are used correctly
- ✅ Optional: Rate units conversions using segment widths

### Features

**Exit codes:**
- `0` = OK (all checks pass)
- `1` = Parity mismatch or validation failure
- `2` = Usage / path errors

**Validates:**
1. `reports/Density.md` Executive Summary vs `artifacts/ui/flags.json`
2. `reports/Density.md` vs `artifacts/ui/segment_metrics.json` (if present)
3. Optional: `tooltips.json` presence (if `--require-tooltips`)
4. Optional: Rate unit conversions with `--check-units`

### Usage Examples

**Local development:**
```bash
python tests/verify_artifact_parity.py --root reports/2025-10-20 --verbose
```

**CI/CD pipeline:**
```bash
python tests/verify_artifact_parity.py --root $ARTIFACTS_ROOT --check-units --verbose
```

**Post E2E tests:**
```bash
python e2e.py --local
python tests/verify_artifact_parity.py --root reports/$(date +%Y-%m-%d)
```

---

## Script Implementation

The full script has been saved to: **`tests/verify_artifact_parity.py`**

Key validation logic:
- Parses `Density.md` Executive Summary using regex
- Handles both canonical (`segment_id`, `flagged_bins`) and legacy (`seg_id`, `flagged_bin_count`) field names
- Compares exact sets of segment IDs (not just counts)
- Optional unit validation: `rate_per_m_per_min ≈ (rate / width_m) * 60`

---

## GitHub Actions Integration

Example workflow snippet provided for CI integration:

```yaml
- name: Run parity checks (counts & sets)
  run: |
    python tests/verify_artifact_parity.py --root ./build --verbose

- name: Run parity + units checks
  run: |
    python tests/verify_artifact_parity.py --root ./build --check-units --verbose
```

---

## Next Steps

1. ✅ Script saved to `tests/verify_artifact_parity.py`
2. ⏳ Test locally after next E2E run
3. ⏳ Integrate into CI/CD pipeline
4. ⏳ Use during Issue #283 implementation for continuous validation

---

**This script provides:**
- Fast local validation during development
- CI/CD gate enforcement
- Regression testing capability
- Clear error messages indicating which check failed

**Ready to use immediately!** 🚀

---

**Source:** ChatGPT Technical Architecture Review (2025-10-20)

