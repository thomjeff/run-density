# Changelog

## [1.1.4] — 2025-08-14
### Added
- Added Execution Time to API calls
- Hardened one-shot analysis prompt with structured checklist and acceptance criteria.
- Pre-run checklist validation for:
- CSV schema verification
- Parameter lock (start times, step size, time window)
- Event filtering
- Segment bounds confirmation
- Distinct-runner counting method
- Deterministic file naming convention:
   - {EventA}_vs_{EventB}_{X.XX}_{Y.YY}km_split_counts.csv
   - {EventA}_vs_{EventB}_{X.XX}_{Y.YY}km_split_counts.png
- Inline result preview: First 4 rows + peak row shown for quick sanity check.
- Optional hard gate for expected peak congestion values.

### Changed
- Replaced ad-hoc instructions with a single execution-grade SOP.
- Consolidated scattered notes into a unified markdown file for GitHub.
- Simplified follow-up prompts — only event names and km range now required.

### Fixed
- Eliminated early-step full-field counts for later-starting events.
- Prevented logic drift from reintroducing naive distance slicing or reliance on overlaps.csv for counts.

## [1.1.5] — 2025-08-13
### Added
- Test Runner scripts

## [1.1.4] — 2025-08-13
### Added
- Execution-time telemetry restored:
  - **CLI** prints `⏱️ Compute time: Ns`.
  - **API** returns `X-Compute-Seconds` response header.

### Changed
- Canonicalized step size naming across stack:
  - **CLI flag:** `--step-km` (alias `--step` retained for back-compat).
  - **API JSON:** `stepKm`.
  - Internals normalize to `step_km`.
- Hardened **segments** handling:
  - Case/whitespace-insensitive event matching.
  - Friendly 400s listing valid segments when no match.
- API response remains **plain text** (CLI parity) with debug headers:
  - `X-Request-UTC`, `X-Events-Seen`, `X-StepKm`, `X-Compute-Seconds`.

### Fixed
- Invocation failures caused by positional calls into `engine`; all calls are keyword-only via adapter.
- Crash when passing a DataFrame where a CSV path was required; API now persists filtered overlaps to temp CSV before calling engine.

### Notes
- Vercel timeout envelope remains the gating factor; `stepKm=0.03` is the practical lower bound on the Hobby tier without background jobs.

## v1.1.3 - 2025-08-12
### Changed
- License from Apache to MIT.

## v1.1.2 - 2025-08-12
### Added
- Summary CSV outputs are now written to a dedicated `results/` folder instead of the `examples/` directory.
- Maintains the existing date-time stamp (YYYY-MM-DDTHHMMSS) prefix for output files.
- Improved file organization for better separation of example data and generated run outputs.

## [1.1.1] - 2025-08-12
## Fixed
- Breaking errors by GPT4o.

## [1.1.0] - 2025-08-06
### Added
- Benchmark timing output: prints total computation time after analysis.
- Pre-filter optimization to eliminate non-overlapping runners before step scanning.
- NumPy broadcasting for vectorized arrival-time matrix computation, replacing Python loops.
- True multi-core parallelism via `ProcessPoolExecutor` in `engine.py`.
- Two-phase adaptive stepping (coarse + refined) to minimize detailed scanning steps.
- `--rank-by` CLI flag to choose summary ranking by `peak_ratio` (default) or `intensity`.
- Timestamped CSV export via `--export-summary <path>`, stored in `examples/` by default.

### Changed
- Refactored `detect_overlap.py` to include timing, ranking, and export functionality.
- Updated `engine.py` with performance optimizations while preserving existing CLI output.
- README updated with new usage instructions and examples.

### Fixed
- Removed unused JSONL export option.
- Clarified file permission instructions (`chmod +x detect_overlap.py`).
