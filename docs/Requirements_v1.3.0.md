# run-density v1.3.0 Requirements

## Overview
Version 1.3.0 builds on v1.2.0 by introducing structured overlap metadata, three-event support, and human-readable reporting. It also aligns all data sources with the **run-density** repository instead of **run-density**.

---

## Pre-conditions
The following are satisfied before v1.3.0 implementation:
1. **Structured overlap CSV** available (`overlaps_v2.csv` → rename to `overlaps.csv`).
2. **Validation script** (`scripts/validate_overlaps.py`) in place.
3. **Data inputs** (`your_pace_data.csv`, `overlaps.csv`) hosted in run-density repo.
4. **Zone thresholds** confirmed:  
   - Green: `< 1.0`  
   - Amber: `1.0 – 1.5`  
   - Red: `1.5 – 2.0`  
   - Dark-Red: `≥ 2.0` runners/m²  

---

## Requirements

### 1. Overlaps CSV
- **File:** `/data/overlaps.csv`
- **Schema (required columns):**
  - `seg_id`
  - `segment_label`
  - `eventA`
  - `eventB`
  - `from_km_A`, `to_km_A`
  - `from_km_B`, `to_km_B`
  - `direction` (`uni`/`bi`)
  - `width_m`
- **Rules:**
  - `overlaps.csv` is the single source of truth for width/direction.
  - Single-event continuity rows retained for validation.

### 2. Three-Event Handling
- Compute density for **pairwise overlaps** (A–B, A–C, B–C).
- Provide optional **stacked density** when all three events share the segment.

### 3. Reporting
- Replace raw metrics with **human-readable report strings**, including:
  - Segment label (e.g., *“Start → Friel”*).
  - Start times for each event (offsets converted to `hh:mm:ss`).
  - Runner totals (`Runners: 10K: …, Half: …`).
  - Overlap segment range.
  - First overlap (time, km, bibs).
  - Peak density (combined, ppl/m², zone color).

### 4. Inputs
- API continues to accept:
  - `paceCsv`: now defaults to  
    `https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv`
  - `overlapsCsv`: defaults to  
    `https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv`
- If both overlapsCsv and inline width/direction passed, **CSV wins**.

### 5. Persistence
- Persist outputs (CSV + PNG charts) to Cloud Storage.
- Naming convention: `DTM_<ts>_<service>_<seg>.csv/png`.

---

## Example curl

```bash
BASE="https://run-density-131075166528.us-central1.run.app"

# Health + Ready
curl -fsS "$BASE/health" | jq .
curl -fsS "$BASE/ready"  | jq .

# Density with overlaps
curl -s -X POST "$BASE/api/density" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
    "overlapsCsv":"https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv",
    "startTimes":{"10K":440,"Half":460,"Full":420},
    "stepKm":0.03,
    "timeWindow":60
  }' | jq .