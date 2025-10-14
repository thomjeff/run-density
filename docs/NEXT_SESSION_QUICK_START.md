# Next Session Quick Start - Issue #233

## 🚀 **IMMEDIATE ACTIONS FOR NEW CURSOR SESSION**

### **1. CONTEXT DOCUMENTS TO READ:**
- **`@docs/ISSUE_233_DEVELOPMENT_PRIMER.md`** - Complete technical roadmap
- **`@cursor/chats/CHAT_SESSION_SUMMARY_2025-09-19.md`** - Today's achievements
- **`@docs/Pre-task safeguards.md`** - Mandatory rules and workflow

### **2. ISSUE TO WORK ON:**
- **Primary**: Issue #233 - Operational Intelligence (Map + Report)
- **URL**: https://github.com/thomjeff/run-density/issues/233
- **Status**: READY with perfect canonical segments foundation

### **3. FOUNDATION STATUS:**
- **✅ Canonical Segments**: Operational (0.000000% error validation)
- **✅ API Endpoints**: Serving canonical data with metadata
- **✅ CI/CD Pipeline**: Fixed and working (v1.6.41 created automatically)
- **✅ Main Branch**: Healthy and ready for development

### **4. CHATGPT QUESTIONS TO ASK:**
1. **Flagging Logic**: LOS ≥ C on density_mean or density_peak?
2. **Time Windows**: Peak only or sustained periods for flagging?
3. **Flow Calculation**: Per-bin flow logic or inherit from segments?
4. **Map Format**: PNG/SVG preference and resolution requirements?
5. **Report Integration**: Replace density.md or create separate report?

### **5. DEVELOPMENT WORKFLOW:**
```bash
# Create dev branch
git checkout -b v1.6.42-operational-intelligence

# Start local server for testing
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080 &

# Test canonical segments foundation
python scripts/validation/reconcile_canonical_segments_v2.py --reports-dir ./reports/2025-09-19
```

### **6. KEY FILES TO UNDERSTAND:**
- **`app/canonical_segments.py`** - Canonical segments utilities
- **`reports/2025-09-19/segment_windows_from_bins.parquet`** - Data source
- **`app/density_report.py`** - Report generation patterns
- **`data/density_rulebook.yml`** - LOS thresholds

## 🎯 **SUCCESS CRITERIA:**
- Executive summary with flagged bins/segments
- Map snippets for operational intelligence
- Metadata compliance (density_method, schema_version)
- Perfect reconciliation maintained (0.000000% error)
- E2E tests passing (local and Cloud Run)

## 🏆 **CONFIDENCE LEVEL: HIGH**
Ready for immediate productive work with excellent foundation! 🚀

