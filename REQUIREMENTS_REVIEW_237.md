# Requirements Review: Issue #233 & #237

## 📊 **Current State Analysis**

### **Data Files Available:**
1. **bins.parquet** (8,800 rows) - Bin-level spatial data
   - Columns: bin_id, segment_id, start_km, end_km, t_start, t_end, density, flow, los_class, bin_size_km, schema_version, analysis_hash
   - Readable version: `reports/2025-10-15/bins_readable.csv`

2. **segment_windows_from_bins.parquet** (1,760 rows) - Segment-level temporal data
   - Columns: segment_id, t_start, t_end, density_mean, density_peak, n_bins
   - Readable version: `reports/2025-10-15/segment_windows_readable.csv`

3. **tooltips.json** (445 entries) - Flagged bins with operational intelligence
   - Fields: segment_id, start_km, end_km, density_peak, los, los_description, los_color, severity, flag_reason, t_start, t_end

---

## 📋 **Mockup vs. Current Implementation**

### **Density.md Report:**

#### **Mockup Structure:**
```
1. Key Metrics Summary
   - Peak Areal Density: 0.75 p/m² (LOS=D)
   - Peak Flow Utilization: 308.5%
   - Segments with ≥1 flagged bin: 4/12
   - Total Flagged Bins: 9/60

2. Executive Summary Table (FLAGGED SEGMENTS ONLY)
   | Segment | Location | Worst Bin | Density | Util% | LOS | Flag Reason |
   | F1 | Friel → Station | 1200-1400 | 0.03 | 308% | A | Util>100% |
   | H2 | Gibson Trail | 600-800 | 0.84 | 95% | D | LOS ≥ C |
   | N3 | Marysville | 400-600 | 1.10 | 87% | E | LOS ≥ C |

3. Per-Segment Detailed Sections (existing)

4. Appendix — Flagged Segments Only
   ### Segment F1 (Friel → Station Rd.)
   Worst Bin (1200-1400m):
   - Density: 0.03 p/m²
   - Flow Utilization: 308.5%
   - LOS: A (On Course Narrow)
   [Map Snippet Placeholder]
```

#### **Current Implementation:**
```
1. ❌ No Key Metrics Summary at top
2. Executive Summary Table (ALL SEGMENTS)
   | Segment | Label | Key Takeaway | LOS |
   - Shows all 22 segments, not just flagged ones
   - Missing: Worst Bin, Density, Util%, Flag Reason columns
3. ✅ Per-Segment Detailed Sections (existing)
4. ❌ No Appendix with bin-level detail
```

---

### **Map UI:**

#### **Expected (from Issue #233 snippet):**
- Bin-level detail panel/sidebar showing:
  - Bin range (start_km - end_km)
  - Density value
  - LOS classification
  - Severity badge
  - Time window
- Ability to click bins and see full details
- Flagged bins highlighted/filtered

#### **Current Implementation:**
- ✅ Bins rendered with LOS colors
- ✅ Tooltips show basic info + operational intelligence
- ❌ No bin-level detail panel/sidebar
- ❌ No filtering for flagged bins only

---

### **Dashboard:**

#### **Expected:**
- Not explicitly specified in Issue #233
- Issue #237 mentions "operational intelligence summary widget"

#### **Current Implementation:**
- ✅ Operational intelligence widget added (PR #241)
- ⚠️ "Canonical segments: 80 windows" - This comes from backend API, not hardcoded
  - Source: `notes: [f"Canonical segments: {peak_data['total_windows']} windows"]` in `/api/segments`
  - This is dynamic data, but the message format could be improved

---

## 🎯 **Key Gaps Identified:**

### **Report (Density.md):**
1. ❌ Missing Key Metrics summary at top
2. ❌ Executive Summary shows ALL segments, should show FLAGGED only
3. ❌ Missing columns: Worst Bin, Util%, Flag Reason
4. ❌ Missing Appendix with bin-level detail for flagged segments

### **Map UI:**
1. ❌ Missing bin-level detail panel/sidebar
2. ❌ No filtering for flagged bins
3. ❌ No map snippets for flagged segments

### **Dashboard:**
1. ⚠️ "Canonical segments: 80 windows" message could be clearer
2. ✅ Operational intelligence widget is good

---

## 💡 **Recommended Next Steps:**

### **Option A: Fix Report Structure First (Recommended)**
1. Update `app/density_report.py` to match mockup:
   - Add Key Metrics summary at top
   - Change Executive Summary to show FLAGGED segments only
   - Add missing columns (Worst Bin, Util%, Flag Reason)
   - Add Appendix with bin-level detail for flagged segments
2. Test report generation
3. Then update frontend to consume corrected structure

### **Option B: Update Issues #233 and #237**
1. Review and update Issue #233 with clearer report structure requirements
2. Update Issue #237 with specific map UI requirements (bin detail panel)
3. Close PR #241 and reimplement with correct requirements

### **Option C: Incremental Approach**
1. Keep PR #241 as Phase 1 (basic integration)
2. Create new issues for:
   - Issue #XXX: Fix Density.md report structure to match mockup
   - Issue #XXX: Add bin-level detail panel to map UI
   - Issue #XXX: Add map snippets for flagged segments

---

## 📁 **Files for Review:**

I've created readable versions of the parquet files:
- `reports/2025-10-15/bins_readable.csv` (8,800 rows)
- `reports/2025-10-15/segment_windows_readable.csv` (1,760 rows)

You can also review:
- Current Density.md: `reports/2025-10-15/2025-10-15-1408-Density.md`
- Current Flow.csv: `reports/2025-10-15/2025-10-15-1407-Flow.csv`
- tooltips.json: `reports/2025-10-15/tooltips.json`

---

**What would you like to do next?**

