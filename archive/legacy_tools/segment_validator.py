#!/usr/bin/env python3
"""
SEGMENT VALIDATOR: Bottom-up analysis utility for validating algorithm results.
This utility can analyze any segment to verify overtaking counts and convergence points.
"""

import pandas as pd
import numpy as np
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime

def calculate_arrival_time(start_time_sec: float, start_offset_sec: int, km: float, pace_min_per_km: float) -> float:
    """Calculate arrival time at km mark in seconds from midnight."""
    # start_time_sec is already in seconds, no need to convert
    total_start_sec = start_time_sec + start_offset_sec  # Add start offset
    travel_time_sec = pace_min_per_km * 60.0 * km  # Convert pace to seconds per km, then multiply by distance
    return total_start_sec + travel_time_sec

def format_time_clock(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def check_time_interval_intersection(
    a_enter: float, a_exit: float, 
    b_enter: float, b_exit: float,
    min_overlap_duration: float = 5.0
) -> bool:
    """Check if two time intervals intersect with minimum duration."""
    overlap_start = max(a_enter, b_enter)
    overlap_end = min(a_exit, b_exit)
    overlap_duration = overlap_end - overlap_start
    has_overlap = (overlap_end > overlap_start) and (overlap_duration >= min_overlap_duration)
    
    # Debug output for first few checks
    if has_overlap:
        print(f"    DEBUG: Overlap found - {overlap_duration:.1f}s")
    
    return has_overlap

def extract_segment_data(df: pd.DataFrame, event_a: str, event_b: str, 
                        expected_count_a: int, expected_count_b: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Extract the expected number of runners for each event in a segment."""
    
    df_a = df[df['event'] == event_a].copy()
    df_b = df[df['event'] == event_b].copy()
    
    # For B1: 10K runners 1000-1071 (72 runners), Full runners 2867-2897 (31 runners)
    # For A1c: 10K runners 1529-1617 (89 runners), Half runners 1618-1950 (333 runners)
    
    if event_a == '10K' and event_b == 'Full':
        # B1 segment: 10K runners 1000-1071, Full runners 2867-2897
        df_a = df_a[(df_a['runner_id'] >= 1000) & (df_a['runner_id'] <= 1071)]
        df_b = df_b[(df_b['runner_id'] >= 2867) & (df_b['runner_id'] <= 2897)]
    elif event_a == '10K' and event_b == 'Half':
        # A1c segment: 10K runners 1529-1617, Half runners 1618-1950
        df_a = df_a[(df_a['runner_id'] >= 1529) & (df_a['runner_id'] <= 1617)]
        df_b = df_b[(df_b['runner_id'] >= 1618) & (df_b['runner_id'] <= 1950)]
    else:
        # Default: sort by pace and take expected counts
        df_a = df_a.sort_values('pace')
        df_b = df_b.sort_values('pace')
        
        if len(df_a) >= expected_count_a:
            df_a = df_a.head(expected_count_a)
        if len(df_b) >= expected_count_b:
            df_b = df_b.head(expected_count_b)
    
    return df_a, df_b

def validate_segment_overlaps(
    df_a: pd.DataFrame, 
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    convergence_point: float,
    zone_end: float,
    min_overlap_duration: float = 5.0
) -> Dict:
    """Validate overlaps for a specific segment."""
    
    # Get start times in seconds
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate arrival times for all runners
    print(f"    Calculating arrival times...")
    print(f"    start_a: {start_a} seconds ({start_a/3600:.2f}h)")
    print(f"    start_b: {start_b} seconds ({start_b/3600:.2f}h)")
    
    df_a['enter_time'] = df_a.apply(
        lambda row: calculate_arrival_time(start_a, row['start_offset'], convergence_point, row['pace']), axis=1
    )
    df_a['exit_time'] = df_a.apply(
        lambda row: calculate_arrival_time(start_a, row['start_offset'], zone_end, row['pace']), axis=1
    )
    
    df_b['enter_time'] = df_b.apply(
        lambda row: calculate_arrival_time(start_b, row['start_offset'], convergence_point, row['pace']), axis=1
    )
    df_b['exit_time'] = df_b.apply(
        lambda row: calculate_arrival_time(start_b, row['start_offset'], zone_end, row['pace']), axis=1
    )
    
    # Debug first few calculated times
    print(f"    Sample 10K times:")
    for i, (_, runner) in enumerate(df_a.head(2).iterrows()):
        print(f"      Runner {runner['runner_id']}: {runner['enter_time']/3600:.2f}h to {runner['exit_time']/3600:.2f}h")
    
    print(f"    Sample Full times:")
    for i, (_, runner) in enumerate(df_b.head(2).iterrows()):
        print(f"      Runner {runner['runner_id']}: {runner['enter_time']/3600:.2f}h to {runner['exit_time']/3600:.2f}h")
    
    # Find all overlaps
    overlaps_found = []
    a_bibs = set()
    b_bibs = set()
    
    # Test every single runner pair
    print(f"    Testing {len(df_a)} × {len(df_b)} = {len(df_a) * len(df_b)} runner pairs...")
    
    for i, (_, runner_a) in enumerate(df_a.iterrows()):
        a_enter = runner_a['enter_time']
        a_exit = runner_a['exit_time']
        
        for j, (_, runner_b) in enumerate(df_b.iterrows()):
            b_enter = runner_b['enter_time']
            b_exit = runner_b['exit_time']
            
            # Debug first few pairs
            if i < 2 and j < 2:
                print(f"      Pair {i},{j}: 10K {runner_a['runner_id']} ({a_enter/3600:.2f}h to {a_exit/3600:.2f}h) vs Full {runner_b['runner_id']} ({b_enter/3600:.2f}h to {b_exit/3600:.2f}h)")
            
            # Check for time interval intersection
            if check_time_interval_intersection(a_enter, a_exit, b_enter, b_exit, min_overlap_duration):
                overlap_start = max(a_enter, b_enter)
                overlap_end = min(a_exit, b_exit)
                overlap_duration = overlap_end - overlap_start
                
                overlaps_found.append({
                    'a_runner': runner_a['runner_id'],
                    'a_pace': runner_a['pace'],
                    'a_enter': a_enter,
                    'a_exit': a_exit,
                    'b_runner': runner_b['runner_id'],
                    'b_pace': runner_b['pace'],
                    'b_enter': b_enter,
                    'b_exit': b_exit,
                    'overlap_duration': overlap_duration,
                    'overlap_start': overlap_start,
                    'overlap_end': overlap_end
                })
                
                # Track unique runners
                a_bibs.add(runner_a['runner_id'])
                b_bibs.add(runner_b['runner_id'])
    
    return {
        'total_overlaps': len(overlaps_found),
        'unique_a_runners': len(a_bibs),
        'unique_b_runners': len(b_bibs),
        'a_bibs': sorted(list(a_bibs)),
        'b_bibs': sorted(list(b_bibs)),
        'overlaps_found': overlaps_found
    }

def create_comprehensive_csv_report(
    df_a: pd.DataFrame, 
    df_b: pd.DataFrame,
    validation_results: Dict,
    segment_name: str,
    event_a: str,
    event_b: str,
    convergence_point: float,
    zone_end: float,
    expected_count_a: int,
    expected_count_b: int,
    min_overlap_duration: float,
    output_dir: str = "audit"
) -> str:
    """Create a comprehensive CSV report including validation results and runner data."""
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H%M")
    filename = f"{output_dir}/{timestamp} {segment_name} Validation Report.csv"
    
    # Create a list to hold all the data rows
    all_rows = []
    
    # Add validation summary section
    all_rows.append(["SEGMENT VALIDATION SUMMARY"])
    all_rows.append([])
    all_rows.append(["Segment", segment_name])
    all_rows.append(["Event A", event_a])
    all_rows.append(["Event B", event_b])
    all_rows.append(["Convergence Point (km)", f"{convergence_point:.2f}"])
    all_rows.append(["Zone End (km)", f"{zone_end:.2f}"])
    all_rows.append(["Zone Length (km)", f"{zone_end - convergence_point:.2f}"])
    all_rows.append(["Min Overlap Duration (s)", f"{min_overlap_duration:.1f}"])
    all_rows.append([])
    
    # Add expected vs actual counts
    all_rows.append(["COUNT VALIDATION"])
    all_rows.append([])
    all_rows.append(["Metric", "Expected", "Actual", "Status"])
    all_rows.append([f"{event_a} Runners", expected_count_a, validation_results["unique_a_runners"], 
                    "✅ MATCH" if expected_count_a == validation_results["unique_a_runners"] else "❌ MISMATCH"])
    all_rows.append([f"{event_b} Runners", expected_count_b, validation_results["unique_b_runners"], 
                    "✅ MATCH" if expected_count_b == validation_results["unique_b_runners"] else "❌ MISMATCH"])
    all_rows.append([])
    
    # Add overlap statistics
    all_rows.append(["OVERLAP STATISTICS"])
    all_rows.append([])
    all_rows.append(["Total Overlaps Found", validation_results["total_overlaps"]])
    all_rows.append(["Unique Overlapping Runners", f"{event_a}: {validation_results['unique_a_runners']}, {event_b}: {validation_results['unique_b_runners']}"])
    all_rows.append([])
    
    # Add sample overlaps
    if validation_results["overlaps_found"]:
        all_rows.append(["SAMPLE OVERLAPS (First 10)"])
        all_rows.append([])
        all_rows.append(["#", f"{event_a} Runner", f"{event_a} Pace", f"{event_b} Runner", f"{event_b} Pace", "Overlap Start", "Overlap End", "Duration (s)"])
        
        for i, overlap in enumerate(validation_results['overlaps_found'][:10], 1):
            overlap_start_clock = format_time_clock(overlap['overlap_start'])
            overlap_end_clock = format_time_clock(overlap['overlap_end'])
            
            all_rows.append([
                i,
                overlap['a_runner'],
                f"{overlap['a_pace']:.2f}",
                overlap['b_runner'],
                f"{overlap['b_pace']:.2f}",
                overlap_start_clock,
                overlap_end_clock,
                f"{overlap['overlap_duration']:.1f}"
            ])
        
        if len(validation_results['overlaps_found']) > 10:
            all_rows.append([f"... and {len(validation_results['overlaps_found']) - 10} more overlaps"])
        all_rows.append([])
    
    # Add runner data section
    all_rows.append([f"{event_a} RUNNER DATA"])
    all_rows.append([])
    
    # Add headers for runner data
    df_a_with_times = df_a.copy()
    start_times = {'Full': 420, 'Half': 460, '10K': 440}
    start_a = start_times.get(event_a, 0) * 60.0
    
    # Calculate arrival times for display
    df_a_with_times['enter_time_clock'] = df_a_with_times.apply(
        lambda row: format_time_clock(start_a + row['start_offset'] + row['pace'] * 60.0 * convergence_point), axis=1
    )
    df_a_with_times['exit_time_clock'] = df_a_with_times.apply(
        lambda row: format_time_clock(start_a + row['start_offset'] + row['pace'] * 60.0 * zone_end), axis=1
    )
    
    # Add start_time column for reference
    df_a_with_times['start_time'] = start_times.get(event_a, 0)
    
    # Reorder columns for readability
    column_order = ['event', 'runner_id', 'pace', 'distance', 'start_time', 'start_offset', 'enter_time_clock', 'exit_time_clock']
    df_a_with_times = df_a_with_times[column_order]
    
    # Add runner data rows
    all_rows.append(list(df_a_with_times.columns))
    for _, row in df_a_with_times.iterrows():
        all_rows.append(list(row))
    
    all_rows.append([])
    
    # Add event B runner data
    all_rows.append([f"{event_b} RUNNER DATA"])
    all_rows.append([])
    
    df_b_with_times = df_b.copy()
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate arrival times for display
    df_b_with_times['enter_time_clock'] = df_b_with_times.apply(
        lambda row: format_time_clock(start_b + row['start_offset'] + row['pace'] * 60.0 * convergence_point), axis=1
    )
    df_b_with_times['exit_time_clock'] = df_b_with_times.apply(
        lambda row: format_time_clock(start_b + row['start_offset'] + row['pace'] * 60.0 * zone_end), axis=1
    )
    
    # Add start_time column for reference
    df_b_with_times['start_time'] = start_times.get(event_b, 0)
    
    # Reorder columns for readability
    df_b_with_times = df_b_with_times[column_order]
    
    # Add runner data rows
    all_rows.append(list(df_b_with_times.columns))
    for _, row in df_b_with_times.iterrows():
        all_rows.append(list(row))
    
    # Convert to DataFrame and save
    report_df = pd.DataFrame(all_rows)
    report_df.to_csv(filename, index=False, header=False)
    
    return filename

def create_test_data_csv(df_a: pd.DataFrame, df_b: pd.DataFrame, 
                        segment_name: str, output_dir: str = "audit") -> str:
    """Create a test data CSV file for the segment (legacy function for backward compatibility)."""
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)
    
    # Combine the dataframes
    combined_df = pd.concat([df_a, df_b], ignore_index=True)
    
    # Add start_time column for reference
    start_times = {'Full': 420, 'Half': 460, '10K': 440}
    combined_df['start_time'] = combined_df['event'].map(start_times)
    
    # Reorder columns to match your format
    column_order = ['event', 'runner_id', 'pace', 'distance', 'start_time', 'start_offset']
    combined_df = combined_df[column_order]
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H%M")
    filename = f"{output_dir}/{timestamp} {segment_name} Test Data.csv"
    
    # Save to CSV
    combined_df.to_csv(filename, index=False)
    
    return filename

def run_segment_validation(
    pace_csv: str,
    segment_name: str,
    event_a: str,
    event_b: str,
    convergence_point: float,
    zone_end: float,
    expected_count_a: int,
    expected_count_b: int,
    min_overlap_duration: float = 5.0,
    create_test_data: bool = True,
    create_comprehensive_report: bool = True
) -> Dict:
    """Run complete validation for a segment."""
    
    print(f'🧪 SEGMENT VALIDATION: {segment_name}')
    print('=' * 60)
    
    # Load pace data
    df = pd.read_csv(pace_csv)
    print(f'📊 Loaded {len(df)} total runners from {pace_csv}')
    
    # Extract segment data
    df_a, df_b = extract_segment_data(df, event_a, event_b, expected_count_a, expected_count_b)
    print(f'🏃‍♂️ Extracted {len(df_a)} {event_a} runners and {len(df_b)} {event_b} runners')
    
    # Define start times
    start_times = {'Full': 420, 'Half': 460, '10K': 440}
    
    # Validate overlaps
    print(f'\n🔍 VALIDATING OVERLAPS...')
    print(f'  Convergence Zone: {convergence_point}km to {zone_end}km')
    print(f'  Start times: {event_a} {start_times[event_a]//60:02d}:{start_times[event_a]%60:02d}, {event_b} {start_times[event_b]//60:02d}:{start_times[event_b]%60:02d}')
    print(f'  Min overlap duration: {min_overlap_duration} seconds')
    
    validation_results = validate_segment_overlaps(
        df_a, df_b, event_a, event_b, start_times, 
        convergence_point, zone_end, min_overlap_duration
    )
    
    # Display results
    print(f'\n📊 VALIDATION RESULTS:')
    print('-' * 50)
    print(f'Total overlaps found: {validation_results["total_overlaps"]:,}')
    print(f'Unique {event_a} runners: {validation_results["unique_a_runners"]}')
    print(f'Unique {event_b} runners: {validation_results["unique_b_runners"]}')
    
    # Compare with expected counts
    print(f'\n🎯 COMPARISON WITH EXPECTED:')
    print('-' * 50)
    print(f'Expected: {event_a} = {expected_count_a}, {event_b} = {expected_count_b}')
    print(f'Actual: {event_a} = {validation_results["unique_a_runners"]}, {event_b} = {validation_results["unique_b_runners"]}')
    
    if (validation_results["unique_a_runners"] == expected_count_a and 
        validation_results["unique_b_runners"] == expected_count_b):
        print('✅ COUNTS MATCH - Algorithm is accurate!')
    else:
        print('❌ COUNT DISCREPANCY - Algorithm needs investigation!')
        if validation_results["unique_a_runners"] != expected_count_a:
            print(f'  {event_a}: Expected {expected_count_a}, got {validation_results["unique_a_runners"]}')
        if validation_results["unique_b_runners"] != expected_count_b:
            print(f'  {event_b}: Expected {expected_count_b}, got {validation_results["unique_b_runners"]}')
    
    # Show sample overlaps
    print(f'\n🏃‍♂️ SAMPLE OVERLAPS (First 5):')
    print('-' * 50)
    for i, overlap in enumerate(validation_results['overlaps_found'][:5]):
        overlap_start_clock = format_time_clock(overlap['overlap_start'])
        overlap_end_clock = format_time_clock(overlap['overlap_end'])
        print(f"  {i+1}. {event_a} Runner {overlap['a_runner']} (pace {overlap['a_pace']:.2f}) vs {event_b} Runner {overlap['b_runner']} (pace {overlap['b_pace']:.2f})")
        print(f"     Overlap: {overlap_start_clock} to {overlap_end_clock} ({overlap['overlap_duration']:.1f}s)")
    
    if len(validation_results['overlaps_found']) > 5:
        print(f"  ... and {len(validation_results['overlaps_found']) - 5} more overlaps")
    
    # Create comprehensive CSV report if requested
    if create_comprehensive_report:
        comprehensive_file = create_comprehensive_csv_report(
            df_a, df_b, validation_results, segment_name, event_a, event_b,
            convergence_point, zone_end, expected_count_a, expected_count_b, min_overlap_duration
        )
        print(f'\n📋 Comprehensive report saved to: {comprehensive_file}')
    
    # Create test data CSV if requested
    if create_test_data:
        test_data_file = create_test_data_csv(df_a, df_b, segment_name)
        print(f'\n💾 Test data saved to: {test_data_file}')
    
    return validation_results

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Validate segment overlap counts')
    parser.add_argument('--pace-csv', required=True, help='Path to pace CSV file')
    parser.add_argument('--segment', required=True, help='Segment name (e.g., B1, A1c)')
    parser.add_argument('--event-a', required=True, help='First event name')
    parser.add_argument('--event-b', required=True, help='Second event name')
    parser.add_argument('--convergence-point', type=float, required=True, help='Convergence point in km')
    parser.add_argument('--zone-end', type=float, required=True, help='End of convergence zone in km')
    parser.add_argument('--count-a', type=int, required=True, help='Expected count for event A')
    parser.add_argument('--count-b', type=int, required=True, help='Expected count for event B')
    parser.add_argument('--min-duration', type=float, default=5.0, help='Minimum overlap duration in seconds')
    parser.add_argument('--no-test-data', action='store_true', help='Skip creating test data CSV')
    parser.add_argument('--no-comprehensive', action='store_true', help='Skip creating comprehensive CSV report')
    
    args = parser.parse_args()
    
    try:
        results = run_segment_validation(
            pace_csv=args.pace_csv,
            segment_name=args.segment,
            event_a=args.event_a,
            event_b=args.event_b,
            convergence_point=args.convergence_point,
            zone_end=args.zone_end,
            expected_count_a=args.count_a,
            expected_count_b=args.count_b,
            min_overlap_duration=args.min_duration,
            create_test_data=not args.no_test_data,
            create_comprehensive_report=not args.no_comprehensive
        )
        
        # Exit with error code if counts don't match
        if (results["unique_a_runners"] != args.count_a or 
            results["unique_b_runners"] != args.count_b):
            sys.exit(1)
            
    except Exception as e:
        print(f'❌ ERROR: {e}')
        sys.exit(1)

if __name__ == "__main__":
    # Example usage for B1
    if len(sys.argv) == 1:
        print('🔍 SEGMENT VALIDATOR - Example Usage')
        print('=' * 50)
        print('Command line usage:')
        print('python segment_validator.py --pace-csv data/your_pace_data.csv \\')
        print('  --segment B1 --event-a 10K --event-b Full \\')
        print('  --convergence-point 3.48 --zone-end 4.25 \\')
        print('  --count-a 71 --count-b 29')
        print()
        print('Or run the interactive example below:')
        print()
        
        # Run example for B1
        try:
            results = run_segment_validation(
                pace_csv='data/your_pace_data.csv',
                segment_name='B1',
                event_a='10K',
                event_b='Full',
                convergence_point=3.48,
                zone_end=4.25,
                expected_count_a=71,
                expected_count_b=29,
                min_overlap_duration=5.0,
                create_test_data=True,
                create_comprehensive_report=True
            )
        except FileNotFoundError:
            print('❌ Pace CSV not found. Please run with --pace-csv argument.')
    else:
        main()
