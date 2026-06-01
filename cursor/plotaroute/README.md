# PlotARoute segment library (reference)

GPX **routes** in this folder are reusable course **segments**. Event courses are built by **combining** routes in order (PlotARoute “Combine Route”), or—in the app—by assigning **order numbers** per event in a table.

## Files

| Prefix | Meaning |
|--------|---------|
| `01`–`15` | Individual segments |
| `00_full_new.gpx` | Combined **Full** (authoritative check for full recipe) |
| `00_half.gpx`, `00_10k.gpx` | Combined Half / 10K |

## Full marathon (corrected Marysville legs)

**Do not** combine route `10` (out-and-back) before route `13` — the return strand leaves the course disconnected.

**Use:**

`01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 14 → 13 → 15 → 11`

Matches `00_full_new.gpx` (~41.9 km).

| Id | File | ~km | Full order |
|----|------|-----|------------|
| 01 | `01_start_friel.gpx` | 2.71 | 1 |
| 02 | `02_friel_10kturn.gpx` | 1.59 | 2 |
| 03 | `03_10kturn_fullturn.gpx` | 11.14 | 3 |
| 04 | `04_10kturn_friel.gpx` | 1.59 | 4 |
| 05 | `05_friel_station.gpx` | 2.24 | 5 |
| 06 | `06_station_gibsontrail.gpx` | 0.11 | 6 |
| 07 | `07_station_qsloop.gpx` | 4.69 | 7 |
| 08 | `08_gibsontrail_bridgemill.gpx` | 5.77 | 8 |
| 14 | `14_bridgemill_to_halfturn.gpx` | 2.57 | 9 |
| 13 | `13_halfturn_to_fullturn.gpx` | 1.58 | 10 |
| 15 | `15_halfturn_to_bridgemill.gpx` | 2.58 | 11 |
| 11 | `11_bridgemill_finish.gpx` | 5.22 | 12 |

## Half marathon

`00_half.gpx` in this folder still uses legacy route **10** (out-and-back). For runflow, use this recipe instead (~**21.20 km**, matches distance target; all stitches &lt; 15 m):

`01 → 05 → 06 → 08 → 14 → 15 → 11`

| Id | File | ~km | half order |
|----|------|-----|------------|
| 01 | `01_start_friel.gpx` | 2.71 | 1 |
| 05 | `05_friel_station.gpx` | 2.24 | 2 |
| 06 | `06_station_gibsontrail.gpx` | 0.11 | 3 |
| 08 | `08_gibsontrail_bridgemill.gpx` | 5.77 | 4 |
| 14 | `14_bridgemill_to_halfturn.gpx` | 2.57 | 5 |
| 15 | `15_halfturn_to_bridgemill.gpx` | 2.58 | 6 |
| 11 | `11_bridgemill_finish.gpx` | 5.22 | 7 |

No route **10**, **12**, or **13** on Half.

## 10K

Unchanged (~**10.00 km** vs `00_10k.gpx` 10.02 km):

`01 → 02 → 04 → 05 → 12`

| Id | File | ~km | 10k order |
|----|------|-----|-----------|
| 01 | `01_start_friel.gpx` | 2.71 | 1 |
| 02 | `02_friel_10kturn.gpx` | 1.59 | 2 |
| 04 | `04_10kturn_friel.gpx` | 1.59 | 3 |
| 05 | `05_friel_station.gpx` | 2.24 | 4 |
| 12 | `12_station_finish.gpx` | 1.87 | 5 |

## Stitch gaps

Small endpoint gaps (&lt;10 m) are normal. ~105 m between `06` and `07` exists in PlotARoute too—fix in PlotARoute or add a connector segment later if needed.

## App direction

Organizers will **not** edit this YAML. Phase 1 UI: import GPX → recipe table (order per event) → **Save** → `segments.csv`.
