"""
Naming Normalization Module

Normalizes variable names from various formats to canonical internal names.
Used primarily at API boundaries to accept legacy aliases while maintaining
internal naming consistency.

See ADR-001 for naming conventions and migration strategy.
"""

from typing import Optional


def normalize_segment_id(request: dict, default: Optional[str] = None) -> Optional[str]:
    """
    Normalize segment identifier from request dict.
    
    Accepts various alias formats and returns canonical 'segment_id'.
    
    Supported aliases:
        - segment_id (canonical)
        - segmentId (camelCase)
        - seg_id (internal data layer)
        - segId (mixed case)
    
    Args:
        request: Dictionary containing segment identifier (e.g., request params, JSON body)
        default: Optional default value if no segment identifier found
        
    Returns:
        Normalized segment_id string, or default if not found
        
    Example:
        >>> request = {'segmentId': 'A1'}
        >>> normalize_segment_id(request)
        'A1'
        
        >>> request = {'seg_id': 'B2'}
        >>> normalize_segment_id(request)
        'B2'
    """
    # Try canonical name first
    if 'segment_id' in request:
        return request['segment_id']
    
    # Try camelCase variant
    if 'segmentId' in request:
        return request['segmentId']
    
    # Try internal data layer name
    if 'seg_id' in request:
        return request['seg_id']
    
    # Try mixed case variant
    if 'segId' in request:
        return request['segId']
    
    return default


def normalize_checkpoint_id(request: dict, default: Optional[str] = None) -> Optional[str]:
    """
    Normalize checkpoint identifier from request dict.
    
    Accepts various alias formats and returns canonical 'checkpoint_id'.
    
    Supported aliases:
        - checkpoint_id (canonical)
        - checkpointId (camelCase)
        - chk_id (internal data layer)
        - chkptId (mixed case)
    
    Args:
        request: Dictionary containing checkpoint identifier
        default: Optional default value if no checkpoint identifier found
        
    Returns:
        Normalized checkpoint_id string, or default if not found
        
    Example:
        >>> request = {'checkpointId': 'CP1'}
        >>> normalize_checkpoint_id(request)
        'CP1'
        
        >>> request = {'chk_id': 'CP2'}
        >>> normalize_checkpoint_id(request)
        'CP2'
    """
    # Try canonical name first
    if 'checkpoint_id' in request:
        return request['checkpoint_id']
    
    # Try camelCase variant
    if 'checkpointId' in request:
        return request['checkpointId']
    
    # Try internal data layer name
    if 'chk_id' in request:
        return request['chk_id']
    
    # Try mixed case variant
    if 'chkptId' in request:
        return request['chkptId']
    
    return default


def normalize_cursor_index(request: dict, default: Optional[int] = None) -> Optional[int]:
    """
    Normalize cursor/index identifier from request dict.
    
    Accepts various alias formats and returns canonical 'cursor_index'.
    
    Supported aliases:
        - cursor_index (canonical)
        - cursorIndex (camelCase)
        - event_cursor (legacy)
        - cursor_pos (legacy)
    
    Args:
        request: Dictionary containing cursor identifier
        default: Optional default value if no cursor found
        
    Returns:
        Normalized cursor_index integer, or default if not found
    """
    # Try canonical name first
    if 'cursor_index' in request:
        val = request['cursor_index']
        return int(val) if val is not None else default
    
    # Try camelCase variant
    if 'cursorIndex' in request:
        val = request['cursorIndex']
        return int(val) if val is not None else default
    
    # Try legacy names
    if 'event_cursor' in request:
        val = request['event_cursor']
        return int(val) if val is not None else default
    
    if 'cursor_pos' in request:
        val = request['cursor_pos']
        return int(val) if val is not None else default
    
    return default



















