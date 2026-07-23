# Race templates (Issue #798 Phase 8)

Race-specific UI suggestions, hotspot segment IDs, map centers, and legacy v1
event durations live under `app/core/race_templates/`.

| Env | Meaning |
|-----|---------|
| `RACE_TEMPLATE` | Template id (default: `sample_fredericton`) |

**v2 analysis** still takes start times / durations from the request / package /
`analysis.json`. Template schedules are **UI suggestions only** unless the user
applies them in the run-analysis dialog.

To add another race: create `app/core/race_templates/<id>.py` and register it in
`RACE_TEMPLATES` in `__init__.py`.
