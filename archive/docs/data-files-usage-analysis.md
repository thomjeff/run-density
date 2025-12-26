# Data Directory Files Usage Analysis

**Generated:** 2025-11-23  
**Purpose:** Identify unused files in `/data` directory that can be removed or archived

---

## Summary

**Total Files Analyzed:** 13  
**Actively Used:** 8  
**Potentially Unused:** 3  
**Output Files (Not Inputs):** 2

---

## ✅ ACTIVELY USED FILES

### Core Input Files

#### 1. `segments.csv` (9.5 KB)
**Status:** ✅ **CRITICAL - Heavily Used**  
**References Found:** 202+ code references

**Usage:**
- Primary segment definition file
- Used in density analysis, flow analysis, report generation
- Referenced in constants: `DEFAULT_SEGMENTS_CSV = "data/segments.csv"`
- Served via API endpoint: `/data/segments.csv`
- Used by all major modules:
  - `app/core/density/compute.py`
  - `app/core/flow/flow.py`
  - `app/density_report.py`
  - `app/flow_report.py`
  - `app/main.py`
  - `app/api/density.py`
  - Validation and E2E testing

**Action:** Keep - This is the canonical segment data source.

---

#### 2. `runners.csv` (63 KB)
**Status:** ✅ **CRITICAL - Heavily Used**  
**References Found:** 87+ code references

**Usage:**
- Primary runner pace data file
- Used in all analysis functions
- Referenced in constants: `DEFAULT_PACE_CSV = "data/runners.csv"`
- Served via API endpoint: `/data/runners.csv`
- Used by:
  - All density analysis modules
  - All flow analysis modules
  - Report generation
  - Dashboard API
  - E2E testing

**Action:** Keep - This is the primary input data file.

---

#### 3. `flow_expected_results.csv` (8.0 KB)
**Status:** ✅ **ACTIVELY USED - Testing/Oracle**  
**References Found:** 19 code references

**Usage:**
- Validation oracle for flow analysis (Issue #233)
- Used by `app/flow_validation.py`
- Served via API endpoint: `/data/flow_expected_results.csv`
- Referenced in documentation and testing
- Part of expected results validation workflow

**Action:** Keep - Required for flow algorithm validation.

---

#### 4. `flow_expected_results.data_dictionary.json` (8.7 KB)
**Status:** ✅ **REFERENCED - Documentation**  
**References Found:** Self-referenced in CSV

**Usage:**
- Descriptive documentation for `flow_expected_results.csv`
- Provides human-readable column definitions
- Not used for strict schema validation (descriptive only)

**Action:** Keep - Useful documentation, small file size.

---

### GPX Route Files

#### 5. `Full.gpx` (30 KB)
**Status:** ✅ **ACTIVELY USED**  
**References Found:** In `app/core/gpx/processor.py`

**Usage:**
- Used by GPX processor for full marathon route
- Referenced in: `app/core/gpx/processor.py` line 395
- Used for map generation and route geometry

**Action:** Keep - Required for full marathon route.

---

#### 6. `Half.gpx` (15 KB)
**Status:** ✅ **ACTIVELY USED**  
**References Found:** In `app/core/gpx/processor.py`

**Usage:**
- Used by GPX processor for half marathon route
- Referenced in: `app/core/gpx/processor.py` line 394
- Used for map generation and route geometry

**Action:** Keep - Required for half marathon route.

---

#### 7. `10K.gpx` (17 KB)
**Status:** ✅ **ACTIVELY USED**  
**References Found:** In `app/core/gpx/processor.py`

**Usage:**
- Used by GPX processor for 10K route
- Referenced in: `app/core/gpx/processor.py` line 393
- Used for map generation and route geometry

**Action:** Keep - Required for 10K route.

---

## ⚠️ OUTPUT FILES (Generated, Not Inputs)

These files are **generated outputs** from analysis runs (e2e-local), not input files. They appear in `/data` but are actually generated to `runflow/<uuid>/ui/` or `cursor/chats/<run_id>/ui/` directories during E2E runs.

### 8. `meta.json` (305 B)
**Status:** ✅ **GENERATED OUTPUT - Legacy/Example in /data**  
**References Found:** 21 references (all as OUTPUT)

**Usage:**
- Generated during E2E runs (`make e2e-local`)
- Stored in `runflow/<uuid>/ui/meta.json` or `cursor/chats/<run_id>/ui/meta.json`
- Contains run metadata (timestamp, environment, validation status)
- Example: `cursor/chats/23KbwK3cCpqPX8iUjkeKJ9/ui/meta.json` (latest E2E run)

**Action:** ✅ **CONFIRMED - Remove from `/data`** - This is a legacy/example file. Actual outputs are generated during E2E runs.

---

### 9. `flags.json` (4.1 KB)
**Status:** ✅ **GENERATED OUTPUT - Legacy/Example in /data**  
**References Found:** 34 references (all as OUTPUT)

**Usage:**
- Generated during E2E runs (`make e2e-local`)
- Stored in `runflow/<uuid>/ui/flags.json` or `cursor/chats/<run_id>/ui/flags.json`
- Contains flagged segments and bins data
- Example: `cursor/chats/23KbwK3cCpqPX8iUjkeKJ9/ui/flags.json` (latest E2E run)

**Action:** ✅ **CONFIRMED - Remove from `/data`** - This is a legacy/example file. Actual outputs are generated during E2E runs.

---

### 10. `segment_metrics.json` (2.4 KB)
**Status:** ✅ **GENERATED OUTPUT - Legacy/Example in /data**  
**References Found:** 43 references (all as OUTPUT)

**Usage:**
- Generated during E2E runs (`make e2e-local`)
- Stored in `runflow/<uuid>/ui/segment_metrics.json` or `cursor/chats/<run_id>/ui/segment_metrics.json`
- Contains segment-level metrics
- Example: `cursor/chats/23KbwK3cCpqPX8iUjkeKJ9/ui/segment_metrics.json` (latest E2E run)

**Action:** ✅ **CONFIRMED - Remove from `/data`** - This is a legacy/example file. Actual outputs are generated during E2E runs.

---

## ❌ POTENTIALLY UNUSED FILES

### 11. `calc_startOffsets_out.csv` (92 KB)
**Status:** ❌ **NO REFERENCES FOUND**  
**References Found:** 0

**Usage:**
- No code references found
- Not used in any analysis modules
- Not referenced in documentation
- Not served via API endpoints

**Action:** **CANDIDATE FOR REMOVAL** - Appears to be intermediate calculation output that's no longer needed. Largest unused file (92 KB).

---

### 12. `5K.gpx` (5.1 KB)
**Status:** ❌ **NOT REFERENCED**  
**References Found:** 0

**Usage:**
- Not referenced in `app/core/gpx/processor.py`
- Only `Full.gpx`, `Half.gpx`, and `10K.gpx` are loaded
- No 5K event analysis in codebase

**Action:** **CANDIDATE FOR REMOVAL** - 5K route file not used. Only Full, Half, and 10K events are processed.

---

### 13. `flow.csv` (6.9 KB)
**Status:** ⚠️ **MINIMAL USAGE - Possible Bug**  
**References Found:** 2 references

**Usage:**
- Referenced in `app/api/density.py` line 230 (looks like a bug - should be `segments.csv`)
- Referenced in CHANGELOG.md (historical reference)

**File Structure:**
- Contains event pairs (eventA, eventB) format
- Different structure than `segments.csv` (flow-specific format)
- Has columns: `seg_id`, `eventA`, `eventB`, `from_km_A`, `to_km_B`, etc.

**Analysis:**
- Line 230 in `app/api/density.py` loads `data/flow.csv` but should probably load `data/segments.csv`
- This looks like a bug - density analysis should use segments.csv, not flow.csv
- File might be legacy from old flow analysis approach

**Action:** **INVESTIGATE** - Review `app/api/density.py:230` to determine if this is a bug. If bug, fix and remove `data/flow.csv`. If intentional, document why density analysis uses flow.csv.

---

## 📊 Usage Summary Table

| File | Size | Status | References | Action |
|------|------|--------|------------|--------|
| `segments.csv` | 9.5 KB | ✅ Critical | 202+ | **Keep** |
| `runners.csv` | 63 KB | ✅ Critical | 87+ | **Keep** |
| `flow_expected_results.csv` | 8.0 KB | ✅ Active | 19 | **Keep** |
| `flow_expected_results.data_dictionary.json` | 8.7 KB | ✅ Referenced | Self-ref | **Keep** |
| `Full.gpx` | 30 KB | ✅ Active | 1 | **Keep** |
| `Half.gpx` | 15 KB | ✅ Active | 1 | **Keep** |
| `10K.gpx` | 17 KB | ✅ Active | 1 | **Keep** |
| `meta.json` | 305 B | ✅ Generated | 21 (output) | **Remove** - Legacy/example |
| `flags.json` | 4.1 KB | ✅ Generated | 34 (output) | **Remove** - Legacy/example |
| `segment_metrics.json` | 2.4 KB | ✅ Generated | 43 (output) | **Remove** - Legacy/example |
| `calc_startOffsets_out.csv` | 92 KB | ❌ Unused | 0 | **Remove** |
| `5K.gpx` | 5.1 KB | ❌ Unused | 0 | **Remove** |
| `flow.csv` | 6.9 KB | ⚠️ Bug? | 2 | **Investigate** |

---

## 🔍 Files to Investigate Further

### 1. `app/api/density.py` Line 230

**Current Code:**
```python
segments_df = pd.read_csv('data/flow.csv')
```

**Issue:** This loads `flow.csv` but should probably load `segments.csv` for density analysis.

**Recommendation:** 
1. Review this code section to understand intent
2. Check if `flow.csv` format is actually needed for this endpoint
3. If bug, fix to use `segments.csv`
4. If intentional, document why

---

## 📋 Recommended Actions

### Immediate Actions

1. **Remove Unused Files:**
   - ❌ `calc_startOffsets_out.csv` (92 KB) - No references
   - ❌ `5K.gpx` (5.1 KB) - Not used, no 5K event processing

2. **Remove Legacy Output Files from `/data`:**
   - ✅ `meta.json` - **CONFIRMED**: Generated during E2E runs, remove legacy version
   - ✅ `flags.json` - **CONFIRMED**: Generated during E2E runs, remove legacy version
   - ✅ `segment_metrics.json` - **CONFIRMED**: Generated during E2E runs, remove legacy version
   
   **Note:** These files are automatically generated to `runflow/<uuid>/ui/` or `cursor/chats/<run_id>/ui/` during `make e2e-local` runs. The versions in `/data` are legacy/example files that are not used by the application.

3. **Investigate `flow.csv` Usage:**
   - Review `app/api/density.py:230`
   - Determine if this is a bug or intentional
   - If bug, fix and remove file
   - If intentional, document usage

### Potential Space Savings

- `calc_startOffsets_out.csv`: 92 KB
- `5K.gpx`: 5.1 KB
- `meta.json`: 305 B
- `flags.json`: 4.1 KB
- `segment_metrics.json`: 2.4 KB
- `flow.csv`: 6.9 KB (if removed after investigation)

**Total Potential Savings:** ~111 KB

---

## 🔄 Files Mentioned But Not in `/data`

### `segments.geojson`
**Status:** ✅ **USED - But as OUTPUT**  
**References Found:** 297+ references

**Note:** User mentioned `segments.geojson` might not be used. However, this file is:
- **NOT** an input file in `/data`
- **GENERATED** as output in `runflow/<uuid>/ui/segments.geojson`
- Heavily used by UI and map generation

**Action:** This file is correctly placed as output, not input. No action needed for `/data` directory.

---

## 📝 Notes

1. **Output Files in `/data`:** ✅ **CONFIRMED** - The files `meta.json`, `flags.json`, and `segment_metrics.json` in `/data` are legacy/example files. The actual outputs are automatically generated during E2E runs (`make e2e-local`) and stored in:
   - `runflow/<uuid>/ui/` (runtime outputs)
   - `cursor/chats/<run_id>/ui/` (E2E test outputs)
   
   These can be safely removed from `/data` as they are not used as input files by the application.

2. **GPX Files:** Only Full, Half, and 10K routes are processed. The 5K.gpx file is not referenced and can be removed.

3. **File Naming:** Be careful with `flow.csv` vs `Flow.csv`:
   - `data/flow.csv` - Input file (potentially unused)
   - `runflow/<uuid>/reports/Flow.csv` - Output file (actively used)

---

## ✅ Conclusion

**Files Safe to Remove:**
1. `calc_startOffsets_out.csv` - No references (92 KB)
2. `5K.gpx` - Not used (5.1 KB)
3. `meta.json` - Output file, not input (305 B)
4. `flags.json` - Output file, not input (4.1 KB)
5. `segment_metrics.json` - Output file, not input (2.4 KB)

**Files Requiring Investigation:**
1. `flow.csv` - Only 2 references, one appears to be a bug in `app/api/density.py:230`

**Total Potential Cleanup:** ~111 KB of unused/legacy files

---

---

## ✅ ACTIONS TAKEN (2025-11-23)

### Files Archived to `archive/data/`:
1. ✅ `calc_startOffsets_out.csv` (92 KB) - Moved
2. ✅ `meta.json` (305 B) - Moved  
3. ✅ `flags.json` (4.1 KB) - Moved
4. ✅ `segment_metrics.json` (2.4 KB) - Moved

**Total Archived:** ~99 KB

### Files Kept (As Requested):
- ✅ `5K.gpx` - Reserved for future 5K map feature
- ✅ `flow.csv` - Used in flow analysis (event pairs format), not density analysis

**Note:** `flow.csv` is used by flow analysis modules, not density analysis. The reference in `app/api/density.py:230` may still need review, but `flow.csv` itself is a valid input file for flow analysis.

---

**Report Generated:** 2025-11-23  
**Analysis Method:** Grep search for file references across entire codebase  
**Actions Completed:** Files archived to `archive/data/`
