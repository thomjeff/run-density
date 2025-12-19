# UI Testing Checklist

**Version:** 2.1  
**Last Updated:** 2025-12-19  
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

**Multi-Day Support:** All pages support `?day=sat` and `?day=sun` parameters. Test both scenarios to ensure data switches correctly between days.

### 1. ✅ Dashboard Page Verification

**URL:** `/dashboard` or `/dashboard?day=sat` or `/dashboard?day=sun`

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
- [ ] Day selector works correctly (if present)
- [ ] Data updates when switching between `?day=sat` and `?day=sun`

**Expected Results:**
- Values vary by day and run_id - check E2E test output for expected values
- Peak Density: Check latest E2E run output
- Peak Rate: Check latest E2E run output
- Total Participants: Check latest E2E run output
- Segments with Flags: Check latest E2E run output
- Flagged Bins: Check latest E2E run output

### 2. ✅ Density Page Verification

**URL:** `/density` or `/density?day=sat` or `/density?day=sun` or `/density?run_id={uuid}&day=sat`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] All flags showing correctly (⚠️ icons)
- [ ] Flagged segments displaying properly (A1, A2, A3, B1, B2, B3, D1, D2, F1, etc.)
- [ ] No zero values in density, rate, or utilization columns
- [ ] Pagination working correctly
- [ ] Segment data matches E2E run expectations
- [ ] LOS (Level of Service) ratings displaying correctly
- [ ] Day selector works correctly (if present)
- [ ] Data updates when switching between `?day=sat` and `?day=sun`
- [ ] Run ID parameter works correctly (`?run_id={uuid}`)

**Segment Detail Testing:**
- [ ] Click on any segment row to open detailed view
- [ ] Verify heatmap image loads correctly from `/heatmaps/{run_id}/{day}/ui/heatmaps/{seg_id}.png`
- [ ] Confirm segment data matches E2E run (check latest E2E output for expected values)
- [ ] Verify bin-level details showing
- [ ] Confirm no zero values in bin data
- [ ] Verify heatmap timestamp matches latest E2E run
- [ ] Test with both `?day=sat` and `?day=sun` parameters

**Expected Results:**
- All flagged segments show ⚠️ icons
- Heatmaps display correctly (served via static file mount at `/heatmaps/`)
- Bin data shows proper density and rate values
- No missing or zero values
- Values vary by day - check E2E test output for expected values per day

### 3. ✅ Reports Page Verification

**URL:** `/reports`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] Reports list displays correctly
- [ ] Most recent reports from latest E2E run visible
- [ ] Report timestamps match E2E run completion time
- [ ] Both Flow.csv and Density.md reports present
- [ ] Report file sizes reasonable (not zero)
- [ ] Download links working correctly
- [ ] Reports organized by run_id and day (if multi-day run)

**Expected Reports (from latest E2E run):**
- Reports are in `runflow/{run_id}/{day}/reports/` directory
- Check latest E2E run output for actual report filenames and sizes
- Typical reports: `Flow.csv`, `Flow.md`, `Density.md`, `Locations.csv`
- **Example (Run cyvCJ8CCpuepAhe8gkt3nZ):**
  - SAT: Density.md (5.8K), Flow.csv (3.8K), Flow.md (13K), Locations.csv (2.1K)
  - SUN: Density.md (110K), Flow.csv (13K), Flow.md (41K), Locations.csv (18K)

**Download Testing:**
Download the following reports created from your E2E test:
- [ ] Download Flow.csv successfully (both SAT and SUN)
- [ ] Download Flow.md successfully (both SAT and SUN)
- [ ] Download Density.md successfully (both SAT and SUN)
- [ ] Download Locations.csv successfully (both SAT and SUN)
- [ ] Verify downloaded files contain expected content
- [ ] Verify reports are accessible via `/api/reports/download?path=runflow/{run_id}/{day}/reports/{filename}`
- [ ] Verify file sizes match expected values (SUN reports typically larger than SAT)

### 4. ✅ Flow Page Verification

**URL:** `/flow` or `/flow?day=sat` or `/flow?day=sun` or `/flow?run_id={uuid}&day=sat`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] All segments displaying in table
- [ ] Flow analysis data showing correctly
- [ ] No zero values or N/A in any columns
- [ ] Flow types working (overtake, parallel, counterflow)
- [ ] Percentages and counts displaying properly
- [ ] Total summary showing correct counts
- [ ] Day selector works correctly (if present)
- [ ] Data updates when switching between `?day=sat` and `?day=sun`
- [ ] Run ID parameter works correctly (`?run_id={uuid}`)

**Expected Results:**
- All segments showing proper flow data
- Values vary by day and run_id - check E2E test output for expected values
- No missing or zero values
- Segment count matches E2E run output

### 5. ✅ Segments Page Verification

**URL:** `/segments`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] Interactive map initializing correctly
- [ ] All segments displayed in metadata table
- [ ] Segment details showing properly:
  - Length (km)
  - Width (m)
  - Direction (uni/bi)
  - Events (Full, Half, 10K)
  - LOS ratings
- [ ] No zero values in segment metadata
- [ ] Map controls working (zoom in/out)
- [ ] Segment descriptions displaying correctly
- [ ] Heatmap preview works when selecting segments (if available)
- [ ] GeoJSON data loads correctly from `/api/segments/geojson`

**Expected Results:**
- Interactive map loads with all segments
- Complete segment metadata for all segments
- Proper LOS ratings (A, B, C, D)
- No missing or zero values
- Segment count matches E2E run output

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
- `/api/health/data` - 🟢 Up (system health data)
- `/api/dashboard/summary` - 🟢 Up (supports `?day=` parameter)
- `/api/segments/summary` - 🟢 Up
- `/api/segments/geojson` - 🟢 Up (map GeoJSON data)
- `/api/density/segments` - 🟢 Up (supports `?day=` and `?run_id=` parameters)
- `/api/density/segment/{seg_id}` - 🟢 Up (detail view, supports `?day=` and `?run_id=`)
- `/api/flow/segments` - 🟢 Up (supports `?day=` and `?run_id=` parameters)
- `/api/reports/list` - 🟢 Up
- `/api/reports/download` - 🟢 Up
- `/api/bins/*` - 🟢 Up (if used by frontend)
- `/runflow/v2/analyze` - 🟢 Up (v2 API endpoint)

---

## Data Validation Checks

### Heatmap Verification
- [ ] Heatmaps load from `/heatmaps/{run_id}/{day}/ui/heatmaps/{seg_id}.png` (static file serving)
- [ ] Heatmap images display correctly without errors
- [ ] Heatmap timestamp matches latest E2E run
- [ ] Bin-level details show proper data
- [ ] Heatmaps work for both `sat` and `sun` days
- [ ] Heatmap paths resolve correctly (no 404 errors)
- [ ] Note: Heatmaps are served via static file mount, not API endpoint (Phase 3 cleanup removed `/api/generate/heatmaps`)
- [ ] **Expected Counts (Run cyvCJ8CCpuepAhe8gkt3nZ):**
  - SAT: 6 heatmaps (N1, N2, N3, O1, O2, O3 - Elite/Open segments only)
  - SUN: 20 heatmaps (all segments with flagged bins)

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
- [ ] Run ID consistent across all API calls
- [ ] Day parameter works consistently across all pages

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

# System health data
curl -s http://localhost:8080/api/health/data | jq .

# Dashboard API (with day parameter)
curl -s http://localhost:8080/api/dashboard/summary | jq .
curl -s "http://localhost:8080/api/dashboard/summary?day=sat" | jq .
curl -s "http://localhost:8080/api/dashboard/summary?day=sun" | jq .

# Density API (with day and run_id parameters)
curl -s "http://localhost:8080/api/density/segments?day=sat" | jq .
curl -s "http://localhost:8080/api/density/segment/A1?day=sat&run_id={uuid}" | jq .

# Flow API (with day and run_id parameters)
curl -s "http://localhost:8080/api/flow/segments?day=sat" | jq .

# Segments GeoJSON
curl -s http://localhost:8080/api/segments/geojson | jq .

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
- Verify heatmaps and reports are in correct locations (`runflow/<uuid>/<day>/`)
- Test both `?day=sat` and `?day=sun` scenarios
- Verify `?run_id={uuid}` parameter works when specified

### URL Parameter Testing
- [ ] Test pages with `?run_id={uuid}` parameter
- [ ] Test pages with `?day=sat` parameter
- [ ] Test pages with `?day=sun` parameter
- [ ] Test pages with both `?run_id={uuid}&day=sat`
- [ ] Verify fallback to latest run_id when not specified
- [ ] Verify day parameter defaults correctly when not specified

---

## Troubleshooting

### Common Issues
1. **Page not loading**: Check Docker container status (`docker ps`)
2. **Missing data**: Verify E2E run completed successfully (`make e2e-local` or `make e2e-coverage-lite DAY=both`)
3. **Heatmap not loading**: Check `runflow/<uuid>/<day>/ui/heatmaps/` directory (note: includes day subdirectory)
4. **Reports missing**: Verify reports in `runflow/<uuid>/<day>/reports/` directory
5. **Flags not showing**: Check `runflow/<uuid>/<day>/ui/flags.json`
6. **Wrong day data**: Verify `?day=` parameter is correctly passed to API calls
7. **404 on heatmaps**: Verify static file mount at `/heatmaps/` is working (check `main.py` mount configuration)

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

**Last Updated:** 2025-12-19  
**Updated By:** AI Assistant (Issue #544 Phase 3B - E2E Test Review)  
**Changes in v2.1:**
- Added multi-day support testing (`?day=sat` and `?day=sun` parameters)
- Updated API endpoints list (added `/api/health/data`, `/api/segments/geojson`, `/api/density/segment/{seg_id}`, etc.)
- Updated heatmap verification (static file serving via `/heatmaps/` mount)
- Made expected results day-agnostic (reference E2E test output)
- Added URL parameter testing section
- Fixed path references to include day subdirectory (`runflow/<uuid>/<day>/`)
- Updated API testing commands with day and run_id parameters

**Changes in v2.2 (2025-12-19):**
- Added Locations.csv to expected reports list
- Added file size examples from Run cyvCJ8CCpuepAhe8gkt3nZ
- Added heatmap count expectations (SAT: 6, SUN: 20)
- Updated download testing to include Locations.csv
- Added note about SUN reports typically being larger than SAT

**Next Review:** When new testing requirements are identified
