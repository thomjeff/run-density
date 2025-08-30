#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8081}"

usage() {
  echo "Usage: $0 {all|seg SEG_ID|peaks|segments|custom-zones|menu}"
  exit 1
}

run_all() {
  echo ">> density (summary)"
  curl -s -X POST "$BASE/api/density" -H 'Content-Type: application/json' \
    -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv","overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0}' \
  | jq '{engine, count: (.segments|length)}'

  echo ">> non-green zones (areal + crowd)"
  curl -s -X POST "$BASE/api/density.summary" -H 'Content-Type: application/json' \
    -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv","overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0}' \
  | jq -r '.segments | map(select(.zone!="green")) | .[:9][] | "\(.seg_id)\tareal=\(.areal_density)\tcrowd=\(.crowd_density)\tzone=\(.zone)"'
}

run_seg() {
  local SEG="$1"
  echo ">> seg $SEG (debug)"
  curl -s -X POST "$BASE/api/density?seg_id=$SEG&debug=true" -H 'Content-Type: application/json' \
    -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv","overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0}' \
  | jq '{seg: .segments[0].seg_id, peak: .segments[0].peak, first: .segments[0].first_overlap}'
}

run_peaks() {
  echo ">> peaks.csv (areal default cuts)"
  curl -s -X POST "$BASE/api/peaks.csv" -H 'Content-Type: application/json' \
    -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv","overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0}' \
  | head -n 12

  echo ">> peaks.csv (crowd with custom cuts)"
  curl -s -X POST "$BASE/api/peaks.csv?zoneMetric=crowd" -H 'Content-Type: application/json' \
    -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv","overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0,"zones":{"crowd":[1,2,4,8]}}' \
  | head -n 12
}

run_segments() {
  echo ">> /api/segments.csv"
  curl -s -X POST "$BASE/api/segments.csv" -H 'Content-Type: application/json' \
    -d '{"overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv"}' \
  | head -n 12
}

run_custom_zones() {
  echo ">> density.summary (zoneMetric=crowd, custom cuts)"
  curl -s -X POST "$BASE/api/density.summary?zoneMetric=crowd" -H 'Content-Type: application/json' \
    -d '{"paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv","overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv","startTimes":{"Full":420,"Half":460,"10K":440},"stepKm":0.03,"timeWindow":60,"depth_m":3.0,"zones":{"crowd":[1,2,4,8]}}' \
  | jq -r '.segments | map(select(.zone!="green")) | .[:10][] | "\(.seg_id)\tcrowd=\(.crowd_density)\tzone=\(.zone)"'
}

menu() {
  echo "Select a test:"
  echo "  1) all"
  echo "  2) seg (prompt)"
  echo "  3) peaks"
  echo "  4) segments"
  echo "  5) custom-zones"
  read -rp "> " CH
  case "$CH" in
    1) run_all ;;
    2) read -rp "SEG_ID: " S; run_seg "$S" ;;
    3) run_peaks ;;
    4) run_segments ;;
    5) run_custom_zones ;;
    *) usage ;;
  esac
}

case "${1:-menu}" in
  all) run_all ;;
  seg) [[ $# -ge 2 ]] || usage; run_seg "$2" ;;
  peaks) run_peaks ;;
  segments) run_segments ;;
  custom-zones) run_custom_zones ;;
  menu|"") menu ;;
  *) usage ;;
esac