# Changelog

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
