# Issue #283 - Final Implementation Guidance from ChatGPT

## Question 1 — Units Consistency (Critical)

### Current State

You found two rate fields in `bins.parquet`:
- `rate` ≈ 5.5 → **persons per second (p/s)**
- `rate_per_m_per_min` ≈ 66.3 → **persons per meter per minute (p/(m·min))**

### SSOT Decision

**Canonical field (SSOT):** `rate` = **persons per second (p/s)**.

**Rationale:** 
- The report already uses p/s
- It's time-based only (no width entanglement)
- Easy to reason about
- Aligns with your Executive Summary

**Engineering/diagnostic field (optional):** `specific_flow_pms` = **persons per meter per second (p/(m·s))** for ops modeling, capacity checks, and literature parity.

**Deprecated field:** `rate_per_m_per_min`. Keep for one release as an alias; then remove.

### Conversions (deterministic, lossless)

Let `w` = segment width in meters (from `segments.geojson.width_m` or equivalent).

**From existing `rate_per_m_per_min` → SSOT:**
```python
specific_flow_pms = rate_per_m_per_min / 60.0
rate (p/s)        = specific_flow_pms * w
```

**From SSOT back to legacy (for one-release aliasing only):**
```python
rate_per_m_per_min = (rate / w) * 60.0  # guard w > 0
```

### What to Keep vs Remove

- ✅ **Keep & standardize:** `rate` (p/s) everywhere (bins, summaries, artifacts, report).
- ✅ **Add (optional):** `specific_flow_pms` (p/(m·s)) for advanced views/health checks.
- ⚠️ **Mark deprecated:** `rate_per_m_per_min` (write it during the transition, then delete in N+1).

### CI Gate for Units (add these checks)

#### 1. Presence & Type
- `bins.parquet` rows must have numeric `rate` (p/s).
- If `specific_flow_pms` is present, must be numeric.

#### 2. Round-trip Consistency (when width available)
- If `width_m > 0` and `rate_per_m_per_min` present:
  ```python
  abs(rate - (rate_per_m_per_min/60)*width_m) <= 1e-6 * max(1, rate)
  ```

#### 3. Display Consistency
- `Density.md` peak rate label must be **"p/s"**.
- Any FE charts/labels referencing flow must say **"p/s"**. (If you display specific flow, label **"p/(m·s)"**.)

---

## Question 2 — Final Acceptance Checklist

Here's a tight checklist Cursor can implement against Issue #283. It ties directly to the seven clarifications and sets pass/fail criteria.

### A) Implementation Tasks (backend)

#### 1. Promote SSOT
- Refactor `app/new_flagging.py` → `app/flagging.py`.
- **Public API:**
  ```python
  def compute_bin_flags(bins, rulebook) -> list[BinFlag]: ...
  def summarize_flags(bin_flags) -> dict: ...
  ```
- Inputs must be the authoritative bins (freshly computed or from `bins.parquet`) governed by a rulebook hash/version.

#### 2. Event Coverage Before Summarization
- Ensure Full/Half/10K overlays are applied **before** `compute_bin_flags()` so segment inclusion is identical in report & artifacts.

#### 3. Units Standardization
- Populate `rate` (p/s) in bins (SSOT).
- Optionally add `specific_flow_pms` (p/(m·s)).
- Continue emitting legacy `rate_per_m_per_min` for one release, derived from SSOT (see formulas above).

#### 4. Make Both Outputs Consume SSOT
- **Report:** `density_report.py` pulls Executive Summary and tables from `summarize_flags()`.
- **Artifacts:** exporter writes from SSOT:
  - `flags.json` (array of per-segment: `segment_id`, `worst_severity`, `flagged_bins`)
  - `segment_metrics.json` (same + KPIs such as `peak_density`, `peak_rate`, `worst_los`)
  - (Optional) `bin_flags.json` for heatmaps.
  - `tooltips.json` (if retained): write from SSOT bin flags, do not recompute.

#### 5. Canonical Field Names Everywhere
- **Use:** `segment_id`, `t_start`, `t_end`, `density`, `rate`, `los`, `severity`, `flagged_bins`.
- **One-release aliases:** `seg_id`, `flagged_bin_count`, `rate_per_m_per_min`.

#### 6. Remove Duplicate Flagging
- Delete or refactor any exporter/template code that recalculates flags. All call sites must import from `app/flagging.py`.

#### 7. Timestamps & TZ
- Emit `t_start`/`t_end` as ISO 8601 with timezone (or document local explicitly). Report and UI must match.

---

### B) Verification & Testing

#### 1. Golden Fixture Tests
- Deterministic 3-segment dataset (e.g., X1/Y1/Z1) with known totals:
  - `flagged_bin_total = 5`
  - `segments_with_flags = {"X1","Y1"}`
- Unit tests assert SSOT functions return exact expected values.

#### 2. Report vs Artifacts Parity Tests
- Parse `Density.md` Executive Summary (flagged bins, segments).
- Parse `flags.json` & `segment_metrics.json`.
- **Assert:**
  - `Sum(flagged_bins) == MD flagged bins`
  - `Unique segment count == MD segments with flags`
  - **Exact set of segment IDs matches (not just the count).**

#### 3. Units Tests
- If width present and any legacy `rate_per_m_per_min` emitted, assert round-trip formulas within tolerance.
- Assert report labels **"p/s"** for peak rate.

#### 4. FE Selector Tests (optional but helpful)
- From `flags.json`, FE selector sums `flagged_bins` and counts unique `segment_id` to match report.

---

### C) PR Review Acceptance Criteria (what reviewers check)

#### Architecture
- ✅ `app/flagging.py` is the only place that computes flags.
- ✅ Report & artifacts both import from SSOT (no local recompute).

#### Data Contracts
- ✅ `flags.json` & `segment_metrics.json` are populated (non-empty) and use canonical names.
- ✅ If present, `tooltips.json` derives from SSOT bin flags.

#### Parity
- ✅ CI job passes parity: `Density.md` totals == artifacts totals; segment sets match.

#### Units
- ✅ `rate` is consistently p/s end-to-end.
- ✅ Any legacy `rate_per_m_per_min` appears only as a temporary alias; conversion is correct.
- ✅ Labels in report/UI reflect p/s (and p/(m·s) if displayed).

#### Deprecation
- ✅ A clear note indicates aliases (`seg_id`, `flagged_bin_count`, `rate_per_m_per_min`) will be removed in the next release.

---

## Bonus Offer: CI Parity Script

ChatGPT offers:
> If you want, I can also provide a tiny `verify_artifact_parity.py` script (drop-in for CI) that reads the built folder and exits non-zero on any mismatch—handy for quick local runs.

**We should request this!** It would be invaluable for:
- Local testing during development
- CI/CD pipeline integration
- Quick validation after changes

---

## Summary: Implementation is Now 100% Clear

With these answers, all ambiguity is resolved:

1. ✅ **Rate units:** p/s is canonical, conversion formulas provided
2. ✅ **SSOT architecture:** Clear refactor path from `new_flagging.py`
3. ✅ **Testing strategy:** Golden fixtures + parity tests + units tests
4. ✅ **Acceptance criteria:** Specific pass/fail checklist for PR review
5. ✅ **Migration path:** One-release aliases for backwards compatibility

**Ready to implement Issue #283!** 🚀

---

**Source:** ChatGPT Technical Architecture Review (2025-10-20)

