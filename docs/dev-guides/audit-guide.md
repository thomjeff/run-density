# Flow Audit Guide

## Overview

The Flow Audit feature provides detailed runner-level pairwise overlap and overtaking data for debugging, validation, and deep analysis of flow results. Audit data is stored in Parquet format (one file per day) for efficient querying and analysis.

**Related Issues**: #607 (Parquet format), #552 (Overtaking count logic)

## File Structure

### Location

Audit files are generated in the analysis output directory:

```
{run_id}/
  {day}/
    audit/
      audit_{day}.parquet    # e.g., audit_sat.parquet, audit_sun.parquet
```

### File Format

- **Format**: Parquet (columnar storage, efficient for analytical queries)
- **Size**: Typically 15-25 MB per day (vs. ~552 MB for previous CSV shard approach)
- **Tooling**: Queryable via DuckDB, Pandas, DBeaver, or any Parquet-compatible tool

## Data Schema

### Core Columns

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | string | Analysis run identifier |
| `executed_at_utc` | string | Timestamp when audit was generated |
| `seg_id` | string | Segment ID (e.g., 'L1b', 'J2', 'B3') |
| `segment_label` | string | Human-readable segment label |
| `flow_type` | string | Flow type: 'overtake', 'merge', 'counterflow', 'parallel', 'none' |
| `event_a` | string | First event name (e.g., '10k', 'full', 'half') |
| `event_b` | string | Second event name |
| `pair_key` | string | Composite key: `{runner_id_a}-{runner_id_b}` |

### Runner A Data

| Column | Type | Description |
|--------|------|-------------|
| `runner_id_a` | string | Runner ID for event A |
| `entry_km_a` | float | Entry distance (km) for runner A (full segment) |
| `exit_km_a` | float | Exit distance (km) for runner A (full segment) |
| `entry_time_sec_a` | float | Entry time (seconds from midnight) for runner A |
| `exit_time_sec_a` | float | Exit time (seconds from midnight) for runner A |

### Runner B Data

| Column | Type | Description |
|--------|------|-------------|
| `runner_id_b` | string | Runner ID for event B |
| `entry_km_b` | float | Entry distance (km) for runner B (full segment) |
| `exit_km_b` | float | Exit distance (km) for runner B (full segment) |
| `entry_time_sec_b` | float | Entry time (seconds from midnight) for runner B |
| `exit_time_sec_b` | float | Exit time (seconds from midnight) for runner B |

### Overlap Data

| Column | Type | Description |
|--------|------|-------------|
| `overlap_start_time_sec` | float | Start time of temporal overlap (seconds) |
| `overlap_end_time_sec` | float | End time of temporal overlap (seconds) |
| `overlap_dwell_sec` | float | Duration of overlap (seconds) |
| `entry_delta_sec` | float | `entry_time_sec_a - entry_time_sec_b` (positive = A entered after B) |
| `exit_delta_sec` | float | `exit_time_sec_a - exit_time_sec_b` (positive = A exited after B) |
| `rel_order_entry` | int | Relative order at entry: -1 (A before B), 0 (same), 1 (A after B) |
| `rel_order_exit` | int | Relative order at exit: -1 (A before B), 0 (same), 1 (A after B) |
| `order_flip_bool` | bool | True if relative order changed (indicates overtaking) |
| `directional_gain_sec` | float | Time gained by faster runner: `exit_delta - entry_delta` |

### Pass Detection Flags

| Column | Type | Description |
|--------|------|-------------|
| `pass_flag_raw` | bool | True if order_flip occurred (basic overtaking detection) |
| `pass_flag_strict` | bool | True if strict pass criteria met: order_flip AND dwell >= 5s AND directional_gain >= 2s |
| `reason_code` | string | Reason code for pass detection (e.g., 'raw_pass', 'strict_pass', 'no_pass') |

### Conflict Zone Data (Issue #607)

| Column | Type | Description |
|--------|------|-------------|
| `convergence_zone_start` | float | Normalized convergence zone start (0.0-1.0) |
| `convergence_zone_end` | float | Normalized convergence zone end (0.0-1.0) |
| `zone_width_m` | float | Conflict zone width in meters |
| `conflict_zone_a_start_km` | float | Conflict zone start for event A (km) |
| `conflict_zone_a_end_km` | float | Conflict zone end for event A (km) |
| `conflict_zone_b_start_km` | float | Conflict zone start for event B (km) |
| `conflict_zone_b_end_km` | float | Conflict zone end for event B (km) |
| `in_conflict_zone` | bool | **Approximate** flag indicating if overlap is within conflict zone (see Known Limitations) |

### Metadata

| Column | Type | Description |
|--------|------|-------------|
| `binning_applied` | bool | Whether binning was used in analysis |
| `binning_mode` | string | Binning mode: 'time', 'distance', or 'none' |

## Query Examples

### Setup

**DBeaver Setup**:
1. Create new connection → DuckDB
2. Database: (leave empty for in-memory, or specify a path)
3. Use SQL Editor to run queries

**Important**: Update the file path in `read_parquet()` to your actual file path:
```sql
read_parquet('/path/to/runflow/{run_id}/{day}/audit/audit_{day}.parquet')
```

---

## 1. Basic Overtaking Counts

### Query 1.1: Count Unique Overtakers (Overtaking_B)

**Use Case**: Count how many unique runners from event B overtook runners from event A in a segment.

```sql
SELECT
    COUNT(DISTINCT runner_id_b) AS overtaking_b_unique,
    COUNT(DISTINCT runner_id_a) AS overtaken_a_unique,
    COUNT(*) AS total_overtake_events
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b'
  AND entry_delta_sec < 0       -- B entered after A
  AND exit_delta_sec > 0        -- B exited before A (B passed A)
  AND event_a = '10k'
  AND event_b = 'full';
```

**Explanation**:
- `entry_delta_sec < 0`: Runner B entered the segment after runner A
- `exit_delta_sec > 0`: Runner B exited the segment before runner A
- Together, these conditions indicate B overtook A

**Expected Result**: Returns unique count of overtakers and overtaken runners, plus total event count.

---

### Query 1.2: Count Unique Overtakers (Overtaking_A)

**Use Case**: Count how many unique runners from event A overtook runners from event B.

```sql
SELECT
    COUNT(DISTINCT runner_id_a) AS overtaking_a_unique,
    COUNT(DISTINCT runner_id_b) AS overtaken_b_unique,
    COUNT(*) AS total_overtake_events
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b'
  AND entry_delta_sec > 0       -- A entered after B
  AND exit_delta_sec < 0        -- A exited before B (A passed B)
  AND event_a = '10k'
  AND event_b = 'full';
```

---

## 2. Conflict Zone Filtering (Issue #607)

### Query 2.1: Filtered View (Conflict Zone Only)

**Use Case**: Get a filtered subset of overlaps that occurred within the conflict zone. **Note**: This is an approximation and may not exactly match Flow.csv counts.

```sql
SELECT
    COUNT(DISTINCT runner_id_b) AS overtaking_b_unique,
    COUNT(DISTINCT runner_id_a) AS overtaken_a_unique
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b'
  AND entry_delta_sec < 0       -- B entered after A
  AND exit_delta_sec > 0        -- B exited before A
  AND in_conflict_zone = True   -- Filtered to conflict zone overlaps (approximate)
  AND event_a = '10k'
  AND event_b = 'full';
```

**Known Limitation**: The `in_conflict_zone` flag provides a best-effort approximation. For exact validation, use Flow.csv as the authoritative source.

**Example Discrepancy**:
- Flow.csv (L1b): `overtaking_b = 206` (authoritative)
- Audit (filtered): `~297` (approximate, ~44% higher)

---

### Query 2.2: Inspect Conflict Zone Boundaries

**Use Case**: View the conflict zone boundaries for a segment.

```sql
SELECT DISTINCT
    seg_id,
    conflict_zone_a_start_km,
    conflict_zone_a_end_km,
    conflict_zone_b_start_km,
    conflict_zone_b_end_km,
    zone_width_m
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b';
```

---

## 3. Detailed Overtaking Analysis

### Query 3.1: Overtaker Summary (Who Overtook How Many)

**Use Case**: For each overtaker, count how many unique runners they overtook and get statistics.

```sql
SELECT 
    runner_id_b AS overtaker,
    COUNT(DISTINCT runner_id_a) AS unique_runners_overtaken,
    COUNT(*) AS total_overtake_events,
    AVG(overlap_dwell_sec) AS avg_dwell_sec,
    MIN(overlap_dwell_sec) AS min_dwell_sec,
    MAX(overlap_dwell_sec) AS max_dwell_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'J2'
  AND entry_delta_sec < 0       -- b entered after a
  AND exit_delta_sec > 0        -- b exited before a (b passed a)
GROUP BY runner_id_b
ORDER BY unique_runners_overtaken DESC;
```

**Example Use Case**: "Which runners did the 520 overtaking_b runners overtake?" (for segment B3)

---

### Query 3.2: Detailed Overtaking List

**Use Case**: Get a detailed list of all overtake events with timing information.

```sql
SELECT 
    runner_id_b AS overtaker,
    runner_id_a AS overtaken,
    overlap_dwell_sec,
    entry_time_sec_a,
    exit_time_sec_a,
    entry_time_sec_b,
    exit_time_sec_b,
    entry_delta_sec,
    exit_delta_sec,
    pass_flag_raw,
    pass_flag_strict
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'J2'
  AND entry_delta_sec < 0       -- b entered after a
  AND exit_delta_sec > 0        -- b exited before a (b passed a)
ORDER BY runner_id_b, runner_id_a;
```

---

### Query 3.3: Grouped Overtaking (Count per Pair)

**Use Case**: Count how many times each overtaker/overtaken pair occurred.

```sql
SELECT 
    runner_id_b AS overtaker,
    runner_id_a AS overtaken,
    COUNT(*) AS overtake_count,
    AVG(overlap_dwell_sec) AS avg_dwell_sec,
    MIN(overlap_dwell_sec) AS min_dwell_sec,
    MAX(overlap_dwell_sec) AS max_dwell_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'J2'
  AND entry_delta_sec < 0       -- b entered after a
  AND exit_delta_sec > 0        -- b exited before a (b passed a)
GROUP BY runner_id_b, runner_id_a
ORDER BY runner_id_b, runner_id_a;
```

---

## 4. Bidirectional Overtaking Analysis

### Query 4.1: Combined View (All Overtaking Directions)

**Use Case**: View all overtake events with direction indicator (A overtakes B or B overtakes A).

```sql
SELECT 
    CASE 
        WHEN entry_delta_sec > 0 AND exit_delta_sec < 0 THEN 'A overtakes B'
        WHEN entry_delta_sec < 0 AND exit_delta_sec > 0 THEN 'B overtakes A'
        ELSE 'No overtake'
    END AS overtake_direction,
    runner_id_a,
    runner_id_b,
    overlap_dwell_sec,
    entry_delta_sec,
    exit_delta_sec,
    pass_flag_raw,
    pass_flag_strict
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'J2'
  AND (
    (entry_delta_sec > 0 AND exit_delta_sec < 0) OR  -- A overtakes B
    (entry_delta_sec < 0 AND exit_delta_sec > 0)    -- B overtakes A
  )
ORDER BY 
    CASE 
        WHEN entry_delta_sec > 0 AND exit_delta_sec < 0 THEN 1
        WHEN entry_delta_sec < 0 AND exit_delta_sec > 0 THEN 2
    END,
    runner_id_a,
    runner_id_b;
```

**Use Case**: Understanding symmetric overtaking (e.g., J2 shows 5/5, meaning 5 runners overtook in each direction, forming 5 pairs).

---

## 5. Pass Detection Analysis

### Query 5.1: Raw vs. Strict Pass Detection

**Use Case**: Compare RAW pass detection (simple order flip) vs. STRICT pass detection (order flip + min dwell + directional gain).

```sql
SELECT
    COUNT(*) AS total_overlaps,
    SUM(CASE WHEN pass_flag_raw = True THEN 1 ELSE 0 END) AS raw_passes,
    SUM(CASE WHEN pass_flag_strict = True THEN 1 ELSE 0 END) AS strict_passes,
    AVG(overlap_dwell_sec) AS avg_dwell_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'B3'
  AND event_a = '10k'
  AND event_b = '10k';
```

**Explanation**:
- **RAW**: `pass_flag_raw = True` means order flip occurred (basic overtaking)
- **STRICT**: `pass_flag_strict = True` means order flip AND dwell >= 5s AND directional_gain >= 2s
- Flow.csv uses RAW pass detection for counting

---

### Query 5.2: Filter by Minimum Overlap Duration

**Use Case**: Filter overlaps by minimum duration threshold (matches main analysis requirement).

```sql
SELECT
    COUNT(DISTINCT runner_id_b) AS overtaking_b_unique,
    COUNT(DISTINCT runner_id_a) AS overtaken_a_unique,
    COUNT(*) AS total_overtake_events
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b'
  AND entry_delta_sec < 0       -- B entered after A
  AND exit_delta_sec > 0        -- B exited before A
  AND overlap_dwell_sec >= 5.0  -- Minimum overlap duration (DEFAULT_MIN_OVERLAP_DURATION)
  AND event_a = '10k'
  AND event_b = 'full';
```

---

## 6. Segment-Specific Analysis

### Query 6.1: Segment B3 Analysis (10k/10k Overtaking)

**Use Case**: Analyze segment B3 where one runner (1529) overtook 20 runners, and 520 runners overtook others.

```sql
-- Which runners did the 520 overtaking_b runners overtake?
SELECT
    runner_id_b AS overtaker,
    COUNT(DISTINCT runner_id_a) AS unique_runners_overtaken,
    COUNT(*) AS total_overtake_events,
    AVG(overlap_dwell_sec) AS avg_dwell_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'B3'
  AND entry_delta_sec < 0       -- b entered after a
  AND exit_delta_sec > 0        -- b exited before a (b passed a)
  AND event_a = '10k'
  AND event_b = '10k'
GROUP BY runner_id_b
ORDER BY unique_runners_overtaken DESC;
```

---

### Query 6.2: Segment J2 Analysis (5/5 Symmetric Overtaking)

**Use Case**: Understand symmetric overtaking where the same 5 runners appear in both directions.

```sql
-- Overtaking_A: 5 runners who overtook
SELECT
    runner_id_a AS overtaker,
    runner_id_b AS overtaken,
    overlap_dwell_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'J2'
  AND entry_delta_sec > 0      -- a entered after b
  AND exit_delta_sec < 0       -- a exited before b (a passed b)
ORDER BY runner_id_a, runner_id_b;

-- Overtaking_B: 5 runners who overtook (same pairs, reversed)
SELECT
    runner_id_b AS overtaker,
    runner_id_a AS overtaken,
    overlap_dwell_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'J2'
  AND entry_delta_sec < 0       -- b entered after a
  AND exit_delta_sec > 0        -- b exited before a (b passed a)
ORDER BY runner_id_b, runner_id_a;
```

**Explanation**: For J2, the 5/5 counts represent 5 unique pairs where each runner overtook the other, forming symmetric overtaking.

---

## 7. Advanced Analysis

### Query 7.1: Detailed Breakdown by Overtaker

**Use Case**: Understand the distribution of overtakes per runner.

```sql
SELECT
    runner_id_b AS overtaker,
    COUNT(DISTINCT runner_id_a) AS unique_overtaken,
    COUNT(*) AS total_events,
    AVG(overlap_dwell_sec) AS avg_dwell_sec,
    MIN(overlap_dwell_sec) AS min_dwell_sec,
    MAX(overlap_dwell_sec) AS max_dwell_sec,
    AVG(directional_gain_sec) AS avg_directional_gain_sec
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b'
  AND entry_delta_sec < 0       -- B entered after A
  AND exit_delta_sec > 0        -- B exited before A
  AND event_a = '10k'
  AND event_b = 'full'
GROUP BY runner_id_b
ORDER BY unique_overtaken DESC;
```

---

### Query 7.2: Filter by Strict Pass Detection

**Use Case**: Use stricter pass detection criteria (min_dwell=5s, margin=2s).

```sql
SELECT
    COUNT(DISTINCT runner_id_b) AS overtaking_b_unique,
    COUNT(DISTINCT runner_id_a) AS overtaken_a_unique,
    COUNT(*) AS total_overtake_events
FROM read_parquet('audit_sun.parquet')
WHERE seg_id = 'L1b'
  AND entry_delta_sec < 0       -- B entered after A
  AND exit_delta_sec > 0        -- B exited before A
  AND pass_flag_strict = True   -- Stricter pass detection
  AND event_a = '10k'
  AND event_b = 'full';
```

---

## Understanding the Data

### Flow.csv vs. Audit Data

| Source | Scope | Count Method | Example (L1b) |
|--------|-------|--------------|---------------|
| **Flow.csv** | Conflict zone only | Authoritative, exact | `overtaking_b = 206` |
| **Audit (filtered)** | Conflict zone (approximate) | Best-effort approximation | `~297` (44% higher) |
| **Audit (raw)** | Full segment | All overlaps in segment | `325` |

### Key Concepts

1. **Entry/Exit Deltas**:
   - `entry_delta_sec = entry_time_sec_a - entry_time_sec_b`
   - Positive: A entered after B
   - Negative: A entered before B

2. **Overtaking Detection**:
   - **Overtaking_A**: `entry_delta_sec > 0 AND exit_delta_sec < 0` (A entered after B, exited before B)
   - **Overtaking_B**: `entry_delta_sec < 0 AND exit_delta_sec > 0` (B entered after A, exited before A)

3. **Pass Detection**:
   - **RAW**: Simple order flip (`order_flip_bool = True`)
   - **STRICT**: Order flip + min dwell (5s) + directional gain (2s)

4. **Conflict Zone**:
   - Main analysis uses conflict zone boundaries (subset of segment)
   - Audit provides `in_conflict_zone` flag as approximation
   - For exact validation, use Flow.csv

### Known Limitations

1. **`in_conflict_zone` Accuracy**: Provides best-effort approximation, not exact match to Flow.csv
2. **Calculation Differences**: Audit recalculates pace from full segment times, while main analysis uses original pace
3. **Algorithm Complexity**: Main analysis has complex edge case handling that isn't fully replicated in audit

### Recommended Usage

1. **Exact Validation**: Use Flow.csv as authoritative source
2. **Comprehensive Analysis**: Use audit data (raw or filtered) for detailed investigation
3. **Debugging**: Use audit data to understand specific overtake events and timing
4. **Research**: Use audit data to explore patterns and relationships not visible in summary counts

---

## File Path Examples

Update the file path in queries to match your analysis run:

```sql
-- Example paths:
read_parquet('/Users/jthompson/Documents/runflow/{run_id}/sun/audit/audit_sun.parquet')
read_parquet('/Users/jthompson/Documents/runflow/{run_id}/sat/audit/audit_sat.parquet')

-- Or use relative paths if in the runflow directory:
read_parquet('{run_id}/sun/audit/audit_sun.parquet')
```

---

## Related Documentation

- **Issue #607**: Conflict Zone Support in Audit Data
- **Issue #552**: Flow Overtaking Count Logic Fix
- **Flow Analysis**: See main flow analysis documentation for algorithm details
