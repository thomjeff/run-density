#!/usr/bin/env python3
"""
Flow Report Validation Script for Issue #390 Phase 3

This script validates that Phase 3 refactoring of complex conditional chains
in core/flow/flow.py, app/flow_report.py, and app/routes/api_e2e.py maintains
exact functional equivalence by comparing Flow report outputs.

Usage:
    python scripts/validate_flow_refactoring.py baseline_flow.md refactored_flow.md
    python scripts/validate_flow_refactoring.py baseline_flow.csv refactored_flow.csv
"""

import sys
import os
import pandas as pd
import difflib
from pathlib import Path
from typing import Dict, List, Any, Tuple
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FlowReportValidator:
    """Validates Flow report outputs for functional equivalence."""
    
    def __init__(self):
        self.differences = []
        self.summary_stats = {}
    
    def validate_markdown_reports(self, baseline_path: str, refactored_path: str) -> Dict[str, Any]:
        """
        Compare two Flow markdown reports for functional equivalence.
        
        Args:
            baseline_path: Path to baseline Flow.md report
            refactored_path: Path to refactored Flow.md report
            
        Returns:
            Dictionary with validation results
        """
        logger.info(f"Validating markdown reports: {baseline_path} vs {refactored_path}")
        
        try:
            with open(baseline_path, 'r', encoding='utf-8') as f:
                baseline_content = f.read()
            
            with open(refactored_path, 'r', encoding='utf-8') as f:
                refactored_content = f.read()
            
            # Extract key metrics from markdown
            baseline_metrics = self._extract_markdown_metrics(baseline_content)
            refactored_metrics = self._extract_markdown_metrics(refactored_content)
            
            # Compare metrics
            metrics_match = self._compare_metrics(baseline_metrics, refactored_metrics)
            
            # Generate unified diff
            diff_lines = list(difflib.unified_diff(
                baseline_content.splitlines(keepends=True),
                refactored_content.splitlines(keepends=True),
                fromfile='baseline_flow.md',
                tofile='refactored_flow.md',
                lineterm=''
            ))
            
            # Check for significant differences
            significant_diffs = [line for line in diff_lines if not self._is_insignificant_diff(line)]
            
            result = {
                'files_match': len(significant_diffs) == 0,
                'metrics_match': metrics_match,
                'total_differences': len(significant_diffs),
                'baseline_metrics': baseline_metrics,
                'refactored_metrics': refactored_metrics,
                'differences': significant_diffs,
                'full_diff': diff_lines
            }
            
            logger.info(f"Markdown validation complete: {len(significant_diffs)} significant differences")
            return result
            
        except Exception as e:
            logger.error(f"Error validating markdown reports: {e}")
            return {'error': str(e)}
    
    def validate_csv_reports(self, baseline_path: str, refactored_path: str) -> Dict[str, Any]:
        """
        Compare two Flow CSV reports for functional equivalence.
        
        Args:
            baseline_path: Path to baseline Flow.csv report
            refactored_path: Path to refactored Flow.csv report
            
        Returns:
            Dictionary with validation results
        """
        logger.info(f"Validating CSV reports: {baseline_path} vs {refactored_path}")
        
        try:
            # Load CSV files
            df_baseline = pd.read_csv(baseline_path)
            df_refactored = pd.read_csv(refactored_path)
            
            # Check shape consistency
            shape_match = df_baseline.shape == df_refactored.shape
            
            if not shape_match:
                logger.error(f"Shape mismatch: baseline {df_baseline.shape} vs refactored {df_refactored.shape}")
                return {
                    'files_match': False,
                    'error': f"Shape mismatch: baseline {df_baseline.shape} vs refactored {df_refactored.shape}"
                }
            
            # Check column consistency
            columns_match = list(df_baseline.columns) == list(df_refactored.columns)
            
            if not columns_match:
                logger.error(f"Column mismatch: baseline {list(df_baseline.columns)} vs refactored {list(df_refactored.columns)}")
                return {
                    'files_match': False,
                    'error': f"Column mismatch: baseline {list(df_baseline.columns)} vs refactored {list(df_refactored.columns)}"
                }
            
            # Compare values (excluding timestamp columns)
            timestamp_cols = [col for col in df_baseline.columns if 'timestamp' in col.lower() or 'time' in col.lower()]
            data_cols = [col for col in df_baseline.columns if col not in timestamp_cols]
            
            # Check for differences in data columns
            differences = []
            for col in data_cols:
                col_diff = (df_baseline[col] != df_refactored[col]) & ~(df_baseline[col].isna() & df_refactored[col].isna())
                if col_diff.any():
                    diff_rows = df_baseline[col_diff].index.tolist()
                    differences.append({
                        'column': col,
                        'different_rows': diff_rows,
                        'baseline_values': df_baseline.loc[diff_rows, col].tolist(),
                        'refactored_values': df_refactored.loc[diff_rows, col].tolist()
                    })
            
            # Extract key metrics
            baseline_metrics = self._extract_csv_metrics(df_baseline)
            refactored_metrics = self._extract_csv_metrics(df_refactored)
            
            result = {
                'files_match': len(differences) == 0,
                'shape_match': shape_match,
                'columns_match': columns_match,
                'total_differences': len(differences),
                'differences': differences,
                'baseline_metrics': baseline_metrics,
                'refactored_metrics': refactored_metrics,
                'timestamp_columns': timestamp_cols,
                'data_columns': data_cols
            }
            
            logger.info(f"CSV validation complete: {len(differences)} differences found")
            return result
            
        except Exception as e:
            logger.error(f"Error validating CSV reports: {e}")
            return {'error': str(e)}
    
    def _extract_markdown_metrics(self, content: str) -> Dict[str, Any]:
        """Extract key metrics from Flow markdown report."""
        metrics = {}
        
        try:
            lines = content.split('\n')
            
            # Extract total segments
            for line in lines:
                if 'Total Segments' in line and '|' in line:
                    try:
                        metrics['total_segments'] = int(line.split('|')[2].strip())
                    except:
                        pass
            
            # Extract segments with convergence
            for line in lines:
                if 'Segments with Convergence' in line and '|' in line:
                    try:
                        metrics['convergence_segments'] = int(line.split('|')[2].strip())
                    except:
                        pass
            
            # Extract convergence rate
            for line in lines:
                if 'Convergence Rate' in line and '|' in line:
                    try:
                        metrics['convergence_rate'] = float(line.split('|')[2].strip().replace('%', ''))
                    except:
                        pass
            
            # Count flow types
            flow_types = {}
            in_flow_type_section = False
            for line in lines:
                if 'Flow Type Breakdown' in line:
                    in_flow_type_section = True
                    continue
                if in_flow_type_section and '|' in line and 'Flow Type' not in line and 'Count' not in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        flow_type = parts[1].strip()
                        count = parts[2].strip()
                        if flow_type and count.isdigit():
                            flow_types[flow_type] = int(count)
                if in_flow_type_section and line.strip() == '':
                    in_flow_type_section = False
            
            metrics['flow_types'] = flow_types
            
        except Exception as e:
            logger.warning(f"Error extracting markdown metrics: {e}")
        
        return metrics
    
    def _extract_csv_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract key metrics from Flow CSV report."""
        metrics = {}
        
        try:
            metrics['total_rows'] = len(df)
            metrics['total_columns'] = len(df.columns)
            
            # Count segments if seg_id column exists
            if 'seg_id' in df.columns:
                metrics['unique_segments'] = df['seg_id'].nunique()
            
            # Count flow types if flow_type column exists
            if 'flow_type' in df.columns:
                metrics['flow_type_counts'] = df['flow_type'].value_counts().to_dict()
            
            # Count convergence if has_convergence column exists
            if 'has_convergence' in df.columns:
                metrics['convergence_count'] = df['has_convergence'].sum()
            
        except Exception as e:
            logger.warning(f"Error extracting CSV metrics: {e}")
        
        return metrics
    
    def _compare_metrics(self, baseline: Dict[str, Any], refactored: Dict[str, Any]) -> bool:
        """Compare extracted metrics for equivalence."""
        try:
            # Compare numeric metrics
            numeric_keys = ['total_segments', 'convergence_segments', 'convergence_rate', 
                          'total_rows', 'total_columns', 'unique_segments', 'convergence_count']
            
            for key in numeric_keys:
                if key in baseline and key in refactored:
                    if baseline[key] != refactored[key]:
                        logger.warning(f"Metric mismatch: {key} baseline={baseline[key]} refactored={refactored[key]}")
                        return False
            
            # Compare flow types
            if 'flow_types' in baseline and 'flow_types' in refactored:
                if baseline['flow_types'] != refactored['flow_types']:
                    logger.warning(f"Flow types mismatch: baseline={baseline['flow_types']} refactored={refactored['flow_types']}")
                    return False
            
            if 'flow_type_counts' in baseline and 'flow_type_counts' in refactored:
                if baseline['flow_type_counts'] != refactored['flow_type_counts']:
                    logger.warning(f"Flow type counts mismatch: baseline={baseline['flow_type_counts']} refactored={refactored['flow_type_counts']}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error comparing metrics: {e}")
            return False
    
    def _is_insignificant_diff(self, line: str) -> bool:
        """Check if a diff line represents an insignificant change."""
        # Ignore timestamp differences
        if 'timestamp' in line.lower() or 'generated' in line.lower():
            return True
        
        # Ignore whitespace-only changes
        if line.startswith('+') or line.startswith('-'):
            content = line[1:].strip()
            if not content:
                return True
        
        return False
    
    def generate_report(self, markdown_result: Dict[str, Any], csv_result: Dict[str, Any], output_path: str):
        """Generate a comprehensive validation report."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("# Flow Report Validation Results\n\n")
                f.write(f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Summary
                f.write("## Summary\n\n")
                markdown_match = markdown_result.get('files_match', False)
                csv_match = csv_result.get('files_match', False)
                
                if markdown_match and csv_match:
                    f.write("✅ **VALIDATION PASSED** - All Flow reports match exactly\n\n")
                else:
                    f.write("❌ **VALIDATION FAILED** - Differences detected\n\n")
                
                # Markdown results
                f.write("## Markdown Report Validation\n\n")
                if 'error' in markdown_result:
                    f.write(f"❌ Error: {markdown_result['error']}\n\n")
                else:
                    f.write(f"- **Files Match:** {'✅ Yes' if markdown_match else '❌ No'}\n")
                    f.write(f"- **Metrics Match:** {'✅ Yes' if markdown_result.get('metrics_match', False) else '❌ No'}\n")
                    f.write(f"- **Total Differences:** {markdown_result.get('total_differences', 0)}\n\n")
                    
                    if markdown_result.get('baseline_metrics'):
                        f.write("### Baseline Metrics\n")
                        for key, value in markdown_result['baseline_metrics'].items():
                            f.write(f"- {key}: {value}\n")
                        f.write("\n")
                    
                    if markdown_result.get('refactored_metrics'):
                        f.write("### Refactored Metrics\n")
                        for key, value in markdown_result['refactored_metrics'].items():
                            f.write(f"- {key}: {value}\n")
                        f.write("\n")
                
                # CSV results
                f.write("## CSV Report Validation\n\n")
                if 'error' in csv_result:
                    f.write(f"❌ Error: {csv_result['error']}\n\n")
                else:
                    f.write(f"- **Files Match:** {'✅ Yes' if csv_match else '❌ No'}\n")
                    f.write(f"- **Shape Match:** {'✅ Yes' if csv_result.get('shape_match', False) else '❌ No'}\n")
                    f.write(f"- **Columns Match:** {'✅ Yes' if csv_result.get('columns_match', False) else '❌ No'}\n")
                    f.write(f"- **Total Differences:** {csv_result.get('total_differences', 0)}\n\n")
                    
                    if csv_result.get('differences'):
                        f.write("### Differences Found\n")
                        for diff in csv_result['differences']:
                            f.write(f"- Column: {diff['column']}\n")
                            f.write(f"  - Different rows: {diff['different_rows']}\n")
                            f.write(f"  - Baseline values: {diff['baseline_values']}\n")
                            f.write(f"  - Refactored values: {diff['refactored_values']}\n\n")
                
                # Recommendations
                f.write("## Recommendations\n\n")
                if markdown_match and csv_match:
                    f.write("✅ **Phase 3 refactoring is safe to proceed**\n")
                    f.write("- No functional differences detected\n")
                    f.write("- All metrics and data match exactly\n")
                    f.write("- Complex conditional chains successfully abstracted\n")
                else:
                    f.write("⚠️ **Review required before proceeding**\n")
                    f.write("- Investigate differences found\n")
                    f.write("- Ensure refactoring maintains exact behavior\n")
                    f.write("- Consider rollback if differences are significant\n")
            
            logger.info(f"Validation report saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating validation report: {e}")

def main():
    """Main function for Flow report validation."""
    parser = argparse.ArgumentParser(description='Validate Flow report refactoring')
    parser.add_argument('baseline_md', help='Path to baseline Flow.md report')
    parser.add_argument('refactored_md', help='Path to refactored Flow.md report')
    parser.add_argument('baseline_csv', help='Path to baseline Flow.csv report')
    parser.add_argument('refactored_csv', help='Path to refactored Flow.csv report')
    parser.add_argument('--output', '-o', default='flow_validation_report.md', 
                       help='Output path for validation report')
    
    args = parser.parse_args()
    
    # Validate file existence
    for file_path in [args.baseline_md, args.refactored_md, args.baseline_csv, args.refactored_csv]:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            sys.exit(1)
    
    # Create validator
    validator = FlowReportValidator()
    
    # Validate reports
    logger.info("Starting Flow report validation...")
    
    markdown_result = validator.validate_markdown_reports(args.baseline_md, args.refactored_md)
    csv_result = validator.validate_csv_reports(args.baseline_csv, args.refactored_csv)
    
    # Generate report
    validator.generate_report(markdown_result, csv_result, args.output)
    
    # Exit with appropriate code
    if markdown_result.get('files_match', False) and csv_result.get('files_match', False):
        logger.info("✅ Validation passed - Flow reports match exactly")
        sys.exit(0)
    else:
        logger.error("❌ Validation failed - Differences detected")
        sys.exit(1)

if __name__ == '__main__':
    main()
