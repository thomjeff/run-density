# UI Testing Checklist

**Version:** 1.0  
**Last Updated:** 2025-10-28  
**Purpose:** Comprehensive UI testing steps for verifying deployments and issue fixes

This document provides a systematic approach to testing local and cloud deployments, ensuring all functionality works correctly after code changes. Use this checklist for any local or cloud deployment for functional verification and issue resolution testing.

---

## Prerequisites

- Local environment is running and health (for local)
- Cloud Run service deployed and accessible (for cloud)
- For Cloud: CI Pipeline completed successfully and all 4 stages passed (Build, E2E, Bin Datasets, Release)
- No critical errors in local start-up logs or Cloud Run logs for cloud

---

## Testing Environment

**Cloud Run URL:** `http://localhost:8081`

**Cloud Run URL:** `https://run-density-ln4r3sfkha-uc.a.run.app`

**Browser Tool:** Use Playwright browser automation for consistent testing

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

### Browser Automation
```bash
# Use Playwright browser tool for consistent testing
mcp_cursor-playwright_browser_navigate
mcp_cursor-playwright_browser_click
mcp_cursor-playwright_browser_wait_for
```

### Cloud Run Logs Monitoring
```bash
# Check for errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=run-density AND severity>=ERROR" --limit=10

# Check for warnings
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=run-density AND severity>=WARNING" --limit=10

# Check recent activity
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=run-density" --limit=10 --freshness=15m
```

### CI Pipeline Monitoring
```bash
# Check workflow status
gh run list --limit 5

# View specific run
gh run view <run-id>

# Check job status
gh run view --job=<job-id>
```

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

### For Issue #389 (Import Scoping Patterns)
- **Primary Focus**: Verify flags displaying correctly on Density page
- **Key Test**: A1 heatmap loading and displaying
- **Data Validation**: Reports generated from latest E2E run
- **Success Indicator**: No import-related errors in console or logs

### For Future Issues
- Adapt this checklist based on the specific changes made
- Focus testing on areas most likely affected by the changes
- Always verify core functionality remains intact
- Document any new testing requirements discovered

---

## Troubleshooting

### Common Issues
1. **Page not loading**: Check Cloud Run service status
2. **Missing data**: Verify E2E run completed successfully
3. **Heatmap not loading**: Check GCS permissions and signed URLs
4. **Reports missing**: Verify report generation in CI pipeline
5. **Flags not showing**: Check flags.json file in GCS

### Debugging Steps
1. Check Cloud Run logs for errors
2. Verify CI pipeline completed successfully
3. Check browser console for JavaScript errors
4. Verify API endpoints responding correctly
5. Check GCS bucket contents for missing files

---

## Maintenance

This checklist should be updated when:
- New pages or features are added
- Testing requirements change
- New error patterns are discovered
- Cloud Run configuration changes

**Last Updated:** 2025-10-28  
**Updated By:** AI Assistant (Issue #389 verification)  
**Next Review:** When new testing requirements are identified
