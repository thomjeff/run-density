# Issue #283 - Readiness Assessment from ChatGPT

## Cursor's Understanding Summary

Based on the Q&A clarifications, Cursor demonstrated understanding of:

✅ **The core problem** (two flagging paths) and the SSOT solution.  
✅ **Refactor** `new_flagging.py` → `flagging.py` with `compute_bin_flags()` + `summarize_flags()`.  
✅ **Both** `Density.md` and `/artifacts` consume the same results.  
✅ **Regenerate** `tooltips.json` from SSOT (don't use it as the source).  
✅ **Add** parity tests + CI gate.

## Assessment: Very Close, Not Quite 100%

**Short answer:** Very close, not quite 100%. Cursor clearly gets the architecture and the fix, but there are a few small gaps to lock down so implementation doesn't drift.

---

## 🔎 Minor Clarifications to Reach 100%

### 1. Source of SSOT Input

**SSOT should read bin flags from the authoritative bins** (either in-memory just computed, or from `bins.parquet` that already has `flag_severity`/`flag_reason`/`los`). 

**It must not recompute flags independently.** Tie this to the rulebook version/hash.

### 2. Event Coverage Timing

**Ensure event overlays** (Full/Half/10K) are applied **before summarization** so segment inclusion is identical for report and artifacts.

### 3. Severity + Threshold Parity

**Confirm severity ordering and thresholds** (WATCH/ALERT/CRITICAL) and LOS mapping come **only from `rulebook.py`**, versioned with the rulebook hash included in artifacts.

### 4. Units Consistency ⚠️

**The report shows Peak Rate in p/s.** Some pipelines and UI code use p/min. 

**SSOT must standardize units (recommend p/s)**, and the UI/report must both label accordingly. 

**Add a unit check in the CI gate.**

### 5. Parity Checks—Lists, Not Just Counts

**CI should compare the exact set of `segment_ids`** (not only counts) between `Density.md` and `flags.json`. 

Also compare the sum of flagged bins.

### 6. Artifacts Completeness

All three files must be populated:

- **`flags.json`** (per-segment rollups) — canonical fields: `segment_id`, `worst_severity`, `flagged_bins`.
- **`segment_metrics.json`** — same rollups + KPIs (peak density/rate, worst_los). **Must not be empty.**
- **`flow.json`** — populated and using canonical names (`segment_id`, `rate`).

**Keep aliases** (`seg_id`, `flagged_bin_count`) **for one release only.**

### 7. Time Fields and TZ

**If you emit bin-level detail later:** ensure `t_start`/`t_end` are **ISO 8601 with timezone** (or clearly documented local time). 

The report and UI must match.

---

## 🟢 Green Light with These Adds

If Cursor folds in the seven clarifications above, I'm comfortable calling the understanding complete and the plan ready to implement.

---

## Next Step: Final Acceptance Checklist

ChatGPT offers to create a **"Final Acceptance Checklist"** for Issue #283 so the PR can be reviewed against it.

---

**Source:** ChatGPT Technical Architecture Review (2025-10-20)

