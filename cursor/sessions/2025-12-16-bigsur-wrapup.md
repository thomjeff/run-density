# Big Sur Milestone Wrap‑up – Session Summary (Dec 16, 2025)

**Branch:** merged `bigsur` → `main` (PR #543)  
**Scope:** Milestone 19 cleanups and DX improvements  

---

## Executive Summary
- Closed Milestone 19 issues: **#527 (logs), #528 (flags.json), #531 (locations.csv), #532 (segments map UI), #538 (latest run_id), #541 (prune utility)**.  
- Added run-level logging to `runflow/{run_id}/logs/app.log`.  
- Flags generation fixed (sun populated; sat acceptable for now).  
- Locations.csv now includes elite/open; sat Locations.csv populated.  
- Segments map heatmap moved bottom-left; Clear Filter removed.  
- Frontend always uses latest run_id.  
- Prune utility + Makefile target `make prune-runs KEEP=n`.  
- Follow-up Issue **#542** filed to have reports read bins directly from `{day}/bins/bins.parquet`.  
- Golden regressions still failing by design until goldens/normalization are updated (Issue **#540** remains open).

---

## Work Completed
- **Logging (Issue #527):** `RunLogHandler` writes per-run app logs under `runflow/{run_id}/logs/app.log`, adds metadata reference, non-blocking on failures.
- **Flags (Issue #528):** Ensure rate column is preserved when generating flags.json (sun populated; sat under separate investigation #516).
- **Locations (Issue #531):** Include elite/open in arrival modeling; sat Locations.csv now populated.
- **Segments Map UI (Issue #532):** Heatmap overlay moved to bottom-left; Clear Filter button removed.
- **Latest run_id (Issue #538):** Frontend resolves latest run_id from dashboard summary and updates URL/local state.
- **Prune utility (Issue #541):** `app/utils/prune_runs.py` with CLI (`--keep`, `--dry-run`, `--confirm`) and Makefile target `make prune-runs KEEP=n`; atomic index updates; preserves latest.json.
- **Docs/Makefile sync:** README updated with current Makefile targets; validate_output gains `--all` mode; test_v2 script archived/removed.

---

## Test Results (Dec 16, 2025)
- `make e2e-full`: **Functional scenarios PASS**; **Golden regressions FAIL (expected)**.  
  - Diff artifacts:  
    - Sat-only: `runflow/Un6Em5sZYUQZ26N44MbuWM/_test_artifacts/`  
    - Sun-only: `runflow/QPZa5hvK9SwmFhtRMV3DBK/_test_artifacts/`  
    - Mixed-day: `runflow/6SNEi9A83dCYebCefo3hzw/_test_artifacts/`  
- bins duplication: Only canonical pair per day (`bins/bins.parquet` and `reports/bins.parquet`); size difference due to compression (zstd vs default/snappy).
- Logs: present per run_id (e.g., `runflow/6SNEi9A83dCYebCefo3hzw/logs/app.log`).
- Locations: sat now populated (16 rows); sun 72 rows.

---

## Outstanding / Follow-ups
- **Issue #540:** Golden file regression updates (normalize timestamps/run_id or regenerate goldens).  
- **Issue #542:** Make reports consume `{day}/bins/bins.parquet` directly; remove duplicate copy.  
- **Issue #516:** Deeper investigation into sat flags behavior.

---

## Helpful Commands
- `make e2e` / `make e2e-full` / `make e2e-sat` / `make e2e-sun`
- `make validate-output` / `make validate-all`
- `make prune-runs KEEP=10` (use `DRY_RUN=1` for preview)
- Logs: `runflow/{run_id}/logs/app.log`

