# Logging Standards

**Version:** 1.0  
**Last Updated:** 2025-11-11  
**Issue:** #467 Phase 3 Step 7

This document defines logging patterns for the Run-Density application.

---

## 📋 Logging Patterns (Mandatory in Phase 3+)

### Success Messages (stdout via logger.info)

**Format:**
```
✅ [Stage] completed — Output: [path]
```

**Examples:**
```python
logger.info("✅ Density Report completed — Output: runflow/jBsYHSLUVhcBtECqJZP6tv/reports/Density.md")
logger.info("✅ Heatmaps generated — Count: 17 PNG files — Location: runflow/jBsYHSLUVhcBtECqJZP6tv/ui/heatmaps/")
logger.info("✅ UI Artifacts exported — Location: runflow/jBsYHSLUVhcBtECqJZP6tv/ui/")
logger.info("✅ Output Validation — Status: PASS — Run: jBsYHSLUVhcBtECqJZP6tv")
```

---

### Error Messages (stderr via logger.error)

**Format:**
```
❌ [Stage] FAILED — Error: [message] — Run: [run_id]
```

**All `logger.error(...)` calls are routed to stderr with `[ERROR]` prefix for visibility.**

**Examples:**
```python
logger.error("❌ Density Report FAILED — Error: data/runners.csv not found — Run: jBsYHSLUVhcBtECqJZP6tv")
logger.error("❌ Schema Validation FAILED — Error: segment_metrics.json missing 'segments' field — Run: jBsYHSLUVhcBtECqJZP6tv")
logger.error("❌ File Missing — File: runflow/jBsYHSLUVhcBtECqJZP6tv/ui/flags.json — Run: jBsYHSLUVhcBtECqJZP6tv")
```

---

### Warning Messages (stdout via logger.warning)

**Format:**
```
⚠️ [Description] — Context: [details]
```

**For non-critical issues:**
```python
logger.warning("⚠️ Optional file missing — File: runflow/jBsYHSLUVhcBtECqJZP6tv/maps/map_data.json")
logger.warning("⚠️ Required file missing — File: bins/bin_summary.json — Status: PARTIAL")
```

---

## 🔧 Configuration

### Logger Setup

```python
import logging
import sys

# Configure root logger
logging.basicConfig(
    format='%(levelname)s:%(name)s:%(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)  # INFO, WARNING
    ]
)

# Add stderr handler for errors
error_handler = logging.StreamHandler(sys.stderr)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('[ERROR] %(name)s: %(message)s'))
logging.getLogger().addHandler(error_handler)
```

### Result

- ✅ All `logger.error(...)` → stderr with `[ERROR]` prefix
- ✅ All `logger.info(...)` → stdout
- ✅ All `logger.warning(...)` → stdout with `WARNING:` prefix

---

## 📊 Implementation Status

### Modules Using New Patterns

- ✅ `app/tests/validate_output.py` - Full implementation
- ⏳ `app/density_report.py` - Opportunistic updates
- ⏳ `app/flow_report.py` - Opportunistic updates
- ⏳ `app/heatmap_generator.py` - Opportunistic updates

**Strategy:** All new code must follow these patterns. Existing code updated opportunistically during maintenance.

---

## 🎯 Benefits

1. **Observability** - Clear success/failure in logs
2. **Debuggability** - Errors include context (run_id, file, stage)
3. **Automation** - Structured format easy to parse
4. **Ops-Friendly** - stderr routing for monitoring tools

---

**Last Updated:** 2025-11-11 (Issue #467 - Phase 3 Step 7)

