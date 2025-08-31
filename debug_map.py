#!/usr/bin/env python3
"""
Debug script to test map data flow and identify missing segments
"""

import requests
import json

def test_map_data_flow():
    """Test the complete data flow for the map"""
    
    base_url = "http://localhost:8000"
    
    print("🔍 Testing Map Data Flow...")
    print("=" * 50)
    
    # 1. Test segments.geojson endpoint
    print("\n1️⃣ Testing /api/segments.geojson...")
    try:
        response = requests.get(f"{base_url}/api/segments.geojson")
        if response.status_code == 200:
            segments_data = response.json()
            print(f"✅ Segments endpoint: {len(segments_data['features'])} features")
            
            # Check for D2
            d2_feature = next((f for f in segments_data['features'] if f['properties']['seg_id'] == 'D2'), None)
            if d2_feature:
                print(f"✅ D2 found in GeoJSON: {d2_feature['properties']}")
                print(f"   Coordinates: {d2_feature['geometry']['coordinates']}")
            else:
                print("❌ D2 NOT found in GeoJSON")
                
        else:
            print(f"❌ Segments endpoint failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error testing segments endpoint: {e}")
        return
    
    # 2. Test density.summary endpoint
    print("\n2️⃣ Testing /api/density.summary...")
    try:
        payload = {
            "paceCsv": "https://raw.githubusercontent.com/thomjeff/run-density/main/data/your_pace_data.csv",
            "overlapsCsv": "https://raw.githubusercontent.com/thomjeff/run-density/main/data/overlaps.csv",
            "startTimes": {"Full": 420, "Half": 460, "10K": 440},
            "stepKm": 0.03,
            "timeWindow": 60,
            "depth_m": 3.0
        }
        
        response = requests.post(f"{base_url}/api/density.summary", json=payload)
        if response.status_code == 200:
            density_data = response.json()
            print(f"✅ Density endpoint: {len(density_data['segments'])} segments")
            
            # Check for D2
            d2_segment = next((s for s in density_data['segments'] if s['seg_id'] == 'D2'), None)
            if d2_segment:
                print(f"✅ D2 found in density data: {d2_segment}")
            else:
                print("❌ D2 NOT found in density data")
                
        else:
            print(f"❌ Density endpoint failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error testing density endpoint: {e}")
        return
    
    # 3. Test the map page
    print("\n3️⃣ Testing /map page...")
    try:
        response = requests.get(f"{base_url}/map")
        if response.status_code == 200:
            print("✅ Map page loads successfully")
            
            # Check if D2 is mentioned in the HTML
            if 'D2' in response.text:
                print("✅ D2 found in map HTML")
            else:
                print("❌ D2 NOT found in map HTML")
                
        else:
            print(f"❌ Map page failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing map page: {e}")
    
    print("\n" + "=" * 50)
    print("🔍 Debug complete!")

if __name__ == "__main__":
    # Start the server first
    import subprocess
    import time
    
    print("🚀 Starting server...")
    server_process = subprocess.Popen([
        "python3", "-m", "uvicorn", "app.main:app", "--port", "8000"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(5)
    
    try:
        test_map_data_flow()
    finally:
        # Clean up
        print("\n🛑 Stopping server...")
        server_process.terminate()
        server_process.wait()
