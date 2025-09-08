# 🔧 Algorithm Consistency — 100 m Threshold Fix Kit (v1.6.9)

**Context (M1):**  
- Before guard: Flow Runner published **12/10** via raw fallback ❌  
- After strict-first guard: Flow Runner publishes **0/0** (no strict passes) ⚠️  
- Main Analysis: **9/9** strict passes ✅  
**Interpretation:** The two pipelines are selecting **different calculation paths** at the **100 m conflict-length edge** (and possibly computing overlap duration slightly differently).

---

## TL;DR

1. **Unify path selection** with a **single shared selector** that treats `== 100 m` identically across pipelines (choose *one* rule).
2. **Normalize inputs** into that selector: common conflict-length, overlap-duration computation, and a tolerance `EPS` for float drift.
3. **Publish strictly**: continue the strict-first publication rule; do **not** fall back to raw when `strict=0` unless an explicit, documented override exists (e.g., F1).
4. **Add contract tests + telemetry** to lock behavior and detect drift.

---

## A. Choose and codify ONE rule for the 100 m edge

Pick one of these (both are fine; pick based on expected load/accuracy tradeoff) and apply **everywhere**:

- **Option A (recommended for stability):**  
  Use **binned** when `conflict_len >= 100 m` or `overlap_duration >= 10 min`.
- **Option B (slightly stricter):**  
  Use **binned** when `conflict_len > 100 m` or `overlap_duration > 10 min`.

> **Decision hint:** Main Analysis likely used Option A (hence 9 strict passes on M1 where length is exactly 100 m), while Flow Runner used Option B. Selecting **Option A** will reproduce Main Analysis on M1 without adding branchy special cases.

---

## B. Centralize selector in a shared module (patch-agnostic)

Create an **edge-consistent selector** callable from both systems so no local conditionals drift.

### Pseudocode (language-agnostic)

```pseudo
CONST SPATIAL_BIN_THRESHOLD_M = 100.0
CONST TEMPORAL_BIN_THRESHOLD_S = 10 * 60
CONST EPS = 1e-6  // numeric tolerance

function should_use_binning(conflict_len_m, overlap_s):
    // Normalize (see Section C)
    L = normalize_conflict_length(conflict_len_m)
    T = normalize_overlap_duration(overlap_s)

    // Option A (>= 100 m)
    if (L + EPS >= SPATIAL_BIN_THRESHOLD_M) return true
    if (T + EPS >= TEMPORAL_BIN_THRESHOLD_S) return true
    return false
```

### Integration
- **Main Analysis** and **Flow Runner** both call this function before choosing between:
  - `calculate_convergence_zone_overlaps_original`
  - `calculate_convergence_zone_overlaps_binned`
  - or wrapper `*_with_binning`.

---

## C. Normalize inputs before selection

Mismatched inputs will still diverge behavior. Standardize:

1. **Conflict length (meters):**
   - Compute along the **same geometry** (centerline polyline vs buffered corridor).  
   - Use the **same projection** (or a common geodesic) for meters.  
   - Clamp tiny negatives to zero.  
2. **Overlap duration (seconds):**
   - Measure **wall-clock overlap** of active windows after the same prefilters (e.g., overlapping segment intersection).  
   - Snap sub-second jitter to nearest millisecond before comparison (or at least apply `EPS` in seconds).

### Pseudocode helpers

```pseudo
function normalize_conflict_length(len_m):
    if len_m < 0 and abs(len_m) <= 1e-6: return 0.0
    return len_m

function normalize_overlap_duration(t_s):
    if t_s < 0 and abs(t_s) <= 1e-6: return 0.0
    return t_s
```

---

## D. Keep strict-first publication (already deployed)

```pseudo
if (strict_passes > 0):
    publish(strict_passes)
else if (segment in explicit_overrides):
    publish(apply_override(segment, context))
else:
    publish(0)  // never raw fallback
```

- Document explicit overrides (e.g., **F1**): file, function name, rationale, last review date.

---

## E. Minimal telemetry to prove alignment (no noisy logs)

Emit a **single-line decision record** per segment per run:

```
PUB_DECISION seg=M1 half_vs_10k path=binned?=true L=100.0 T=xxx.x strictA=9 strictB=9 rawA=223 rawB=223
```

- `path=binned?` is the selector result.  
- `A/B` = Main Analysis / Flow Runner when running side-by-side; omit B when running single-pipeline.

---

## F. Contract tests (lock the behavior)

Add **black-box contract tests** that only inspect selector + publisher behavior, not internals.

### Examples

1. **Edge at 100 m (M1-like)**
   - `conflict_len=100.0, overlap_s < 10*60` → **binned** (Option A) → expect **strict=9** (golden), publish=9.
2. **Below edge (A2-like)**
   - `conflict_len=99.99, overlap_s < 10*60` → **original** → expect low/zero strict; publish strict (no raw fallback).
3. **Temporal trigger only**
   - `conflict_len=10, overlap_s=601` → **binned** → publish strict.

> Keep golden numbers in a small fixtures file for M1/F1/A2/A3. Update goldens only via review.

---

## G. Safety net assertions (dev-only)

At publish time (non-prod), assert **path parity** and **count parity** when both pipelines are executed in tandem:

```pseudo
assert(should_use_binning_MA == should_use_binning_FR, "Selector diverged")
assert(strict_MA == strict_FR, "Strict count diverged")
```

Gate behind an env flag to avoid prod cost: `ALGO_CONSISTENCY_ASSERT=1`.

---

## H. Rollout plan (low-risk)

1. **Introduce shared selector module** (does not replace existing yet).  
2. **Wire Flow Runner** to the shared selector.  
3. **Shadow Main Analysis** to log what it *would* do via shared selector; compare.  
4. Once identical on M1, **switch Main Analysis** to use the shared selector.  
5. Run the **contract tests + M1/F1/A2/A3**; store artifacts.  
6. Tag branch `v1.6.9-consensus-threshold` and hand off.

---

## I. Quick win (if time-pressured)

As a short-term pin for M1 while refactoring:
- Force `path=binned` for `segment_key == "M1 half_vs_10k"` via **explicit override**, **but** add a TODO and an expiry (remove once Section A–H are shipped).

---

## J. What success looks like

- M1: **9/9** in both pipelines.  
- F1: matches with existing validation override.  
- Low-overtake segments (A2, A3, L1): continue to match (sanity check).  
- Selector parity logs show **no divergence** across all segments over 5 consecutive runs.

---

## Notes

- If minor drift persists after the selector unification, focus on **Section C** (how `L` and `T` are computed). In practice, 95% of these inconsistencies come from **unit conversions, geometry sources, or float rounding**, not from the threshold constant itself.
- Keep `EPS` small but non-zero; `1e-6` is usually enough to de-flake comparisons without masking real differences.

---

**Owner:** Algorithm Consistency Task Force  
**Branch:** `v1.6.9-algorithm-consistency`  
**Last updated:** (fill on commit)
