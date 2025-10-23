# Operations Guide

Comprehensive guide for deployment monitoring, version management, and production operations.

## Table of Contents
1. [CI/CD Pipeline](#cicd-pipeline)
2. [Deployment Monitoring](#deployment-monitoring)
3. [Version Management](#version-management)
4. [Production Health Checks](#production-health-checks)
5. [Troubleshooting](#troubleshooting)

---

## CI/CD Pipeline

### Pipeline Overview

Every push to `main` automatically triggers the full deployment pipeline:

```
Push to main
  ↓
Build & Deploy (Docker → Artifact Registry → Cloud Run)
  ↓
E2E Tests (Density/Flow + Bin Datasets)
  ↓
Automated Release (if version is new)
  ↓
Production Live
```

**Total Time**: ~5-6 minutes

### Pipeline Stages

| Stage | Duration | Purpose | Failure Impact |
|-------|----------|---------|----------------|
| **Build & Deploy** | 1-2 min | Docker build, push to registry, deploy to Cloud Run | Blocks deployment |
| **E2E (Density/Flow)** | 3-4 min | Validates density and flow report generation | Blocks release |
| **E2E (Bin Datasets)** | 1-2 min | Validates bin quality and schemas | Blocks release |
| **Automated Release** | 20-30s | Creates GitHub release with assets | Skips if version unchanged |

### Monitoring Commands

```bash
# Check recent workflow runs
gh run list --limit 5

# View workflow details
gh run view <run-id>

# Monitor in real-time
for i in {1..12}; do 
  sleep 30
  gh run list --limit 1 --json status,conclusion
done

# Check logs for errors
gh run view <run-id> --log 2>&1 | grep -E "(ERROR|FAIL)"
```

### Success Criteria

**Workflow completion:**
```
✓ 1️⃣ Build & Deploy (Docker → Artifacts)
✓ 2️⃣ E2E (Density/Flow)
✓ 3️⃣ E2E (Bin Datasets)
✓ 4️⃣ Automated Release
```

**E2E test results:**
```
✅ Health: OK
✅ Ready: OK
✅ Density Report: OK
✅ Temporal Flow Report: OK
```

---

## Deployment Monitoring

### Step-by-Step Process

#### 1. Monitor Initial Workflow
```bash
gh run list --limit 3
```
Look for `in_progress` status on latest workflow.

#### 2. Monitor Progress
```bash
gh run view <workflow-id>
```
Watch each stage complete in sequence.

#### 3. Monitor E2E Tests (Longest Stage)
```bash
gh run view --job=<e2e-job-id>
```
E2E tests typically take 3-4 minutes.

#### 4. Verify Success
```bash
gh run list --limit 1
```
Should show `completed` with `success` conclusion.

### Testing Post-Deployment

#### Cloud Run E2E
```bash
source test_env/bin/activate
TEST_CLOUD_RUN=true python e2e.py --cloud
```

**Expected output:**
```
🎉 ALL TESTS PASSED!
✅ Cloud Run is working correctly
```

#### Local E2E (Main Branch Verification)
```bash
git checkout main
git pull
source test_env/bin/activate
python e2e.py --local
```

Ensures next dev branch starts from healthy main.

### Health Verification

```bash
# Production health check
curl -s https://run-density-ln4r3sfkha-uc.a.run.app/health | jq

# Expected response
{
  "ok": true,
  "status": "healthy",
  "version": "v1.6.42"
}
```

---

## Version Management

### Version Scheme

Run-density uses semantic versioning: `vMAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (v1 → v2)
- **MINOR**: New features, backward compatible (v1.6 → v1.7)
- **PATCH**: Bug fixes, minor improvements (v1.6.42 → v1.6.43)

### Current Version

```bash
# Check current version
python3 -m app.version current
# Output: v1.6.42
```

### Bumping Versions

#### Using Python Module
```bash
# Bump patch version
python3 -m app.version bump patch

# Bump minor version
python3 -m app.version bump minor

# Bump major version
python3 -m app.version bump major
```

#### Using Bash Script
```bash
# Bump patch (most common)
./scripts/bump_version.sh patch

# Bump minor (new features)
./scripts/bump_version.sh minor

# Bump major (breaking changes)
./scripts/bump_version.sh major
```

**The script automatically:**
1. Checks working directory is clean
2. Updates version in `app/main.py`
3. Commits the change
4. Creates git tag
5. Provides push instructions

### Version Consistency

**CRITICAL**: Version in code must match latest git tag.

```bash
# Validate consistency
python3 -m app.version validate

# If mismatch detected, fix before deploying!
```

### Release Process

#### Automated (Recommended)
1. Bump version using script
2. Push changes: `git push origin main`
3. Push tag: `git push origin v1.6.43`
4. CI automatically creates release

#### Manual (If Needed)
```bash
# Create release with assets
gh release create v1.6.43 \
  reports/2025-10-16/*-Flow.md \
  reports/2025-10-16/*-Flow.csv \
  reports/2025-10-16/*-Density.md \
  --title "Release v1.6.43: Description" \
  --notes "Changes and improvements"
```

### When to Bump Version

| Change Type | Bump | Example |
|-------------|------|---------|
| Bug fix | PATCH | Issue #243 (10K timing) |
| New feature | MINOR | Operational intelligence |
| Breaking change | MAJOR | Schema changes |
| Documentation only | NONE | Don't bump for docs-only |
| Refactoring (no behavior change) | PATCH | Code cleanup |

---

## Production Health Checks

### Quick Health Verification

```bash
# One-liner health check
curl -s https://run-density-ln4r3sfkha-uc.a.run.app/health | jq '.ok'
# Should return: true
```

### Comprehensive Health Check

```bash
BASE="https://run-density-ln4r3sfkha-uc.a.run.app"

# Health
curl -fsS "$BASE/health" && echo "✅ Health OK"

# Ready
curl -fsS "$BASE/ready" && echo "✅ Ready OK"

# Version check
curl -s "$BASE/health" | jq -r '.version'
# Should match latest git tag
```

### Service Status

```bash
# Cloud Run service status
gcloud run services describe run-density \
  --region us-central1 \
  --format="table(status.url,status.conditions)"

# Recent logs
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="run-density"' \
  --limit 50 \
  --format='table(timestamp,severity,textPayload)'
```

### Performance Metrics

```bash
# Check latency
curl -w "\nTime: %{time_total}s\n" -o /dev/null -s \
  https://run-density-ln4r3sfkha-uc.a.run.app/health

# Expected: <1s for health endpoint
# Expected: <30s for density report
# Expected: <60s for flow report
```

---

## Troubleshooting

### Common Deployment Issues

#### 1. Build Failures

**Symptom**: Stage 1 fails with "Build & Deploy" error

**Common Causes:**
- Missing dependencies in `requirements.txt`
- Docker image build errors
- Missing directories in Dockerfile COPY (e.g., /config)

**Fix:**
```bash
# Check Dockerfile COPY statements
grep "COPY" Dockerfile

# Ensure all required directories are copied:
# - app/
# - data/
# - config/  ← Don't forget!
# - frontend/
# - tests/
```

#### 2. E2E Test Failures

**Symptom**: Stage 2/3 fails with test errors

**Common Causes:**
- API endpoint returning 500 errors
- Missing configuration files in deployment
- Schema changes not reflected in validation scripts

**Diagnosis:**
```bash
# Check E2E logs
gh run view <run-id> --log 2>&1 | grep -A 5 "FAIL"

# Test locally first
source test_env/bin/activate
python e2e.py --local
```

**Common Fixes:**
- Update `scripts/validation/verify_bins.py` for schema changes
- Ensure config files copied to Docker image
- Verify constants.py values are correct

#### 3. Cloud Run Timeouts

**Symptom**: 504 Gateway Timeout or "WORKER TIMEOUT"

**Causes:**
- Heavy computation exceeding 600s timeout
- Inefficient algorithms (nested loops)
- Missing vectorization

**Solutions:**
1. Check gunicorn timeout in Dockerfile (should be 600s)
2. Implement coarsening for large datasets
3. Vectorize nested loops (use pandas/numpy)
4. Add performance budgets

#### 4. Version Mismatch

**Symptom**: Pipeline fails on version consistency check

**Fix:**
```bash
# Check versions
python3 -m app.version current  # Code version
git describe --tags --abbrev=0  # Latest tag

# If mismatch, bump version
python3 -m app.version bump patch
git push origin main
git push origin <new-tag>
```

### Rollback Procedure

If deployment fails and needs rollback:

```bash
# 1. Revert commit on main
git revert <bad-commit-sha>
git push origin main

# 2. Monitor new deployment
gh run list --limit 1

# 3. Verify rollback successful
TEST_CLOUD_RUN=true python e2e.py --cloud

# 4. Fix issue in new feature branch
git checkout -b fix/issue-description
# ... make fixes
# ... test thoroughly
# ... create new PR
```

---

## Production URLs and Endpoints

### Cloud Run Service
- **Base URL**: https://run-density-ln4r3sfkha-uc.a.run.app
- **Region**: us-central1
- **Resources**: 1GB RAM / 1 CPU
- **Timeout**: 600 seconds

### API Endpoints

```bash
BASE="https://run-density-ln4r3sfkha-uc.a.run.app"

# Health & Status
GET  $BASE/health
GET  $BASE/ready

# Analysis APIs
POST $BASE/api/density-report
POST $BASE/api/temporal-flow-report

# Data APIs
GET  $BASE/api/segments
GET  $BASE/api/tooltips
GET  $BASE/api/summary

# Frontend
GET  $BASE/frontend/
GET  $BASE/frontend/map.html
GET  $BASE/frontend/reports.html
```

### Testing Endpoints

**NEVER manually construct curl commands!** Always use:
```bash
source test_env/bin/activate
TEST_CLOUD_RUN=true python e2e.py --cloud
```

---

## Release Checklist

### Pre-Release
- [ ] All E2E tests passing (local)
- [ ] Feature branch merged to main via PR
- [ ] No hardcoded values in code
- [ ] Documentation updated
- [ ] Version bumped (if needed)

### During Release
- [ ] CI/CD pipeline completes successfully
- [ ] E2E tests pass on Cloud Run
- [ ] Health endpoints responding
- [ ] Report generation working

### Post-Release
- [ ] Verify production health
- [ ] Test key user workflows
- [ ] Monitor error logs for 30 minutes
- [ ] Update release notes if needed
- [ ] Close related GitHub issues

### Mandatory Release Assets

Attach to every release:
- **Flow.md** - Latest flow analysis report
- **Flow.csv** - Latest flow data
- **Density.md** - Latest density report

```bash
gh release upload v1.6.43 \
  reports/2025-10-16/*-Flow.md \
  reports/2025-10-16/*-Flow.csv \
  reports/2025-10-16/*-Density.md
```

---

## Monitoring Best Practices

### Daily Operations
1. **Check service health** at start of day
2. **Monitor error logs** for anomalies
3. **Verify latest deployment** succeeded
4. **Review recent issues** for patterns

### After Each Deployment
1. **Monitor CI/CD pipeline** to completion
2. **Run E2E tests** against Cloud Run
3. **Verify health endpoints** responding
4. **Check error logs** for new issues
5. **Test key workflows** (density report, flow report)

### Performance Tracking
- **Build time**: Should be <2 minutes
- **E2E time**: Should be <4 minutes total
- **Health response**: Should be <1 second
- **Density report**: Should be <30 seconds (local), <60s (Cloud Run)
- **Flow report**: Should be <60 seconds (local), <120s (Cloud Run)

**If times increase**, investigate for performance regressions.

---

## Emergency Procedures

### Service Down

1. **Verify outage**: `curl https://run-density-ln4r3sfkha-uc.a.run.app/health`
2. **Check logs**: `gcloud logging read --limit 100`
3. **Check recent deployments**: `gh run list --limit 5`
4. **Rollback if needed**: Revert last commit and redeploy
5. **Monitor recovery**: Run E2E tests

### Data Corruption

1. **Verify with known-good inputs**: Test with data/runners.csv, data/segments.csv
2. **Check cache**: Clear `/cache` if stale
3. **Regenerate reports**: Force fresh analysis
4. **Compare with baseline**: Use `tests/qa_regression_baseline.py`

### Performance Degradation

1. **Check resource usage**: Cloud Run metrics
2. **Profile code**: Add timing instrumentation
3. **Review recent changes**: Git blame on slow modules
4. **Optimize if needed**: Vectorize, add coarsening, cache results

---

## Maintenance & Cleanup

### Cloud Run Revision Management

Cloud Run revisions accumulate indefinitely by default. Regular cleanup prevents clutter and improves console performance.

**Tool**: `scripts/cleanup_cloud_run_revisions.sh`

#### Usage

```bash
# Manual execution
./scripts/cleanup_cloud_run_revisions.sh

# Add to scheduled maintenance (monthly)
```

#### Configuration

- **Service**: `run-density`
- **Region**: `us-central1`
- **Keep Count**: 5 revisions (1 active + 4 rollback options)

#### What It Does

1. Lists all revisions for the service
2. Keeps the last 5 revisions (configurable)
3. Deletes all older revisions
4. Shows progress with counts
5. Confirms final state

#### Safety Features

- Preview of what will be deleted
- Progress tracking
- Lists kept revisions at end
- No impact on active deployment

#### When to Run

- **Monthly**: As part of regular maintenance
- **After major releases**: Clean up test/rollback revisions
- **When console is slow**: Too many revisions can impact performance

### Reports Retention Policy

**Established Practice**:
- **Keep**: Current month + previous month
- **Delete**: Reports older than 2 months
- **Archive**: Important reports before deletion (if needed)

**Frequency**: Monthly cleanup recommended

**Rationale**: Reports can be regenerated from source data if needed. Keeping 2 months provides adequate history while managing disk usage.

### Repository Maintenance Schedule

#### Monthly Tasks
1. ✅ **Delete old reports** (older than 2 months)
2. ✅ **Clean Cloud Run revisions** (keep last 5-10)
3. ✅ **Review branch list** (delete merged branches)
4. ✅ **Check disk usage** (artifacts, cache, logs)

#### Quarterly Tasks
1. ✅ **Review archive directories** (consolidate if needed)
2. ✅ **Update dependencies** (requirements.txt)
3. ✅ **Review .gitignore** (add new patterns)
4. ✅ **Audit permissions** (Cloud Run, GCS)

#### Annual Tasks
1. ✅ **Archive old releases** (keep last 12 months)
2. ✅ **Review documentation** (update outdated info)
3. ✅ **Clean test artifacts** (old test data)
4. ✅ **Optimize storage** (GCS lifecycle policies)

### Storage Management

**Disk Usage Patterns**:
- **`/reports`**: Can grow large with daily reports
- **`/cache`**: Gitignored, safe to clear
- **`/artifacts`**: Monthly JSON/GeoJSON artifacts
- **`/archive`**: Historical files, review annually

**Best Practices**:
- Keep reports for current + previous month only
- Clean Cloud Run revisions monthly
- Archive before deleting important files
- Use GCS lifecycle policies for Cloud Storage

---

## Related Documentation

- `@GUARDRAILS.md` - Development rules and workflows
- `@ARCHITECTURE.md` - System design and modules
- `DEPLOYMENT_MONITORING_QUICK_REFERENCE.md` - Quick commands (deprecated, merged here)
- `VERSION_MANAGEMENT.md` - Detailed version module docs (deprecated, merged here)

---

**Remember**: Production is auto-deployed on every main push. Always test thoroughly before merging!

