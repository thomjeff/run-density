# Canonical execution paths (Issue #798)

**Product name:** Runflow  
**Repository name:** `run-density` (historical; density was the original scope)  
**Audience:** maintainers and coding agents  
**Status:** living document — update when paths change

This page answers: *what is the supported path today?* Names like `new_*` or `legacy` are **not** authoritative; this ledger and the [deprecation ledger](deprecation-ledger.md) are.

---

## 1. Analysis (v2) — canonical

```text
UI Build (Package → Run analysis)
  or POST /runflow/v2/analyze
        │
        ▼
app/routes/v2/analyze.py
        │
        ▼
app/core/v2/analysis_submit.py  (submit_v2_analysis / run_analysis_background)
        │
        ▼
app/core/v2/pipeline.py
        │
        ├─ analysis.json (SSOT for the run)
        ├─ density:  app/core/v2/density.py  → analyze_density_segments_v2
        ├─ flow:     app/core/v2/flow.py     → analyze_temporal_flow_segments_v2
        ├─ bins:     app/core/v2/bins.py     → generate_bins_v2
        ├─ reports:  app/core/v2/reports.py  → generate_reports_per_day
        └─ artifacts / overlaps / UI helpers as invoked by the pipeline
```

**Run storage root:** `runflow/analysis/{run_id}/` (container: `/app/runflow/...`).  
**Do not** treat flat legacy `app/main.py` report-generation endpoints as the primary authoring path; Build → package analysis → v2 is canonical.

---

## 2. Density report generation — live call graph

Despite “DEPRECATED” banners on `new_*` modules, **production density Markdown still flows through them**:

```text
app/core/v2/reports.py
  generate_density_report_v2(...)
        │
        ▼
app/density_report.py
  generate_new_density_report_issue246(...)
        │
        ▼
app/new_density_report.py
  generate_new_density_report(...)
        │
        ├─ app/new_flagging.py          (also used from app/save_bins.py)
        └─ app/new_density_template_engine.py
             NewDensityTemplateEngine
```

**Disposition (Phase 6):** rename/move to a canonical package (e.g. `app/core/reports/density/`). Do **not** delete `new_*` until callers are retargeted and ledger removal gates pass.

Related: bin flagging during save uses `app/new_flagging.apply_new_flagging` from `app/save_bins.py`.

---

## 3. Flow report generation — live call graph

```text
app/core/v2/reports.py
  generate_flow_report_v2(...)
        │
        ├─ app/flow_report.generate_temporal_flow_report
        └─ app/flow_report.export_temporal_flow_csv

Core interval/overlap math:
  app/core/flow/flow.py   (large module; Phase 9 split candidates)
  orchestrated via app/core/v2/flow.py
```

Issue #600: **Flow.csv** is the operator artifact; Flow.md generation is deprecated.

---

## 4. HTTP composition root

| Concern | Canonical module | Notes |
|---------|------------------|--------|
| App entry (local) | `app/main.py` | Full UI + APIs |
| App entry (cloud skinny) | `app/cloud_app.py` | Read-oriented subset |
| v2 analyze | `app/routes/v2/analyze.py` | Prefix `/runflow/v2` |
| Reports list/download UI API | `app/routes/api_reports.py` | Used by frontend |
| Empty `/reports` shim | ~~removed~~ | Phase 1 deleted empty router |
| Flow API | `app/api/flow.py` | Composed directly from `main.py` (Phase 1) |
| Bidirectional API | `app/api/bidirectional.py` | Composed directly from `main.py` (Phase 1) |
| Build / packages | `app/routes/api_config_packages.py` | Large surface; org legs + packages |
| Results UI pages | `app/routes/ui.py` | Jinja pages |

---

## 5. Frontend chrome

| Path | Status |
|------|--------|
| Classic header/nav in `base.html` | **To be removed** — Tabler-only cutover (Phase 7) |
| Tabler shell (`?ui=tabler` today) | **Adopt as sole UI** (Phase 7 makes default; drop Classic) |
| Results pages | Shared templates; chrome from `base.html` + `run_context.html` |
| Build hub | `race_configuration.html` + map/recipe JS modules |

Until Phase 7, preview remains opt-in via `?ui=tabler` (Issue #796 / v2.0.11).

---

## 6. Configuration authoring

```text
Build UI (Legs / Courses / Packages)
        │
        ▼
app/routes/api_config_packages.py
        │
        ▼
app/core/config_package/*   (legs, saved courses, org library, recipes, analysis launch)
        │
        ▼
Package on disk under runflow/config/...
        │
        ▼
Run analysis → v2 pipeline (section 1)
```

Legacy course-mapping routes may still exist for compatibility; Race Configuration / Build is the supported authoring UX.

---

## 7. What is *not* canonical

- Relying on module names containing `new_`, `legacy`, or `old` to decide delete vs keep.
- Fabricated report metadata (`window_s = 30`, `bin_km = 0.2` TODOs in `new_density_report.py`) — fix in Phase 5.
- Host/container path rewrite unified in `app.utils.path_mapper` — Phase 4 ✓.
- Start-time contract unified in `app.core.v2.start_time` (300–1200) — Phase 2 ✓.

---

## 8. Related docs

- [Deprecation ledger](deprecation-ledger.md) — dispositions and removal gates  
- [Domain glossary](domain-glossary.md) — Phase 3 (naming)  
- [Frontend UI contract](../dev-guides/frontend-ui.md)  
- [Developer guide](../dev-guides/developer-guide.md)
