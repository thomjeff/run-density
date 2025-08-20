#!/usr/bin/env bash
set -euo pipefail

BASE_URL=$1
echo ">> Hitting $BASE_URL"

logfile=smoke-report.log
exec > >(tee $logfile) 2>&1

check() {
  path=$1
  echo -n "Checking $path ... "
  curl -sf "$BASE_URL$path" > /dev/null
  echo "OK"
}

check /health
check /ready

echo "Posting to /api/report ..."
resp=$(curl -s -X POST "$BASE_URL/api/report"   -H "Content-Type: application/json"   -d '{
    "eventA":"10K","eventB":"Half",
    "from":0.00,"to":2.74,
    "segment_name":"A",
    "segment_label":"Start to Friel",
    "direction":"uni","width_m":3.0,
    "startTimes":{"10K":1200,"Half":2400},
    "startTimesClock":{"10K":"07:20:00","Half":"07:40:00"},
    "runnersA":618,"runnersB":368,
    "overlap_from_km":2.55,"overlap_to_km":2.74,
    "first_overlap_clock":"07:48:15",
    "first_overlap_km":2.55,
    "first_overlap_bibA":"1617","first_overlap_bibB":"1681",
    "peak":{"km":1.80,"A":260,"B":140,"combined":400,"areal_density":2.20}
  }')

report=$(echo "$resp" | jq -r .report)
echo "Report:"
echo "$report"

if [[ -z "$report" ]]; then
  echo "ERROR: report was empty"
  exit 1
fi

# minimal contract check
if ! echo "$report" | grep -q "Checking 10K vs Half"; then
  echo "ERROR: Expected header missing"
  exit 1
fi

echo "Smoke report successful"
