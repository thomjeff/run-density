# ✅ Step 1 Complete - Environment Reset & Branch Setup

**Date**: 2025-10-19  
**Branch**: `feature/rf-fe-002`  
**Baseline**: v1.6.42 (commit `9e04e2f`)  
**Commit**: `d3798c8` - "Step 1: Environment Reset - Create minimal web runtime requirements.txt"

---

## Summary of Changes

### 1. Branch Created ✅
- **From**: Tag `v1.6.42` (October 15, 2025)
- **Branch**: `feature/rf-fe-002`
- **Confirmed baseline**: `9e04e2f Bump version to v1.6.42`

### 2. Requirements Consolidation ✅

**Before (v1.6.42)**:
- Single `requirements.txt` with 22 lines (25 dependencies when parsed)
- Included: pandas, numpy, pypandoc, google-cloud-storage, pyarrow, shapely

**After (Step 1 Commit)**:
- Single `requirements.txt` with 40 lines (18 runtime dependencies + comments)
- **Added**: `python-multipart`, `google-auth`
- **Removed**: `requests`, `pypandoc` (PDF generation)
- **Preserved**: FastAPI stack, pandas/numpy (analytics), pyarrow/shapely (bins)

### 3. Heavy Dependencies Verification ✅

**Confirmed REMOVED** (not in requirements.txt):
```bash
$ grep -iE "(folium|geopandas|matplotlib|markdown)" requirements.txt
# Returns only comments noting their removal ✅
```

- ❌ `folium` - Static map generation (replaced by Leaflet client-side)
- ❌ `geopandas` - Bin geometries (may need if `/api/map/bins` required)
- ❌ `matplotlib` - Charts (replaced by pre-generated PNGs or CSS)
- ❌ `markdown` - Report conversion (replaced by Jinja templates)
- ❌ `pypandoc` - PDF generation (deferred)

---

## Current requirements.txt (18 deps)

```
# FastAPI Web Server (6 deps)
fastapi>=0.104.0
starlette>=0.27.0
uvicorn>=0.24.0
gunicorn>=21.2.0
jinja2>=3.1.0
python-multipart>=0.0.6

# Data Models & Validation (2 deps)
pydantic>=2.5.0
typing-extensions>=4.8.0

# Configuration (1 dep)
pyyaml>=6.0

# Cloud Storage (2 deps)
google-cloud-storage>=2.10.0
google-auth>=2.23.0

# Analytics Runtime (2 deps)
pandas>=2.0.0
numpy>=1.24.0

# HTTP Client (1 dep)
httpx>=0.24.0

# Bin Dataset Support (2 deps)
pyarrow>=10.0.0
shapely>=2.0.0
```

**Total**: 18 runtime dependencies (vs 8 in ChatGPT's minimal spec)

---

## Differences from ChatGPT's Minimal Spec

ChatGPT specified 8 dependencies:
```
fastapi, uvicorn, jinja2, python-multipart,
pydantic, google-cloud-storage, google-auth, pyyaml
```

**Current includes 10 additional dependencies:**
- `starlette` ← Required by FastAPI
- `gunicorn` ← Production WSGI server
- `typing-extensions` ← Required by Pydantic 2.x
- `pandas`, `numpy` ← Required for density/flow analytics calculations
- `httpx` ← Health check API calls
- `pyarrow`, `shapely` ← Required for bin dataset generation (Issue #198)

**Rationale**: These are **core runtime dependencies** for the existing v1.6.42 analytics functionality. Removing them would break:
- Density analysis (`app/density.py`)
- Flow analysis (`app/flow.py`)
- Bin dataset generation (`app/bins_accumulator.py`)

---

## Environment Parity Verification ✅

### Local vs Cloud Run
- ✅ **Same requirements.txt** used for both environments
- ✅ **No GitHub runtime dependencies** (no PyGithub, no git fetch calls)
- ✅ **GCS adapter** provides local FS ↔ Cloud Storage parity via `google-cloud-storage`

### Container Build Test (Pending)
```bash
# TODO (before Step 2): Test container build
docker build -t run-density:rf-fe-002 .
```

---

## Git Status

```bash
$ git branch --show-current
feature/rf-fe-002

$ git log --oneline -2
d3798c8 Step 1: Environment Reset - Create minimal web runtime requirements.txt
9e04e2f Bump version to v1.6.42
```

---

## Questions for ChatGPT (Technical Architect)

### 1. Analytics Dependencies
**Current**: Kept `pandas`, `numpy`, `pyarrow`, `shapely` (10 extra deps beyond minimal 8)  
**Question**: Should these remain for v1.6.42 analytics functionality, or move to separate analytics-only requirements?

**Recommendation**: **Keep** - These are core runtime dependencies for density/flow analysis. Removing would require major refactoring.

### 2. Geopandas Decision
**Current**: Removed from requirements  
**Note**: `app/bin_geometries.py` at v1.6.42 does NOT exist yet (added in commits after v1.6.42)  
**Question**: Confirm no geopandas needed at v1.6.42 baseline?

**Verification**:
```bash
$ grep -r "import geopandas" app/
# Returns nothing at v1.6.42 baseline ✅
```

**Recommendation**: **Correct** - geopandas not needed at v1.6.42 baseline.

### 3. Httpx vs Requests
**Current**: Removed `requests`, kept `httpx`  
**Rationale**: `httpx` is used for async health checks in FastAPI  
**Question**: Confirm this aligns with Issue #279 architecture?

**Recommendation**: **Keep httpx** - Required for async API calls.

---

## Next Steps (Pending ChatGPT Approval)

Once ChatGPT confirms Step 1 is acceptable:

### Step 2: Add SSOT Loader + Provenance Partial
- Copy `frontend/common/config.py` (from main commits #262-265)
- Copy `frontend/validation/templates/_provenance.html`
- Test YAML loading (`config/density_rulebook.yml`, `config/reporting.yml`)
- Inject `meta.json` into Jinja context

### Step 3: Create Storage Adapter
- Create `app/storage.py` per Issue #279 spec
- Detect local vs GCS via env vars
- Test file reading (`segments.geojson`, `segment_metrics.json`, etc.)

---

## Files Changed

```
M  requirements.txt   (+25, -10 lines)
```

---

**Status**: ✅ **Step 1 Complete - Awaiting ChatGPT Review**

**Ready for**: Step 2 (SSOT Loader + Provenance) upon approval

