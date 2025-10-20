# Issue #281 - Data Source Map and Dictionary Documentation

**Created**: 2025-10-19  
**GitHub Issue**: https://github.com/thomjeff/run-density/issues/281  
**Parent Issue**: #279 (RF-FE-002 - New Multi-Page Web UI)  
**Project**: runflow  
**Labels**: enhancement, documentation  
**Status**: Open

---

## Purpose

Create comprehensive documentation that serves as the **single source of truth (SSOT)** for all data flows in the run-density application, from analytics → artifacts → API → UI.

---

## Problem

The RF-FE-002 implementation introduced complex data flows with no comprehensive documentation mapping:
- ❌ Where each UI element gets its data
- ❌ What each metric means (definitions, units, constraints)
- ❌ How to validate data parity from source to UI
- ❌ API contracts and schemas
- ❌ Transform rules and calculations

This creates risks for development, QA, and maintenance.

---

## Solution

Create `docs/DATA_SOURCE_MAP_AND_DICTIONARY.md` with complete documentation of:

### 0. Directory & Config Map
- Artifact directory structure (`/artifacts/<run_id>/ui/`)
- Config file locations (`/config/`, `/data/`)
- SSOT loader references (`app/common/config.py`)

### 1. API Endpoints Reference
- Complete table of all 10 implemented endpoints
- Purpose and backing files for each
- Notes on what doesn't exist (e.g., `/api/density/heatmap`)

### 2. UI → Data Lineage
Maps every UI element to its data source:
- **Dashboard** - All 12 KPI tiles mapped to source
- **Segments** - Map + table data sources
- **Density** - Table and detail panel sources
- **Flow** - Flow table data sources
- **Reports** - Report listing sources
- **Health** - Health check data sources

### 3. Artifact Schemas
Complete schemas for 5 artifact files:
- `meta.json` - Run metadata
- `segments.geojson` - Segment geometries
- `segment_metrics.json` - Density metrics per segment
- `flags.json` - Operational flags
- `flow.json` - Flow metrics per segment

Each with type definitions, examples, and validation constraints.

### 4. Metric Dictionary
Comprehensive table with 13 metrics:
- Field name, Meaning, Units, Source, Rules/Notes
- Covers: runners, segments, density, flow, LOS, flags, utilization
- References to config files

### 5. Transform Rules
Algorithms for:
- LOS classification
- Aggregation calculations (max, count, sum)
- Join operations (geo + metrics + flags)
- Flagging logic

### 6. Contract Tests
Test specifications for QA:
- Dashboard parity tests
- Segments GeoJSON enrichment tests
- Flow table parity tests
- Health/presence tests
- Implementation guidance for `tests/test_contracts_*.py`

### 7. Known Gaps / Future
- Missing endpoints
- Schema versioning considerations
- Upstream fix requirements

### 8. Acceptance Criteria
- Data parity validation checklist
- SSOT compliance rules
- Local/Cloud parity requirements

### Appendix A. Minimal JSON Schemas
Informal schema definitions for quick reference

---

## ChatGPT's Draft

ChatGPT (technical architect) has provided a **complete draft** of this document with all sections filled out. The draft is saved in:

**Location**: `cursor/chatgpt/DATA_SOURCE_MAP_AND_DICTIONARY_DRAFT.md`

---

## Benefits

### For Developers
✅ **Clear data lineage** - Understand where every value comes from  
✅ **API contracts** - Know exactly what each endpoint returns  
✅ **Transform rules** - Understand how metrics are calculated  
✅ **Testing guidance** - Know what to test and how

### For QA
✅ **Validation checklist** - Verify data accuracy systematically  
✅ **Parity tests** - Automated checks for source → API → UI  
✅ **Known gaps** - Understand what's missing vs. broken

### For Product
✅ **Metric definitions** - Understand what each number means  
✅ **Data accuracy** - Confidence in displayed values  
✅ **Feature planning** - Know what data is available

### For Operations
✅ **Health monitoring** - Understand what files are required  
✅ **Debugging** - Trace data issues from UI back to source  
✅ **Deployment** - Verify artifacts are complete

---

## Implementation Tasks

### 1. Document Creation ✅
- [ ] Create `docs/DATA_SOURCE_MAP_AND_DICTIONARY.md` from ChatGPT's draft
- [ ] Review all API endpoints match current implementation
- [ ] Verify all artifact schemas match Step 7 QA-fixed artifacts
- [ ] Verify all metrics match current dashboard/density/flow pages

### 2. Integration ✅
- [ ] Add link from `docs/REFERENCE.md` to new document
- [ ] Add link from Issue #279 to new document
- [ ] Update README with reference to data dictionary (if appropriate)

### 3. Validation ✅
- [ ] Technical review by developer (Cursor)
- [ ] Verify against actual API responses
- [ ] Verify against actual artifact files
- [ ] Cross-check with `tests/test_ui_artifacts_qc.py`

### 4. Optional Enhancements
- [ ] Generate starter contract test: `tests/test_contracts_dashboard.py`
- [ ] Add diagrams showing data flow
- [ ] Link to `VARIABLE_NAMING_REFERENCE.md`

---

## Key Content Examples

### API Endpoint Table
```
| Category   | Endpoint                        | Purpose                  | Backing Files                |
|------------|---------------------------------|--------------------------|------------------------------|
| Dashboard  | GET /api/dashboard/summary      | KPI tiles & banner       | meta.json, segment_metrics.  |
|            |                                 |                          | json, flags.json, flow.json  |
| Segments   | GET /api/segments/geojson       | Map + table              | segments.geojson,            |
|            |                                 |                          | segment_metrics.json, flags. |
|            |                                 |                          | json                         |
```

### Metric Dictionary Example
```
| Field           | Meaning                 | Units      | Source               | Rules / Notes          |
|-----------------|-------------------------|------------|----------------------|------------------------|
| peak_density    | Max density across all  | persons/m² | segment_metrics.json | max(peak_density);     |
|                 | segments                |            |                      | non-negative float     |
| segments_flagged| Segments with any flag  | count      | flags.json           | Count distinct seg_id  |
```

### Contract Test Example
```python
def test_dashboard_peak_density_parity():
    """Verify API peak_density matches max from segment_metrics.json"""
    # Fetch API
    response = client.get("/api/dashboard/summary")
    api_peak = response.json()["peak_density"]
    
    # Load artifact
    metrics = json.loads(Path("artifacts/2025-10-19/ui/segment_metrics.json").read_text())
    artifact_peak = max(m["peak_density"] for m in metrics.values())
    
    # Assert parity
    assert abs(api_peak - artifact_peak) < 1e-6
```

---

## Priority

**High Priority**

This documentation is critical for:
- ✅ Maintaining data accuracy as the system evolves
- ✅ Onboarding new developers
- ✅ QA validation processes
- ✅ Future feature development

**Should be completed before closing Issue #279.**

---

## Out of Scope

- Implementing new contract tests (optional, can be separate issue)
- Modifying API endpoints or schemas
- Changing artifact generation logic
- Adding new metrics or data sources

This is **documentation-only** - consolidating existing information.

---

## Deliverables

1. ✅ `docs/DATA_SOURCE_MAP_AND_DICTIONARY.md` - Main document
2. ✅ Updated `docs/REFERENCE.md` - Link to new document
3. ✅ Comment on Issue #279 - Announcing completion with link
4. ⏸️ (Optional) `tests/test_contracts_dashboard.py` - Starter contract tests

---

## Timeline

**Target**: Complete before Issue #279 closure  
**Estimated Effort**: 2-3 hours (documentation formatting + validation)

---

## References

- **GitHub Issue**: https://github.com/thomjeff/run-density/issues/281
- **Parent Issue**: #279 (RF-FE-002 - New Multi-Page Web UI)
- **ChatGPT Draft**: `cursor/chatgpt/DATA_SOURCE_MAP_AND_DICTIONARY_DRAFT.md`
- **Architecture Decision**: `cursor/chatgpt/TECHNICAL_ARCHITECTURE_DECISION_RF-FE-002.md`
- **Step 7 Artifacts**: `cursor/chatgpt/STEP7_COMPLETION_SUMMARY.md`
- **Step 8 Implementation**: `cursor/chatgpt/STEP8_COMPLETION_SUMMARY.md`

---

**Status**: ✅ Issue created with complete draft from ChatGPT  
**Next Step**: Format and validate the documentation

