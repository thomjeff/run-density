# Issue #254 Status & Recommendations for ChatGPT Review

## What Cursor Fixed (Aligns with ChatGPT's Diagnosis)

### ✅ 1. Global vs Schema-Specific LOS Thresholds - FIXED
**Problem:** `rulebook.py` wasn't loading `globals.los_thresholds` from YAML
- Result: `on_course_open` schemas used wrong thresholds (0.5, 0.9, 1.6...)
- Impact: 0.755 p/m² classified as LOS A/B instead of LOS D

**Fix Applied:**
```python
# Load global LOS thresholds first
global_los_cfg = data.get("globals", {}).get("los_thresholds", {})
default_bands = LosBands(
    A=float(_extract_max(global_los_cfg.get("A"), 0.36)),
    B=float(_extract_max(global_los_cfg.get("B"), 0.54)),
    C=float(_extract_max(global_los_cfg.get("C"), 0.72)),
    D=float(_extract_max(global_los_cfg.get("D"), 1.08)),
    E=float(_extract_max(global_los_cfg.get("E"), 1.63)),
    F=float(_extract_max(global_los_cfg.get("F"), 999.0)),
)

# Use schema-specific only if present, otherwise fall back to globals
if "los_thresholds" in cfg:
    # Use schema override
else:
    bands = default_bands  # Use globals
```

**Helper Function:**
```python
def _extract_max(threshold_obj, default: float) -> float:
    """Extract max from {min, max, label} or simple number."""
    if isinstance(threshold_obj, dict) and 'max' in threshold_obj:
        return float(threshold_obj['max'])
    # ... handles simple numbers and None
```

### ✅ 2. Verification - LOS Now Correct
**Test Results:**
- `on_course_open`: A=0.36, B=0.54, C=0.72, D=1.08, E=1.63 ✅ (globals)
- `start_corral`: A=0.5, B=0.8, C=1.2, D=1.6, E=2.0 ✅ (schema override)
- 0.755 p/m² → LOS D under `on_course_open` ✅ CORRECT
- 0.755 p/m² → LOS B under `start_corral` ✅ CORRECT

### ⚠️ 3. Schema Binding Issue - STILL PRESENT (as predicted)
**Status:** `segments.csv` has NO `segment_type` column
**Result:** 100% of segments default to `on_course_open`
**Impact:** Rate flags NEVER fire (only start_corral and on_course_narrow have flow_ref)

---

## Current Flagging Results (After LOS Fix)

**Metrics:**
- Total bins: 19,440
- Flagged: 4 bins (0.02%)
- Severity: 4 watch, 0 critical
- Reason: 100% density-based

**Occupied Bins LOS Distribution:**
- A: 7,891 (99.0%)
- B: 68 (0.9%)
- C: 9 (0.1%)
- D: 4 (0.1%) ← These 4 are flagged as watch ✅

**Sample Flagged Bins:**
```
segment_id  density     rate  rate_per_m_per_min  los  flag_reason  flag_severity
A1          0.749      10.09   121.0               D    density      watch
A1          0.749      11.31   135.7               D    density      watch
A1          0.755      10.19   122.3               D    density      watch
B1          0.720       3.05   121.9               D    density      watch
```

---

## Reconciling "1,994 vs 4 flags" Gap

ChatGPT identified THREE factors:

### Factor 1: Schema Binding (100% on_course_open)
- **Current:** All segments except A1 → `on_course_open` (no rate thresholds)
- **Impact:** Rate flags can't fire → density-only flagging
- **Fix needed:** Add `segment_type` to `segments.csv`

### Factor 2: Different Flagging Policies
**Old Report (reporting.yml):**
- Flag at LOS ≥ C
- Top 5% utilization
- More sensitive

**New Rulebook (density_rulebook.yml):**
- Watch at LOS D
- Critical at LOS E/F
- Rate only where `flow_ref` defined
- Operationally conservative

### Factor 3: Old Report Used Broken Thresholds (0.0)
- The 2025-10-16-2242 report had 1,994 flags because `rate_threshold=0.0`
- ANY rate > 0 triggered critical
- This was WRONG

---

## Cursor's Recommendations (for ChatGPT Review)

### Priority 1: Fix Schema Binding NOW ✅ AGREE
**Options:**
1. **Add `segment_type` to `segments.csv`** (ChatGPT's preference) ← **Cursor recommends this**
2. Hardcode mapping in code

**Proposed mapping:**
- A1 → `start_corral` (already working)
- B1, B2, B3, D1, D2, H1, J1, J2, J3, J4, J5, L1, L2 → `on_course_narrow` (1.5m width)
- A2, A3, F1, G1, I1, K1, M1, M2 → `on_course_open` (3.0-5.0m width)

### Priority 2: Keep Current Stricter Policy ✅ AGREE
- Watch at D, Critical at E/F (as designed)
- Don't add "watch at C" unless operational feedback requires it
- Current data shows excellent management (99% LOS A)

### Priority 3: Commit & Test ✅ READY
1. Commit LOS threshold fix
2. Add schema binding
3. Re-run E2E
4. Validate realistic flagging (expect rate flags in narrow corridors during surges)

---

## Questions for ChatGPT

1. **Schema Binding Implementation:**
   - Should I add `segment_type` column to `segments.csv` now?
   - Or wait for ChatGPT to provide the exact mapping?

2. **Expected Flagging Rate:**
   - With correct schemas, what % flagging is realistic for this data?
   - Current: 99% LOS A, max density 0.755, max rate 135.7 p/m/min

3. **Boundary Policy:**
   - ChatGPT mentioned testing exact boundaries (0.36, 0.54, etc.)
   - Current implementation: `if d <= bands.A: return "A"`
   - Is this correct (inclusive) or should it be `<` (exclusive)?

4. **Additional Unit Tests:**
   - Should I add the boundary tests ChatGPT mentioned?
   - Add schema resolution telemetry?

5. **Next Steps Priority:**
   - Fix schema binding first, then continue Phase 1.5?
   - Or commit LOS fix separately and schema binding in next PR?

---

## Current Status

**Branch:** `fix/centralize-rulebook`
**PR:** #256 (needs update with LOS fix)
**Commit:** Applied LOS threshold fix (not yet committed)
**Tests:** 15/15 unit tests passing, E2E passing
**Blocking Issue:** Schema binding prevents rate-based flags

**Waiting for ChatGPT approval before proceeding with schema binding implementation.**

