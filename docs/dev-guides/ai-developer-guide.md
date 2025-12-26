# AI Developer Guide - Runflow v2

**Version:** v2.0.2+  
**Last Updated:** 2025-12-26  
**Audience:** AI Assistants (Cursor, ChatGPT, Codex, GitHub Copilot)  
**Purpose:** Complete onboarding and critical rules for AI pair programming

This guide consolidates the essential information AI assistants need to work effectively in the `runflow` codebase. It combines onboarding instructions, critical rules, and development patterns.

---

## ⚠️ MANDATORY: Setup & Verification

**You MUST complete ALL verification steps below before proceeding with any development work. This is non-negotiable.**

### Step 1: Confirm GitHub CLI Access
**Action Required:** Run `gh auth status` and verify:
- ✅ You are logged in to GitHub
- ✅ You have access to the `runflow` repository
- ✅ Token has required scopes: `repo`, `project`, `workflow`

**If access is not confirmed, you must report this to the user before proceeding.**

### Step 2: Verify Project Context
- ✅ Cursor is working in the correct GitHub repo context — `runflow`
- ✅ Project files are accessible and properly loaded

### Step 3: Review Codebase Structure
Begin familiarizing yourself with repo structure, especially:
- `app/routes/v2/analyze.py`: Main v2 API endpoint
- `app/core/v2/`: v2 core modules (pipeline, density, flow, reports, bins)
- `app/core/v2/analysis_config.py`: `analysis.json` generation (single source of truth)
- `app/core/v2/validation.py`: Comprehensive validation layer
- `tests/v2/e2e.py`: v2 E2E test suite
- `app/utils/constants.py`: Application constants (deprecated constants removed in Issue #553)
- `docs/user-guide/api-user-guide.md`: API user guide (v2.0.2+)
- `docs/dev-guides/developer-guide-v2.md`: Developer guide (v2.0.2+)
- `docs/dev-guides/ai-developer-guide.md`: This document (AI assistant onboarding)

**Only after completing all three steps above should you proceed with development tasks.**

---

## 📋 MANDATORY DOCUMENT REFERENCES

Before starting ANY work, you **MUST** reference these documents:

- `@docs/README.md` – Documentation index and architecture overview
- `@docs/user-guide/api-user-guide.md` – API user guide (v2.0.2+)
- `@docs/dev-guides/developer-guide-v2.md` – Developer guide (v2.0.2+)
- `@docs/reference/quick-reference.md` – Authoritative variable names and field mappings
- `@docs/dev-guides/docker-dev.md` – Development workflow and commands

---

## ✅ MANDATORY RULE CONFIRMATION

Before any code or tests are written, confirm the following:

```
✅ CONFIRMING CRITICAL RULES (v2.0.2+):
1. NO HARDCODED VALUES – Use app/core/v2/analysis_config.py helpers (Issue #553)
2. PERMANENT CODE ONLY – No temp scripts or isolated experiments
3. START TIME CONSTANTS – Use get_start_time() from analysis.json (Issue #553)
4. API TESTING ONLY – Always test via POST /runflow/v2/analyze endpoint
5. MINIMAL CHANGES – Make small, testable commits
6. NO ENDLESS LOOPS – Stop after 3 failed analysis attempts and ask
7. STRICT TYPOS – Match variable names exactly to references
8. NAMING CONVENTIONS – Use field names from QUICK_REFERENCE.md
9. TODO PERMISSION – Ask before creating task lists or suggestions
10. GITHUB CONTEXT – Read entire GitHub issue + all comments
11. CLARITY FIRST – STOP and ask if any instruction is unclear
12. FAIL-FAST ONLY – No fallback logic in code (Issue #553)
```

---

## 🚫 NON-NEGOTIABLE RULES

### 1. NO HARDCODED VALUES (Issue #553)

**Rule:** All analysis inputs must come from API request → `analysis.json` → helper functions.

**What Changed:**
- ❌ No hardcoded event names (e.g., `['full', 'half', '10k']`)
- ❌ No hardcoded start times (e.g., `DEFAULT_START_TIMES`)
- ❌ No hardcoded file paths (e.g., `"data/segments.csv"`)
- ❌ No hardcoded event durations (e.g., `EVENT_DURATION_MINUTES`)

**How to Use:**
```python
# ✅ CORRECT: Load from analysis.json
from app.core.v2.analysis_config import load_analysis_json, get_segments_file, get_flow_file

analysis_config = load_analysis_json(run_id)
segments_file = get_segments_file(analysis_config)
flow_file = get_flow_file(analysis_config)
event_names = analysis_config["events"].keys()  # Dynamic event names

# ❌ WRONG: Hardcoded values
segments_file = "data/segments.csv"  # NO!
event_names = ['full', 'half', '10k']  # NO!
```

**Helper Functions:**
- `load_analysis_json(run_id)` - Load analysis.json
- `get_segments_file(analysis_config)` - Get segments file path
- `get_flow_file(analysis_config)` - Get flow file path
- `get_locations_file(analysis_config)` - Get locations file path
- `get_event_duration(analysis_config, event_name)` - Get event duration
- `get_start_time(analysis_config, event_name)` - Get event start time

### 2. PERMANENT CODE ONLY

**Rule:** Never create temporary scripts or one-off experiments. All code must be permanent, reusable, and properly integrated.

**Examples:**
- ❌ Creating `debug_script.py` in root
- ❌ Adding test code directly in route handlers
- ❌ Creating temporary CSV files for testing

**Instead:**
- ✅ Add permanent helper functions to appropriate modules
- ✅ Use existing test infrastructure (`tests/v2/`)
- ✅ Use proper fixtures and test data

### 3. API TESTING ONLY

**Rule:** Always test via the public API endpoint. Never call internal modules directly.

**Correct:**
```python
# ✅ Use API endpoint
response = requests.post(f"{base_url}/runflow/v2/analyze", json=payload)
```

**Wrong:**
```python
# ❌ Don't call internal modules directly
from app.core.v2.pipeline import create_full_analysis_pipeline
result = create_full_analysis_pipeline(...)  # NO!
```

**Test Infrastructure:**
- Use `tests/v2/e2e.py` for E2E tests
- Use `make e2e` to run tests
- All tests must use the API endpoint

### 4. FAIL-FAST BEHAVIOR (Issue #553)

**Rule:** No fallback logic. If required data is missing, raise an error immediately.

**Flow Analysis:**
- ❌ No synthetic event pairs
- ❌ No inferred relationships
- ❌ No "best guess" behavior
- ✅ If `flow.csv` is missing → `FileNotFoundError`
- ✅ If no valid pairs → `ValueError` with clear message

**Example:**
```python
# ✅ CORRECT: Fail fast
if not flow_file_path.exists():
    raise FileNotFoundError(f"flow.csv file not found at {flow_file_path}")

# ❌ WRONG: Fallback logic
if not flow_file_path.exists():
    # Generate synthetic pairs - NO!
    pairs = generate_fallback_pairs()
```

### 5. analysis.json IS SINGLE SOURCE OF TRUTH

**Rule:** Load `analysis.json` once at pipeline start, pass `analysis_config` object throughout.

**Pattern:**
```python
# ✅ CORRECT: Load once, use throughout
analysis_config = load_analysis_json(run_id)
# Pass analysis_config to all functions

# ❌ WRONG: Load multiple times
analysis_config_1 = load_analysis_json(run_id)  # In function A
analysis_config_2 = load_analysis_json(run_id)  # In function B - NO!
```

### 6. MINIMAL CHANGES

**Rule:** Make small, testable commits. One logical change per commit.

**Good:**
- Commit 1: Add validation function
- Commit 2: Update API route to use validation
- Commit 3: Add tests for validation

**Bad:**
- Commit 1: Refactor entire pipeline, update 20 files, add tests, fix bugs

### 7. STRICT TYPOS & NAMING

**Rule:** Match variable names exactly to references in `quick-reference.md`.

**Common Mistakes:**
- `seg_id` vs `segment_id` (use `seg_id`)
- `event_name` vs `event` (check context)
- `start_time` vs `startTime` (use `start_time`)

**Reference:**
- See `docs/reference/quick-reference.md` for exact field names

### 8. GITHUB CONTEXT

**Rule:** Read entire GitHub issue + all comments before starting work.

**Process:**
1. Read issue title and body
2. Read all comments (especially user feedback)
3. Review linked issues/PRs
4. Understand acceptance criteria
5. Ask clarifying questions if needed

### 9. CLARITY FIRST

**Rule:** If any instruction is unclear, STOP and ask. Don't guess.

**When to Ask:**
- Unclear requirements
- Conflicting instructions
- Missing context
- Ambiguous error messages

---

## 🏗️ Project Architecture

### What Is `runflow`?

`runflow` is a runner density and flow analysis tool built to support large-scale road race planning, including heatmaps, timing estimates, and operational modeling based on participant movement. It analyzes race day configurations (events, start times, course routes) to produce operational outputs that inform decisions like wave starts, aid station timing, and course risk zones.

**Version:** v2.0.2+ (Issue #553 complete - all inputs configurable via API)

### Core Architecture Principles

1. **API-Driven Configuration** - All inputs via API request → `analysis.json`
2. **Day-Partitioned Outputs** - Results organized by day (`sat/`, `sun/`)
3. **Fail-Fast Validation** - No silent failures or fallbacks
4. **Single Source of Truth** - `analysis.json` for all runtime configuration

### Key Modules

- `app/routes/v2/analyze.py` - Main v2 API endpoint
- `app/core/v2/analysis_config.py` - `analysis.json` generation and helpers
- `app/core/v2/validation.py` - Comprehensive validation layer
- `app/core/v2/pipeline.py` - Main analysis pipeline
- `app/core/v2/reports.py` - Report generation
- `app/core/v2/density.py` - Density analysis
- `app/core/v2/flow.py` - Flow analysis
- `app/core/v2/bins.py` - Bin generation

### Testing

- `tests/v2/e2e.py` - E2E test suite (use `make e2e`)
- `tests/v2/test_*.py` - Unit and integration tests
- All tests must use API endpoint, never call internal modules directly

---

## 🚨 COMMON MISTAKES TO AVOID

**Never do these things:**

1. **Hardcoding values** instead of using `analysis.json` helpers
2. **Creating temporary scripts** instead of permanent code
3. **Manually testing APIs** instead of using `tests/v2/e2e.py`
4. **Calling internal modules** instead of using API endpoint
5. **Adding fallback logic** instead of fail-fast behavior
6. **Loading `analysis.json` multiple times** instead of passing `analysis_config`
7. **Making large commits** instead of small, testable changes
8. **Guessing at requirements** instead of asking for clarification
9. **Using wrong field names** instead of checking `QUICK_REFERENCE.md`
10. **Skipping verification steps** instead of completing mandatory setup

---

## 📚 Additional Resources

- **API Usage:** `docs/user-guide/api-user-guide.md`
- **Developer Guide:** `docs/dev-guides/developer-guide-v2.md`
- **Docker Workflow:** `docs/dev-guides/docker-dev.md`
- **Quick Reference:** `docs/reference/QUICK_REFERENCE.md`
- **Testing Guide:** `docs/testing/testing-guide.md`

---

## 🔄 Development Workflow

1. **Read GitHub Issue** - Complete issue + all comments
2. **Verify Setup** - Complete mandatory verification steps
3. **Review Rules** - Confirm all critical rules
4. **Plan Changes** - Small, testable commits
5. **Write Code** - Follow patterns, use helpers
6. **Test** - Use `make e2e` or `pytest tests/v2/e2e.py`
7. **Commit** - Small, focused commits with clear messages
8. **Ask for Review** - Don't merge without user approval

---

**Last Updated:** 2025-12-26  
**Maintained By:** Development Team