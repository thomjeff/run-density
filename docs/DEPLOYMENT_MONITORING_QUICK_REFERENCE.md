# Deployment Monitoring - Quick Reference Card

**Use this for rapid deployment health checks after every merge to main.**

---

## **🚀 Quick Commands**

```bash
# 1. Check workflow status
gh run list --limit 3

# 2. Monitor active workflow  
gh run view <workflow-id>

# 3. Check E2E test results
gh run view --log --job=<e2e-job-id> | tail -10

# 4. Verify new Cloud Run revision
gcloud run revisions list --service=run-density --region=us-central1 --limit=2

# 5. Check traffic routing (CRITICAL)
gcloud run services describe run-density --region=us-central1 \
  --format="table(status.traffic[].revisionName,status.traffic[].percent)"

# 6. Check for errors in logs
gcloud run services logs read run-density --region=us-central1 \
  --log-filter="severity>=WARNING" --freshness=10m
```

---

## **⏱️ Expected Timings**

| Stage | Duration |
|-------|----------|
| Build & Deploy | ~1m18s |
| E2E Validation | ~3m16s |
| Automated Release | ~21s |
| **Total** | **~5m** |

---

## **✅ Success Indicators**

- **Workflow**: `completed success`
- **E2E Logs**: `🎉 ALL TESTS PASSED!`
- **Revision**: `Deploying revision succeeded`
- **Traffic**: `100%` on new revision
- **Logs**: No ERROR level messages

---

## **🚨 Red Flags**

- E2E tests fail or timeout (>6 minutes)
- ERROR level logs in application
- Traffic not 100% on new revision
- Build/deploy job failures

---

**For detailed instructions, see**: `docs/DEPLOYMENT_MONITORING_GUIDE.md`
