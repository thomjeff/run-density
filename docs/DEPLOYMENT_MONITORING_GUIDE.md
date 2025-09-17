# Deployment Monitoring Guide

**Purpose**: Comprehensive guide for monitoring GitHub Workflows and Cloud Run deployments to ensure clean, error-free deployments.

**Critical**: This process must be followed after every merge to main to verify deployment health before proceeding with additional development work.

---

## **🚀 Overview**

Every merge to main triggers the automated CI/CD pipeline with three stages:
1. **Build & Deploy** - Docker build and Cloud Run deployment
2. **E2E Validation** - End-to-end testing against deployed service  
3. **Automated Release** - GitHub release creation with assets

**Total Expected Time**: ~5-6 minutes for complete pipeline

---

## **📋 Step-by-Step Monitoring Process**

### **Step 1: Monitor Initial Workflow Status**

```bash
# Check recent workflow runs
gh run list --limit 3
```

**Expected Output**: Look for `in_progress` status on the latest workflow.

**Timing**: Start monitoring immediately after merge.

### **Step 2: Monitor Workflow Progress**

```bash
# Check detailed workflow status
gh run view <workflow-id>
```

**Expected Stages & Timings**:
- ✅ **Build & Deploy**: ~1-2 minutes
- 🔄 **E2E Validation**: ~3-4 minutes  
- ⏳ **Automated Release**: ~20-30 seconds

**Example Output**:
```
* main CI Pipeline · 17798631630
Triggered via push about 2 minutes ago

JOBS
✓ 1️⃣ Build & Deploy (Docker → Artifacts) in 1m18s (ID 50592220547)
* 2️⃣ E2E Validation (ID 50592351507)
```

### **Step 3: Monitor E2E Test Execution**

While E2E tests are running (longest stage), check progress:

```bash
# Monitor specific E2E job
gh run view --job=<e2e-job-id>
```

**Expected Steps**:
- ✓ Set up job
- ✓ Checkout code  
- ✓ Setup Python
- ✓ Install dependencies
- * Run E2E Tests ← **This takes the longest (3-4 minutes)**

### **Step 4: Verify E2E Test Success**

```bash
# Check E2E test completion logs
gh run view --log --job=<e2e-job-id> | tail -20
```

**Success Indicators**:
```
🎉 ALL TESTS PASSED!
✅ Cloud Run is working correctly
```

### **Step 5: Verify Complete Workflow Success**

```bash
# Final workflow status check
gh run list --limit 3
```

**Expected Output**:
```
completed	success	Merge pull request #XXX	CI Pipeline	main	push
```

**Final Job Status**:
```bash
gh run view <workflow-id>
```

**Expected Output**:
```
✓ main CI Pipeline · <workflow-id>

JOBS
✓ 1️⃣ Build & Deploy (Docker → Artifacts) in 1m18s
✓ 2️⃣ E2E Validation in 3m16s
✓ 3️⃣ Automated Release in 21s
```

---

## **☁️ Cloud Run Deployment Verification**

### **Step 6: Verify New Revision Deployment**

```bash
# Check latest Cloud Run revisions
gcloud run revisions list --service=run-density --region=us-central1 --limit=2 \
  --format="table(metadata.name,status.conditions[0].status,metadata.creationTimestamp)"
```

**Expected Output**:
```
NAME                   STATUS  CREATION_TIMESTAMP
run-density-00369-mxm  True    2025-09-17T13:08:27.370912Z  ← New revision
run-density-00368-76k  True    2025-09-17T01:29:20.086832Z  ← Previous revision
```

### **Step 7: Verify Deployment Success**

```bash
# Check revision deployment status
gcloud run revisions describe <latest-revision-name> --region=us-central1 \
  --format="value(status.conditions[0].message)"
```

**Expected Output**:
```
Deploying revision succeeded in 11.73s.
```

### **Step 8: Verify Traffic Routing**

**CRITICAL**: Ensure 100% traffic is routed to the new revision.

```bash
# Check traffic allocation
gcloud run services describe run-density --region=us-central1 \
  --format="table(status.traffic[].revisionName,status.traffic[].percent)"
```

**Expected Output**:
```
REVISIONNAME           PERCENT
run-density-00369-mxm  100      ← All traffic on new revision
```

**⚠️ Warning**: If traffic is not 100% on the new revision, the deployment may not be fully active.

---

## **📊 Log Analysis for Error Detection**

### **Step 9: Check Application Logs**

```bash
# Check recent application logs
gcloud run services logs read run-density --region=us-central1 --limit=30 \
  --format="table(timestamp,severity,textPayload)" --freshness=10m
```

**Healthy Indicators**:
- Application startup messages
- Successful report generation
- API endpoint responses (200 status codes)
- No ERROR level messages

### **Step 10: Check for Warnings and Errors**

```bash
# Check for WARNING and ERROR level logs
gcloud run services logs read run-density --region=us-central1 --limit=50 \
  --log-filter="severity>=WARNING" --freshness=10m
```

**Acceptable Warnings**:
- `GET 404` for favicon.ico (cosmetic only)
- `GET 404` for apple-touch-icon files (cosmetic only)

**Unacceptable Errors**:
- Application crashes
- Module import errors
- Database connection failures
- API endpoint failures (5xx status codes)

### **Step 11: Check Build/Deploy Logs**

```bash
# Check build job for errors
gh run view --log --job=<build-job-id> | grep -E "(ERROR|WARNING|FAILED)" | head -10
```

**Acceptable Warnings**:
- `pip as 'root' user` warning (standard Docker build warning)

**Unacceptable Errors**:
- Docker build failures
- Dependency installation failures
- Cloud Run deployment failures

---

## **⏱️ Expected Timing Benchmarks**

Based on successful deployment monitoring:

| Stage | Expected Duration | Acceptable Range |
|-------|------------------|------------------|
| **Build & Deploy** | 1m18s | 1-2 minutes |
| **E2E Validation** | 3m16s | 3-4 minutes |
| **Automated Release** | 21s | 20-30 seconds |
| **Total Pipeline** | 5m6s | 5-6 minutes |

**⚠️ Escalation Triggers**:
- Any stage taking >2x expected duration
- Any ERROR level logs in application
- E2E tests failing
- Traffic not routing to new revision

---

## **✅ Success Criteria Checklist**

Before proceeding with additional development, verify:

- [ ] **Workflow Status**: `completed success` 
- [ ] **All Jobs Passed**: Build & Deploy ✓, E2E Validation ✓, Automated Release ✓
- [ ] **New Revision Created**: Latest revision shows `True` status
- [ ] **Traffic Routing**: 100% traffic on new revision
- [ ] **Application Logs**: No ERROR level messages
- [ ] **E2E Test Results**: `🎉 ALL TESTS PASSED!`
- [ ] **Deployment Message**: `Deploying revision succeeded`

---

## **🚨 Troubleshooting Common Issues**

### **E2E Tests Taking Too Long**
- **Normal**: E2E tests can take 3-4 minutes due to computational requirements
- **Action**: Wait patiently, check logs for progress indicators
- **Escalate**: If >6 minutes, check for resource constraints

### **Traffic Not Routing to New Revision**
- **Check**: Verify automated traffic redirection in workflow logs
- **Manual Fix**: Use `gcloud run services update-traffic` command
- **Root Cause**: Usually indicates deployment pipeline issue

### **404 Errors in Logs**
- **favicon.ico 404s**: Cosmetic only, not functional issue
- **API endpoint 404s**: Functional issue, requires investigation
- **Static file 404s**: May indicate frontend deployment issue

### **Build Warnings**
- **pip root user warning**: Safe to ignore, standard Docker behavior
- **Dependency warnings**: Review but usually not critical
- **Security warnings**: Must be addressed immediately

---

## **📝 Documentation Requirements**

After each monitored deployment, document:

1. **Workflow ID** and timing results
2. **New revision name** and deployment time  
3. **Any warnings or errors** encountered
4. **Traffic routing verification** results
5. **Overall deployment health** assessment

**Example Documentation**:
```
Deployment: 2025-09-17 13:07:21Z
Workflow: 17798631630 - SUCCESS (5m6s)
Revision: run-density-00369-mxm - HEALTHY
Traffic: 100% routed to new revision
Status: ✅ CLEAN DEPLOYMENT
```

---

## **🔄 Integration with Development Workflow**

This monitoring process integrates with the Pre-task safeguards:

1. **After PR Merge**: Immediately start monitoring
2. **During Monitoring**: Do not start new development work
3. **After Success**: Proceed with next development task
4. **After Failure**: Investigate and resolve before continuing

**Remember**: A clean deployment is essential for maintaining system stability and avoiding cascading issues in subsequent development work.

---

**Last Updated**: 2025-09-17  
**Next Review**: When deployment pipeline changes  
**Maintainer**: Development Team
