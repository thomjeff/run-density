"""Execute-safe display constants. Combined image keeps utils.constants."""

DISPLAY_TIMEZONE = "America/Halifax"
DISPLAY_DATETIME_FMT = "%m-%d %H:%M"
# Mirrors RACE_EVENTS in app/utils/constants.py (kept in sync by a unit test).
COURSE_EVENT_IDS = ["full", "half", "10k", "5k", "elite", "open"]
EVENT_LABELS = {
    "full": "Full",
    "half": "Half",
    "10k": "10K",
    "5k": "5K",
    "elite": "5K Elite",
    "open": "5K Open",
}
