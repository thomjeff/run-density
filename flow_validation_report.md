# Flow Report Validation Results

**Generated:** 2025-10-28 18:51:59

## Summary

❌ **VALIDATION FAILED** - Differences detected

## Markdown Report Validation

- **Files Match:** ❌ No
- **Metrics Match:** ✅ Yes
- **Total Differences:** 17

### Baseline Metrics
- total_segments: 29
- convergence_segments: 23
- convergence_rate: 79.3
- flow_types: {}

### Refactored Metrics
- total_segments: 29
- convergence_segments: 23
- convergence_rate: 79.3
- flow_types: {}

## CSV Report Validation

- **Files Match:** ❌ No
- **Shape Match:** ✅ Yes
- **Columns Match:** ✅ Yes
- **Total Differences:** 2

### Differences Found
- Column: sample_a
  - Different rows: [5, 8, 10, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 24, 26, 27, 28]
  - Baseline values: ['1621, 1623, 1629, ... (10 total)', '1621, 1655, 1667, ... (10 total)', '2538, 2539, 2560, ... (10 total)', '2531, 2546, 2549, ... (10 total)', '2549, 2560, 2567, ... (10 total)', '1701, 1740, 2011, ... (10 total)', '2661, 2711, 2807, ... (10 total)', '2538, 2539, 2560, ... (10 total)', '2531, 2539, 2546, ... (10 total)', '2539, 2549, 2560, ... (10 total)', '2539, 2549, 2560, ... (10 total)', '2531, 2540, 2555, ... (10 total)', '2549, 2560, 2567, ... (10 total)', '2539, 2549, 2567, ... (10 total)', '2802, 2814, 2821, ... (10 total)', '2538, 2539, 2549, ... (10 total)', '1628, 1631, 1633, ... (10 total)']
  - Refactored values: ['1618, 1630, 1631, ... (10 total)', '1642, 1648, 1664, ... (10 total)', '2540, 2557, 2568, ... (10 total)', '2535, 2540, 2543, ... (10 total)', '2540, 2557, 2568, ... (10 total)', '1669, 1670, 1711, ... (10 total)', '2724, 2762, 2767, ... (10 total)', '2540, 2557, 2568, ... (10 total)', '2535, 2540, 2553, ... (10 total)', '2540, 2557, 2568, ... (10 total)', '2540, 2557, 2568, ... (10 total)', '2540, 2553, 2556, ... (10 total)', '2540, 2557, 2575, ... (10 total)', '2540, 2557, 2575, ... (10 total)', '2775, 2795, 2813, ... (10 total)', '2540, 2557, 2614, ... (10 total)', '1631, 1632, 1633, ... (10 total)']

- Column: sample_b
  - Different rows: [8, 9, 10, 12, 13, 14, 15, 16, 19, 20, 21, 22, 24, 26, 27, 28]
  - Baseline values: ['1529, 1607, 1608, ... (10 total)', '1000, 1003, 1005, ... (10 total)', '1567, 1575, 1581, ... (10 total)', '2488, 2489, 2500, ... (10 total)', '1517, 1520, 1538, ... (10 total)', '1078, 1103, 1129, ... (10 total)', '1621, 1701, 1740, ... (10 total)', '1538, 1544, 1567, ... (10 total)', '2328, 2329, 2355, ... (10 total)', '2355, 2394, 2414, ... (10 total)', '2505, 2509, 2510, ... (10 total)', '2274, 2293, 2294, ... (10 total)', '1447, 1520, 1538, ... (10 total)', '1655, 1681, 1701, ... (10 total)', '1329, 1402, 1421, ... (10 total)', '1598, 1603, 1604, ... (10 total)']
  - Refactored values: ['1529, 1606, 1607, ... (10 total)', '1001, 1003, 1004, ... (10 total)', '1529, 1571, 1576, ... (10 total)', '2478, 2490, 2494, ... (10 total)', '1493, 1513, 1514, ... (10 total)', '1155, 1215, 1220, ... (10 total)', '1711, 1759, 1812, ... (10 total)', '1529, 1545, 1550, ... (10 total)', '2314, 2348, 2354, ... (10 total)', '2348, 2354, 2372, ... (10 total)', '2509, 2511, 2512, ... (10 total)', '2314, 2348, 2354, ... (10 total)', '1420, 1433, 1458, ... (10 total)', '1664, 1670, 1764, ... (10 total)', '1420, 1433, 1443, ... (10 total)', '1598, 1602, 1603, ... (10 total)']

## Recommendations

⚠️ **Review required before proceeding**
- Investigate differences found
- Ensure refactoring maintains exact behavior
- Consider rollback if differences are significant
