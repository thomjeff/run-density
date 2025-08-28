# Changelog

## [1.3.4] – 2025-08-27

### Added
- Custom zoning metric & thresholds
- New zoneMetric request field: "areal" (default) or "crowd".
- Optional zones object to override 5-band cuts:
- zones.areal: e.g. [7.5, 15, 30, 50]
- zones.crowd: e.g. [1, 2, 4, 8] (pax / m²)
- Crowd density output (peak.crowd_density) alongside peak.areal_density.
- CSV export endpoint: POST /api/peaks.csv streams per-segment peaks (includes areal, crowd, zone).

### Changed
- Per-segment binning: very short segments now auto-reduce stepKm so each span has ≥1 bin.
- Zoning logic refactored:
- Generic _zone_from_metric + _zone_for_density choose cuts from zones and metric from zoneMetric.
- Bi-direction segments halve effective width before density.
- Validation & errors: clearer 422s for missing start times, invalid thresholds, or bad params.

### Fixed
- Eliminated intermittent 500s caused by stale helpers and unbound loop vars during recent refactors.
- peaks.csv now streams correctly and respects zoneMetric/zones.

### Dev / DX
- New Makefile smokes:
- make smoke-areal — custom areal cuts
- make smoke-crowd — custom crowd cuts
- Debug traces are bounded (trace[:50]) when ?debug=true to keep payloads lightweight.

### Compatibility
- Request remains backward-compatible:
- If zones is omitted, defaults apply.
- If zoneMetric is omitted, "areal" is used.
- Existing fields (paceCsv, overlapsCsv, startTimes, stepKm, timeWindow, depth_m) unchanged.


## [1.3.3] – 2025-08-27

### 🔧 Fixes & Improvements
- **Shared Start Window Fix**  
  Corrected logic so overlapping events respect their distinct start times rather than producing artificial overlaps.  
  *Example: A1a (Start to Queen/Regent) now shows only 10K counts at 07:20, Half is correctly excluded.*

- **New Metric: `crowd_density`**  
  Added a human-intuitive density measure expressed as *runners per m²*, configurable with a `depth_m` parameter (default: 3.0m).  
  This complements `areal_density` and provides better interpretability of congestion.

- **Start-Line Splits**  
  Segments A1, A2, A3 were subdivided into finer spans (~0.9 km each) to capture how the field disperses downstream from the start.  
  Early peaks are concentrated at 0.0 km, then densities taper in later sub-segments.

- **Stability**  
  Local and prod smoke tests passed; 40 segments returned.  
  Non-green congestion zones align with expected field sizes and course widths.

### 📊 Sample Outputs
- **A1a**: peak = 586, areal_density = 58.6, crowd_density = 19.5 → *dark-red*.  
- **A1b**: peak = 20, areal_density = 2.0, crowd_density = 0.67 → *green*.  
- **A2a/A3a**: peak values corrected, tapering visible over ~1 km.

---

**Next steps (v1.3.4-dev):**
- Add bib-level trace outputs.  
- Validate bi-direction edge cases (e.g., H3).  
- Explore export options for human-readable outputs alongside JSON.
  
## [1.3.2] – 2025-08-27
### Added
- Per-segment debug view: GET /api/density?seg_id=<ID>&debug=true now returns a focused segment with first_overlap and a short trace sample for quick inspection.
- Query filter: Support ?seg_id=<ID> to compute/return a single segment from overlaps.csv.

### Changed
- Canonical overlaps schema: API and engine now only accept seg_id (we removed legacy segment_id).
- Start time model: {"10K": 440} is now a first-class field (no leading underscore). Internal model normalized (TenK) with alias mapping for request/response stability.
- Areal density sanity: Correct handling of minutes-per-km (pace) and direction/width rules: direction: "bi" halves the effective width (width_m / 2); Areal density reported as people per m² using the effective width.
- Main ↔ engine alignment: main.py now calls run_density(payload, seg_id_filter=…, debug=…) to prevent drift and 422/500 mismatches.

### Fixed
- Intermittent 422/500 errors stemming from mismatched parameter names and optional JSON fields.
- Local/prod smoke parity (both return stable counts; A1 spot-check matches across environments).
- Minor CSV header gotchas (e.g., accidental segmenttolabel) — stricter validation paths.

### Developer experience
- Make targets stabilized (run-local, stop-local, smoke-local, smoke-prod) on port 8081.
- Clearer error surfaces in /api/density (500 returns {"error": "..."}" with concise message).
- Pinned/verified deps (FastAPI / Starlette / Pydantic / Requests) for Python 3.12 runtime.

## [1.3.1] – 2025-08-27
Stability release that operationalized density engine.

## [1.3.0] – 2025-08-27
Stability release

## [1.2.0] – 2025-08-21
### Added
- Human-readable reporting endpoint (`/api/report`)  
  - Outputs overlap segments in plain English with segment labels, start times, runner counts, overlap timing, and peak density.  
  - Includes density expressed in ppl/m² with color-coded zone labels (green → dark-red).  
- CI/CD improvements:  
  - GitHub Actions workflow for deployment (`deploy-cloud-run.yml`).  
  - Smoke tests (`smoke-report.yml`) with badges in README.md.  
  - Added `VERIFY.md` for manual endpoint verification.  
  - Added `smoke-report.sh` for local/GCP smoke checks.  
- Repo hygiene:  
  - `.gitignore` tuned for Python/macOS/venv.  
  - `.python-version` (3.12.5) and `Makefile` with helper targets (`run-local`, `smoke-local`, `smoke-prod`).  

### Changed
- Documentation refreshed (README.md) with updated install/run/deploy steps.  
- Clarified guardrails: always use Docker + Artifact Registry for builds (no Cloud Build).  

### Fixed
- Consistent segment labels by integrating `overlaps.csv` with names (e.g. “Start to Friel”).  
- Smoke tests now validated both locally and on GCP.  

## [v1.1.1] - 2025-08-20
### Added
- Introduced GitHub Actions workflow with **Docker → Artifact Registry → Cloud Run** deployment.
- Added automated **smoke tests** (`/health`, `/ready`, `/api/density`) with retry logic to validate live service after deploy.
- Integrated **service URL resolution** directly from Cloud Run for consistent test targeting.

### Changed
- Updated `Makefile` with `smoke-local` and `smoke-prod` targets for easier local and CI/CD validation.
- Standardized deployment path to **Docker builds** (explicitly avoiding Google Cloud Build).

### Fixed
- Resolved build failures caused by invalid Artifact Registry tags (missing repo name).
- Fixed empty `BASE_URL` issue in smoke tests by passing through service URL correctly.

## [1.0.0] - 2025-08-19
### Added
- Cloud Run deployment with FastAPI/Gunicorn.
- /api/density: density metrics & zone classification per segment.
- /api/overlap: per-step split counts with staggered starts.
- /health and /ready endpoints for liveness/readiness.
- X-Compute-Seconds response header.

### Changed
- Default platform from Vercel to Cloud Run.

### Fixed
- Eliminated legacy runtime/version errors; stable container boot.
