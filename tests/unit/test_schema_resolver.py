"""
Unit tests for schema resolver.

Issue #557: dict Object Has No Attribute 'lower' in Flagging Engine
"""

import pytest
from app.schema_resolver import resolve_schema


class TestResolveSchema:
    """Test resolve_schema function."""
    
    def test_resolves_explicit_mapping(self):
        """Test that explicit segment mappings work."""
        assert resolve_schema("A1") == "start_corral"
        assert resolve_schema("B1") == "on_course_narrow"
        assert resolve_schema("A2") == "on_course_open"
    
    def test_resolves_from_segment_type_narrow(self):
        """Test that segment_type mapping works for narrow segments."""
        assert resolve_schema("X1", "funnel") == "on_course_narrow"
        assert resolve_schema("X2", "bridge") == "on_course_narrow"
        assert resolve_schema("X3", "narrow") == "on_course_narrow"
    
    def test_resolves_from_segment_type_start(self):
        """Test that segment_type mapping works for start corrals."""
        assert resolve_schema("X1", "start") == "start_corral"
        assert resolve_schema("X2", "corral") == "start_corral"
    
    def test_defaults_to_open_course(self):
        """Test that unknown segments default to on_course_open."""
        assert resolve_schema("UNKNOWN") == "on_course_open"
        assert resolve_schema("X99", "unknown_type") == "on_course_open"
    
    def test_raises_type_error_for_dict_segment_type(self):
        """Test that TypeError is raised when segment_type is a dict (Issue #557)."""
        with pytest.raises(TypeError, match="Expected string for segment_type"):
            resolve_schema("A1", {"some": "dict"})
    
    def test_raises_type_error_for_list_segment_type(self):
        """Test that TypeError is raised when segment_type is a list."""
        with pytest.raises(TypeError, match="Expected string for segment_type"):
            resolve_schema("A1", ["list", "value"])
    
    def test_handles_none_segment_type(self):
        """Test that None segment_type is handled correctly."""
        # Should use explicit mapping or default
        assert resolve_schema("A1", None) == "start_corral"
        assert resolve_schema("UNKNOWN", None) == "on_course_open"
    
    def test_case_insensitive_segment_type(self):
        """Test that segment_type is case-insensitive."""
        assert resolve_schema("X1", "FUNNEL") == "on_course_narrow"
        assert resolve_schema("X2", "Bridge") == "on_course_narrow"
        assert resolve_schema("X3", "START") == "start_corral"

