# 🪲 Bug Report — Inconsistent Flagging Logic Between Report and UI Artifacts

**Issue #283**

**Labels:** `bug`, `backend`, `data-pipeline`, `high-priority`

---

## Summary

The `Density.md` report and the UI artifacts (`flags.json`, `segment_metrics.json`) report different totals for flagged bins and flagged segments.

This is caused by **duplicate flagging logic** in two separate code paths — one in the report generator, one in the UI artifact exporter — which are not synchronized.

---

## Actual Result

| Source | Flagged Bins | Segments with Flags |
|--------|--------------|---------------------|
| **Density.md** (Executive Summary) | 1875 / 19440 | 17 / 22 |
| **/artifacts/.../ui/flags.json** | 445 (sum of flagged_bin_count) | 12 segments |
| **/artifacts/.../ui/segment_metrics.json** | empty | — |
| **UI Dashboard** | Flagged bins = 0 | Segments with flags = 12 |

---

## Expected Result

- Both `Density.md` and UI artifacts reflect the **same numbers**:
  - **Flagged Bins:** 1875 / 19440
  - **Segments with Flags:** 17 / 22
- Dashboard accurately displays those totals.
- **No duplicated flagging logic** exists between report generation and artifact export.

---

## Investigation Findings

- **Report pipeline** uses canonical rulebook logic (density + rate thresholds, LOS classification) across all bins.
  → Produces correct totals (1875 / 17 segments).

- **Artifact pipeline** re-implements a partial derivation (appears density-only, event coverage subset, and alias field names like `seg_id`, `flagged_bin_count`).
  → Under-counts (445 / 12) and uses different field names.

- `segment_metrics.json` is **empty**, so the Dashboard falls back to 0.

---

## Recommended Fix (Permanent)

**Eliminate the duplicate flagging logic.**

Both report and UI artifacts should draw from a **single canonical flagging module** that produces a unified result structure.

### ✅ Implementation Plan

#### 1. Create / Refactor `flagging.py`

```python
# flagging.py
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class BinFlag:
    segment_id: str
    t_start: str  # ISO
    t_end: str    # ISO
    density: float
    rate: float
    los: str
    severity: str   # WATCH/ALERT/CRITICAL
    reason: str     # short code

def compute_bin_flags(bins, rulebook) -> List[BinFlag]:
    """
    Apply density + rate triggers, LOS mapping, event coverage.
    Return a list of BinFlag (one per flagged bin).
    """
    ...

def summarize_flags(bin_flags: List[BinFlag]) -> Dict:
    per_segment: Dict[str, Dict] = {}
    for f in bin_flags:
        d = per_segment.setdefault(f.segment_id, {
            "segment_id": f.segment_id,
            "flagged_bins": 0,
            "worst_severity": "NONE",
        })
        d["flagged_bins"] += 1
        # severity order NONE < WATCH < ALERT < CRITICAL
        order = {"NONE":0,"WATCH":1,"ALERT":2,"CRITICAL":3}
        if order[f.severity] > order[d["worst_severity"]]:
            d["worst_severity"] = f.severity

    return {
        "flagged_bin_total": len(bin_flags),
        "segments_with_flags": sorted(per_segment.keys()),
        "per_segment": list(per_segment.values()),
    }
```

#### 2. Use this single output everywhere:

- **Density.md** generator imports `summarize_flags(...)` for Executive Summary and tables.
- **UI artifact builder** writes from the same data:
  - `flags.json` ← `per_segment` (fields: `segment_id`, `worst_severity`, `flagged_bins`).
  - `segment_metrics.json` ← same rollups + optional KPIs.
  - (Optional) `bin_flags.json` = raw BinFlag list for future heatmaps.

#### 3. Canonical Field Names

- **Standard fields:** `segment_id`, `t_start`, `t_end`, `density`, `rate`, `los`, `severity`, `flagged_bins`
- **For one release only, include compatibility aliases in artifacts:**
  - `flagged_bin_count` (alias of `flagged_bins`)
  - `seg_id` (alias of `segment_id`)

#### 4. Deprecate old code

- Remove/disable any flag computation inside the artifact exporter; it should **import and serialize the SSOT (single source of truth) only**.

---

## Acceptance Criteria

- ✅ Report and UI show **identical totals** for flagged bins and segments (e.g., 1875 / 17).
- ✅ Field names are **consistent** across report, JSON, and UI.
- ✅ No "density-only" or "rate-only" divergences.
- ✅ **CI check** enforces parity before artifacts publish.

---

## ✅ Test Plan (QA + CI)

### A. Golden Fixture (deterministic)

Create a tiny deterministic dataset under `tests/fixtures/golden_course/`:
- **3 segments:** X1, Y1, Z1
- **12 bins total**; 5 bins cross density/rate thresholds
- **Known outputs:**
  - `flagged_bin_total = 5`
  - `segments_with_flags = ["X1","Y1"]` (2 segments)
  - per-segment: X1.flagged_bins=3, Y1.flagged_bins=2, worst severities set

### B. Unit tests (backend)

```python
# tests/test_flagging.py
from app.flagging import compute_bin_flags, summarize_flags

def test_summarize_flags_golden(golden_bins, rulebook):
    flags = compute_bin_flags(golden_bins, rulebook)
    agg   = summarize_flags(flags)
    assert agg["flagged_bin_total"] == 5
    assert set(agg["segments_with_flags"]) == {"X1", "Y1"}
    ps = {x["segment_id"]: x for x in agg["per_segment"]}
    assert ps["X1"]["flagged_bins"] == 3
    assert ps["Y1"]["flagged_bins"] == 2
```

### C. Artifact parity tests

```python
# tests/test_artifact_parity.py
import json, re, pathlib

def parse_exec_summary(md:str):
    fb = re.search(r"Flagged Bins:\s*(\d+)\s*/", md); assert fb
    swf = re.search(r"Segments with Flags:\s*(\d+)\s*/", md); assert swf
    return int(fb.group(1)), int(swf.group(1))

def test_report_vs_artifacts(tmp_path):
    # assume pipeline wrote outputs to tmp_path
    md = pathlib.Path(tmp_path/"reports/Density.md").read_text()
    flags = json.loads(pathlib.Path(tmp_path/"artifacts/ui/flags.json").read_text())
    segm  = json.loads(pathlib.Path(tmp_path/"artifacts/ui/segment_metrics.json").read_text())

    md_bins, md_segs = parse_exec_summary(md)

    # flags.json
    def get_flagged_bins(it): return it.get("flagged_bins") or it.get("flagged_bin_count") or 0
    f_bins_sum = sum(get_flagged_bins(x) for x in flags)
    f_segs = len({x.get("segment_id") or x.get("seg_id") for x in flags})

    assert md_bins == f_bins_sum
    assert md_segs == f_segs

    # segment_metrics.json (if present)
    if isinstance(segm, list) and segm:
        sm_bins = sum(get_flagged_bins(x) for x in segm)
        sm_segs = len({x.get("segment_id") for x in segm})
        assert md_bins == sm_bins
        assert md_segs == sm_segs
```

### D. Front-end selector test (TypeScript)

```typescript
// __tests__/flagsSelector.test.ts
import flags from '../fixtures/flags.json';

function sumFlaggedBins(list: any[]): number {
  return list.reduce((acc, r) => acc + (r.flagged_bins ?? r.flagged_bin_count ?? 0), 0);
}
function uniqueSegments(list: any[]): number {
  const ids = new Set(list.map(r => r.segment_id ?? r.seg_id));
  return ids.size;
}

test('dashboard KPIs from flags.json', () => {
  expect(sumFlaggedBins(flags)).toBe(1875);
  expect(uniqueSegments(flags)).toBe(17);
});
```

### E. CI Gate (pre-publish)

Add a step that fails the build if report and artifacts diverge:

```bash
python - << 'PY'
import json, re, sys, pathlib
root = pathlib.Path(sys.argv[1])
md = (root/"reports/Density.md").read_text()
flags = json.loads((root/"artifacts/ui/flags.json").read_text())

bins = int(re.search(r"Flagged Bins:\s*(\d+)\s*/", md).group(1))
segs = int(re.search(r"Segments with Flags:\s*(\d+)\s*/", md).group(1))

def get_fb(x): return x.get("flagged_bins") or x.get("flagged_bin_count") or 0
fb_sum = sum(get_fb(x) for x in flags)
seg_cnt = len({x.get("segment_id") or x.get("seg_id") for x in flags})

assert bins == fb_sum, f"Mismatch flagged bins: md={bins} flags.json={fb_sum}"
assert segs == seg_cnt, f"Mismatch segments: md={segs} flags.json={seg_cnt}"
print("Artifact parity OK")
PY "$ARTIFACTS_ROOT"
```

---

## 📦 Data Contracts (for `/artifacts/.../ui/`)

### `flags.json` (array of segment rollups)

```json
[
  {
    "segment_id": "A1",
    "worst_severity": "WATCH",
    "flagged_bins": 47,

    "_compat": {
      "seg_id": "A1",
      "flagged_bin_count": 47
    }
  }
]
```

### `segment_metrics.json` (array; mirrors flags + KPIs)

```json
[
  {
    "segment_id": "A1",
    "worst_severity": "WATCH",
    "flagged_bins": 47,
    "peak_density": 0.199,
    "peak_rate": 4.88,
    "worst_los": "B"
  }
]
```

### `bin_flags.json` (optional; for future heatmaps)

```json
[
  {
    "segment_id": "A1",
    "t_start": "2025-10-20T07:00:00Z",
    "t_end": "2025-10-20T07:02:00Z",
    "density": 0.33,
    "rate": 4.12,
    "los": "B",
    "severity": "WATCH",
    "reason": "DENSITY_WATCH"
  }
]
```

**Canonical names:** `segment_id`, `t_start`, `t_end`, `density`, `rate`, `los`, `severity`, `flagged_bins`.

**Aliases (one release only):** `seg_id`, `flagged_bin_count`.

---

## 🛠️ Affected Areas / Files

- `app/flagging.py` (new or refactor)
- `app/density_report.py` (read from `summarize_flags`)
- `app/artifact_exporter.py` or equivalent (serialize SSOT to `flags.json`, `segment_metrics.json`)
- Remove duplicate flagging from any exporter/template helpers.

---

## 🚦 Rollout / Migration

- **Release N:** produce canonical fields + aliases (`flagged_bin_count`, `seg_id`)
- **Release N+1:** remove aliases after FE has switched fully to canonical names.

---

## 🔁 Rollback

- If needed, revert to previous release tag. This change is low-risk if CI parity checks are in place.

---

## 📌 Definition of Done

- ✅ **Parity:** `Density.md` Executive Summary matches `flags.json` + `segment_metrics.json`.
- ✅ **Dashboard** shows same totals as the report (no zeros when flags exist).
- ✅ **CI parity gate** in place and passing.
- ✅ **No duplicate flagging logic** remains in the codebase.

---

## Related Issues

- Issue #280: Missing Density Features
- Issue #281: Data Dictionary
- Issue #282: UI/UX Polish

## Source

ChatGPT Technical Architecture Review (2025-10-20)

## Status

**Open** - Awaiting implementation

