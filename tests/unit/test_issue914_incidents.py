"""Issue #914: reported problems, lifecycle badges, 911, closure care."""

from __future__ import annotations

from app.core.execute.incidents import (
    NOT_YET_KNOWN,
    apply_fields,
    assign_care,
    catalog,
    clean_care_types,
    clean_incident_types,
    close_incident,
    empty_incident,
    lifecycle,
    suggested_care_ids,
    transfer_care,
)


def test_reported_problem_catalog_includes_not_yet_known():
    types = {item["id"]: item["label"] for item in catalog()["incident_types"]}
    assert types[NOT_YET_KNOWN] == "Not yet known"
    assert types["fall_collision_injury"] == "Fall / collision / injury"
    assert types["blister_chafing_skin"] == "Blister / chafing / skin problem"
    assert "blister_skin" not in types
    assert "heat_dehydration" not in types
    assert catalog()["catalog_review"].startswith(
        "Reported-problem and care catalogs have not been reviewed"
    )


def test_care_catalog_has_no_agency_actions():
    care = {item["id"]: item["label"] for item in catalog()["care_types"]}
    assert "sja" not in care
    assert "first_aid" not in care
    assert care["no_care_as_reported"] == "No care provided — as reported"
    assert care["care_details_not_known"] == "Care details not known"
    assert care["other_care"] == "Other care reported"
    assert "immobilisation" not in " ".join(care.values())


def test_empty_problems_are_not_converted_to_not_yet_known():
    incident = empty_incident(reg_id="1")
    apply_fields(
        incident,
        {
            "reported_by_name": "Jeff",
            "reported_by_agency": "race_crew",
            "location_text": "Water Stop",
            "description": "Radio report, details pending.",
            "incident_types": [],
        },
    )
    assert incident["incident_types"] == []
    assert NOT_YET_KNOWN not in incident["incident_types"]


def test_not_yet_known_is_mutually_exclusive_with_specific_problems():
    assert clean_incident_types([NOT_YET_KNOWN]) == [NOT_YET_KNOWN]
    assert clean_incident_types(
        [NOT_YET_KNOWN, "heat_concern"]
    ) == ["heat_concern"]
    incident = empty_incident(reg_id="1")
    apply_fields(incident, {"incident_types": [NOT_YET_KNOWN]})
    assert incident["incident_types"] == [NOT_YET_KNOWN]
    apply_fields(
        incident,
        {"incident_types": [NOT_YET_KNOWN, "exhaustion", "heat_concern"]},
    )
    assert incident["incident_types"] == ["exhaustion", "heat_concern"]


def test_exclusive_care_cannot_mix_with_actual_care():
    assert clean_care_types(["fluids_provided", "no_care_as_reported"]) == [
        "fluids_provided"
    ]
    assert clean_care_types(
        ["no_care_as_reported", "care_details_not_known"]
    ) == ["care_details_not_known"]
    assert clean_care_types(["care_details_not_known"]) == [
        "care_details_not_known"
    ]


def test_suggested_care_combines_problems_without_duplicates():
    ids = suggested_care_ids(["exhaustion", "heat_concern"])
    assert ids == [
        "rest_recovery",
        "fluids_provided",
        "observation",
        "moved_shade",
        "cooling_measures",
    ]
    assert len(ids) == len(set(ids))
    assert suggested_care_ids([NOT_YET_KNOWN]) == []
    assert suggested_care_ids([]) == []


def test_changing_problem_does_not_clear_recorded_care():
    incident = empty_incident(reg_id="1")
    apply_fields(
        incident,
        {
            "incident_types": ["heat_concern"],
            "care_types": ["fluids_provided", "cooling_measures"],
        },
    )
    apply_fields(incident, {"incident_types": ["exhaustion"]})
    assert incident["care_types"] == ["fluids_provided", "cooling_measures"]


def test_lifecycle_open_assigned_closed_and_911_independent():
    incident = empty_incident(reg_id="1")
    assert lifecycle(incident)["id"] == "open"
    apply_fields(incident, {"assigned_to": "sja", "called_911": "yes"})
    life = lifecycle(incident)
    assert life["id"] == "assigned"
    assert life["display"] == "Assigned · SJA"
    assert incident["called_911"] == "yes"
    assigned_notes = [
        note for note in incident["notes"] if note.get("kind") == "transfer"
    ]
    assert assigned_notes[-1]["text"] == "Assigned SJA."
    apply_fields(incident, {"assigned_to": "anb"})
    assert lifecycle(incident)["id"] == "assigned"
    assert incident["called_911"] == "yes"
    apply_fields(incident, {"called_911": "yes"})
    assert [note["text"] for note in incident["notes"]].count("911 called.") == 1
    close_incident(incident)
    assert lifecycle(incident)["id"] == "closed"
    assert incident["called_911"] == "yes"
    assert [note["text"] for note in incident["notes"]].count("911 called.") == 1


def test_assign_care_logs_like_handoff_with_separate_detail():
    incident = empty_incident(reg_id="1")
    assign_care(incident, "ski", "at 10K water")
    note = incident["notes"][-1]
    assert incident["assigned_to"] == "ski"
    assert note["kind"] == "transfer"
    assert note["text"] == "Assigned SKI."
    assert note["detail"] == "at 10K water"
    transfer_care(incident, "sja", "walking, alert")
    handoff = incident["notes"][-1]
    assert handoff["text"] == "Transferred SKI → SJA."
    assert handoff["detail"] == "walking, alert"
    apply_fields(incident, {"assigned_to": "anb", "assigned_note": "left in ANB care"})
    moved = incident["notes"][-1]
    assert moved["text"] == "Transferred SJA → ANB."
    assert moved["detail"] == "left in ANB care"
