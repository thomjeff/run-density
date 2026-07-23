# Deprecation ledger (Issue #798)

Track modules that look transitional or dead. **Do not delete from name alone.**  
Update this file in the same PR that changes disposition or removes a module.

**Legend**

| Disposition | Meaning |
|-------------|---------|
| **rename** | Live; name/location wrong — move/rename (do not delete first) |
| **remove** | Proven unused after gates — delete in listed phase |
| **shim** | Temporary re-export; dated removal |
| **keep** | Supported as-is |
| **investigate** | Callers or external use unclear |

**Removal gates (all required for `remove`):**

1. No internal callers after canonical imports  
2. No registered route / background entry  
3. No documented external compatibility promise (or shim expired)  
4. Route/artifact contract tests pass  
5. CHANGELOG + this ledger updated  

---

## Active ledger

| Module / symbol | Status today | Callers (summary) | Disposition | Target phase | Owner notes | Removal version |
|-----------------|--------------|-------------------|-------------|--------------|-------------|-----------------|
| `app/new_density_report.py` | **shim** | → `app.core.reports.density.report` | **shim** | Phase 6 ✓ | Remove after one release | next release |
| `app/new_density_template_engine.py` | **shim** | → `…density.template_engine` | **shim** | Phase 6 ✓ | Remove after one release | next release |
| `app/new_flagging.py` | **shim** | → `…density.flagging` | **shim** | Phase 6 ✓ | Remove after one release | next release |
| `app/core/reports/density/*` | **LIVE** canonical | v2 reports, `save_bins`, façade | **keep** | Phase 6 ✓ | Public API in package `__init__` | — |
| `app/density_report.py` | **LIVE** façade + legacy helpers | v2 reports, bins, `main.py` legacy endpoints | **keep** then thin | Phase 6 / 9 | `generate_density_report_markdown` (+ alias) | — |
| `app/flow_report.py` | **LIVE** | v2 `generate_flow_report_v2` | **keep** | — | Flow.md path deprecated; CSV kept | — |
| `app/routes/reports.py` | ~~Empty router~~ **REMOVED** | — | **remove** ✓ | Phase 1 | Frontend uses `api_reports` | Phase 1 |
| `app/routes/api_flow.py` | ~~Wildcard re-export~~ **REMOVED** | — | **remove** ✓ | Phase 1 | `main` imports `app.api.flow` | Phase 1 |
| `app/routes/api_bidirectional.py` | ~~Wildcard re-export~~ **REMOVED** | — | **remove** ✓ | Phase 1 | `main` imports `app.api.bidirectional` | Phase 1 |
| `app/core/flow/flow.py` `_ShardWriter` | ~~Unused~~ **REMOVED** | — | **remove** ✓ | Phase 1 | Also `_write_index_csv`, `_write_topk_csv` | Phase 1 |
| `app/utils/constants.py` `EVENT_DURATION_MINUTES` | Deprecated dict; capitalized dupes | v1 compatibility risk | **investigate** → remove or v1-only adapter | Phase 8 | Confirm v1 endpoint retirement | TBD |
| `HOTSPOT_SEGMENTS` / map center constants | Sample-race / city defaults | bin generation / maps | **rename/move** to template data | Phase 8 | Not universal domain law | — |
| Classic UI chrome (`base.html` else branch) | Dual chrome with Tabler | all pages without `ui=tabler` | **remove** | Phase 7 | Product: Tabler-only; Git for rollback | Phase 7 |
| Course-mapping legacy DOM (`course-legacy-*`, hidden recipes) | Partially hidden | `course_mapping.js`, `segment_recipes.js` | **investigate** | Phase 9 | Smoke preferred Build workflow first | TBD |
| Host path `/Users/jthompson/Documents/runflow` | ~~Duplicated~~ **FIXED** | `path_mapper` + `RUNFLOW_ROOT` | **keep** env contract | Phase 4 ✓ | Compose `.env` / `.env.example` | — |
| Hardcoded `window_s=30` / `bin_km=0.2` in `new_density_report` | ~~Fabricated~~ **FIXED** | `app.core.bin.provenance` | **keep** artifact-backed | Phase 5 ✓ | Fail-fast if bins lack columns | — |
| Start-time docs/tests claiming 0–1439 | ~~Conflict~~ **FIXED** | `app.core.v2.start_time` is SSOT | **keep** contract | Phase 2 ✓ | Operating hours 300–1200 | — |

---

## Completed

| Module / symbol | Removed in | Notes |
|-----------------|------------|-------|
| Conflicting 0–1439 start-time docs/tests | Phase 2 | Canonical module `app.core.v2.start_time` (300–1200) |
| Domain glossary stub | Phase 3 | Expanded field alias map + agent guidance; FastAPI title → Runflow |
| Host `/Users/.../runflow` literals | Phase 4 | `app.utils.path_mapper` + `RUNFLOW_ROOT` env; compose `.env.example` |
| Fabricated report `window_s`/`bin_km` | Phase 5 | Resolved from `bins.parquet` via `app.core.bin.provenance` |
| Live `new_*` density stack moved | Phase 6 | Canonical under `app/core/reports/density/`; old paths are shims |
| `app/routes/reports.py` | Phase 1 | Empty `/reports` router |
| `app/routes/api_flow.py` | Phase 1 | Wildcard shim → `app.api.flow` |
| `app/routes/api_bidirectional.py` | Phase 1 | Wildcard shim → `app.api.bidirectional` |
| `flow._ShardWriter`, `_write_index_csv`, `_write_topk_csv` | Phase 1 | Dead CSV audit helpers post-Parquet |

---

## How to use (agents)

1. Before deleting anything named `new_` / `legacy` / `old`, read this table.  
2. Prefer **rename while live** for reporting stacks.  
3. Record the PR that changes a row’s disposition.  
4. See [canonical-paths.md](canonical-paths.md) for the supported call graphs.
