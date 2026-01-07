# Codex Reseach Issue 629

Below is a research-only investigation based on the current repo state. Codex could not find /codex/issue629.md in this repository; the path does not exist in the tree here, so I proceeded by auditing the relevant code directly. (If that file should exist in this environment, please point me to its exact location.)

## 2) Debug flags removal investigation

### Where these flags are produced
The flags are all created by the convergence policy logic and then copied into segment results:
- apply_convergence_policy() computes spatial_zone_exists, temporal_overlap_exists, true_pass_exists, has_convergence_policy, and no_pass_reason_code.
- process_segment_with_convergence() assigns those policy results into segment_result, and sets has_convergence equal to has_convergence_policy (duplicating the policy flag).

### Where these flags are exported/consumed
- The Flow CSV exports all the flags as a “Technical & Debugging” group of columns: spatial_zone_exists, temporal_overlap_exists, true_pass_exists, has_convergence_policy, has_convergence, no_pass_reason_code (plus convergence zone bounds).
- The Flow Audit data includes spatial_zone_exists, temporal_overlap_exists, true_pass_exists, has_convergence_policy, and no_pass_reason_code as part of the audit payload.
- The report generator uses has_convergence to decide whether to print convergence analysis in the Markdown report.
- The reporting config requires has_convergence in Flow CSV validation (but not the other flags).

### Takeaways
- has_convergence is redundant with has_convergence_policy because it is set directly from that policy result (no transformation).
- The other flags are purely diagnostic in flow outputs and audit exports; there’s no frontend usage in the repo (I did not find them referenced outside flow_report.py / flow core).
- If downstream UI/analytics are not consuming them, they can be removed from Flow CSV outputs and/or relegated to a .debug bundle. If you keep any one of them for analysis, has_convergence alone is sufficient for basic gating (and it’s already required by config/reporting.yml).

## 3) overtaking_load_a/b and max_overtaking_load_a/b — meaning, formula, and export guidance

**How they’re calculated**
- calculate_overtaking_loads():
   - Defines a conflict zone (using cp_km + window logic similar to the detector).
   - Keeps only runners who reach the zone end (filters on distance >= zone_end_km).
   - Computes boundary arrival times using pace and start offset, then does pairwise temporal overlap checks.
   - Counts a “pass” when one runner’s boundary interval fully wraps another’s interval (directional pass), subject to min_overlap_duration.
   - Returns per-runner pass counts (loads_a, loads_b), average loads, and max loads.
- detect_temporal_overlap_and_passes() defines the pass logic (directional, based on interval nesting).

**What the units are**
- Units: counts of runners passed (i.e., count of directional passes) per runner.
- The report explicitly describes this as “passing burden” and labels the output as “runners.”

**Where they’re exposed now**
- The Flow CSV includes overtaking_load_a/b and max_overtaking_load_a/b columns.
- The Markdown report has a “Runner Experience Analysis” section presenting them as average and max loads, with high-load flags for >5 and >10 thresholds.
- They are not exported to fz.parquet or fz_runners.parquet (those exports only include zone-level overtaking/copresence counts, not load statistics).

**Accuracy considerations**
- The pass detection counts only cases where one runner’s zone interval is fully inside another’s interval (as_ > bs_ and ae_ < be_, or vice versa). That’s a strict pass definition and may undercount if overtaking happens without full interval containment (e.g., pacing variability or partial overlaps).
- Only runners that reach the zone end are included, which can bias loads in segments with DNFs or runners who slow/stop before the end.

**Should these be added to fz.parquet or fz_runners.parquet?**
- _Current values are segment-level aggregates, not per-zone._
- Since fz.parquet is zone-level, you’d need zone-scoped load calculations if you want them there (which likely means repeating this logic per zone index rather than per segment).
- fz_runners.parquet is runner/zone/role; if you want runner-level pass-load metrics, you’d need to export per-runner load counts (e.g., loads_a / loads_b) with zone IDs. Right now those distributions are only kept in-memory and used in the report narrative.

## Additional thoughts for Issue #629
1. has_convergence duplication: it’s literally set from has_convergence_policy, so removing one of them would reduce confusion without losing info (keep one for CSV validation).
2. Flow CSV contains conflict_length_m twice (once in the “Technical & Debugging” group and once in “Metadata”). This could cause downstream confusion or tooling issues when parsing by column name. Consider consolidating to a single column if you touch this file anyway.
3. If overtaking_load_* is considered a key analytic, it may need a formal schema description or explicit export policy (e.g., whether it’s derived from cp-based conflict zones vs. multi-zone outputs). Right now it’s implicitly tied to the convergence point (cp_km) and conflict zone logic, which **will not match zone-level interpretations**. The calculation is specific to the same conflict zone logic as the “working detector,” not necessarily to all zones that are reported in fz.

## Commands run (research)
- rg -n "spatial_zone_exists|temporal_overlap_exists|true_pass_exists|has_convergence_policy|has_convergence|no_pass_reason" to locate flag definitions/usages in flow core and report exports.
- rg -n "overtaking_load|max_overtaking_load" to locate overtaking load computations and reporting usage.
- rg -n "fz" and inspection of export functions to verify fz.parquet and fz_runners.parquet schema contents.

## Tests
No tests were run (research-only task).