# Fredericton Marathon — Density Report
**Schema:** 1.0.0
**Method:** segments_from_bins
**Date:** 2025-12-14 01:23:22
**Inputs:** bins.parquet, segments.parquet, segment_windows_from_bins.parquet
**App:** vv1.8.5

---

## Executive Summary
- **Peak Density:** 0.0000 p/m² (LOS A)
- **Peak Rate:** 0.00 p/s
- **Segments with Flags:** 0 / 6
- **Flagged Bins:** 0 / 4160
- **Operational Status:** ✅ All Clear (No operational flags)

> LOS (Level of Service) describes how comfortable runners are within a section — A means free-flowing, while E/F indicate crowding. Even when overall LOS is good, short-lived surges in runner flow can stress aid stations or intersections, requiring active flow management.

---

## Methodology & Inputs
- **Window Size:** 30 s; **Bin Size:** 0.2 km

### LOS and Rate Triggers (from Rulebook)
- **LOS thresholds** define crowding levels based on density (p/m²):
  - A: < 0.36 | B: 0.36–0.54 | C: 0.54–0.72 | D: 0.72–1.08 | E: 1.08–1.63 | F: > 1.63
- **Rate thresholds** define throughput risk based on flow references (persons/m/min):
  - Warning: 15.0 | Critical: 25.0

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
| N1 | 5K Elite Lap 1 (Start to Queen/York) | N/A | 5.0 | 13 |
| N2 | 5K Elite Lap 2 (Queen/York to Queen/York) | N/A | 5.0 | 12 |
| N3 | 5K Elite Finish (Queen/York to Finish) | N/A | 5.0 | 1 |
| O1 | 5K Open Lap 1 (Start to Queen/York) | N/A | 5.0 | 13 |
| O2 | 5K Open Lap 2 (Queen/York to Queen/York) | N/A | 5.0 | 12 |
| O3 | 5K Open Finish (Queen/York to Finish) | N/A | 5.0 | 1 |

> Note: Each spatial bin is analyzed across 80 time windows (30-second intervals). Total space-time bins per segment = spatial bins × 80 (e.g., A1: 5 × 80 = 400; I1: 121 × 80 = 9,680).

---

## Flagged Segments

| Segment | Label | Flagged Bins | Total Bins | % | Worst Bin (km) | Time | Density (p/m²) | Rate (p/s) | Util% | LOS | Severity | Reason |
|----------|--------|--------------|------------|---|----------------|-------|----------------|-------------|-------|-----|-----------|---------|
| *No flagged segments* | | | | | | | | | | | | |

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

*No flagged bins to display*

---

## Segment Details

### 5K Elite Lap 1 (Start to Queen/York) (N1)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 1040
- **Active:** 07:00 → 10:00
- **Peaks:** Density 0.0000 p/m² (LOS A), Rate 0.00 p/s
- **Worst Bin:** 0.0-0.0 km at N/A — none (none)
- **Mitigations:** No mitigations required

### 5K Elite Lap 2 (Queen/York to Queen/York) (N2)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 960
- **Active:** 07:00 → 10:00
- **Peaks:** Density 0.0000 p/m² (LOS A), Rate 0.00 p/s
- **Worst Bin:** 0.0-0.0 km at N/A — none (none)
- **Mitigations:** No mitigations required

### 5K Elite Finish (Queen/York to Finish) (N3)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 80
- **Active:** 07:00 → 10:00
- **Peaks:** Density 0.0000 p/m² (LOS A), Rate 0.00 p/s
- **Worst Bin:** 0.0-0.0 km at N/A — none (none)
- **Mitigations:** No mitigations required

### 5K Open Lap 1 (Start to Queen/York) (O1)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 1040
- **Active:** 07:00 → 10:00
- **Peaks:** Density 0.0000 p/m² (LOS A), Rate 0.00 p/s
- **Worst Bin:** 0.0-0.0 km at N/A — none (none)
- **Mitigations:** No mitigations required

### 5K Open Lap 2 (Queen/York to Queen/York) (O2)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 960
- **Active:** 07:00 → 10:00
- **Peaks:** Density 0.0000 p/m² (LOS A), Rate 0.00 p/s
- **Worst Bin:** 0.0-0.0 km at N/A — none (none)
- **Mitigations:** No mitigations required

### 5K Open Finish (Queen/York to Finish) (O3)
- **Schema:** on_course_open · **Width:** 5.0 m · **Bins:** 80
- **Active:** 07:00 → 10:00
- **Peaks:** Density 0.0000 p/m² (LOS A), Rate 0.00 p/s
- **Worst Bin:** 0.0-0.0 km at N/A — none (none)
- **Mitigations:** No mitigations required

---

## Mitigations
No operational mitigations required.

---

## Appendix

### Definitions of Metrics
- **Density (ρ):** Areal density in persons per square meter (p/m²)
- **Rate (q):** Throughput rate in persons per second (p/s)
- **Rate per meter per minute:** (rate / width_m) × 60 in persons/m/min
- **Utilization (%):** Current flow rate / reference flow rate (critical)
- **LOS (Level of Service):** Crowd comfort class (A–F)
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
- **los_high:** Density ≥ LOS C threshold
- **rate_high:** Rate per m per min ≥ warning threshold
- **both:** Both density and rate conditions met
- **Severity:** critical > watch > none

### Terminology Notes
- "Rate" = persons/s (formerly "Flow")
- Note: operational heatmap to be added in future release