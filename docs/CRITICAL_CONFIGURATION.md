# Critical Configuration - Development and Deployment

This document captures critical configuration details, workflows, and operational requirements that are essential for the application to function correctly and must never be forgotten or changed without careful consideration.

## Core Application Knowledge

**IMPORTANT**: For fundamental application concepts (start times, data structures, time calculations), see `docs/Application Fundamentals.md`. This document focuses on configuration and workflow.

## **🚨 CRITICAL: 7-STEP COMMIT-TO-MAIN WORKFLOW**

**MANDATORY**: This workflow MUST be followed for ALL commits to main. No exceptions.

### **Step 1: Check for Required Commits**
- Verify all changes are committed to the dev branch
- Ensure working tree is clean
- Confirm branch is ready for PR creation

### **Step 2: Create Pull Request**
- Create PR from dev branch to main
- Include comprehensive description of changes
- Wait for user review and approval
- **NEVER skip this step - no direct pushes to main**

### **Step 3: Wait for User Review (60 seconds)**
- Allow time for user to review PR
- Wait for explicit approval before proceeding
- Do not proceed without user confirmation

### **Step 4: Monitor GitHub Workflow (Automated)**
- Use `gh run list --json databaseId,status,conclusion,headBranch,event,createdAt --limit 5` for non-interactive monitoring
- Verify deployment status is "success"
- **DO NOT use `gh run view --log` (causes interactive prompts)**

### **Step 5: Run E2E Tests Against Cloud Run Production**
- Set environment variable: `python e2e.py --cloud`
- Run: `python e2e.py --local`
- **CRITICAL**: Use the SAME automated testing module for both local and Cloud Run
- **NEVER** use manual curl commands for Cloud Run testing
- Verify all tests pass against production deployment
- **URL automatically uses `CLOUD_RUN_URL` from constants.py**

### **Step 6: Run E2E Tests Locally on Main Branch**
- Switch to main branch: `git checkout main`
- Kill existing local environment and create fresh environment
- Run: `python e2e.py --local` (without TEST_CLOUD_RUN)
- **CRITICAL**: Use the SAME automated testing module for both local and Cloud Run
- **NEVER** use manual curl commands for local testing
- Verify all tests pass locally
- **URL automatically uses `TEST_SERVER_URL` from constants.py**

### **Step 7: Report Results and Analysis**
- Provide comprehensive analysis format every time
- Include key achievements summary
- Test results comparison table
- File analysis for both environments
- Notable observations and warnings
- Production readiness confirmation
- Recommendations for future workflow

### **Environment Variables for E2E Testing**
- `python e2e.py --cloud`: Test against Cloud Run production
- `TEST_CLOUD_RUN=false` (default): Test against local TestClient
- URLs automatically configured via `app/constants.py`:
  - `CLOUD_RUN_URL`: "https://run-density-ln4r3sfkha-uc.a.run.app"
  - `LOCAL_RUN_URL`: "http://localhost:8080"
  - `TEST_SERVER_URL`: "http://testserver:8080"

### **Workflow Violations**
- **CRITICAL**: Never push directly to main without PR
- **CRITICAL**: Never skip E2E testing steps
- **CRITICAL**: Always use automated E2E testing scripts
- **CRITICAL**: Always test both Cloud Run and local environments

## Production Environment Configuration

### **🚨 CRITICAL: PRODUCTION URLS AND ENDPOINTS**

**NEVER guess production URLs or endpoints.** Always use the documented production environment details.

**Production Cloud Runner Service:**
- **Base URL**: `https://run-density-ln4r3sfkha-uc.a.run.app`
- **Health Check**: `GET /health` - Returns `{"ok": true, "status": "healthy", "version": "X.X.X"}`
- **Ready Check**: `GET /ready` - Returns `{"ok": true, "density_loaded": true, "overlap_loaded": true}`
- **Temporal Flow API**: `POST /api/temporal-flow`
- **Temporal Flow Report API**: `POST /api/temporal-flow-report`
- **Density Report API**: `POST /api/density-report`

**Production Testing Commands:**
```bash
# Health check
BASE="https://run-density-ln4r3sfkha-uc.a.run.app"
curl -fsS "$BASE/health" | jq -e '.ok == true' >/dev/null && echo "health OK"

# Ready check  
curl -fsS "$BASE/ready" | jq -e '.ok == true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready OK"

# API test
curl -X POST "$BASE/api/temporal-flow" -H "Content-Type: application/json" \
  -d '{"paceCsv": "data/runners.csv", "segmentsCsv": "data/segments_new.csv", 
       "startTimes": {"Full": 420, "10K": 440, "Half": 460}, 
       "minOverlapDuration": 10, "conflictLengthM": 100}'
```

**⚠️ NEVER use these incorrect URLs:**
- ❌ `https://run-density-7g2q.onrender.com` (old/incorrect)
- ❌ Any other guessed URLs

## Data Formatting Standards

### Decimal Places Rule
**CRITICAL**: All numeric values in reports must be formatted to a maximum of 2 decimal places for human readability and consistency.

- **Convergence points**: 1.33 (not 1.3300000000000003)
- **Convergence zones**: 1.28, 2.03 (not 1.2800000000000002, 2.0299999999999985)
- **Percentages**: 7.6% (not 7.6000000000000005%)
- **Distances**: 0.25 km (not 0.25000000000000006)

**Implementation**: Use `app/report_utils.py` `format_decimal_places()` function for consistent formatting across all report modules.

## Testing Configuration

### **🚨 CRITICAL: AUTOMATED TESTING ONLY**

**NEVER manually construct curl commands or guess API parameters.** This wastes time and leads to errors.

**ALWAYS use the automated test scripts:**
- **Primary**: `python e2e.py --local` - Comprehensive testing suite
- **Secondary**: `python3 -m tests.temporal_flow_tests` - Flow-specific tests
- **Secondary**: `python3 -m tests.density_tests` - Density-specific tests

**Available Test Scripts:**
- `e2e.py` - Main comprehensive testing suite
- `app/flow_validation.py` - Flow analysis validation framework
- `tests/temporal_flow_tests.py` - Temporal Flow Integration Tests
- `tests/test_flow_unit.py` - Flow Unit Tests
- `tests/density_tests.py` - Density Analysis Tests
- `tests/test_runner.py` - Runner Data Tests

## Testing Workflow

### What "Reports" Means:
**Reports** = Actual markdown (.md) and CSV (.csv) files generated by the application's report modules, NOT just JSON data or test files.

### Required Reports for Testing:
1. **Temporal Flow Report** - Markdown file using `temporal_flow_report.py`
2. **Temporal Flow CSV** - CSV data file (automatically generated)
3. **Density Analysis Report** - Markdown file using `density_report.py`

### Testing Commands:
```bash
# 1. Create virtual environment
python3 -m venv test_env && source test_env/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. **USE AUTOMATED TEST SCRIPTS ONLY** - NEVER manually construct API calls
python e2e.py --local

# 4. **ALTERNATIVE**: Direct report generation (if automated scripts fail)
python3 -c "
from app.temporal_flow_report import generate_temporal_flow_report
from app.density_report import generate_density_report

start_times = {'10K': 420, 'Half': 440, 'Full': 460}  # 7:00, 7:20, 7:40 AM

# Generate temporal flow report
temporal_result = generate_temporal_flow_report('data/runners.csv', 'data/flow.csv', start_times)

# Generate density report  
density_result = generate_density_report('data/runners.csv', 'data/density.csv', start_times)
"
```

### Comprehensive End-to-End Testing (RECOMMENDED):
```bash
# 1. Create virtual environment
python3 -m venv test_env && source test_env/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run comprehensive end-to-end tests
python3 -c "
# Legacy module removed - use e2e.py instead run_comprehensive_tests
results = run_comprehensive_tests()
"

# Or run the module directly
python3 e2e.py
```

### Individual Test Components:
```bash
# Test only API endpoints
python3 -c "
# Legacy module removed - use e2e.py instead test_api_endpoints
results = test_api_endpoints()
"

# Test only report generation
python3 -c "
# Legacy module removed - use e2e.py instead test_report_generation
results = test_report_generation()
"

# Test only report content quality
python3 -c "
# Legacy module removed - use e2e.py instead test_report_content_quality
results = test_report_content_quality()
"
```

## Architecture Principles

### Module Separation:
- **Flow analysis** (`app/flow.py`) - temporal flow calculations, including distance normalization
- **Density analysis** (`app/density.py`) - density calculations,  including distance normalization
- **Report generation** (`app/temporal_flow_report.py`, `app/density_report.py`) - report creation logic consuming results from core modules like Flow and Density.
- **API endpoints** (`app/main.py`) - web interface

### Data Sources:
- `segments.csv` (now `flow.csv`) - source of truth for width_m parameters
- `density.csv` - event-specific km ranges for density analysis
- `runners.csv` - runner pace data

### Non-Negotiable Requirements:
- Overtakes must be counted precisely (real temporal overlaps only)
- Use 'flow' to describe temporal_flow output
- Smaller modules with strict functional separation
- Always include automated and unit tests
- **NO HARDCODED VALUES** - This is a strict rule. Never use hardcoded values unless explicitly directed to do so. Always use proper dynamic calculations and configuration instead.

### Key Development Requirements:
- **MINIMAL CHANGES APPROACH** - When making changes, make only the minimal changes needed and test frequently.
- **TEST FREQUENTLY** - Test as often as possible and where it makes sense during development.
- **REFER TO APPLICATION FUNDAMENTALS** - For core concepts, see `docs/Application Fundamentals.md`

## CRITICAL AI ASSISTANT LEARNINGS (MUST NOT BE FORGOTTEN)

### **🚫 ENDLESS LOOPS - ABSOLUTE PROHIBITION**
- **NEVER** enter endless analysis loops where you repeatedly analyze the same code sections without taking action
- **NEVER** repeatedly identify the same bug without fixing it
- **STOP** immediately when user says "You're looping" or "You seem stuck"
- **TAKE ACTION** instead of endless analysis - if you see a bug, fix it immediately
- **RECOGNIZE PATTERNS**: If you've analyzed the same issue 3+ times, STOP and act

### **🔧 PERMANENT VS TEMPORARY CODE**
- **ALWAYS** modify permanent modules (`app/temporal_flow_report.py`, `app/density_report.py`) instead of creating temporary scripts
- **ASK** if unsure whether code should be permanent or temporary
- **AVOID** creating standalone scripts for functionality that could be permanent
- **PRINCIPLE**: If functionality will be used repeatedly, it belongs in permanent modules

### **🐛 CRITICAL BUG PATTERNS**
- **TYPO BUGS**: Simple typos can cause massive regressions (e.g., `'flow-type'` vs `'flow_type'`)
- **ALWAYS** check for typos in variable names, especially when debugging data flow issues
- **VERIFY** that data is flowing correctly through the entire pipeline
- **TEST** immediately after fixing bugs to ensure the fix works

### **⏱️ PERFORMANCE & TESTING**
- **ANALYSIS TAKES TIME**: Complex analysis (temporal flow, density) can take several minutes
- **DON'T INTERRUPT** long-running processes unless there's a clear error
- **BE PATIENT** with computationally intensive operations
- **VERIFY SUCCESS**: Check that files are generated and contain expected data

### **📊 REPORT QUALITY STANDARDS**
- **HUMAN READABILITY**: All reports must be formatted for human consumption
- **CONSISTENT DECIMALS**: Use max 3 decimal places, remove trailing zeros
- **NO "N/A" VALUES**: Replace with actual values or meaningful defaults
- **NORMALIZED VALUES**: Use 0.0-1.0 ranges for normalized metrics
- **PERCENTAGES**: Always include percentage calculations where relevant

### **🔄 WORKFLOW DISCIPLINE**
- **COMMIT FREQUENTLY**: Make commits after testing and verification
- **USE DEV BRANCHES**: Work on version branches (e.g., v1.6.2-dev)
- **DOCUMENT CHANGES**: Always update CRITICAL_CONFIGURATION.md with new learnings
- **TEST COMPREHENSIVELY**: Run end-to-end tests before considering work complete

### **🔧 DEBUG SCRIPT CONSISTENCY**
- **CRITICAL RULE**: Any debug script MUST use the same variables and values as the actual algorithm
- **NEVER** use different tolerance values, step sizes, or constants in debug scripts
- **ALWAYS** import and use the same constants from `app/constants.py` in debug scripts
- **EXAMPLE**: If algorithm uses `TEMPORAL_OVERLAP_TOLERANCE_SECONDS = 5.0`, debug script must use the same value
- **CONSEQUENCE**: Using different values wastes debugging time and creates false comparisons with historical reports
- **VERIFICATION**: Before debugging, check that debug script imports the same constants as the algorithm

## Issue Completion Workflow

**CRITICAL: After completing an Issue and all of its sub-issues, ALWAYS follow these 7 steps:**

### 0. Create Development Branch (FIRST STEP)
- Create new development branch for the issue (e.g., v1.6.2-dev)
- Branch should be based on latest main
- All work for the issue should be done on this branch
- **This is the FIRST step before any development work**

## Git Workflow and Branch Management

### **🚨 CRITICAL BRANCH CREATION RULES**

**BEFORE creating any new branch, you MUST:**

1. **Test the source branch first** - If creating from `main`, test `main` to ensure it's working
2. **Verify expected results** - Run flow analysis and confirm results match expected values
3. **Get user approval** - Never create branches without explicit user approval
4. **Document the decision** - Explain why this branch is needed and what it will accomplish

### **🚫 PROHIBITED ACTIONS**
- **NEVER** create branches without testing the source branch first
- **NEVER** merge PRs to main without user approval
- **NEVER** assume a branch is working without verification
- **NEVER** create branches from potentially broken foundations

### **✅ REQUIRED WORKFLOW**
```
1. Test source branch (e.g., main) → Verify it works correctly
2. Get user approval → "Should I create v1.6.5 from main?"
3. Create branch → Only after approval and verification
4. Test new branch → Verify it works as expected
5. Document results → Update todos and commit changes
```

### **Branch Creation Checklist**
- [ ] Source branch tested and working
- [ ] Expected results verified
- [ ] User approval obtained
- [ ] Branch purpose clearly defined
- [ ] Testing plan established

### 1. Update CHANGELOG.md
- Add comprehensive entry documenting all changes
- Include technical implementation details and commit history
- Follow existing changelog format and structure

### 2. Commit Changes
- Commit all remaining changes (CHANGELOG.md, documentation updates, etc.)
- Use descriptive commit messages referencing the issue
- Ensure all work is properly committed before creating PR

### 3. Create Pull Request
- Create PR from feature branch to main
- Include comprehensive description with objectives, changes, and testing results
- Link to the original issue
- Use clear, descriptive PR title

### 4. Merge PR to Main
- Review PR for completeness
- Merge to main branch (preferably with merge commit for history)
- Delete feature branch after merge

### 5. Monitor GitHub Workflow
- Watch GitHub Actions workflow for deployment
- Monitor build, test, and deployment status
- Review Cloud Run logs if deployment issues occur
- Ensure successful deployment before proceeding

### 6. Run End-to-End Tests Using API
- Test all API endpoints through main.py (NOT direct module calls)
- Verify all functionality works through the web interface
- Test report generation endpoints specifically
- Confirm all endpoints return 200 status codes

### 7. Verify Reports and Human-Readability
- Generate all 3 report types (temporal_flow.md, temporal_flow.csv, density.md)
- Verify report content quality and human-readability
- Confirm proper event names, segment names, and formatting
- Ensure no generic names, NaN values, or formatting issues
- Validate actual results match expectations

**This workflow ensures quality, reliability, and proper deployment for every issue completion.**

## Common Pitfalls to Avoid

1. **File References** - Use correct file names (runners.csv, segments_new.csv)
2. **Report Generation** - Use actual report modules, not temporary code
3. **Testing** - Generate real markdown/CSV reports, not JSON data
4. **Import References** - Update all imports after file renames
5. **API Testing** - Always test through main.py APIs, not direct module calls
6. **JSON Serialization** - Watch for NaN values that break API responses
7. **Issue Completion Workflow** - ALWAYS follow the 7-step workflow above
8. **Development Branch** - ALWAYS create a new branch for each parent issue before starting work
9. **HARDCODED VALUES** - NEVER use hardcoded values unless explicitly directed. This is a critical rule that has been emphasized multiple times.
10. **DEBUG SCRIPT CONSISTENCY** - ALWAYS use the same constants and values in debug scripts as the actual algorithm. Using different values wastes time and creates false comparisons.
11. **Application Fundamentals** - Refer to `docs/Application Fundamentals.md` for core concepts
12. **🚨 BRANCH CREATION WITHOUT TESTING** - NEVER create branches without first testing the source branch. This leads to broken branches built on broken foundations.
13. **🚨 MERGING WITHOUT APPROVAL** - NEVER merge PRs to main without explicit user approval. Always get permission before merging.
14. **🚨 MANUAL API TESTING** - NEVER manually construct curl commands or guess API parameters. Always use automated test scripts (`python e2e.py --local`). Manual API calls waste time and lead to errors.
15. **🚨 GUESSING PRODUCTION URLS** - NEVER guess production URLs or endpoints. Always use the documented production environment details in this configuration file. URL guessing wastes time and leads to failed tests.
16. **🚨 TESTING METHODOLOGY INCONSISTENCY** - NEVER use different testing approaches for local vs Cloud Run testing. Always use the SAME automated testing module (`python e2e.py --local`) with appropriate environment variables. Inconsistent testing methodologies make results incomparable and unreliable.

## **🚨 CRITICAL: 9-STEP MERGE/TEST PROCESS (UPDATED)**

**MANDATORY**: This is the updated workflow that MUST be followed for ALL releases and merges. No exceptions.

### **Step 1: Verify Dev Branch Health**
- Check git status and recent commits
- Ensure all changes are committed to dev branch
- Verify branch is ready for merge

### **Step 2: Run Final E2E Tests on Dev Branch**
- Ensure all tests pass before merge
- Use `python e2e.py --local`
- Verify no regressions detected

### **Step 3: Create Pull Request**
- Create PR from dev branch to main
- Include comprehensive description and testing results
- Wait for user review and approval

### **Step 4: Wait for User Review/Approval**
- User will review and merge via GitHub Desktop or Web UI
- **NEVER merge without user approval**

### **Step 5: Verify Merge to Main**
- Check git status and recent commits after user merge
- Pull latest changes from origin/main

### **Step 6: Run Final E2E Tests on Main**
- Confirm no regressions after merge
- Use `python e2e.py --local`
- Verify all tests pass

### **Step 7: Create Release with Assets**
- Include latest reports as release assets
- Use `gh release create` with proper description

### **Step 8: Add E2E Files to Release**
- Attach Flow.md, Flow.csv, Density.md, E2E.md to release
- Use `gh release upload` command

### **Step 9: Verify Release and Run Final E2E Tests**
- Confirm release is complete and working
- Run final E2E tests to verify everything works

**This 9-step process replaces the previous 7-step workflow and must be followed for all releases.**

## **🚨 CRITICAL: CI WORKFLOW CONSOLIDATION**

**Current Status**: Three separate CI workflows have been consolidated into a single `ci-pipeline.yml` with four jobs:

1. **Build and Test** - Compiles code and runs tests
2. **Deploy to Cloud Run** - Deploys to production environment
3. **Automated Release** - Creates GitHub releases with assets
4. **Upload Release Assets** - Attaches reports and E2E files to releases

**Key Features**:
- Lightweight E2E testing (skips computationally intensive endpoints)
- Automated release creation with proper asset attachment
- `GH_TOKEN` environment variable for release operations
- Consolidated workflow reduces complexity and maintenance

**Files Modified**:
- `.github/workflows/ci-pipeline.yml` - Single consolidated workflow
- Removed: `version-check.yml`, `release.yml` (consolidated)

## **🚨 CRITICAL: WORKFLOW VIOLATIONS - LESSONS LEARNED**

**MAJOR VIOLATION**: Direct changes to main branch (Issue #134)
- **What Happened**: Initial implementation made changes directly to main instead of using dev branch
- **Impact**: Required reverting to v1.6.18 and losing several hours of work
- **Prevention**: Always create dev branch for all work, never modify main directly

**Secondary Violations**:
- Over-engineering beyond scope requirements
- Not following Pre-task safeguards
- Making extensive changes without user approval

**Prevention Measures**:
1. Always reference Pre-task safeguards before starting work
2. Never make changes directly to main branch
3. Create dev branch for all work
4. Stay within scope of requirements
5. Test frequently and commit incrementally
6. Wait for user approval before merging

## Last Updated
2025-09-11 - Added 9-step merge/test process, CI workflow consolidation details, and critical workflow violation lessons learned from Issue #134

## Related Issues
- #32 - Distance gaps fix
- #33 - Density diagnostics logging  
- #34 - File renames
- #35, #36, #37 - Testing sub-issues
