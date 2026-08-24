# UI Testing Checklist

**Version:** 3.1  
**Last Updated:** 2026-08-21  
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

**Run context:** Plan URLs are `run_id`-primary. Day is derived from the selected run (no day dropdown). Do not treat stale `?day=` as the product control.

**Retired destinations:** `/segments` must redirect to Density; `/reports` must redirect to Overview (query string preserved).

### 1. ✅ Runs catalog (`/dashboard`)

**URL:** `/dashboard`

**Verification Steps:**
- [ ] Page loads without errors
- [ ] Recent / all runs list is visible
- [ ] Choosing a run opens `/overview?run_id=…`
- [ ] Plan chrome shows **Overview · Density · Flow · Junctions · Motion · Progression · Locations** (no Segments, no Reports)

### 2. ✅ Overview

**URL:** `/overview?run_id={uuid}`

**Verification Steps:**
- [ ] **New analysis** card: package dropdown + **Run analysis…** (disabled until the package is analysis-ready)
- [ ] Analysis Inputs and Analysis Outputs render for the selected run
- [ ] Package name on Analysis Inputs links to Build → that package
- [ ] **Exports** shows **Reports (.zip)** and **Data Files (.zip)** (no “Download” prefix)
- [ ] Reports ZIP contains Density/Flow/Locations/Passes/finish artifacts for the run/day, not the whole analysis tree
- [ ] Data Files ZIP contains analysis input CSV/GPX
- [ ] Bookmark `/reports?run_id={uuid}` lands on Overview

### 3. ✅ Density

**URL:** `/density?run_id={uuid}`

**Verification Steps:**
- [ ] Course map loads with LOS-coloured segments
- [ ] Segment Analysis columns are `ID | Name | Length | Width | Peak Window | LOS` (no Schema / Peak Density / Peak Rate / Flag columns)
- [ ] Table height is capped (scrolls; does not consume the full viewport)
- [ ] Clicking a map segment selects the matching table row and opens assessment
- [ ] Clicking a table row emphasizes the map segment without aggressive zoom
- [ ] Hover on map or table highlights the counterpart without changing selection
- [ ] Selected segment shows LOS + Peak Density, Peak Condition (clock + `0.0–0.2 km` style range), Field Window, supporting Peak Rate / Direction / Events / Flagged bins
- [ ] Narrative sits under the heatmap/assessment row; compact LOS reference is in the same card below the narrative
- [ ] **View N flagged bins** opens a modal with KM/time/density/rate/LOS plus the same LOS reference
- [ ] Heatmap loads from `/heatmaps/analysis/{run_id}/{day}/ui/visualizations/{seg_id}.png`
- [ ] `/segments?run_id={uuid}` redirects to Density

**Expected Results:**
- Map and table stay in sync
- Peak Window is the worst-bin clock, not the full occupancy interval
- Field Window is occupancy first–last
- Bin details are drill-down only (not a permanent table on the main page)

### 4. ✅ Flow

**URL:** `/flow?run_id={uuid}`

**Verification Steps:**
- [ ] Flow Overlaps list Segment IDs in numeric order (`S9` before `S10`; IDs are not renamed to `S09`)
- [ ] Selected-segment detail shows one tile per event with Unique Overtakers and Unique Overtaken together
- [ ] Two directional matrices remain, with headings **Who this event overtakes →** and **← Who overtakes this event**
- [ ] Crowding Context copy identifies concurrent occupancy, not overtaking counts
- [ ] Tile uniques are unions (do not expect matrix cells to sum to the tile)

### 5. ✅ Other Plan views (smoke)

- [ ] Junctions, Motion, Progression, and Locations load for the selected run
- [ ] Motion Q×Q headers show unique-enter counts where the window detail is open
- [ ] Progression map/legend/wallboard follow earliest modeled start

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
- `/api/reports/export.zip` - 🟢 Up
- `/api/bins/*` - 🟢 Up (if used by frontend)
- `/runflow/v2/analyze` - 🟢 Up (v2 API endpoint)

---

## Data Validation Checks

### Heatmap Verification
- [ ] Heatmaps load from `/heatmaps/analysis/{run_id}/{day}/ui/visualizations/{seg_id}.png` (static file serving)
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
- [ ] Overview **Reports (.zip)** / **Data Files (.zip)** download for the selected run/day
- [ ] ZIP contents match the allow-list (not every file under the run directory)
- [ ] Report timestamps match CI completion
- [ ] File sizes reasonable and non-zero

### Data Consistency
- [ ] No zero values in any metrics
- [ ] No N/A values in any columns
- [ ] All segments showing proper data
- [ ] Flag counts consistent across pages
- [ ] Run ID consistent across all API calls
- [ ] Selected run's day is used consistently (run-derived, not a Plan day dropdown)

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

# List reports / export ZIP
curl -s "http://localhost:8080/api/reports/list?run_id={uuid}" | jq .
curl -sI "http://localhost:8080/api/reports/export.zip?kind=reports&run_id={uuid}&day=sun"

---

## Success Criteria

A deployment is considered successful when:

- ✅ Plan pages load without errors (Overview, Density, Flow, Junctions, Motion, Progression, Locations)
- ✅ `/segments` and `/reports` redirect
- ✅ Density map/table selection stays in sync; flagged bins open in a modal
- ✅ Overview ZIP exports download
- ✅ Flow Segment IDs sort numerically
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
- Test `?run_id={uuid}` on Plan pages; day is run-derived
- Verify `?run_id={uuid}` parameter works when specified

### URL Parameter Testing
- [ ] Test pages with `?run_id={uuid}` parameter
- [ ] Day comes from the run (chrome / localStorage), not a Plan day dropdown
- [ ] `/segments?run_id={uuid}` redirects to Density
- [ ] `/reports?run_id={uuid}` redirects to Overview
- [ ] Verify fallback to latest run_id when not specified

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

**Last Updated:** 2026-08-21  
**Updated By:** Alignment with Plan UI (#888, #890, #891)  
**Changes in v3.1:**
- Plan nav no longer includes Segments or Reports
- Density is the segment workspace (map + table + assessment + bin modal)
- Overview Exports replace the Reports page
- Flow numeric Segment ID order and combined event tiles
- Run-derived day; `/segments` and `/reports` redirects

**Next Review:** When new testing requirements are identified
