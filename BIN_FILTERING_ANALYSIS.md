# Bin Filtering Analysis: Density Report vs UI

## 🔍 **The Discrepancy**

**Density Report (2025-10-23-1555-Density.md)**: Shows **37 bins** for A1
**UI (/bins page)**: Shows **~400 bins** for A1

## 🎯 **Root Cause: Operational Intelligence Filtering**

The Density report applies **operational intelligence flagging** that filters bins based on operational significance, while the UI shows **all bins** from the dataset.

### 📋 **Filtering Logic in Density Report**

The Density report only includes bins that meet **operational intelligence criteria**:

#### 1. **Minimum Bin Length Filter**
```yaml
require_min_bin_len_m: 10.0  # Only bins >= 10 meters long
```

#### 2. **LOS Threshold Filter**
```yaml
min_los_flag: "C"  # Only bins with LOS >= C (≥ 0.54 p/m²)
```

#### 3. **Utilization Percentile Filter**
```yaml
utilization_pctile: 95  # Only bins in top 5% utilization globally
```

#### 4. **Combined Flagging Logic**
A bin is included in the report if it meets **ANY** of these criteria:
- **LOS_HIGH**: Density ≥ 0.54 p/m² (LOS C or worse)
- **UTILIZATION_HIGH**: Density in top 5% globally
- **BOTH**: Both conditions met (highest priority)

### 🏷️ **Severity Classification**
- **CRITICAL**: Both LOS ≥ C AND top 5% utilization
- **CAUTION**: LOS ≥ C only  
- **WATCH**: Top 5% utilization only
- **NONE**: Neither condition met (excluded from report)

## 📊 **Why A1 Shows 37 vs 400 Bins**

### **A1 Segment Characteristics**
- **Total Bins**: ~400 bins (0.0-0.9 km, 2-minute time windows)
- **Bin Length**: Most bins are 200m long (well above 10m minimum)
- **Density Range**: 0.001-0.749 p/m² (mostly LOS A, some LOS B)

### **Filtering Results**
- **37 bins flagged**: Only bins with density ≥ 0.54 p/m² (LOS C+) OR in top 5% utilization
- **363 bins excluded**: Bins with density < 0.54 p/m² (LOS A/B) and not in top 5%

### **Example from Report**
Looking at the A1 data in the report:
- **07:00-07:02**: 0.353 p/m² (LOS A) - **EXCLUDED** (below 0.54 threshold)
- **07:20-07:22**: 0.749 p/m² (LOS B) - **INCLUDED** (top 5% utilization)
- **07:40-07:42**: 0.749 p/m² (LOS B) - **INCLUDED** (top 5% utilization)

## 🎯 **Design Rationale**

### **Density Report Purpose**
- **Operational Intelligence**: Focus on bins requiring attention
- **Actionable Insights**: Only show bins that need monitoring/mitigation
- **Reduced Noise**: Filter out low-density, non-problematic bins

### **UI Purpose**  
- **Complete Dataset**: Show all available data for analysis
- **User Exploration**: Allow users to see full density patterns
- **Research/Analysis**: Enable detailed investigation of all bins

## 🔧 **Technical Implementation**

### **Report Generation** (`app/density_report.py:1318-1366`)
```python
# Get only flagged bins
from .bin_intelligence import get_flagged_bins
flagged = get_flagged_bins(bins_flagged)

# Only include bins with operational significance
if len(flagged) > 0:
    content.append("### Bin-Level Detail (Flagged Segments Only)")
```

### **UI Generation** (`app/routes/api_bins.py`)
```python
# Return ALL bins from bins.parquet (no filtering)
bins_data = load_bins_data()  # All 19,440 bins
```

## 📈 **Summary**

| Aspect | Density Report | UI (/bins) |
|--------|----------------|------------|
| **Purpose** | Operational Intelligence | Complete Dataset |
| **Filtering** | LOS ≥ C OR Top 5% Util | None (all bins) |
| **A1 Bins** | 37 (flagged only) | ~400 (all bins) |
| **Use Case** | Action Planning | Data Exploration |
| **Audience** | Operations Team | Analysts/Researchers |

## 🎯 **Conclusion**

The discrepancy is **intentional and correct**:
- **Density Report**: Shows only operationally significant bins (37 for A1)
- **UI**: Shows complete dataset for analysis (400 for A1)

Both serve different purposes and are working as designed. The filtering logic ensures the Density report focuses on actionable insights while the UI provides complete data access.
