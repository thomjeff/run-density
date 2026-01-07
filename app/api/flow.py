"""
API Routes for Flow Data (RF-FE-002)

Provides temporal flow analysis endpoints for the flow page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
import json

# Issue #466 Step 2: Storage consolidated to app.storage


# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage singleton (not needed)


@router.get("/api/flow/segments")
async def get_flow_segments(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get flow analysis data for all segments from UI artifacts.
    
    Issue #628: Updated to read from metrics/flow_segments.json instead of Flow.csv.
    Returns segment-level data with worst zone metrics and nested zones.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped data
    
    Returns:
        Dictionary with:
        - selected_day: Day code
        - available_days: List of available days
        - flow: Dictionary keyed by composite key (seg_id_event_a_event_b) with:
            - Segment metadata
            - Worst zone metrics
            - Nested zones array
    """
    try:
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Issue #628: Load flow_segments.json from metrics/ subdirectory
        try:
            # flow_segments.json is at: runflow/<run_id>/<day>/ui/metrics/flow_segments.json
            flow_segments_content = storage.read_text(f"{selected_day}/ui/metrics/flow_segments.json")
            
            if not flow_segments_content:
                logger.error("Failed to read flow_segments.json: file is empty")
                return JSONResponse(content={
                    "selected_day": selected_day,
                    "available_days": available_days,
                    "flow": {}
                })
            
            # Parse JSON content
            flow_segments = json.loads(flow_segments_content)
        
        except FileNotFoundError:
            logger.warning(f"flow_segments.json not found for day {selected_day}, returning empty flow")
            flow_segments = {}
        except Exception as e:
            logger.error(f"Failed to load flow_segments.json: {e}")
            flow_segments = {}
        
        # Issue #628: Load zone_captions.json from visualizations/ subdirectory
        zone_captions = []
        try:
            # zone_captions.json is at: runflow/<run_id>/<day>/ui/visualizations/zone_captions.json
            zone_captions_content = storage.read_text(f"{selected_day}/ui/visualizations/zone_captions.json")
            if zone_captions_content:
                zone_captions = json.loads(zone_captions_content)
        except FileNotFoundError:
            logger.debug(f"zone_captions.json not found for day {selected_day}")
        except Exception as e:
            logger.warning(f"Failed to load zone_captions.json: {e}")
        
        # Issue #628: Create lookup for zone captions (keyed by seg_id_event_a_event_b_zone_index)
        captions_lookup = {}
        for caption in zone_captions:
            if isinstance(caption, dict):
                key = f"{caption.get('seg_id', '')}_{caption.get('event_a', '')}_{caption.get('event_b', '')}_{caption.get('zone_index', 0)}"
                captions_lookup[key] = caption
        
        # Issue #628: Enrich flow_segments with zone captions
        for composite_key, segment_data in flow_segments.items():
            if not isinstance(segment_data, dict):
                continue
            
            # Add captions to each zone in the zones array
            zones = segment_data.get("zones", [])
            enriched_zones = []
            for zone in zones:
                if isinstance(zone, dict):
                    zone_key = f"{segment_data.get('seg_id', '')}_{segment_data.get('event_a', '')}_{segment_data.get('event_b', '')}_{zone.get('zone_index', 0)}"
                    caption = captions_lookup.get(zone_key)
                    if caption:
                        zone["caption"] = caption
                    enriched_zones.append(zone)
            
            segment_data["zones"] = enriched_zones
        
        logger.info(f"Loaded {len(flow_segments)} flow segment entries for day {selected_day} with {len(captions_lookup)} zone captions")
        
        response = JSONResponse(content={
            "selected_day": selected_day,
            "available_days": available_days,
            "flow": flow_segments
        })
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating flow segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load flow data: {str(e)}")

