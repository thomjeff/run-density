# 🧭 Temporal-Flow vs Flow-Audit — Root Cause & Rapid Fix Plan
**Segments in focus:** M1 (Half/10K) and F1 (Half/10K)  
**Prepared for:** Cursor + FM data/analysis team  
**Date:** 2025-09-08 (America/Moncton)

---

## ✅ Executive Summary

- **Root cause confirmed (F1):** The **Main Analysis** applies an **F1-specific validation override** (`validate_per_runner_entry_exit_f1`) while **Flow Runner Detailed Analysis** does **not**. Flow Runner publishes the **raw calculation**; Main Analysis publishes **validated/corrected output**.  
  **Effect:** F1 shows large divergence (Main: **694/451** vs Flow Runner: **822/465**).

- **M1 discrepancy remains (small):** Both pipelines **use raw calculations** (no per-segment override), yet results differ (**9/9** vs **12/10**). This points to **inputs/parameters/call-path** mismatches or a subtle **bug** under M1 conditions.

- **Boundary audit support:**  
  - **M1:** Overlapped pairs **538**; **Raw passes 223 (41.4%)**; **Strict passes 0 (0.0%)** → Flow Runner reporting **12/10** despite **0 strict** indicates that **raw (non-strict)** is being surfaced.
  - **F1:** Overlapped pairs **464,569**; Raw **28,160 (6.1%)**; Strict **2,189 (0.5%)** → Scale amplifies raw-vs-validated divergence.

**Bottom line:** Align Flow Runner with Main Analysis’s validation stage (especially the **F1 override**) and then isolate the **M1 call/param/data** mismatch.

---

## 📌 What’s Actually Different

| Stage | Main Analysis | Flow Runner Detailed Analysis | Impact |
|---|---|---|---|
| Core pass detection | Same base algorithm | Same base algorithm | Neutral |
| Strict pass criteria | Implemented | Implemented (but not surfaced for M1) | Neutral, unless bypassed |
| Validation stage | **Includes F1 override** (`validate_per_runner_entry_exit_f1`) | **Missing** | **Major drift in F1** |
| Output selection | **Validated** results | **Raw** (for F1 and likely M1) | F1: big drift; M1: small drift |

**Interpretation:** The **result selection** stage diverges: **Main** → *validated*; **Flow Runner** → *raw* (or *mixed*) under some segments.

---

## 🎯 Rapid Fix Plan (3 Phases)

### Phase 1 — **Fix F1 Immediately** (known cause)
1. **Port the F1 validator** to Flow Runner and call it in the result-selection stage:
   ```python
   # result_selection.py
   def select_final_results(segment, raw_results, strict_results, meta):
       if segment.code == "F1":
           validated = validate_per_runner_entry_exit_f1(raw_results, meta)
           return validated
       # default path (current behavior)
       return choose_default(raw_results, strict_results, meta)
   ```
2. **Guardrails:** Add an integration test asserting **F1 Half/10K = 694/451** end-to-end.
3. **Telemetry:** Log counts at each stage (raw, strict, validated) and the **chosen** output so we can prove alignment in prod.

**Expected outcome:** Flow Runner F1 == Main Analysis F1 (**694/451**).

---

### Phase 2 — **Investigate M1 Drift (9/9 vs 12/10)**

Given both paths should be identical (no overrides), target **inputs/parameters/call-path** and **tie-breakers**:

**A. Deterministic Trace (1 run)**  
Capture and diff the following for M1 in both systems:
- **Config & parameters**: time windows, spatial thresholds, speed filters, minimum gap, bin widths, dedup toggles.
- **Input dataset fingerprints**: file path + SHA256, row counts, distinct bibs, time span, timezone/offset.
- **Pre-filters & joins**: filters applied, join keys/order, null handling policy.
- **Ordering & tie-breaks**: sort keys (time asc/desc, bib asc), stability guarantees.
- **Numeric precision**: float dtype (32/64), rounding method & places for time/distance, epsilon tolerances.
- **Concurrency**: chunking/windowing logic; any parallel aggregation path that could re-order events.
- **Event selection policy**: when strict == 0, do we fall back to raw for publication? Is that **segment-conditional**?

**B. Targeted Experiments**
1. **Freeze input**: Export the exact **intermediate table** used by Main Analysis as Flow Runner **input**. If results now match 9/9 → input delta was the cause.  
2. **Param sweep**: Programmatically sweep key thresholds (±1–5%) and compare to 9/9. A single parameter off-by-one often explains a +3/+1 swing.  
3. **Stable sort enforcement**: Force a **stable secondary sort key** (e.g., `timestamp, bib_a, bib_b`) before dedup. If Flow falls to 9/9, the culprit is non-deterministic ordering.  
4. **Strict publication rule**: Verify that, when **strict_passes == 0**, Flow Runner **doesn’t** incorrectly publish **raw** as final (which would explain 12/10).

**C. What will likely shake out**
- **Param mismatch** (e.g., time window/bin width) or  
- **Ordering instability** (dedup depends on sorted adjacency) or  
- **Publication rule** (fallback to raw when strict=0).

**Success criterion:** Flow Runner M1 == Main Analysis M1 (**9/9**).

---

### Phase 3 — **Regression + Observability**

- **Golden tests:** Lock **A2, A3, L1, M1, F1** into CI with pinned inputs and assert exact outputs.  
- **Stage metrics (per segment):** overlapped_pairs, raw_passes, strict_passes, validated_passes, **published**. Emit to logs + dashboard.  
- **Diff hook:** If `published_flow != published_main` by > 0, emit a **high-severity alert** with stage metrics.  
- **Re-run suite on any code touching:**
  - bin/windowing,  
  - dedup/merge,  
  - result selection/publication.

---

## 🧪 Minimal, Focused Tests (ready-to-implement)

1. **Unit — Validator parity (F1)**  
   - Input: canned raw events for F1 (subset that previously drifted).  
   - Expect: `validate_per_runner_entry_exit_f1(raw) -> 694/451` after aggregation.

2. **Unit — Publication rule**  
   - Case strict=0 & raw>0 (M1-like).  
   - Expect: **publish strict (0)** unless a validator explicitly says otherwise. No silent fallback to raw.

3. **Integration — End-to-end (F1 & M1)**  
   - Pin inputs. Assert exact published numbers equal to Main Analysis.

4. **Property-based (density sweep)**  
   - Generate synthetic sequences with controllable overtake density.  
   - Expect: **Flow == Main** across densities; no growth in delta with density.

---

## 🛡️ Design Recommendations (Prevent Repeat)

- **Single source of truth for validation:** Centralize segment-specific validators into a **registry** used by **both** pipelines.
  ```python
  VALIDATORS = {
      "F1": validate_per_runner_entry_exit_f1,
      # future: "X2": validate_turnback_zone, ...
  }

  def apply_validation(segment_code, raw, strict, meta):
      fn = VALIDATORS.get(segment_code)
      if fn:
          return fn(raw, meta)
      return strict  # default to strict; never publish raw by default
  ```

- **Configuration, not code paths:** Store validator bindings in a **versioned config** (YAML/JSON) so deployments can’t drift. Load config in both Main & Flow.
- **Fail-closed publication:** If strict is empty/zero and no validator applies, **publish strict (zero)** and emit a warning — do **not** silently publish raw.
- **Deterministic pipelines:** Enforce stable sorts before dedup, and set explicit float tolerances/rounding policies shared across services.
- **Traceability:** For every published number, record `(raw, strict, validated, chosen, reason)` to logs for later audit.

---

## 🧩 Notes on the Boundary Audit

- **Why the pass-rate gap matters:** M1’s **0% strict** but non-zero published suggests a **publication rule** (raw surfaced) or a **strict-criteria bug** for M1.  
- **Why F1 scales badly:** With **~465K overlapped pairs**, any tendency to publish **raw** or to relax validation mushrooms into a large visible delta.

---

## 📣 Concrete Tasks for Cursor

- [ ] **Patch Flow Runner** to call `validate_per_runner_entry_exit_f1` for F1 prior to publication.  
- [ ] **Add publication rule tests** (no fallback to raw unless validator exists & says so).  
- [ ] **Emit stage metrics** (raw/strict/validated/published) in logs.  
- [ ] **Add M1 trace logging** (inputs, params, sorts) in non-prod and reproduce **9/9**.  
- [ ] **Create a shared validator registry** and load from config used by both pipelines.  
- [ ] **Lock goldens** for A2/A3/L1/M1/F1 in CI.

---

## 🏁 Acceptance Criteria

- **F1:** Flow == Main (**694/451**).  
- **M1:** Flow == Main (**9/9**).  
- **CI:** Regression suite fails if any tracked segment changes by >0 without an accompanying config change.  
- **Observability:** For every segment, logs show `raw, strict, validated, published, reason`.

---

### Appendix — Quick Pseudocode for Safer Publication

```python
def publish_overtakes(segment_code, raw, strict, meta):
    # 1) Always compute strict first
    # 2) Apply segment validator if configured
    validated = apply_validation(segment_code, raw, strict, meta)

    # 3) Choose final output with transparent policy
    if validated is not None:
        chosen, reason = validated, "segment_validator"
    elif strict is not None:
        chosen, reason = strict, "strict_default"
    else:
        chosen, reason = raw, "raw_fallback_only_with_explicit_flag"
        # consider banning this path entirely

    log_publish_metrics(segment_code, raw, strict, validated, chosen, reason)
    return chosen
```
