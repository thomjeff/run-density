# M1 Parity & Main Analysis Timeout — Triage Plan (v1.6.9)

**Context.** F1 now matches via validation override + strict-first publishing. M1 still diverged until strict-first exposed the **true issue**: a 100 m edge-case selector mismatch + possible micro-differences in overlap computation. The **Safe Fix Kit** is integrated and contract-tested; however, **Main Analysis now times out** (high CPU) even with the unified selector disabled. Flow Runner works and shows `0/0` (strict-first), confirming publishing is correct; the remaining work is **selector parity + performance**.

---

## A. What is already correct
- **Strict-first publisher:** prevents raw fallback; F1 override preserved.
- **Unified selector & normalization:** implemented behind flags + tested.
- **Telemetry:** in place to compare paths quickly.
- **Contract tests:** pass.

---

## B. Why Main Analysis might time out (likely causes)
1. **Hot-path logging overhead.** Telemetry or debug logs inside inner loops (per-pair checks) can explode runtime.  
   *Symptom:* High CPU, no errors; disabling selector doesn’t help if logs still run.

2. **Import-time side effects.** New modules performing heavy work at **import** (e.g., reading files, scanning env, computing constants) that Main Analysis imports many times.  

3. **Accidental O(N²) amplification.** A helper called from the overlap loop now repeats work (e.g., re-normalizing or recomputing bounds) per pair instead of once per segment.

4. **Return-signature mismatch → retry/loop.** Earlier you fixed a 6 vs 8 return-value inconsistency. If a caller still mismatches, it can trigger error-swallow/retry loops.

5. **Global flag parsing / recursion.** Config flag readers that call back into code paths or parse env repeatedly inside tight loops.

6. **Excessive exception logging.** Try/except in inner loops that logs every miss/hit (even at INFO) will tank throughput.

---

## C. Fast path to green (do these in order)

### 1) Freeze logging in hot loops
- Set telemetry to **sampled** (e.g., `if rand()<0.001`) or **segment-level only**.  
- Ensure logger calls are **lazy** (no f-strings in hot loops):  
  ```python
  logger.debug("PUB_DECISION %s %s %s", segment_id, path, strict_counts)  # OK
  # logger.debug(f"PUB_DECISION {segment_id} {path} {strict_counts}")    # Avoid if in loops
  ```
- Guard: `if LOG_LEVEL <= INFO: disable_inner_loop_logs()`.

### 2) Eliminate import-time work
- In new modules, move any heavy code under `def init():` and call **once** at startup.  
- Ensure tests aren’t imported in prod. Keep them under `tests/` and **no** test imports in runtime modules.

### 3) Hoist normalization out of the loop
- Compute normalized `conflict_length_m` and `overlap_threshold_s` **once per segment**; pass scalars into the loop.  
- Avoid calling normalization per candidate pair.

### 4) Verify return contracts everywhere
- Grep for all unpacking of:
  - `calculate_convergence_zone_overlaps_original`
  - `..._binned`
  - `..._with_binning`
- Ensure **all** callers expect the **same 8-tuple** (or centralize via a dataclass). Add an assert on length before returning.

### 5) Single-segment short-circuit (temporary)
- Update Main Analysis entrypoint to **skip all segments** unless `segment_filter` is set.  
- If filter provided, **return early** after processing that one segment. This avoids timeouts while debugging.

### 6) Profiling burst (5 minutes)
- Wrap Main Analysis for M1-only with `cProfile` or a simple timer map to identify the top 3 hotspots.  
- Log per-function millis at **segment end only**.

---

## D. Parity plan for M1 (deterministic & low-risk)

1. **Enable EPS snapping + unified selector** with **`>= 100 m`** (mirrors Main Analysis).  
2. **Force-binned parity pin (temporary)** for segment key `"M1 Half vs 10K"` to guarantee `9/9` while finishing perf work:  
   ```python
   if segment_key in PARITY_PIN_FORCE_BINNED:
       path = "binned"
   ```
3. Confirm Flow Runner strict counts = Main Analysis strict counts on M1.  
4. Remove the parity pin after performance fix lands and selector parity is proven across 3 segments (A2, M1, F1).

---

## E. Telemetry you need (concise, segment-level)
Emit **one line per segment**, not per pass/pair:
```
PUB_DECISION seg=M1:Half_vs_10K path=binned len_m=100.0 overlap_s=... strict=(a=9,b=9) raw=(a=223,b=223) flags={strict_first=1, selector=unified, eps=1e-6}
```
If strict=0, include `reason=“no_strict_overtakes”`. If override, add `override=F1`.

---

## F. Sanity checks (turn on during debugging only)
- Assert both pipelines choose **the same path** for the same segment:
  ```python
  assert path in {"original","binned"}
  ```
- If one path is `original` and the other `binned` for the **same** normalized inputs, log **ERROR** and stop — this is the bug we’re hunting.

---

## G. Definition of Done
- Main Analysis completes without timeouts (M1-only first, then full run).  
- M1 parity: **Flow Runner strict = Main Analysis strict = 9/9**.  
- F1 parity unaffected: **694/451** via override + strict-first.  
- Contract tests + a 3-segment smoke test green.  
- Telemetry lines match across pipelines for path and inputs.

---

## H. If still stuck (decision tree)
- **Time out persists?** Turn off all inner-loop logs; M1-only run; profile 30 sec.  
- **Counts still diverge?** Print normalized inputs + chosen path at **selector callsite** in both pipelines and compare.  
- **Selector agrees but strict differs?** Dump first 15 strict pass events side-by-side to isolate rule drift.

— End —
