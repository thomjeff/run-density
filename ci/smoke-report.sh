#!/usr/bin/env bash
set -euo pipefail

: "${BASE_URL:?BASE_URL must be set}"

echo ">> Hitting ${BASE_URL}"

curl -fsS "${BASE_URL}/health" | jq -e '.ok == true' >/dev/null
echo "health OK"

curl -fsS "${BASE_URL}/ready"  | jq -e '.ok == true and .density_loaded and .overlap_loaded' >/dev/null
echo "ready OK"

# Sample /api/report payload — mirrors your agreed format
read -r -d '' PAYLOAD << 'JSON'
{
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
}
JSON

REPORT=$(curl -fsS -X POST "${BASE_URL}/api/report"       -H "Content-Type: application/json"       -d "${PAYLOAD}" | jq -r '.report')

# Basic assertions on the string report
echo "${REPORT}" | grep -q "Checking 10K vs Half from 0.00km–2.74km" || { echo "report header missing"; exit 1; }
echo "${REPORT}" | grep -q "Start: 10K 07:20:00, Half 07:40:00"      || { echo "start times missing"; exit 1; }
echo "${REPORT}" | grep -q "Runners: 10K: 618, Half: 368"            || { echo "runners line missing"; exit 1; }
echo "${REPORT}" | grep -q "Overlap Segment: 2.55km–2.74km"          || { echo "overlap segment line missing"; exit 1; }
echo "${REPORT}" | grep -q "First overlap: 07:48:15 at 2.55km"       || { echo "first overlap line missing"; exit 1; }
echo "${REPORT}" | grep -q "Peak: 400"                                || { echo "peak line missing"; exit 1; }

echo "report OK"
echo "✅ Smoke-report passed for ${BASE_URL}"