#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./ci/test_runner.sh https://YOUR-CLOUD-RUN-URL
# or
#   BASE=https://YOUR-CLOUD-RUN-URL ./ci/test_runner.sh
#
# Produces human‑readable reports via /api/report, and validates /health and /ready.

BASE="${1:-${BASE:-}}"
if [ -z "${BASE}" ]; then
  echo "ERROR: Provide Cloud Run base URL as arg or BASE env var" >&2
  exit 1
fi

echo ">> Hitting ${BASE}"
curl -fsS "${BASE}/health" | jq -e '.ok == true' >/dev/null && echo "OK /health"
curl -fsS "${BASE}/ready"  | jq -e '.ok == true and .density_loaded and .overlap_loaded' >/dev/null && echo "OK /ready"

run_case () {
  local file="$1"
  echo ""
  echo "== Case: ${file} =="
  # Route selection: if payload has `report:true` (default), hit /api/report, else /api/density
  local dest
  if jq -e '.report // true' "${file}" >/dev/null 2>&1; then
    dest="report"
  else
    dest="density"
  fi
  if [ "${dest}" = "report" ]; then
    curl -fsS -X POST "${BASE}/api/report"       -H "Content-Type: application/json"       --data-binary "@${file}"       | jq -r '.report'
  else
    curl -fsS -X POST "${BASE}/api/density"       -H "Content-Type: application/json"       --data-binary "@${file}"       | jq .
  fi
}

# Run the baked cases
run_case "ci/cases/A.json"

# Template hint
echo ""
echo ">> To add more cases, copy ci/cases/TEMPLATE.json to ci/cases/B.json (etc.) and edit."
