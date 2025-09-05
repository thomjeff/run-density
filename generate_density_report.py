#!/usr/bin/env python3
"""
Density Report Generator CLI

A command-line interface for generating density analysis reports.
This replaces the need for hand-crafted report generation scripts.
"""

import argparse
import sys
import os
from typing import Dict

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from density_report import generate_density_report, generate_simple_density_report


def main():
    parser = argparse.ArgumentParser(
        description="Generate density analysis reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate full report with per-event analysis
  python generate_density_report.py data/your_pace_data.csv data/density.csv

  # Generate simple report without per-event analysis
  python generate_density_report.py data/your_pace_data.csv data/density.csv --simple

  # Custom parameters
  python generate_density_report.py data/your_pace_data.csv data/density.csv \\
    --step-km 0.2 --time-window 60 --output-dir reports/custom
        """
    )
    
    parser.add_argument("pace_csv", help="Path to pace data CSV file")
    parser.add_argument("density_csv", help="Path to density configuration CSV file")
    parser.add_argument("--start-times", nargs="+", 
                       help="Event start times in format 'Event:HH:MM' (e.g., 'Full:07:00 10K:07:20 Half:07:40')")
    parser.add_argument("--step-km", type=float, default=0.3, 
                       help="Step size for density calculations in km (default: 0.3)")
    parser.add_argument("--time-window", type=int, default=30, 
                       help="Time window for density calculations in seconds (default: 30)")
    parser.add_argument("--output-dir", default="reports/analysis", 
                       help="Output directory for reports (default: reports/analysis)")
    parser.add_argument("--simple", action="store_true", 
                       help="Generate simple report without per-event analysis")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.pace_csv):
        print(f"❌ Error: Pace CSV file not found: {args.pace_csv}")
        sys.exit(1)
    
    if not os.path.exists(args.density_csv):
        print(f"❌ Error: Density CSV file not found: {args.density_csv}")
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
            print(f"🔍 Generating density report...")
            print(f"   Pace CSV: {args.pace_csv}")
            print(f"   Density CSV: {args.density_csv}")
            print(f"   Step size: {args.step_km}km")
            print(f"   Time window: {args.time_window}s")
            print(f"   Output directory: {args.output_dir}")
            print(f"   Include per-event: {not args.simple}")
        
        if args.simple:
            results = generate_simple_density_report(
                pace_csv=args.pace_csv,
                density_csv=args.density_csv,
                start_times=start_times,
                step_km=args.step_km,
                time_window_s=args.time_window
            )
        else:
            results = generate_density_report(
                pace_csv=args.pace_csv,
                density_csv=args.density_csv,
                start_times=start_times,
                step_km=args.step_km,
                time_window_s=args.time_window,
                include_per_event=True,
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
