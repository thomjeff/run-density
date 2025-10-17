# tests/test_rulebook_flags.py
"""
Unit tests for app/rulebook.py

Tests threshold loading, LOS classification, rate conversion,
and flag evaluation logic per Issue #254.
"""
import math
import pytest
import app.rulebook as rb

# --- Helpers to inject a tiny test rulebook in-memory ---

_FAKE_YAML = {
    "version": "2.1",
    "globals": {
        "los_thresholds": {
            "A": {"min": 0.0, "max": 0.36, "label": "Free flow"},
            "B": {"min": 0.36, "max": 0.54, "label": "Comfortable"},
            "C": {"min": 0.54, "max": 0.72, "label": "Moderate"},
            "D": {"min": 0.72, "max": 1.08, "label": "Dense"},
            "E": {"min": 1.08, "max": 1.63, "label": "Very dense"},
            "F": {"min": 1.63, "max": 999.0, "label": "Extremely dense"}
        }
    },
    "schemas": {
        "start_corral": {
            "label": "Start Corral",
            "los_thresholds": {
                "A": {"min": 0.0, "max": 0.5, "label": "Free flow"},
                "B": {"min": 0.5, "max": 0.9, "label": "Comfortable"},
                "C": {"min": 0.9, "max": 1.6, "label": "Moderate"},
                "D": {"min": 1.6, "max": 2.3, "label": "Dense"},
                "E": {"min": 2.3, "max": 3.0, "label": "Very dense"},
                "F": {"min": 3.0, "max": 999.0, "label": "Extremely dense"}
            },
            "flow_ref": {"warn": 500, "critical": 600}  # p/min/m
        },
        "on_course_narrow": {
            "label": "Narrow",
            # No los_thresholds => uses globals
            "flow_ref": {"warn": 300, "critical": 400}
        },
        "on_course_open": {
            "label": "Open"
            # No los_thresholds => uses globals
            # No flow_ref => skip rate flags
        }
    }
}

def _monkey_yaml(monkeypatch):
    """Replace YAML loading with fake data and reset caches."""
    def fake_load_yaml(path=None):
        return _FAKE_YAML
    
    # Reset caches
    rb._load_yaml.cache_clear()
    rb._threshold_index.cache_clear()
    rb.version.cache_clear()
    
    monkeypatch.setattr(rb, "_load_yaml", fake_load_yaml)

# --- Tests ---

def test_version(monkeypatch):
    """Test rulebook version loading."""
    _monkey_yaml(monkeypatch)
    assert rb.version() == "2.1"

def test_los_classification(monkeypatch):
    """Test LOS band classification for start_corral (schema override)."""
    _monkey_yaml(monkeypatch)
    th = rb.get_thresholds("start_corral")
    
    # start_corral has override: A=0.5, B=0.9, C=1.6, D=2.3, E=3.0
    assert rb.classify_los(0.45, th.los) == "A"  # Just below A max
    assert rb.classify_los(0.5, th.los) == "A"   # At A max (inclusive)
    assert rb.classify_los(0.89, th.los) == "B"  # Just below B max
    assert rb.classify_los(0.9, th.los) == "B"   # At B max
    assert rb.classify_los(1.59, th.los) == "C"  # Just below C max
    assert rb.classify_los(1.6, th.los) == "C"   # At C max
    assert rb.classify_los(2.29, th.los) == "D"  # Just below D max
    assert rb.classify_los(2.3, th.los) == "D"   # At D max
    assert rb.classify_los(2.99, th.los) == "E"  # Just below E max
    assert rb.classify_los(3.0, th.los) == "E"   # At E max
    assert rb.classify_los(3.1, th.los) == "F"   # Above E max

def test_rate_conversion_and_no_flags(monkeypatch):
    """Test rate conversion and no flagging when below thresholds."""
    _monkey_yaml(monkeypatch)
    
    # Example: width=5m, rate=10 p/s -> rpm = (10/5)*60 = 120 p/min/m
    res = rb.evaluate_flags(
        density_pm2=0.3,  # LOS A under globals (< 0.36)
        rate_p_s=10.0,
        width_m=5.0,
        schema_key="on_course_narrow"
    )
    
    # Check rate conversion
    assert math.isclose(res.rate_per_m_per_min, 120.0, rel_tol=1e-6)
    
    # Narrow thresholds: warn=300, critical=400
    # 120 < 300 => no rate flag
    # 0.3 density => LOS A (globals) => no density flag
    assert res.los_class == "A"
    assert res.severity == "none"
    assert res.flag_reason is None

def test_rate_watch_flag(monkeypatch):
    """Test rate-based watch flagging."""
    _monkey_yaml(monkeypatch)
    
    # Narrow: warn=300, critical=400
    # width=5, rate=25 p/s -> rpm= (25/5)*60 = 300 => watch on rate alone
    # Use low density (< 0.36) to stay in LOS A under globals
    res = rb.evaluate_flags(0.3, 25.0, 5.0, "on_course_narrow")
    
    assert math.isclose(res.rate_per_m_per_min, 300.0, rel_tol=1e-6)
    assert res.los_class == "A"  # Low density under globals
    assert res.severity == "watch"
    assert res.flag_reason == "rate"

def test_rate_critical_flag(monkeypatch):
    """Test rate-based critical flagging."""
    _monkey_yaml(monkeypatch)
    
    # width=5, rate=40 p/s -> rpm = 480 => critical on rate
    # Use low density to stay in LOS A
    res = rb.evaluate_flags(0.3, 40.0, 5.0, "on_course_narrow")
    
    assert math.isclose(res.rate_per_m_per_min, 480.0, rel_tol=1e-6)
    assert res.los_class == "A"  # Low density under globals
    assert res.severity == "critical"
    assert res.flag_reason == "rate"

def test_density_watch_flag(monkeypatch):
    """Test density-based watch flagging (LOS D)."""
    _monkey_yaml(monkeypatch)
    
    # Use on_course_narrow (uses globals) with density in LOS D range (0.72-1.08)
    res = rb.evaluate_flags(density_pm2=0.9, rate_p_s=0.0, width_m=5.0, schema_key="on_course_narrow")
    
    assert res.los_class == "D"  # 0.9 is in D range under globals
    assert res.severity == "watch"
    assert res.flag_reason == "density"

def test_density_critical_flag(monkeypatch):
    """Test density-based critical flagging (LOS E/F)."""
    _monkey_yaml(monkeypatch)
    
    # LOS E should trigger critical density flag (use globals via on_course_narrow)
    res_e = rb.evaluate_flags(density_pm2=1.2, rate_p_s=0.0, width_m=5.0, schema_key="on_course_narrow")
    assert res_e.los_class == "E"  # 1.2 > 1.08 under globals
    assert res_e.severity == "critical"
    assert res_e.flag_reason == "density"
    
    # LOS F should also trigger critical
    res_f = rb.evaluate_flags(density_pm2=2.0, rate_p_s=0.0, width_m=5.0, schema_key="on_course_narrow")
    assert res_f.los_class == "F"  # 2.0 > 1.63 under globals
    assert res_f.severity == "critical"
    assert res_f.flag_reason == "density"

def test_both_flags(monkeypatch):
    """Test combined density + rate flagging."""
    _monkey_yaml(monkeypatch)
    
    # High density (LOS E under globals) + high rate => both
    # Use on_course_narrow (uses globals) with density=1.2 (LOS E) and high rate
    # width=5, rate=40 p/s -> rpm = 480 (critical for narrow: 400)
    res = rb.evaluate_flags(density_pm2=1.2, rate_p_s=40.0, width_m=5.0, schema_key="on_course_narrow")
    
    assert res.los_class == "E"  # 1.2 > 1.08 under globals
    assert math.isclose(res.rate_per_m_per_min, 480.0, rel_tol=1e-6)
    assert res.severity == "critical"
    assert res.flag_reason == "both"  # Both density (E) and rate (480>400) trigger

def test_open_course_skips_rate(monkeypatch):
    """Test that schemas without flow_ref skip rate flagging."""
    _monkey_yaml(monkeypatch)
    
    # on_course_open has no flow_ref => rate flagged must be skipped
    res = rb.evaluate_flags(density_pm2=0.3, rate_p_s=999.0, width_m=5.0, schema_key="on_course_open")
    
    # Rate should still be computed for display
    assert res.rate_per_m_per_min == (999.0/5.0)*60.0
    
    # But no rate-based flagging
    assert res.severity == "none"  # Low density, no rate thresholds
    assert res.flag_reason is None

def test_utilization_calculation(monkeypatch):
    """Test utilization percentage calculation."""
    _monkey_yaml(monkeypatch)
    
    # start_corral critical=600 p/min/m
    # width=5, rate=50 p/s -> rpm=600 => util=100%
    res = rb.evaluate_flags(density_pm2=0.3, rate_p_s=50.0, width_m=5.0, schema_key="start_corral")
    
    assert math.isclose(res.rate_per_m_per_min, 600.0, rel_tol=1e-6)
    assert math.isclose(res.util_percent, 100.0, rel_tol=1e-6)
    
    # Test 50% utilization
    res_50 = rb.evaluate_flags(density_pm2=0.3, rate_p_s=25.0, width_m=5.0, schema_key="start_corral")
    assert math.isclose(res_50.rate_per_m_per_min, 300.0, rel_tol=1e-6)
    assert math.isclose(res_50.util_percent, 50.0, rel_tol=1e-6)

def test_zero_width_handling(monkeypatch):
    """Test handling of zero or negative width."""
    _monkey_yaml(monkeypatch)
    
    # Zero width should result in no rate calculation
    res = rb.evaluate_flags(density_pm2=0.5, rate_p_s=10.0, width_m=0.0, schema_key="start_corral")
    
    assert res.rate_per_m_per_min is None
    assert res.util_percent is None
    assert res.severity == "none"  # LOS A, no rate to flag

def test_none_rate_handling(monkeypatch):
    """Test handling of None rate (no flow)."""
    _monkey_yaml(monkeypatch)
    
    # None rate should result in no rate calculation
    res = rb.evaluate_flags(density_pm2=0.5, rate_p_s=None, width_m=5.0, schema_key="start_corral")
    
    assert res.rate_per_m_per_min is None
    assert res.util_percent is None
    assert res.severity == "none"  # LOS A, no rate to flag

def test_unknown_schema_fallback(monkeypatch):
    """Test fallback behavior for unknown schema."""
    _monkey_yaml(monkeypatch)
    
    # Unknown schema should use defaults and skip rate flagging
    res = rb.evaluate_flags(density_pm2=0.5, rate_p_s=10.0, width_m=5.0, schema_key="unknown_schema")
    
    assert res.los_class == "A"  # Default LOS bands
    assert res.rate_per_m_per_min == 120.0  # Rate still computed
    assert res.util_percent is None  # No flow_ref => no util
    assert res.severity == "none"
    assert res.flag_reason is None

def test_boundary_at_thresholds(monkeypatch):
    """Test exact boundary conditions at thresholds."""
    _monkey_yaml(monkeypatch)
    
    # Test exactly at warn threshold (should trigger watch)
    # on_course_narrow: warn=300
    # width=5, rate=25 p/s -> rpm=300
    res_warn = rb.evaluate_flags(0.3, 25.0, 5.0, "on_course_narrow")
    assert res_warn.severity == "watch"
    assert res_warn.flag_reason == "rate"
    
    # Test exactly at critical threshold (should trigger critical)
    # on_course_narrow: critical=400
    # width=3, rate=20 p/s -> rpm=400
    res_crit = rb.evaluate_flags(0.3, 20.0, 3.0, "on_course_narrow")
    assert res_crit.severity == "critical"
    assert res_crit.flag_reason == "rate"
    
    # Test just below warn threshold (should not trigger)
    # width=5, rate=24.99 p/s -> rpm=299.88
    res_below = rb.evaluate_flags(0.3, 24.99, 5.0, "on_course_narrow")
    assert res_below.severity == "none"

def test_severity_precedence(monkeypatch):
    """Test that critical takes precedence over watch."""
    _monkey_yaml(monkeypatch)
    
    # Density watch (LOS D under globals: 0.72-1.08) + rate critical => overall critical
    # width=5, rate=40 p/s -> rpm=480 (critical for narrow: 400)
    res = rb.evaluate_flags(density_pm2=0.9, rate_p_s=40.0, width_m=5.0, schema_key="on_course_narrow")
    
    assert res.los_class == "D"  # Watch level for density (0.9 in D range)
    assert res.severity == "critical"  # Critical level overall (rate critical)
    assert res.flag_reason == "both"

def test_global_thresholds_exact_boundaries(monkeypatch):
    """Test exact boundary conditions for global LOS thresholds."""
    _monkey_yaml(monkeypatch)
    th = rb.get_thresholds("on_course_open")
    
    # Test exact boundaries (global thresholds: 0.36, 0.54, 0.72, 1.08, 1.63)
    assert rb.classify_los(0.35, th.los) == "A"  # Just below B
    assert rb.classify_los(0.36, th.los) == "A"  # At A threshold (inclusive)
    assert rb.classify_los(0.53, th.los) == "B"  # Just below C
    assert rb.classify_los(0.54, th.los) == "B"  # At B threshold
    assert rb.classify_los(0.71, th.los) == "C"  # Just below D
    assert rb.classify_los(0.72, th.los) == "C"  # At C threshold
    assert rb.classify_los(1.07, th.los) == "D"  # Just below E
    assert rb.classify_los(1.08, th.los) == "D"  # At D threshold
    assert rb.classify_los(1.62, th.los) == "E"  # Just below F
    assert rb.classify_los(1.63, th.los) == "E"  # At E threshold
    assert rb.classify_los(1.64, th.los) == "F"  # Above E

def test_start_corral_override_boundaries(monkeypatch):
    """Test that start_corral uses its own LOS thresholds."""
    _monkey_yaml(monkeypatch)
    th = rb.get_thresholds("start_corral")
    
    # start_corral has different thresholds: A=0.5, B=0.9, C=1.6, D=2.3, E=3.0
    assert rb.classify_los(0.49, th.los) == "A"
    assert rb.classify_los(0.5, th.los) == "A"
    assert rb.classify_los(0.755, th.los) == "B"  # Would be D under globals!
    assert rb.classify_los(0.89, th.los) == "B"
    assert rb.classify_los(0.9, th.los) == "B"
    assert rb.classify_los(1.59, th.los) == "C"
    assert rb.classify_los(1.6, th.los) == "C"

def test_no_rate_flags_for_open_course(monkeypatch):
    """Test that on_course_open has no rate thresholds."""
    _monkey_yaml(monkeypatch)
    
    # Even with very high rate, no rate flag should fire for on_course_open
    res = rb.evaluate_flags(
        density_pm2=0.3,  # LOS A
        rate_p_s=100.0,   # Very high
        width_m=5.0,
        schema_key="on_course_narrow"
    )
    
    # Narrow has thresholds, so high rate should flag
    assert res.severity in ("watch", "critical")
    assert res.flag_reason in ("rate", "both")
    
    # Same rate on open course - should not flag
    res_open = rb.evaluate_flags(
        density_pm2=0.3,
        rate_p_s=100.0,
        width_m=5.0,
        schema_key="on_course_open"
    )
    assert res_open.severity == "none"  # No rate threshold
    assert res_open.flag_reason is None

