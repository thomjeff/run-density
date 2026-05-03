"""Issue #747: LOCATION_TYPE_CHOICES includes extraction and stays sorted."""

from app.utils.constants import LOCATION_TYPE_CHOICES


def test_extraction_in_location_type_choices():
    assert "extraction" in LOCATION_TYPE_CHOICES


def test_location_type_choices_sorted():
    assert LOCATION_TYPE_CHOICES == sorted(LOCATION_TYPE_CHOICES)
