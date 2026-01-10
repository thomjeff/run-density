# Audit Task: Configuration Integrity, Hardcoded Fallbacks & SSOT Violations

## Objective

Conduct a full audit of the `run-density` codebase to identify **technical debt and implementation violations** relating to configuration consistency and hardcoded fallbacks. This supports **Issue #616 - Configuration as Single Source of Truth (SSOT)**.

---

## Scope of Investigation

### 🔗 Hardcoded File Paths

Search for any **explicit or implicit references** to the following files outside of `/data` or `analysis.json` configuration sources:

- `segments.csv`, `segments_new.csv`, `segments_old.csv`
- `flow.csv`
- `locations.csv`
- `runners.csv`
- `5K.gpx`, `*.gpx`

**Flag**:
- Any use of `pd.read_csv("...")`, `open("...")`, or file read operations with hardcoded strings.
- Any relative paths such as `"data/segments.csv"` or `"../data/flow.csv"`.
- Functions that default to known filenames without accepting a `path` parameter.

---

### (B) Silent Fallbacks to Defaults

Identify cases where the system silently defaults to hardcoded values **without warning or error**, including:

- A **schema** value (e.g., `"on_course_open"`)
- A **width or length** value
- A **filename or data file path**
- A **segment ID** or **label**
- Any logic that handles missing config data silently instead of failing or raising a warning

---

### (C) Configuration Violations (SSOT Breaches)

Investigate how configuration files are loaded and propagated. Confirm that:

- Segments, flow, locations, and runners files are **loaded once** and **passed through** downstream consumers (not reloaded in submodules)
- Schema resolution and segment metadata enrichment do **not re-implement fallback logic**
- All configuration values (e.g., LOS thresholds, segment widths, mappings) are **centralized**
- Report generation, binning, and geojson creation respect **analysis.json** and `data_files` consistently

---

### (D) Additional Checks (Suggested by ChatGPT)

- Identify any functions that **should accept a config or context object** but do not
- Detect if **schema resolution** or **file path logic** occurs deep inside helpers/utilities instead of injected from the top level
- Ensure all artifact generation (e.g., geojson, bin reports) pull from **analysis.json-defined paths**
- Identify constants or defaults in:
  - `constants.py`
  - `rulebook.py`
  - hardcoded `dict`s
  that could be migrated into configuration

---

## Deliverables

### 1. Audit Report

Create a structured markdown file and save to: codex/config_audit_report.md

This should include:

- Confirmed compliant areas
- Violations or weak patterns (with file + line references)
- Suggestions for cleanup or refactoring
- Deprecated or dangerous fallback patterns

### 2. Implementation Plan (Optional, After Approval)

Once the report is reviewed and approved:

- Propose a clear, staged cleanup/refactor plan
- Address high-priority SSOT violations first
- Fixes will proceed in a dedicated branch (to be provided)

---

## Kickoff Instructions

- Work in **655-audit-config-integrity** branch**
- Use tools like `grep`, `ripgrep`, AST parsers, or internal tools for detection
- Do **not** begin modifying code until your research findings have been reviewed and a plan approved.
- Focus only on audit, investigation, and reporting

---

## 🧩 Background

This is part of Issue #616 to eliminate all hardcoded CSV and GPX references, enforce a **configuration-driven pipeline**, and move toward a **single source of truth (SSOT)** architecture for all input data.