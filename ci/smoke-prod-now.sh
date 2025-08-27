#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-$(gcloud run services describe run-density --region us-central1 --format='value(status.url)')}"
echo ">> $BASE"
curl -fsS "$BASE/health" | jq -e '.ok==true' >/dev/null && echo "health OK"
curl -fsS "$BASE/ready"  | jq -e '.ok==true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready  OK"
curl -fsS -X POST "$BASE/api/density" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
       "overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv",
       "startTimes":{"Full":420,"10K":440,"Half":460},
       "stepKm":0.03,"timeWindow":60}' \
 | jq -e '.engine=="density" and (.segments|length)>0' >/dev/null && echo "density OK"
echo "✅ smoke-prod-now passed"
