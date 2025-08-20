# run-congestion — Cloud Run deployment (FastAPI)

This skeleton wraps your existing **density** and **overlap** engines behind a stable FastAPI API and ships to **Google Cloud Run** with one script.

## Structure
```
app/
  main.py         # FastAPI app (health, /api/density, /api/overlap)
  density.py      # REPLACE with your implementation (stub included)
  overlap.py      # REPLACE with your implementation (stub included)
requirements.txt  # pinned deps
Dockerfile        # Cloud Run container
deploy.sh         # Build + Deploy
```

## Deploy
```bash
export PROJECT_ID=your-gcp-project
export REGION=us-central1
export SERVICE=run-congestion

./deploy.sh
```

## Health
```bash
BASE=$(gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')
curl -s $BASE/health | jq
curl -s $BASE/ready | jq
```

## API — Density (same payload style)
```bash
curl -s -X POST "$BASE/api/density" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
    "startTimes":{"10K":440,"Half":460},
    "segments":[
      "10K,Half,0.00,2.74,3.0,uni",
      "10K,,2.74,5.80,1.5,bi",
      {"eventA":"10K","eventB":"Half","from":5.81,"to":8.10,"width":3.0,"direction":"uni"}
    ],
    "stepKm":0.03,
    "timeWindow":60
  }' | jq
```

## API — Overlap
```bash
curl -s -X POST "$BASE/api/overlap" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/your_pace_data.csv",
    "overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-congestion/main/data/overlaps.csv",
    "startTimes":{"10K":440,"Half":460},
    "stepKm":0.03,
    "timeWindow":60,
    "eventA":"10K",
    "eventB":"Half",
    "from":0.00,
    "to":2.74
  }' | jq
```

## Notes
- `X-Compute-Seconds` is emitted on responses.
- If you keep `density.py` and `overlap.py` pure functions, the API layer will stay stable across refactors.
- Scale/cost protections: bump `--max-instances` and `--concurrency` as needed.
