#!/usr/bin/env python3
"""
Temporal Flow Report Generator CLI

A command-line interface for generating temporal flow analysis reports.
This replaces the need for hand-crafted report generation scripts.
"""

import argparse
import sys
import os
from typing import Dict

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.temporal_flow_report import generate_temporal_flow_report, generate_simple_temporal_flow_report


def main():
    parser = argparse.ArgumentParser(
        description="Generate temporal flow analysis reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate full temporal flow report
  python generate_temporal_flow_report.py data/your_pace_data.csv data/segments.csv

  # Generate simple report
  python generate_temporal_flow_report.py data/your_pace_data.csv data/segments.csv --simple

  # Custom parameters
  python generate_temporal_flow_report.py data/your_pace_data.csv data/segments.csv \\
    --min-overlap 10 --conflict-length 150 --output-dir reports/custom
        """
    )
    
    parser.add_argument("pace_csv", help="Path to pace data CSV file")
    parser.add_argument("segments_csv", help="Path to segments CSV file")
    parser.add_argument("--start-times", nargs="+", 
                       help="Event start times in format 'Event:HH:MM' (e.g., 'Full:07:00 10K:07:20 Half:07:40')")
    parser.add_argument("--min-overlap", type=float, default=5.0, 
                       help="Minimum overlap duration in seconds (default: 5.0)")
    parser.add_argument("--conflict-length", type=float, default=100.0, 
                       help="Conflict length in meters (default: 100.0)")
    parser.add_argument("--output-dir", default="reports/analysis", 
                       help="Output directory for reports (default: reports/analysis)")
    parser.add_argument("--simple", action="store_true", 
                       help="Generate simple report without deep dive analysis")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.pace_csv):
        print(f"❌ Error: Pace CSV file not found: {args.pace_csv}")
        sys.exit(1)
    
    if not os.path.exists(args.segments_csv):
        print(f"❌ Error: Segments CSV file not found: {args.segments_csv}")
        sys.exit(1)
    
    # Parse start times
    start_times = {}
    if args.start_times:
        for time_str in args.start_times:
            try:
                event, time_part = time_str.split(":")
                hours, minutes = map(int, time_part.split(":"))
                start_times[event] = hours * 60 + minutes
            except ValueError:
                print(f"❌ Error: Invalid start time format: {time_str}")
                print("Expected format: 'Event:HH:MM' (e.g., 'Full:07:00')")
                sys.exit(1)
    else:
        # Default start times
        start_times = {
            "Full": 7 * 60,      # 07:00
            "10K": 7 * 60 + 20,  # 07:20
            "Half": 7 * 60 + 40  # 07:40
        }
        if args.verbose:
            print("ℹ️  Using default start times: Full=07:00, 10K=07:20, Half=07:40")
    
    # Generate report
    try:
        if args.verbose:
            print(f"🔍 Generating temporal flow report...")
            print(f"   Pace CSV: {args.pace_csv}")
            print(f"   Segments CSV: {args.segments_csv}")
            print(f"   Min overlap duration: {args.min_overlap}s")
            print(f"   Conflict length: {args.conflict_length}m")
            print(f"   Output directory: {args.output_dir}")
            print(f"   Simple mode: {args.simple}")
        
        if args.simple:
            results = generate_simple_temporal_flow_report(
                pace_csv=args.pace_csv,
                segments_csv=args.segments_csv,
                start_times=start_times,
                min_overlap_duration=args.min_overlap,
                conflict_length_m=args.conflict_length
            )
        else:
            results = generate_temporal_flow_report(
                pace_csv=args.pace_csv,
                segments_csv=args.segments_csv,
                start_times=start_times,
                min_overlap_duration=args.min_overlap,
                conflict_length_m=args.conflict_length,
                output_dir=args.output_dir
            )
        
        if results.get("ok", False):
            print(f"✅ Report generated successfully!")
            print(f"📊 Report saved to: {results['report_path']}")
            if args.verbose:
                print(f"🕐 Generated at: {results['timestamp']}")
        else:
            print(f"❌ Report generation failed: {results.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
