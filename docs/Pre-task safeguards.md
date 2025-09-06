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
3. CORRECT START TIMES - will use {'10K': 420, 'Half': 440, 'Full': 460}
4. API TESTING - will test through main.py endpoints, not direct module calls
5. MINIMAL CHANGES - will make only necessary changes and test frequently
6. NO ENDLESS LOOPS - will take action after 3 analysis attempts, not repeat analysis
7. TYPO CHECKING - will verify variable names and data flow integrity
```

## **🧪 MANDATORY TESTING SEQUENCE**

After ANY code changes, you **MUST**:
1. Run end-to-end tests: `python3 -m app.end_to_end_testing`
2. Generate actual reports (MD + CSV), not just JSON data
3. Verify no hardcoded values were introduced
4. Test through API endpoints, not direct module calls
5. Validate report content quality and human readability

## **📁 CRITICAL FILE REFERENCES**

- **ALWAYS use**: `data/runners.csv`, `data/segments_new.csv`
- **NEVER use**: `data/your_pace_data.csv`, `data/segments_old.csv`
- **ALWAYS use**: `app/constants.py` for configuration values
- **NEVER hardcode**: start times, tolerance values, conflict lengths

## **✅ SUCCESS CRITERIA**

Work is complete ONLY when:
- All code changes use constants.py, no hardcoded values
- All testing done through API endpoints
- All reports generate correctly with proper formatting
- All changes committed to version branch (e.g., v1.6.3-flow-debug)
- All validation tests pass

---

**Remember**: You cannot persist memory between conversations. Always reference these documents and confirm understanding before starting work.