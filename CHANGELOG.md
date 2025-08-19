# Changelog

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
