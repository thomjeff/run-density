# app/rulebook.py
"""
Single Source of Truth (SSOT) for density rulebook logic.

This module is the ONLY place that reads density_rulebook.yml and implements
threshold evaluation. All consumers (reports, maps, UI) must use this module
to ensure consistency.

LOS computation is centralized here as well. LOS must never be recomputed or
defaulted elsewhere; downstream systems should only consume los_class outputs
from this module.

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
    util_percent: Optional[float]       # % of flow_ref.critical (schema capacity)
    util_percentile: Optional[float]    # Percentile rank within cohort (0-100)
    severity: str                       # "none"|"watch"|"caution"|"critical"
    flag_reason: Optional[str]          # None|"density"|"utilization"|"rate"|"both"

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
    # Try meta.version first, fallback to version
    meta = data.get("meta", {})
    return str(meta.get("version") or data.get("version", "unversioned"))

@functools.lru_cache(maxsize=1)
def get_policy(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get global policy configuration.
    
    Returns policy dict with:
    - density_watch_at: LOS threshold for watch flagging (e.g., "C")
    - density_critical_at: LOS threshold for critical flagging (e.g., "E")
    - utilization_pctile: Percentile threshold for utilization flagging (e.g., 95)
    - utilization_cohort: Cohort for percentile calculation (e.g., "window")
    """
    data = _load_yaml(path)
    policy = data.get("globals", {}).get("policy", {})
    
    # Defaults matching user's operational baseline
    return {
        "density_watch_at": policy.get("density_watch_at", "C"),
        "density_critical_at": policy.get("density_critical_at", "E"),
        "utilization_pctile": policy.get("utilization_pctile", 95),
        "utilization_cohort": policy.get("utilization_cohort", "window")
    }

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

def los_ge(los_class: str, threshold: str) -> bool:
    """
    Check if LOS class is greater than or equal to threshold.
    
    LOS ordering: A < B < C < D < E < F
    
    Args:
        los_class: Current LOS (e.g., "C")
        threshold: Threshold LOS (e.g., "C")
        
    Returns:
        True if los_class >= threshold
    """
    los_order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
    return los_order.get(los_class, 0) >= los_order.get(threshold, 0)

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
    util_percentile: Optional[float] = None,  # NEW: precomputed percentile rank
    path: Optional[str] = None
) -> FlagResult:
    """
    Evaluate flagging for a single bin using unified policy (Issue #254 v2.2).
    
    Implements ChatGPT's specification:
    - Density trigger: LOS >= C (watch), LOS >= E (critical)
    - Utilization trigger: percentile >= P95 (watch)
    - Rate trigger: Schema-specific flow_ref thresholds
    - Combined severity: CRITICAL > CAUTION > WATCH > NONE
    
    Args:
        density_pm2: Areal density in persons per square meter
        rate_p_s: Throughput rate in persons per second (None if no flow)
        width_m: Segment width in meters (None or <=0 if unknown)
        schema_key: Segment schema key (e.g., "start_corral", "on_course_narrow")
        util_percentile: Precomputed percentile rank (0-100) within cohort
        path: Optional path to rulebook YAML
    
    Returns:
        FlagResult with los_class, rpm, util_percent, util_percentile, severity, flag_reason
    """
    th = get_thresholds(schema_key, path)
    policy = get_policy(path)
    
    # 1) Classify LOS from density
    los = classify_los(density_pm2, th.los)

    # 2) Compute rate per meter per minute
    rpm: Optional[float] = None
    if rate_p_s is not None and width_m and width_m > 0:
        rpm = (float(rate_p_s) / float(width_m)) * 60.0
    
    # 3) Compute utilization vs flow_ref.critical (schema capacity)
    util_vs_crit: Optional[float] = None
    if rpm is not None and th.flow_ref and th.flow_ref.critical:
        util_vs_crit = 100.0 * rpm / th.flow_ref.critical

    # 4) Independent triggers
    # Density trigger: from policy (watch at C, critical at E)
    density_watch = los_ge(los, policy["density_watch_at"])
    density_critical = los_ge(los, policy["density_critical_at"])
    
    # Utilization trigger: percentile >= P95
    util_watch = (util_percentile is not None and util_percentile >= policy["utilization_pctile"])
    
    # Rate trigger: schema-specific flow_ref
    rate_flag = None
    if rpm is not None and th.flow_ref:
        rate_flag = _severity_from_value(rpm, th.flow_ref.warn, th.flow_ref.critical)

    # 5) Combine per severity rules (ChatGPT's specification)
    # CRITICAL: (LOS ≥ C AND util ≥ P95) OR rate critical OR (density critical)
    # CAUTION:  LOS ≥ C ONLY OR (LOS ≥ C AND rate watch)
    # WATCH:    util ≥ P95 ONLY OR rate watch ONLY
    # NONE:     else
    
    severity = "none"
    reason = None
    
    if (density_watch and util_watch) or density_critical or rate_flag == "critical":
        severity = "critical"
        # Determine reason
        if density_watch and util_watch:
            reason = "both"
        elif density_critical and rate_flag == "critical":
            reason = "both"
        elif rate_flag == "critical":
            reason = "rate"
        elif density_critical:
            reason = "density"
        else:
            reason = "both"  # density_watch + util_watch
            
    elif density_watch or rate_flag == "watch":
        severity = "caution"
        if density_watch and rate_flag == "watch":
            reason = "both"
        elif density_watch:
            reason = "density"
        else:
            reason = "rate"
            
    elif util_watch:
        severity = "watch"
        reason = "utilization"

    return FlagResult(
        los_class=los,
        rate_per_m_per_min=(None if rpm is None else float(rpm)),
        util_percent=(None if util_vs_crit is None else float(util_vs_crit)),
        util_percentile=util_percentile,
        severity=severity,
        flag_reason=reason
    )

