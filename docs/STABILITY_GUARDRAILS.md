# Stability Guardrails (v1.0.0)

This repo treats the API surface as **stable**. Breaking changes require a **major** bump per SemVer.

## Guardrails
1. **Schema freeze**
   - `openapi.yaml` defines the contract.
   - `schemas/*.schema.json` are used for automated validation.

2. **Version headers**
   - Every response should include `X-API-Version: 1.0.0` and `X-Compute-Seconds`.

3. **Contract tests**
   - `pytest -q tests/test_contract.py` validates prod (or canary) endpoints.
   - Set `BASE_URL` to target a specific environment.

4. **CI/CD canary**
   - GitHub Actions builds a no-traffic revision and smoke-tests the tag URL.
   - Promotion to 100% is a separate step (uncomment when ready).

5. **Observability**
   - Tail logs during deploys: `gcloud beta run services logs tail run-density --region us-central1`.

6. **Rollback**
   - Keep the previous good revision handy; switch traffic instantly if needed.

7. **Performance budgets**
   - Watch `X-Compute-Seconds`. If p95 grows > 2x week-over-week, investigate.

8. **Deprecation policy**
   - For any breaking change, expose `/v2` paths in parallel; deprecate `/v1` with a 60–90 day window.

## Local quickstart
```
uvicorn app.main:app --reload --port 8080
BASE_URL=http://localhost:8080 ./scripts/smoke.sh
```
