# app/rulebook.py
"""
Single Source of Truth (SSOT) for density rulebook logic.

This module is the ONLY place that reads density_rulebook.yml and implements
threshold evaluation. All consumers (reports, maps, UI) must use this module
to ensure consistency.

Issue #254: Centralize Rulebook Logic
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import yaml
import pathlib
import functools
import logging

logger = logging.getLogger(__name__)

# ---------- Data Models ----------

@dataclass(frozen=True)
class FlowRef:
    """Flow reference thresholds for rate-based flagging (p/min/m)."""
    warn: Optional[float]        # p/min/m  (None => no rate-based flags)
    critical: Optional[float]    # p/min/m

@dataclass(frozen=True)
class LosBands:
    """Level of Service density thresholds (p/m²)."""
    # Upper bounds for A..F in p/m² (F may be omitted or very large)
    A: float
    B: float
    C: float
    D: float
    E: float
    F: float

@dataclass(frozen=True)
class SchemaThresholds:
    """Complete threshold configuration for a segment schema."""
    schema_key: str
    los: LosBands
    flow_ref: Optional[FlowRef]     # None if not defined (skip rate flags)
    label: Optional[str] = None     # optional human-friendly name

@dataclass(frozen=True)
class FlagResult:
    """Result of flag evaluation for a single bin."""
    los_class: str                      # "A".."F"
    rate_per_m_per_min: Optional[float] # None if width <= 0 or rate missing
    util_percent: Optional[float]       # None if no flow_ref.critical
    severity: str                       # "none"|"watch"|"critical"
    flag_reason: Optional[str]          # None|"density"|"rate"|"both"

# ---------- Loader / SSOT ----------

_DEFAULT_RULEBOOK_PATH = pathlib.Path("config/density_rulebook.yml")

def _extract_max(threshold_obj, default: float) -> float:
    """
    Extract max value from threshold object.
    
    Handles both formats:
    - Simple number: 0.36
    - Dict with min/max: {min: 0.0, max: 0.36, label: "..."}
    """
    if threshold_obj is None:
        return default
    if isinstance(threshold_obj, (int, float)):
        return float(threshold_obj)
    if isinstance(threshold_obj, dict) and 'max' in threshold_obj:
        return float(threshold_obj['max'])
    return default

@functools.lru_cache(maxsize=1)
def _load_yaml(path: Optional[str] = None) -> Dict[str, Any]:
    """Load rulebook YAML (cached)."""
    p = pathlib.Path(path or _DEFAULT_RULEBOOK_PATH)
    logger.info(f"Loading rulebook from {p}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@functools.lru_cache(maxsize=1)
def version(path: Optional[str] = None) -> str:
    """Get rulebook version."""
    data = _load_yaml(path)
    return str(data.get("version", "unversioned"))

@functools.lru_cache(maxsize=1)
def _threshold_index(path: Optional[str] = None) -> Dict[str, SchemaThresholds]:
    """Build index of schema thresholds from rulebook (cached)."""
    data = _load_yaml(path)

    # Load global LOS thresholds (fallback for schemas without their own)
    global_los_cfg = data.get("globals", {}).get("los_thresholds", {})
    default_bands = LosBands(
        A=float(_extract_max(global_los_cfg.get("A"), 0.36)),
        B=float(_extract_max(global_los_cfg.get("B"), 0.54)),
        C=float(_extract_max(global_los_cfg.get("C"), 0.72)),
        D=float(_extract_max(global_los_cfg.get("D"), 1.08)),
        E=float(_extract_max(global_los_cfg.get("E"), 1.63)),
        F=float(_extract_max(global_los_cfg.get("F"), 999.0)),
    )
    
    logger.info(f"Global LOS bands: A={default_bands.A}, B={default_bands.B}, C={default_bands.C}, D={default_bands.D}, E={default_bands.E}, F={default_bands.F}")

    out: Dict[str, SchemaThresholds] = {}
    schemas = data.get("schemas", {})
    
    for key, cfg in schemas.items():
        # Use schema-specific LOS if present, otherwise use global defaults
        if "los_thresholds" in cfg:
            los_cfg = cfg["los_thresholds"]
            bands = LosBands(
                A=float(_extract_max(los_cfg.get("A"), default_bands.A)),
                B=float(_extract_max(los_cfg.get("B"), default_bands.B)),
                C=float(_extract_max(los_cfg.get("C"), default_bands.C)),
                D=float(_extract_max(los_cfg.get("D"), default_bands.D)),
                E=float(_extract_max(los_cfg.get("E"), default_bands.E)),
                F=float(_extract_max(los_cfg.get("F"), default_bands.F)),
            )
            logger.info(f"Schema {key}: Using schema-specific LOS bands")
        else:
            # Use global defaults
            bands = default_bands
            logger.info(f"Schema {key}: Using global LOS bands")
        
        # Load flow_ref if present
        fr = None
        if "flow_ref" in cfg and cfg["flow_ref"] is not None:
            fr_cfg = cfg["flow_ref"]
            # Handle None/"none"/empty values
            warn_val = fr_cfg.get("warn")
            crit_val = fr_cfg.get("critical")
            if warn_val not in (None, "", "none") or crit_val not in (None, "", "none"):
                fr = FlowRef(
                    warn=(None if warn_val in (None, "", "none") else float(warn_val)),
                    critical=(None if crit_val in (None, "", "none") else float(crit_val))
                )
        
        out[key] = SchemaThresholds(
            schema_key=key,
            los=bands,
            flow_ref=fr,
            label=cfg.get("label")
        )
    
    logger.info(f"Loaded {len(out)} schema configurations from rulebook v{version(path)}")
    return out

def get_thresholds(schema_key: str, path: Optional[str] = None) -> SchemaThresholds:
    """
    Get thresholds for a specific schema.
    
    If schema_key not found, returns conservative defaults with no rate flagging.
    """
    idx = _threshold_index(path)
    if schema_key not in idx:
        logger.warning(f"Schema '{schema_key}' not found in rulebook, using defaults")
        # Fallback: use a conservative default LOS; no rate flags
        return SchemaThresholds(
            schema_key=schema_key,
            los=LosBands(A=0.5, B=0.9, C=1.6, D=2.3, E=3.0, F=99.0),
            flow_ref=None,
            label=None
        )
    return idx[schema_key]

# ---------- LOS & Flagging ----------

def classify_los(density_pm2: float, bands: LosBands) -> str:
    """
    Classify density into LOS bands (A-F).
    
    Uses upper-bound classification: if density <= threshold, assign that LOS.
    """
    d = max(0.0, float(density_pm2 or 0.0))
    
    # Upper-bound classification
    if d <= bands.A: return "A"
    if d <= bands.B: return "B"
    if d <= bands.C: return "C"
    if d <= bands.D: return "D"
    if d <= bands.E: return "E"
    return "F"  # > E → F

def _severity_from_value(val: float, warn: Optional[float], crit: Optional[float]) -> Optional[str]:
    """
    Determine severity level from a value and thresholds.
    
    Returns: "critical", "watch", or None
    """
    # None => no thresholds → no flagging
    if warn is None and crit is None:
        return None
    
    # Check critical first
    if crit is not None and val >= crit:
        return "critical"
    
    # Then check watch
    if warn is not None and val >= warn:
        return "watch"
    
    return None

def evaluate_flags(
    density_pm2: float,
    rate_p_s: Optional[float],
    width_m: Optional[float],
    schema_key: str,
    path: Optional[str] = None
) -> FlagResult:
    """
    Evaluate flagging for a single bin.
    
    This is the MAIN function that all consumers should use.
    
    Args:
        density_pm2: Areal density in persons per square meter
        rate_p_s: Throughput rate in persons per second (None if no flow)
        width_m: Segment width in meters (None or <=0 if unknown)
        schema_key: Segment schema key (e.g., "start_corral", "on_course_narrow")
        path: Optional path to rulebook YAML (defaults to config/density_rulebook.yml)
    
    Returns:
        FlagResult with los_class, rate_per_m_per_min, util_percent, severity, flag_reason
    """
    th = get_thresholds(schema_key, path)
    
    # Classify LOS from density
    los = classify_los(density_pm2, th.los)

    # Compute rate per meter per minute if possible
    rpm: Optional[float] = None
    if rate_p_s is not None and width_m and width_m > 0:
        rpm = (float(rate_p_s) / float(width_m)) * 60.0
    
    # Compute utilization vs flow_ref.critical if available
    util: Optional[float] = None
    if rpm is not None and th.flow_ref and th.flow_ref.critical:
        util = 100.0 * rpm / th.flow_ref.critical

    # Density-based flag: E/F are critical, D is watch, A/B/C are none
    # (Adjust if your rulebook has explicit density warn/critical separate from LOS)
    density_flag = None
    if los in ("E", "F"):
        density_flag = "critical"
    elif los == "D":
        density_flag = "watch"

    # Rate-based flag: check against schema thresholds
    rate_flag = None
    if rpm is not None and th.flow_ref:
        rate_flag = _severity_from_value(rpm, th.flow_ref.warn, th.flow_ref.critical)

    # Combine severity: highest level wins
    if density_flag == "critical" or rate_flag == "critical":
        severity = "critical"
    elif density_flag == "watch" or rate_flag == "watch":
        severity = "watch"
    else:
        severity = "none"

    # Determine reason
    reason = _combine_reason(density_flag, rate_flag)

    return FlagResult(
        los_class=los,
        rate_per_m_per_min=(None if rpm is None else float(rpm)),
        util_percent=(None if util is None else float(util)),
        severity=severity,
        flag_reason=reason
    )

def _combine_reason(density_flag: Optional[str], rate_flag: Optional[str]) -> Optional[str]:
    """Combine density and rate flags into a reason code."""
    if density_flag and rate_flag:
        return "both"
    if density_flag:
        return "density"
    if rate_flag:
        return "rate"
    return None

