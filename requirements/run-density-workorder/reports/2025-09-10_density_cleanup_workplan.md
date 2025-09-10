# Density Cleanup Workplan (Cursor Work Order)

**Repo:** `run-density`  
**Date:** 2025-09-10  
**Owner:** Jeff (FM)  
**Context:** Flow is stable on `v1.6.13`. Density did not receive the same full audit. Goal is to clean up `/data` for Density and align runtime behavior **without** introducing architectural churn. Cursor has no memory; keep tasks atomic and guard against regressions.

---

## Ground Rules
- **No architecture changes.** Keep CSVs, minimal glue only when necessary.
- **Single segment source:** `segments_new.csv` (later renamed to `segments.csv` in a final pass).
- **Flow untouched.** Density first; Flow enhancements (Milestone 2) are out of scope here.
- **Cursor-proofing:** tiny guard tests to prevent re-introducing legacy names or files.
- **Branching policy:** **Cursor must NOT push code to `main`.** Every change must land via a PR from a `dev/*` or `bugfix/*` branch with green CI/E2E before merge.

---

## Objectives (Definition of Done)
1. Density reads **only** `segments_new.csv` (later `segments.csv`) for segment geometry and event windows.
2. Any legacy/duplicate density sources (e.g., `density.csv`) are archived and excluded from runtime.
3. Minimal validation: ensure required headers/flags/ranges are sane for Density processing.
4. Keep E2E green; no Flow regressions.
5. Optional Improvements (tracked as GitHub issues): cross-checks with Flow; preflight validator.

---

## Phase D0 — Guardrails (Forbidden Identifiers)
**Goal:** Prevent Cursor from resurrecting legacy names/files in runtime code.

**Tasks**
- Add `tests/test_forbidden_identifiers.py` that fails if these strings appear in runtime code:
  - `paceCsv`, `flow.csv` (runtime reads), `density.csv` (runtime reads), `segments_old.csv`.
- Allow these to exist under `data/archive/` for reference.

**Acceptance Criteria**
- Test fails if any forbidden string is found in source (excluding `data/archive/`).
- CI runs this test on PRs.
- **Branching:** Do work on `bugfix/density-D0-forbidden-identifiers` → PR → merge to `main` only after green.

**Prompt (Cursor)**
> Create branch `bugfix/density-D0-forbidden-identifiers`. Add `tests/test_forbidden_identifiers.py` that scans repo text files and fails on: `paceCsv`, `flow.csv`, `density.csv`, `segments_old.csv`. Permit occurrences only under `data/archive/`. Wire into CI test job. No runtime changes. Open a PR and run CI.

---

## Phase D1 — Thin Loader Shim for Density Reads
**Goal:** Ensure Density and Flow use the same segment source consistently, with tiny normalization only. Compatible with Cloud Run.

**Tasks**
- Create `app/io/loader.py` with:
  - `load_segments(path="data/segments_new.csv")` → reads CSV, normalizes event flags to lowercase `y/n`, coerces `width_m` to float. *No* schema framework.
  - `load_runners(path="data/runners.csv")` → as-is.
- Refactor `app/density.py` to import and use `load_segments()` instead of direct CSV reads.
- Do **not** change algorithms or outputs.

**Risk & Cloud Run Notes**
- **Risk:** Low. Read path is the same relative path; we only centralize the read/normalization. 
- **Cloud Run:** Compatible if images already include `/data` files at runtime. Use relative paths (repo root working dir). If your entrypoint changes CWD, set `WORKDIR` or pass full paths from env.

**Acceptance Criteria**
- Unit tests & E2E unchanged and passing.
- No change in Density outputs compared to baseline.
- **Branching:** `bugfix/density-D1-loader` → PR → green CI/E2E → merge.

**Prompt (Cursor)**
> Create branch `bugfix/density-D1-loader`. Add `app/io/loader.py` with `load_segments()` and `load_runners()` as described. Refactor `app/density.py` to use `load_segments()` only. Make no algorithm changes. Run tests and E2E; post a diff of files changed and confirm outputs are identical. Open a PR.

---

## Phase D2 — Archive Conflicting Density Sources
**Goal:** Remove the second competing source to stop drift.

**Tasks**
- Move `data/density.csv` (if present) to `data/archive/density.csv`.
- Add `data/archive/README.md` documenting deprecation and the active runtime sources.
- Extend forbidden-identifiers test to ensure runtime code never references `density.csv`.

**Acceptance Criteria**
- No code reads from `data/archive/` at runtime.
- Build/tests pass.
- **Branching:** `bugfix/density-D2-archive` → PR → green → merge.

**Prompt (Cursor)**
> Create branch `bugfix/density-D2-archive`. Move `data/density.csv` to `data/archive/density.csv` and add `data/archive/README.md` that lists runtime sources (`data/segments_new.csv`, `data/runners.csv`). Ensure no runtime code references `density.csv` (extend check). Run tests/E2E and open a PR.

---

## Phase D3 — Density Sanity Checks (Unit Tests)
**Goal:** Validate critical assumptions used by Density without heavy machinery.

**Tasks**
- Add unit tests that:
  1) `width_m` exists and is positive for sampled segments (e.g., A1, A2, C1 if present).
  2) For events where flag == `y`, both `*_from_km` and `*_to_km` are present, numeric, and `from <= to`.
  3) `direction ∈ {uni, bi}` only.

**Acceptance Criteria**
- Tests pass on current `segments_new.csv`.
- Failures provide clear messages for quick CSV fixes.
- **Branching:** `bugfix/density-D3-sanity-tests` → PR → green → merge.

**Prompt (Cursor)**
> Create branch `bugfix/density-D3-sanity-tests`. Add unit tests for Density: (1) positive `width_m` for sampled seg_ids, (2) event windows present and ordered when flags are `y`, (3) direction limited to `{uni, bi}`. No runtime logic changes. Run tests/E2E and open a PR.

---

## Phase D4 — (Deferred to Issue) Flow↔Density Cross-Checks
**Status:** **Create GitHub Issue**, do not implement now.

**Issue Title:** "Add analysis-only Flow↔Density correlation report"

**Issue Body (summary)**
- Build `tools/correlation_flow_density.py` to correlate parent-segment Flow overlap proxy vs. Density peaks; output markdown + CSV under `results/diagnostics/`. Non-blocking, insight-only. 

---

## Phase D5 — (Deferred to Issue) Pre-E2E Input Validator
**Status:** **Create GitHub Issue**, do not implement now.

**Issue Title:** "Add preflight validator for Density inputs"

**Issue Body (summary)**
- A tiny script to check presence of required headers/flags/ranges in `segments_new.csv` before E2E. Fails fast with friendly errors. Optional CI step.

---

## Phase D6 — Move `flow_expected_results.csv` to `/data`
**Goal:** Co-locate expected Flow results with other CSV inputs for clarity and discoverability.

**Tasks**
- Move `docs/flow_expected_results.csv` → `data/flow_expected_results.csv`.
- Update any code/tests that reference the old path.
- Document the change in `docs/` (a short stub readme that points to `/data`).

**Acceptance Criteria**
- Tests/E2E pass; no Flow behavior change.
- **Branching:** `bugfix/density-D6-move-flow-expected` → PR → green → merge.

**Prompt (Cursor)**
> Create branch `bugfix/density-D6-move-flow-expected`. Move `docs/flow_expected_results.csv` to `data/flow_expected_results.csv`. Update references. Add a docs note pointing to `/data`. Run tests/E2E. Open PR.

---

## Phase D7 — Final Rename: `segments_new.csv` → `segments.csv`
**Goal:** Remove the transitional "new" suffix now that the audit is complete.

**Tasks**
- Rename file and update loader default path: `data/segments_new.csv` → `data/segments.csv`.
- Update all import paths/tests.
- Keep `data/segments_new.csv` **out** of the repo after rename (avoid dual sources). If you must retain for reference, park it in `data/archive/` with a README note.
- Extend forbidden-identifiers test to forbid `segments_new.csv` in runtime code **after** migration.

**Acceptance Criteria**
- Build/tests/E2E pass; no behavior change.
- **Branching:** `bugfix/density-D7-rename-segments` → PR → green → merge.

**Prompt (Cursor)**
> Create branch `bugfix/density-D7-rename-segments`. Rename `data/segments_new.csv` to `data/segments.csv`. Update `app/io/loader.py` default path and all call sites/tests. Extend forbidden-identifiers test to fail if runtime references `segments_new.csv`. Run tests/E2E and open a PR.

---

## Risk Register (Short)
- **Loader shim introduces path bugs** → Mitigation: keep relative paths; run E2E post-change; confirm outputs identical.
- **Archiving density.csv breaks a hidden reader** → Mitigation: forbidden-identifiers test; repo-wide search; E2E.
- **Rename `segments_new.csv` late** → Mitigation: do as a final, isolated change (Phase D7) after all green.
- **Cloud Run pathing** → Mitigation: use relative paths; ensure container `WORKDIR` is repo root; verify `/data` present in image.

---

## Deliverables
- Phases **D0–D3 & D6–D7 completed via PRs from `dev/*` or `bugfix/*` branches** (no direct commits to `main`).
- `data/archive/README.md` explaining deprecations.
- Updated `app/io/loader.py`.
- Unit tests added under `tests/` as described.
- Short `docs/CHANGES.md` entry describing file moves and the final rename.

---

## Quick Copy/Paste Prompts (Cursor)

**D0 — Forbidden Identifiers**
> Create branch `bugfix/density-D0-forbidden-identifiers`. Add `tests/test_forbidden_identifiers.py` to fail on `paceCsv`, `flow.csv`, `density.csv`, `segments_old.csv` in runtime code. Permit under `data/archive/`. Wire into CI. Open PR.

**D1 — Loader Shim & Refactor**
> Create branch `bugfix/density-D1-loader`. Add `app/io/loader.py` with `load_segments("data/segments_new.csv")` and `load_runners("data/runners.csv")`. Normalize flags to `y/n`, coerce `width_m` to float. Refactor `app/density.py` to use `load_segments()`. No algo changes. Run tests/E2E and confirm identical outputs. Open PR.

**D2 — Archive density.csv**
> Create branch `bugfix/density-D2-archive`. Move `data/density.csv` → `data/archive/density.csv`. Add `data/archive/README.md` listing active runtime sources. Ensure no runtime code references `density.csv` (extend forbidden test). Run tests/E2E. Open PR.

**D3 — Density Sanity Tests**
> Create branch `bugfix/density-D3-sanity-tests`. Add unit tests: positive `width_m` for sampled seg_ids; event windows present & ordered for `y` flags; `direction ∈ {uni, bi}`. Run tests/E2E. Open PR.

**D6 — Move flow_expected_results.csv to /data**
> Create branch `bugfix/density-D6-move-flow-expected`. Move `docs/flow_expected_results.csv` → `data/flow_expected_results.csv`. Update references. Add a docs note pointing to `/data`. Run tests/E2E. Open PR.

**D7 — Rename segments_new.csv → segments.csv**
> Create branch `bugfix/density-D7-rename-segments`. Rename `data/segments_new.csv` to `data/segments.csv`. Update `app/io/loader.py` default path and all references. Extend forbidden test to block runtime mentions of `segments_new.csv`. Run tests/E2E. Open PR.

---

## Post-Plan GitHub Issues to Create
1. **Flow↔Density correlation report (analysis-only).**
2. **Pre-E2E input validator for Density.**
3. **(Optional) Snapshot test for a tiny set of Density metrics** to detect future drift.

---

## Notes for Reviewers
- Expect **zero** algorithmic behavior changes across D0–D3, D6–D7.
- If any E2E diffs appear, stop and investigate path/normalization only.
- Keep PRs small (one phase per PR) to help with review and rollback.
