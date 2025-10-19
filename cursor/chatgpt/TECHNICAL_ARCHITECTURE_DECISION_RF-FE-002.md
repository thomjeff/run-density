# 🧭 Technical Architecture & Implementation Plan — Epic RF-FE-002

**Author**: ChatGPT (Technical Architect)  
**Based on**: Architecture Review Responses Issue 279 + Work Summary v1.6.42→Current  
**Date**: 2025-10-19

---

## ✅ Architectural Decision

After full review of `ARCHITECTURE_REVIEW_RESPONSES_ISSUE_279.md` and `WORK_SUMMARY_v1.6.42_to_CURRENT.md`,
we are proceeding with **Option 3 — Hybrid Approach**:

**🧩 Baseline v1.6.42 → New Branch `feature/rf-fe-002`**  
Preserve proven infrastructure; remove static-site code; keep runtime = local = cloud parity.

---

## ⚙️ Key Architecture Summary

| Area | Decision | Rationale |
|------|----------|-----------|
| **SSOT Loader** | ✅ Keep | `frontend/common/config.py` loads YAML (`density_rulebook.yml`, `reporting.yml`) – single source of truth for LOS thresholds and colors. |
| **Provenance Badge** | ✅ Keep | `frontend/validation/templates/_provenance.html` → reused as Jinja partial; reads `meta.json`. |
| **LOS Mapping** | ✅ Keep | Uses `reporting.yml` for LOS colors (A–F). |
| **Storage Adapter** | ⚠️ Adapt → ✅ | Simplify `app/storage_service.py` → lean `app/storage.py` with `read_json/read_text/list_paths` etc. Local = GCS behavior; no GitHub runtime calls. |
| **Heavy Deps** | ❌ Remove from web runtime | Eliminate folium, geopandas, matplotlib. Heatmaps served as pre-generated PNGs from analytics. |
| **Requirements** | ✅ Consolidate | Return to single `requirements.txt` (~20 deps) for web runtime only. |
| **Manifest/Bundler** | ❌ Remove | Web app lists reports directly via storage; no ZIP bundles or manifest files. |

---

## 📁 File-Level Actions

### ✅ Keep / Import

```
frontend/common/config.py                  # SSOT loader
frontend/validation/templates/_provenance.html
tests/... (YAML coherence checks)
```

### ⚙️ Adapt

**`app/storage_service.py` → `app/storage.py`**

```python
class Storage:
    def __init__(self, mode: Literal["local","gcs"], root=None, bucket=None, prefix=None): ...
    def read_json(self, path): ...
    def read_text(self, path): ...
    def read_bytes(self, path): ...
    def exists(self, path): ...
    def mtime(self, path): ...
    def list_paths(self, prefix): ...
```

### ❌ Remove

```
frontend/*/scripts/
frontend/release/
Split requirements-*.txt
Any folium/geopandas/matplotlib imports in app path
```

---

## 🧱 Templates (7 Pages)

| Page | Purpose |
|------|---------|
| `password.html` | Authentication screen (index route) |
| `dashboard.html` | Main summary tiles + metrics |
| `segments.html` | Segment list + Leaflet map |
| `density.html` | Segment table + heatmap PNG + bin-level table |
| `flow.html` | Flow metrics table (sticky columns) |
| `reports.html` | Report listing (download links) |
| `health.html` | API endpoint + file checks + env status |

**Shared partials:**
- `_provenance.html`
- `_placeholders.html` ("Loading map data…", "No bin-level data …")

---

## 🎨 CSS and UX

- **Reuse v1.6.42 CSS** + add:
  - `.badge-los.badge-A..F` (colors from `reporting.yml`)
  - `.card`, `.kpi`, `.placeholder`, `.table-sticky`, `.legend`
  - Media query @ 768 px → Dashboard 2-column, Flow table scroll/sticky.
- **Accessible contrast** per Canva v2 mock (WCAG AA compliant).

---

## 📊 Data Bindings

| Environment | Source | Example Files |
|-------------|--------|---------------|
| **Local** | FS path `DATA_ROOT` | `segments.geojson`, `segment_metrics.json`, `flags.json`, `meta.json`, `bin_details/*.csv`, `heatmaps/*.png` |
| **Cloud Run** | GCS `GCS_BUCKET` + `GCS_PREFIX` | same structure as local |

**Page Bindings:**
- **Dashboard** → tiles from `runners.csv`, `segment_metrics.json`, `flags.json`.
- **Segments** → Leaflet map (`segments.geojson`) + tooltip with ID, name, length, width, direction, events.
- **Density** → heatmap PNGs or placeholders; bin-level table if CSV exists.
- **Reports** → list via `storage.list_paths("reports/")`.
- **Health** → check presence + timestamps + hashes.

---

## 🧩 Requirements (web runtime only)

```
fastapi
uvicorn
jinja2
python-multipart
pydantic
google-cloud-storage
google-auth
pyyaml
```

*(Leaflet via CDN; no folium/geopandas/matplotlib/markdown.)*

---

## 🚀 Cursor Task List

**Branch**: `feature/rf-fe-002` (off v1.6.42)

### 1️⃣ Environment Reset
- Delete split requirements files
- Create single `requirements.txt`
- Remove folium/geopandas/matplotlib imports

### 2️⃣ Add SSOT Loader + Provenance Partial
- Copy to `app/common/config.py` and `templates/partials/_provenance.html`
- Inject `meta.json` into Jinja context

### 3️⃣ Create Storage Adapter (`app/storage.py`)
- Detect local vs GCS via env vars (`RUNFLOW_ENV`, `DATA_ROOT`, `GCS_BUCKET`, `GCS_PREFIX`)

### 4️⃣ Template Scaffolding (7 Pages)
- Match Canva v2 mocks
- Add provenance pill (top right)
- Add placeholders for Density heatmap and Segment map

### 5️⃣ Leaflet Integration
- Load `segments.geojson`
- Style by `worst_los` mapping
- Tooltips with segment metadata

### 6️⃣ Bind Data
- Dashboard metrics
- Density & Flow tables
- Heatmap and bin-level details

### 7️⃣ Reports & Health
- Reports: list + download
- Health: env, timestamps, file presence, API ping

### 8️⃣ Parity Tests
- Run locally and on Cloud Run → identical behavior
- CI check: assert single `requirements.txt` and no heavy imports

---

## ⚠️ Risks & Mitigations

- **Missing heatmap** → placeholder + log
- **Missing worst_los** → compute from segment_metrics
- **Environment drift** → CI import guard and req file hash check

---

## ✅ Summary

- **Baseline**: v1.6.42
- **Approach**: Hybrid (clean app + modern frontend)
- **Output**: Fully functional Run-Crew Web UI aligned to Epic #279
- **Parity**: Local and Cloud Run identical
- **No static generation, no GitHub runtime, no heavy libs**

---

**@Cursor** — please use this comment as the authoritative implementation reference for Epic RF-FE-002.
Work should begin from v1.6.42 and follow the plan above.
ChatGPT will serve as the reviewing technical architect to ensure alignment and parity throughout delivery.

