# Reports Directory Structure

This directory contains all analysis reports and test results for the run-density project.

## Directory Organization

### `/analysis/`
Contains comprehensive analysis reports generated from validated test data.

**Naming Convention**: `YYYY-MM-DD_HHMMSS_ReportType.md`

**Current Reports**:
- `2025-09-04_142206_Segments_Detailed_Report.md` - Latest formatted segments analysis with convergence points
- `2025-09-04_140000_Segments_Detailed_Report_fixed.md` - Fixed version with correct event names
- `2025-09-04_135949_Segments_Detailed_Report_corrected.md` - Corrected version with validated data

### `/test-results/`
Contains test execution results, comparison data, and validation outputs.

**File Types**:
- **Temporal Flow Compare CSV**: `YYYY-MM-DD_HHMMSS_Temporal_Flow_Compare.csv`
- **Test Data CSV**: `comprehensive_segments_test_report_*.csv`
- **Test Results JSON**: `density_test_results.json`

### `/archive/`
Contains historical reports organized by date.

## Report Types

### Segments Detailed Report
- **Purpose**: Comprehensive analysis of all segments with temporal flow and density metrics
- **Content**: Convergence points, overtake data, density calculations, LOS classifications
- **Data Source**: Validated temporal flow test results
- **Format**: Markdown with tables and analysis sections

### Temporal Flow Compare
- **Purpose**: Validation comparison between expected and actual temporal flow results
- **Content**: Segment-by-segment comparison with pass/fail status
- **Data Source**: Test framework validation runs
- **Format**: CSV with detailed comparison metrics

## Usage

1. **Latest Analysis**: Check `/analysis/` for the most recent comprehensive report
2. **Test Validation**: Check `/test-results/` for validation data and test outputs
3. **Historical Data**: Check `/archive/` for previous analysis runs

## File Naming Standards

- **Analysis Reports**: `YYYY-MM-DD_HHMMSS_ReportType.md`
- **Test Results**: `YYYY-MM-DD_HHMMSS_TestType.csv`
- **Comparison Data**: `comprehensive_*_test_report_*.csv`

This organization ensures:
- Clear separation of analysis vs test results
- Consistent naming conventions
- Easy identification of latest reports
- Historical tracking of analysis evolution
