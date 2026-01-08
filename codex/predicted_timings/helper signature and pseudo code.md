Below is a concrete helper signature and pseudo-code (still code-free) that align with the checklist and your architecture decisions.

**Proposed Helper Signature**
Location: app/core/v2/timings.py
Purpose: compute and return predicted_timings dict (no file writes).
Inputs: day events, analysis config, and day-filtered runners DataFrame.

```text
def compute_predicted_timings(
    *,
    events: List[Event],
    analysis_config: Dict[str, Any],
    runners_df: pd.DataFrame
) -> Dict[str, Any]:
    """Return predicted_timings dict computed from runner finish times."""
```

Rationale:
events supplies event names/days and aligns with current pipeline usage.
analysis_config supplies event start_time and event_duration_minutes.
runners_df provides pace, distance, start_offset for timing computations.

**Pseudo-code (Code-Free)**

```text
function compute_predicted_timings(events, analysis_config, runners_df):

    # Build lookup from analysis_config
    # event_start_minutes[event_name] and event_duration_minutes[event_name]
    start_times = { event.name.lower(): event.start_time }
    durations = { event.name.lower(): event.event_duration_minutes }

    # Precompute per-runner timing fields (vectorized)
    # pace_sec_per_km = pace * 60
    # start_offset_sec = start_offset (or 0 if missing)
    # runner_start_sec = event_start_min * 60 + start_offset_sec
    # finish_time_sec = runner_start_sec + pace_sec_per_km * distance_km

    init event_first_finisher = {}
    init event_last_finisher = {}
    init actual_event_duration = {}

    for each event in events:
        event_name = event.name.lower()
        event_runners = runners_df where runners_df["event"] == event_name

        if event_runners empty:
            # fallback: use analysis_config event duration
            if duration exists:
                event_last = start_times[event_name] + duration (in minutes)
                event_last_finisher[event_name] = format_hhmm(event_last)
            else:
                # if no duration, skip or leave empty
                continue

            # event_first_finisher can remain empty or be start_time
            # actual_event_duration can remain empty or computed from fallback
            continue

        compute finish_time_sec for event_runners
        event_first = min(finish_time_sec)
        event_last = max(finish_time_sec)

        event_first_finisher[event_name] = format_hhmm(event_first)
        event_last_finisher[event_name] = format_hhmm(event_last)
        actual_event_duration[event_name] = format_hhmm(event_last - event_first)

    # Day-level aggregation
    day_start = min(start_times.values())
    day_first_finisher = min(all event_first values that exist)
    day_last_finisher = max(all event_last values that exist)

    day_end = day_last_finisher
    day_duration = day_end - day_start

    return {
        "day_start": format_hhmm(day_start),
        "event_first_finisher": event_first_finisher,
        "day_first_finisher": format_hhmm(day_first_finisher),
        "event_last_finisher": event_last_finisher,
        "day_last_finisher": format_hhmm(day_last_finisher),
        "day_end": format_hhmm(day_end),
        "actual_event_duration": actual_event_duration,
        "day_duration": format_hhmm(day_duration)
    }
```

**Key Data References Used in the Pseudo-code**
- pace, distance, start_offset are runner-level fields used to compute finish times.
- pace_sec_per_km = pace * 60 is consistent with existing timing logic in density calculations.
- start_time and event_duration_minutes are available in analysis.json for fallbacks and day start calculations.


