# 🧭 Temporal-Flow vs Flow-Audit — Root Cause, Fix, and Validation Plan
**Scope:** Segments **F1 (Half/10K)** and **M1 (Half/10K)**  
**Audience:** Cursor / engineering maintainers of Main Analysis & Flow Runner Detailed Analysis  
**Author:** Marathon Policy Writer (analysis distilled from your boundary + validation audit)

---

## ✅ Executive Summary

- **Root Cause (confirmed):** The **F1 discrepancy** comes from **different validation logic** paths.  
  - **Main Analysis** applies **F1-specific validation override**: `validate_per_runner_entry_exit_f1(...)`  
  - **Flow Runner** uses **raw calculation results** (no override), so it **over-reports** overtakes in F1.

- **M1 discrepancy (smaller):** Both systems **use the same calculation path** (no override), yet differ **9/9 vs 12/10**.  
  - Indicates a **secondary issue**: parameter/inputs mismatch, call-order difference, or a dedup/strict-pass selection bug in Flow Runner.

- **Immediate win:** Port the **F1 validation override** into Flow Runner and **standardize result selection** to prefer **strict passes**, not raw passes.

---

## 🔍 Evidence Recap (from your audit)

### M1 (small delta)
- **Overlapped Pairs:** 538  
- **Raw Passes:** 223 (41.4%)  
- **Strict Passes:** 0 (0.0%)  
- **Final:** Flow Runner **12/10** vs Main **9/9**  

**Signal:** Flow Runner appears to be **using raw passes** or a looser post-filter to compute “final,” because strict is **0** yet final is **non-zero**.

### F1 (large delta)
- **Overlapped Pairs:** 464,569  
- **Raw Passes:** 28,160 (6.1%)  
- **Strict Passes:** 2,189 (0.5%)  
- **Final:** Flow Runner **822/465** vs Main **694/451**  

**Signal:** Main uses **F1-specific validation override**; Flow Runner does **not**. Discrepancy scales with density.

---

## 🎯 Objectives

1. **Fix F1 immediately** by adding the same validation override to Flow Runner.  
2. **Harden result selection** so “final” counts are based on **strict** (or stricter) criteria, not raw.  
3. **Investigate M1** for residual drift with a tight, code-first checklist.

---

## 🛠️ Implementation Plan (Flow Runner)

### 1) Introduce a Validation Override Registry

> Decouple “calculation” from “validation” selection. This matches Main Analysis behavior and prevents per-segment logic from drifting.

```python
# flow_runner/validation.py
from typing import Callable, Dict, Any

Validator = Callable[[dict, dict], dict]  # (calc_artifacts, context) -> validated_artifacts

def validate_identity(artifacts: dict, context: dict) -> dict:
    """Default no-op validation."""
    return artifacts

def validate_per_runner_entry_exit_f1(artifacts: dict, context: dict) -> dict:
    """Mirror Main Analysis F1-specific override exactly."""
    # IMPORTANT: this should be a literal port from Main Analysis.
    # Pseudocode structure (replace with exact logic):
    # 1) enforce per-runner consistency on entry/exit of F1 segment
    # 2) drop/merge passes that violate directionality/order constraints
    # 3) recompute final overtakes from strict subset only
    return _apply_f1_rules(artifacts, context)  # implement using Main's logic

VALIDATION_OVERRIDES: Dict[str, Validator] = {
    # Key should match whatever identifier Main uses for F1 (e.g., segment_id, route_key, or tuple("F1","Half","10K"))
    "F1": validate_per_runner_entry_exit_f1,
}

def pick_validator(segment_key: str) -> Validator:
    return VALIDATION_OVERRIDES.get(segment_key, validate_identity)
```

```python
# flow_runner/pipeline.py
from .validation import pick_validator

def compute_final_overtakes(calc_artifacts: dict, context: dict) -> dict:
    # calc_artifacts should include: overlapped_pairs, raw_passes, strict_passes, etc.
    segment_key = context.get("segment_key")  # must match Main Analysis key for F1
    validator = pick_validator(segment_key)

    # 1) Apply per-segment validator (F1 gets special handling)
    validated = validator(calc_artifacts, context)

    # 2) Select “final” from STRICT, never from RAW (guardrails below)
    final = _select_final_counts(validated, context)
    return {**validated, **final}

def _select_final_counts(artifacts: dict, context: dict) -> dict:
    # Prefer strict; fall back to raw only if strict unavailable (and log loudly).
    strict = artifacts.get("strict_passes_counts")
    raw    = artifacts.get("raw_passes_counts")
    meta   = {"used": None, "reason": None}

    if strict is not None and _nonzero_or_zero_intent_ok(strict, context):
        meta["used"], meta["reason"] = "strict", "strict_available"
        return {"final_counts": strict, "final_source": meta}
    elif raw is not None:
        meta["used"], meta["reason"] = "raw", "strict_missing_fallback"
        return {"final_counts": raw, "final_source": meta}
    else:
        raise ValueError("No counts available for final selection.")
```

### 2) Guardrails & Telemetry (catch M1-class drift fast)

```python
# flow_runner/guards.py
def assert_monotonic(artifacts: dict) -> None:
    op = artifacts.get("overlapped_pairs_count", 0)
    rp = artifacts.get("raw_passes_count", 0)
    sp = artifacts.get("strict_passes_count", 0)
    assert 0 <= sp <= rp <= op, f"Monotonicity violated: strict={sp} raw={rp} pairs={op}"

def assert_strict_selected_when_present(artifacts: dict) -> None:
    if artifacts.get("strict_passes_count") is not None:
        src = artifacts.get("final_source", {}).get("used")
        assert src == "strict", f"Expected strict-selected final; got {src}"
```

Integrate both assertions right after `_select_final_counts` and emit structured logs:
```python
# After computing final
assert_monotonic(validated)
assert_strict_selected_when_present({**validated, **final})
logger.info("final_counts", extra={
    "segment": context.get("segment_key"),
    "overlapped": artifacts.get("overlapped_pairs_count"),
    "raw": artifacts.get("raw_passes_count"),
    "strict": artifacts.get("strict_passes_count"),
    "final_src": final.get("final_source", {}).get("used")
})
```

### 3) Config Flag (feature safety)

```python
# flow_runner/config.py
USE_VALIDATION_OVERRIDES = True  # enable in prod after tests
FINAL_FROM_STRICT_ONLY   = True  # prevents regression to RAW
```

Wire these into `compute_final_overtakes` to allow quick toggle/backout if needed.

---

## 🧪 Tests (must pass before rollout)

### Unit Tests

1. **F1 override parity**
   - **Given:** F1 calc artifacts identical to Main’s pre-validation values  
   - **When:** Flow Runner applies `validate_per_runner_entry_exit_f1`  
   - **Then:** `final_counts` **exactly match** Main Analysis **694/451** and `final_source.used == "strict"`

2. **Strict preferred over Raw**
   - **Given:** `strict_passes_count=0`, `raw_passes_count>0`  
   - **Then:** `final_counts` must still originate from **strict** (0 is valid), not raw.  
   - Confirms we never inflate final by choosing raw when strict is present.

3. **Monotonicity invariant**
   - **Given:** `overlapped >= raw >= strict >= 0`  
   - **Then:** Assertions pass; otherwise test fails.

4. **Registry default path**
   - **Given:** Unknown segment key  
   - **Then:** identity validator is used; selection still favors strict.

### Integration Tests

- **Dataset:** Use your **F1 and M1** inputs that produced the reported stats.  
- **Flow Runner (new):**
  - F1 must equal **694/451** (Main).  
  - M1 must be **9/9** (if not, this test should **fail** to force the M1 investigation to conclusion).

### Regression Matrix

| Segment | Expectation |
|---|---|
| A2 (5/1) | **match** |
| A3 (10/1) | **match** |
| L1 (0/0) | **match** |
| M1 (9/9) | **match** (post-fix) |
| F1 (694/451) | **match** (post-fix) |

---

## 🔎 M1 Investigation Checklist (code-first)

Because both pipelines use the **same calculation path**, focus on *inputs & selection*:

1. **Inputs parity**
   - Confirm identical **filtered bib sets**, **timing sources**, **segment geometry/version**, and **trajectory windows**.
   - Dump and diff **calc_artifacts** (overlapped, raw, strict) between Main and Flow Runner **before** any validation/selection.

2. **Parameter parity**
   - Verify equal values for: bin size, min-gap, pass direction epsilon, segment time bounds, speed filters, coasting filters, minimum contact length.  
   - Watch for “default differs” (Flow Runner vs Main) due to env/config precedence.

3. **Call order / dedup location**
   - Ensure **dedup happens before aggregation** (matches Main).  
   - Check that **strict** is computed from **deduped** passes, not vice versa.

4. **Final selection policy**
   - Enforce **strict-first** policy (see guardrails).  
   - If strict==0 and Main==9/9, inspect Main’s strict definition vs Flow’s.

5. **Numerical edges**
   - Floating-point comparisons: use **same rounding/epsilon**.  
   - Off-by-one on **bin edges / inclusive vs exclusive** window ends.  
   - Timezone or timestamp normalization (UTC vs local).

6. **Concurrency**
   - Parallel chunk boundaries re-joining: check for **double-counts** or **missed merges** at worker boundaries.

**Instrumentation for speed:** emit a one-line per-pass trace key only when `segment in {"M1","F1"}` and `debug_pass_tracing=True`:
```
[TRACE] seg=M1 runner=A123 t=09:41:21 type=strict enter=... exit=... bin=... reason=...
```

---

## 🚦 Rollout Plan

1. **Branch & PR**
   - Add validator registry + F1 override + strict-first selection + guardrails.

2. **Pre-merge CI**
   - Run the **unit + integration + regression matrix** above.

3. **Staged deploy**
   - **Shadow mode** (log-only) for one backfill run across F1/M1.  
   - Compare **final counts** + source (`strict/raw`) + monotonicity assert passes.

4. **Enable flags**
   - Turn on `USE_VALIDATION_OVERRIDES` and `FINAL_FROM_STRICT_ONLY` in prod.  
   - Re-run F1/M1; confirm **F1=694/451** and **M1=9/9**.

5. **Backfill & freeze**
   - Recompute historical reports for segments impacted since the divergence commit (scope: F1 first, then others if selection policy changed results).

---

## 🧩 Example Minimal Diff (pseudocode, adapt to your language)

```diff
- final_counts = artifacts.get("raw_passes_counts", {})
- final_source = "raw"
+ if USE_VALIDATION_OVERRIDES and context.segment_key == "F1":
+     artifacts = validate_per_runner_entry_exit_f1(artifacts, context)
+
+ if FINAL_FROM_STRICT_ONLY and "strict_passes_counts" in artifacts:
+     final_counts = artifacts["strict_passes_counts"]
+     final_source = "strict"
+ else:
+     final_counts = artifacts.get("strict_passes_counts") or artifacts.get("raw_passes_counts", {})
+     final_source = "strict" if "strict_passes_counts" in artifacts else "raw"
+
+ assert_monotonic(artifacts)
+ assert final_source == "strict" or "strict_passes_counts" not in artifacts
```

---

## 📣 Message to Cursor (include in PR description)

> **Summary:** Flow Runner over-reported overtakes in **F1** because it skipped the **F1-specific validation override** used by Main Analysis. We introduced a **validator registry** and ported Main’s `validate_per_runner_entry_exit_f1`. We also hardened **final selection** to always prefer **strict** over **raw** and added guardrails to catch drift (monotonicity + selection assertions).  
>
> **Impact:** F1 now matches Main (**694/451**). Low-density segments remain matching.  
>
> **M1:** Still investigating a **9/9 vs 12/10** delta; we added telemetry and tests to force strict-first selection and expose parameter/input differences quickly.  
>
> **Next:** Complete the M1 checklist; if needed, add a targeted validator (only if Main genuinely encodes stricter semantics).

---

## ✅ Acceptance Criteria

- [ ] F1 Flow Runner final overtakes **exactly equal** Main (**694/451**).  
- [ ] M1 Flow Runner final overtakes **exactly equal** Main (**9/9**).  
- [ ] All regression segments (A2, A3, L1) still **match**.  
- [ ] Logs show `final_source=strict` whenever `strict_passes_count` is present.  
- [ ] No monotonicity assertion failures in CI or staging.

---

## 📎 Notes

- If `strict_passes_count == 0` for M1 in Flow Runner while Main shows **9/9**, then the two pipelines **do not compute the same strict set**. Focus on **dedup order**, **epsilon**, and **bin edges**; these are the usual culprits.
- Avoid re-introducing per-segment forks unless validated; prefer **shared strict semantics** + **specific validators** only where domain rules truly demand it (e.g., F1).

---

*End of report.*
