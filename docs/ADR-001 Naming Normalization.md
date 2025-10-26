# ADR-001: Naming Normalization and Migration Strategy

**Status:** Accepted  
**Date:** 2025-10-26  
**ADR Type:** Standards / Compatibility  
**Linked Issues:** #340, #341, #348

---

## 1. Context

The `run-density` codebase currently contains **inconsistent naming conventions** across frontend, backend, and artifacts. Variants include:

| Concept        | Variants Found                             |
|----------------|--------------------------------------------|
| Segment ID     | `segment_id`, `seg_id`, `segmentId`, `segId` |
| Checkpoint ID  | `checkpoint_id`, `chk_id`, `chkptId`       |
| Cursor         | `cursor`, `event_cursor`, `cursor_pos`     |

These inconsistencies exist in:
- API query parameters (camelCase: `segmentId`)
- Python internal variables (snake_case: `segment_id`)
- Templates and JS handlers (mixed)
- Legacy schema/alias layers (`seg_id`, `seg_label`)
- Output reports and CSV headers

This drift increases the risk of:
- Bugs from ambiguous variable meanings
- Broken API contracts
- Duplicate logic for alias handling
- Inconsistent test coverage

---

## 2. Decision Summary

We adopt a **canonical, snake_case naming standard** for all internal code. API input/output may retain legacy names **only via adapter layers** or alias maps.

### ✅ Canonical Names and Layer Mapping

**Critical Clarification**: The existing `seg_id` → `segment_id` mapping convention is preserved:

| Layer | Field Name | Example |
|-------|------------|---------|
| **Internal Data Layer** | `seg_id` | CSV files, pandas DataFrames, internal lookups |
| **API Layer** | `segment_id` | API request/response, JSON bodies, external interfaces |

This dual naming is **intentional** and reflects the boundary between:
- Data ingestion/persistence (uses `seg_id`)
- External API contracts (uses `segment_id`)

### ✅ Canonical Internal Names

| Canonical Term     | Applies To | Notes |
|--------------------|------------|-------|
| `segment_id`       | All API boundaries (request/response) | External-facing |
| `seg_id`           | Internal data layer (CSV, DB, DataFrames) | Internal data |
| `checkpoint_id`    | All internal code  
| `cursor_index`     | Cursor in segment sequence  
| `bin_id`, `bin_flag`, `density_value` | Analysis objects

- **snake_case is mandatory** for Python code
- **camelCase remains permitted** in frontend inputs and API query parameters (mapped internally via adapters)
- **Internal data sources** continue using `seg_id` (e.g., `segments.csv`)

---

## 3. Migration Strategy (Non-Breaking)

Refactor proceeds in **three phases** to maintain compatibility:

### Phase 0–1 (now)

- No breaking changes or renames
- **Adapter functions** (e.g., `normalize_segment_id()`) used to map aliases in request handlers
- **Scope**: Normalize API input only (not responses)
- **Location**: `app/normalize.py` (to be relocated to `core/` in Phase 3)
- **Legacy aliases preserved** in `.to_dict()` and UI templates
- Document legacy mappings in `docs/VARIABLE_NAMING_REFERENCE.md`

### Phase 2 (future)

- Internal renames: migrate `seg_id` → `segment_id` in internal code only
- Refactor existing modules with compatibility layers (functions and data adapters)
- Deprecate legacy terms in internal models; warn in CI if used

### Phase 3 (final)

- Remove aliases where possible
- Update all consumers (internal & external) to canonical naming
- Remove adapter logic

---

## 4. Rationale

- Naming clarity reduces onboarding time and bug surface
- SSOT (Single Source of Truth) supported through strict naming enforcement
- Adapter-based compatibility allows gradual rollout and testing
- Matches community Python conventions (PEP8, REST best practices)
- Preserves existing working patterns (`seg_id` in data, `segment_id` in API)

---

## 5. Tradeoffs

- Short-term increase in complexity due to adapter layers
- Risk of inconsistencies in early phases unless CI enforces usage
- Requires discipline to avoid bypassing adapters during refactors
- Dual naming convention (`seg_id` vs `segment_id`) requires clear documentation

---

## 6. Implementation Plan

**Phase 1 Tasks:**
- [x] Create `app/normalize.py` with `normalize_segment_id()` and `normalize_checkpoint_id()`
- [ ] Audit API boundary functions for alias handling
- [ ] Add lint rule (or code comment tag) to detect legacy terms
- [ ] Unit tests for adapters: accept all known aliases, map to canonical
- [ ] Update `docs/VARIABLE_NAMING_REFERENCE.md`
- [ ] Schedule full rename for Phase 2 milestone

**Implementation Location**: `app/normalize.py` (Phase 1), move to `core/normalize.py` (Phase 3)

---

## 7. Related

- 🔗 [#340] Refactor Parent Task  
- 🔗 [#341] Phase 0 Code Review  
- 🔗 [#348] This ADR  
- 📄 `docs/VARIABLE_NAMING_REFERENCE.md` (in scope for update)