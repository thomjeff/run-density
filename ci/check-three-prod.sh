# ci/check-three-prod.sh
#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  echo "Usage: $0 https://<your-cloud-run-url>" >&2
  exit 1
fi

echo ">> Hitting $BASE"
curl -fsS "$BASE/health" | jq -e '.ok==true' >/dev/null && echo "health OK"
curl -fsS "$BASE/ready"  | jq -e '.ok==true and .density_loaded and .overlap_loaded' >/dev/null && echo "ready  OK"

check_seg () {
  local SEG="$1"
  echo
  echo "== seg_id: ${SEG} =="
  curl -fsS -X POST "$BASE/api/density?debug=true&seg_id=${SEG}" \
    -H 'Content-Type: application/json' \
    -d '{
          "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
          "overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv",
          "startTimes":{"Full":420,"10K":440,"Half":460},
          "stepKm":0.03,"timeWindow":60
        }' \
    | jq '{
        seg: .segments[0].seg_id,
        dir: .segments[0].direction,
        width: .segments[0].width_m,
        first_overlap: .segments[0].first_overlap,
        peak: .segments[0].peak,
        trace_head: (.segments[0].trace[:6])
      }'
}

check_seg "A1"
check_seg "B2"
check_seg "H3"

echo
echo "✅ Done"