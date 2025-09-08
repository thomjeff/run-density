# 🏃 M1 Discrepancy – Root Cause and Fix Path

## Executive Summary
Unlike the F1 discrepancy (caused by missing validation overrides), the M1 discrepancy comes from **calculation path divergence**.  
Flow Runner appears to fall back to **raw passes when strict passes = 0**, while Main Analysis correctly sticks to strict results.  
Additionally, M1 sits **exactly on a binning threshold (100m conflict length)**, making it sensitive to edge-case handling between `original` vs `with_binning` functions.

---

## 🔑 Key Findings

- **Flow Runner behavior**: Reports `12/10` overtakes despite **0 strict passes** → suggests fallback to raw pass counts.
- **Main Analysis behavior**: Reports `9/9`, strictly respecting strict passes, with no fallback.
- **Boundary audit**: M1 → 538 overlapped pairs, 223 raw passes, 0 strict passes → confirms that strict is possible but Flow Runner is mis-publishing raw counts.
- **Threshold sensitivity**: Conflict zone = 100m, which is the **exact cutoff** for switching from original to binned calculation functions.

---

## 🎯 Root Cause Hypothesis
1. **Fallback bug**: Flow Runner defaults to raw passes when strict=0 (unlike Main Analysis).  
2. **Threshold handling inconsistency**: Main Analysis and Flow Runner may differ in how they handle the `== 100m` case.  
3. **Parameter mismatch**: If Flow Runner passes slightly different duration/zone parameters into the function, it may trigger fallback differently.

---

## 🛠️ Action Plan

### Phase 1 – Instrumentation
- Add **trace logging** to confirm which function (`original`, `binned`, or `with_binning`) is being invoked for M1 in both systems.
- Log whether strict pass counts are being **returned** vs **discarded**.

### Phase 2 – Enforce Strict-First Rule
- Patch Flow Runner to **never publish raw pass counts if strict=0**, unless explicitly overridden (like F1).  
- Main Analysis should be treated as baseline truth here.

**Pseudocode Fix:**

```python
if strict_passes > 0:
    publish(strict_passes)
elif override_rule_applies(segment):
    publish(apply_override(segment))
else:
    publish(0)   # Do NOT fall back to raw passes
```

### Phase 3 – Threshold Consistency
- Standardize edge-case handling of the `100m` spatial bin cutoff.  
- Ensure both systems interpret `== 100m` identically (either always binned or always original).

### Phase 4 – Regression Tests
- Retest **M1** (Half/10K) → expect 9/9 match.
- Confirm **F1** still matches after override logic → expect 694/451.  
- Validate a low-overtake control segment (e.g., **A2**) → expect no discrepancy.

---

## ✅ Expected Outcomes
- **F1** discrepancy resolved via override alignment (already fixed).  
- **M1** discrepancy resolved via strict-pass enforcement and threshold consistency.  
- **System-wide**: No more silent fallbacks to raw passes, ensuring Flow Runner and Main Analysis publish consistent, validated results.

---
