# CSV Export Standards

## Overview

All CSV exports from parquet files use **consistent decimal precision** to ensure human-readable formats are properly formatted for spreadsheet applications like Excel.

## Standard Precision

**All numeric values are formatted to 4 decimal places.**

This ensures:
- ✅ Consistent display across all CSV files
- ✅ Sufficient precision for density (p/m²) and flow (p/s) values
- ✅ No misleading "0.00" displays for small but meaningful values
- ✅ Excel and other spreadsheet apps display values consistently

## Export Utility

Use `app/csv_export_utils.py` for all parquet-to-CSV conversions:

### Export Single Report Directory

```bash
python app/csv_export_utils.py reports/2025-10-15
```

This will export:
- `bins.parquet` → `bins_readable.csv` (4 decimal places)
- `segment_windows_from_bins.parquet` → `segment_windows_from_bins_readable.csv` (4 decimal places)

### Programmatic Usage

```python
from app.csv_export_utils import export_bins_to_csv, export_segment_windows_to_csv

# Export bins
csv_path = export_bins_to_csv("reports/2025-10-15/bins.parquet")

# Export segment windows
csv_path = export_segment_windows_to_csv("reports/2025-10-15/segment_windows_from_bins.parquet")
```

## Formatted Columns

### bins_readable.csv
- `start_km`: 4 decimal places (e.g., 0.8000) - Bin start position in km
- `end_km`: 4 decimal places (e.g., 1.0000) - Bin end position in km
- `density`: 4 decimal places (e.g., 0.7490) - Areal density in persons/m²
- **`rate`**: 4 decimal places (e.g., 5.5284) - **Throughput rate in persons/second**
- `bin_size_km`: 4 decimal places (e.g., 0.2000) - Bin length in km

**Rate Calculation**: `rate = density × width × mean_speed`
- Where density = persons/m², width = segment width in meters, mean_speed = average runner speed in m/s
- Rate represents the **actual number of people crossing a virtual line per second** at that location
- Example: density=0.353 p/m², width=5m, speed=3.13 m/s → rate=5.528 p/s ✅

**Note**: Renamed from `flow` to `rate` to avoid confusion with Flow analysis (event-level convergence in `flow.csv`).

### segment_windows_from_bins_readable.csv
- `density_mean`: 4 decimal places (e.g., 0.1900)
- `density_peak`: 4 decimal places (e.g., 0.7490)
- `n_bins`: Integer (no decimal places)

## Implementation Details

The utility:
1. Reads parquet files (which store full float precision)
2. Rounds numeric columns to 4 decimal places using `pandas.round(4)`
3. Exports to CSV with `float_format='%.4f'` to ensure consistent trailing zeros

## Examples

### Before Standardization
```csv
density,flow
0.353,5.528415428204609
0.182,3.162696114444935
0.064,0.7698290814161795
```

### After Standardization (4 decimal places)
```csv
density,flow
0.3530,5.5284
0.1820,3.1627
0.0640,0.7698
```

## Why 4 Decimal Places?

1. **Density values** (p/m²): Range from 0.001 to 2.0
   - 4 decimals captures 0.0001 precision, suitable for low-density areas
   
2. **Flow values** (p/s): Range from 0.006 to 24.0
   - 4 decimals provides adequate precision for flow calculations
   
3. **Spatial values** (km): Range from 0.0 to 42.2
   - 4 decimals = 0.1 meter precision, appropriate for bin boundaries

4. **Consistency**: Same precision across all numeric types simplifies data review

## Changing Precision

To change the standard precision, update `DECIMAL_PRECISION` in `app/csv_export_utils.py`:

```python
DECIMAL_PRECISION = 4  # Change to 5 if more precision needed
```

Then re-export all CSV files using the utility.

