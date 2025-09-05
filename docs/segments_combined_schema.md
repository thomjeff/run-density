# Segments Combined Schema Documentation

## Overview

The `segments_combined.csv` file consolidates the data from both `flow.csv` and `density.csv` into a single, normalized format. This eliminates duplication and provides a cleaner data structure for both temporal flow and density analysis modules.

## Schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `seg_id` | string | Unique segment identifier | `A1a` |
| `event` | string | Event name (10K, Half, Full) | `10K` |
| `from_km` | float | Starting kilometer for this event | `0.0` |
| `to_km` | float | Ending kilometer for this event | `0.9` |
| `width_m` | float | Physical width in meters | `5.0` |
| `direction` | string | Traffic direction (uni, bi) | `uni` |
| `step_km` | float | Analysis step size in kilometers | `0.1` |
| `include_y` | string | Include flag for density analysis (y, n) | `y` |
| `physical_name` | string | Human-readable segment name | `Start to Queen/Regent` |
| `notes` | string | Additional segment information | `Start along St John Street; All events use this segment` |

## Data Structure

### Long/Tidy Format
- **One row per segment_id + event combination**
- Each segment can have multiple events (10K, Half, Full)
- Each event has its own kilometer range and properties
- Eliminates duplication between flow and density data

### Event Coverage
- **10K**: Segments A1a-A1c, B1, C1, F1, G2
- **Half**: Segments A1a-A1c, F1, G2, G3, H1, I1, J1, K1, K2, L1
- **Full**: All segments (A1a-A1c, B1, C1, D1, D2, F1, G1, G2, G3, H1, I1, J1, K1, K2, L1, M1)

### Physical Properties
- **Width**: Consistent across all events for a given segment
- **Direction**: Consistent across all events for a given segment
- **Step Size**: Consistent across all events for a given segment
- **Include Flag**: Event-specific inclusion for density analysis

## Benefits

### 1. Eliminates Duplication
- Single source of truth for segment definitions
- No more maintaining separate flow.csv and density.csv files
- Consistent data across all modules

### 2. Supports Any Number of Events
- Easy to add new events (e.g., 5K, Marathon)
- Flexible event-specific kilometer ranges
- Scalable architecture

### 3. Cleaner Data Structure
- Normalized format reduces data redundancy
- Easier to query and filter by event
- Better data integrity

### 4. Better Validation
- Single file to validate for consistency
- Easier to detect gaps and overlaps
- Centralized data quality checks

## Usage in Modules

### Temporal Flow Analysis
- Derive A/B event pairs from combined format
- Filter segments by event combinations
- Use kilometer ranges for overlap calculations

### Density Analysis
- Filter segments by event using `include_y` flag
- Use event-specific kilometer ranges
- Access physical properties (width, direction)

## Migration from Previous Format

### From flow.csv
- `seg_id` → `seg_id`
- `eventA`, `eventB` → Multiple rows with `event` column
- `from_km_A`, `to_km_A` → `from_km`, `to_km` for event A
- `from_km_B`, `to_km_B` → `from_km`, `to_km` for event B
- `width_m`, `direction` → Same columns
- `overtake_flag` → Not needed (derived from event pairs)

### From density.csv
- `seg_id` → `seg_id`
- `physical_name` → `physical_name`
- `width_m`, `direction` → Same columns
- `full`, `half`, `10k` → `include_y` flag per event
- `full_from_km`, `full_to_km` → `from_km`, `to_km` for Full event
- `half_from_km`, `half_to_km` → `from_km`, `to_km` for Half event
- `10k_from_km`, `10k_to_km` → `from_km`, `to_km` for 10K event

## Validation Rules

1. **Distance Continuity**: Within each event, segments should connect without gaps
2. **Event Consistency**: Same events should have consistent properties across segments
3. **Required Fields**: All fields must be present and valid
4. **Numeric Ranges**: Kilometer values should be positive and logical
5. **No Duplicates**: No duplicate segment_id + event combinations
6. **Marathon Distance**: Full marathon should total 42.2km

## Known Limitations

### Distance Gaps (Documented but not fixed)
1. **D2 vs C1 gap**: 0.01km (14.79 → 14.8)
2. **G2 vs H1 gap**: 0.29km (23.55 → 23.26)

These gaps exist due to the 42.2km Full Marathon constraint and are acceptable for current analysis needs.

## File Location
- **Path**: `data/segments_combined.csv`
- **Format**: CSV with header row
- **Encoding**: UTF-8
- **Line Endings**: Unix (LF)

## Related Files
- `data/flow.csv` - Original temporal flow segments (to be deprecated)
- `data/density.csv` - Original density segments (to be deprecated)
- `app/flow.py` - Temporal flow analysis module
- `app/density.py` - Density analysis module
