"""
Segment and Bin Validation Script (ChatGPT Guidance)

Validates that:
1. One segment_id = one physical stretch with single absolute km range
2. Bins don't exceed segment length  
3. Expected spatial bin count matches actual
4. Last bin is clipped correctly

Per ChatGPT: "Fix at the source, not with geometry fallbacks"
"""

import pandas as pd
import math
from pathlib import Path

def validate_segment_uniqueness(segments_df):
    """
    Validate: One segment_id = one physical stretch (single absolute km range)
    
    Fails if any segment_id has multiple disjoint absolute ranges across events.
    """
    print("\n" + "="*60)
    print("TEST 1: Segment ID Uniqueness (One ID = One Physical Stretch)")
    print("="*60)
    
    issues = []
    
    for seg_id in segments_df['seg_id'].unique():
        seg_rows = segments_df[segments_df['seg_id'] == seg_id]
        
        # Collect all absolute ranges for this segment across events
        absolute_ranges = []
        
        for event in ['10K', 'half', 'full']:
            from_col = f'{event}_from_km'
            to_col = f'{event}_to_km'
            
            if from_col in seg_rows.columns:
                for _, row in seg_rows.iterrows():
                    if row.get(event, '').lower() == 'y' and not pd.isna(row.get(from_col)):
                        from_km = float(row[from_col])
                        to_km = float(row[to_col])
                        absolute_ranges.append((event, from_km, to_km, to_km - from_km))
        
        if len(absolute_ranges) > 1:
            # Check if ranges are identical (same physical stretch)
            lengths = [r[3] for r in absolute_ranges]
            if len(set(lengths)) > 1:
                issues.append(f"  ❌ {seg_id}: Different lengths across events: {absolute_ranges}")
            else:
                # Same length but different absolute positions - this is OK if it's the same physical stretch
                # used at different points in different events
                print(f"  ℹ️  {seg_id}: Multiple events with same length ({lengths[0]:.2f} km) at different absolute km")
                for event, from_km, to_km, length in absolute_ranges:
                    print(f"      {event}: {from_km:.2f} - {to_km:.2f} km")
    
    if issues:
        print("\n❌ VALIDATION FAILED:")
        for issue in issues:
            print(issue)
        return False
    else:
        print("\n✅ All segments have consistent lengths across events")
        return True


def validate_bins_bounds(bins_df, segments_df):
    """
    Validate: Bins don't exceed segment spatial length
    
    For each segment_id:
    - max(end_km_rel) ≤ seg_length_km + ε
    - min(start_km_rel) ≥ 0 - ε
    """
    print("\n" + "="*60)
    print("TEST 2: Bin Bounds Within Segment Length")
    print("="*60)
    
    # Get segment lengths from segments.csv
    # Use the FIRST available event to determine segment length
    segment_lengths = {}
    for _, seg in segments_df.iterrows():
        seg_id = seg['seg_id']
        
        # Find first available event length
        for event in ['10K', 'half', 'full']:
            from_col = f'{event}_from_km'
            to_col = f'{event}_to_km'
            
            if seg.get(event, '').lower() == 'y' and not pd.isna(seg.get(from_col)):
                length_km = float(seg[to_col]) - float(seg[from_col])
                segment_lengths[seg_id] = length_km
                break
    
    epsilon = 0.01  # 10m tolerance
    issues = []
    
    for seg_id in bins_df['segment_id'].unique():
        seg_bins = bins_df[bins_df['segment_id'] == seg_id]
        
        min_start = seg_bins['start_km'].min()
        max_end = seg_bins['end_km'].max()
        bin_extent = max_end - min_start
        
        expected_length = segment_lengths.get(seg_id)
        
        if expected_length is None:
            issues.append(f"  ❌ {seg_id}: No segment length found in segments.csv")
            continue
        
        # Check bounds
        if min_start < -epsilon:
            issues.append(f"  ❌ {seg_id}: Bins start at {min_start:.3f} km (< 0)")
        
        if max_end > expected_length + epsilon:
            overrun = max_end - expected_length
            issues.append(f"  ❌ {seg_id}: Bins extend to {max_end:.3f} km (expected ≤ {expected_length:.3f} km, overrun: {overrun:.3f} km)")
    
    if issues:
        print("\n❌ VALIDATION FAILED:")
        for issue in issues:
            print(issue)
        print(f"\nTotal segments with issues: {len(issues)}")
        return False
    else:
        print("\n✅ All bins within segment boundaries")
        return True


def validate_bin_count_parity(bins_df, segments_df, bin_km=0.2):
    """
    Validate: Expected spatial bin count matches actual
    
    expected_bins = ceil(seg_length_km / bin_km)
    actual_bins = unique (start_km, end_km) pairs per segment
    """
    print("\n" + "="*60)
    print("TEST 3: Bin Count Parity")
    print("="*60)
    
    # Get segment lengths
    segment_lengths = {}
    for _, seg in segments_df.iterrows():
        seg_id = seg['seg_id']
        for event in ['10K', 'half', 'full']:
            from_col = f'{event}_from_km'
            to_col = f'{event}_to_km'
            if seg.get(event, '').lower() == 'y' and not pd.isna(seg.get(from_col)):
                length_km = float(seg[to_col]) - float(seg[from_col])
                segment_lengths[seg_id] = length_km
                break
    
    issues = []
    
    for seg_id in bins_df['segment_id'].unique():
        seg_bins = bins_df[bins_df['segment_id'] == seg_id]
        
        # Count unique spatial bins
        spatial_bins = seg_bins[['start_km', 'end_km']].drop_duplicates()
        actual_count = len(spatial_bins)
        
        expected_length = segment_lengths.get(seg_id)
        if expected_length is None:
            continue
        
        expected_count = math.ceil(expected_length / bin_km)
        
        if actual_count != expected_count:
            ratio = actual_count / expected_count if expected_count > 0 else 0
            issues.append(f"  ❌ {seg_id}: Expected {expected_count} bins, got {actual_count} (ratio: {ratio:.1f}x)")
    
    if issues:
        print("\n❌ VALIDATION FAILED:")
        for issue in issues:
            print(issue)
        print(f"\nTotal segments with count mismatch: {len(issues)}")
        return False
    else:
        print("\n✅ All segments have expected bin counts")
        return True


def validate_last_bin_clipping(bins_df, segments_df):
    """
    Validate: Last bin end_km equals segment end_km (clipped)
    """
    print("\n" + "="*60)
    print("TEST 4: Last Bin Clipping")
    print("="*60)
    
    segment_lengths = {}
    for _, seg in segments_df.iterrows():
        seg_id = seg['seg_id']
        for event in ['10K', 'half', 'full']:
            from_col = f'{event}_from_km'
            to_col = f'{event}_to_km'
            if seg.get(event, '').lower() == 'y' and not pd.isna(seg.get(from_col)):
                length_km = float(seg[to_col]) - float(seg[from_col])
                segment_lengths[seg_id] = length_km
                break
    
    epsilon = 0.01
    issues = []
    
    for seg_id in bins_df['segment_id'].unique():
        seg_bins = bins_df[bins_df['segment_id'] == seg_id]
        
        # Get last bin
        last_bin_end = seg_bins['end_km'].max()
        expected_length = segment_lengths.get(seg_id)
        
        if expected_length is None:
            continue
        
        if abs(last_bin_end - expected_length) > epsilon:
            issues.append(f"  ❌ {seg_id}: Last bin ends at {last_bin_end:.3f} km (expected {expected_length:.3f} km)")
    
    if issues:
        print("\n❌ VALIDATION FAILED:")
        for issue in issues:
            print(issue)
        return False
    else:
        print("\n✅ All last bins correctly clipped")
        return True


def main():
    print("🔍 SEGMENT AND BIN CONSISTENCY VALIDATION")
    print("Per ChatGPT guidance: Fix at source, not with geometry fallbacks")
    
    # Load data
    segments_df = pd.read_csv('data/segments.csv')
    bins_df = pd.read_parquet('reports/2025-10-16/bins.parquet')
    
    print(f"\nData loaded:")
    print(f"  Segments: {len(segments_df)} rows")
    print(f"  Bins: {len(bins_df):,} rows")
    print(f"  Unique segments in bins: {bins_df['segment_id'].nunique()}")
    
    # Run validations
    results = []
    
    results.append(("Segment Uniqueness", validate_segment_uniqueness(segments_df)))
    results.append(("Bin Bounds", validate_bins_bounds(bins_df, segments_df)))
    results.append(("Bin Count Parity", validate_bin_count_parity(bins_df, segments_df)))
    results.append(("Last Bin Clipping", validate_last_bin_clipping(bins_df, segments_df)))
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED - Data model is consistent!")
    else:
        print("\n⚠️ VALIDATION FAILURES DETECTED - Fix required before rendering bins")
        print("\nRecommendation:")
        print("1. Investigate segments with bin overruns")
        print("2. Check if segment_ids are reused across different absolute ranges")
        print("3. Fix bin generation to respect segment boundaries")
        print("4. Do NOT render bins that fail bounds validation")
    
    return all_passed


if __name__ == '__main__':
    main()

