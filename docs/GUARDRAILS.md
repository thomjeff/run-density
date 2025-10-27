
# Guardrails for AI-Assisted Development

**Version:** 1.1  (replaces /archive/guardrails.md)
**Last Updated:** 2025-10-27  
**Applies to:** Cursor, ChatGPT w/ Code Interpreter, GitHub Copilot (read-only), VSCode AI Agents (custom plugins)  

⚠️ **CRITICAL**: This document contains NON-NEGOTIABLE RULES for AI pair programming assistants. These rules were established through hard-learned lessons and MUST be followed without exception.

---

## 📋 MANDATORY DOCUMENT REFERENCES

Before starting ANY work, you **MUST** reference these documents:

- `@GUARDRAILS.md` – This document
- `@ARCHITECTURE.md` – System design and core concepts
- `@VARIABLE_NAMING_REFERENCE.md` – Authoritative variable names and field mappings
- `@OPERATIONS.md` – Deployment, monitoring, and version control

---

## ✅ MANDATORY RULE CONFIRMATION

Before any code or tests are written, confirm the following:

```
✅ CONFIRMING CRITICAL RULES:
1. NO HARDCODED VALUES – Use app/constants.py and config files only
2. PERMANENT CODE ONLY – No temp scripts or isolated experiments
3. START TIME CONSTANTS – Use constants.START_TIMES from app/constants.py
4. API TESTING ONLY – Always test via app/main.py endpoints
5. MINIMAL CHANGES – Make small, testable commits
6. NO ENDLESS LOOPS – Stop after 3 failed analysis attempts and ask
7. STRICT TYPOS – Match variable names exactly to references
8. NAMING CONVENTIONS – Use field names from VARIABLE_NAMING_REFERENCE.md
9. TODO PERMISSION – Ask before creating task lists or suggestions
10. GITHUB CONTEXT – Read entire GitHub issue + all comments
11. CLARITY FIRST – STOP and ask if any instruction is unclear
```

---

## 📁 CRITICAL FILE REFERENCES

### ✅ Always Use:
- `data/runners.csv`
- `data/segments.csv`
- `data/flow_expected_results.csv`
- `config/density_rulebook.yml`
- `config/reporting.yml`
- `app/constants.py`

### ❌ Never Use:
- `data/segments_old.csv`
- `data/your_pace_data.csv` (archived)

### Directory Structure
```
/app          – Core application code
/config       – YAML configuration
/data         – Input CSVs only
/docs         – Internal documentation
/frontend     – Static files
/tests        – Unit and integration tests
/reports      – Auto-generated results
/cache        – Git-ignored analysis cache
/archive      – Historical snapshots
```

---

## 🐍 PYTHON ENVIRONMENT

### Activate Before All Python Work:
```bash
source test_env/bin/activate
```

### Deactivate for Git or CLI:
```bash
deactivate
```

Signs you forgot:
- `ModuleNotFoundError: No module named 'pandas'`
- Commands fail or misbehave

---

## 🧪 TESTING GUARDRAILS

1. Activate venv
2. Use: `python e2e.py --local` for local testing
3. Do NOT test via curl or isolated modules
4. Validate output reports (CSV + MD)
5. Check constants are used, not hardcoded values

### For Unit Testing:
```bash
pytest tests/test_*.py
```

### For Cloud Run Validation:
```bash
TEST_CLOUD_RUN=true python e2e.py --cloud
```

---

## 🔍 GITHUB ISSUES

You MUST:
- Read full title, description, and **all** comments
- Use `gh issue view <number> --comments`
- Never summarize or skip subthreads
- GitHub is the source of truth - issues persist across Cursor sessions.
- Complete context is required - missing context leads to failed outcomes. Why critical:
  - Comments contain implementation strategies
  - ChatGPT answers provide specific technical details
  - User feedback and decisions documented
  - Incomplete reading causes rework

---

## 🚫 PROHIBITED ACTIONS

- Developing in `main` - all dev/hotfix/bugfix must be done in branch
- Pushing to `main` directly
- Force pushing any branch
- Skipping E2E tests for logic-affecting changes
- Hardcoding thresholds, timing, or config logic
- Mixing time units (e.g., min/km with sec/km)
- Guessing API formats or variable names
- Creating unrequested todos
- Leaving ambiguity unresolved

---

## 🔁 MERGE AND RELEASE PROCESS

Follow this sequence:

1. ✅ Confirm local branch health
2. ✅ Run: `python e2e.py --local`
3. ✅ Create PR with testing proof
4. ✅ Wait for user to review and merge manually
5. ✅ CI runs all Cloud Run tests: monitor workflow logs and Cloud Run logs during execution.
6. ✅ Confirm CI workflow completed without errors. All 4 stages must pass (Build, E2E, Bin Datasets, Release). CI runs the full E2E tests on Cloud Run automatically
7. ✅ Wait for the user to review the deployed code with manual testing via UI.
8. ✅ Tag release and upload:
   - `Flow.csv`
   - `Density.md`

**When to Skip E2E Tests:**
- **Documentation-only changes** (README, GUARDRAILS, docs/)
- **Validation-only features** (frontend/validation/ - operates independently)
- **CI/CD configuration** (.github/workflows/ - validated by CI itself)
- **Non-code assets** (frontend/assets/, archive/)

**Monitoring Commands:**
```bash
# Check recent runs
gh run list --limit 5

# View run details
gh run view <run-id>

# Check logs for errors
gh run view <run-id> --log 2>&1 | grep -E "(ERROR|FAIL)"
```

---

## ☁️ CLOUD RUN CONFIG (PROD)

- **URL**: https://run-density-...a.run.app
- **Timeout**: 600s
- **Resources**: 3GB / 2CPU (verify using Google CLI as resources might have changed)
- **Check**: `gcloud run services describe ...`

---

## 🐛 COMMON FAILURE PATTERNS

### Zeroes in Reports?
1. **Check time unit consistency**
   - Start times: minutes → seconds (`* 60.0`)
   - Pace: minutes/km → seconds/km (`* 60.0`)
   - **Bug pattern**: `start_a = start_times.get(event_a, 0) * 60.0` but `start_b = start_times.get(event_b, 0)` ❌

2. **Verify data filtering logic**
   - Check if filtered datasets are empty
   - Log boundary values
   - Validate intersection calculations

3. **Validate algorithm assumptions**
   - Reuse proven functions
   - Compare with working reference code
   - Test with known good data first

### CI Fails?
1. **Check /config directory** - Ensure Dockerfile copies it
2. **Verify resource constraints** - CI has required resources 3GB RAM / 2 CPU is recommended.
3. **Check schema changes** - Update validation scripts (e.g., `scripts/validation/verify_bins.py`)
4. **Review deployment logs** - `gh run view <run-id> --log`

---

## 📎 RELEASE CHECKLIST

Every release needs:
- ✅ `Flow.csv`, `Density.md` attached
- ✅ Cloud Run validated
- ✅ Version consistency with Git tag
- ✅ Confirmation from CI logs

---

## 🎯 SUCCESS CRITERIA

Work is complete ONLY when:
- ✅ All code uses constants.py, no hardcoded values
- ✅ All testing done through API endpoints
- ✅ All reports generate correctly with proper formatting
- ✅ All changes committed to feature branch
- ✅ All validation tests pass
- ✅ 9-step merge/test process completed
- ✅ Production deployment verified (Cloud Run + local)
- ✅ Release assets attached (if version bumped)

---

## 🚨 REMINDERS FOR AI AGENTS

- No session memory: re-check guardrails every time
- Never guess — ask for clarity to user or ChatGPT as Senior Architect and QA Analyst
- Always test via documented endpoints
- Stop after ambiguity or repeated failures

**Common mistakes made by prior AI agents:**
Never do these things:
1. Hardcoding values instead of using constants
2. Creating temporary scripts instead of permanent code
3. Manually testing APIs instead of using e2e.py
4. Pushing to main without PR review
5. Skipping E2E tests after changes
6. Guessing production URLs instead of using documented values
7. Using inconsistent testing methodologies (local vs cloud)
8. Incomplete GitHub issue reading (missing comments)
9. Forgetting to activate the virtual environment before running e2e.py tests.
10. Mixing time units without conversion

**Remember**: These guardrails exist because they've been violated before, causing significant debugging overhead. Follow them strictly to maintain code quality and development velocity.