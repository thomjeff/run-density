"""
Flow Analysis Validation Framework

Provides comprehensive validation for temporal flow analysis results,
including regression testing, data integrity checks, and baseline comparisons.
"""

import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json


class FlowValidationResult:
    """Result of a validation check."""
    
    def __init__(self, check_name: str, passed: bool, message: str, details: Optional[Dict] = None):
        self.check_name = check_name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class FlowValidationFramework:
    """Comprehensive validation framework for flow analysis."""
    
    def __init__(self):
        self.results: List[FlowValidationResult] = []
    
    def add_result(self, result: FlowValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)
    
    def validate_data_integrity(self, segments: List[Dict[str, Any]]) -> None:
        """Validate data integrity of segment results."""
        
        # Check 1: All segments have required fields
        required_fields = ['seg_id', 'event_a', 'event_b', 'has_convergence']
        for segment in segments:
            for field in required_fields:
                if field not in segment:
                    self.add_result(FlowValidationResult(
                        "data_integrity_required_fields",
                        False,
                        f"Missing required field '{field}' in segment {segment.get('seg_id', 'unknown')}"
                    ))
                    return
        
        self.add_result(FlowValidationResult(
            "data_integrity_required_fields",
            True,
            f"All {len(segments)} segments have required fields"
        ))
        
        # Check 2: Convergence point consistency
        convergent_segments = [s for s in segments if s.get('has_convergence')]
        inconsistent_segments = []
        
        for segment in convergent_segments:
            has_cp = segment.get('convergence_point') is not None
            has_cz_start = segment.get('convergence_zone_start') is not None
            has_cz_end = segment.get('convergence_zone_end') is not None
            
            if not (has_cp and has_cz_start and has_cz_end):
                inconsistent_segments.append(segment['seg_id'])
        
        if inconsistent_segments:
            self.add_result(FlowValidationResult(
                "data_integrity_convergence_consistency",
                False,
                f"Convergent segments with missing convergence data: {inconsistent_segments}",
                {"inconsistent_segments": inconsistent_segments}
            ))
        else:
            self.add_result(FlowValidationResult(
                "data_integrity_convergence_consistency",
                True,
                f"All {len(convergent_segments)} convergent segments have complete convergence data"
            ))
        
        # Check 3: Sample data completeness
        segments_with_samples = 0
        for segment in convergent_segments:
            sample_a = segment.get('sample_a', [])
            sample_b = segment.get('sample_b', [])
            if sample_a and sample_b:
                segments_with_samples += 1
        
        sample_completeness = len(convergent_segments) > 0 and segments_with_samples == len(convergent_segments)
        
        self.add_result(FlowValidationResult(
            "data_integrity_sample_completeness",
            sample_completeness,
            f"Sample data completeness: {segments_with_samples}/{len(convergent_segments)} convergent segments have sample data",
            {"segments_with_samples": segments_with_samples, "total_convergent": len(convergent_segments)}
        ))
    
    def validate_convergence_detection(self, segments: List[Dict[str, Any]], baseline_segments: Optional[List[Dict[str, Any]]] = None) -> None:
        """Validate convergence detection logic."""
        
        convergent_segments = [s for s in segments if s.get('has_convergence')]
        
        # Check 1: Expected convergent segments are found
        expected_convergent = ['A3', 'B2', 'F1', 'I1', 'K1', 'L1', 'M1']  # Based on test results
        
        found_expected = []
        missing_expected = []
        
        for expected_seg in expected_convergent:
            found = any(s['seg_id'] == expected_seg for s in convergent_segments)
            if found:
                found_expected.append(expected_seg)
            else:
                missing_expected.append(expected_seg)
        
        if missing_expected:
            self.add_result(FlowValidationResult(
                "convergence_detection_expected_segments",
                False,
                f"Missing expected convergent segments: {missing_expected}",
                {"missing": missing_expected, "found": found_expected}
            ))
        else:
            self.add_result(FlowValidationResult(
                "convergence_detection_expected_segments",
                True,
                f"All expected convergent segments found: {found_expected}"
            ))
        
        # Check 2: Convergence point ranges are reasonable
        unreasonable_cps = []
        for segment in convergent_segments:
            cp = segment.get('convergence_point')
            from_km = segment.get('from_km_a', 0)
            to_km = segment.get('to_km_a', 0)
            
            if cp is not None and not (from_km <= cp <= to_km):
                unreasonable_cps.append({
                    'seg_id': segment['seg_id'],
                    'convergence_point': cp,
                    'from_km': from_km,
                    'to_km': to_km
                })
        
        if unreasonable_cps:
            self.add_result(FlowValidationResult(
                "convergence_detection_point_ranges",
                False,
                f"Convergence points outside segment range: {len(unreasonable_cps)} segments",
                {"unreasonable_points": unreasonable_cps}
            ))
        else:
            self.add_result(FlowValidationResult(
                "convergence_detection_point_ranges",
                True,
                f"All {len(convergent_segments)} convergence points are within segment ranges"
            ))
        
        # Check 3: Baseline comparison (if provided)
        if baseline_segments:
            self._compare_with_baseline(segments, baseline_segments)
    
    def validate_sample_data_quality(self, segments: List[Dict[str, Any]]) -> None:
        """Validate quality of sample runner data."""
        
        convergent_segments = [s for s in segments if s.get('has_convergence')]
        
        # Check 1: Sample data is not empty for convergent segments
        empty_samples = []
        for segment in convergent_segments:
            sample_a = segment.get('sample_a', [])
            sample_b = segment.get('sample_b', [])
            
            if not sample_a or not sample_b:
                empty_samples.append(segment['seg_id'])
        
        if empty_samples:
            self.add_result(FlowValidationResult(
                "sample_data_empty_samples",
                False,
                f"Empty sample data in convergent segments: {empty_samples}"
            ))
        else:
            self.add_result(FlowValidationResult(
                "sample_data_empty_samples",
                True,
                f"All {len(convergent_segments)} convergent segments have non-empty sample data"
            ))
        
        # Check 2: Sample data format consistency
        invalid_format_samples = []
        for segment in convergent_segments:
            sample_a = segment.get('sample_a', [])
            sample_b = segment.get('sample_b', [])
            
            # Check if samples are lists of strings/numbers
            if not isinstance(sample_a, list) or not isinstance(sample_b, list):
                invalid_format_samples.append(segment['seg_id'])
        
        if invalid_format_samples:
            self.add_result(FlowValidationResult(
                "sample_data_format",
                False,
                f"Invalid sample data format in segments: {invalid_format_samples}"
            ))
        else:
            self.add_result(FlowValidationResult(
                "sample_data_format",
                True,
                f"All sample data has correct list format"
            ))
    
    def validate_unit_consistency(self, segments: List[Dict[str, Any]]) -> None:
        """Validate unit consistency in results."""
        
        # Check 1: Convergence points are reasonable (not negative, not too large)
        unreasonable_points = []
        for segment in segments:
            cp = segment.get('convergence_point')
            if cp is not None and (cp < 0 or cp > 50):  # Assume race is less than 50km
                unreasonable_points.append({
                    'seg_id': segment['seg_id'],
                    'convergence_point': cp
                })
        
        if unreasonable_points:
            self.add_result(FlowValidationResult(
                "unit_consistency_convergence_points",
                False,
                f"Unreasonable convergence point values: {len(unreasonable_points)} segments",
                {"unreasonable_points": unreasonable_points}
            ))
        else:
            self.add_result(FlowValidationResult(
                "unit_consistency_convergence_points",
                True,
                f"All convergence points have reasonable values"
            ))
        
        # Check 2: Distance ranges are consistent
        inconsistent_ranges = []
        for segment in segments:
            from_km = segment.get('from_km_a', 0)
            to_km = segment.get('to_km_a', 0)
            
            if to_km <= from_km:
                inconsistent_ranges.append({
                    'seg_id': segment['seg_id'],
                    'from_km': from_km,
                    'to_km': to_km
                })
        
        if inconsistent_ranges:
            self.add_result(FlowValidationResult(
                "unit_consistency_distance_ranges",
                False,
                f"Invalid distance ranges: {len(inconsistent_ranges)} segments",
                {"inconsistent_ranges": inconsistent_ranges}
            ))
        else:
            self.add_result(FlowValidationResult(
                "unit_consistency_distance_ranges",
                True,
                f"All distance ranges are valid (to_km > from_km)"
            ))
    
    def _compare_with_baseline(self, current_segments: List[Dict[str, Any]], baseline_segments: List[Dict[str, Any]]) -> None:
        """Compare current results with baseline results."""
        
        # Create lookup dictionaries
        current_dict = {s['seg_id']: s for s in current_segments}
        baseline_dict = {s['seg_id']: s for s in baseline_segments}
        
        # Check for segments that disappeared
        disappeared = []
        for seg_id in baseline_dict:
            if seg_id not in current_dict:
                disappeared.append(seg_id)
        
        if disappeared:
            self.add_result(FlowValidationResult(
                "baseline_comparison_disappeared_segments",
                False,
                f"Segments that disappeared from baseline: {disappeared}"
            ))
        
        # Check for convergence changes
        convergence_changes = []
        for seg_id in current_dict:
            if seg_id in baseline_dict:
                current_conv = current_dict[seg_id].get('has_convergence', False)
                baseline_conv = baseline_dict[seg_id].get('has_convergence', False)
                
                if current_conv != baseline_conv:
                    convergence_changes.append({
                        'seg_id': seg_id,
                        'baseline_convergence': baseline_conv,
                        'current_convergence': current_conv
                    })
        
        if convergence_changes:
            self.add_result(FlowValidationResult(
                "baseline_comparison_convergence_changes",
                False,
                f"Convergence detection changes: {len(convergence_changes)} segments",
                {"changes": convergence_changes}
            ))
        else:
            self.add_result(FlowValidationResult(
                "baseline_comparison_convergence_changes",
                True,
                "No convergence detection changes from baseline"
            ))
    
    def run_comprehensive_validation(self, segments: List[Dict[str, Any]], baseline_segments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Run all validation checks."""
        
        print("🔍 Running comprehensive flow analysis validation...")
        
        # Run all validation checks
        self.validate_data_integrity(segments)
        self.validate_convergence_detection(segments, baseline_segments)
        self.validate_sample_data_quality(segments)
        self.validate_unit_consistency(segments)
        
        # Calculate summary statistics
        total_checks = len(self.results)
        passed_checks = sum(1 for r in self.results if r.passed)
        failed_checks = total_checks - passed_checks
        
        summary = {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "success_rate": (passed_checks / total_checks * 100) if total_checks > 0 else 0,
            "validation_results": [r.to_dict() for r in self.results],
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"✅ Validation complete: {passed_checks}/{total_checks} checks passed ({summary['success_rate']:.1f}%)")
        
        if failed_checks > 0:
            print("❌ Failed checks:")
            for result in self.results:
                if not result.passed:
                    print(f"   - {result.check_name}: {result.message}")
        
        return summary
    
    def export_validation_report(self, output_path: str, summary: Dict[str, Any]) -> None:
        """Export validation results to JSON file."""
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Validation report exported to: {output_path}")


def validate_flow_analysis_results(segments: List[Dict[str, Any]], baseline_segments: Optional[List[Dict[str, Any]]] = None, export_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to run comprehensive validation.
    
    Args:
        segments: Current flow analysis results
        baseline_segments: Optional baseline results for comparison
        export_path: Optional path to export validation report
        
    Returns:
        Validation summary dictionary
    """
    
    validator = FlowValidationFramework()
    summary = validator.run_comprehensive_validation(segments, baseline_segments)
    
    if export_path:
        validator.export_validation_report(export_path, summary)
    
    return summary


if __name__ == "__main__":
    """Command-line interface for validation framework."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate flow analysis results against expected baseline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate with expected results (flow frozen for Issue #233)
  python app/flow_validation.py --expected data/flow_expected_results.csv
  
  # Validate segments JSON with baseline
  python app/flow_validation.py segments.json --baseline baseline.json
  
  # Validate and save report
  python app/flow_validation.py segments.json --baseline baseline.json --output report.json
        """
    )
    
    parser.add_argument('segments_file', nargs='?',
                       help='Path to segments JSON file')
    parser.add_argument('--expected', '-e',
                       help='Path to expected results CSV (flow oracle for Issue #233)')
    parser.add_argument('--baseline', '-b',
                       help='Path to baseline segments JSON for comparison')
    parser.add_argument('--output', '-o',
                       help='Path to save validation report JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Validate input
    if not args.segments_file and not args.expected:
        parser.print_help()
        print("\nError: Either segments_file or --expected must be provided")
        sys.exit(1)
    
    try:
        # Load segments from JSON file
        segments = None
        if args.segments_file:
            with open(args.segments_file, 'r') as f:
                segments = json.load(f)
            if args.verbose:
                print(f"Loaded segments from: {args.segments_file}")
        
        # Load baseline/expected results
        baseline_segments = None
        if args.expected:
            # Load expected results from CSV (flow oracle)
            expected_df = pd.read_csv(args.expected)
            # Convert to segments format for validation
            # This assumes flow_expected_results.csv has compatible schema
            baseline_segments = expected_df.to_dict('records')
            if args.verbose:
                print(f"Loaded expected results from: {args.expected}")
                print(f"  -> {len(baseline_segments)} expected segments")
        elif args.baseline:
            with open(args.baseline, 'r') as f:
                baseline_segments = json.load(f)
            if args.verbose:
                print(f"Loaded baseline from: {args.baseline}")
        
        # Run validation
        if args.verbose:
            print("\nRunning flow validation...")
        
        summary = validate_flow_analysis_results(segments, baseline_segments, args.output)
        
        # Display summary
        print("\n" + "="*60)
        print("FLOW VALIDATION SUMMARY")
        print("="*60)
        print(f"Total checks: {summary['total_checks']}")
        print(f"Passed checks: {summary['passed_checks']}")
        print(f"Failed checks: {summary['failed_checks']}")
        print(f"Success rate: {summary.get('success_rate', 0):.1f}%")
        
        if summary['failed_checks'] > 0:
            print("\n⚠️  VALIDATION FAILED")
            print("Review failed checks for details")
        else:
            print("\n✅ VALIDATION PASSED")
            print("All checks succeeded - Flow is frozen for Issue #233")
        
        if args.output:
            print(f"\nDetailed report saved to: {args.output}")
        
        # Exit with appropriate code
        sys.exit(0 if summary['failed_checks'] == 0 else 1)
        
    except FileNotFoundError as e:
        print(f"\nError: File not found - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
