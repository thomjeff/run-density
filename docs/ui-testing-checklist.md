# UI Testing Checklist

**Version:** 2.0  
**Last Updated:** 2025-11-11  
**Purpose:** Comprehensive UI testing steps for verifying local deployments and issue fixes

This document provides a systematic approach to testing local Docker deployments, ensuring all functionality works correctly after code changes. Use this checklist for local deployment verification and issue resolution testing.

---

## Prerequisites

- Local Docker environment is running and healthy
- Container accessible at `http://localhost:8080`
- No critical errors in startup logs
- E2E tests have completed successfully

---

## Testing Environment

**Local Docker URL:** `http://localhost:8080`

**Browser Tool:** Use browser automation for consistent testing

---

## Comprehensive Testing Steps

### 1. ✅ Dashboard Page Verification

**URL:** `/dashboard`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] All metrics displaying correctly
- [ ] Peak Density value matches expected E2E run data
- [ ] Peak Rate value matches expected E2E run data
- [ ] Flag counts showing correctly (e.g., "17/28 segments with flags")
- [ ] No zero values in any metrics
- [ ] Last updated timestamp matches latest E2E run
- [ ] All model inputs showing correct participant counts
- [ ] All model outputs showing proper values

**Expected Results:**
- Peak Density: ~0.755 p/m²
- Peak Rate: ~11.31 p/s
- Total Participants: ~1,898
- Segments with Flags: 17/28
- Flagged Bins: ~1,875

### 2. ✅ Density Page Verification

**URL:** `/density`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] All flags showing correctly (⚠️ icons)
- [ ] Flagged segments displaying properly (A1, A2, A3, B1, B2, B3, D1, D2, F1, etc.)
- [ ] No zero values in density, rate, or utilization columns
- [ ] Pagination working correctly
- [ ] Segment data matches E2E run expectations
- [ ] LOS (Level of Service) ratings displaying correctly

**A1 Segment Specific Testing:**
- [ ] Click on A1 row to open detailed view
- [ ] Verify A1 heatmap image loads correctly
- [ ] Confirm A1 data matches E2E run:
  - Peak Density: 0.755 p/m²
  - LOS: D
  - Peak Rate: 11.31 p/s
- [ ] Verify bin-level details showing (37 bins)
- [ ] Confirm no zero values in bin data
- [ ] Verify heatmap timestamp matches latest E2E run

**Expected Results:**
- All flagged segments show ⚠️ icons
- A1 heatmap displays correctly
- Bin data shows proper density and rate values
- No missing or zero values

### 3. ✅ Reports Page Verification

**URL:** `/reports`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] Reports list displays correctly
- [ ] Most recent reports from latest E2E run visible
- [ ] Report timestamps match CI workflow completion time
- [ ] Both Flow.csv and Density.md reports present
- [ ] Report file sizes reasonable (not zero)
- [ ] Download links working correctly

**Expected Reports (from latest E2E run):**
- `2025-10-28-1848-Flow.csv` (~9.7 KB)
- `2025-10-28-1848-Flow.md` (~32.4 KB)
- `2025-10-28-1844-Density.md` (~109.0 KB)

**Download Testing:**
Download the following reports created from your E2E test:
- [ ] Download Flow.csv successfully
- [ ] Download Flow.md successfully
- [ ] Download Density.md successfully
- [ ] Verify downloaded files contain expected content

### 4. ✅ Flow Page Verification

**URL:** `/flow`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] All 28 segments displaying in table
- [ ] Flow analysis data showing correctly
- [ ] No zero values or N/A in any columns
- [ ] Flow types working (overtake, parallel, counterflow)
- [ ] Percentages and counts displaying properly
- [ ] Total summary showing correct counts

**Expected Results:**
- 29 segments total (including totals row)
- All segments showing proper flow data
- Overtaking events: ~2,472/2,375
- Co-presence events: ~2,690/2,479
- No missing or zero values

### 5. ✅ Segments Page Verification

**URL:** `/segments`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] Interactive map initializing correctly
- [ ] All 22 segments displayed in metadata table
- [ ] Segment details showing properly:
  - Length (km)
  - Width (m)
  - Direction (uni/bi)
  - Events (Full, Half, 10K)
  - LOS ratings
- [ ] No zero values in segment metadata
- [ ] Map controls working (zoom in/out)
- [ ] Segment descriptions displaying correctly

**Expected Results:**
- Interactive map loads with all segments
- Complete segment metadata for all 22 segments
- Proper LOS ratings (A, B, C, D)
- No missing or zero values

### 6. ✅ Health Check Page Verification

**URL:** `/health-check`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] System status shows "All Systems Operational"
- [ ] Version number matches deployment
- [ ] Last updated timestamp matches deployment time
- [ ] All API endpoints showing 🟢 Up status
- [ ] No error indicators

**Expected API Endpoints:**
- `/health` - 🟢 Up
- `/ready` - 🟢 Up
- `/api/dashboard/summary` - 🟢 Up
- `/api/segments/summary` - 🟢 Up
- `/api/density/segments` - 🟢 Up
- `/api/flow/segments` - 🟢 Up
- `/api/reports/list` - 🟢 Up

---

## Data Validation Checks

### Heatmap Verification
- [ ] A1.png heatmap loads correctly
- [ ] Heatmap timestamp matches latest E2E run
- [ ] Image displays without errors
- [ ] Bin-level details show proper data

### Report Verification
- [ ] Reports generated from latest E2E run
- [ ] Report timestamps match CI completion
- [ ] File sizes reasonable and non-zero
- [ ] Download functionality working

### Data Consistency
- [ ] No zero values in any metrics
- [ ] No N/A values in any columns
- [ ] All segments showing proper data
- [ ] Flag counts consistent across pages

---

## Error Detection

### Console Errors
- [ ] No JavaScript errors in browser console
- [ ] No network request failures
- [ ] No 404 or 500 errors
- [ ] No timeout errors

### Visual Errors
- [ ] No broken images
- [ ] No missing UI elements
- [ ] No layout issues
- [ ] No loading failures

### Data Errors
- [ ] No missing data in tables
- [ ] No incorrect calculations
- [ ] No inconsistent values
- [ ] No empty responses

---

## Testing Tools and Commands

### Docker Logs Monitoring
```bash
# Check container logs for errors
docker logs run-density-dev | grep -iE "error|exception|failed"

# Check for warnings
docker logs run-density-dev | grep -i "warning"

# View recent logs
docker logs run-density-dev --tail 50

# Follow logs in real-time
docker logs run-density-dev --follow
```

### API Testing
```bash
# Health check
curl -s http://localhost:8080/health | jq .

# Dashboard API
curl -s http://localhost:8080/api/dashboard/summary | jq .

# Latest run_id
docker exec run-density-dev cat /app/runflow/latest.json | jq .

# List reports
curl -s http://localhost:8080/api/reports/list | jq .

---

## Success Criteria

A deployment is considered successful when:

- ✅ All 6 pages load without errors
- ✅ All flags displaying correctly on Density page
- ✅ A1 heatmap loads and displays correctly
- ✅ Reports from latest E2E run available and downloadable
- ✅ Flow page shows all 28 segments with proper data
- ✅ No zero values or N/A in any data
- ✅ Health check shows all systems operational
- ✅ No console errors or visual issues
- ✅ All API endpoints responding correctly

---

## Issue-Specific Testing Notes

### General Testing Approach
- Focus testing on areas most likely affected by code changes
- Always verify core functionality remains intact
- Check that latest run_id is consistent across all APIs
- Verify heatmaps and reports are in correct locations (`runflow/<uuid>/`)

---

## Troubleshooting

### Common Issues
1. **Page not loading**: Check Docker container status (`docker ps`)
2. **Missing data**: Verify E2E run completed successfully (`make e2e-local`)
3. **Heatmap not loading**: Check `runflow/<uuid>/ui/heatmaps/` directory
4. **Reports missing**: Verify reports in `runflow/<uuid>/reports/`
5. **Flags not showing**: Check `runflow/<uuid>/ui/flags.json`

### Debugging Steps
1. Check Docker logs: `docker logs run-density-dev --tail 100`
2. Verify container is running: `docker ps`
3. Check browser console for JavaScript errors
4. Verify API endpoints: `curl http://localhost:8080/health`
5. Check latest run_id: `docker exec run-density-dev cat /app/runflow/latest.json`

---

## Maintenance

This checklist should be updated when:
- New pages or features are added
- Testing requirements change
- New error patterns are discovered
- Docker configuration changes

**Last Updated:** 2025-11-11  
**Updated By:** AI Assistant (Issue #466 Phase 2 - Documentation Refresh)  
**Next Review:** When new testing requirements are identified
