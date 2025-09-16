# Pre-Task Safeguards

⚠️ **CRITICAL**: This document contains NON-NEGOTIABLE RULES that have been violated multiple times, causing significant debugging issues. These rules MUST be followed without exception.

## **📋 MANDATORY DOCUMENT REFERENCES**

Before starting ANY work, you **MUST** reference these four documents:
- `@CRITICAL_CONFIGURATION.md` - Critical rules and workflow requirements
- `@Application Fundamentals.md` - Core concepts and data structures  
- `@Application Architecture.md` - System design and testing patterns
- `@VARIABLE_NAMING_REFERENCE.md` - Authoritative variable names and field mappings

## **✅ MANDATORY RULE CONFIRMATION**

You **MUST** explicitly confirm understanding of these CRITICAL RULES before proceeding:

```
✅ CONFIRMING CRITICAL RULES:
1. NO HARDCODED VALUES - will use app/constants.py and dynamic calculations
2. PERMANENT CODE ONLY - will modify existing modules, not create temp scripts
3. CORRECT START TIMES - will use {'Full': 420, '10K': 440, 'Half': 460}
4. API TESTING - will test through main.py endpoints, not direct module calls
5. MINIMAL CHANGES - will make only necessary changes and test frequently
6. NO ENDLESS LOOPS - will take action after 3 analysis attempts, not repeat analysis
7. TYPO CHECKING - will verify variable names and data flow integrity
8. VARIABLE NAMING - will use correct field names (seg_label not segment_label, from_km not 10K_from_km)
9. TODO PERMISSION - will ask for permission before creating todo lists when user asks for thoughts
10. COMPLETE GITHUB ISSUE READING - will read ENTIRE GitHub issues including ALL comments, no shortcuts
```

## **🧪 MANDATORY TESTING SEQUENCE**

After ANY code changes, you **MUST**:
1. **ACTIVATE VIRTUAL ENVIRONMENT FIRST**: `source .venv/bin/activate` (CRITICAL - prevents ModuleNotFoundError)
2. **USE AUTOMATED TEST SCRIPTS ONLY**: `python3 -m app.end_to_end_testing`
3. **NEVER manually construct curl commands** - this wastes time and leads to errors
4. **NEVER guess API parameters** - use the automated scripts that know the correct endpoints
5. **MAINTAIN TESTING CONSISTENCY** - Use the SAME testing methodology for both local and Cloud Run testing
6. **FOR CLOUD RUN TESTING**: Use `TEST_CLOUD_RUN=true python3 -m app.end_to_end_testing` (skips heavy computation)
7. **FOR LOCAL TESTING**: Use `python3 -m app.end_to_end_testing` (full E2E with all endpoints)
8. **FOR CI PIPELINE**: Automatically uses `SKIP_TEMPORAL_FLOW=true` due to Cloud Run resource limits
9. Generate actual reports (MD + CSV), not just JSON data
10. Verify no hardcoded values were introduced
11. Test through API endpoints, not direct module calls
12. Validate report content quality and human readability

### **🚫 PROHIBITED TESTING ACTIONS**
- **NEVER** manually construct curl commands for API testing
- **NEVER** guess API endpoint parameters or request formats
- **NEVER** waste time looking up correct API calls when automated scripts exist
- **NEVER** modify code to "fix" API calls instead of using proper automated testing
- **NEVER** use different testing methodologies for local vs Cloud Run testing
- **NEVER** compare results from different testing approaches

### **🚫 PROHIBITED GITHUB COMMAND ACTIONS**
- **NEVER** use complex multi-line strings in `gh issue comment` commands
- **NEVER** include unescaped quotes, backticks, or special characters in comment bodies
- **NEVER** use complex JSON or code blocks in single-line shell commands
- **ALWAYS** use simple, single-line comment bodies or write to files first
- **IF** complex formatting needed, write to a file first, then use `gh issue comment --body-file`

### **🚫 PROHIBITED TIME CALCULATION ERRORS**
- **NEVER** mix time units without explicit conversion (minutes vs seconds)
- **NEVER** convert only one event's start time and leave the other unconverted
- **ALWAYS** convert ALL start times consistently: `start_a = start_times.get(event_a, 0) * 60.0`
- **ALWAYS** verify time calculations with unit tests for edge cases
- **NEVER** assume time values are in the same units without checking the data source

## **📁 CRITICAL FILE REFERENCES**

- **ALWAYS use**: `data/runners.csv`, `data/segments_new.csv`
- **NEVER use**: `data/your_pace_data.csv`, `data/segments_old.csv`
- **ALWAYS use**: `app/constants.py` for configuration values
- **NEVER hardcode**: start times, tolerance values, conflict lengths

## **📋 MANDATORY GITHUB ISSUE READING**

**CRITICAL**: When reading GitHub issues, you **MUST**:

1. **Read the ENTIRE issue** - Title, description, acceptance criteria, all sections
2. **Read ALL comments** - Use `gh issue view <number> --comments` to get complete context
3. **No shortcuts or skimming** - Every comment contains important technical details
4. **Persistent data store** - GitHub issues are the source of truth for ALL Cursor work
5. **Complete context** - Missing details from comments leads to incomplete implementation

**Command**: `gh issue view <issue-number> --comments`

**Why this is critical:**
- Comments contain technical implementation strategies
- ChatGPT answers provide specific implementation details
- User feedback and decisions are documented in comments
- Incomplete reading leads to missing critical requirements
- This wastes time and creates rework

## **🐍 MANDATORY ENVIRONMENT SETUP**

**CRITICAL**: Before running ANY commands, you **MUST** activate the virtual environment:

```bash
# ALWAYS run this first
source .venv/bin/activate

# THEN run your commands
python3 -m app.end_to_end_testing
```

**Why this is critical:**
- **Prevents ModuleNotFoundError**: System Python doesn't have required dependencies
- **Ensures correct dependencies**: Virtual environment has all required packages
- **Maintains consistency**: Same environment as production deployment
- **Avoids debugging time**: Prevents "missing module" errors that waste time

**Signs you forgot to activate:**
- `ModuleNotFoundError: No module named 'fastapi'`
- `ModuleNotFoundError: No module named 'pandas'`
- Any import errors when running Python commands

**Remember**: Virtual environment activation does NOT persist between terminal sessions!

### **🚫 CRITICAL: DEACTIVATE VIRTUAL ENVIRONMENT FOR NON-PYTHON WORK**

**CRITICAL**: When NOT doing Python development work, you **MUST** deactivate the virtual environment:

```bash
# For Python/E2E work
source test_env/bin/activate
python3 -m app.end_to_end_testing

# For GitHub CLI, system commands, or non-Python work
deactivate
gh issue create --title "Example"
```

**Why this is critical:**
- **GitHub CLI works properly** outside virtual environments
- **System commands have full access** to system tools
- **Prevents command failures** like `gh issue create` not working
- **Cleaner terminal sessions** for different types of work

**When to deactivate:**
- Using GitHub CLI (`gh` commands)
- Running system commands
- File operations outside Python
- Any non-Python development work

**Signs you need to deactivate:**
- GitHub CLI commands fail or don't execute
- System commands return unexpected errors
- Terminal shows `(test_env)` prefix when not doing Python work

## **🔧 CURRENT DEVELOPMENT ISSUES**

**Active Issues for Development Branch:**
- **Issue #191**: Runflow Front-End (Phase 2) - HTMX integration, time windows, enhanced interactions (HIGH priority)
- **Issue #185**: Incorrect E2E Report Metadata - Environment, timestamp, version fixes (HIGH priority)
- **Issue #182**: Align Markdown Report Formatting - Consistent report appearance (MEDIUM priority)
- **Issue #166**: Remove Redundant Zone Values - Map tooltip cleanup (MEDIUM priority)
- **Issue #165**: Remove Hardcoded Values - Configuration management (MEDIUM priority)
- **Issue #164**: Add Single-Segment Testing - Development workflow improvement (MEDIUM priority)
- **Issue #160**: CI Version Consistency - Pipeline improvement (MEDIUM priority)
- **Issue #145**: Code Hygiene Review - General cleanup (LOW priority)
- **Issue #85**: Density Phase 2+ - Full testing implementation (LOW priority)

## **🎨 FRONTEND IMPLEMENTATION STATUS**

**Issue #187 - COMPLETED (v1.6.32)**:
- ✅ **Phase 1**: Core Infrastructure - Password gate, dashboard, health check, navigation
- ✅ **Phase 2**: Interactive Map - Leaflet.js, GPX data, controls, course display
- ✅ **Phase 3**: Reports Page - Data integration, download functionality
- ✅ **Production Deployed**: All pages accessible at Cloud Run URL
- ✅ **Testing Complete**: E2E tests passing, Flow.csv validation perfect (29/29 segments)

**Current Frontend Status**:
- **Cloud Run URL**: https://run-density-ln4r3sfkha-uc.a.run.app/frontend/
- **Pages**: password.html, index.html, map.html, reports.html, health.html
- **Features**: Complete frontend with dashboard, map, reports, health check
- **Next Phase**: Issue #191 - Advanced features and HTMX integration

**Frontend Development Notes**:
- **Configuration**: Use app/constants.py for all configuration values
- **API Endpoints**: /api/summary, /api/segments, /api/reports for frontend data
- **Session Management**: Client-side authentication with sessionStorage (8-hour TTL)
- **Responsive Design**: Mobile-friendly interface with modern CSS
- **Testing**: All frontend pages tested and working on Cloud Run

## **🐛 COMMON DEBUGGING PATTERNS**

**When algorithms return 0 values or unexpected results:**

1. **Check time unit consistency** - Ensure ALL time calculations use the same units
   - Start times: minutes → seconds conversion (`* 60.0`)
   - Pace calculations: minutes per km → seconds per km (`* 60.0`)
   - Example bug: `start_a = start_times.get(event_a, 0) * 60.0` but `start_b = start_times.get(event_b, 0)` (missing `* 60.0`)

2. **Verify data filtering logic** - Check if filtered datasets are empty
   - Absolute intersections: `max(from_km_a, from_km_b)` vs `min(to_km_a, to_km_b)`
   - Use normalized conflict zones when no absolute intersection exists
   - Log boundary values to verify filtering is working

3. **Validate algorithm assumptions** - Ensure logic matches working reference implementation
   - Reuse proven functions instead of recreating logic
   - Compare with existing working code patterns
   - Test with known good data first

**Recommended Development Order:**
1. **Issue #191** (Frontend Phase 2) - Demo preparation, high priority
2. **Issue #185** (E2E Metadata) - Data accuracy, high priority
3. **Issue #182** (Markdown Formatting) - Report consistency, medium priority
4. **Issue #166** (Zone Values) - UI cleanup, medium priority
5. **Issue #165** (Hardcoded Values) - Configuration management, medium priority
6. **Issue #164** (Single-Segment Testing) - Development workflow, medium priority
7. **Issue #160** (CI Version) - Process improvement, medium priority
8. **Issue #145** (Code Hygiene) - General cleanup, low priority
9. **Issue #85** (Density Phase 2+) - Feature work, low priority

**Each issue gets its own commit for easy rollback within the branch.**

## **🎯 CURRENT MILESTONE: DEMO PREPARATION**

**Milestone 9 - Demo**: Fredericton Marathon committee presentation
- **Deadline**: 1 day remaining
- **Status**: Phase 1 frontend complete, Phase 2 in progress
- **Priority**: Issue #191 (Frontend Phase 2) for advanced features
- **Focus**: HTMX integration, time windows, enhanced interactions

**Demo Readiness Checklist**:
- ✅ **Basic Frontend**: Dashboard, map, reports working
- ✅ **Cloud Run Deployed**: All pages accessible
- ✅ **Flow.csv Validation**: Perfect match (29/29 segments)
- ⏳ **Advanced Features**: HTMX, time windows, enhanced interactions
- ⏳ **Report Metadata**: Environment, timestamp, version accuracy
- ⏳ **Final Polish**: UI improvements, error handling, performance

## **🚀 9-STEP MERGE/TEST PROCESS**

For ALL releases and merges, you **MUST** follow this complete process:

1. **Verify Dev Branch Health** - Check git status and recent commits
2. **Run Final E2E Tests on Dev Branch** - Ensure all tests pass before merge
3. **Create Pull Request** - With comprehensive description and testing results
4. **Wait for User Review/Approval** - User will review and merge via GitHub Desktop or Web UI
5. **Verify Merge to Main** - Check git status and recent commits after user merge
6. **Create Release with Assets** - Include latest reports as release assets
7. **Add E2E Files to Release** - Attach Flow.md, Flow.csv, Density.md, E2E.md to release
8. **Verify Release and Run Final E2E Tests** - Confirm release is complete and working
9. **Run Final E2E Tests on Main (Safeguard for Next Branch)** - Ensure main branch is healthy for future development

**Note**: Step 9 serves as a safeguard to ensure the next dev branch starts from a healthy main branch. Since dev branch E2E tests = main branch E2E tests (same code), running them twice is redundant and delays deployment.

## **🔄 AUTOMATED CI/CD PIPELINE**

**CRITICAL**: This project has automated CI/CD that runs on EVERY push to main:

### **Pipeline Triggers**
- **Push to main branch**: Automatically triggers full deployment pipeline
- **Pull requests to main**: Runs validation tests only
- **Manual dispatch**: Can be triggered manually via GitHub Actions

### **Pipeline Stages**
1. **Build & Deploy**: Docker → Artifact Registry → Cloud Run
2. **Smoke Test**: Production validation (health, ready, density endpoint)
3. **Version Consistency Check**: Validates app version matches git tags
4. **Automated Release**: Creates GitHub release with assets (if version is new)

### **🧪 CI E2E Testing Scope**

**IMPORTANT**: The CI pipeline runs **lightweight E2E tests** due to Cloud Run resource constraints (1GB RAM / 1 CPU):

#### **✅ What CI Tests:**
- **Health endpoints**: `/health`, `/ready`
- **Density reports**: `/api/density-report` (lightweight)
- **Temporal flow reports**: `/api/temporal-flow-report` (markdown generation)
- **Basic API functionality**: Core endpoints without heavy computation

#### **❌ What CI Skips:**
- **Temporal flow analysis**: `/api/temporal-flow` (SKIPPED - too resource intensive)
- **Heavy computation**: Large dataset processing, complex pandas operations
- **Full flow audit**: Resource-intensive analysis that would timeout

#### **🔧 E2E Testing Strategy:**
- **Local Development**: Full E2E testing with all endpoints (`python3 -m app.end_to_end_testing`)
- **CI Pipeline**: Resource-constrained testing (`SKIP_TEMPORAL_FLOW=true`)
- **Production Validation**: Manual full E2E tests when needed
- **Cloud Run Limits**: 1GB RAM / 1 CPU - designed for basic functionality only

**This is intentional architecture** - CI validates deployment and basic functionality, while comprehensive testing is done locally with full resources.

### **⚠️ CRITICAL WARNINGS**
- **NEVER push directly to main** - Always use pull requests
- **Version consistency required** - App version must match latest git tag
- **Cloud Run auto-deploys** - Every main push deploys to production
- **Pipeline failures block releases** - Fix CI issues before creating releases

### **Pipeline Monitoring**
- Check status: `gh run list --limit 5`
- View details: `gh run view <run-id>`
- View logs: `gh run view <run-id> --log`

### **📎 MANDATORY RELEASE ASSETS**

For EVERY release, you **MUST** attach these files:
- **Flow.md** - Latest temporal flow analysis report
- **Flow.csv** - Latest temporal flow data
- **Density.md** - Latest density analysis report  
- **E2E.md** - Latest end-to-end test results

**Command**: `gh release upload <version> <file1> <file2> <file3> <file4>`

## **✅ SUCCESS CRITERIA**

Work is complete ONLY when:
- All code changes use constants.py, no hardcoded values
- All testing done through API endpoints
- All reports generate correctly with proper formatting
- All changes committed to version branch (e.g., v1.6.3-flow-debug)
- All validation tests pass
- **9-step merge/test process completed**
- **Release assets attached (Flow.md, Flow.csv, Density.md, E2E.md)**

---

**Remember**: You cannot persist memory between conversations. Always reference these documents and confirm understanding before starting work.