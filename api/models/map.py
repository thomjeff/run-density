"""
Pydantic Models for Map API

Request and response models for map-related endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


class MapManifestResponse(BaseModel):
    """Response model for map manifest endpoint."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MapBinsRequest(BaseModel):
    """Request model for map bins endpoint."""
    segment_id: Optional[str] = None
    time_window: Optional[str] = None


class MapBinsResponse(BaseModel):
    """Response model for map bins endpoint."""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
