#!/usr/bin/env bash
# Robust smoke test for run-density (local or GCP)
# Usage:
#   ./ci/smoke-report.sh https://run-density-xxxxxx-uc.a.run.app
#   # or
#   BASE_URL=https://run-density-xxxxxx-uc.a.run.app ./ci/smoke-report.sh
#
# Exits non-zero if any check fails.

set -euo pipefail

BASE="${1:-${BASE_URL:-}}"
if [[ -z "${BASE}" ]]; then
  echo "ERROR: BASE_URL is empty."
  echo "Usage: ./ci/smoke-report.sh <BASE_URL>    or    BASE_URL=<url> ./ci/smoke-report.sh"
  exit 2
fi

echo ">> Hitting ${BASE}"

have_jq=1
command -v jq >/dev/null 2>&1 || have_jq=0

check_json () {
  local path="$1"
  local expect="$2"
  local out
  out="$(curl -fsS "${BASE}${path}")" || { echo "FAIL ${path} (HTTP)"; exit 1; }
  if [[ ${have_jq} -eq 1 ]]; then
    echo "${out}" | jq . >/dev/null 2>&1 || { echo "FAIL ${path} (invalid JSON)"; echo "${out}"; exit 1; }
    if [[ -n "${expect}" ]]; then
      echo "${out}" | jq -e "${expect}" >/dev/null 2>&1 || { echo "FAIL ${path} (expect ${expect})"; echo "${out}" | jq .; exit 1; }
    fi
  else
    # Fallback: shallow checks
    [[ "${out}" == *'"ok": true'* ]] || { echo "WARN: jq not found; basic check failed for ${path}"; echo "${out}"; exit 1; }
  fi
  echo "OK ${path}"
}

# 1) Health & Ready
check_json "/health" ".ok == true"
check_json "/ready"  ".ok == true and .density_loaded and .overlap_loaded"

# 2) Tiny density POST (shape only)
payload='{
  "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
  "startTimes":{"10K":440,"Half":460},
  "segments":[{"eventA":"10K","eventB":"Half","from":0.00,"to":2.74,"width":3.0,"direction":"uni"}],
  "stepKm":0.03,
  "timeWindow":60
}'

resp="$(curl -fsS -X POST "${BASE}/api/density" -H "Content-Type: application/json" -d "${payload}")" || { echo "FAIL /api/density (HTTP)"; exit 1; }
if [[ ${have_jq} -eq 1 ]]; then
  echo "${resp}" | jq -e '.engine == "density" and (.segments | length) >= 1' >/dev/null 2>&1 || { echo "FAIL /api/density (contract)"; echo "${resp}" | jq .; exit 1; }
else
  [[ "${resp}" == *'"engine":"density"'* ]] || { echo "FAIL /api/density (engine)"; echo "${resp}"; exit 1; }
fi
echo "OK /api/density"

echo "✅ Smoke passed for ${BASE}"
