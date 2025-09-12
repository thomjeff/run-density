# Pre-Task Safeguards

⚠️ **CRITICAL**: This document contains NON-NEGOTIABLE RULES that have been violated multiple times, causing significant debugging issues. These rules MUST be followed without exception.

## **📋 MANDATORY DOCUMENT REFERENCES**

Before starting ANY work, you **MUST** reference these three documents:
- `@CRITICAL_CONFIGURATION.md` - Critical rules and workflow requirements
- `@Application Fundamentals.md` - Core concepts and data structures  
- `@Application Architecture.md` - System design and testing patterns

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
```

## **🧪 MANDATORY TESTING SEQUENCE**

After ANY code changes, you **MUST**:
1. **ACTIVATE VIRTUAL ENVIRONMENT FIRST**: `source .venv/bin/activate` (CRITICAL - prevents ModuleNotFoundError)
2. **USE AUTOMATED TEST SCRIPTS ONLY**: `python3 -m app.end_to_end_testing`
3. **NEVER manually construct curl commands** - this wastes time and leads to errors
4. **NEVER guess API parameters** - use the automated scripts that know the correct endpoints
5. **MAINTAIN TESTING CONSISTENCY** - Use the SAME testing methodology for both local and Cloud Run testing
6. **FOR CLOUD RUN TESTING**: Use `TEST_CLOUD_RUN=true python3 -m app.end_to_end_testing`
7. **FOR LOCAL TESTING**: Use `python3 -m app.end_to_end_testing` (without TEST_CLOUD_RUN)
8. Generate actual reports (MD + CSV), not just JSON data
9. Verify no hardcoded values were introduced
10. Test through API endpoints, not direct module calls
11. Validate report content quality and human readability

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

## **📁 CRITICAL FILE REFERENCES**

- **ALWAYS use**: `data/runners.csv`, `data/segments_new.csv`
- **NEVER use**: `data/your_pace_data.csv`, `data/segments_old.csv`
- **ALWAYS use**: `app/constants.py` for configuration values
- **NEVER hardcode**: start times, tolerance values, conflict lengths

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

## **🔧 CURRENT DEVELOPMENT ISSUES**

**Active Issues for Development Branch:**
- **Issue #143**: CRITICAL - Cloud Run E2E tests using stale/cached reports (HIGH priority)
- **Issue #144**: Flow zone cleanup - Remove duplicate columns (MEDIUM priority)  
- **Issue #142**: PR E2E artifacts workflow improvements (MEDIUM priority)
- **Issue #131**: Density enhancements (MEDIUM priority)

**Recommended Development Order:**
1. **Issue #144** (Flow zone cleanup) - Safe technical debt, low risk
2. **Issue #142** (PR E2E artifacts) - Process improvement, low risk
3. **Issue #131** (Density enhancements) - Feature work, medium risk
4. **Issue #143** (Cloud Run E2E) - Critical bug, high risk, needs investigation

**Each issue gets its own commit for easy rollback within the branch.**

## **🚀 9-STEP MERGE/TEST PROCESS**

For ALL releases and merges, you **MUST** follow this complete process:

1. **Verify Dev Branch Health** - Check git status and recent commits
2. **Run Final E2E Tests on Dev Branch** - Ensure all tests pass before merge
3. **Create Pull Request** - With comprehensive description and testing results
4. **Wait for User Review/Approval** - User will review and merge via GitHub Desktop or Web UI
5. **Verify Merge to Main** - Check git status and recent commits after user merge
6. **Run Final E2E Tests on Main** - Confirm no regressions after merge
7. **Create Release with Assets** - Include latest reports as release assets
8. **Add E2E Files to Release** - Attach Flow.md, Flow.csv, Density.md, E2E.md to release
9. **Verify Release and Run Final E2E Tests** - Confirm release is complete and working

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