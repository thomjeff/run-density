
# Flow Zones Data Guide

This document provides a detailed explanation of each field in the `flow_zones` dataset, with narrative examples using real data from the A2a segment (Sunday event). It is intended for data analysts and reviewers interpreting flow dynamics in multi-convergence-point (multi‑CP) race segments.

---

## Overview

Each row in `flow_zones` represents a flow analysis zone derived from convergence points (CPs) between two events (e.g., 10K and Half-Marathon) on the same segment. Zones are ~100–150m in length and are used to detect interactions such as overtaking and co-presence.

### Example: A2a Segment
A2a spans Queen/Regent to WSB midpoint. It includes 5 zones created during analysis between convergence points at 1.33km and 1.73km.

![A2a Flow Visualization](https://raw.githubusercontent.com/thomjeff/run-density/refs/heads/main/docs/user-guide/a2segment.png?token=GHSAT0AAAAAADQKQF4OFDQHN3G4FFL3R6MI2K5QQHQ) 


**Event Start Times and Participant Counts**

The two race events involved in this analysis started at different times:
| Event | Start Time | Runners | 
|-------|------------|---------|
|10k|07:20 (440)|618|
|half|07:40 (460)|912|

This 20-minute gap is essential context for understanding overtaking patterns — the Half field begins behind but at a faster pace.


## Flow Zone Key metrics:

|seg_id| event_a | event_b | zone_index | cp_km | zone_start_km_a | zone_end_km_a | zone_start_km_b | zone_end_km_b | overtaking_a | overtaking_b | copresence_a | copresence_b | unique_encounters | participants_involved |
|---|---------|---------|------------|-------|------------------|----------------|------------------|----------------|---------------|---------------|----------------|----------------|----------------------|--------------------------|
| A2a | 10k     | half    | 0          | 1.33  | 1.28             | 1.38           | 1.28             | 1.38           | 0             | 5             | 0              | 0              | 5                    | 6                        |
| A2a | 10k     | half    | 1          | 1.43  | 1.38             | 1.48           | 1.38             | 1.48           | 0             | 14            | 0              | 0              | 14                   | 15                       |
| A2a | 10k     | half    | 2          | 1.53  | 1.48             | 1.58           | 1.48             | 1.58           | 0             | 26            | 0              | 0              | 26                   | 27                       |
| A2a | 10k     | half    | 3          | 1.63  | 1.58             | 1.68           | 1.58             | 1.68           | 0             | 31            | 1              | 2              | 33                   | 34                       |
| A2a | 10k     | half    | 4          | 1.73  | 1.68             | 1.78           | 1.68             | 1.78           | 0             | 27            | 1              | 15             | 42                   | 43                       |


---

## Field Definitions

### `seg_id`
The segment identifier, e.g., `A2a`. Used to group zones by segment.

---

### `event_a`
The first event in the pair being compared in a shared segment. This is typically the earlier or slower-starting event. Metrics like cp_km, zone_start_km_a, and zone_end_km_a are measured relative to this event’s course. In A2a, event_a = 10k means the 10K runners are used to anchor the segment, and all zone distances are aligned to the 10K course.

---

### `event_b`
The second event in the comparison, typically the later or faster-moving one (e.g., Half). This is the event whose participants may overtake runners from event_a in shared segments. Metrics like zone_start_km_b and zone_end_km_b are measured on this event’s course. In A2a, event_b = half means Half Marathon runners are compared to 10K runners for interactions during overlap in the shared course section.

---
### `zone_index`
The index of the zone within the segment, starting at 0 and increasing with each additional CP. For example, A2a has 5 zones, numbered 0 through 4.

---

### `cp_km`
The kilometer mark on Event A’s course is where an interaction zone begins. It is not a measure of overtaking, speed, or dominance. It is a spatial anchor that answers the question: _“Where on Event A’s course does this interaction zone start?”_

**Key clarifications:**
- `cp_km` always refers to Event A’s distance scale, regardless of which event is faster or doing the overtaking.
- It is effectively equivalent to zone_start_km_a.
- The value represents the entry point into the zone, not the midpoint, and not a normalized percentage.
- All zone boundaries and metrics are evaluated after this point.

This design allows all interaction zones to be described in a single, consistent spatial reference frame, even when:
- Event B has a different start time,
- Event B has covered a very different absolute distance,
- Event B is the primary overtaker.

**Examples**
- A2a (10K vs Half)
   - `cp_km` = 1.33
   - The first interaction zone begins at 1.33 km on the 10K and Half course, as both events started from the same starting point and followed the same course from 0.00 km to 1.33 km. 
- F1a (10K vs Half)
   - cp_km = 5.8
   - In this example, the 10k `zone_start_km_a` = 5.8, while the Half `zone_start_km_b` ≈ 2.7
- This indicates the zone begins when 10K runners are at 5.8 km of their course, which is different from the Half runners' course, who are only at ~2.7 km
- The two values are intentionally (based on course design) different.

**Important distinction**
`cp_km` describes where the interaction occurs, not who is overtaking whom. Overtaking dynamics are captured separately by:
	•	`overtaking_a`
	•	`overtaking_b`
	•	`copresence_*`
	•	`unique_encounters`

This separation ensures that spatial structure (zones) and interaction dynamics (flow) remain analytically distinct.

---

### `zone_start_km_a` / `zone_end_km_a`

Start and end of the zone on the course (in kilometers) for event A (e.g., 10K). These define the physical boundaries for analysis for runners from event A. 

The values represent _actual distance_ along the event A course (not a normalized or shared scale) and indicate where the interaction zone begins and ends for event A participants based on their own course progression.

---

### `zone_start_km_b` / `zone_end_km_b`

Start and end of the zone on the course (in kilometers) for event B (e.g., Half). These define the physical boundaries for analysis for runners from event B. While the zones typically align spatially with those of event A in shared segments, the distances are measured along event B’s own course and reflect its unique start point and progression.

---

### `overtaking_a` / `overtaking_b`

**Definition:**  
The number of *distinct runners* from the opposing event who were overtaken by runners from this event within the zone.

**Interpretation:**
- `overtaking_a = 0` in all A2a zones: No 10K runners (_event_a_) passed Half (_event_b_) runners.
- `overtaking_b` increases with zone_index as Half runners catch and pass 10K runners who started earlier.

**Example (A2a):**  
At `zone_index = 3`, `overtaking_b = 31` means **31 unique 10K runners** were passed by Half runners **in this 100–150m zone**.

*Note:* This does not tell us how many B runners did the overtaking—just the number of unique A runners who were passed. This is a future feature request for Flow analysis.

---

### `copresence_a` / `copresence_b`

**Definition:**  
The number of runners from each event who were in the zone at the same time as runners from the *other* event, but not necessarily involved in overtaking. Copresence is determined based on a minimum **dwell time** threshold—runners must be in proximity for a sufficient duration to qualify. This helps distinguish sustained co-location from brief or passing overlaps.

**Interpretation:**  
This metric measures how many runners were co-located in time and space with runners from the other event. A runner who quickly overtakes another (_not meeting the dwell time threshold_) without remaining nearby may not count toward copresence.

**Example (A2a):**  
At `zone_index = 3`,  
- `copresence_b = 2`: 2 Half runners were near 10K runners (they may or may not have overtaken them).  
- `copresence_a = 1`: 1 10K runner was overlapped by Half runners but not necessarily overtaken.

**Note:**  
Copresence may be 0 even when overtaking is > 0. This happens in sparse zones or when fast runners pass quickly through the zone without sustained interaction.

---

### `unique_encounters`

**Definition:**  
The number of unique A–B runner *pairs* that interacted in the zone, either through overtaking or co-presence. Each pair consists of one runner from event A and one from event B who share space in the zone according to time-based proximity criteria. This metric represents distinct cross-event runner combinations (e.g., A3 with B2), where interaction could mean:
- B overtook A (or vice versa), or
- A and B were in the zone at the same time long enough to be considered co-present.

Each qualifying A–B pair counts as **one encounter**, regardless of how long they were near each other or whether overtaking occurred. Example Table (A2a, zone_index = 0) **5 unique encounters** are recorded—one for each A–B pair. Even though only one B runner is involved (B1), each distinct interaction with an A runner counts individually:

| Encounter     | Counted? |
|---------------|----------|
| B1 → A1       | Y       |
| B1 → A2       | Y       |
| B1 → A3       | Y       |
| B1 → A4       | Y       |
| B1 → A5       | Y       |

---

### `participants_involved`

**Definition:**  

Total number of *individual* runners from either event involved in any cross-event interaction within the zone. This includes:
- Runners who overtook others
- Runners who were overtaken
- Runners who were co-present (in the same zone at the same time)

**Calculation:**
After the recent fix (vectorized path + binned path parity), this field now uses the _full participant_ sets tracked in memory:

```python
participants_involved = len(
    set(a_bibs_overtakes + a_bibs_overtaken + a_bibs_copresence)
    .union(
         b_bibs_overtakes + b_bibs_overtaken + b_bibs_copresence
    )
)
```

This ensures all unique bibs from both events are included — whether they initiated or received interaction. This value represents the total number of unique runners (from A and B) that interacted within the zone. It offers a realistic view of runner exposure and density during multi-event convergence. Example (A2a, zone_index = 3):
- overtaking_b = 31 → 31 A runners passed by B
- copresence_a = 1, copresence_b = 2
- → Participants:
   - A runners: 31 overtaken + 1 co-present = 32
   - B runners: 0 overtaking + 2 co-present = 2 
   - A + B runners = participants_involved = 34

Note:
- This field does not double-count participants.
- It uses set() operations to ensure each bib is only counted once, even if a runner participated in multiple types of interactions.

---

## Summary Takeaways

- A2a shows Half (B) runners catching and overtaking 10K (A) runners over 400m.
- No A runners overtook B runners, as expected due to start delay and pace differences.
- `flow.csv` reports only the worst zone per segment; `flow_zones` allows full analysis.
- `participants_involved` and `unique_encounters` reflect the intensity of interaction in the zone.
- These metrics support evaluating congestion, runner experience, and race dynamics.

## How Zones Are Reported in Flow.csv and the Flow UI

Each segment in `flow.csv` and the Flow UI represents a summary of multiple underlying zones identified within that segment. The selected zone is meant to reflect the highest-congestion or highest-interaction portion of the segment — often referred to as the "worst" zone.

### Selection Logic

The selection process is as follows:

1. **Primary Criterion – Maximum Overtaking**  
   The zone with the highest value of `overtaking_a` or `overtaking_b` (depending on which event is overtaking) is chosen.

2. **Tie-Breaker – Maximum Copresence**  
   If multiple zones have the same highest overtaking count, the zone with the higher combined copresence (`copresence_a + copresence_b`) is selected.

3. **Result**  
   The chosen zone becomes the one reported in:
   - The corresponding row in `flow.csv`
   - The Flow UI
   - Summary metrics in downstream reports

### Example (A2a)

For segment `A2a`, five zones were detected. Here's a summary:

| zone_index | overtaking_b | copresence_b |
|------------|---------------|---------------|
| 0          | 5             | 0             |
| 1          | 14            | 0             |
| 2          | 26            | 2             |
| 3          | 31            | 15            |
| 4          | 27            | 12            |

- The highest overtaking_b value is `31` at `zone_index = 3`.
- Therefore, this zone is selected and its metrics are reported in `flow.csv`.

If there had been a tie in overtaking_b (e.g., two zones with 31), then the zone with higher copresence would be selected.

### Future Improvements
To improve user interpretability, a future enhancement could display in the runflow user interface:
- The selected zone index (e.g., `3`)
- The total number of zones in the segment (e.g., `5`)
- As a string like: **"3/5 (worst zone)"**
- Add `num_overtakers_b` to measure how many B runners did the overtaking.
- Add `dwell_time_*` to support experience-focused metrics.
- In reports/UI, show `zone_index/total_zones` to help locate interaction zones.

---

## Sources Referenced

- `flow_zones_202601061517.csv` (Sunday zone metrics)
- `data_flow.csv` (source input segments)
- `Flow.csv` (aggregated report of worst zone per segment)
- `flow_expected_results.md` (historical field guide)




