#!/usr/bin/env python3
"""
Density Report Comparison Script for Issue #390 Phase 1 Validation

This script compares density reports before and after refactoring to ensure
identical results. It validates that the Event Logic utility function refactoring
does not change the density calculation outputs.

Usage:
    python scripts/validate_density_refactoring.py --baseline reports/2025-10-28-1538-Density.md --new reports/2025-10-28-NEW-Density.md

Author: AI Assistant
Created: 2025-10-28
Issue: #390 Phase 1 Validation
"""

import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class DensityReportComparator:
    """Compare density reports for validation of refactoring changes."""
    
    def __init__(self, baseline_path: str, new_path: str):
        self.baseline_path = Path(baseline_path)
        self.new_path = Path(new_path)
        self.baseline_content = ""
        self.new_content = ""
        self.comparison_results = {}
        
    def load_reports(self) -> bool:
        """Load both report files."""
        try:
            self.baseline_content = self.baseline_path.read_text(encoding='utf-8')
            self.new_content = self.new_path.read_text(encoding='utf-8')
            logger.info(f"✅ Loaded baseline report: {self.baseline_path}")
            logger.info(f"✅ Loaded new report: {self.new_path}")
            return True
        except FileNotFoundError as e:
            logger.error(f"❌ File not found: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error loading files: {e}")
            return False
    
    def extract_key_metrics(self, content: str) -> Dict[str, str]:
        """Extract key metrics from density report."""
        metrics = {}
        
        # Extract Executive Summary metrics
        exec_summary_patterns = {
            'peak_density': r'Peak Density:\s*([0-9.]+)\s*p/m²',
            'peak_rate': r'Peak Rate:\s*([0-9.]+)\s*p/s',
            'segments_with_flags': r'Segments with Flags:\s*(\d+)\s*/\s*(\d+)',
            'flagged_bins': r'Flagged Bins:\s*([0-9,]+)',
            'total_participants': r'Total Participants:\s*([0-9,]+)',
            'overtaking_segments': r'Overtaking Segments:\s*(\d+)',
            'copresence_segments': r'Co-presence Segments:\s*(\d+)'
        }
        
        for key, pattern in exec_summary_patterns.items():
            match = re.search(pattern, content)
            if match:
                metrics[key] = match.group(1) if len(match.groups()) == 1 else match.groups()
        
        # Extract Start Times section
        start_times_pattern = r'## Start Times\s*\n(.*?)(?=\n##|\n---|\Z)'
        start_times_match = re.search(start_times_pattern, content, re.DOTALL)
        if start_times_match:
            metrics['start_times'] = start_times_match.group(1).strip()
        
        # Extract Methodology section
        methodology_pattern = r'## Methodology\s*\n(.*?)(?=\n##|\n---|\Z)'
        methodology_match = re.search(methodology_pattern, content, re.DOTALL)
        if methodology_match:
            metrics['methodology'] = methodology_match.group(1).strip()
        
        # Extract segment count
        segment_count_pattern = r'Total Segments Analyzed:\s*(\d+)'
        segment_match = re.search(segment_count_pattern, content)
        if segment_match:
            metrics['total_segments'] = segment_match.group(1)
        
        return metrics
    
    def extract_segment_data(self, content: str) -> Dict[str, Dict[str, str]]:
        """Extract per-segment data from density report."""
        segments = {}
        
        # Pattern to match segment sections
        segment_pattern = r'### Segment ([A-Z]\d+):\s*(.*?)\n(.*?)(?=\n###|\n---|\Z)'
        segment_matches = re.findall(segment_pattern, content, re.DOTALL)
        
        for segment_id, segment_name, segment_content in segment_matches:
            segment_data = {
                'name': segment_name.strip(),
                'content': segment_content.strip()
            }
            
            # Extract segment-specific metrics
            peak_density_match = re.search(r'Peak Density:\s*([0-9.]+)\s*p/m²', segment_content)
            if peak_density_match:
                segment_data['peak_density'] = peak_density_match.group(1)
            
            los_match = re.search(r'Level of Service:\s*([A-F])', segment_content)
            if los_match:
                segment_data['los'] = los_match.group(1)
            
            peak_rate_match = re.search(r'Peak Rate:\s*([0-9.]+)\s*p/s', segment_content)
            if peak_rate_match:
                segment_data['peak_rate'] = peak_rate_match.group(1)
            
            flagged_match = re.search(r'Flagged:\s*(Yes|No)', segment_content)
            if flagged_match:
                segment_data['flagged'] = flagged_match.group(1)
            
            segments[segment_id] = segment_data
        
        return segments
    
    def compare_metrics(self) -> Dict[str, bool]:
        """Compare key metrics between reports."""
        baseline_metrics = self.extract_key_metrics(self.baseline_content)
        new_metrics = self.extract_key_metrics(self.new_content)
        
        comparison = {}
        
        # Compare each metric
        all_keys = set(baseline_metrics.keys()) | set(new_metrics.keys())
        
        for key in all_keys:
            baseline_value = baseline_metrics.get(key, "MISSING")
            new_value = new_metrics.get(key, "MISSING")
            
            if baseline_value == new_value:
                comparison[key] = True
                logger.info(f"✅ {key}: MATCH ({baseline_value})")
            else:
                comparison[key] = False
                logger.error(f"❌ {key}: MISMATCH")
                logger.error(f"   Baseline: {baseline_value}")
                logger.error(f"   New:      {new_value}")
        
        return comparison
    
    def compare_segments(self) -> Dict[str, bool]:
        """Compare per-segment data between reports."""
        baseline_segments = self.extract_segment_data(self.baseline_content)
        new_segments = self.extract_segment_data(self.new_content)
        
        comparison = {}
        
        # Compare each segment
        all_segment_ids = set(baseline_segments.keys()) | set(new_segments.keys())
        
        for segment_id in all_segment_ids:
            baseline_segment = baseline_segments.get(segment_id, {})
            new_segment = new_segments.get(segment_id, {})
            
            segment_match = True
            
            # Compare segment metrics
            for metric in ['peak_density', 'los', 'peak_rate', 'flagged']:
                baseline_value = baseline_segment.get(metric, "MISSING")
                new_value = new_segment.get(metric, "MISSING")
                
                if baseline_value != new_value:
                    segment_match = False
                    logger.error(f"❌ {segment_id} {metric}: MISMATCH")
                    logger.error(f"   Baseline: {baseline_value}")
                    logger.error(f"   New:      {new_value}")
            
            if segment_match:
                logger.info(f"✅ {segment_id}: MATCH")
            
            comparison[segment_id] = segment_match
        
        return comparison
    
    def generate_unified_diff(self) -> List[str]:
        """Generate unified diff between reports."""
        baseline_lines = self.baseline_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            baseline_lines,
            new_lines,
            fromfile=str(self.baseline_path),
            tofile=str(self.new_path),
            lineterm=''
        )
        
        return list(diff)
    
    def generate_html_diff(self) -> str:
        """Generate HTML diff for better visualization."""
        baseline_lines = self.baseline_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        
        html_diff = difflib.HtmlDiff()
        return html_diff.make_file(
            baseline_lines,
            new_lines,
            fromdesc=str(self.baseline_path),
            todesc=str(self.new_path)
        )
    
    def run_comparison(self) -> bool:
        """Run complete comparison and return success status."""
        logger.info("🔍 Starting density report comparison...")
        
        # Load reports
        if not self.load_reports():
            return False
        
        # Compare key metrics
        logger.info("\n📊 Comparing key metrics...")
        metrics_comparison = self.compare_metrics()
        
        # Compare segment data
        logger.info("\n🎯 Comparing segment data...")
        segments_comparison = self.compare_segments()
        
        # Generate diff
        logger.info("\n📝 Generating unified diff...")
        diff_lines = self.generate_unified_diff()
        
        # Save diff to file
        diff_path = Path("density_report_diff.txt")
        with open(diff_path, 'w', encoding='utf-8') as f:
            f.writelines(diff_lines)
        logger.info(f"📄 Diff saved to: {diff_path}")
        
        # Generate HTML diff
        html_diff = self.generate_html_diff()
        html_path = Path("density_report_diff.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_diff)
        logger.info(f"🌐 HTML diff saved to: {html_path}")
        
        # Determine overall success
        all_metrics_match = all(metrics_comparison.values())
        all_segments_match = all(segments_comparison.values())
        
        success = all_metrics_match and all_segments_match
        
        # Summary
        logger.info(f"\n📋 COMPARISON SUMMARY:")
        logger.info(f"   Key Metrics Match: {all_metrics_match}")
        logger.info(f"   Segments Match: {all_segments_match}")
        logger.info(f"   Overall Success: {success}")
        
        if success:
            logger.info("🎉 VALIDATION PASSED: Density calculations are identical after refactoring!")
        else:
            logger.error("❌ VALIDATION FAILED: Density calculations differ after refactoring!")
        
        return success


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Compare density reports for Issue #390 Phase 1 validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Compare with baseline report
    python scripts/validate_density_refactoring.py \\
        --baseline reports/2025-10-28-1538-Density.md \\
        --new reports/2025-10-28-NEW-Density.md
    
    # Compare with verbose output
    python scripts/validate_density_refactoring.py \\
        --baseline reports/2025-10-28-1538-Density.md \\
        --new reports/2025-10-28-NEW-Density.md \\
        --verbose
        """
    )
    
    parser.add_argument(
        '--baseline',
        required=True,
        help='Path to baseline density report (e.g., 2025-10-28-1538-Density.md)'
    )
    
    parser.add_argument(
        '--new',
        required=True,
        help='Path to new density report after refactoring'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run comparison
    comparator = DensityReportComparator(args.baseline, args.new)
    success = comparator.run_comparison()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
