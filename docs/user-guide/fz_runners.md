# Flow Zone Runners Data Guide
**Version:** {tbd}

**Date:** 2026-01-06

## Overview
`fz_runners.parquet` contains runner-level records that power the flow zone metrics reported in `flow_zones.parquet`. Each row represents a runner participating in a specific flow zone, enabling analyst-level inspection of who was involved in overtaking or co-presence within a zone.

## Scope and Purpose

The `fz_runners.parquet` artifact captures **who** was involved in cross-event zone interactions — not **how many interactions** they had.

Each row represents a **unique runner-role participation**:
- One row for each runner involved in a zone (e.g., as overtaking, overtaken, or co-present)
- Tied to `seg_id`, `zone_index`, `runner_id`, and `role`
- Exported per runner per role per zone, not per interaction

This allows:
- Drill-downs by runner (e.g., was runner 1529 overtaken? where?)
- Joins with `fz.parquet` zone summaries
- Lightweight, audit-free exports that run on every flow analysis

**Importantly:**
- This file does **not** capture how many passes or encounters a runner was involved in.
- It does not include pairwise data (who passed whom).
- It does not report multiple passes by the same runner.
- It omits pass flags, time-in-zone, and other audit-level detail.

### Why this matters — A3a, Zone 8 Example

In zone A3a / index 8:
- `fz_runners.parquet` reports 54 runners from side B (`side = b`) in the `overtaking` role.
- But `fz.parquet` for the same zone shows `overtaking_b = 188`.

This is **not a mismatch** — it's by design:
- The 54 runners **initiated** at least one overtake.
- The 188 is the **total number of overtakes**, which can include multiple overtake per runner.
- `fz_runners` shows *who was involved*, not *how often*.

This is a crucial distinction to prevent row explosion and ensure `fz_runners` remains a compact, fast, always-available artifact. For full pass-level details, use `audit.parquet` that contains detailed interaction data with pairwise overlaps and pass flags. This design was chosen:
- fz_runners is optimized for who was involved, not how many times.
- It avoids audit-like row explosion and focuses on per-runner presence and roles.
- This enables efficient queries like: “Which runners were overtaken?” or “Who had copresence in this zone?”

### Relationship to `flow_zones.parquet`
Use the composite key of `seg_id` + `zone_index` to map runner rows back to their parent zone metrics.

```text
fz_runners.seg_id   = flow_zones.seg_id
fz_runners.zone_index = flow_zones.zone_index
```

### Version Notes
- Pass flags are **not included in v1** because they are only available via audit logic, which is intentionally excluded from v1 exports.

---

## Core Fields (Representative)
The runner-level export is designed to include only the minimum keys needed to join with `flow_zones.parquet`, plus runner identifiers and interaction attributes. The exact schema may expand over time, but typically includes:

- `seg_id`: Segment identifier (e.g., `A2a`).
- `zone_index`: 0-based index of the zone within the segment.
- `event`: Event label for the runner (e.g., `10k`, `half`).
- `runner_id`: Unique runner identifier (e.g., bib).
- Interaction descriptors that capture how the runner participated in the zone (e.g., overtaking vs. copresence).

---

## Example Join

```sql
SELECT
  z.seg_id,
  z.zone_index,
  z.overtaking_b,
  r.runner_id,
  r.event
FROM read_parquet('flow_zones.parquet') AS z
JOIN read_parquet('fz_runners.parquet') AS r
  ON z.seg_id = r.seg_id
 AND z.zone_index = r.zone_index
WHERE z.seg_id = 'A2a'
  AND z.zone_index = 3;
```

---

## Summary Takeaways
- Use `fz_runners.parquet` for runner-level investigation of specific zones.
- Join to `flow_zones.parquet` on `seg_id` + `zone_index` for full context.
- Pass flags are intentionally omitted from v1 exports due to audit-only availability.


## Sample Queries
These queries confirm that the runner-level table `fz_runners.parquet` properly aggregates back to the zone-level metrics reported in `flow_zones.parquet` for a given segment — in this case, `seg_id = 'A2a'`.

---

### 1. Overtaking Counts

**Overtaking — Event A**

_Purpose:_ Returns the number of unique runners from event A who performed overtaking in each zone. This count should match the `overtaking_a` value in `flow_zones.parquet`.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS overtaking_a
FROM fz_runners
WHERE seg_id = 'A2a'
  AND role = 'overtaking'
  AND side = 'a'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```

**Overtaking — Event B**

_Purpose:_ Same as above, but for event B. Compares directly to `overtaking_b` in `flow_zones`.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS overtaking_b
FROM fz_runners
WHERE seg_id = 'A2a'
  AND role = 'overtaking'
  AND side = 'b'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```

---

## 2. Overtaken Counts

**Overtaken — Event A**

_Purpose:_ Counts how many **event A** runners were overtaken in each zone. Validates against `overtaken_a` from `flow_zones`.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS overtaken_a
FROM fz_runners
WHERE seg_id = 'A2a'
  AND role = 'overtaken'
  AND side = 'a'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```
 

**Overtaken — Event B**

_Purpose:_ Same logic, for event B runners who were overtaken.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS overtaken_b
FROM fz_runners
WHERE seg_id = 'A2a'
  AND role = 'overtaken'
  AND side = 'b'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```

---

## 3. Copresence Counts

**Copresence — Event A**

_Purpose:_ Counts unique runners from event A who were in copresence with others in the zone. Cross-check with `copresence_a` in `flow_zones`.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS copresence_a
FROM fz_runners
WHERE seg_id = 'A2a'
  AND role = 'copresent'
  AND side = 'a'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```

**Copresence — Event B**

_Purpose:_ Same as above for event B.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS copresence_b
FROM fz_runners
WHERE seg_id = 'A2a'
  AND role = 'copresent'
  AND side = 'b'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```

---

## 4. Participants Involved

**All Participants per Zone**

_Purpose:_ Returns the total number of **unique runners** per zone across all roles. This count must match `participants_involved` in `flow_zones` for that `zone_index`.

```sql
SELECT
    seg_id,
    zone_index,
    COUNT(DISTINCT runner_id) AS participants_involved
FROM fz_runners
WHERE seg_id = 'A2a'
GROUP BY seg_id, zone_index
ORDER BY zone_index;
```

---

## 5. Full Side-by-Side Summary Table

### 📌 One-table view of all metrics per zone
_Purpose:_ Consolidated result showing all role counts and the total participant count in one table, per `zone_index`. Use this as a **direct row-by-row comparison** with `flow_zones.parquet` to confirm traceability is correct.

```sql
SELECT
    zone_index,
    SUM(CASE WHEN role = 'overtaking' AND side = 'a' THEN 1 ELSE 0 END) AS overtaking_a,
    SUM(CASE WHEN role = 'overtaking' AND side = 'b' THEN 1 ELSE 0 END) AS overtaking_b,
    SUM(CASE WHEN role = 'overtaken'  AND side = 'a' THEN 1 ELSE 0 END) AS overtaken_a,
    SUM(CASE WHEN role = 'overtaken'  AND side = 'b' THEN 1 ELSE 0 END) AS overtaken_b,
    SUM(CASE WHEN role = 'copresent'  AND side = 'a' THEN 1 ELSE 0 END) AS copresence_a,
    SUM(CASE WHEN role = 'copresent'  AND side = 'b' THEN 1 ELSE 0 END) AS copresence_b,
    COUNT(DISTINCT runner_id) AS participants_involved
FROM fz_runners
WHERE seg_id = 'A2a'
GROUP BY zone_index
ORDER BY zone_index;
```

---

## Flow Zones with Zero Counts
If all interaction metrics for a `seg_id` and `zone_index` are 0 (overtaking_a, overtaking_b, overtaken_a, overtaken_b, copresence_a, copresence_b), the seg_id and zone_index will **not** be included in fz_runners.parquet. The system will INFO-level logging: when a zone is skipped due to zero counts, logs:
```text
   [fz_runners] Zone {seg_id} index={zone_index} skipped - zero counts 
   (no runner interactions: overtaking_a=0, overtaking_b=0, ...)
   [fz_runners] Zone {seg_id} index={zone_index} skipped - zero counts    (no runner interactions: overtaking_a=0, overtaking_b=0, ...)
```

Distinction: distinguishes between:
- Zones with zero counts (expected for empty zones) — logged at INFO
- Zones missing internal sets (potential issue) — logged at DEBUG

Behavior:
- Zones with zero counts are logged at INFO so they’re visible in normal logs.
- This helps identify zones that exist but have no runner interactions.
- The logging happens during the export process, so you’ll see which zones are skipped and why.

To verify which seg_ids have zero counts, run the following SQL on the fz.parquet:

```sql
SELECT *
FROM sun_fz
WHERE 
  overtaking_a = 0 AND overtaking_b = 0 AND
  overtaken_a = 0 AND overtaken_b = 0 AND
  copresence_a = 0 AND copresence_b = 0 AND
  participants_involved = 0 AND
  multi_category_runners = 0;
```

## Conclusion
Using these queries return values that match `flow_zones`:
- Issue #627 is fully validated.
- You have proven that `fz_runners` correctly decomposes and reconstructs all metrics in `flow_zones`.
- You can now reliably **trace the "who" behind every metric**, enabling future experience scoring and runner-centric analysis.

These queries can be adapted for other segments (just change `seg_id`) and should be included in any regression QA suite for flow traceability.
