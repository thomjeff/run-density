"""Issue #810: paired reverse-leg location helpers."""

from app.core.locations.pairing import (
    annotate_location_passes,
    effective_location_key,
    group_rows_by_location_key,
    time_to_seconds,
)


def test_annotate_assigns_outbound_return_by_first_runner():
    rows = [
        {
            "loc_id": 129,
            "location_key": "J6NJY",
            "first_runner": "08:12:57",
            "last_runner": "09:51:00",
        },
        {
            "loc_id": 117,
            "location_key": "J6NJY",
            "first_runner": "08:02:33",
            "last_runner": "09:09:37",
        },
    ]
    annotate_location_passes(rows)
    by_id = {r["loc_id"]: r for r in rows}
    assert by_id[117]["pass"] == "outbound"
    assert by_id[117]["same_location_as"] == 129
    assert by_id[129]["pass"] == "return"
    assert by_id[129]["same_location_as"] == 117


def test_annotate_leaves_unpaired_empty():
    rows = [
        {"loc_id": 1, "location_key": "AAAAA", "first_runner": "08:00:00"},
        {"loc_id": 2, "location_key": "", "first_runner": "09:00:00"},
    ]
    annotate_location_passes(rows)
    assert rows[0]["pass"] == ""
    assert rows[0]["same_location_as"] == ""
    assert rows[1]["pass"] == ""


def test_group_rows_combines_paired_window():
    rows = [
        {
            "loc_id": 117,
            "location_key": "J6NJY",
            "loc_label": "University at George",
            "first_runner": "08:02:33",
            "last_runner": "09:09:37",
            "loc_start": "06:15:00",
            "loc_end": "09:20:00",
            "onepage": "y",
        },
        {
            "loc_id": 129,
            "location_key": "J6NJY",
            "loc_label": "University at George",
            "first_runner": "08:12:57",
            "last_runner": "09:51:00",
            "loc_start": "06:15:00",
            "loc_end": "10:05:00",
            "onepage": "n",
        },
        {
            "loc_id": 50,
            "location_key": "SOLO1",
            "loc_label": "Solo",
            "first_runner": "08:00:00",
            "last_runner": "09:00:00",
            "loc_start": "06:15:00",
            "loc_end": "09:10:00",
        },
    ]
    groups = group_rows_by_location_key(rows)
    paired = next(g for g in groups if g.get("pass_key") == "J6NJY" or g["location_key"] == "J6NJY")
    assert paired["paired"] is True
    assert paired["pass_ids"] == [117, 129]
    assert paired["loc_ids"] == [paired["loc_id"]]
    assert paired["first_runner"] == "08:02:33"
    assert paired["last_runner"] == "09:51:00"
    assert paired["loc_end"] == "10:05:00"
    assert paired["onepage"] == "y"
    assert [p["pass"] for p in paired["passes"]] == ["outbound", "return"]

    solo = next(g for g in groups if g.get("pass_key") == "SOLO1" or g["location_key"] == "SOLO1")
    assert solo["paired"] is False
    assert solo["loc_ids"] == [50]


def test_effective_location_key_leg_fallback():
    assert effective_location_key({"leg_loc_key": "ABCDE"}) == "ABCDE"
    assert time_to_seconds("08:02:33") == 8 * 3600 + 2 * 60 + 33
