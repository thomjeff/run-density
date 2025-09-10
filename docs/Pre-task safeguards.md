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
1. **USE AUTOMATED TEST SCRIPTS ONLY**: `python3 -m app.end_to_end_testing`
2. **NEVER manually construct curl commands** - this wastes time and leads to errors
3. **NEVER guess API parameters** - use the automated scripts that know the correct endpoints
4. **MAINTAIN TESTING CONSISTENCY** - Use the SAME testing methodology for both local and Cloud Run testing
5. **FOR CLOUD RUN TESTING**: Use `TEST_CLOUD_RUN=true python3 -m app.end_to_end_testing`
6. **FOR LOCAL TESTING**: Use `python3 -m app.end_to_end_testing` (without TEST_CLOUD_RUN)
7. Generate actual reports (MD + CSV), not just JSON data
8. Verify no hardcoded values were introduced
9. Test through API endpoints, not direct module calls
10. Validate report content quality and human readability

### **🚫 PROHIBITED TESTING ACTIONS**
- **NEVER** manually construct curl commands for API testing
- **NEVER** guess API endpoint parameters or request formats
- **NEVER** waste time looking up correct API calls when automated scripts exist
- **NEVER** modify code to "fix" API calls instead of using proper automated testing
- **NEVER** use different testing methodologies for local vs Cloud Run testing
- **NEVER** compare results from different testing approaches

## **📁 CRITICAL FILE REFERENCES**

- **ALWAYS use**: `data/runners.csv`, `data/segments_new.csv`
- **NEVER use**: `data/your_pace_data.csv`, `data/segments_old.csv`
- **ALWAYS use**: `app/constants.py` for configuration values
- **NEVER hardcode**: start times, tolerance values, conflict lengths

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