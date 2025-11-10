#!/usr/bin/env python3
"""
QA Regression Baseline for Issue #243 Fix

This test verifies that 10K runners appear at correct start times
and that no phantom late blocks exist.

Baseline established: 2025-10-15
Expected behavior:
- Full: First density at A1 ~07:00
- 10K:  First density at A1 ~07:20 (Issue #243 fix)
- Half: First density at A1 ~07:40
- No phantom late blocks for any event
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta


def get_latest_bins() -> pd.DataFrame:
    """Load the most recent bins.parquet file."""
    reports_dir = Path("reports")
    date_dirs = sorted([d for d in reports_dir.iterdir() 
                       if d.is_dir() and d.name.startswith("2025-")], 
                       reverse=True)
    
    for date_dir in date_dirs:
        bins_file = date_dir / "bins.parquet"
        if bins_file.exists():
            df = pd.read_parquet(bins_file)
            df['t_start'] = pd.to_datetime(df['t_start'])
            return df
    
    raise FileNotFoundError("No bins.parquet found")


def test_event_start_times():
    """Verify each event starts at correct time."""
    bins_df = get_latest_bins()
    a1_bins = bins_df[bins_df['segment_id'] == 'A1'].copy()
    
    # Get first non-zero density for A1
    nonzero = a1_bins[a1_bins['density'] > 0].sort_values('t_start')
    first_time = nonzero['t_start'].min()
    
    # Should be Full start at 07:00
    expected_full_start = first_time.replace(hour=7, minute=0, second=0)
    assert first_time == expected_full_start, \
        f"First A1 density at {first_time}, expected {expected_full_start}"
    
    print(f"✅ Full Marathon starts at correct time: {first_time}")
    
    # Check 10K at 07:20
    bins_10k_start = a1_bins[
        (a1_bins['t_start'] >= first_time.replace(hour=7, minute=20)) &
        (a1_bins['t_start'] < first_time.replace(hour=7, minute=22))
    ]
    max_density_10k = bins_10k_start['density'].max()
    
    assert max_density_10k > 0, \
        f"No 10K density at 07:20! Max density = {max_density_10k}"
    
    print(f"✅ 10K Marathon starts at correct time: 07:20 (density={max_density_10k:.4f})")
    
    # Check Half at 07:40
    bins_half_start = a1_bins[
        (a1_bins['t_start'] >= first_time.replace(hour=7, minute=40)) &
        (a1_bins['t_start'] < first_time.replace(hour=7, minute=42))
    ]
    max_density_half = bins_half_start['density'].max()
    
    assert max_density_half > 0, \
        f"No Half density at 07:40! Max density = {max_density_half}"
    
    print(f"✅ Half Marathon starts at correct time: 07:40 (density={max_density_half:.4f})")


def test_no_phantom_late_blocks():
    """Verify no phantom late 10K blocks exist."""
    bins_df = get_latest_bins()
    a1_bins = bins_df[bins_df['segment_id'] == 'A1'].copy()
    
    # Check for phantom block at 08:12-08:26 (Issue #243)
    first_time = a1_bins[a1_bins['density'] > 0]['t_start'].min()
    phantom_window_start = first_time.replace(hour=8, minute=12)
    phantom_window_end = first_time.replace(hour=8, minute=26)
    
    phantom_bins = a1_bins[
        (a1_bins['t_start'] >= phantom_window_start) &
        (a1_bins['t_start'] < phantom_window_end)
    ]
    max_phantom_density = phantom_bins['density'].max()
    
    # Should be near-zero (accounting for possible tail runners)
    assert max_phantom_density < 0.1, \
        f"Phantom late block detected! Density at 08:12-08:26 = {max_phantom_density:.4f}"
    
    print(f"✅ No phantom late blocks (08:12-08:26 density={max_phantom_density:.4f})")


def test_density_attenuation():
    """Verify density attenuates naturally downstream."""
    bins_df = get_latest_bins()
    
    # Get peak densities for early segments
    segment_peaks = {}
    for seg_id in ['A1', 'A2', 'A3']:
        seg_bins = bins_df[bins_df['segment_id'] == seg_id]
        segment_peaks[seg_id] = seg_bins['density'].max()
    
    # Should decrease downstream
    assert segment_peaks['A1'] > segment_peaks['A2'], \
        f"A1 peak ({segment_peaks['A1']:.3f}) should be > A2 ({segment_peaks['A2']:.3f})"
    
    assert segment_peaks['A2'] > segment_peaks['A3'], \
        f"A2 peak ({segment_peaks['A2']:.3f}) should be > A3 ({segment_peaks['A3']:.3f})"
    
    print(f"✅ Density attenuates naturally: A1={segment_peaks['A1']:.3f} → "
          f"A2={segment_peaks['A2']:.3f} → A3={segment_peaks['A3']:.3f}")


def test_segment_timeline_baseline():
    """Generate baseline timeline for all segments (QA reference)."""
    bins_df = get_latest_bins()
    
    baseline = []
    for seg_id in sorted(bins_df['segment_id'].unique()):
        seg_bins = bins_df[bins_df['segment_id'] == seg_id]
        nonzero = seg_bins[seg_bins['density'] > 0]
        
        if len(nonzero) > 0:
            baseline.append({
                'segment_id': seg_id,
                'first_nonzero': nonzero['t_start'].min().strftime('%H:%M'),
                'last_nonzero': nonzero['t_start'].max().strftime('%H:%M'),
                'peak_density': nonzero['density'].max(),
                'mean_density': nonzero['density'].mean()
            })
    
    baseline_df = pd.DataFrame(baseline)
    print("\n📊 QA Baseline Timeline:")
    print(baseline_df.to_string(index=False))
    
    return baseline_df


if __name__ == '__main__':
    print("🧪 Running QA Regression Tests (Issue #243 Fix Verification)\n")
    print("="*80)
    
    try:
        test_event_start_times()
        test_no_phantom_late_blocks()
        test_density_attenuation()
        baseline_df = test_segment_timeline_baseline()
        
        print("\n" + "="*80)
        print("🎉 ALL REGRESSION TESTS PASSED!")
        print("\nBaseline established for future runs. Any deviation from this timeline")
        print("indicates a regression in event anchoring or window mapping.")
        
    except AssertionError as e:
        print(f"\n❌ REGRESSION TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        exit(1)

