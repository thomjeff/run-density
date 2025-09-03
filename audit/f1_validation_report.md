# F1 Segment Validation Report
**Generated**: 2025-09-02 21:15

## Segment Overview
- **Segment ID**: F1
- **Label**: Friel to Station Rd. (shared path)
- **Event A**: 10K (618 runners)
- **Event B**: Half (912 runners)
- **Range A**: 5.81km to 8.10km (10K course)
- **Range B**: 2.70km to 4.95km (Half course)
- **Start Times**: 10K=7:20 AM (440 min), Half=7:40 AM (460 min)

## Algorithm Results
- **Convergence Point**: 6.98km (10K ruler) = 3.85km (Half ruler)
- **Convergence Zone**: 6.98km to 8.10km (10K) = 3.85km to 4.95km (Half)
- **Zone Length**: 1.12km (10K) / 1.10km (Half)
- **Overtaking 10K**: 601 runners (97.2% of 618 total)
- **Overtaking Half**: 912 runners (100% of 912 total)

## Timing Analysis

### Pace Statistics
- **10K**: mean=6.44 min/km, median=6.10 min/km, std=1.49
- **Half**: mean=5.98 min/km, median=5.77 min/km, std=1.19

### Temporal Overlap Analysis
- **10K enters zone**: 463.5 to 524.3 minutes
- **10K exits zone**: 467.3 to 537.9 minutes
- **Half enters zone**: 473.8 to 508.8 minutes
- **Half exits zone**: 477.7 to 522.8 minutes
- **Overlap window**: 473.8 to 522.8 minutes (49 minutes)

## Sample Runner Analysis

### 10K Sample Runners (Convergence Zone Timing)
| Runner ID | Pace (min/km) | Enter Zone | Exit Zone | Duration |
|-----------|---------------|------------|-----------|----------|
| 1049 | 4.90 | 474.2 min | 479.7 min | 5.5 min |
| 1582 | 9.40 | 505.6 min | 516.1 min | 10.5 min |
| 1082 | 5.13 | 475.8 min | 481.6 min | 5.8 min |
| 1305 | 6.10 | 482.6 min | 489.4 min | 6.8 min |
| 1109 | 5.32 | 477.1 min | 483.1 min | 6.0 min |

### Half Sample Runners (Convergence Zone Timing)
| Runner ID | Pace (min/km) | Enter Zone | Exit Zone | Duration |
|-----------|---------------|------------|-----------|----------|
| 2267 | 6.45 | 484.8 min | 491.9 min | 7.1 min |
| 2379 | 7.07 | 487.2 min | 495.0 min | 7.8 min |
| 2163 | 6.07 | 483.4 min | 490.0 min | 6.6 min |
| 1985 | 5.50 | 481.2 min | 487.2 min | 6.0 min |
| 1979 | 5.52 | 481.2 min | 487.3 min | 6.1 min |

## Overlap Analysis

### Sample Runner Pair Overlaps
| 10K Runner | Half Runner | 10K Window | Half Window | Overlap |
|------------|-------------|------------|-------------|---------|
| 1049 (4.90) | 2267 (6.45) | 474.2-479.7 | 484.8-491.9 | 0.0 min |
| 1049 (4.90) | 2379 (7.07) | 474.2-479.7 | 487.2-495.0 | 0.0 min |
| 1049 (4.90) | 2163 (6.07) | 474.2-479.7 | 483.4-490.0 | 0.0 min |
| 1582 (9.40) | 2267 (6.45) | 505.6-516.1 | 484.8-491.9 | 0.0 min |
| 1582 (9.40) | 2379 (7.07) | 505.6-516.1 | 487.2-495.0 | 0.0 min |
| 1582 (9.40) | 2163 (6.07) | 505.6-516.1 | 483.4-490.0 | 0.0 min |

## Key Findings

### 1. High Overtaking Percentages
- **100% of Half runners** (912/912) are reported as overtaking
- **97.2% of 10K runners** (601/618) are reported as overtaking
- These percentages seem unrealistic for race analysis

### 2. Convergence Zone Length
- The convergence zone is **1.12km long** (10K) and **1.10km long** (Half)
- This represents **49% of the total segment length** for 10K and **49% for Half**
- Such a long zone creates extensive temporal overlap

### 3. Temporal Overlap
- **49 minutes of temporal overlap** between events
- This large overlap window explains the high overtaking percentages
- The algorithm correctly identifies temporal overlap but may be too permissive

### 4. Sample Runner Analysis
- Individual runner pairs show **0.0 minutes overlap** in the sample
- This suggests the algorithm may be using different logic for individual vs. aggregate analysis

## Recommendations

### 1. Convergence Zone Refinement
- Consider using a shorter convergence zone (e.g., 0.2-0.5km instead of 1.1km)
- This would reduce the temporal overlap window and provide more realistic overtaking percentages

### 2. Overlap Detection Logic
- Review the overlap detection algorithm to ensure it's using the correct convergence zone
- Verify that individual runner analysis matches aggregate analysis

### 3. Validation Against Race Data
- Compare results with actual race data if available
- Validate that 100% overtaking percentages are realistic for this segment

## Conclusion
The algorithm is mathematically correct but produces unrealistic overtaking percentages due to the long convergence zone (1.1km) and extensive temporal overlap (49 minutes). The high percentages suggest that almost all runners from both events are in the same space at the same time, which may not reflect the actual race dynamics.

**Recommendation**: Refine the convergence zone calculation to use a shorter, more realistic overtaking window.
