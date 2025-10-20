from typing import Literal, Optional, List
from pydantic import BaseModel, Field, confloat

# segments.geojson
class SegmentProperties(BaseModel):
    segment_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    length_m: confloat(gt=0)
    events: List[Literal["Full","Half","10K"]] = Field(default_factory=list)

class GeoJSONGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list  # [[lon, lat], ...]

class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: SegmentProperties
    geometry: GeoJSONGeometry

class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature]

# segment_metrics.json
class SegmentMetrics(BaseModel):
    segment_id: str
    worst_los: Literal["A","B","C","D","E","F"]
    peak_density_window: str  # "HH:MM–HH:MM"
    co_presence_pct: confloat(ge=0, le=100)
    overtaking_pct: confloat(ge=0, le=100)
    utilization_pct: confloat(ge=0, le=100)

class SegmentMetricsFile(BaseModel):
    items: List[SegmentMetrics]

# flags.json
class SegmentFlag(BaseModel):
    segment_id: str
    flag_type: Literal["co_presence","overtaking"]
    severity: Literal["info","warn","critical"]
    window: str
    note: Optional[str] = None

class FlagsFile(BaseModel):
    items: List[SegmentFlag]

# meta.json
class Meta(BaseModel):
    run_timestamp: str  # ISO 8601
    environment: Literal["local","cloud"]
    rulebook_hash: str
    dataset_version: str
    run_hash: Optional[str] = None
    validated: Optional[bool] = None
