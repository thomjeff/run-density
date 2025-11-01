# Archived: Legacy /frontend Directory

**Archived Date:** November 1, 2025  
**Archived By:** AI Assistant (v1.7.1 architecture cleanup)  
**Original Location:** `/frontend/`  
**Reason:** Unused duplicate code - functionality replaced by `/app/common/config.py`

---

## Why This Was Archived

### Summary
The `/frontend` directory contained a duplicate, outdated version of configuration loading code that was never used by the application. The actual frontend is served from `/templates` (Jinja2) and `/static` (CSS/JS), not from this directory.

### Evidence of Non-Use

1. **No Imports Found:**
   - Zero imports of `from frontend` in entire codebase
   - All active code uses `from app.common.config import load_rulebook, load_reporting`

2. **Duplicate Code:**
   - `/frontend/common/config.py` (70 lines) - older version
   - `/app/common/config.py` (118 lines) - current version with additional features

3. **Static Mount Unused:**
   - `app/main.py` mounted `/frontend` as static files
   - No HTML templates reference `/frontend/` URLs

4. **Frontend Actually Served From:**
   - `/templates/` - Jinja2 HTML templates
   - `/static/` - CSS, JavaScript, images

---

## Archived Contents

```
frontend/
├── __init__.py (0 bytes - empty)
└── common/
    ├── __init__.py (0 bytes - empty)
    └── config.py (70 lines - outdated version)
```

---

## Restoration Instructions

**Note:** Restoration is not recommended as this code was superseded by `/app/common/config.py`.

```bash
# View archived code
cat archive/frontend/legacy-config-2025-11/common/config.py

# Compare with current version
diff archive/frontend/legacy-config-2025-11/common/config.py app/common/config.py
```

---

**Archived as part of v1.7.1 architecture cleanup - November 2025**
