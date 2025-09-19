# Issue #233 Development Primer - Operational Intelligence

## 🎯 **CRITICAL CONTEXT FOR NEW CURSOR SESSION**

**Date Created**: September 19, 2025  
**Purpose**: Enable immediate productive work on Issue #233 without context loss  
**Foundation**: Issues #231 & #232 COMPLETE with perfect validation  

## 🏆 **CURRENT STATE: READY FOR ISSUE #233**

### **✅ PERFECT FOUNDATION ESTABLISHED**
- **Canonical Segments**: Operational with 0.000000% reconciliation error
- **API Endpoints**: All serving canonical segments as source of truth
- **CI/CD Pipeline**: Fixed and working (v1.6.41 created automatically)
- **Validation Framework**: ChatGPT's reconciliation v2 script operational

### **📊 VALIDATION EVIDENCE**
```
Reconciliation v2 Results (PERFECT):
- Rows compared: 1,760 (80 windows × 22 segments)
- Mean |rel err|: 0.000000
- P95 |rel err|: 0.000000 (tolerance 0.0200)
- Max |rel err|: 0.000000
- Windows > 0.0200: 0
- RESULT: PASS ✅
```

## 📋 **ISSUE #233 REQUIREMENTS SUMMARY**

### **🎯 OBJECTIVE**
Transform canonical segments into **operational intelligence** for Race Directors, Health & Safety leads, and course marshals.

### **👥 TARGET USERS**
1. **Race Directors**: High-level flagged segments/bins overview
2. **Health & Safety Leads**: Bin-level detail for resource deployment
3. **Course Marshals**: Map snippets of attention areas with context

### **📋 KEY REQUIREMENTS**
1. **Bin-Level Flagging**: Apply LOS thresholds (A-F) + top 5% utilization
2. **Executive Summary**: One-page table with flagged segments/bins
3. **Map Visualization**: Auto-generated snippets for flagged areas
4. **Metadata Compliance**: `density_method: "segments_from_bins"`, `schema_version: "1.1.0"`
5. **CI Guardrails**: Validate canonical reconciliation in pipeline
6. **Legacy Sunset**: Clearly mark legacy as deprecated

## 🚀 **TECHNICAL IMPLEMENTATION ROADMAP**

### **Phase 1: Data Processing (Days 1-2)**
**File**: `app/bin_intelligence.py` (NEW)
```python
def analyze_bin_intelligence(canonical_segments_df):
    """Apply LOS thresholds and flagging logic to canonical segments."""
    # Use density_peak for LOS classification (more conservative)
    # Calculate top 5% utilization globally across all bins
    # Return flagged bins with severity and reason codes
```

### **Phase 2: Report Generation (Days 2-3)**
**File**: `app/executive_summary.py` (NEW)
```python
def generate_executive_summary(flagged_bins, canonical_segments):
    """Generate one-page executive summary with operational intelligence."""
    # Roll up flagged bins to segment level
    # Create summary table: Segment | Bin Range | LOS | Density | Utilization | Flag
    # Include metadata compliance and clear action items
```

### **Phase 3: Map Visualization (Days 3-4)**
**File**: `app/bin_mapper.py` (NEW)
```python
def generate_flagged_bin_maps(flagged_bins, segments_geojson):
    """Generate map snippets for flagged segments with bin-level detail."""
    # Convert bins to polyline segments using start_km/end_km
    # Apply color coding with utilization overlay
    # Export 1200px PNG with tooltips and legend
```

### **Phase 4: Integration & CI (Days 4-5)**
- **API Endpoint**: `/api/operational-intelligence` (NEW)
- **CI Enhancement**: Extend reconciliation validation
- **Frontend Integration**: Update map.html for flagged bins
- **E2E Testing**: Comprehensive validation pipeline

## 🔧 **KEY TECHNICAL ASSETS AVAILABLE**

### **Canonical Segments Data Structure**
```python
# Available in: reports/2025-09-19/segment_windows_from_bins.parquet
columns = ['segment_id', 't_start', 't_end', 'density_mean', 'density_peak', 'n_bins']
# 1,760 rows (80 windows × 22 segments)
# Perfect validation with 0.000000% error
```

### **Existing Modules to Leverage**
- **`app/canonical_segments.py`**: Load and work with canonical segments
- **`app/gpx_processor.py`**: Geographic processing and polyline slicing
- **`app/density_report.py`**: Report generation pipeline
- **`app/map_data_generator.py`**: Map data creation and validation
- **`scripts/validation/reconcile_canonical_segments_v2.py`**: Quality validation

### **API Endpoints Ready**
- **`/api/segments`**: Serves canonical segments with metadata
- **`/api/debug/env`**: Shows canonical segments availability
- **`/api/density-report`**: Generates canonical segments and bins

## 🤔 **CRITICAL QUESTIONS TO RESOLVE WITH CHATGPT**

### **Implementation Decisions Needed:**
1. **Flagging Logic**: LOS ≥ C on `density_mean` or `density_peak`?
2. **Time Windows**: Peak only or sustained periods for flagging?
3. **Flow Calculation**: Per-bin flow logic or inherit from segments?
4. **Map Format**: PNG/SVG preference and resolution requirements?
5. **Report Integration**: Replace density.md or create separate report?

### **Technical Specifications:**
- **Performance Targets**: Response time requirements for Cloud Run
- **Export Requirements**: Map snippet format for presentations
- **Visualization Details**: Bin representation (lines vs points)

## 📁 **CRITICAL FILES TO UNDERSTAND**

### **Must Read First:**
1. **`app/canonical_segments.py`** - Core utilities for canonical segments
2. **`reports/2025-09-19/segment_windows_from_bins.parquet`** - Data structure
3. **`app/density_report.py`** - Report generation pipeline (lines 1496-1623)
4. **`app/main.py`** - API endpoints (lines 1054-1172)

### **Reference for Implementation:**
- **`app/gpx_processor.py`** - Geographic processing functions
- **`app/map_data_generator.py`** - Map data creation patterns
- **`data/density_rulebook.yml`** - LOS thresholds and schemas
- **`.github/workflows/ci-pipeline.yml`** - CI integration patterns

## 🎯 **DEVELOPMENT WORKFLOW READY**

### **Branch Strategy:**
```bash
git checkout -b v1.6.42-operational-intelligence
# Follow established dev branch → test → merge workflow
```

### **Testing Strategy:**
```bash
# Local testing
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080 &
python3 e2e.py --local

# Validation
python scripts/validation/reconcile_canonical_segments_v2.py --reports-dir ./reports/2025-09-19
```

### **Commit Pattern:**
- One commit per major component (bin_intelligence.py, executive_summary.py, etc.)
- Test after each commit
- Follow Pre-task safeguards for E2E testing

## 🚀 **SUCCESS CRITERIA CLEAR**

### **Acceptance Criteria from Issue #233:**
- [ ] Executive summary report with flagged bins/segments
- [ ] Map snippets for flagged areas with bin-level detail
- [ ] Metadata compliance (density_method, schema_version)
- [ ] CI guardrails with canonical reconciliation validation
- [ ] Legacy methods clearly marked as deprecated

### **Quality Gates:**
- [ ] Perfect reconciliation maintained (0.000000% error)
- [ ] E2E tests passing (local and Cloud Run)
- [ ] Frontend compatibility preserved
- [ ] Performance acceptable on Cloud Run

## 💡 **KEY INSIGHTS FOR NEXT SESSION**

### **Technical Strengths to Leverage:**
- **Canonical segments are rock-solid** - 0.000000% validation error
- **API infrastructure proven** - all endpoints serving canonical data
- **CI/CD working perfectly** - automatic releases now functional
- **Validation framework established** - ChatGPT's reconciliation script operational

### **Implementation Approach:**
- **Build incrementally** on proven canonical segments foundation
- **Reuse existing patterns** from density_report.py and map_data_generator.py
- **Maintain backward compatibility** with graceful fallbacks
- **Follow established testing** and validation procedures

### **Critical Success Factors:**
- **Start with ChatGPT questions** to clarify implementation details
- **Use proven development workflow** (dev branch → test → merge)
- **Leverage existing geographic processing** from gpx_processor.py
- **Maintain perfect validation** throughout development

## 🎉 **READY FOR IMMEDIATE PRODUCTIVE WORK**

The next Cursor session can **immediately begin Issue #233 implementation** with:
- ✅ **Perfect foundation** (canonical segments operational)
- ✅ **Clear requirements** (comprehensive analysis provided)
- ✅ **Technical roadmap** (4-phase implementation plan)
- ✅ **Proven infrastructure** (APIs, CI/CD, validation all working)

**This is the perfect evolution from canonical segments to operational intelligence! 🚀**

## 📚 **REFERENCE LINKS**
- **Issue #233**: https://github.com/thomjeff/run-density/issues/233
- **Technical Analysis**: Comment #3314045184 on Issue #233
- **Validation Package**: Issue233_Validation_Package_20250919_1019.zip
- **Session Summary**: cursor/chats/CHAT_SESSION_SUMMARY_2025-09-19.md
