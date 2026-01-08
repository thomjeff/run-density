Below is a planning‑only response with concrete, step‑by‑step implementation stubs (no code), aligned to your requests and the current code paths. I’m also explicitly confirming the heatmap behavior and preserving PowerNorm. Citations point to the exact locations in the codebase that inform each item.


Issue 1 — LOS SSOT & Column Strategy (single authoritative LOS, computed once)
Today LOS is computed multiple ways (bins_accumulator defaults, new_flagging, new_density_template_engine, and report fallbacks). This is the core divergence driver across tables, reports, and UI artifacts.

Suggested task
Unify LOS classification under rulebook SSOT and a single stored column
Define SSOT ownership: declare app/rulebook.py as the only LOS classifier and threshold loader (using get_thresholds() + classify_los()), and forbid other modules from deriving LOS independently.​codex-file-citation​Choose the canonical LOS column (e.g., los_class only) and remove or deprecate parallel columns (los), including any fallback “recompute LOS from density” logic in report generation (see new_density_template_engine recompute).​codex-file-citation​Write LOS once: ensure bins are assigned los_class after rulebook evaluation and stored in bins.parquet (already done in the flagging path); remove any alternate LOS computation paths that overwrite or recompute later in report/UI pipelines.​codex-file-citation​​codex-file-citation​Read LOS everywhere else: update segment metrics and UI artifacts to only read the canonical LOS column from bins.parquet (no fallback). This matches the current worst‑bin extraction logic in generate_segment_metrics_json.​codex-file-citation​Remove legacy LOS thresholds in bins_accumulator, app/los.py, and config/reporting.yml as authoritative sources to prevent drift (keep reporting.yml LOS colors only).​codex-file-citation​​codex-file-citation​​codex-file-citation​




Issue 2 — Decide “What Drives LOS” (Density vs Rate vs Derived)
Current LOS computation is density‑based via rulebook thresholds, while rate is used for flagging severity. This distinction is already embedded in rulebook.evaluate_flags() and downstream pipelines, but it needs to be explicitly formalized in the architecture and output semantics.

Suggested task
Formalize LOS as density-driven and define rate’s role in severity only
Document the decision: LOS is determined solely by areal density (p/m²), per the rulebook thresholds. Rate influences flag severity but does not change LOS. (This aligns with the current rulebook API signature and classification function.)​codex-file-citation​Update reporting semantics: ensure all reports/exports reflect this, and remove any places where LOS is recomputed using non‑density data or alternative thresholds (e.g., “recalculate LOS from worst_bin_density” using segment_type fallback).​codex-file-citation​Explicitly codify rate as: a) utilization/flag severity input, b) diagnostic metric in UI and reports, not a LOS driver.​codex-file-citation​



Issue 3 — Heatmap Alignment (preserve PowerNorm & visual fidelity)
Heatmaps currently read density from bins.parquet and apply PowerNorm (gamma=0.5) with a fixed vmax=2.0, then map colors from rulebook LOS palette. This is aligned with your historical intent and should be preserved. The plan should explicitly state this to avoid “table‑driven” downgrades of heatmap fidelity.

Suggested task
Preserve heatmap perceptual scaling and LOS color palette
Lock in current heatmap behavior: keep PowerNorm (gamma=0.5) and NaN→white behavior unchanged; document that this is visual enhancement only, not LOS logic.​codex-file-citation​Confirm LOS color palette source remains from rulebook/reporting config (do not re-map to table output).​codex-file-citation​​codex-file-citation​Ensure heatmaps read from bins.parquet as SSOT for density (unchanged).​codex-file-citation​


Issue 4 — Data Model Cleanup (columns to keep/delete, write vs read)
There is still dual‑column usage (los + los_class) and fallback logic that can silently diverge. This needs hard enforcement at the data model level.
Suggested task
Normalize LOS columns across bins, reports, and UI artifacts
Keep only one LOS column in bins artifacts (recommended: los_class) and remove or stop writing los during flagging/export paths (currently set in new_flagging and optionally propagated in save_bins).​codex-file-citation​​codex-file-citation​Update all consumers to read the canonical column only (segment metrics, API endpoints, reports). Avoid los/los_class fallback chains.​codex-file-citation​​codex-file-citation​Remove deprecated thresholds that previously supported legacy LOS columns (app/los.py, config/reporting.yml), to prevent accidental fallback to non‑SSOT bands.​codex-file-citation​​codex-file-citation​


Issue 5 — Density vs Rate Correlation Analysis (A1 and flow sub‑segments)
This is an analysis requirement rather than a coding change, and should be a dedicated validation step during implementation planning. We need to quantify correlation on A1 and (if present) sub‑segments (A1a–A1c), and detect divergence patterns (high rate + moderate density, high density + suppressed rate). The current code does not do this; it should be explicitly added as a validation artifact or analysis notebook/script.

Suggested task
Add A1 density–rate correlation analysis and divergence checks
Load bins.parquet for A1 (and any flow sub‑segments if present), compute correlation between density and rate, and identify time windows where they diverge (e.g., high density + low rate).Use segment_id and time windows already in bins for correlation breakdowns (per window and per bin).​codex-file-citation​Report findings: include summary stats in a validation note (e.g., correlation coefficient, scatter plots, and highlighted divergence windows).Decide on LOS divergence rules: based on results, determine whether LOS should remain purely density‑based at segment aggregation while rate is reserved for severity/alerts (expected), or whether a derived “operational status” should be reported separately from LOS.

Issue 6 — Validation Strategy (end‑to‑end alignment)
We should explicitly define how to verify that all surfaces (UI, reports, artifacts) are aligned after SSOT changes.
Suggested task
Define LOS alignment validation across UI, reports, and artifacts
Single‑run audit checklist (use A1 as reference):bins.parquet has canonical los_class values.segment_metrics.json uses worst bin los_class and matches UI table badges.Density.md flagged segments table uses the same LOS column (no recompute).Heatmap colors remain unchanged and consistent with density patterns (PowerNorm preserved).​codex-file-citation​​codex-file-citation​Add regression guards to detect reintroduction of fallback LOS thresholds (e.g., static defaults in bins_accumulator, app/los.py, or report templating).​codex-file-citation​​codex-file-citation​​codex-file-citation​


Direct responses to your design questions
A) SSOT & Column Strategy
Plan: The SSOT is the rulebook (app/rulebook.py), and the single canonical column is los_class stored in bins.parquet. LOS is computed once during rulebook evaluation and then read everywhere else. No backward compatibility is required, so remove los and any fallback reclassification. This aligns with the current rulebook classifier and the post‑#603 “worst bin” logic used in segment metrics.
B) What Drives LOS
Recommendation: LOS should remain density‑driven. Rate should continue to drive severity and operational flags, but not LOS labels. This is already how the rulebook interface is structured and is operationally consistent with LOS definitions (density-based crowding).
C) Density vs Rate Correlation
This needs explicit analysis (not assumptions). I’ve included a concrete validation stub to compute correlation and identify divergence cases for A1 and any sub‑segments if present. The outcome should inform whether LOS is ever allowed to diverge between segment‑level aggregation and flow‑level resolution; default expectation is LOS remains density‑based, while rate differences surface as severity/operational status, not LOS changes.