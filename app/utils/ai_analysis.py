"""
AI Analysis Module for Run-Density

Provides functions for extracting metrics from run results and generating
AI-powered analysis summaries using OpenAI API or manual prompt generation.

Issue #694: AI-Generated Analysis Summary for Run Results
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.storage import create_runflow_storage
from app.core.v2.analysis_config import load_analysis_json
from app.utils.run_id import get_run_directory
from app.version import get_version

logger = logging.getLogger(__name__)


def extract_analysis_metrics(run_id: str) -> Dict[str, Any]:
    """
    Extract structured metrics from run results for AI analysis.
    
    Issue #694: Extract all metrics required for AI-generated assessment.
    
    Args:
        run_id: Run identifier
        
    Returns:
        Dictionary with extracted metrics including metadata, events, density,
        flow, and critical segments
        
    Raises:
        FileNotFoundError: If required files are missing
        ValueError: If data is invalid
    """
    # Get run directory and storage
    run_path = get_run_directory(run_id)
    if not run_path.exists():
        raise FileNotFoundError(f"Run directory not found: {run_path}")
    
    storage = create_runflow_storage(run_id)
    
    # Load analysis.json (SSOT)
    analysis_config = load_analysis_json(run_path)
    
    # Extract scenario description
    scenario = analysis_config.get("description", "")
    if not scenario:
        logger.warning(f"Analysis description missing for run_id {run_id}")
        scenario = "Standard Analysis"
    
    # Build context data structure
    context_data = {
        "metadata": {
            "context_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator_version": get_version(),
            "units": {
                "density": "runners/m²",
                "rate": "runners/min/m",
                "flow_rate": "runners/s",
                "time": "ISO 8601 UTC"
            }
        },
        "run_id": run_id,
        "scenario": scenario,
        "total_runners": analysis_config.get("runners", 0),
        "days": analysis_config.get("event_days", []),
        "events": {},
        "density_metrics": {},
        "flow_metrics": {},
        "critical_segments": [],
        "narrow_segments": [],
        "flow_highlights": []
    }
    
    # Process each day
    for day in context_data["days"]:
        # Extract event metadata
        metadata_path = f"{day}/metadata.json"
        if not storage.exists(metadata_path):
            raise FileNotFoundError(f"metadata.json not found for {day} at {metadata_path}")
        
        metadata = storage.read_json(metadata_path)
        
        # Extract participant distribution
        day_events = {}
        for ev_name, ev_data in metadata.get("events", {}).items():
            if not isinstance(ev_data, dict):
                continue
            day_events[ev_name] = {
                "start_time": ev_data.get("start_time", ""),
                "participants": ev_data.get("participants", 0)
            }
        
        # Extract density summary metrics
        segment_metrics_path = f"{day}/ui/metrics/segment_metrics.json"
        if not storage.exists(segment_metrics_path):
            raise FileNotFoundError(f"segment_metrics.json not found for {day} at {segment_metrics_path}")
        
        segment_metrics = storage.read_json(segment_metrics_path)
        
        # Calculate LOS distribution
        los_distribution = _calculate_los_distribution(segment_metrics)
        
        # Extract runner experience scores
        res_score = _extract_res_score(metadata, day)
        
        # Load flags.json (needed for day-level metrics and critical segments)
        flags_path = f"{day}/ui/metrics/flags.json"
        flags = []
        if storage.exists(flags_path):
            flags = storage.read_json(flags_path)
            if not isinstance(flags, list):
                flags = []
        
        # Issue #694: Extract additional density metrics from flags.json for day-level summary
        # Calculate flagged_bin_percentage and flag_severity_distribution from flags
        total_bins_day = 0
        flagged_bins_day = 0
        flag_severity_distribution = {"critical": 0, "watch": 0, "none": 0}
        
        for flag in flags:
            if isinstance(flag, dict):
                # Sum total_bins and flagged_bins from all segments
                seg_total_bins = flag.get("total_bins", 0) or 0
                seg_flagged_bins = flag.get("flagged_bins") or flag.get("flagged_bin_count", 0) or 0
                total_bins_day += seg_total_bins
                flagged_bins_day += seg_flagged_bins
                
                # Count severity distribution
                severity = flag.get("worst_severity", "none")
                if severity in flag_severity_distribution:
                    flag_severity_distribution[severity] += 1
                else:
                    flag_severity_distribution["none"] += 1
        
        # Calculate flagged_bin_percentage at day level
        flagged_bin_percentage_day = (flagged_bins_day / total_bins_day * 100.0) if total_bins_day > 0 else None
        
        # Extract density summary
        density_summary = {
            "peak_density": segment_metrics.get("peak_density", 0.0),
            "peak_rate": segment_metrics.get("peak_rate", 0.0),
            "flagged_segments": segment_metrics.get("segments_with_flags", 0),
            "flagged_bins": segment_metrics.get("flagged_bins", 0),
            "flagged_bin_percentage": round(flagged_bin_percentage_day, 2) if flagged_bin_percentage_day is not None else None,  # Issue #694: Add day-level percentage
            "flag_severity_distribution": flag_severity_distribution,  # Issue #694: Add severity distribution
            "los_distribution": los_distribution,
            "runner_experience_score": res_score
        }
        
        # Extract flow summary
        flow_summary = {
            "overtaking_segments": segment_metrics.get("overtaking_segments", 0),
            "copresence_segments": segment_metrics.get("co_presence_segments", 0)
        }
        
        # Extract critical segments (flags already loaded above for day-level metrics)
        segments_geojson = None
        segments_geojson_path = f"{day}/ui/geospatial/segments.geojson"
        if storage.exists(segments_geojson_path):
            segments_geojson = storage.read_json(segments_geojson_path)
        
        critical_segments = _identify_critical_segments(
            day, segment_metrics, flags, segments_geojson
        )
        
        # Extract narrow segments
        narrow_segments = _identify_narrow_segments(
            day, segments_geojson, segment_metrics, flags
        )
        
        # Extract flow highlights
        flow_segments_path = f"{day}/ui/metrics/flow_segments.json"
        flow_segments = {}
        if storage.exists(flow_segments_path):
            flow_segments = storage.read_json(flow_segments_path)
        
        flow_highlights = _identify_flow_highlights(day, flow_segments)
        
        # Store day-specific data
        context_data["events"][day] = day_events
        context_data["density_metrics"][day] = density_summary
        context_data["flow_metrics"][day] = flow_summary
        context_data["critical_segments"].extend(critical_segments)
        context_data["narrow_segments"].extend(narrow_segments)
        context_data["flow_highlights"].extend(flow_highlights)
    
    return context_data


def _calculate_los_distribution(segment_metrics: Dict[str, Any]) -> Dict[str, int]:
    """Calculate LOS distribution from segment metrics."""
    summary_fields = [
        "peak_density", "peak_rate", "segments_with_flags", "flagged_bins",
        "overtaking_segments", "co_presence_segments"
    ]
    
    # Filter out summary fields
    segment_data = {
        k: v for k, v in segment_metrics.items()
        if isinstance(v, dict) and k not in summary_fields
    }
    
    los_dist = defaultdict(int)
    for seg_id, metrics in segment_data.items():
        los = metrics.get("worst_los", "Unknown")
        los_dist[los] += 1
    
    return dict(los_dist)


def _extract_res_score(metadata: Dict[str, Any], day: str) -> Optional[float]:
    """Extract runner experience score from metadata."""
    event_groups = metadata.get("event_groups", {})
    if not event_groups:
        return None
    
    # Find RES for this day (may be in day-specific event group)
    for group_key, group_data in event_groups.items():
        if isinstance(group_data, dict) and "res" in group_data:
            # Check if this group applies to the current day
            if day in group_key or group_key.endswith(f"-{day}"):
                return group_data.get("res")
    
    # If no day-specific RES, return first available
    for group_data in event_groups.values():
        if isinstance(group_data, dict) and "res" in group_data:
            return group_data.get("res")
    
    return None


def _calculate_active_window_duration(active_window: str) -> Optional[float]:
    """Calculate active window duration in minutes from string format 'HH:MM–HH:MM'."""
    if not active_window or active_window == "N/A":
        return None
    
    try:
        # Format: "HH:MM–HH:MM" or "HH:MM:SS–HH:MM:SS"
        if "–" in active_window:
            parts = active_window.split("–")
            if len(parts) == 2:
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                
                # Parse time strings
                def parse_time(time_str):
                    time_parts = time_str.split(":")
                    if len(time_parts) >= 2:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        return hours * 60 + minutes
                    return 0
                
                start_minutes = parse_time(start_str)
                end_minutes = parse_time(end_str)
                
                # Handle day rollover
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                
                duration_minutes = end_minutes - start_minutes
                return max(0.0, duration_minutes)
    except (ValueError, AttributeError):
        pass
    
    return None


def _calculate_severity_distribution(flags: List[Dict[str, Any]], seg_id: str) -> Dict[str, int]:
    """Calculate severity distribution for a segment from flags."""
    distribution = {"critical": 0, "watch": 0, "none": 0}
    
    for flag in flags:
        if isinstance(flag, dict):
            flag_seg_id = flag.get("seg_id") or flag.get("segment_id")
            if flag_seg_id == seg_id:
                severity = flag.get("worst_severity", "none")
                if severity == "critical":
                    distribution["critical"] += 1
                elif severity == "watch":
                    distribution["watch"] += 1
                else:
                    distribution["none"] += 1
    
    return distribution


def _identify_critical_segments(
    day: str,
    segment_metrics: Dict[str, Any],
    flags: List[Dict[str, Any]],
    segments_geojson: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Identify critical segments requiring attention."""
    summary_fields = [
        "peak_density", "peak_rate", "segments_with_flags", "flagged_bins",
        "overtaking_segments", "co_presence_segments"
    ]
    
    segment_data = {
        k: v for k, v in segment_metrics.items()
        if isinstance(v, dict) and k not in summary_fields
    }
    
    # Build flags lookup
    flags_by_seg_id = {}
    for flag in flags:
        if isinstance(flag, dict):
            seg_id = flag.get("seg_id") or flag.get("segment_id")
            if seg_id:
                flags_by_seg_id[seg_id] = flag
    
    # Build segment properties lookup
    segment_props = {}
    if segments_geojson:
        for feature in segments_geojson.get("features", []):
            props = feature.get("properties", {})
            seg_id = props.get("seg_id", "")
            if seg_id:
                segment_props[seg_id] = props
    
    critical = []
    for seg_id, metrics in segment_data.items():
        los = metrics.get("worst_los", "Unknown")
        density = metrics.get("peak_density", 0.0)
        
        # Critical if LOS D/E/F or high density
        if los in ["D", "E", "F"] or density > 0.7:
            flag_data = flags_by_seg_id.get(seg_id, {})
            props = segment_props.get(seg_id, {})
            
            # Issue #694: Extract metrics from flags.json (now calculated in generate_flags_json)
            # Support both canonical ("flagged_bins") and legacy ("flagged_bin_count") field names
            flagged_bins = flag_data.get("flagged_bins") or flag_data.get("flagged_bin_count", 0)
            total_bins = flag_data.get("total_bins", 0)
            flagged_bin_percentage = flag_data.get("flagged_bin_percentage")  # Extract directly from JSON
            # If not present in JSON (backward compatibility), calculate from available data
            if flagged_bin_percentage is None and total_bins > 0:
                flagged_bin_percentage = (flagged_bins / total_bins) * 100.0
            
            # Issue #694: Extract duration metrics from flags.json
            flagged_duration_seconds = flag_data.get("flagged_duration_seconds", 0.0)
            flagged_duration_minutes = flag_data.get("flagged_duration_minutes")
            # If not present, calculate from seconds for backward compatibility
            if flagged_duration_minutes is None and flagged_duration_seconds > 0:
                flagged_duration_minutes = flagged_duration_seconds / 60.0
            flagged_span_duration_seconds = flag_data.get("flagged_span_duration_seconds", 0.0)
            
            # Calculate active window duration (separate from flagged duration)
            active_window = metrics.get("active_window", "N/A")
            active_window_duration = _calculate_active_window_duration(active_window)
            
            critical.append({
                "day": day,
                "seg_id": seg_id,
                "label": props.get("label", seg_id),
                "length_km": props.get("length_km", 0.0),
                "width_m": props.get("width_m", 0.0),
                "direction": props.get("direction", ""),
                "schema": props.get("schema", ""),
                "utilization": metrics.get("utilization", 0.0),
                "los": los,
                "density": density,
                "rate": metrics.get("peak_rate", 0.0),
                "active_window": active_window,
                "active_window_duration_minutes": active_window_duration,
                "flagged_bins": flagged_bins,
                "flagged_bin_percentage": round(flagged_bin_percentage, 2) if flagged_bin_percentage is not None else None,
                "total_bins": total_bins if total_bins > 0 else None,
                "flagged_duration_seconds": round(flagged_duration_seconds, 1) if flagged_duration_seconds > 0 else None,
                "flagged_duration_minutes": round(flagged_duration_minutes, 1) if flagged_duration_minutes else None,
                "flagged_span_duration_seconds": round(flagged_span_duration_seconds, 1) if flagged_span_duration_seconds > 0 else None,
                "severity": flag_data.get("worst_severity", "none"),
                "severity_distribution": _calculate_severity_distribution(flags, seg_id),
                "reason": "high_density" if density > 0.7 else "poor_los"
            })
    
    # Sort by density descending
    critical.sort(key=lambda x: x["density"], reverse=True)
    return critical[:10]  # Top 10


def _identify_narrow_segments(
    day: str,
    segments_geojson: Optional[Dict[str, Any]],
    segment_metrics: Dict[str, Any],
    flags: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Identify narrow segments (< 3.0m width) with elevated density."""
    if not segments_geojson:
        return []
    
    summary_fields = [
        "peak_density", "peak_rate", "segments_with_flags", "flagged_bins",
        "overtaking_segments", "co_presence_segments"
    ]
    
    segment_data = {
        k: v for k, v in segment_metrics.items()
        if isinstance(v, dict) and k not in summary_fields
    }
    
    flags_by_seg_id = {}
    for flag in flags:
        if isinstance(flag, dict):
            seg_id = flag.get("seg_id") or flag.get("segment_id")
            if seg_id:
                flags_by_seg_id[seg_id] = flag
    
    narrow = []
    for feature in segments_geojson.get("features", []):
        props = feature.get("properties", {})
        seg_id = props.get("seg_id", "")
        width_m = props.get("width_m", 0.0)
        
        # Narrow if width < 3.0m
        if width_m > 0 and width_m < 3.0:
            metrics = segment_data.get(seg_id, {})
            if metrics:
                los = metrics.get("worst_los", "Unknown")
                density = metrics.get("peak_density", 0.0)
                
                # Include if elevated density or poor LOS
                if los in ["C", "D", "E", "F"] or density > 0.5:
                    flag_data = flags_by_seg_id.get(seg_id, {})
                    
                    # Issue #694: Extract metrics from flags.json (now calculated in generate_flags_json)
                    # Support both canonical ("flagged_bins") and legacy ("flagged_bin_count") field names
                    flagged_bins = flag_data.get("flagged_bins") or flag_data.get("flagged_bin_count", 0)
                    total_bins = flag_data.get("total_bins", 0)
                    flagged_bin_percentage = flag_data.get("flagged_bin_percentage")  # Extract directly from JSON
                    # If not present in JSON (backward compatibility), calculate from available data
                    if flagged_bin_percentage is None and total_bins > 0:
                        flagged_bin_percentage = (flagged_bins / total_bins) * 100.0
                    
                    # Issue #694: Extract duration metrics from flags.json
                    flagged_duration_seconds = flag_data.get("flagged_duration_seconds", 0.0)
                    flagged_duration_minutes = flag_data.get("flagged_duration_minutes")
                    # If not present, calculate from seconds for backward compatibility
                    if flagged_duration_minutes is None and flagged_duration_seconds > 0:
                        flagged_duration_minutes = flagged_duration_seconds / 60.0
                    flagged_span_duration_seconds = flag_data.get("flagged_span_duration_seconds", 0.0)
                    
                    # Calculate active window duration
                    active_window = metrics.get("active_window", "N/A")
                    active_window_duration = _calculate_active_window_duration(active_window)
                    
                    narrow.append({
                        "day": day,
                        "seg_id": seg_id,
                        "label": props.get("label", seg_id),
                        "length_km": props.get("length_km", 0.0),
                        "width_m": width_m,
                        "direction": props.get("direction", ""),
                        "schema": props.get("schema", ""),
                        "utilization": metrics.get("utilization", 0.0),
                        "los": los,
                        "density": density,
                        "rate": metrics.get("peak_rate", 0.0),
                        "active_window": active_window,
                        "active_window_duration_minutes": active_window_duration,
                        "flagged_bins": flagged_bins,
                        "flagged_bin_percentage": round(flagged_bin_percentage, 2) if flagged_bin_percentage is not None else None,
                        "total_bins": total_bins if total_bins > 0 else None,
                        "flagged_duration_seconds": round(flagged_duration_seconds, 1) if flagged_duration_seconds > 0 else None,
                        "flagged_duration_minutes": round(flagged_duration_minutes, 1) if flagged_duration_minutes else None,
                        "flagged_span_duration_seconds": round(flagged_span_duration_seconds, 1) if flagged_span_duration_seconds > 0 else None
                    })
    
    # Sort by density descending
    narrow.sort(key=lambda x: x["density"], reverse=True)
    return narrow


def _identify_flow_highlights(
    day: str,
    flow_segments: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Identify high-impact flow interactions."""
    highlights = []
    
    for key, seg in flow_segments.items():
        worst_zone = seg.get("worst_zone", {})
        zones = seg.get("zones", [])
        if not worst_zone:
            continue
        
        max_ovt = max(
            worst_zone.get("overtaking_a", 0),
            worst_zone.get("overtaking_b", 0)
        )
        max_cop = max(
            worst_zone.get("copresence_a", 0),
            worst_zone.get("copresence_b", 0)
        )
        
        # Highlight if high overtaking (>100) or high co-presence (>400)
        if max_ovt > 100 or max_cop > 400:
            # Calculate flow zone details
            zone_count = len(zones) if isinstance(zones, list) else 0
            
            # Calculate total zone duration (if available)
            total_zone_duration = None
            if zones:
                total_duration = 0.0
                for zone in zones:
                    if isinstance(zone, dict):
                        # Try to get duration from zone (may not be directly available)
                        # Could be calculated from zone_start_km and zone_end_km if needed
                        pass
                if total_duration > 0:
                    total_zone_duration = total_duration
            
            # Extract convergence points
            convergence_points = []
            if zones:
                for zone in zones:
                    if isinstance(zone, dict):
                        zone_start_km = zone.get("zone_start_km_a") or zone.get("zone_start_km")
                        participants = zone.get("participants_involved", 0)
                        if zone_start_km is not None and participants > 0:
                            convergence_points.append({
                                "km": zone_start_km,
                                "participants_involved": participants
                            })
            
            highlights.append({
                "day": day,
                "segment_pair": key,
                "seg_id": seg.get("seg_id", ""),
                "segment_label": seg.get("segment_label", ""),
                "event_a": seg.get("event_a", ""),
                "event_b": seg.get("event_b", ""),
                "overtaking": max_ovt,
                "copresence": max_cop,
                "participants_involved": worst_zone.get("participants_involved", 0),
                "zone_count": zone_count,
                "total_zone_duration_minutes": total_zone_duration,
                "convergence_points": convergence_points[:5]  # Top 5 convergence points
            })
    
    # Sort by max interaction
    highlights.sort(key=lambda x: max(x["overtaking"], x["copresence"]), reverse=True)
    return highlights[:5]  # Top 5


def save_analysis_context(run_id: str, context_data: Dict[str, Any]) -> Path:
    """
    Save analysis context to ai-summary directory.
    
    Issue #694: Save extracted metrics to {run_id}/ai-summary/analysis-context.json
    
    Args:
        run_id: Run identifier
        context_data: Extracted metrics dictionary
        
    Returns:
        Path to saved file
        
    Raises:
        OSError: If directory creation fails
    """
    run_path = get_run_directory(run_id)
    ai_summary_dir = run_path / "ai-summary"
    ai_summary_dir.mkdir(exist_ok=True)
    
    context_path = ai_summary_dir / "analysis-context.json"
    context_path.write_text(
        json.dumps(context_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    logger.info(f"Saved analysis context to {context_path}")
    return context_path


def generate_analysis_prompt(run_id: str, context_data: Dict[str, Any]) -> str:
    """
    Generate analysis prompt from template and context data.
    
    Issue #694: Generate prompt for OpenAI API or manual use.
    
    Args:
        run_id: Run identifier
        context_data: Extracted metrics dictionary
        
    Returns:
        Complete prompt string
        
    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    # Load template
    template_path = Path(__file__).parent.parent.parent / "docs" / "templates" / "ai-analysis-prompt.md"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found at {template_path}")
    
    template_content = template_path.read_text(encoding="utf-8")
    
    # Convert context data to formatted JSON string
    context_json = json.dumps(context_data, indent=2, ensure_ascii=False)
    
    # Replace placeholders (simple string substitution)
    prompt = template_content.replace("{context_json}", context_json)
    prompt = prompt.replace("{run_id}", run_id)
    prompt = prompt.replace("{scenario}", context_data.get("scenario", "Standard Analysis"))
    
    # Replace units placeholders
    units = context_data.get("metadata", {}).get("units", {})
    for unit_key, unit_value in units.items():
        prompt = prompt.replace(f"{{units.{unit_key}}}", unit_value)
    
    return prompt


def save_analysis_prompt(run_id: str, prompt: str) -> Path:
    """
    Save generated prompt to ai-summary directory.
    
    Issue #694: Save prompt for reproducibility.
    
    Args:
        run_id: Run identifier
        prompt: Generated prompt string
        
    Returns:
        Path to saved file
    """
    run_path = get_run_directory(run_id)
    ai_summary_dir = run_path / "ai-summary"
    ai_summary_dir.mkdir(exist_ok=True)
    
    prompt_path = ai_summary_dir / "prompt-used.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    
    logger.info(f"Saved analysis prompt to {prompt_path}")
    return prompt_path


def generate_ai_assessment(
    run_id: str,
    prompt: str,
    use_openai: bool = False,
    api_key: Optional[str] = None
) -> str:
    """
    Generate AI assessment from prompt.
    
    Issue #694: Generate assessment via OpenAI API or return prompt for manual use.
    
    Args:
        run_id: Run identifier
        prompt: Generated prompt string
        use_openai: If True, call OpenAI API; if False, return prompt for manual use
        api_key: OpenAI API key (required if use_openai=True)
        
    Returns:
        Assessment markdown string (or prompt if use_openai=False)
        
    Raises:
        ValueError: If use_openai=True but api_key is missing
        Exception: If OpenAI API call fails
    """
    if use_openai:
        if not api_key:
            raise ValueError(
                "OpenAI API key required when use_openai=True. "
                "Set OPENAI_API_KEY environment variable or provide api_key parameter."
            )
        
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4-1106-preview"),
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert race operations assistant analyzing course metrics."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4
            )
            
            assessment = response.choices[0].message.content
            
            # Log token usage
            if hasattr(response, 'usage') and response.usage:
                logger.info(
                    f"OpenAI API usage: {response.usage.prompt_tokens} prompt tokens, "
                    f"{response.usage.completion_tokens} completion tokens, "
                    f"{response.usage.total_tokens} total tokens"
                )
            
            return assessment
            
        except ImportError:
            raise ImportError("openai package required for OpenAI API integration. Install with: pip install openai")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    else:
        # Manual mode: return prompt for user to use with Cursor/OpenAI web
        return prompt


def save_ai_assessment(run_id: str, assessment: str) -> Path:
    """
    Save AI-generated assessment to ai-summary directory.
    
    Issue #694: Save final assessment to {run_id}/ai-summary/assessment.md
    
    Args:
        run_id: Run identifier
        assessment: Generated assessment markdown string
        
    Returns:
        Path to saved file
    """
    run_path = get_run_directory(run_id)
    ai_summary_dir = run_path / "ai-summary"
    ai_summary_dir.mkdir(exist_ok=True)
    
    assessment_path = ai_summary_dir / "assessment.md"
    assessment_path.write_text(assessment, encoding="utf-8")
    
    logger.info(f"Saved AI assessment to {assessment_path}")
    return assessment_path


def extract_and_generate_assessment(
    run_id: str,
    use_openai: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Path]:
    """
    Complete workflow: Extract metrics, generate prompt, and create assessment.
    
    Issue #694: One-step function for automated pipeline integration.
    
    Args:
        run_id: Run identifier
        use_openai: If True, call OpenAI API; if False, return prompt for manual use
        api_key: OpenAI API key (required if use_openai=True)
        
    Returns:
        Dictionary with paths to generated files:
        {
            "context": Path to analysis-context.json,
            "prompt": Path to prompt-used.md,
            "assessment": Path to assessment.md (if use_openai=True)
        }
    """
    # Extract metrics
    context_data = extract_analysis_metrics(run_id)
    context_path = save_analysis_context(run_id, context_data)
    
    # Generate prompt
    prompt = generate_analysis_prompt(run_id, context_data)
    prompt_path = save_analysis_prompt(run_id, prompt)
    
    # Generate assessment
    assessment = generate_ai_assessment(run_id, prompt, use_openai, api_key)
    
    result = {
        "context": context_path,
        "prompt": prompt_path
    }
    
    # Save assessment if generated
    if use_openai or assessment != prompt:
        assessment_path = save_ai_assessment(run_id, assessment)
        result["assessment"] = assessment_path
    else:
        # In manual mode, assessment is the prompt
        result["assessment"] = prompt_path
    
    return result


if __name__ == "__main__":
    """CLI interface for AI analysis generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate AI analysis summary for run results")
    parser.add_argument("command", choices=["extract", "prompt", "generate"], help="Command to execute")
    parser.add_argument("--run-id", required=True, help="Run ID to analyze")
    parser.add_argument("--use-openai", action="store_true", help="Use OpenAI API (requires OPENAI_API_KEY)")
    parser.add_argument("--openai-api-key", help="OpenAI API key (overrides OPENAI_API_KEY env var)")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    try:
        if args.command == "extract":
            context_data = extract_analysis_metrics(args.run_id)
            context_path = save_analysis_context(args.run_id, context_data)
            print(f"✅ Extracted metrics saved to: {context_path}")
            
        elif args.command == "prompt":
            context_data = extract_analysis_metrics(args.run_id)
            prompt = generate_analysis_prompt(args.run_id, context_data)
            prompt_path = save_analysis_prompt(args.run_id, prompt)
            print(f"✅ Generated prompt saved to: {prompt_path}")
            
        elif args.command == "generate":
            api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
            results = extract_and_generate_assessment(
                args.run_id,
                use_openai=args.use_openai,
                api_key=api_key
            )
            print(f"✅ Analysis complete:")
            print(f"   Context: {results['context']}")
            print(f"   Prompt: {results['prompt']}")
            if "assessment" in results and results["assessment"] != results["prompt"]:
                print(f"   Assessment: {results['assessment']}")
            else:
                print(f"   Assessment: Use prompt for manual generation")
                
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise
