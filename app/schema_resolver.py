# app/schema_resolver.py
"""
Schema resolver for segment-to-schema mapping.

Maps segment IDs to rulebook schema keys (start_corral, on_course_narrow, on_course_open).
This enables schema-specific thresholds for LOS and rate-based flagging.

Issue #254: Centralize Rulebook Logic
Issue #648: Load schema mappings from segments.csv (SSOT) instead of hardcoded EXPLICIT dict
"""
import functools
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Issue #648: Schema mappings now loaded from segments.csv (SSOT)
# Removed hardcoded EXPLICIT dictionary - all mappings come from CSV

@functools.lru_cache(maxsize=1)
def _load_schema_map(csv_path: str = "data/segments.csv") -> Dict[str, str]:
    """
    Load segment-to-schema mapping from segments.csv (SSOT).
    
    Issue #648: This replaces the hardcoded EXPLICIT dictionary with CSV-based SSOT.
    
    Args:
        csv_path: Path to segments.csv file (default: "data/segments.csv")
        
    Returns:
        Dictionary mapping segment_id to schema_key
        
    Raises:
        FileNotFoundError: If segments.csv not found
        ValueError: If required columns (seg_id, schema) are missing
    """
    try:
        from app.io.loader import load_segments
        
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"segments.csv not found at {csv_file.absolute()}")
        
        df = load_segments(str(csv_file))
        
        # Validate required columns
        if 'seg_id' not in df.columns:
            raise ValueError(f"segments.csv missing required column: seg_id")
        if 'schema' not in df.columns:
            raise ValueError(f"segments.csv missing required column: schema")
        
        # Build schema mapping
        schema_map = {}
        for _, row in df.iterrows():
            seg_id = str(row['seg_id']).strip()
            schema = str(row.get('schema', '')).strip()
            
            if seg_id and schema:
                # Validate schema value (must be valid rulebook schema)
                valid_schemas = {'start_corral', 'on_course_narrow', 'on_course_open'}
                if schema not in valid_schemas:
                    logger.warning(
                        f"Invalid schema value '{schema}' for segment {seg_id} in segments.csv. "
                        f"Must be one of: {valid_schemas}. Defaulting to 'on_course_open'."
                    )
                    schema = 'on_course_open'
                schema_map[seg_id] = schema
        
        logger.info(f"Loaded {len(schema_map)} segment-to-schema mappings from {csv_file}")
        return schema_map
        
    except Exception as e:
        logger.error(f"Failed to load schema map from {csv_path}: {e}")
        raise

def resolve_schema(segment_id: str, segment_type: Optional[str] = None) -> str:
    """
    Resolve segment ID to rulebook schema key from segments.csv (SSOT).
    
    Issue #648: Schema mappings now loaded from segments.csv instead of hardcoded EXPLICIT dict.
    
    Resolution order:
    1. segments.csv schema column (SSOT)
    2. Type-based mapping (if segment_type provided, as fallback only)
    3. Default to on_course_open
    
    Args:
        segment_id: Segment identifier (e.g., "A1", "B1", "D1a", "N1")
        segment_type: Optional segment type from segments.csv (used as fallback only)
        
    Returns:
        Schema key: "start_corral", "on_course_narrow", or "on_course_open"
    
    Raises:
        TypeError: If segment_type is not a string (Issue #557)
        FileNotFoundError: If segments.csv not found
        ValueError: If segments.csv is invalid
    """
    # 1) Load from segments.csv (SSOT)
    schema_map = _load_schema_map()
    if segment_id in schema_map:
        return schema_map[segment_id]
    
    # 2) Type-based fallback (preserve existing logic for backward compatibility)
    if segment_type:
        # Type guard: ensure segment_type is a string (Issue #557)
        if not isinstance(segment_type, str):
            raise TypeError(
                f"Expected string for segment_type, got {type(segment_type).__name__}. "
                f"segment_id={segment_id}, segment_type={segment_type}"
            )
        t = segment_type.lower()
        
        # Narrow/constrained segments
        if t in {"funnel", "merge", "bridge", "chute", "finish", "narrow"}:
            logger.warning(
                f"Segment {segment_id} not found in segments.csv, using type-based fallback: "
                f"segment_type='{segment_type}' → on_course_narrow"
            )
            return "on_course_narrow"
        
        # Start corrals
        if t in {"start", "corral"}:
            logger.warning(
                f"Segment {segment_id} not found in segments.csv, using type-based fallback: "
                f"segment_type='{segment_type}' → start_corral"
            )
            return "start_corral"
    
    # 3) Default fallback (should not happen in production if CSV is complete)
    logger.warning(
        f"Segment {segment_id} not found in segments.csv and no segment_type provided, "
        f"defaulting to on_course_open"
    )
    return "on_course_open"

def get_schema_stats() -> Dict[str, int]:
    """
    Get statistics on schema mappings from segments.csv (SSOT).
    
    Issue #648: Now loads from CSV instead of hardcoded EXPLICIT dict.
    
    Returns:
        Dict with counts per schema type (e.g., {"start_corral": 1, "on_course_narrow": 13, ...})
    """
    schema_map = _load_schema_map()
    
    stats = {}
    for schema in schema_map.values():
        stats[schema] = stats.get(schema, 0) + 1
    
    return stats

