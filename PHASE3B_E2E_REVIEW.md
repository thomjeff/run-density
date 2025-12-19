# Phase 3B: E2E Test Review - Run cyvCJ8CCpuepAhe8gkt3nZ

**Issue:** #544  
**Date:** December 19, 2025  
**Run ID:** `cyvCJ8CCpuepAhe8gkt3nZ`  
**Test:** `e2e-coverage-lite DAY=both`  
**Status:** ✅ **PASSED**

---

## 1. Log Review - Errors and Warnings

### ✅ Test Completion
- **Status:** ✅ Test completed successfully
- **Run ID:** `cyvCJ8CCpuepAhe8gkt3nZ`
- **Completion Message:** "Run completed successfully: cyvCJ8CCpuepAhe8gkt3nZ"

### ⚠️ Warnings Found (Expected/Non-Critical)

**Location Report Warnings (Expected):**
- 19 warnings about centerline projection failures for certain segments
- These are expected warnings for segments where centerline projection doesn't match full course distance
- System falls back to using segment midpoint for arrival calculations
- **Impact:** None - warnings are handled gracefully with fallback logic
- **Segments Affected:** O1, N1, I1, L2, J4, J5, B1, B2, B3, K1 (various events)

**Example Warning:**
```
WARNING - Location 100 (elite): Segment O1 [0.000, 2.580]km listed but centerline projection failed 
and full course distance 4.732km doesn't match. Using segment midpoint 1.290km for arrival calculations.
```

**UI Artifacts Warning (Non-Critical):**
- 1 warning: `bins.parquet not found at /app/runflow/cyvCJ8CCpuepAhe8gkt3nZ/sun/reports_temp/bins.parquet`
- **Impact:** None - system found bins.parquet at correct location (`/app/runflow/cyvCJ8CCpuepAhe8gkt3nZ/sun/reports_heatmaps/bins/bins.parquet`)
- This is a fallback path check, not an error

### ❌ Errors Found
- **None** - No errors detected in logs

---

## 2. File Validation

### SAT Day Files

#### `/ui` Directory (13 files)
- ✅ `captions.json` - Heatmap captions
- ✅ `flags.json` - Segment flags
- ✅ `flow.json` - Flow data
- ✅ `health.json` - Health metrics
- ✅ `meta.json` - Metadata
- ✅ `schema_density.json` - Density schema
- ✅ `segment_metrics.json` - Segment metrics
- ✅ `segments.geojson` - GeoJSON segments
- ✅ `heatmaps/` directory with 6 PNG files:
  - N1.png, N2.png, N3.png, O1.png, O2.png, O3.png

#### `/maps` Directory (1 file)
- ✅ `map_data.json` - Map visualization data

#### `/bins` Directory (4 files)
- ✅ `bin_summary.json` - Bin summary statistics
- ✅ `bins.geojson.gz` - Compressed GeoJSON bins
- ✅ `bins.parquet` - Bin data (Parquet format)
- ✅ `segment_windows_from_bins.parquet` - Segment windows data

#### `/reports` Directory (7 files)
- ✅ `Density.md` - 5.8K (density analysis report)
- ✅ `Flow.csv` - 3.8K (flow data CSV)
- ✅ `Flow.md` - 13K (flow analysis report)
- ✅ `Locations.csv` - 2.1K (location data)
- ✅ `bins.parquet` - Bin data
- ✅ `segment_windows_from_bins.parquet` - Segment windows
- ✅ `segments.parquet` - Segment data

### SUN Day Files

#### `/ui` Directory (28 files)
- ✅ All UI artifacts present (captions, flags, flow, health, meta, schema, metrics, GeoJSON)
- ✅ `heatmaps/` directory with 20 PNG files (one per segment)

#### `/maps` Directory (1 file)
- ✅ `map_data.json` - Map visualization data

#### `/bins` Directory (4 files)
- ✅ All bin files present (same structure as SAT)

#### `/reports` Directory (7 files)
- ✅ `Density.md` - 110K (comprehensive density report)
- ✅ `Flow.csv` - 13K (flow data CSV)
- ✅ `Flow.md` - 41K (flow analysis report)
- ✅ `Locations.csv` - 18K (location data)
- ✅ All Parquet files present

### Coverage Directory
- ✅ `coverage/` directory exists with HTML reports
- ✅ Coverage data generated successfully

---

## 3. File Count Summary

| Directory | SAT Files | SUN Files | Total |
|-----------|-----------|-----------|-------|
| `/ui` | 13 | 28 | 41 |
| `/maps` | 1 | 1 | 2 |
| `/bins` | 4 | 4 | 8 |
| `/reports` | 7 | 7 | 14 |
| **Total** | **25** | **40** | **65** |

**Plus:**
- Coverage directory with HTML reports
- Logs directory with app.log
- metadata.json at run level

---

## 4. Observations

### ✅ Expected Behavior
1. **Multi-Day Support:** Both SAT and SUN directories created successfully
2. **File Sizes:** SUN reports are larger (110K Density.md vs 5.8K for SAT) - expected due to more data
3. **Heatmaps:** SAT has 6 heatmaps (Elite/Open segments only), SUN has 20 heatmaps (all segments)
4. **Structure:** All files in correct day-scoped directories (`runflow/{run_id}/{day}/`)

### ✅ No Issues Found
- All expected files generated
- No missing files
- File sizes are reasonable (non-zero)
- Directory structure is correct
- No errors in logs

---

## 5. Conclusion

**Status:** ✅ **ALL CHECKS PASSED**

- ✅ Test completed successfully
- ✅ No errors detected
- ✅ Only expected warnings (centerline projection fallbacks)
- ✅ All files generated as expected
- ✅ File structure is correct
- ✅ Both SAT and SUN days processed successfully

**Ready for:** UI testing checklist completion and Phase 3 closure

