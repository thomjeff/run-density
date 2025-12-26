#!/usr/bin/env python3
"""
E2E Performance Profiling Script

Runs E2E test with profiling enabled to identify performance bottlenecks.

Issue #503: Phase 1 - Performance Instrumentation

Usage:
    python scripts/profile_e2e.py
    # Or with Docker:
    docker exec run-density-dev python scripts/profile_e2e.py
"""

import cProfile
import pstats
import io
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def profile_e2e_test():
    """Run E2E test with profiling."""
    from app.routes.v2.analyze import analyze_v2
    import json
    
    # Load E2E test payload
    e2e_payload_path = Path(__file__).parent.parent / "tests" / "e2e" / "test_payload.json"
    if not e2e_payload_path.exists():
        print(f"Error: E2E test payload not found at {e2e_payload_path}")
        return
    
    with open(e2e_payload_path, 'r') as f:
        payload = json.load(f)
    
    # Create profiler
    profiler = cProfile.Profile()
    
    print("Starting profiled E2E test...")
    profiler.enable()
    
    try:
        # Run analysis
        result = analyze_v2(payload)
        print(f"✅ Analysis completed: {result.get('run_id', 'unknown')}")
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        profiler.disable()
    
    # Generate statistics
    stats_stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stats_stream)
    stats.sort_stats('cumulative')
    
    print("\n" + "=" * 80)
    print("Performance Profile - Top 30 Functions by Cumulative Time")
    print("=" * 80)
    stats.print_stats(30)
    
    # Save full profile to file
    profile_output = Path(__file__).parent.parent / "profile_output.prof"
    profiler.dump_stats(str(profile_output))
    print(f"\n📊 Full profile saved to: {profile_output}")
    print(f"   View with: python -m pstats {profile_output}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("Profile Summary")
    print("=" * 80)
    print(stats_stream.getvalue())
    
    # Generate call graph (if gprof2dot available)
    try:
        import subprocess
        dot_output = Path(__file__).parent.parent / "profile_graph.dot"
        svg_output = Path(__file__).parent.parent / "profile_graph.svg"
        
        # Try to generate call graph
        result = subprocess.run(
            ["gprof2dot", "-f", "pstats", str(profile_output)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            with open(dot_output, 'w') as f:
                f.write(result.stdout)
            print(f"📈 Call graph saved to: {dot_output}")
            print(f"   Convert to SVG: dot -Tsvg {dot_output} -o {svg_output}")
        else:
            print("ℹ️  gprof2dot not available. Install with: pip install gprof2dot")
    except FileNotFoundError:
        print("ℹ️  gprof2dot not available. Install with: pip install gprof2dot")

if __name__ == "__main__":
    profile_e2e_test()

