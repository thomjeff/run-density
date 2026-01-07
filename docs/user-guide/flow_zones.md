# Flow Zones Data Guide
**Version:** {tbd}

**Date:** 2026-01-06


## Overview
This document provides a detailed explanation of each field in the `flow_zones` dataset, with narrative examples using real data from the A2a segment (Sunday event). It is intended for data analysts and reviewers interpreting flow dynamics in multi-convergence-point (multi‑CP) race segments. Each row in `flow_zones` represents a flow analysis zone derived from convergence points (CPs) between two events (e.g., 10K and Half-Marathon) on the same segment. Zones are ~100–150m in length and are used to detect interactions such as overtaking and co-presence.

## Flow Zone Metrics: Direct vs. Binned Execution Paths

The flow zone computation engine supports two different execution paths depending on the size and complexity of the zone:

### `calculate_zone_metrics_vectorized_direct`
This path is used when the zone size is small enough to safely process all pairwise overlaps in memory.

- **Trigger:** Zones that fall below defined thresholds for size and overlap count.
- **Behavior:** Processes all overlaps in a fully vectorized manner.
- **Pros:** Fast, precise, and accumulates full runner interaction sets (e.g., `_a_bibs_overtaken`).
- **Use Case:** Small segments like A2a or A3a.

### `calculate_zone_metrics_vectorized_binned`
This path is used for larger zones with more runners or denser overlap windows.

- **Trigger:** Exceeds internal thresholds on runner count or interaction density.
- **Behavior:** Splits the zone into smaller time/distance bins, processes each bin individually, and aggregates the results.
- **Pros:** Scalable and avoids memory issues.
- **Caveat (now fixed):** Previously did **not** return internal runner sets, which meant runner-level exports like `fz_runners.parquet` lacked data for zones processed this way.

> ✅ As of 2026-01, both paths now return full internal runner sets to support downstream exports like `fz_runners.parquet`.

### Why Two Paths?
This dual-path architecture balances:
- **Performance** for large events with thousands of runners.
- **Precision** for zones where full in-memory computation is feasible.

This design allows the flow zone engine to scale across a wide range of course types, event sizes, and concurrency levels.

## Flow Zome Example: A2a Segment
A2a spans Queen/Regent to WSB midpoint. It includes 5 zones created during analysis between convergence points at 1.33km and 1.73km.

![A2a Flow Visualization](https://github.com/thomjeff/run-density/blob/main/docs/user-guide/a2segment.png?raw=true) 


**Event Start Times and Participant Counts**

This document is based on two race events involved in an analysis that started at different times with the following runner counts:
| Event | Start Time | Runners | 
|-------|------------|---------|
|10k|07:20 (440)|618|
|half|07:40 (460)|912|

This 20-minute gap is essential context for understanding overtaking patterns — the Half field begins behind but at a faster pace.

Runners from both events shared segment A2a.


## A2a Flow Zone Metrics:
While there are 200+ flow zones across 20+ segments, we are using A2a to provide the reader an overview of `{day}_fz.parquet` (renamed from `flow_zones.parquet` in Issue #627). The file contains the following fields with data for A2a:


| seg_id   | event_a   | event_b   |   zone_index |   cp_km | cp_type   | zone_source   |   zone_start_km_a |   zone_end_km_a |   zone_start_km_b |   zone_end_km_b |   overtaking_a |   overtaking_b |   overtaken_a |   overtaken_b |   copresence_a |   copresence_b |   unique_encounters |   participants_involved |   multi_category_runners |
|:---------|:----------|:----------|-------------:|--------:|:----------|:--------------|------------------:|----------------:|------------------:|----------------:|---------------:|---------------:|--------------:|--------------:|---------------:|---------------:|--------------------:|------------------------:|-------------------------:|
| A2a      | 10k       | half      |            0 |    1.33 | true_pass | true_pass     |              1.28 |            1.38 |              1.28 |            1.38 |              0 |              5 |             1 |             0 |              0 |              0 |                   5 |                       6 |                        0 |
| A2a      | 10k       | half      |            1 |    1.43 | true_pass | true_pass     |              1.38 |            1.48 |              1.38 |            1.48 |              0 |             14 |             1 |             0 |              0 |              0 |                  14 |                      15 |                        0 |
| A2a      | 10k       | half      |            2 |    1.53 | true_pass | true_pass     |              1.48 |            1.58 |              1.48 |            1.58 |              0 |             26 |             1 |             0 |              0 |              0 |                  26 |                      27 |                        0 |
| A2a      | 10k       | half      |            3 |    1.63 | true_pass | true_pass     |              1.58 |            1.68 |              1.58 |            1.68 |              0 |             31 |             1 |             0 |              1 |              2 |                  33 |                      34 |                        1 |
| A2a      | 10k       | half      |            4 |    1.73 | true_pass | true_pass     |              1.68 |            1.78 |              1.68 |            1.78 |              0 |             27 |             1 |             0 |              1 |             15 |                  42 |                      43 |                        1 |


---

## Field Definitions
The following are field definitions with examples, where appropriate, to aid in understanding:

### `seg_id`
The segment identifier, e.g., `A2a`. Used to group zones by segment. Segment identifiers are provided in `/data/segments.csv` provided as part of the analysis. 

---

### `event_a`
The first event in the pair being compared in a shared segment. This is typically the earlier or slower-starting event. Metrics like cp_km, zone_start_km_a, and zone_end_km_a are measured relative to this event’s course. In A2a, event_a = 10k means the 10K runners are used to anchor the segment, and all zone distances are aligned to the 10K course.

---

### `event_b`
The second event in the comparison is typically the later or faster-moving one (e.g., Half). This is the event whose participants may overtake runners from event_a in shared segments. Metrics like zone_start_km_b and zone_end_km_b are measured on this event’s course. In A2a, event_b = half means that Half Marathon runners are compared to 10K runners for interactions during the overlap on the shared course section.

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

### `overtaken_a`

**Definition:**  
The number of *distinct runners from event A* who were overtaken by runners from event B within the zone.

**Interpretation:**  
Each runner from event A is counted once if they were passed by at least one runner from event B in this zone, regardless of how many times or by how many runners they were overtaken.

This field represents the *receiving side* of overtaking interactions for event A.

**Example:**  
If 5 different 10K runners are passed by Half Marathon runners in a zone, then: `overtaken_a = 5`

**Notes:**
- `overtaking_*` and `overtaken_*` are complementary but not symmetric counts.
- A single runner may appear in multiple interaction categories (overtaking, overtaken, copresence), but each field counts *distinct runners* within that category only.
- These fields are used together with `participants_involved` and `multi_category_runners` to describe interaction dynamics within a zone fully.

---

### `overtaken_b`

**Definition:**  
The number of *distinct runners from event B* who were overtaken by runners from event A within the zone.

**Interpretation:**  
Each runner from event B is counted once if they were passed by at least one runner from event A in this zone.

This field represents the *receiving side* of overtaking interactions for event B.

**Example:**  
If 2 Half Marathon runners are passed by 10K runners in a zone, then: `overtaken_b = 2`

**Notes:**
- `overtaking_*` and `overtaken_*` are complementary but not symmetric counts.
- A single runner may appear in multiple interaction categories (overtaking, overtaken, copresence), but each field counts *distinct runners* within that category only.
- These fields are used together with `participants_involved` and `multi_category_runners` to describe interaction dynamics within a zone fully.

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

Each qualifying A–B pair counts as **one encounter**, regardless of how long they were near each other or whether overtaking occurred.

#### Example Table (A2a, zone_index = 0) 
**5 unique encounters** are recorded—one for each A–B pair. Even though only one B runner is involved (B1), each distinct interaction with an A runner counts individually:

| Encounter     | Counted? | Cumulative Count | 
|---------------|----------|------------------|
| B1 → A1       | Y        | 1                |
| B1 → A2       | Y        | 2                |
| B1 → A3       | Y        | 3                |
| B1 → A4       | Y        | 4                |
| B1 → A5       | Y        | 5                |

---

#### Example: I1, Zone 7 (event_a = Half, event_b = Full)

| Metric               | Value   |
|----------------------|---------|
| unique_encounters    | 12,974  |
| overtaking_a         | 0       |
| overtaking_b         | 0       |
| overtaken_a          | 0       |
| overtaken_b          | 0       |
| copresence_a         | 0       |
| copresence_b         | 0       |

In this case, **12,974 unique A–B pairs** were detected as being in proximity within the zone — yet none met the stricter rules to qualify as overtaking or copresent.

This can happen when:
- Runners from both events overlap briefly within bins but not long enough for classification.
- Their time offsets don't allow for sustained zone overlap.
- They were detected in the same bin once, which qualifies as an encounter but not an interaction.

This illustrates the distinction between *potential interaction* (`unique_encounters`) and *confirmed interaction* (the other metrics).

**Usage tip:** `unique_encounters` is excellent for identifying zones of *latent crowding risk* — even when the zone appears "quiet" by other metrics.

---

### `participants_involved`

**Definition:**  

Total number of *individual* runners from either event involved in any cross-event interaction within the zone. This includes:
- Runners who overtook others
- Runners who were overtaken
- Runners who were co-present (in the same zone at the same time)

**Calculation:**
Participants are computed by tracking full sets of bibs in memory for each interaction category. Overlapping runners (those involved in multiple categories) are deduplicated using set logic. 
```markdown
participants_involved = len(
    set(a_bibs_overtakes + a_bibs_overtaken + a_bibs_copresence)
    .union(
         b_bibs_overtakes + b_bibs_overtaken + b_bibs_copresence
    )
)
```

This ensures all unique bibs from both events are included — whether they initiated or received interaction. This value represents the total number of unique runners (from A and B) that interacted within the zone. It offers a realistic view of runner exposure and density during multi-event convergence. 

For exported data in `flow_zone.parquet`, the following formula validates the count:

```markdown
participants_involved =
    overtaking_a
  + overtaking_b
  + overtaken_a
  + overtaken_b
  + copresence_a
  + copresence_b
  - multi_category_runners
```

where _multi_category_runners_ is the number of runners involved in multiple interaction types and required for deduplication overlap in the summation.

Example (A2a, zone_index = 3):
```markdown
overtaking_a = 0
overtaking_b = 31
overtaken_a = 1
overtaken_b = 0
copresence_a = 1
copresence_b = 2
multi_category_runners = 1 (see below)
#count:
→ sum_of_counts = 0 + 31 + 1 + 0 + 1 + 2 = 35
#calculate multi-category:
→ participants_involved = sum_of_counts = multi_category_runners 
→ participants_involved = 35 - 1 = 34
```

Key Notes:
- multi_category_runners is a new field that enables validation by capturing overlaps.
- This calculation is now accurate for both vectorized direct and binned execution paths.
- The field is designed for accurate impact measurement across event boundaries — useful for analyzing congestion and runner experience.

Note:
- This field does not double-count participants.
- It uses set() operations to ensure each bib is only counted once, even if a runner participated in multiple types of interactions.

---

### `multi_category_runners` 

**Definition:**  
The number of unique runners who participated in more than one interaction role within the same zone. Interaction roles include:
- Overtaking (initiated a pass)
- Overtaken (was passed by another runner)
- Copresent (shared the zone with another runner without a pass)

These roles are captured in fz_runners.parquet as role values. If a runner appears in multiple roles within a zone (e.g., both overtaken and copresent), they are:
- Counted multiple times in the individual role totals (e.g., overtaken_a, copresence_a),
- But only once in participants_involved.

`multi_category_runners` quantifies this overlap, allowing accurate reconstruction of unique participant counts using the equation:

```text
participants_involved < overtaking_a + overtaking_b + overtaken_a + overtaken_b + copresence_a + copresence_b
```

and to make the `participants_involved` calculation auditable.

**Calculation Conceptually:**
```python
multi_category_runners = (
    total category counts
    − number of unique runners across all categories
)
```

or equivalently:
```text
participants_involved = sum_of_counts − multi_category_runners
```

Example (A2a, zone_index = 3):
- One 10K runner was both:
   - overtaken by Half runners, and
   - co-present in the zone
- That runner appears in multiple category counts but should only be counted once as a participant

Result is `multi_category_runners` = 1 and ensures participants_involved reflects unique runners only

```text
overtaking_a = 0
overtaking_b = 31
overtaken_a = 1
overtaken_b = 0
copresence_a = 1
copresence_b = 2
sum_of_counts = 35
participants_involved = 34
multi_category_runners = 1
```

This means one runner appears in two roles (overtaken + copresent).

```sql
SELECT
  seg_id,
  zone_index,
  runner_id,
  COUNT(DISTINCT role) AS role_count,
  ARRAY_AGG(role) AS roles
FROM
  sun_fz_runners
WHERE
  seg_id = 'A2a'
  AND zone_index = 3
GROUP BY
  seg_id,
  zone_index,
  runner_id
HAVING
  COUNT(DISTINCT role) > 1;
```

Result:

| seg_id | zone_index | runner_id | role_count | roles |
|---|---|---|---|---|
| A2a | 3 | 1529 | 2 | overtaken, copresent | 

**Interpretation:**
- A multi_category_runners value of 0 means all runners were only involved in a single interaction role.
- A value >0 indicates more complex interactions — e.g., runners who were overtaken but also remained near other runners (copresence), or overtook multiple people and lingered.

This field enables accurate validation, precise analytics, and trustworthy interpretation of runner exposure in multi-event flow zones.

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

## Related Artifacts

### `{day}_fz_runners.parquet` (Issue #627)

The `{day}_fz_runners.parquet` file (e.g., `sat_fz_runners.parquet`, `sun_fz_runners.parquet`) provides runner-level participation data for flow zones. This file contains one row per (runner, zone, role) combination, enabling:

- **Traceability**: Identify which specific runners were involved in each zone
- **Runner-centric analytics**: Build experience scores, density exposure metrics
- **Drill-downs**: Analyze who was overtaken, where, and how many times

**Schema:**
- `seg_id`: Segment ID (e.g., A2a)
- `zone_index`: Index of the zone within the segment
- `runner_id`: Unique runner ID (bib number)
- `event`: Event name (e.g., "10k", "half")
- `role`: One of "overtaking", "overtaken", "copresent"
- `side`: "a" or "b" (event A or event B)

**Key Notes:**
- A single runner may appear multiple times in a zone (e.g., both "overtaken" and "copresent")
- This file is derived from zone metrics only (not audit logic) and is always exported alongside `{day}_fz.parquet`
- Pass flags (`pass_flag_raw`, `pass_flag_strict`) are not included in v1 as they require audit logic
- Files are prefixed with day (e.g., `sat_`, `sun_`) for multi-day analysis

**Relationship to `{day}_fz.parquet`:**
- Join using `seg_id` + `zone_index` to link runner participation to zone metrics
- Use `runner_id` to trace individual runner experiences across zones
- Aggregate by `role` to understand interaction patterns

---

## Sources Referenced

- `flow_zones_202601061517.csv` (Sunday zone metrics)
- `data_flow.csv` (source input segments)
- `Flow.csv` (aggregated report of worst zone per segment)
- `flow_expected_results.md` (historical field guide)




