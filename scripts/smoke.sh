#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8080}"

echo "Health:"
curl -s "$BASE/health" | jq .
echo "Ready:"
curl -s "$BASE/ready" | jq .

echo "Density:"
curl -s -X POST "$BASE/api/density" -H "Content-Type: application/json" -d '{
  "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
  "startTimes":{"10K":440,"Half":460},
  "segments":[
    "10K,Half,0.00,2.74,3.0,uni",
    "10K,,2.74,5.80,1.5,bi",
    {"eventA":"10K","eventB":"Half","from":5.81,"to":8.10,"width":3.0,"direction":"uni"}
  ],
  "stepKm":0.03,
  "timeWindow":60
}' | jq '.engine, .segments[0].peak'

echo "Overlap:"
curl -s -X POST "$BASE/api/overlap" -H "Content-Type: application/json" -d '{
  "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
  "startTimes":{"10K":440,"Half":460},
  "eventA":"10K","eventB":"Half",
  "from":0.00,"to":2.74,
  "stepKm":0.03,"timeWindow":60
}' | jq '.engine, .peak'
