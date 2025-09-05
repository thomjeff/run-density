"""
Density Analysis API Endpoints

This module provides API endpoints for density analysis functionality.
It integrates with the density analysis module and provides RESTful
endpoints for density calculations and reporting.

Author: AI Assistant
Version: 1.6.0
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

from .density import (
    analyze_density_segments,
    DensityConfig,
    StaticWidthProvider,
    DynamicWidthProvider
)

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI Router
router = APIRouter(prefix='/api/density', tags=['density'])


class DensityAnalysisRequest(BaseModel):
    """Request model for density analysis."""
    segments: Optional[list] = None
    config: Optional[Dict[str, Any]] = None
    width_provider: str = "static"


class DensityAnalysisResponse(BaseModel):
    """Response model for density analysis."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post('/analyze', response_model=DensityAnalysisResponse)
async def analyze_density(request: DensityAnalysisRequest):
    """
    Analyze density for all segments.
    
    Request body:
    {
        "segments": [...],  # Optional: segment data
        "config": {         # Optional: configuration overrides
            "bin_seconds": 30,
            "threshold_areal": 1.2,
            "threshold_crowd": 2.0,
            "min_segment_length_m": 50.0
        },
        "width_provider": "static"  # Optional: "static" or "dynamic"
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "summary": {...},
            "segments": {...}
        }
    }
    """
    try:
        # Load segments data
        if request.segments:
            segments_df = pd.DataFrame(request.segments)
        else:
            # Load from default location
            segments_df = pd.read_csv('data/segments.csv')
        
        # Load pace data
        pace_data = pd.read_csv('data/your_pace_data.csv')
        
        # Load start times
        start_times = {
            '10K': datetime.strptime('08:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            'Half': datetime.strptime('08:30:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            'Full': datetime.strptime('09:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1)
        }
        
        # Create configuration
        config_data = request.config or {}
        config = DensityConfig(
            bin_seconds=config_data.get('bin_seconds', 30),
            threshold_areal=config_data.get('threshold_areal', 1.2),
            threshold_crowd=config_data.get('threshold_crowd', 2.0),
            min_segment_length_m=config_data.get('min_segment_length_m', 50.0)
        )
        
        # Create width provider
        if request.width_provider == 'dynamic':
            width_provider = DynamicWidthProvider()
        else:
            width_provider = StaticWidthProvider(segments_df)
        
        # Perform analysis
        results = analyze_density_segments(
            segments_df=segments_df,
            pace_data=pace_data,
            start_times=start_times,
            config=config,
            width_provider=width_provider
        )
        
        return DensityAnalysisResponse(
            success=True,
            data=results
        )
        
    except Exception as e:
        logger.error(f"Density analysis error: {str(e)}")
        return DensityAnalysisResponse(
            success=False,
            error=str(e)
        )


@router.get('/segment/{segment_id}', response_model=DensityAnalysisResponse)
async def get_segment_density(
    segment_id: str,
    config: Optional[str] = Query(None, description="JSON string with configuration overrides"),
    width_provider: str = Query("static", description="Width provider type: static or dynamic")
):
    """
    Get density analysis for a specific segment.
    
    Query parameters:
    - config: JSON string with configuration overrides
    - width_provider: "static" or "dynamic"
    
    Returns:
    {
        "success": true,
        "data": {
            "segment_id": "...",
            "summary": {...},
            "time_series": [...],
            "sustained_periods": [...]
        }
    }
    """
    try:
        # Load data
        segments_df = pd.read_csv('data/segments.csv')
        pace_data = pd.read_csv('data/your_pace_data.csv')
        
        start_times = {
            '10K': datetime.strptime('08:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            'Half': datetime.strptime('08:30:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            'Full': datetime.strptime('09:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1)
        }
        
        # Get configuration from query parameters
        config_data = eval(config) if config else {}
        
        density_config = DensityConfig(
            bin_seconds=config_data.get('bin_seconds', 30),
            threshold_areal=config_data.get('threshold_areal', 1.2),
            threshold_crowd=config_data.get('threshold_crowd', 2.0),
            min_segment_length_m=config_data.get('min_segment_length_m', 50.0)
        )
        
        # Create width provider
        if width_provider == 'dynamic':
            width_provider_instance = DynamicWidthProvider()
        else:
            width_provider_instance = StaticWidthProvider(segments_df)
        
        # Filter to specific segment
        segment_df = segments_df[segments_df['segment_id'] == segment_id]
        if segment_df.empty:
            return DensityAnalysisResponse(
                success=False,
                error=f"Segment {segment_id} not found"
            )
        
        # Perform analysis
        results = analyze_density_segments(
            segments_df=segment_df,
            pace_data=pace_data,
            start_times=start_times,
            config=density_config,
            width_provider=width_provider_instance
        )
        
        if segment_id not in results['segments']:
            return DensityAnalysisResponse(
                success=False,
                error=f"No density data available for segment {segment_id}"
            )
        
        return DensityAnalysisResponse(
            success=True,
            data=results['segments'][segment_id]
        )
        
    except Exception as e:
        logger.error(f"Segment density analysis error: {str(e)}")
        return DensityAnalysisResponse(
            success=False,
            error=str(e)
        )


@router.get('/summary', response_model=DensityAnalysisResponse)
async def get_density_summary(
    config: Optional[str] = Query(None, description="JSON string with configuration overrides"),
    width_provider: str = Query("static", description="Width provider type: static or dynamic")
):
    """
    Get density analysis summary for all segments.
    
    Query parameters:
    - config: JSON string with configuration overrides
    - width_provider: "static" or "dynamic"
    
    Returns:
    {
        "success": true,
        "data": {
            "summary": {...},
            "segments": {
                "segment_id": {
                    "summary": {...}
                }
            }
        }
    }
    """
    try:
        # Load data
        segments_df = pd.read_csv('data/segments.csv')
        pace_data = pd.read_csv('data/your_pace_data.csv')
        
        start_times = {
            '10K': datetime.strptime('08:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            'Half': datetime.strptime('08:30:00', '%H:%M:%S').replace(year=2024, month=1, day=1),
            'Full': datetime.strptime('09:00:00', '%H:%M:%S').replace(year=2024, month=1, day=1)
        }
        
        # Get configuration from query parameters
        config_data = eval(config) if config else {}
        
        density_config = DensityConfig(
            bin_seconds=config_data.get('bin_seconds', 30),
            threshold_areal=config_data.get('threshold_areal', 1.2),
            threshold_crowd=config_data.get('threshold_crowd', 2.0),
            min_segment_length_m=config_data.get('min_segment_length_m', 50.0)
        )
        
        # Create width provider
        if width_provider == 'dynamic':
            width_provider_instance = DynamicWidthProvider()
        else:
            width_provider_instance = StaticWidthProvider(segments_df)
        
        # Perform analysis
        results = analyze_density_segments(
            segments_df=segments_df,
            pace_data=pace_data,
            start_times=start_times,
            config=density_config,
            width_provider=width_provider_instance
        )
        
        # Return only summary data
        summary_data = {
            "summary": results['summary'],
            "segments": {
                segment_id: segment_data['summary']
                for segment_id, segment_data in results['segments'].items()
            }
        }
        
        return DensityAnalysisResponse(
            success=True,
            data=summary_data
        )
        
    except Exception as e:
        logger.error(f"Density summary error: {str(e)}")
        return DensityAnalysisResponse(
            success=False,
            error=str(e)
        )


@router.get('/health')
async def health_check():
    """
    Health check endpoint for density analysis.
    
    Returns:
    {
        "status": "healthy",
        "module": "density",
        "version": "1.6.0"
    }
    """
    return {
        "status": "healthy",
        "module": "density",
        "version": "1.6.0"
    }
