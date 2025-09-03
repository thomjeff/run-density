# F* Segments Validation Report
**Date:** September 3, 2025  
**Analysis Period:** F1, F2, F3  
**Algorithm Version:** Temporal Flow Analysis v1.5.0  
**Critical Discovery:** Shared path merge analysis and runner overlap patterns

## Executive Summary

This report documents the validation of the F* segment series, which revealed critical insights about shared path merge scenarios, runner overlap patterns between segments, and the impact of start time gaps on interaction rates. The analysis confirmed the algorithm's ability to handle complex merge scenarios while uncovering important patterns in runner flow between consecutive segments.

## Test Environment

### Overtake Percentage Classification
- **Significant:** >20% - enough to warrant race organizer attention
- **Meaningful:** >15% - indicates real interaction patterns  
- **Notable:** >5% - worth planning for in race management

### Segment Configuration
- **F1:** 10K vs Half Marathon (shared path merge)
- **F2:** 10K vs Full Marathon (shared path merge)
- **F3:** Half vs Full Marathon (shared path merge)

### Start Times
- **Full Marathon:** 7:00 AM (420 minutes)
- **10K:** 7:20 AM (440 minutes)
- **Half Marathon:** 7:40 AM (460 minutes)

### Algorithm Parameters
- **Conflict Length:** 100m around convergence point
- **Minimum Overlap Duration:** 5 seconds
- **Tolerance for Convergence Detection:** 5 seconds

## Key Findings

### 1. F1 Analysis: Massive Merge Scenario

**Segment Details:**
- **Events:** 10K vs Half Marathon
- **Range A (10K):** 5.8km to 8.1km (returning from 10K Turn)
- **Range B (Half):** 2.7km to 5.0km (outbound to Station Rd)
- **Flow Type:** merge
- **Direction:** unidirectional (same direction)

**Results:**
- ✅ **Convergence Point:** 5.8km (start of segment)
- ✅ **Total Interactions:** 1,398 overtakes
- ✅ **Percentage Overtake:** 78.8% 10K (Significant), 99.9% Half (Significant)

**Key Insights:**
- **131 10K runners NOT included:** Fastest 10K runners exit F1 before any Half runners enter
- **1 Half runner NOT included:** Runner 2529 (pace 12.68 min/km, 108s start offset)
- **Runner 1529:** Not included because enters F1 after all Half runners have exited
- **Overlap window:** 26 minutes of temporal convergence

### 2. F2 Analysis: Moderate Cross-Event Interactions

**Segment Details:**
- **Events:** 10K vs Full Marathon
- **Range A (10K):** 5.8km to 8.1km (returning from 10K Turn)
- **Range B (Full):** 16.35km to 18.65km (outbound to Station Rd)
- **Flow Type:** merge
- **Direction:** unidirectional (same direction)

**Results:**
- ✅ **Convergence Point:** 5.8km (start of segment)
- ✅ **Total Interactions:** 236 overtakes
- ✅ **Percentage Overtake:** 17.8% 10K (Meaningful), 34.2% Full (Significant)

**Key Insights:**
- **508 10K runners NOT included:** Fastest 10K runners exit F2 before any Full runners enter
- **242 Full runners NOT included:** Slowest Full runners enter F2 after all 10K runners exit
- **Overlap window:** 53.9 minutes of temporal convergence
- **C1 vs F2 overlap:** 70.1% of C1 Full runners (54 out of 77) appear in F2

### 3. F3 Analysis: Low Interaction Merge

**Segment Details:**
- **Events:** Half vs Full Marathon
- **Range A (Half):** 2.7km to 5.0km (outbound to Station Rd)
- **Range B (Full):** 16.35km to 18.65km (outbound to Station Rd)
- **Flow Type:** merge
- **Direction:** unidirectional (same direction)

**Results:**
- ✅ **Convergence Point:** 2.7km (start of segment)
- ✅ **Total Interactions:** 73 overtakes
- ✅ **Percentage Overtake:** 4.6% Half (Notable), 8.4% Full (Notable)

**Key Insights:**
- **870 Half runners NOT included:** Fastest Half runners exit F3 before any Full runners enter
- **337 Full runners NOT included:** Slowest Full runners enter F3 after all Half runners exit
- **Overlap window:** 40.9 minutes of temporal convergence
- **F2 vs F3 overlap:** 74.2% of F3 Full runners (23 out of 31) also appear in F2

## Technical Insights

### 1. Start Time Gap Impact on Interaction Rates
**Finding:** Start time gaps significantly impact interaction rates in merge scenarios.

**Pattern Analysis:**
- **F1 (10K vs Half, 20min gap):** 78.8% 10K, 99.9% Half (Significant)
- **F2 (10K vs Full, 20min gap):** 17.8% 10K, 34.2% Full (Meaningful/Significant)
- **F3 (Half vs Full, 40min gap):** 4.6% Half, 8.4% Full (Notable)

**Insight:** Larger start time gaps result in lower interaction rates due to reduced temporal overlap windows.

### 2. Runner Overlap Patterns Between Segments
**Finding:** Consecutive segments show significant runner overlap patterns.

**F2 vs F3 Analysis:**
- **F3 Full runners:** 31 total
- **F2 Full runners:** 126 total
- **Overlap:** 23 runners (74.2% of F3 Full runners)
- **F3 unique:** 8 runners
- **F2 unique:** 103 runners

**Insight:** Most F3 Full runners are also in F2, confirming segment continuation patterns.

### 3. Algorithm Precision in Merge Scenarios
**Finding:** The algorithm correctly identifies temporal overlaps in complex merge scenarios.

**Validation Examples:**
- **Runner 1529:** Correctly excluded from F1 (enters after all Half runners exit)
- **Runner 2529:** Correctly excluded from F1 (extreme start offset)
- **Fast runners:** Correctly excluded when they exit before slower runners enter

**Insight:** Algorithm maintains precision in complex temporal scenarios.

### 4. Convergence Point Patterns
**Finding:** All F* segments converge at the start of their respective segments.

**Pattern:**
- **F1:** Convergence at 5.8km (start of 5.8-8.1km segment)
- **F2:** Convergence at 5.8km (start of 5.8-8.1km segment)
- **F3:** Convergence at 2.7km (start of 2.7-5.0km segment)

**Insight:** Merge scenarios tend to converge at segment boundaries where different event flows meet.

## Race Organizer Implications

### 1. Merge Scenario Management
- **High interaction rates** in F1 (99.9% Half involvement) require significant course management
- **Start time gaps** can be used to control interaction rates in merge scenarios
- **Temporal overlap windows** provide planning timeframes for course management

### 2. Runner Flow Patterns
- **Segment continuation** patterns (F2→F3) show consistent runner populations
- **Fast runner exclusion** patterns help identify course management priorities
- **Start offset impacts** create unexpected but legitimate interaction scenarios

### 3. Course Planning Insights
- **Merge points** at segment boundaries require special attention
- **Interaction rates** vary significantly based on start time gaps
- **Temporal windows** provide specific timeframes for course management

## Recommendations

### 1. Algorithm Validation
- ✅ Continue supporting merge scenario analysis
- ✅ Maintain precision in temporal overlap detection
- ✅ Preserve runner exclusion logic for fast runners

### 2. Course Management
- **F1 segment:** Requires significant attention due to 99.9% Half involvement
- **F2 segment:** Moderate attention needed for 34.2% Full involvement
- **F3 segment:** Minimal attention needed for 8.4% Full involvement

### 3. Start Time Optimization
- **20-minute gaps** create moderate to high interaction rates
- **40-minute gaps** create low interaction rates
- **Start offset monitoring** is critical for accurate planning

## Conclusion

The F* segment validation successfully confirmed the algorithm's ability to handle complex merge scenarios. Key insights include:

1. **Merge Scenario Success:** Algorithm correctly analyzes shared path merge scenarios with different event combinations
2. **Start Time Gap Impact:** Larger gaps result in lower interaction rates, providing course management control
3. **Runner Overlap Patterns:** Consecutive segments show significant runner overlap, confirming flow patterns
4. **Algorithm Precision:** Maintains accuracy in complex temporal scenarios with proper exclusion logic

The algorithm is performing as designed and provides the precision required for effective race planning in complex merge scenarios.

---

**Report Generated:** September 3, 2025  
**Algorithm Version:** Temporal Flow Analysis v1.5.0  
**Validation Status:** ✅ PASSED  
**Next Phase:** Continue with additional segment testing
