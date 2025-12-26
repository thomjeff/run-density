# Deprecated and Removed Features

**Version:** 1.0  
**Date:** 2025-12-14  
**Runflow Version:** v2.0.0+

This document lists all endpoints, modules, constants, and features that have been removed in Runflow v2.0.0.

---

## Removed API Endpoints

### Analysis Endpoints (v1)

All v1 analysis endpoints have been removed. Use `POST /runflow/v2/analyze` instead.

**Removed:**
- `POST /api/temporal-flow` – Temporal flow analysis
- `POST /api/temporal-flow-single` – Single segment flow analysis
- `POST /api/density-report` – Density report generation
- `POST /api/temporal-flow-report` – Temporal flow report generation
- `POST /api/flow-audit` – Flow audit analysis
- `POST /api/pdf-report` – PDF report generation
- `GET /api/pdf-templates` – PDF template listing
- `GET /api/pdf-status` – PDF generation status

**Replacement:**
- `POST /runflow/v2/analyze` – Unified v2 analysis endpoint

### Data Serving Endpoints (v1)

**Removed:**
- `GET /data/runners.csv` – Direct runner file access
- `GET /data/segments.csv` – Direct segment file access
- `GET /data/flow_expected_results.csv` – Test data access

**Reason:** v2 uses per-event runner files and internal file access only.

---

## Removed Modules

### Deleted Files

**Removed:**
- `app/api/density.py` – v1 density analysis module
- `app/api/report.py` – v1 report module
- `app/routes/api_flow.py` – Redirect file (replaced by `app/api/flow.py`)
- `app/routes/api_e2e.py` – E2E-specific endpoints (not used by v2 E2E suite)

**Reason:** These modules were v1-only and read from `/data` inputs rather than serving artifacts from `runflow/{run_id}/{day}`.

---

## Removed Constants

### Event Constants

**Removed from `app/utils/constants.py`:**
- `EVENT_DAYS` – Event-to-day mapping
- `SATURDAY_EVENTS` – Saturday event list
- `SUNDAY_EVENTS` – Sunday event list
- `ALL_EVENTS` – All events list

**Reason:** v2 uses dynamic event configuration from API payload. Events have a `day` property.

### File Path Constants

**Removed from `app/utils/constants.py`:**
- `DEFAULT_PACE_CSV` – Default runner file path (`"data/runners.csv"`)

**Reason:** v2 uses per-event runner files (`{event}_runners.csv`).

---

## Removed Data Files

### Runner Files

**v1:**
- `data/runners.csv` – Single file for all events

**v2:**
- Replaced by per-event files: `full_runners.csv`, `10k_runners.csv`, `half_runners.csv`, `elite_runners.csv`, `open_runners.csv`

---

## Removed Features

### Backward Compatibility

**v1:**
- Supported both `segment_id` and `seg_id` column names
- Automatic column renaming for compatibility

**v2:**
- Uses `seg_id` exclusively
- No backward compatibility for `segment_id`
- All v2 outputs use `seg_id` only

### Hardcoded Event Lists

**v1:**
- Hardcoded event lists in constants
- Assumed specific events exist

**v2:**
- Events defined in API payload
- No hardcoded event lists
- Dynamic event discovery

### Global Timeline

**v1:**
- Single global timeline for all events

**v2:**
- Day-scoped timelines (one per day)
- Events grouped by day

---

## Migration Path

For details on migrating from v1 to v2, see:
- `docs/migration_v1_to_v2.md` – Complete migration guide
- `docs/GUARDRAILS.md` – v2 guardrails and best practices

---

## Reference

- **v1 Tag:** `v1-maintenance` – Last known-good v1 state
- **v2 Tag:** `v2.0.0` – v2 release
- **Archive:** `archive/v1/` – v1 reference code (if archived)

---

**Note:** v1 code is preserved in Git history. To reference v1 behavior, checkout the `v1-maintenance` tag or review archived files.

