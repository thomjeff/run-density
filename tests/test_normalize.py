"""
Unit tests for normalization module (app.normalize)

Tests all supported alias formats and edge cases.
"""

import pytest
from app.normalize import (
    normalize_segment_id,
    normalize_checkpoint_id,
    normalize_cursor_index
)


class TestNormalizeSegmentId:
    """Tests for normalize_segment_id function."""
    
    def test_canonical_segment_id(self):
        """Test canonical 'segment_id' format."""
        request = {'segment_id': 'A1'}
        assert normalize_segment_id(request) == 'A1'
    
    def test_camelcase_segmentId(self):
        """Test camelCase 'segmentId' format."""
        request = {'segmentId': 'B2'}
        assert normalize_segment_id(request) == 'B2'
    
    def test_internal_seg_id(self):
        """Test internal data layer 'seg_id' format."""
        request = {'seg_id': 'C3'}
        assert normalize_segment_id(request) == 'C3'
    
    def test_mixed_segId(self):
        """Test mixed case 'segId' format."""
        request = {'segId': 'D4'}
        assert normalize_segment_id(request) == 'D4'
    
    def test_priority_canonical_first(self):
        """Test that canonical name takes priority when multiple exist."""
        request = {
            'segment_id': 'canonical',
            'segmentId': 'camelCase',
            'seg_id': 'internal'
        }
        assert normalize_segment_id(request) == 'canonical'
    
    def test_not_found_returns_none(self):
        """Test that missing segment_id returns None."""
        request = {'other_key': 'value'}
        assert normalize_segment_id(request) is None
    
    def test_not_found_with_default(self):
        """Test that missing segment_id returns provided default."""
        request = {'other_key': 'value'}
        assert normalize_segment_id(request, default='default') == 'default'
    
    def test_empty_dict(self):
        """Test with empty dictionary."""
        request = {}
        assert normalize_segment_id(request) is None


class TestNormalizeCheckpointId:
    """Tests for normalize_checkpoint_id function."""
    
    def test_canonical_checkpoint_id(self):
        """Test canonical 'checkpoint_id' format."""
        request = {'checkpoint_id': 'CP1'}
        assert normalize_checkpoint_id(request) == 'CP1'
    
    def test_camelcase_checkpointId(self):
        """Test camelCase 'checkpointId' format."""
        request = {'checkpointId': 'CP2'}
        assert normalize_checkpoint_id(request) == 'CP2'
    
    def test_internal_chk_id(self):
        """Test internal data layer 'chk_id' format."""
        request = {'chk_id': 'CP3'}
        assert normalize_checkpoint_id(request) == 'CP3'
    
    def test_mixed_chkptId(self):
        """Test mixed case 'chkptId' format."""
        request = {'chkptId': 'CP4'}
        assert normalize_checkpoint_id(request) == 'CP4'
    
    def test_priority_canonical_first(self):
        """Test that canonical name takes priority when multiple exist."""
        request = {
            'checkpoint_id': 'canonical',
            'checkpointId': 'camelCase',
            'chk_id': 'internal'
        }
        assert normalize_checkpoint_id(request) == 'canonical'
    
    def test_not_found_returns_none(self):
        """Test that missing checkpoint_id returns None."""
        request = {'other_key': 'value'}
        assert normalize_checkpoint_id(request) is None
    
    def test_not_found_with_default(self):
        """Test that missing checkpoint_id returns provided default."""
        request = {'other_key': 'value'}
        assert normalize_checkpoint_id(request, default='DEFAULT') == 'DEFAULT'


class TestNormalizeCursorIndex:
    """Tests for normalize_cursor_index function."""
    
    def test_canonical_cursor_index(self):
        """Test canonical 'cursor_index' format."""
        request = {'cursor_index': 5}
        assert normalize_cursor_index(request) == 5
    
    def test_camelcase_cursorIndex(self):
        """Test camelCase 'cursorIndex' format."""
        request = {'cursorIndex': 10}
        assert normalize_cursor_index(request) == 10
    
    def test_legacy_event_cursor(self):
        """Test legacy 'event_cursor' format."""
        request = {'event_cursor': 15}
        assert normalize_cursor_index(request) == 15
    
    def test_legacy_cursor_pos(self):
        """Test legacy 'cursor_pos' format."""
        request = {'cursor_pos': 20}
        assert normalize_cursor_index(request) == 20
    
    def test_string_conversion(self):
        """Test that string values are converted to int."""
        request = {'cursor_index': '25'}
        assert normalize_cursor_index(request) == 25
        assert isinstance(normalize_cursor_index(request), int)
    
    def test_priority_canonical_first(self):
        """Test that canonical name takes priority when multiple exist."""
        request = {
            'cursor_index': 1,
            'cursorIndex': 2,
            'event_cursor': 3
        }
        assert normalize_cursor_index(request) == 1
    
    def test_not_found_returns_none(self):
        """Test that missing cursor_index returns None."""
        request = {'other_key': 'value'}
        assert normalize_cursor_index(request) is None
    
    def test_not_found_with_default(self):
        """Test that missing cursor_index returns provided default."""
        request = {'other_key': 'value'}
        assert normalize_cursor_index(request, default=99) == 99
    
    def test_none_value(self):
        """Test that None value returns default."""
        request = {'cursor_index': None}
        assert normalize_cursor_index(request) is None
        assert normalize_cursor_index(request, default=0) == 0


class TestNormalizeIntegration:
    """Integration tests combining multiple normalization functions."""
    
    def test_mixed_request_normalization(self):
        """Test normalizing multiple fields from same request."""
        request = {
            'segmentId': 'A1',
            'chk_id': 'CP1',
            'cursor_pos': '5'
        }
        
        segment = normalize_segment_id(request)
        checkpoint = normalize_checkpoint_id(request)
        cursor = normalize_cursor_index(request)
        
        assert segment == 'A1'
        assert checkpoint == 'CP1'
        assert cursor == 5
    
    def test_all_canonical_names(self):
        """Test all canonical names together."""
        request = {
            'segment_id': 'S1',
            'checkpoint_id': 'C1',
            'cursor_index': 10
        }
        
        assert normalize_segment_id(request) == 'S1'
        assert normalize_checkpoint_id(request) == 'C1'
        assert normalize_cursor_index(request) == 10
    
    def test_missing_fields_return_defaults(self):
        """Test that missing fields use provided defaults."""
        request = {}
        
        segment = normalize_segment_id(request, default='UNKNOWN')
        checkpoint = normalize_checkpoint_id(request, default='NONE')
        cursor = normalize_cursor_index(request, default=-1)
        
        assert segment == 'UNKNOWN'
        assert checkpoint == 'NONE'
        assert cursor == -1














