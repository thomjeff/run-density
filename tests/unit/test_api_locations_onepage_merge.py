"""Issue #745: onepage merge from locations_results.json into /api/locations rows."""

from app.routes.api_locations import _merge_onepage_into_report_rows


def test_merge_sets_y_for_matching_day_and_loc_id():
    report = [{"loc_id": 73, "loc_label": "A"}]
    results = {
        "locations": [
            {"loc_id": 73, "day": "sun", "onepage": "y"},
            {"loc_id": 74, "day": "sun", "onepage": "y"},
        ]
    }
    _merge_onepage_into_report_rows(report, results, "sun")
    assert report[0]["onepage"] == "y"


def test_merge_skips_wrong_day():
    report = [{"loc_id": 73, "loc_label": "A"}]
    results = {"locations": [{"loc_id": 73, "day": "sat", "onepage": "y"}]}
    _merge_onepage_into_report_rows(report, results, "sun")
    assert report[0]["onepage"] == "n"


def test_merge_empty_locations_results_defaults_n():
    report = [{"loc_id": 1}]
    _merge_onepage_into_report_rows(report, None, "sun")
    assert report[0]["onepage"] == "n"


def test_merge_matches_loc_id_string_coercion():
    report = [{"loc_id": "73"}]
    results = {"locations": [{"loc_id": 73, "day": "sun", "onepage": "y"}]}
    _merge_onepage_into_report_rows(report, results, "sun")
    assert report[0]["onepage"] == "y"
