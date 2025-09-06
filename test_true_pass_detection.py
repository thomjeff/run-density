#!/usr/bin/env python3
"""
Test script for true pass detection functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.flow import analyze_temporal_flow_segments
import pandas as pd

def test_true_pass_detection():
    """Test the true pass detection on a known convergent segment"""
    
    print("=== TESTING TRUE PASS DETECTION ===")
    
    # Load segments_new.csv
    segments_df = pd.read_csv('data/segments_new.csv')
    print(f"Loaded {len(segments_df)} segments")
    
    # Test with a known convergent segment (A2)
    a2_segment = segments_df[segments_df['seg_id'] == 'A2'].iloc[0]
    print(f"\nA2 segment: {a2_segment.to_dict()}")
    
    # Run analysis on A2
    print("\nRunning temporal flow analysis...")
    results = analyze_temporal_flow_segments(
        'data/runners.csv', 
        'data/segments_new.csv', 
        {'Full': 420, 'Half': 440, '10K': 460}
    )
    
    # Find A2 result
    a2_result = None
    for seg in results.get('segments', []):
        if seg.get('seg_id') == 'A2':
            a2_result = seg
            break
    
    if a2_result:
        print(f"\nA2 analysis result:")
        print(f"  has_convergence: {a2_result.get('has_convergence')}")
        print(f"  convergence_point: {a2_result.get('convergence_point')}")
        print(f"  overtaking_a: {a2_result.get('overtaking_a')}")
        print(f"  overtaking_b: {a2_result.get('overtaking_b')}")
        print(f"  sample_a: {a2_result.get('sample_a')}")
        print(f"  sample_b: {a2_result.get('sample_b')}")
        
        # Check if we have the expected data
        if a2_result.get('has_convergence'):
            print("✅ True pass detection working - convergence found")
            if a2_result.get('sample_a') and a2_result.get('sample_b'):
                print("✅ Sample data present")
            else:
                print("❌ Sample data missing")
        else:
            print("❌ True pass detection not finding convergence")
    else:
        print("❌ A2 segment not found in results")
    
    # Check total segments processed
    print(f"\nTotal segments processed: {len(results.get('segments', []))}")
    convergent_segments = [s for s in results.get('segments', []) if s.get('has_convergence')]
    print(f"Segments with convergence: {len(convergent_segments)}")
    
    if convergent_segments:
        print("\nConvergent segments:")
        for seg in convergent_segments:
            print(f"  {seg['seg_id']}: {seg['event_a']} vs {seg['event_b']} - CP: {seg.get('convergence_point')}")

if __name__ == "__main__":
    test_true_pass_detection()
