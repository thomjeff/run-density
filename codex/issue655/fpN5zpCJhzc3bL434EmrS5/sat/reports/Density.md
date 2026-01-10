# Fredericton Marathon — Density Report
**Schema:** 1.0.0
**Method:** segments_from_bins
**Date:** 2026-01-10 01:16:08
**Inputs:** bins.parquet, segments.parquet, segment_windows_from_bins.parquet
**App:** vv2.0.5

---

## Executive Summary
- **Peak Density:** 0.6920 p/m² (LOS C)
- **Peak Rate:** 1.75 p/s
- **Segments with Flags:** 18 / 18
- **Flagged Bins:** 210 / 4350
- **Operational Status:** 🔴 Action Required (Critical density/rate conditions detected)

- **Runner Experience Scores (RES):**
  - sat-elite: 5.00
  - sat-open: 5.00

> RES (Runner Experience Score) is a composite score (0.0-5.0) representing overall race experience, combining density and flow metrics. Higher scores indicate better runner experience.
> LOS (Level of Service) describes how comfortable runners are within a section — A means free-flowing, while E/F indicate crowding. Even when overall LOS is good, short-lived surges in runner flow can stress aid stations or intersections, requiring active flow management.

---

## Methodology & Inputs
- **Window Size:** 30 s; **Bin Size:** 0.2 km

### LOS and Rate Triggers (from Rulebook)
- **LOS thresholds** define crowding levels based on density (p/m²) only (rate does not affect LOS):
  - A: < 0.36 | B: 0.36–0.54 | C: 0.54–0.72 | D: 0.72–1.08 | E: 1.08–1.63 | F: > 1.63
- **Rate thresholds** define throughput risk based on flow references (persons/m/min) and influence severity flags:
  - Warning: 27.8 | Critical: 39.6

These thresholds come from the Fredericton Marathon rulebook and align with crowd management standards for mass participation events.

---

## Start Times & Cohorts
- **Elite 5K** — 08:00 (39 runners)
- **Open 5K** — 08:30 (550 runners)

> Bins may include runners from multiple events as waves overlap in time.

---

## Course Overview

| Segment | Label | Schema | Width (m) | Spatial Bins |
|----------|--------|--------|-----------|--------------|
| N1 | Start to Queen/Westmorland | N/A | 5.0 | 3 |
| N2 | Queen/Westmorland to PSAB/WSB | N/A | 5.0 | 5 |
| N3 | PSAB/WSB to 104th Bridge | N/A | 5.0 | 3 |
| N4 | 104th to Queen/York | N/A | 5.0 | 4 |
| N5 | Queen/York to Queen at PSAB | N/A | 5.0 | 3 |
| N6 | Queen at PSAB to PSAB/WSB | N/A | 5.0 | 3 |
| N7 | PSAB/WSB to 104th Bridge | N/A | 5.0 | 3 |
| N8 | 104th to Queen/York | N/A | 5.0 | 4 |
| N9 | Queen/York to Finish | N/A | 5.0 | 1 |
| O1 | Start to Queen/Westmorland | N/A | 5.0 | 3 |
| O2 | Queen/Westmorland to PSAB/WSB | N/A | 5.0 | 5 |
| O3 | PSAB/WSB to 104th Bridge | N/A | 5.0 | 3 |
| O4 | 104th to Queen/York | N/A | 5.0 | 4 |
| O5 | Queen/York to Queen at PSAB | N/A | 5.0 | 3 |
| O6 | Queen at PSAB to PSAB/WSB | N/A | 5.0 | 3 |
| O7 | PSAB/WSB to 104th Bridge | N/A | 5.0 | 3 |
| O8 | 104th to Queen/York | N/A | 5.0 | 4 |
| O9 | Queen/York to Finish | N/A | 5.0 | 1 |

> Note: Each spatial bin is analyzed across 80 time windows (30-second intervals). Total space-time bins per segment = spatial bins × 80 (e.g., A1: 5 × 80 = 400; I1: 121 × 80 = 9,680).

---

## Flagged Segments

| Segment | Label | Flagged Bins | Total Bins | % | Worst Bin (km) | Time | Density (p/m²) | Rate (p/s) | Util% | LOS | Severity | Reason |
|----------|--------|--------------|------------|---|----------------|-------|----------------|-------------|-------|-----|-----------|---------|
| N1 | Start to Queen/Westmorland | 3 | 225 | 1.3% | 0.0-0.2 | 08:00 | 0.0390 | 0.950 | N/A | A | watch | none |
| N2 | Queen/Westmorland to PSAB/WSB | 7 | 375 | 1.9% | 0.2-0.4 | 08:02 | 0.0260 | 0.600 | N/A | A | watch | none |
| N3 | PSAB/WSB to 104th Bridge | 4 | 225 | 1.8% | 0.0-0.2 | 08:04 | 0.0260 | 0.650 | N/A | A | watch | none |
| N4 | 104th to Queen/York | 8 | 300 | 2.7% | 0.2-0.4 | 08:06 | 0.0210 | 0.540 | N/A | A | watch | none |
| N5 | Queen/York to Queen at PSAB | 5 | 225 | 2.2% | 0.0-0.2 | 08:08 | 0.0180 | 0.440 | N/A | A | watch | none |
| N6 | Queen at PSAB to PSAB/WSB | 6 | 225 | 2.7% | 0.0-0.2 | 08:10 | 0.0170 | 0.410 | N/A | A | watch | none |
| N7 | PSAB/WSB to 104th Bridge | 4 | 225 | 1.8% | 0.0-0.2 | 08:12 | 0.0160 | 0.390 | N/A | A | watch | none |
| N8 | 104th to Queen/York | 13 | 300 | 4.3% | 0.2-0.4 | 08:14 | 0.0130 | 0.310 | N/A | A | watch | none |
| N9 | Queen/York to Finish | 4 | 75 | 5.3% | 0.0-0.2 | 08:16 | 0.0140 | 0.330 | N/A | A | watch | none |
| O1 | Start to Queen/Westmorland | 8 | 225 | 3.6% | 0.0-0.2 | 08:30 | 0.6920 | 8.730 | N/A | C | critical | none |
| O2 | Queen/Westmorland to PSAB/WSB | 18 | 375 | 4.8% | 0.0-0.2 | 08:34 | 0.4430 | 5.490 | N/A | B | watch | none |
| O3 | PSAB/WSB to 104th Bridge | 8 | 225 | 3.6% | 0.0-0.2 | 08:40 | 0.2660 | 3.270 | N/A | A | watch | none |
| O4 | 104th to Queen/York | 13 | 300 | 4.3% | 0.0-0.2 | 08:44 | 0.2130 | 2.450 | N/A | A | watch | none |
| O5 | Queen/York to Queen at PSAB | 14 | 225 | 6.2% | 0.0-0.2 | 08:48 | 0.1650 | 1.990 | N/A | A | watch | none |
| O6 | Queen at PSAB to PSAB/WSB | 12 | 225 | 5.3% | 0.2-0.4 | 08:54 | 0.1330 | 1.560 | N/A | A | watch | none |
| O7 | PSAB/WSB to 104th Bridge | 18 | 225 | 8.0% | 0.2-0.4 | 08:58 | 0.1240 | 1.440 | N/A | A | watch | none |
| O8 | 104th to Queen/York | 50 | 300 | 16.7% | 0.0-0.2 | 09:00 | 0.1230 | 1.410 | N/A | A | watch | none |
| O9 | Queen/York to Finish | 15 | 75 | 20.0% | 0.0-0.2 | 09:06 | 0.0990 | 1.120 | N/A | A | watch | none |

---

## Operational Heatmap

*Operational heatmap visualization will be added in a future release via new maps capability.*

This section will provide:
- Visual density/rate heatmaps across course segments
- Time-based animation of crowd flows
- Interactive bin-level detail views

---

## Bin-Level Detail

Detailed bin-by-bin breakdown for segments with operational intelligence flags:

### Start to Queen/Westmorland (N1)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:00 | 08:02 | 0.039 | 0.955 | A |
| 0.2 | 0.4 | 08:00 | 08:02 | 0.010 | 0.214 | A |
| 0.4 | 0.6 | 08:00 | 08:02 | 0.029 | 0.741 | A |

### Queen/Westmorland to PSAB/WSB (N2)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:02 | 08:04 | 0.026 | 0.596 | A |
| 0.2 | 0.4 | 08:02 | 08:04 | 0.026 | 0.641 | A |
| 0.4 | 0.6 | 08:02 | 08:04 | 0.019 | 0.474 | A |
| 0.6 | 0.8 | 08:02 | 08:04 | 0.007 | 0.198 | A |
| 0.4 | 0.6 | 08:04 | 08:06 | 0.006 | 0.125 | A |
| 0.6 | 0.8 | 08:04 | 08:06 | 0.023 | 0.528 | A |
| 0.8 | 0.9 | 08:04 | 08:06 | 0.007 | 0.174 | A |

### PSAB/WSB to 104th Bridge (N3)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:04 | 08:06 | 0.026 | 0.648 | A |
| 0.2 | 0.4 | 08:04 | 08:06 | 0.012 | 0.321 | A |
| 0.2 | 0.4 | 08:06 | 08:08 | 0.015 | 0.340 | A |
| 0.4 | 0.4 | 08:06 | 08:08 | 0.006 | 0.134 | A |

### 104th to Queen/York (N4)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:04 | 08:06 | 0.003 | 0.086 | A |
| 0.0 | 0.2 | 08:06 | 08:08 | 0.017 | 0.407 | A |
| 0.2 | 0.4 | 08:06 | 08:08 | 0.021 | 0.541 | A |
| 0.4 | 0.6 | 08:06 | 08:08 | 0.007 | 0.186 | A |
| 0.6 | 0.7 | 08:06 | 08:08 | 0.005 | 0.141 | A |
| 0.2 | 0.4 | 08:08 | 08:10 | 0.009 | 0.191 | A |
| 0.4 | 0.6 | 08:08 | 08:10 | 0.018 | 0.409 | A |
| 0.6 | 0.7 | 08:08 | 08:10 | 0.007 | 0.164 | A |

### Queen/York to Queen at PSAB (N5)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:08 | 08:10 | 0.018 | 0.440 | A |
| 0.2 | 0.4 | 08:08 | 08:10 | 0.013 | 0.353 | A |
| 0.0 | 0.2 | 08:10 | 08:12 | 0.008 | 0.169 | A |
| 0.2 | 0.4 | 08:10 | 08:12 | 0.015 | 0.336 | A |
| 0.4 | 0.6 | 08:10 | 08:12 | 0.010 | 0.232 | A |

### Queen at PSAB to PSAB/WSB (N6)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:08 | 08:10 | 0.007 | 0.198 | A |
| 0.0 | 0.2 | 08:10 | 08:12 | 0.017 | 0.414 | A |
| 0.2 | 0.4 | 08:10 | 08:12 | 0.009 | 0.240 | A |
| 0.4 | 0.5 | 08:10 | 08:12 | 0.009 | 0.246 | A |
| 0.2 | 0.4 | 08:12 | 08:14 | 0.015 | 0.336 | A |
| 0.4 | 0.5 | 08:12 | 08:14 | 0.009 | 0.207 | A |

### PSAB/WSB to 104th Bridge (N7)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:12 | 08:14 | 0.016 | 0.386 | A |
| 0.0 | 0.2 | 08:14 | 08:16 | 0.005 | 0.107 | A |
| 0.2 | 0.4 | 08:14 | 08:16 | 0.011 | 0.247 | A |
| 0.4 | 0.4 | 08:16 | 08:18 | 0.002 | 0.040 | A |

### 104th to Queen/York (N8)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:12 | 08:14 | 0.010 | 0.273 | A |
| 0.2 | 0.4 | 08:12 | 08:14 | 0.005 | 0.139 | A |
| 0.4 | 0.6 | 08:12 | 08:14 | 0.007 | 0.198 | A |
| 0.0 | 0.2 | 08:14 | 08:16 | 0.010 | 0.234 | A |
| 0.2 | 0.4 | 08:14 | 08:16 | 0.013 | 0.315 | A |
| 0.4 | 0.6 | 08:14 | 08:16 | 0.007 | 0.182 | A |
| 0.0 | 0.2 | 08:16 | 08:18 | 0.004 | 0.084 | A |
| 0.2 | 0.4 | 08:16 | 08:18 | 0.010 | 0.217 | A |
| 0.4 | 0.6 | 08:16 | 08:18 | 0.011 | 0.254 | A |
| 0.6 | 0.7 | 08:16 | 08:18 | 0.005 | 0.117 | A |
| 0.2 | 0.4 | 08:18 | 08:20 | 0.001 | 0.020 | A |
| 0.4 | 0.6 | 08:18 | 08:20 | 0.005 | 0.103 | A |
| 0.6 | 0.7 | 08:18 | 08:20 | 0.001 | 0.021 | A |

### Queen/York to Finish (N9)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:14 | 08:16 | 0.010 | 0.278 | A |
| 0.0 | 0.2 | 08:16 | 08:18 | 0.014 | 0.334 | A |
| 0.0 | 0.2 | 08:18 | 08:20 | 0.008 | 0.172 | A |
| 0.0 | 0.2 | 08:20 | 08:22 | 0.001 | 0.020 | A |

### Start to Queen/Westmorland (O1)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:30 | 08:32 | 0.692 | 8.729 | C |
| 0.2 | 0.4 | 08:30 | 08:32 | 0.153 | 2.448 | A |
| 0.4 | 0.6 | 08:30 | 08:32 | 0.006 | 0.139 | A |
| 0.0 | 0.2 | 08:32 | 08:34 | 0.064 | 0.593 | A |
| 0.2 | 0.4 | 08:32 | 08:34 | 0.563 | 6.511 | C |
| 0.4 | 0.6 | 08:32 | 08:34 | 0.330 | 4.548 | A |
| 0.2 | 0.4 | 08:34 | 08:36 | 0.037 | 0.302 | A |
| 0.4 | 0.6 | 08:34 | 08:36 | 0.273 | 2.802 | A |

### Queen/Westmorland to PSAB/WSB (O2)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:32 | 08:34 | 0.112 | 1.956 | A |
| 0.2 | 0.4 | 08:32 | 08:34 | 0.028 | 0.569 | A |
| 0.4 | 0.6 | 08:32 | 08:34 | 0.002 | 0.049 | A |
| 0.0 | 0.2 | 08:34 | 08:36 | 0.443 | 5.494 | B |
| 0.2 | 0.4 | 08:34 | 08:36 | 0.212 | 3.133 | A |
| 0.4 | 0.6 | 08:34 | 08:36 | 0.090 | 1.584 | A |
| 0.6 | 0.8 | 08:34 | 08:36 | 0.035 | 0.707 | A |
| 0.0 | 0.2 | 08:36 | 08:38 | 0.174 | 1.626 | A |
| 0.2 | 0.4 | 08:36 | 08:38 | 0.351 | 4.092 | A |
| 0.4 | 0.6 | 08:36 | 08:38 | 0.286 | 3.790 | A |
| 0.6 | 0.8 | 08:36 | 08:38 | 0.137 | 2.117 | A |
| 0.8 | 0.9 | 08:36 | 08:38 | 0.033 | 0.559 | A |
| 0.2 | 0.4 | 08:38 | 08:40 | 0.113 | 1.017 | A |
| 0.4 | 0.6 | 08:38 | 08:40 | 0.240 | 2.639 | A |
| 0.6 | 0.8 | 08:38 | 08:40 | 0.311 | 3.859 | A |
| 0.8 | 0.9 | 08:38 | 08:40 | 0.083 | 1.125 | A |
| 0.6 | 0.8 | 08:40 | 08:42 | 0.163 | 1.719 | A |
| 0.8 | 0.9 | 08:40 | 08:42 | 0.091 | 1.045 | A |

### PSAB/WSB to 104th Bridge (O3)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:36 | 08:38 | 0.055 | 1.018 | A |
| 0.0 | 0.2 | 08:38 | 08:40 | 0.140 | 2.063 | A |
| 0.2 | 0.4 | 08:38 | 08:40 | 0.081 | 1.330 | A |
| 0.0 | 0.2 | 08:40 | 08:42 | 0.266 | 3.266 | A |
| 0.2 | 0.4 | 08:40 | 08:42 | 0.174 | 2.373 | A |
| 0.0 | 0.2 | 08:42 | 08:44 | 0.153 | 1.644 | A |
| 0.2 | 0.4 | 08:42 | 08:44 | 0.225 | 2.657 | A |
| 0.2 | 0.4 | 08:44 | 08:46 | 0.092 | 0.945 | A |

### 104th to Queen/York (O4)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:40 | 08:42 | 0.097 | 1.488 | A |
| 0.2 | 0.4 | 08:40 | 08:42 | 0.060 | 1.006 | A |
| 0.0 | 0.2 | 08:42 | 08:44 | 0.197 | 2.578 | A |
| 0.2 | 0.4 | 08:42 | 08:44 | 0.111 | 1.585 | A |
| 0.4 | 0.6 | 08:42 | 08:44 | 0.078 | 1.218 | A |
| 0.0 | 0.2 | 08:44 | 08:46 | 0.213 | 2.453 | A |
| 0.2 | 0.4 | 08:44 | 08:46 | 0.183 | 2.303 | A |
| 0.4 | 0.6 | 08:44 | 08:46 | 0.136 | 1.837 | A |
| 0.2 | 0.4 | 08:46 | 08:48 | 0.159 | 1.787 | A |
| 0.4 | 0.6 | 08:46 | 08:48 | 0.185 | 2.222 | A |
| 0.6 | 0.7 | 08:46 | 08:48 | 0.082 | 1.052 | A |
| 0.4 | 0.6 | 08:48 | 08:50 | 0.112 | 1.234 | A |
| 0.6 | 0.7 | 08:48 | 08:50 | 0.087 | 0.996 | A |

### Queen/York to Queen at PSAB (O5)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:42 | 08:44 | 0.043 | 0.747 | A |
| 0.0 | 0.2 | 08:44 | 08:46 | 0.075 | 1.138 | A |
| 0.2 | 0.4 | 08:44 | 08:46 | 0.051 | 0.828 | A |
| 0.0 | 0.2 | 08:46 | 08:48 | 0.134 | 1.801 | A |
| 0.2 | 0.4 | 08:46 | 08:48 | 0.079 | 1.137 | A |
| 0.4 | 0.6 | 08:46 | 08:48 | 0.058 | 0.888 | A |
| 0.0 | 0.2 | 08:48 | 08:50 | 0.165 | 1.990 | A |
| 0.2 | 0.4 | 08:48 | 08:50 | 0.134 | 1.742 | A |
| 0.4 | 0.6 | 08:48 | 08:50 | 0.091 | 1.242 | A |
| 0.0 | 0.2 | 08:50 | 08:52 | 0.125 | 1.391 | A |
| 0.2 | 0.4 | 08:50 | 08:52 | 0.152 | 1.775 | A |
| 0.4 | 0.6 | 08:50 | 08:52 | 0.111 | 1.390 | A |
| 0.2 | 0.4 | 08:52 | 08:54 | 0.085 | 0.928 | A |
| 0.4 | 0.6 | 08:52 | 08:54 | 0.124 | 1.415 | A |

### Queen at PSAB to PSAB/WSB (O6)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:48 | 08:50 | 0.071 | 1.029 | A |
| 0.0 | 0.2 | 08:50 | 08:52 | 0.128 | 1.685 | A |
| 0.2 | 0.4 | 08:50 | 08:52 | 0.077 | 1.068 | A |
| 0.0 | 0.2 | 08:52 | 08:54 | 0.132 | 1.584 | A |
| 0.2 | 0.4 | 08:52 | 08:54 | 0.121 | 1.556 | A |
| 0.4 | 0.5 | 08:52 | 08:54 | 0.074 | 0.985 | A |
| 0.0 | 0.2 | 08:54 | 08:56 | 0.123 | 1.379 | A |
| 0.2 | 0.4 | 08:54 | 08:56 | 0.133 | 1.556 | A |
| 0.4 | 0.5 | 08:54 | 08:56 | 0.073 | 0.900 | A |
| 0.2 | 0.4 | 08:56 | 08:58 | 0.089 | 0.981 | A |
| 0.4 | 0.5 | 08:56 | 08:58 | 0.083 | 0.945 | A |
| 0.2 | 0.4 | 09:08 | 09:10 | 0.024 | 0.181 | A |

### PSAB/WSB to 104th Bridge (O7)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:50 | 08:52 | 0.049 | 0.744 | A |
| 0.0 | 0.2 | 08:52 | 08:54 | 0.069 | 0.957 | A |
| 0.0 | 0.2 | 08:54 | 08:56 | 0.107 | 1.386 | A |
| 0.2 | 0.4 | 08:54 | 08:56 | 0.094 | 1.261 | A |
| 0.0 | 0.2 | 08:56 | 08:58 | 0.117 | 1.385 | A |
| 0.2 | 0.4 | 08:56 | 08:58 | 0.100 | 1.257 | A |
| 0.0 | 0.2 | 08:58 | 09:00 | 0.105 | 1.177 | A |
| 0.2 | 0.4 | 08:58 | 09:00 | 0.124 | 1.439 | A |
| 0.2 | 0.4 | 09:00 | 09:02 | 0.082 | 0.905 | A |
| 0.0 | 0.2 | 09:02 | 09:04 | 0.049 | 0.481 | A |
| 0.2 | 0.4 | 09:04 | 09:06 | 0.045 | 0.439 | A |
| 0.2 | 0.4 | 09:06 | 09:08 | 0.029 | 0.264 | A |
| 0.2 | 0.4 | 09:08 | 09:10 | 0.023 | 0.198 | A |
| 0.2 | 0.4 | 09:10 | 09:12 | 0.019 | 0.156 | A |
| 0.0 | 0.2 | 09:12 | 09:14 | 0.020 | 0.150 | A |
| 0.2 | 0.4 | 09:12 | 09:14 | 0.020 | 0.156 | A |
| 0.2 | 0.4 | 09:14 | 09:16 | 0.022 | 0.166 | A |
| 0.2 | 0.4 | 09:16 | 09:18 | 0.004 | 0.029 | A |

### 104th to Queen/York (O8)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:54 | 08:56 | 0.059 | 0.839 | A |
| 0.0 | 0.2 | 08:56 | 08:58 | 0.103 | 1.357 | A |
| 0.2 | 0.4 | 08:56 | 08:58 | 0.077 | 1.064 | A |
| 0.0 | 0.2 | 08:58 | 09:00 | 0.088 | 1.084 | A |
| 0.2 | 0.4 | 08:58 | 09:00 | 0.104 | 1.348 | A |
| 0.4 | 0.6 | 08:58 | 09:00 | 0.080 | 1.071 | A |
| 0.0 | 0.2 | 09:00 | 09:02 | 0.123 | 1.414 | A |
| 0.2 | 0.4 | 09:00 | 09:02 | 0.090 | 1.082 | A |
| 0.4 | 0.6 | 09:00 | 09:02 | 0.084 | 1.068 | A |
| 0.6 | 0.7 | 09:00 | 09:02 | 0.049 | 0.638 | A |
| 0.0 | 0.2 | 09:02 | 09:04 | 0.058 | 0.634 | A |
| 0.2 | 0.4 | 09:02 | 09:04 | 0.117 | 1.326 | A |
| 0.4 | 0.6 | 09:02 | 09:04 | 0.100 | 1.181 | A |
| 0.6 | 0.7 | 09:02 | 09:04 | 0.036 | 0.436 | A |
| 0.0 | 0.2 | 09:04 | 09:06 | 0.037 | 0.377 | A |
| 0.2 | 0.4 | 09:04 | 09:06 | 0.046 | 0.495 | A |
| 0.4 | 0.6 | 09:04 | 09:06 | 0.094 | 1.054 | A |
| 0.6 | 0.7 | 09:04 | 09:06 | 0.058 | 0.665 | A |
| 0.0 | 0.2 | 09:06 | 09:08 | 0.043 | 0.419 | A |
| 0.2 | 0.4 | 09:06 | 09:08 | 0.037 | 0.372 | A |
| 0.4 | 0.6 | 09:06 | 09:08 | 0.039 | 0.415 | A |
| 0.6 | 0.7 | 09:06 | 09:08 | 0.023 | 0.251 | A |
| 0.0 | 0.2 | 09:08 | 09:10 | 0.028 | 0.255 | A |
| 0.2 | 0.4 | 09:08 | 09:10 | 0.039 | 0.379 | A |
| 0.4 | 0.6 | 09:08 | 09:10 | 0.038 | 0.380 | A |
| 0.0 | 0.2 | 09:10 | 09:12 | 0.025 | 0.217 | A |
| 0.2 | 0.4 | 09:10 | 09:12 | 0.026 | 0.236 | A |
| 0.4 | 0.6 | 09:10 | 09:12 | 0.031 | 0.300 | A |
| 0.6 | 0.7 | 09:10 | 09:12 | 0.023 | 0.227 | A |
| 0.0 | 0.2 | 09:12 | 09:14 | 0.016 | 0.133 | A |
| 0.2 | 0.4 | 09:12 | 09:14 | 0.022 | 0.190 | A |
| 0.4 | 0.6 | 09:12 | 09:14 | 0.024 | 0.216 | A |
| 0.0 | 0.2 | 09:14 | 09:16 | 0.021 | 0.166 | A |
| 0.2 | 0.4 | 09:14 | 09:16 | 0.016 | 0.133 | A |
| 0.4 | 0.6 | 09:14 | 09:16 | 0.021 | 0.181 | A |
| 0.6 | 0.7 | 09:14 | 09:16 | 0.012 | 0.107 | A |
| 0.0 | 0.2 | 09:16 | 09:18 | 0.022 | 0.167 | A |
| 0.2 | 0.4 | 09:16 | 09:18 | 0.017 | 0.135 | A |
| 0.4 | 0.6 | 09:16 | 09:18 | 0.016 | 0.133 | A |
| 0.6 | 0.7 | 09:16 | 09:18 | 0.010 | 0.086 | A |
| 0.0 | 0.2 | 09:18 | 09:20 | 0.006 | 0.045 | A |
| 0.2 | 0.4 | 09:18 | 09:20 | 0.025 | 0.190 | A |
| 0.4 | 0.6 | 09:18 | 09:20 | 0.015 | 0.120 | A |
| 0.6 | 0.7 | 09:18 | 09:20 | 0.008 | 0.066 | A |
| 0.2 | 0.4 | 09:20 | 09:22 | 0.008 | 0.059 | A |
| 0.4 | 0.6 | 09:20 | 09:22 | 0.023 | 0.175 | A |
| 0.6 | 0.7 | 09:20 | 09:22 | 0.006 | 0.047 | A |
| 0.4 | 0.6 | 09:22 | 09:24 | 0.010 | 0.074 | A |
| 0.6 | 0.7 | 09:22 | 09:24 | 0.010 | 0.076 | A |
| 0.6 | 0.7 | 09:24 | 09:26 | 0.004 | 0.029 | A |

### Queen/York to Finish (O9)

| Start (km) | End (km) | Start (t) | End (t) | Density (p/m²) | Rate (p/s) | LOS |
|------------|----------|-----------|---------|----------------|-------------|-----|
| 0.0 | 0.2 | 08:58 | 09:00 | 0.052 | 0.740 | A |
| 0.0 | 0.2 | 09:00 | 09:02 | 0.082 | 1.094 | A |
| 0.0 | 0.2 | 09:02 | 09:04 | 0.074 | 0.938 | A |
| 0.0 | 0.2 | 09:04 | 09:06 | 0.090 | 1.066 | A |
| 0.0 | 0.2 | 09:06 | 09:08 | 0.099 | 1.116 | A |
| 0.0 | 0.2 | 09:08 | 09:10 | 0.036 | 0.386 | A |
| 0.0 | 0.2 | 09:10 | 09:12 | 0.030 | 0.302 | A |
| 0.0 | 0.2 | 09:12 | 09:14 | 0.037 | 0.361 | A |
| 0.0 | 0.2 | 09:14 | 09:16 | 0.020 | 0.184 | A |
| 0.0 | 0.2 | 09:16 | 09:18 | 0.021 | 0.184 | A |
| 0.0 | 0.2 | 09:18 | 09:20 | 0.016 | 0.136 | A |
| 0.0 | 0.2 | 09:20 | 09:22 | 0.016 | 0.130 | A |
| 0.0 | 0.2 | 09:22 | 09:24 | 0.017 | 0.131 | A |
| 0.0 | 0.2 | 09:24 | 09:26 | 0.019 | 0.144 | A |
| 0.0 | 0.2 | 09:26 | 09:28 | 0.004 | 0.029 | A |

---

## Segment Details

### Start to Queen/Westmorland (N1)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0390 p/m² (LOS A), Rate 0.19 p/s
- **Worst Bin:** 0.0-0.2 km at 08:00 — watch (none)
- **Mitigations:** No mitigations required

### Queen/Westmorland to PSAB/WSB (N2)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 375
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0260 p/m² (LOS A), Rate 0.12 p/s
- **Worst Bin:** 0.2-0.4 km at 08:02 — watch (none)
- **Mitigations:** No mitigations required

### PSAB/WSB to 104th Bridge (N3)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0260 p/m² (LOS A), Rate 0.13 p/s
- **Worst Bin:** 0.0-0.2 km at 08:04 — watch (none)
- **Mitigations:** No mitigations required

### 104th to Queen/York (N4)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 300
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0210 p/m² (LOS A), Rate 0.11 p/s
- **Worst Bin:** 0.2-0.4 km at 08:06 — watch (none)
- **Mitigations:** No mitigations required

### Queen/York to Queen at PSAB (N5)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0180 p/m² (LOS A), Rate 0.09 p/s
- **Worst Bin:** 0.0-0.2 km at 08:08 — watch (none)
- **Mitigations:** No mitigations required

### Queen at PSAB to PSAB/WSB (N6)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0170 p/m² (LOS A), Rate 0.08 p/s
- **Worst Bin:** 0.0-0.2 km at 08:10 — watch (none)
- **Mitigations:** No mitigations required

### PSAB/WSB to 104th Bridge (N7)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0160 p/m² (LOS A), Rate 0.08 p/s
- **Worst Bin:** 0.0-0.2 km at 08:12 — watch (none)
- **Mitigations:** No mitigations required

### 104th to Queen/York (N8)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 300
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0130 p/m² (LOS A), Rate 0.06 p/s
- **Worst Bin:** 0.2-0.4 km at 08:14 — watch (none)
- **Mitigations:** No mitigations required

### Queen/York to Finish (N9)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 75
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0140 p/m² (LOS A), Rate 0.07 p/s
- **Worst Bin:** 0.0-0.2 km at 08:16 — watch (none)
- **Mitigations:** No mitigations required

### Start to Queen/Westmorland (O1)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.6920 p/m² (LOS C), Rate 1.75 p/s
- **Worst Bin:** 0.0-0.2 km at 08:30 — critical (none)
- **Mitigations:** No mitigations required

### Queen/Westmorland to PSAB/WSB (O2)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 375
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.4430 p/m² (LOS B), Rate 1.10 p/s
- **Worst Bin:** 0.0-0.2 km at 08:34 — watch (none)
- **Mitigations:** No mitigations required

### PSAB/WSB to 104th Bridge (O3)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.2660 p/m² (LOS A), Rate 0.65 p/s
- **Worst Bin:** 0.0-0.2 km at 08:40 — watch (none)
- **Mitigations:** No mitigations required

### 104th to Queen/York (O4)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 300
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.2130 p/m² (LOS A), Rate 0.49 p/s
- **Worst Bin:** 0.0-0.2 km at 08:44 — watch (none)
- **Mitigations:** No mitigations required

### Queen/York to Queen at PSAB (O5)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.1650 p/m² (LOS A), Rate 0.40 p/s
- **Worst Bin:** 0.0-0.2 km at 08:48 — watch (none)
- **Mitigations:** No mitigations required

### Queen at PSAB to PSAB/WSB (O6)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.1330 p/m² (LOS A), Rate 0.31 p/s
- **Worst Bin:** 0.2-0.4 km at 08:54 — watch (none)
- **Mitigations:** No mitigations required

### PSAB/WSB to 104th Bridge (O7)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 225
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.1240 p/m² (LOS A), Rate 0.29 p/s
- **Worst Bin:** 0.2-0.4 km at 08:58 — watch (none)
- **Mitigations:** No mitigations required

### 104th to Queen/York (O8)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 300
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.1230 p/m² (LOS A), Rate 0.28 p/s
- **Worst Bin:** 0.0-0.2 km at 09:00 — watch (none)
- **Mitigations:** No mitigations required

### Queen/York to Finish (O9)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 75
- **Active:** 08:00 → 10:30
- **Peaks:** Density 0.0990 p/m² (LOS A), Rate 0.22 p/s
- **Worst Bin:** 0.0-0.2 km at 09:06 — watch (none)
- **Mitigations:** No mitigations required

---

## Mitigations


---

## Appendix

### Definitions of Metrics
- **Density (ρ):** Areal density in persons per square meter (p/m²)
- **Rate (q):** Throughput rate in persons per second (p/s)
- **Rate per meter per minute:** (rate / width_m) × 60 in persons/m/min
- **Utilization (%):** Current flow rate / reference flow rate (critical). Shows "N/A" when \`flow_ref.critical\` is not defined for the segment schema in the rulebook.
- **LOS (Level of Service):** Crowd comfort class (A–F) derived from density only
- **Bin:** Space–time cell [segment_id, start_km–end_km, t_start–t_end]

### LOS Thresholds
| LOS | Density Range (p/m²) | Description |
|-----|---------------------|-------------|
| A | 0.00 - 0.36 | Free Flow |
| B | 0.36 - 0.54 | Comfortable |
| C | 0.54 - 0.72 | Moderate |
| D | 0.72 - 1.08 | Dense |
| E | 1.08 - 1.63 | Very Dense |
| F | 1.63+ | Extremely Dense |

### Trigger Logic & Severity
- **los_high:** Density ≥ LOS C threshold (LOS is density-only)
- **rate_high:** Rate per m per min ≥ warning threshold
- **both:** Both density and rate conditions met (rate affects severity, not LOS)
- **Severity:** critical > watch > none

### Terminology Notes
- "Rate" = persons/s (formerly "Flow")
- Note: operational heatmap to be added in future release