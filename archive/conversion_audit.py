"""
Conversion Audit Utilities

Provides reusable functions for auditing segments_new.csv conversion logic
and validating event pair generation.
"""

import pandas as pd
from typing import Dict, List, Tuple, Any
from .flow import convert_segments_new_to_flow_format


def get_segment_events(segment: pd.Series) -> List[str]:
    """
    Extract events present in a segment row.
    
    Args:
        segment: Pandas Series representing a segment row
        
    Returns:
        List of event names ('Full', 'Half', '10K')
    """
    events = []
    if segment.get('full') == 'y':
        events.append('Full')
    if segment.get('half') == 'y':
        events.append('Half')
    if segment.get('10K') == 'y':
        events.append('10K')
    return events


def audit_segments_overview(segments_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate overview audit of segments_new.csv.
    
    Args:
        segments_df: DataFrame loaded from segments_new.csv
        
    Returns:
        Dictionary with audit summary
    """
    overtake_segments = segments_df[segments_df['flow_type'] != 'none']
    
    audit_results = {
        'total_segments': len(segments_df),
        'overtake_segments': len(overtake_segments),
        'segment_details': []
    }
    
    for _, seg in overtake_segments.iterrows():
        events = get_segment_events(seg)
        audit_results['segment_details'].append({
            'seg_id': seg['seg_id'],
            'events': events,
            'flow_type': seg.get('flow_type', 'N/A')
        })
    
    return audit_results


def audit_conversion_pairs(segments_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Audit the conversion function to see what pairs are generated.
    
    Args:
        segments_df: DataFrame loaded from segments_new.csv
        
    Returns:
        Dictionary with conversion audit results
    """
    converted_df = convert_segments_new_to_flow_format(segments_df)
    
    audit_results = {
        'total_converted_pairs': len(converted_df),
        'segments': {}
    }
    
    # Group by seg_id to see what pairs are generated
    for seg_id in converted_df['seg_id'].unique():
        seg_pairs = converted_df[converted_df['seg_id'] == seg_id]
        pairs_info = []
        
        for _, pair in seg_pairs.iterrows():
            pairs_info.append({
                'eventa': pair['eventa'],
                'eventb': pair['eventb'],
                'flow_type': pair.get('flow_type', 'N/A')
            })
        
        audit_results['segments'][seg_id] = {
            'pair_count': len(seg_pairs),
            'pairs': pairs_info
        }
    
    return audit_results


def validate_expected_pairs(converted_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate that expected pairs are present in conversion results.
    
    Args:
        converted_df: DataFrame from convert_segments_new_to_flow_format
        
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        'f1_validation': {},
        'b2_validation': {},
        'missing_pairs': []
    }
    
    # Check F1 pairs (should have 3 pairs: 10K/Half, 10K/Full, Half/Full)
    f1_pairs = converted_df[converted_df['seg_id'] == 'F1']
    validation_results['f1_validation'] = {
        'expected_count': 3,
        'actual_count': len(f1_pairs),
        'valid': len(f1_pairs) >= 3
    }
    
    if len(f1_pairs) < 3:
        expected_pairs = [('10K', 'Half'), ('10K', 'Full'), ('Half', 'Full')]
        for event_a, event_b in expected_pairs:
            found = False
            for _, pair in f1_pairs.iterrows():
                if (pair['eventa'] == event_a and pair['eventb'] == event_b) or \
                   (pair['eventa'] == event_b and pair['eventb'] == event_a):
                    found = True
                    break
            if not found:
                validation_results['missing_pairs'].append({
                    'seg_id': 'F1',
                    'missing_pair': f"{event_a} vs {event_b}"
                })
    
    # Check B2 segment
    b2_pairs = converted_df[converted_df['seg_id'] == 'B2']
    validation_results['b2_validation'] = {
        'expected_count': 1,
        'actual_count': len(b2_pairs),
        'valid': len(b2_pairs) >= 1,
        'missing': len(b2_pairs) == 0
    }
    
    return validation_results


def run_comprehensive_conversion_audit(segments_csv_path: str = 'data/segments_new.csv') -> Dict[str, Any]:
    """
    Run comprehensive audit of conversion logic.
    
    Args:
        segments_csv_path: Path to segments_new.csv file
        
    Returns:
        Dictionary with complete audit results
    """
    # Load segments data
    segments_df = pd.read_csv(segments_csv_path)
    
    # Run all audit functions
    overview = audit_segments_overview(segments_df)
    conversion = audit_conversion_pairs(segments_df)
    
    # Get the converted DataFrame for validation
    converted_df = convert_segments_new_to_flow_format(segments_df)
    validation = validate_expected_pairs(converted_df)
    
    return {
        'overview': overview,
        'conversion': conversion,
        'validation': validation,
        'summary': {
            'total_segments': overview['total_segments'],
            'overtake_segments': overview['overtake_segments'],
            'converted_pairs': conversion['total_converted_pairs'],
            'f1_valid': validation['f1_validation']['valid'],
            'b2_valid': validation['b2_validation']['valid']
        }
    }


def print_audit_results(audit_results: Dict[str, Any]) -> None:
    """
    Print formatted audit results to console.
    
    Args:
        audit_results: Results from run_comprehensive_conversion_audit
    """
    print("=== SEGMENTS_NEW.CSV AUDIT ===")
    print(f"Total segments: {audit_results['overview']['total_segments']}")
    print()
    
    print(f"Segments with flow_type != 'none': {audit_results['overview']['overtake_segments']}")
    for seg_detail in audit_results['overview']['segment_details']:
        print(f"  {seg_detail['seg_id']}: {seg_detail['events']} (flow_type: {seg_detail['flow_type']})")
    
    print()
    print("=== CONVERSION RESULTS ===")
    print(f"Total converted pairs: {audit_results['conversion']['total_converted_pairs']}")
    print()
    
    for seg_id, seg_info in audit_results['conversion']['segments'].items():
        print(f"{seg_id} ({seg_info['pair_count']} pairs):")
        for pair in seg_info['pairs']:
            print(f"  {pair['eventa']} vs {pair['eventb']} - {pair['flow_type']}")
        print()
    
    print("=== VALIDATION RESULTS ===")
    f1_val = audit_results['validation']['f1_validation']
    print(f"F1 pairs: {f1_val['actual_count']}/{f1_val['expected_count']} {'✅' if f1_val['valid'] else '❌'}")
    
    b2_val = audit_results['validation']['b2_validation']
    print(f"B2 pairs: {b2_val['actual_count']}/{b2_val['expected_count']} {'✅' if b2_val['valid'] else '❌'}")
    
    if audit_results['validation']['missing_pairs']:
        print("Missing pairs:")
        for missing in audit_results['validation']['missing_pairs']:
            print(f"  {missing['seg_id']}: {missing['missing_pair']}")


if __name__ == "__main__":
    """Command-line interface for running conversion audit"""
    import sys
    
    segments_path = sys.argv[1] if len(sys.argv) > 1 else 'data/segments_new.csv'
    results = run_comprehensive_conversion_audit(segments_path)
    print_audit_results(results)
