# Changelog

## [v1.6.0] - 2025-09-04

### Major Architecture Refactoring
- **Report Generation Architecture**: Complete separation of analysis logic from output generation
- **CSV Export Refactoring**: Moved CSV export functionality from core modules to report modules
- **API Integration Improvements**: Enhanced JSON serialization and error handling
- **Import Consistency**: Standardized relative imports across all modules

### Report Module Enhancements
- **Temporal Flow Reports**: 
  - Auto-generates both Markdown and CSV outputs
  - Enhanced convergence analysis with detailed overtaking statistics
  - Flow type breakdown (overtake, merge, diverge patterns)
- **Density Reports**:
  - Comprehensive per-event analysis with experienced density
  - LOS scores, sustained periods, and TOT metrics
  - Active window filtering and occupancy calculations
- **Permanent Report Modules**: Replaced temporary scripts with reusable, maintainable modules

### API & Integration Improvements
- **Enhanced JSON Serialization**: Robust handling of NaN values and dataclass objects
- **Improved Error Handling**: Better error messages and HTTP status codes
- **Consistent API Patterns**: Standardized request/response formats across all endpoints
- **CLI Scripts**: Executable command-line tools for both report types

### Developer Experience
- **Better Separation of Concerns**: Core modules focus on analysis, report modules on output
- **Single Responsibility Principle**: Each module has a clear, focused purpose
- **Future-Proof Architecture**: Easy to add PDF, JSON, or other output formats
- **Maintainable Codebase**: Reduced duplication and improved organization

### Testing & Quality
- **Comprehensive API Testing**: All endpoints verified and working
- **Import Consistency**: Fixed all relative import issues
- **JSON Serialization**: Resolved complex data type serialization problems
- **End-to-End Validation**: Both CSV and Markdown generation tested

## [v1.5.0] - 2025-09-03

### Added
- **Density Analysis Engine**: Complete spatial concentration analysis module with areal and crowd density calculations
- **Density API Endpoints**: Full FastAPI integration with RESTful endpoints for density analysis
- **Comprehensive Test Suite**: 279 test cases with 100% pass rate for density analysis validation
- **Performance Optimizations**: NumPy vectorized operations for concurrent runner calculations
- **Narrative Smoothing**: Sustained period analysis to avoid per-bin noise in reporting
- **Pluggable Width Providers**: Architecture for future GPX-based dynamic width calculation
- **Critical Validation System**: Edge case handling for short segments, invalid width_m, and data quality issues

### Density Analysis Features
- **Areal Density**: Runners per square meter (runners/m²) for spatial concentration analysis
- **Crowd Density**: Runners per meter of course length (runners/m) for linear concentration
- **Level of Service (LOS) Classification**: 
  - Areal: Comfortable (<1.0), Busy (1.0-1.8), Constrained (≥1.8)
  - Crowd: Low (<1.5), Medium (1.5-3.0), High (≥3.0)
- **Time-Over-Threshold (TOT) Metrics**: Operational planning for high-density periods
- **Sustained Period Analysis**: Minimum 2-minute sustained LOS periods for meaningful insights
- **Independent Runner Counts**: Density calculates ALL runners in segment (different from temporal flow context)

### API Integration
- **POST /api/density/analyze**: Full density analysis for all segments
- **GET /api/density/segment/{segment_id}**: Single segment analysis with detailed results
- **GET /api/density/summary**: Summary data for all segments
- **GET /api/density/health**: Health check endpoint
- **Configurable Parameters**: JSON configuration overrides for all density parameters
- **Width Provider Selection**: Static (segments.csv) or dynamic (future GPX) width calculation

### Technical Implementation
- **Data Structures**: Dataclass-based design with DensityConfig, SegmentMeta, DensityResult, DensitySummary
- **Validation System**: Comprehensive segment validation with flagging (width_missing, short_segment, edge_case)
- **Performance**: Vectorized NumPy operations for 36 segments × thousands of time bins
- **Error Handling**: Robust error handling with proper logging and graceful degradation
- **Integration**: Seamless integration with existing FastAPI architecture (v1.6.0)

### Testing & Validation
- **Comprehensive Test Suite**: 279 test cases covering all functionality
- **100% Pass Rate**: All tests passing with proper tolerances (epsilon 1e-6, ±1 bin tolerance)
- **Performance Validation**: <5s single segment, <120s all segments analysis
- **Edge Case Testing**: Short segments, invalid width_m, boundary values, narrative smoothing
- **Real Data Validation**: All 36 segments processed successfully with real pace data

### Files
- `app/density.py` - Core density analysis engine with all calculations and validation
- `app/density_api.py` - FastAPI endpoints for density analysis
- `test_density_comprehensive.py` - Comprehensive test suite with 279 test cases
- `density_test_results.json` - Test results with 100% pass rate
- `docs/v1.6.0-density-analysis-requirements.md` - Complete requirements and workplan
- `app/main.py` - Updated to v1.6.0 with density API integration

## [v1.5.0] - 2025-09-03

### Added
- **Temporal Flow Analysis Engine**: Complete rewrite of overtake detection with comprehensive temporal flow analysis
- **12 Major Reporting Enhancements**: 
  - Enhanced labeling with event-specific names (10K, Half, Full) instead of generic A/B
  - Configurable conflict length (default 100m) for convergence zone analysis
  - Flow type classification (overtake, merge, diverge) in segments.csv
  - Entry window information with overlap duration calculations
  - Overtake percentage classification (Significant >20%, Meaningful >15%, Notable >5%, Minimal <5%)
  - Unique encounters counting (distinct cross-event pairs)
  - Participants involved counting (union of all runners in encounters)
  - Deep dive analysis for all overtake segments with comprehensive metrics
  - Prior segment analysis for segments with logical predecessors
  - Distance progression charts and Time-Over-Threshold (TOT) metrics
  - Enhanced narrative generation with contextual summaries
  - L1 Deep Dive Analysis format integration
- **Comprehensive Test Framework**: Full validation system for all 36 segments with expected vs actual comparison
- **Prior Segment Tracking**: Added `prior_segment_id` column to segments.csv for enhanced analysis
- **JSON API Serialization**: Fixed NaN value handling for proper API responses

### Changed
- **Architecture**: Complete separation of temporal flow analysis from density analysis
- **Algorithm Logic**: Replaced time-window presence with precise temporal overlap detection
- **Segment Processing**: Now processes ALL 36 segments (not just overtake_flag = 'y') for comprehensive reporting
- **Convergence Detection**: Only reports convergence points when actual temporal overlaps occur
- **Performance**: Vectorized operations for overlap calculations with pandas optimization
- **Terminology**: Consistent use of "overtake" vs "overlap" for operational precision

### Fixed
- **Critical Data Issue**: Resolved missing runner counts and entry/exit times for 18 non-overtake segments
- **JSON Serialization**: Fixed NaN values in prior_segment_id causing 500 errors in API responses
- **Precision Issues**: Minor floating-point precision differences in range values (functionally equivalent)
- **Segment Filtering**: Modified logic to process all segments while only calculating convergence for overtake segments
- **Main.py Validation**: All endpoints now working correctly with proper JSON responses

### Technical Details
- **Total Segments**: 36 (18 overtake + 18 non-overtake)
- **Segments with Convergence**: 11 (only when actual temporal overlaps occur)
- **Validation Results**: 100% pass rate (36/36 segments) in comprehensive testing
- **API Endpoints**: Temporal flow, density, and combined report endpoints fully functional
- **Deep Dive Analysis**: Comprehensive metrics for all overtake segments including timing, runner characteristics, and contextual analysis

### Files
- `app/temporal_flow.py` - Complete temporal flow analysis engine with all enhancements
- `data/segments.csv` - Enhanced with flow_type and prior_segment_id columns
- `comprehensive_test_comparison_report.csv` - Full validation framework for GitHub workflow
- `app/main.py` - Updated API endpoints with proper JSON serialization
- Various audit reports and validation documents

### Validation Framework
- **Comprehensive Test Report**: 39-column comparison CSV with expected vs actual values
- **Pass/Fail Status**: Automated validation with detailed difference tracking
- **Critical Failure Detection**: Identifies missing data and calculation errors
- **GitHub Workflow Ready**: Complete framework for automated testing and validation

## [v1.4.1] - 2025-09-01

### Added
- **Overtake Detection Logic**: Implemented convergence zone-based overtaking detection for A1c and B1 segments
- **Segment Validation Utility**: New `segment_validator.py` for bottom-up verification of algorithm results
- **Comprehensive CSV Reporting**: Enhanced exports with human-readable summaries and validation results
- **Start Offset Integration**: Proper handling of staggered start times in timing calculations

### Changed
- **Terminology**: Shifted from "overlap" to "overtake" for operational precision
- **Algorithm Logic**: Replaced time-window presence with precise overtaking event detection
- **Performance**: Optimized overlap calculations from O(n²) to vectorized operations

### Fixed
- **Timing Accuracy**: Corrected arrival time calculations with start_offset integration
- **Count Precision**: Eliminated overcounting issues in B1 segment validation
- **Data Extraction**: Fixed runner ID range extraction in validation utility

### Technical Details
- **A1c Validation**: Confirmed 22 vs 288 runners (algorithm accurate)
- **B1 Validation**: Confirmed 71 vs 29 runners (algorithm accurate)
- **Convergence Points**: A1c at 2.36km, B1 at 3.48km
- **Validation Method**: Runner-by-runner time-interval intersection analysis

### Files
- `test_utilities/segment_validator.py` - New validation utility
- `app/overlap.py` - Enhanced overtake detection
- `app/main.py` - Updated API endpoints
- Various audit reports and test data files

## [v1.4.0] - 2025-08-31
- Branch only with broken back-end code. 
- Elephant graveyard at some point. 

## [v1.3.9] - 2025-08-31

### Added
- **Overlap Narrative Text API** (`/api/overlap.narrative.text`) - Human-readable overlap analysis with summary statistics
- **Overlap CSV Export API** (`/api/overlap.narrative.csv`) - Export overlap analysis to CSV with timestamped filenames
- **Dynamic Segment Loading** - All endpoints now load segments from `overlaps.csv` instead of hardcoded lists
- **Makefile Commands** - `make overlaps` for narrative text and `make overlaps-csv` for CSV export
- **Start Offset Support** - Accurate runner timing with individual start delays from `your_pace_data.csv`
- **Summary Statistics** - Total segments, overlap count, overlap rate, and top 3 segments by peak runner count
- **Enhanced Narrative Format** - Emojis, clear formatting, fastest/slowest runner labels, and direction indicators
- **Segment Filtering** - Support for `?seg_id=` parameter to analyze individual segments
- **Tolerance Parameters** - Configurable time tolerance for overlap detection

### Changed
- **Architecture Separation** - Moved overlap logic from `density.py` to dedicated `overlap.py` module
- **Single Source of Truth** - All endpoints now use `overlaps.csv` for segment definitions
- **Map Endpoint Updates** - `/api/segments.geojson` now dynamically loads from `overlaps.csv`
- **Fallback Safety** - Graceful fallback to hardcoded segments if CSV loading fails

### Fixed
- **Segment Consistency** - All endpoints now use identical segment definitions
- **Runner Timing Accuracy** - Proper handling of staggered start times with `start_offset`
- **Overlap Detection Logic** - Improved detection of actual overtaking vs. co-location
- **CSV Export Format** - Correct filename format (`YYYY-MM-DD_HHMM_overlaps.csv`)

### Technical Details
- **New Dependencies**: Enhanced pandas usage for CSV processing
- **API Version**: Updated to v1.3.9-dev
- **File Structure**: Clean separation between density and overlap functionality
- **Error Handling**: Robust fallback mechanisms for CSV loading failures

## [v1.3.8] - 2025-08-31

## [v1.3.7] - 2025-08-31

## [v1.3.6] - 2025-08-30

## [v1.3.5] - 2025-08-30

### Added
- `/version` endpoint now exposes app version, git SHA, and build timestamp.
- New `/api/density.summary` endpoint for compact zone reporting (paired with new `smoke-summary-*` Make targets).
- Extended `/api/peaks.csv` to include `zone_by` and `zone_cuts` headers, with support for both areal and crowd metrics.
- New Makefile smoke tests:
  - `smoke-areal` and `smoke-crowd` for density checks.
  - `smoke-peaks`, `smoke-peaks-areal`, and `smoke-peaks-crowd` for CSV validation.
  - `smoke-summary-areal` and `smoke-summary-crowd` for compact summaries.

### Changed
- Improved error messages: `_fail_422` and `_validate_overlaps` now surface `seg_id` context where available.
- Cleaned up code quality in `density.py`:
  - Removed duplicate imports.
  - Added proper type hints and standardized constants.
  - Replaced “magic numbers” with named constants (e.g., `EPSILON`).

### Fixed
- Corrected async handling in endpoints using `Request.json()` (notably `/api/peaks.csv`).
- Standardized error handling across endpoints for consistent 422 vs 500 responses.

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
  - GitHub Actions workflow for deployment (`deploy-and-test.yml`).  
  - Smoke tests (consolidated into `deploy-and-test.yml`) with badges in README.md.  
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
