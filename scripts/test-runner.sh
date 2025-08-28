#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8081}"
PACE="${PACE:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv}"
OVLS="${OVLS:-https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv}"

body_base() {
  cat <<JSON
{
  "paceCsv":"$PACE",
  "overlapsCsv":"$OVLS",
  "startTimes":{"Full":420,"10K":440,"Half":460},
  "stepKm":0.03,
  "timeWindow":60,
  "depth_m":3.0
}
JSON
}

case "${1:-help}" in
  all)
    echo ">> density (summary)"; curl -s -X POST "$BASE/api/density" -H 'Content-Type: application/json' -d "$(body_base)" \
      | jq '{engine, count: (.segments|length)}'
    echo ">> non-green zones (areal + crowd)"; curl -s -X POST "$BASE/api/density" -H 'Content-Type: application/json' -d "$(body_base)" \
      | jq -r '.segments | map(select(.peak.zone!="green")) | .[] |
               "\(.seg_id)\tareal=\(.peak.areal_density)\tcrowd=\(.peak.crowd_density)\tzone=\(.peak.zone)"'
    ;;
  seg)
    SEG_ID="${2:?usage: $0 seg A1a}"
    echo ">> density seg_id=$SEG_ID"; curl -s -X POST "$BASE/api/density?seg_id=$SEG_ID" -H 'Content-Type: application/json' -d "$(body_base)" \
      | jq '{seg: .segments[0].seg_id, first: .segments[0].first_overlap, peak: .segments[0].peak}'
    ;;
  peaks)
    echo ">> peaks.csv (top 10)"; curl -s -X POST "$BASE/api/peaks.csv" -H 'Content-Type: application/json' -d "$(body_base)" | head -n 10
    ;;
  segments)
    echo ">> segments.csv (top 10)"; curl -s -X POST "$BASE/api/segments.csv" -H 'Content-Type: application/json' -d "$(body_base)" | head -n 10
    ;;
  custom-zones)
    echo ">> density with custom areal cuts"; curl -s -X POST "$BASE/api/density" -H 'Content-Type: application/json' \
      -d "$(jq -n --argjson base "$(body_base)" '
            ($base + {zones:{areal:[5,10,20,40]}})
          ')" \
      | jq -r '.segments | map(select(.peak.zone!="green")) | .[:5][] |
               "\(.seg_id)\t\(.peak.areal_density)\t\(.peak.zone)"'
    ;;
  *)
    echo "Usage: $0 {all|seg SEG_ID|peaks|segments|custom-zones}"
    exit 1
    ;;
esac