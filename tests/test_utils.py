"""
Unit tests for app/utils.py module

Tests for safe configuration parsing and other utility functions.
"""

import pytest
from fastapi import HTTPException

from app.utils import parse_config_safely


class TestParseConfigSafely:
    """Test suite for parse_config_safely function."""
    
    def test_valid_config_parses_correctly(self):
        """Test that valid JSON config string parses correctly."""
        config = '{"width": 5, "length": 10, "bin_seconds": 30}'
        result = parse_config_safely(config)
        assert result == {"width": 5, "length": 10, "bin_seconds": 30}
    
    def test_empty_config_returns_empty_dict(self):
        """Test that empty config string returns empty dict."""
        result = parse_config_safely("")
        assert result == {}
        
        result = parse_config_safely(None)
        assert result == {}
    
    def test_invalid_config_raises_http_exception(self):
        """Test that invalid JSON config raises HTTP 400 exception."""
        with pytest.raises(HTTPException) as exc_info:
            parse_config_safely("{invalid_json}")
        
        assert exc_info.value.status_code == 400
        assert "Invalid config format" in str(exc_info.value.detail)
    
    def test_malformed_json_raises_http_exception(self):
        """Test that malformed JSON raises HTTP 400 exception."""
        with pytest.raises(HTTPException) as exc_info:
            parse_config_safely("{'single_quotes': 'not_json'}")
        
        assert exc_info.value.status_code == 400
    
    def test_unclosed_brace_raises_http_exception(self):
        """Test that unclosed JSON braces raise HTTP 400 exception."""
        with pytest.raises(HTTPException) as exc_info:
            parse_config_safely('{"incomplete": ')
        
        assert exc_info.value.status_code == 400
    
    def test_number_config_parses_correctly(self):
        """Test that numeric values parse correctly."""
        config = '{"threshold": 1.5, "count": 42}'
        result = parse_config_safely(config)
        assert result == {"threshold": 1.5, "count": 42}
    
    def test_array_config_parses_correctly(self):
        """Test that arrays in config parse correctly."""
        config = '{"items": [1, 2, 3], "tags": ["a", "b"]}'
        result = parse_config_safely(config)
        assert result == {"items": [1, 2, 3], "tags": ["a", "b"]}
    
    def test_nested_config_parses_correctly(self):
        """Test that nested objects parse correctly."""
        config = '{"config": {"inner": {"value": 42}}}'
        result = parse_config_safely(config)
        assert result == {"config": {"inner": {"value": 42}}}
    
    def test_boolean_config_parses_correctly(self):
        """Test that boolean values parse correctly."""
        config = '{"enabled": true, "disabled": false}'
        result = parse_config_safely(config)
        assert result == {"enabled": True, "disabled": False}
    
    def test_null_config_parses_correctly(self):
        """Test that null values parse correctly."""
        config = '{"value": null, "data": {"nested": null}}'
        result = parse_config_safely(config)
        assert result == {"value": None, "data": {"nested": None}}
