# Determine Correct Implementation for `predicted_timings` in Analysis Pipeline

## Background

During the implementation of [Issue #594](/codex/predicted_timings/issue594.md), it was discovered that the `predicted_timings` fields in `{day}/metadata.json` — including:

- `day_first_finisher`
- `day_last_finisher`
- `day_duration`
- `event_first_finisher`
- `event_last_finisher`

are either **incorrect** or **empty**.

### Observed Problems

- `day_first_finisher` has been populated with values such as `07:02`, which correspond to the **first runner exiting segment A1**, not the first runner to **finish an event**.
- `event_first_finisher` and `event_last_finisher` are often empty.
- This suggests values are being inferred from **segment entry or bin activity**, rather than true finish-line completion.

The conclusion from Issue #594 was that the data required to compute these values is **not readily available in a directly consumable form**, and the current implementation is therefore incorrect.

---

## Research Objective

Codex is asked to conduct a focused analysis to determine the **correct and reliable approach** for computing `predicted_timings`.

This includes:

1. Reviewing the **current analysis pipeline and code base**
2. Inspecting the **artifacts produced by the pipeline**
3. Proposing a technically sound approach to computing:
   - `day_first_finisher`
   - `day_last_finisher`
   - `day_duration`
   - (optionally) per-event first/last finishers

---

## Reference Runs for Analysis

Two identical runs are provided for inspection:

- **Without audit**  
  `/codex/predicted_timings/QAB5oFK7xx7EoknWgbZ8We`

- **With audit enabled**  
  `/codex/predicted_timings/THoqXc4d7Q7z8kVXSrBQ2X`

### Notes on Audit Mode

- The audit-enabled run includes an `/audit` directory under each day.
- These audit artifacts contain detailed logging useful for debugging.
- **Audit mode must not be relied upon** for production logic, as it is computationally expensive (doubles the analysis by approx. ~4 mins) and not guaranteed to run for all analyses. The audit files do contain entry/exit, but it is at a low level. 

---

## Existing Context

- Original issue documentation:  
  `/codex/predicted_timings/issue594.md`

- Known constraints:
  - `fz_runners.parquet` does **not** contain timestamps.
  - `segment_metrics.json` provides only coarse time windows.
  - `flow.csv` and flow artifacts are aggregate and lack per-runner timing.
  - Some bin-related artifacts may contain temporal information but are not yet clearly leveraged.

---

## Expected Output from Codex

Codex should produce a **short technical research report** that:

- Explains how `predicted_timings` are currently being derived (or mis-derived)
- Identifies which artifacts (if any) can support accurate finish-time inference
- Determines whether a **new computation module or helper function** is required
- Proposes:
  - An implementation approach
  - Architecture and data flow
  - Clear handoff guidance for Cursor (acting as AI-Developer)

This research should focus on **correctness, robustness, and maintainability**, rather than immediate implementation.

---

## Goal

Enable Cursor to implement a correct, repeatable, and well-justified solution for `predicted_timings` based on Codex’s findings, without relying on audit-only artifacts.