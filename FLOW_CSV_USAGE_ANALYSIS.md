# flow.csv Usage Analysis

## 📊 **What is flow.csv?**

`data/flow.csv` is the **temporal flow analysis configuration file** that defines:
- Segment boundaries for each event pair (eventA, eventB)
- Course width (`width_m`) for each segment
- Flow types (merge, overtake, uni-directional, bi-directional)
- Convergence/overlap zones between events

**Note:** This file was previously named `segments.csv` and was renamed to `flow.csv` in v1.6.7 to better reflect its purpose.

---

## 🔧 **Where flow.csv is Used:**

### **1. Temporal Flow Analysis (`app/flow.py`)**
**Purpose:** Analyze runner convergence, overtakes, and flow between event pairs

**Usage:**
- Loads segment definitions for event pairs (10K/Half, 10K/Full, Half/Full)
- Uses `width_m` to calculate flow rates (runners per minute per meter)
- Determines convergence zones where events overlap
- Calculates overtaking opportunities

**Key Function:** `analyze_temporal_flow_segments(pace_csv, segments_csv='data/flow.csv', start_times)`

---

### **2. Density Analysis (`app/density.py`)**
**Purpose:** Get course width for density calculations

**Usage:**
- **StaticWidthProvider class** reads `width_m` from flow.csv
- Used to calculate areal density (runners/m²) = linear density / width
- Formula: `areal_density = (runners / segment_length_m) / width_m`

**Key Class:** `StaticWidthProvider(segments_df)` where segments_df is loaded from flow.csv

**Important:** Density analysis uses `segments.csv` (not flow.csv) for segment boundaries, but uses flow.csv for width values.

---

### **3. Test Suites**
**Files:**
- `tests/temporal_flow_tests.py` - Flow analysis validation
- `tests/density_tests.py` - Density analysis validation

**Usage:** Load flow.csv to run tests against expected results

---

## 📋 **flow.csv vs. segments.csv**

### **Confusion Point:**
There are TWO different CSV files with similar purposes:

| File | Purpose | Used By | Key Fields |
|------|---------|---------|------------|
| **data/flow.csv** | Temporal flow config (event pairs) | Flow analysis, Width provider | seg_id, eventA, eventB, from_km_A, to_km_A, from_km_B, to_km_B, width_m, flow-type |
| **data/segments.csv** | Density config (single events) | Density analysis | seg_id, seg_label, full_from_km, full_to_km, half_from_km, half_to_km, 10K_from_km, 10K_to_km, width_m, schema_name |

### **Key Difference:**
- **flow.csv:** Event PAIRS (A vs B) - for convergence/overlap analysis
- **segments.csv:** Single EVENTS - for density analysis per event

---

## 🎯 **Why This Matters for Issue #237:**

### **Current Situation:**
1. **Density analysis** uses `segments.csv` for segment boundaries
2. **Density analysis** can use `flow.csv` for width values (via StaticWidthProvider)
3. **Flow analysis** uses `flow.csv` exclusively

### **For Operational Intelligence:**
- **bins.parquet** is generated from density analysis (uses `segments.csv`)
- **tooltips.json** is generated from bins.parquet
- **flow.csv** is NOT directly used for operational intelligence

### **Potential Issue:**
The mockup shows "Flow Utilization: 308.5%" which suggests we need flow data, but:
- Current operational intelligence only has density data
- Flow utilization would require integrating flow analysis results
- This might be why the mockup shows different data than we're generating

---

## 🔍 **Data Flow Diagram:**

```
Input Files:
├── data/runners.csv (pace data)
├── data/segments.csv (density config) → Density Analysis → bins.parquet → tooltips.json
└── data/flow.csv (flow config) → Flow Analysis → Flow.csv report

Current:
- Operational Intelligence uses DENSITY data only
- Flow data is separate (Flow.csv report)

Mockup Expectation:
- Operational Intelligence shows BOTH density AND flow utilization
- Suggests integration of flow analysis into operational intelligence
```

---

## 💡 **Key Insight:**

**The mockup shows "Flow Utilization: 308.5%"** which is data from **Flow analysis**, not Density analysis.

**Current implementation:**
- Operational intelligence (tooltips.json) only has density data
- Flow data is in separate Flow.csv report
- These are NOT integrated

**To match the mockup, we would need to:**
1. Run flow analysis for each bin/segment
2. Add flow utilization to tooltips.json
3. Include flow utilization in operational intelligence reports

**This explains the gap between mockup and current implementation!**

---

## 🎯 **Questions for Clarification:**

1. **Should operational intelligence include flow utilization data?**
   - Current: Density only (LOS, density values)
   - Mockup: Density + Flow utilization

2. **How to integrate flow and density data?**
   - Option A: Run flow analysis per bin and merge with density
   - Option B: Keep separate, reference flow report from density report
   - Option C: Create unified analysis that computes both

3. **Is the F1 segment (308.5% utilization) example in mockup real data?**
   - Current data shows F1 with LOS=A, low density
   - Mockup shows high utilization
   - Need to understand if this is expected or example data

---

**This analysis suggests we need to clarify the integration between Flow and Density data before proceeding with Issue #237.**

