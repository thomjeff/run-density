# Architecture Review Responses for Issue #279

Concrete file paths and code snippets for ChatGPT's cherry-pick decision.

---

## 1. SSOT Loader (keep) ✅

### Location
**File**: `frontend/common/config.py` (69 lines)

### API Signature
```python
def load_rulebook() -> dict:
    """
    Load the density rulebook YAML (SSOT for LOS thresholds and operational policy).
    
    Returns:
        dict: Parsed rulebook containing globals.los_thresholds and operational rules
    
    Environment Variables:
        RUNFLOW_RULEBOOK_YML: Override default path (for testing/sandboxing)
    """
    path = os.getenv("RUNFLOW_RULEBOOK_YML", "config/density_rulebook.yml")
    return yaml.safe_load(Path(path).read_text())


def load_reporting() -> dict:
    """
    Load the reporting configuration YAML (SSOT for LOS colors and presentation).
    
    Returns:
        dict: Parsed reporting config containing reporting.los_colors and display settings
    
    Environment Variables:
        RUNFLOW_REPORTING_YML: Override default path (for testing/sandboxing)
    """
    path = os.getenv("RUNFLOW_REPORTING_YML", "config/reporting.yml")
    return yaml.safe_load(Path(path).read_text())
```

### Usage Pattern
```python
from frontend.common.config import load_rulebook, load_reporting

# Get LOS thresholds (analytics)
rulebook = load_rulebook()
los_bands = rulebook["globals"]["los_thresholds"]  # A..F: {label, min, max}

# Get LOS colors (presentation)
reporting = load_reporting()
los_colors = reporting["reporting"]["los_colors"]  # A..F → #hex
```

### YAML Keys Referenced
- `config/density_rulebook.yml` → `globals.los_thresholds` (authoritative for classification)
- `config/reporting.yml` → `reporting.los_colors` (authoritative for display)

**Status**: ✅ **KEEP** - Zero hardcoded values, reusable for Issue #279 templates

---

## 2. Provenance Badge (keep) ✅

### Location
**File**: `frontend/validation/scripts/write_provenance_badge.py`

### Implementation
```python
from jinja2 import Template
import json
from pathlib import Path

def write_badge(meta_path: str, out_path: str):
    """
    Generate provenance HTML badge from meta.json.
    
    Args:
        meta_path: Path to meta.json
        out_path: Output path for HTML snippet
    """
    meta = json.loads(Path(meta_path).read_text())
    tpl = Template(Path("frontend/validation/templates/_provenance.html").read_text())
    html = tpl.render(meta=meta)
    Path(out_path).write_text(html)
```

### Template
**File**: `frontend/validation/templates/_provenance.html`
```html
<div class="provenance" style="font:14px system-ui, sans-serif; opacity:0.9">
  ✅ Validated • Runflow {{ meta.run_timestamp }} • Hash {{ (meta.run_hash or '')[:8] }} • Env {{ meta.environment }}
</div>
```

### Expected Context Keys
```python
meta = {
    "run_timestamp": "2025-10-18 14:30:00",  # ISO format
    "run_hash": "5cfefbe9a1b2c3d4...",        # SHA256 hash
    "environment": "local" | "cloud",         # Deployment env
    "rulebook_hash": "abc123...",             # Config version
    "reporting_hash": "def456..."             # Config version
}
```

**Status**: ✅ **KEEP** - Direct Jinja usage, perfect for Issue #279 templates

---

## 3. LOS Mapping (keep) ✅

### Location
**File**: `frontend/map/scripts/generate_map.py` (lines 77, 109)

### Implementation
```python
from frontend.common.config import load_reporting

# Load YAML configuration (NOT hardcoded)
reporting = load_reporting()
los_colors = reporting["reporting"]["los_colors"]  # A..F → color hex

# Apply to segment styling
for segment in segments:
    worst_los = segment.get("worst_los", "A")
    color = los_colors.get(worst_los, "#9e9e9e")  # Fallback gray
    # ... apply color to map feature
```

### YAML Dependency
**File**: `config/reporting.yml`
```yaml
reporting:
  los_colors:
    A: "#4CAF50"  # Green
    B: "#8BC34A"  # Light Green
    C: "#FFC107"  # Amber
    D: "#FF9800"  # Orange
    E: "#FF5722"  # Deep Orange
    F: "#F44336"  # Red
```

### Verification
```bash
$ grep -r "#4CAF50\|#FF5722" app/ frontend/
# Returns: Only found in config/reporting.yml
# NO hardcoded colors in code ✅
```

**Status**: ✅ **KEEP** - Function is reusable for Issue #279 Leaflet client-side styling

---

## 4. Storage Adapter (review) ⚠️

### Primary Location
**File**: `app/storage_service.py` (337 lines)

### API Signature
```python
class StorageService:
    """
    Unified storage service for local and Cloud Storage operations.
    
    Automatically detects environment and uses appropriate storage method:
    - Local development: File system storage
    - Cloud Run production: Google Cloud Storage
    """
    
    def save_file(self, file_path: str, content: str) -> str:
        """Save file to local or GCS based on environment."""
        
    def load_file(self, file_path: str) -> Optional[str]:
        """Load file from local or GCS based on environment."""
        
    def load_json(self, file_path: str) -> Dict[str, Any]:
        """Load and parse JSON file."""
        
    def list_files(self, date: str, pattern: Optional[str] = None) -> List[str]:
        """List files in a date directory."""
        
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
```

### Environment Detection
```python
def _detect_environment(self):
    """Detect if running in Cloud Run or local environment."""
    # Check for Cloud Run environment variables
    if os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        self.config.use_cloud_storage = True
        self.config.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        logger.info("Detected Cloud Run environment - using Cloud Storage")
    else:
        self.config.use_cloud_storage = False
        logger.info("Detected local environment - using file system storage")
```

### Files It Can Read
✅ `segments.geojson` - Yes, via `load_file()`  
✅ `segment_metrics.json` - Yes, via `load_json()`  
✅ `flags.json` - Yes, via `load_json()`  
✅ `meta.json` - Yes, via `load_json()`  
✅ `bin_details/*.csv` - Yes, via `load_file()` with path  
✅ `heatmaps/*.png` - Yes, via `load_file()` (returns bytes)

### Local vs Cloud Run Behavior
```python
# LOCAL
storage = StorageService()  # Detects local, uses file system
content = storage.load_file("reports/2025-10-18/density.md")
# → Reads from ./reports/2025-10-18/density.md

# CLOUD RUN
storage = StorageService()  # Detects Cloud Run, uses GCS
content = storage.load_file("reports/2025-10-18/density.md")
# → Reads from gs://run-density-reports/reports/2025-10-18/density.md
```

### GitHub Runtime Dependency
✅ **NO GitHub dependency** - Uses only:
- Local: Python `pathlib`, `os`
- Cloud: `google-cloud-storage` library (GCS only)

**Status**: ⚠️ **REVIEW/ADAPT** - Good foundation, but Issue #279 needs simpler adapter:
- Current: Singleton pattern, heavy integration with `app/main.py`
- Issue #279: Needs lightweight adapter in `app/storage.py` per spec
- **Recommendation**: Extract core logic, simplify interface

---

## 5. Heavy Deps (revert) ❌

### App Runtime (web server paths)

**Check**: Do any `app/` files import `folium`, `geopandas`, or `matplotlib`?

```bash
$ grep -r "^import folium\|^import matplotlib\|^from folium\|^from matplotlib" app/
# No results ✅
```

```bash
$ grep -r "^import geopandas\|^from geopandas" app/
app/bin_geometries.py:import geopandas as gpd
```

**File**: `app/bin_geometries.py` (402 lines)
- **Purpose**: Generates bin polygons for map visualization (Issue #249)
- **Used By**: `app/map_api.py` → `/api/map/bins` endpoint
- **Runtime**: Generates GeoJSON at runtime when requested

### Frontend Generation Scripts (offline only)

**All heavy imports isolated to `frontend/` scripts:**

```bash
$ grep -r "^import folium\|^import matplotlib" frontend/
frontend/map/scripts/generate_map.py:import folium
frontend/dashboard/scripts/charts.py:import matplotlib.pyplot as plt
frontend/reports/scripts/generate_sparklines.py:import matplotlib.pyplot as plt
frontend/reports/scripts/generate_minimaps.py:import matplotlib.pyplot as plt
```

### Analysis

| File | Import | Runtime | Removable for Issue #279? |
|------|--------|---------|---------------------------|
| `app/bin_geometries.py` | `geopandas` | YES (API endpoint) | ⚠️ **KEEP** (used by current map API) |
| `frontend/map/scripts/generate_map.py` | `folium`, `matplotlib` | NO (offline) | ✅ **REMOVE** (replaced by Leaflet) |
| `frontend/dashboard/scripts/` | `matplotlib` | NO (offline) | ✅ **REMOVE** (replaced by templates) |
| `frontend/reports/scripts/` | `matplotlib` | NO (offline) | ✅ **REMOVE** (replaced by templates) |

**Status**: 
- ❌ **REMOVE**: All `frontend/*/scripts/` generation code (offline, replaced by Issue #279)
- ⚠️ **KEEP**: `app/bin_geometries.py` (used by current `/api/map/bins` endpoint)
- ⚠️ **DECISION NEEDED**: Does Issue #279 need runtime bin geometry generation or pre-generated GeoJSON?

---

## 6. Requirements (revert to one) ✅

### Current Structure (v1.6.42 → main)

**v1.6.42**: Single `requirements.txt` (25 lines)
```
fastapi>=0.104.0
pandas>=2.0.0
google-cloud-storage>=2.10.0
# ... etc
```

**Current Main**: Split into 3 files
```
requirements.txt → Composite (includes all 3 below)
requirements-core.txt → Runtime (33 lines)
requirements-frontend.txt → Generation scripts (13 lines)
requirements-dev.txt → Testing (5 lines)
```

### Diff Summary

```diff
--- v1.6.42/requirements.txt
+++ main/requirements.txt
- Direct list of 25 dependencies
+ Composite file: -r requirements-core.txt, -r requirements-frontend.txt, -r requirements-dev.txt

# NEW in requirements-core.txt:
+ geopandas>=0.14.0  # Issue #249 - bin geometries
+ pyproj>=3.6.0      # Issue #249 - coordinate transforms

# NEW in requirements-frontend.txt:
+ folium>=0.17       # Phase 2 - static map generation
+ matplotlib>=3.8    # Phase 3/4 - charts, sparklines, minimaps
+ markdown>=3.6      # Phase 4 - report conversion

# NEW in requirements-dev.txt:
+ pytest>=8.0        # (was unlisted before)
```

### Proposed for Issue #279

**Single `requirements.txt` for web app (Cloud Run):**

```txt
# FastAPI Web Server (Issue #279)
fastapi>=0.104.0
starlette>=0.27.0
uvicorn>=0.24.0
gunicorn>=21.2.0
jinja2>=3.1.0

# Data Models
pydantic>=2.5.0
typing-extensions>=4.8.0

# Analytics (density/flow calculations)
pandas>=2.0.0
numpy>=1.24.0

# HTTP & Config
requests>=2.31.0
httpx>=0.24.0
pyyaml>=6.0

# Cloud Storage (GCS adapter)
google-cloud-storage>=2.10.0

# Bin Dataset Generation (Issue #198)
pyarrow>=10.0.0
shapely>=2.0.0

# DECISION NEEDED: Keep geopandas for runtime bin geometries?
# geopandas>=0.14.0  # Only if /api/map/bins needed
# pyproj>=3.6.0      # Only if /api/map/bins needed

# REMOVED (replaced by Leaflet client-side):
# - folium (static map generation → Leaflet)
# - matplotlib (charts → pre-generated or CSS)
# - markdown (reports → Jinja templates)
```

**Status**: ✅ **RECOMMEND**: Single file, ~20 deps (vs 33+13+5=51 current)

---

## 7. Manifest/Bundler (review) ⚠️

### Generation

**File**: `frontend/release/build_bundle.py` (162 lines)

**What it does:**
1. Collects generated HTML artifacts (`map.html`, `dashboard.html`, `density.html`)
2. Computes SHA256 hashes for all files
3. Packages into `release/runflow-<hash>.zip`
4. Creates `release/manifest.json` with provenance

**Example Manifest:**
```json
{
  "artifacts": {
    "frontend/map/output/map.html": {
      "sha256": "5cfefbe9a1b2c3d4...",
      "size": 524288
    }
  },
  "assets": {
    "frontend/reports/output/mini_maps": {
      "frontend/reports/output/mini_maps/A1.png": "abc123..."
    }
  },
  "meta": {
    "run_hash": "5cfefbe9...",
    "environment": "local",
    "run_timestamp": "2025-10-18T14:30:00Z"
  },
  "build_timestamp": "2025-10-18T20:15:00Z"
}
```

### Consumption

**File**: `app/map_api.py` (lines 56-160)

**Endpoint**: `GET /api/map/manifest`

```python
@router.get("/map/manifest")
async def get_map_manifest():
    """
    Get map manifest with available dates and metadata.
    Currently returns list of available map files from storage.
    """
    try:
        storage_service = get_storage_service()
        
        # List available map files
        date = datetime.now().strftime("%Y-%m-%d")
        map_files = storage_service.list_files(date, "map_data")
        
        return {
            "available_dates": [date],
            "latest_file": map_files[0] if map_files else None,
            "count": len(map_files)
        }
    except Exception as e:
        logger.error(f"Error getting map manifest: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map manifest: {e}")
```

### Analysis

**Current Approach:**
- Manifest used for **release bundling** (static artifact deployment)
- Web app lists files via `storage_service.list_files()`, NOT by reading manifest.json
- ZIP bundling is for **external distribution**, not runtime dependency

**Issue #279 Approach:**
- Reports page lists available artifacts (Density.md, Flow.csv, etc.)
- Can use `storage.list_paths(prefix="reports/2025-10-18")` (no manifest needed)
- No ZIP bundling at runtime

**Status**: ⚠️ **OPTIONAL** - Manifest/bundler not needed for Issue #279 web app
- ✅ Web app can list reports without manifest (use `storage.list_paths()`)
- ❌ Remove `frontend/release/` (ZIP bundling not part of Issue #279)
- ℹ️ Keep `manifest.json` concept for future static deployments (GitHub Pages)

---

## Summary Table

| # | Component | Status | Action for Issue #279 |
|---|-----------|--------|----------------------|
| 1 | SSOT Loader (`frontend/common/config.py`) | ✅ KEEP | Reuse directly in templates |
| 2 | Provenance Badge (`frontend/validation/`) | ✅ KEEP | Reuse Jinja partial |
| 3 | LOS Mapping (function in config loader) | ✅ KEEP | Reuse for Leaflet styling |
| 4 | Storage Adapter (`app/storage_service.py`) | ⚠️ ADAPT | Simplify per Issue #279 spec |
| 5 | Heavy Deps (folium, matplotlib in frontend/) | ❌ REMOVE | Delete `frontend/*/scripts/` |
| 6 | Requirements (split files) | ✅ CONSOLIDATE | Single runtime requirements.txt (~20 deps) |
| 7 | Manifest/Bundler (`frontend/release/`) | ❌ REMOVE | Not needed for Issue #279 |

---

## Files to KEEP (valuable infrastructure)

```bash
✅ frontend/common/config.py                      # SSOT loader
✅ frontend/validation/scripts/write_provenance_badge.py  # Badge generator
✅ frontend/validation/templates/_provenance.html # Badge template
✅ frontend/validation/data_contracts/schemas.py  # Pydantic schemas (adapt)
✅ analytics/export_frontend_artifacts.py         # Canonical export (adapt)
✅ app/rulebook.py                                # Centralized rulebook logic
✅ app/schema_resolver.py                         # Schema resolution
✅ app/utilization.py                             # P90 calculations
✅ app/new_flagging.py                            # Unified flagging
✅ tests/test_rulebook_flags.py                   # Valuable tests
✅ requirements-core.txt → requirements.txt       # Consolidate
```

---

## Files to REMOVE (conflicts with Issue #279)

```bash
❌ frontend/dashboard/scripts/                    # Replace with Jinja templates
❌ frontend/map/scripts/                          # Replace with Leaflet client-side
❌ frontend/reports/scripts/                      # Replace with template-based reports
❌ frontend/e2e/e2e_validate.py                   # May need adaptation
❌ frontend/release/                              # Different deployment model
⚠️ app/map_api.py                                # Review for route conflicts
⚠️ app/new_density_report.py                     # May be superseded by templates
```

---

## Recommended Cherry-Pick Strategy

**Option 3: Hybrid Approach**

1. **Create branch from v1.6.42**: `git checkout -b dev/issue-279 v1.6.42`
2. **Cherry-pick infrastructure commits**:
   - Issue #254 (rulebook.py, utilization.py, new_flagging.py)
   - Issue #263 dependencies split (requirements-core.txt concept)
   - Phase 1 SSOT loader (frontend/common/config.py)
   - Phase 1 Pydantic schemas (frontend/validation/data_contracts/)
   - Phase 1 Provenance badge (frontend/validation/templates/_provenance.html)
3. **Skip generation scripts**:
   - Phase 2 (frontend/map/scripts/)
   - Phase 3 (frontend/dashboard/scripts/)
   - Phase 4 (frontend/reports/scripts/)
   - Phase 5 (frontend/release/)
4. **Adapt storage adapter**:
   - Simplify `app/storage_service.py` → `app/storage.py` per Issue #279 spec
5. **Consolidate requirements**:
   - Merge `requirements-core.txt` → `requirements.txt`
   - Remove folium, matplotlib, markdown

**Total LOC preserved**: ~1,500 (vs 5,500+ total)  
**Total LOC removed**: ~4,000 (generation scripts)

