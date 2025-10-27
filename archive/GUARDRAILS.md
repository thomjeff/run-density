# Guardrails for AI-Assisted Development

**Version:** 1.0
Replaced by a newer version on 2025-10-27

⚠️ **CRITICAL**: This document contains NON-NEGOTIABLE RULES for AI pair programming assistants (Cursor, ChatGPT, etc.). These rules have been established through hard-learned lessons and MUST be followed without exception.

## **📋 MANDATORY DOCUMENT REFERENCES**

Before starting ANY work, you **MUST** reference these documents:
- `@GUARDRAILS.md` (this file) - Critical rules and workflows
- `@ARCHITECTURE.md` - System design and core concepts
- `@VARIABLE_NAMING_REFERENCE.md` - Authoritative variable names and field mappings
- `@OPERATIONS.md` - Deployment, monitoring, and version management

## **✅ MANDATORY RULE CONFIRMATION**

You **MUST** explicitly confirm understanding of these CRITICAL RULES before proceeding:

```
✅ CONFIRMING CRITICAL RULES:
1. NO HARDCODED VALUES - will use app/constants.py and dynamic calculations
2. PERMANENT CODE ONLY - will modify existing modules, not create temp scripts
3. CORRECT START TIMES - will use {'Full': 420, '10K': 440, 'Half': 460}
4. API TESTING - will test through main.py endpoints, not direct module calls
5. MINIMAL CHANGES - will make only necessary changes and test frequently
6. NO ENDLESS LOOPS - will stop and consult the user after 3 failed analysis attempts
7. TYPO CHECKING - will verify variable names and data flow integrity
8. VARIABLE NAMING - will use correct field names (e.g.: seg_label not segment_label, from_km not 10K_from_km)
9. TODO PERMISSION - will ask for permission before creating todo lists when user asks for thoughts
10. COMPLETE GITHUB ISSUE READING - will read ENTIRE GitHub issues, including ALL comments, no shortcuts
```

## **📁 CRITICAL FILE REFERENCES**

### Data Files
- **ALWAYS use**: `data/runners.csv`, `data/segments.csv`, `data/flow_expected_results.csv`
- **NEVER use**: `data/segments_old.csv`, `data/your_pace_data.csv` (archived)

### Configuration Files  
- **ALWAYS use**: `config/density_rulebook.yml`, `config/reporting.yml`
- **ALWAYS use**: `app/constants.py` for all configuration values
- **NEVER hardcode**: variables, like: start times, tolerance values, conflict lengths, thresholds

### Directory Structure
```
/app          - Application code
/config       - YAML configuration files (density_rulebook.yml, reporting.yml)
/data         - CSV input files only (runners.csv, segments.csv, flow_expected_results.csv)
/docs         - Documentation
/frontend     - HTML/CSS/JS frontend files
/tests        - Test suites
/reports      - Generated reports (gitignored)
/cache        - Analysis cache (gitignored)
/archive      - Historical files
```

## **🐍 MANDATORY ENVIRONMENT SETUP**

### Virtual Environment Activation

**CRITICAL**: Before running ANY Python commands, activate the virtual environment:

```bash
# ALWAYS start a local env
source test_env/bin/activate

# THEN run your commands
python e2e.py --local
```

**Why this is critical:**
- Prevents `ModuleNotFoundError` (system Python lacks dependencies)
- Ensures correct package versions
- Maintains consistency with production
- Avoids wasted debugging time

**Signs you forgot to activate:**
- `ModuleNotFoundError: No module named 'fastapi'`
- `ModuleNotFoundError: No module named 'pandas'`
- Any import errors when running Python

**Remember**: Virtual environment activation does NOT persist between terminal sessions!

### When to Deactivate

**CRITICAL**: Deactivate the virtual environment for non-Python work:

```bash
# For Python/E2E work
source test_env/bin/activate
python e2e.py --local

# For GitHub CLI, git, system commands
deactivate
gh issue create --title "Example"
git commit -m "message"
```

**Why deactivate:**
- GitHub CLI works better outside venv
- System commands have full access
- Prevents unexpected command failures
- Cleaner separation of concerns

## **🧪 MANDATORY TESTING SEQUENCE**

After ANY code changes, you **MUST**:

1. **ACTIVATE VIRTUAL ENVIRONMENT FIRST**: `source test_env/bin/activate`
2. **USE AUTOMATED TEST SCRIPTS ONLY**: `python e2e.py --local`
3. **NEVER manually construct curl commands** - wastes time, causes errors
4. **NEVER guess API parameters** - use automated scripts
5. **MAINTAIN TESTING CONSISTENCY** - same methodology for local & Cloud Run
6. **FOR LOCAL**: `python e2e.py --local` (full E2E)
7. **FOR CLOUD RUN**: `TEST_CLOUD_RUN=true python e2e.py --cloud`
8. **FOR CI PIPELINE**: Automatically uses resource constraints
9. Generate actual reports (MD + CSV), not just JSON
10. Verify no hardcoded values introduced
11. Test through API endpoints, not direct module calls
12. Validate report content quality and readability

### Testing Methodology

```bash
# Local E2E (full testing)
source test_env/bin/activate
python e2e.py --local

# Cloud Run E2E (production validation)
source test_env/bin/activate
TEST_CLOUD_RUN=true python e2e.py --cloud

# Unit tests
pytest tests/test_*.py

# QA regression (Issue #243 fix verification)
python tests/qa_regression_baseline.py
```

### **🚫 PROHIBITED TESTING ACTIONS**
- **NEVER** manually construct curl commands for API testing
- **NEVER** guess API endpoint parameters or request formats
- **NEVER** waste time looking up API calls when automated scripts exist
- **NEVER** modify code to "fix" API calls instead of using proper testing
- **NEVER** use different methodologies for local vs Cloud Run
- **NEVER** compare results from different testing approaches

## **📋 MANDATORY GITHUB ISSUE READING**

When reading GitHub issues, you **MUST**:

1. **Read the ENTIRE issue** - Title, description, acceptance criteria, all sections
2. **Read ALL comments** - Use `gh issue view <number> --comments` for complete context
3. **No shortcuts or skimming** - Every comment contains important details
4. **GitHub is source of truth** - Issues persist across Cursor sessions
5. **Complete context required** - Missing comments leads to incomplete implementation

**Command**: `gh issue view <issue-number> --comments`

**Why critical:**
- Comments contain implementation strategies
- ChatGPT answers provide specific technical details
- User feedback and decisions documented
- Incomplete reading causes rework

## **🚫 PROHIBITED GITHUB ACTIONS**

### Git Commands
- **NEVER** push directly to main - always use PRs
- **NEVER** force push to main/master
- **NEVER** skip hooks (--no-verify, --no-gpg-sign)
- **NEVER** commit unless explicitly asked
- **NEVER** update git config

### GitHub CLI Commands
- **NEVER** use complex multi-line strings in `gh issue comment`
- **NEVER** include unescaped quotes, backticks, special chars
- **NEVER** use complex JSON/code blocks in single-line commands
- **ALWAYS** use simple comment bodies or write to files first
- **IF** complex formatting needed, use `gh issue comment --body-file`

## **🚫 PROHIBITED CODING PRACTICES**

### Time Calculations
- **NEVER** mix time units without explicit conversion (minutes vs seconds)
- **NEVER** convert only one event's start time (convert ALL consistently)
- **ALWAYS** convert: `start_a = start_times.get(event_a, 0) * 60.0`
- **ALWAYS** verify time calculations with unit tests
- **NEVER** assume time values are in same units without checking

### Hardcoded Values
- **NEVER** hardcode start times, thresholds, lengths, tolerances
- **ALWAYS** use `app/constants.py` for configuration
- **ALWAYS** use config files (`config/density_rulebook.yml`, `config/reporting.yml`)
- **NEVER** use placeholder values like `random.randint(0, 5)` in production code

### Variable Naming
- **ALWAYS** use correct field names per `@VARIABLE_NAMING_REFERENCE.md`
- **Examples**: `seg_label` not `segment_label`, `from_km` not `10K_from_km`
- **NEVER** guess variable names - check the reference doc

## **🚀 9-STEP MERGE/TEST PROCESS**

For ALL releases and merges, follow this complete process:

1. **Verify Dev Branch Health** - Check git status and recent commits
2. **Run Final E2E Tests on Dev Branch** - `python e2e.py --local` must pass
   - **Exception**: Skip for non-application changes (docs, validation-only features, CI configs)
   - **Rationale**: E2E tests validate core application behavior; changes isolated to separate systems don't require full E2E
3. **Create Pull Request** - Comprehensive description + testing results
   - **Note**: PR creation/merge automatically triggers CI/CD pipeline (Build, Deploy, E2E)
   - **Alternative**: For non-application changes, can merge directly to main (triggers CI automatically)
4. **Wait for User Review/Approval** - User reviews and merges via GitHub UI (or merge directly if authorized)
5. **Verify Merge to Main** - `git checkout main && git pull`
6. **Monitor CI/CD Pipeline** - All 4 stages must pass (Build, E2E Cloud Run, Bin Datasets, Release)
   - **Automated E2E**: CI runs full E2E tests on Cloud Run automatically
   - **Skip Manual E2E**: Local E2E tests (Step 2, 7) are redundant if CI passes
7. **Run E2E Tests on Main Locally** - `python e2e.py --local` (validates next dev baseline)
   - **Optional**: Skip if CI E2E tests passed and change doesn't affect application code
   - **Purpose**: Ensures next dev branch starts from healthy main baseline
8. **Verify Production Health** - All endpoints responding correctly

**When to Skip E2E Tests:**
- **Documentation-only changes** (README, GUARDRAILS, docs/)
- **Validation-only features** (frontend/validation/ - operates independently)
- **CI/CD configuration** (.github/workflows/ - validated by CI itself)
- **Non-code assets** (frontend/assets/, archive/)

**When E2E Tests Are Required:**
- Changes to `app/` directory (core application logic)
- Changes to `data/` files (inputs that affect analysis)
- Changes to `config/` files (rulebook, reporting configuration)
- API endpoint modifications (`app/main.py`, `app/routes/`)
- Dependency updates (`requirements.txt` affecting main app)

**Note**: Step 7 ensures next dev branch starts from healthy main.
**Note**: Cloud Run E2E tests run automatically in CI (Step 6, stage 2). Manual Cloud Run testing is redundant.
**Note**: PR merge to main automatically triggers CI/CD pipeline. No manual deployment needed.

## **🔄 AUTOMATED CI/CD PIPELINE**

### Pipeline Triggers
- **Push to main**: Automatically deploys to Cloud Run
- **Pull requests**: Runs validation tests only
- **Manual dispatch**: Can trigger via GitHub Actions

### Pipeline Stages
1. **Build & Deploy**: Docker → Artifact Registry → Cloud Run
2. **E2E Tests**: Density/Flow reports, Bin datasets validation
3. **Version Check**: Validates app version consistency
4. **Automated Release**: Creates release if version is new

### CI E2E Testing Scope

**What CI Tests:**
- Health endpoints (`/health`, `/ready`)
- Density reports (`/api/density-report`)
- Temporal flow reports (`/api/temporal-flow-report`)
- Bin dataset quality validation

**What CI Skips** (resource constraints):
- Heavy temporal flow analysis
- Large dataset processing
- Full flow audit

### Critical Warnings
- **Cloud Run auto-deploys** - Every main push goes to production
- **Pipeline failures block releases** - Fix CI before creating releases
- **Version consistency required** - App version must match git tags

### Monitoring Commands
```bash
# Check recent runs
gh run list --limit 5

# View run details
gh run view <run-id>

# Check logs for errors
gh run view <run-id> --log 2>&1 | grep -E "(ERROR|FAIL)"
```

## **🎯 PRODUCTION ENVIRONMENT**

### Cloud Run Service
- **URL**: https://run-density-ln4r3sfkha-uc.a.run.app
- **Region**: us-central1
- **Resources**: 3GB RAM / 2 CPU (default config - verify before starting work)
- **Timeout**: 600 seconds
- **Verify Config**: Always check actual resources with `gcloud run services describe run-density --region=us-central1 --format="table(spec.template.spec.containers[0].resources.limits)"`
- **Revision**: You MUST verify the latest revision - or the one you're expecting - is serving 100% of the inbound traffic. 

### API Endpoints
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `POST /api/density-report` - Generate density analysis
- `POST /api/temporal-flow-report` - Generate flow analysis
- `GET /api/segments` - Segment data with operational intelligence
- `GET /api/tooltips` - Operational intelligence tooltips

### Testing Against Production
```bash
source test_env/bin/activate
TEST_CLOUD_RUN=true python e2e.py --cloud
```

**NEVER** manually construct curl commands - always use automated test scripts!

## **🐛 COMMON DEBUGGING PATTERNS**

### When Algorithms Return Zero Values

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

### When Tests Fail in CI

1. **Check /config directory** - Ensure Dockerfile copies it
2. **Verify resource constraints** - CI has 1GB RAM / 1 CPU limits
3. **Check schema changes** - Update validation scripts (e.g., `scripts/validation/verify_bins.py`)
4. **Review deployment logs** - `gh run view <run-id> --log`

## **📎 MANDATORY RELEASE ASSETS**

For EVERY release, attach these files:
- **Flow.md** - Latest temporal flow analysis report
- **Flow.csv** - Latest temporal flow data  
- **Density.md** - Latest density analysis report

**Command**: `gh release upload <version> Flow.md Flow.csv Density.md`

**Note**: E2E results captured in GitHub Actions logs, not separate files.

## **✅ SUCCESS CRITERIA**

Work is complete ONLY when:
- ✅ All code uses constants.py, no hardcoded values
- ✅ All testing done through API endpoints
- ✅ All reports generate correctly with proper formatting
- ✅ All changes committed to feature branch
- ✅ All validation tests pass
- ✅ 9-step merge/test process completed
- ✅ Production deployment verified (Cloud Run + local)
- ✅ Release assets attached (if version bumped)

## **🚨 CRITICAL REMINDERS**

### For Cursor/AI Assistants
- You cannot persist memory between conversations
- Always reference these documents at session start
- GitHub issues are your persistent data store
- Test frequently, commit at milestones
- Ask for clarification rather than guessing

### Common Violations (NEVER DO THESE)
1. ❌ Hardcoding values instead of using constants
2. ❌ Creating temporary scripts instead of permanent code
3. ❌ Manually testing APIs instead of using e2e.py
4. ❌ Pushing to main without PR review
5. ❌ Skipping E2E tests after changes
6. ❌ Guessing production URLs instead of using documented values
7. ❌ Using inconsistent testing methodologies (local vs cloud)
8. ❌ Incomplete GitHub issue reading (missing comments)
9. ❌ Forgetting to activate virtual environment
10. ❌ Mixing time units without conversion

---

**Remember**: These guardrails exist because they've been violated before, causing significant debugging overhead. Follow them strictly to maintain code quality and development velocity.

