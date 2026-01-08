# Research Report: Correct Implementation for predicted_timings

1) How predicted_timings are currently derived (and why it’s wrong)

**Current implementation path**
predicted_timings are computed in app/core/v2/pipeline.py::calculate_predicted_timings, which reads {day}/bins/bins.parquet and uses t_start/t_end from bin windows to infer:
day_start = min t_start
day_first_finisher = min t_end
day_last_finisher = max t_end
and event-level values via a filter on the event column.
The event filter only matches if the event column values are a list or string; anything else is ignored and yields empty event dictionaries.
Why these are not true finish times
The bin windows themselves are synthesized for analysis: _create_time_windows_for_bins sets the earliest window to the earliest start time and the latest end to max(start_times) + 120 minutes (hard-coded 2-hour analysis duration). This makes t_start/t_end analysis window bounds, not finish-line times.
As a result, current predicted_timings values in the sample run show implausible finish times (e.g., day_first_finisher at 07:02) and empty event-level dictionaries, which reflect window boundaries rather than finishers.
Bottom line: the current implementation is using analysis window timestamps, not runner finish times, and event-level timings are often empty because the event filter only supports list/str types and may not match the stored type.

2) What artifacts can (and cannot) support accurate finish-time inference
✅ Available, reliable inputs
Runner data
The v2 runner model explicitly defines pace (minutes/km), distance (km), and start_offset (seconds). These are the fields needed to compute finish times per runner.
Simulation/analysis logic already uses this timing model
Density analysis converts pace → pace_sec_per_km and start_offset → start_offset_sec, which confirms how time is computed across the pipeline (pace is minutes/km, start_offset is seconds).
Event start times and durations
analysis.json includes each event’s start_time (minutes after midnight) and event_duration_minutes. These can serve as fallbacks if runner data is missing.
❌ Not suitable for finish times
bins.parquet only contains analysis windows derived from start times and a fixed +120-minute horizon. It does not encode finish-line completions.
fz_runners.parquet is explicitly designed to track who participated in flow zones and omits time-in-zone or audit-level timing data, so it cannot be used for finish-time inference.

3) Proposed correct, robust computation approach
Core idea
Compute finish times directly from runner data and event start times.
Event-level computation (per event)
For each runner:
runner_start_sec = event_start_min * 60 + start_offset_sec
finish_time_sec = runner_start_sec + (pace_sec_per_km * distance_km)
pace_sec_per_km = pace * 60 (as in density_report).
start_offset is in seconds, per the model.
Then aggregate:
event_first_finisher = min finish_time per event
event_last_finisher = max finish_time per event
actual_event_duration = event_last - event_first
Day-level computation
day_start = earliest event start_time in the day
day_first_finisher = min of all event finishers
day_last_finisher = max of all event finishers
day_end = day_last_finisher
day_duration = day_end - day_start
Fallback behavior (if runner data missing)
If runner data is missing for an event:
use start_time + event_duration_minutes for event_last_finisher (and day_last calculation).
set event_first_finisher to start_time or leave null/empty (depending on product expectations).
This leverages fields already validated and required in analysis.json and keeps outputs deterministic.

4) Suggested architecture / data flow
New helper (recommended)
Create a dedicated helper for predicted timings to avoid reliance on bins:
Location idea: app/core/v2/timings.py or a new helper in pipeline.py.
Inputs:
events (for start times)
analysis_config (to get start_time, event_duration_minutes)
runners_df (combined runner data per day)
Outputs: predicted_timings dict (same schema as current metadata).
Where to call it
Right where predicted timings are currently added to metadata:
pipeline.py → create_metadata_json (or just before writing {day}/metadata.json).

5) Handoff guidance for Cursor (AI-Developer)
Implementation Notes
Use the same time model already used in density calculations: pace in minutes/km, start_offset in seconds, and pace_sec_per_km = pace * 60.
Avoid using bins.parquet or any audit artifacts for predicted finish times; those are analysis windows, not finish-line timing data.
Suggested high-level steps
Load/construct runners_df for the day (similar to existing participants calculation).
For each event:
compute per-runner finish times (using start_time from analysis.json)
aggregate min/max to produce event-level timing fields.
Compute day-level metrics from event-level results.
Use event_duration_minutes fallback if runner data is missing.


## Commands executed (for traceability)
rg -n "predicted_timings" /workspace/run-density
sed -n '330,520p' /workspace/run-density/app/core/v2/pipeline.py
sed -n '1960,2065p' /workspace/run-density/app/density_report.py
cat /workspace/run-density/codex/predicted_timings/QAB5oFK7xx7EoknWgbZ8We/analysis.json
sed -n '240,320p' /workspace/run-density/codex/predicted_timings/QAB5oFK7xx7EoknWgbZ8We/sun/metadata.json
sed -n '1,80p' /workspace/run-density/docs/user-guide/fz_runners.md


--

Three follow-ups before shifting to implementation focused discussion.

## 🔄 Follow-Up Questions: `predicted_timings` Implementation

Thanks for the research report. Before Cursor moves into implementation, we’d appreciate your opinion on a few architectural decisions to ensure consistency with the rest of the system.

### 1️⃣ Should a new helper live in `app/core/v2/timings.py`?

This aligns with our modular convention (e.g., density, flow, segments), and would keep time-domain logic isolated from `pipeline.py`.

> Do you agree this is the appropriate location? If not, where would you place it?

---

### 2️⃣ Should the helper persist timing data to a `.parquet`?

We're considering having the helper optionally write a new artifact, e.g., `timing.parquet`, with the following schema:

| runner_id | event | start_time | finish_time | duration_sec |
|-----------|--------|-------------|--------------|---------------|

This mirrors how we persist flow (`fz.parquet`) and runner flow (`fz_runners.parquet`).

Pros:
- Improves auditability and reusability
- Allows visualization or debugging without recomputation
- Simplifies future dev/analysis needing finish times

Concerns:
- Adds write I/O and memory cost
- May be redundant for one-time metadata.json usage

> Does this add significant runtime cost based on the current pipeline structure?
> Would you recommend this persistent output as part of the helper’s default behavior?

---

Below is my evaluation of the three architectural choices, aligned to your goals (consistency, minimal overhead, clean responsibilities). I’m only referencing the current repo structure and artifacts, and not proposing any code changes.
✅ Recommendation Summary (TL;DR)
Helper location: ✅ Yes, app/core/v2/timings.py is appropriate for time-domain logic (parallel to other domain modules) and keeps pipeline.py lighter.
Parquet output: ⚠️ Optional, not default. I’d gate it behind a flag because the pipeline already writes many artifacts, and timing outputs are derived from already-loaded runner data (so reuse is easy without disk I/O).
Metadata writing: ✅ Return dict; let pipeline.py write metadata. This matches existing separation where helpers compute and pipeline persists.
1️⃣ Should a new helper live in app/core/v2/timings.py?
✅ Yes — this is consistent with the v2 module layout
The v2 architecture already uses domain-focused modules for computation, while pipeline.py orchestrates execution and file output. For example, bin generation and analysis logic live in their own files, while the pipeline coordinates when they run and where outputs are written.
Why timings.py fits well:

The timing logic is domain-specific (runner pacing and finish inference), not orchestration.
It naturally mirrors modules like density, flow, and bins.
It keeps pipeline.py focused on orchestration (and metadata assembly), which is already its role.
Alternative placement (less ideal):
Putting it directly in pipeline.py would continue the existing pattern (as with calculate_predicted_timings), but that’s already part of the problem: the pipeline function is doing domain logic today.
Conclusion:
app/core/v2/timings.py is the cleanest and most consistent location.
2️⃣ Should the helper persist a timing.parquet artifact?
Recommendation: Make it optional, not default
✅ Pros (strong):
Auditability: A persisted runner-level table is valuable for debugging or exploratory analysis without rerunning calculations.
Future re-use: Other analyses could read it directly, like flow does with fz.parquet and fz_runners.parquet.
⚠️ Concerns (why not default):
Compute path already has runner data: You will already load runners to compute timings, so persistence adds extra I/O on the critical path.
Potential output bloat: It creates a new artifact per day (and per run), which may be unnecessary unless the consumer actually needs it.
Pipeline already writes multiple artifacts: It’s important to keep additional file writes deliberate (e.g., toggled by config).
Is the runtime cost significant?
The computation itself is cheap (vectorized math on runner rows). The main added cost is I/O (serializing a new Parquet file and storing it). This isn’t massive, but it adds persistent storage and write time each run.
Suggested compromise
Add a flag in analysis.json or env (e.g., ENABLE_TIMING_ARTIFACTS=true) that governs whether this parquet is written.
Default off, but trivially enabled when needed.
Conclusion:
Persisting timing.parquet is valuable but should be optional to keep the default pipeline light.
3️⃣ Should the helper generate metadata.json or just return a dict?
Recommendation: Return a dict (Option A)
✅ Why Option A aligns with architecture
create_metadata_json already owns metadata structure and file writing responsibilities; it is used in the pipeline just before persistence to {day}/metadata.json.
Helpers in other v2 modules compute values but do not write metadata directly (e.g., bins or density helpers).
⚠️ Risk of Option B (helper writes metadata)
It blurs responsibilities and could lead to inconsistent metadata updates (multiple writers).
It complicates the ordering of metadata enrichment, which currently happens in a single place in the pipeline (e.g., derived metrics, flow summaries, and predicted timings).
Conclusion:
Stick to the existing pattern: helper returns a dict, pipeline inserts it into metadata.
Final Architectural Recommendation (Condensed)
Question	Recommended Answer	Rationale
Helper location	app/core/v2/timings.py	Keeps time-domain logic modular and consistent with v2 structure.
Persist timing.parquet	Optional (flagged)	Useful for audit/debug, but avoid default I/O cost.
Metadata writing	Return dict (pipeline writes)	Preserves orchestration responsibilities in pipeline.py.
Commands used (for traceability)
sed -n '1360,1465p' /workspace/run-density/app/core/v2/pipeline.py
sed -n '1,120p' /workspace/run-density/app/core/v2/bins.py
These were used to confirm how metadata writing and module responsibilities are currently structured.
If you want, I can provide a concrete outline of helper signatures and data flow (no code changes) to make the implementation path smoother for Cursor.
---

Agreed on your recommended answers for 1 and 3. On 2 - no need to persist a parquet at this time and no need for an optional flag. With this, please update your research report and implementation.

---
Below is the updated research report and implementation guidance reflecting your decision not to persist a timing parquet (and no optional flag). I did not modify any repository files.
✅ Updated Research Report: predicted_timings
1) Current derivation (and why it’s wrong)
Current logic in app/core/v2/pipeline.py::calculate_predicted_timings computes predicted_timings from bins.parquet time windows (t_start/t_end). This derives:
day_start from min t_start
day_first_finisher from min t_end
day_last_finisher from max t_end
event-level first/last times by filtering on the event column
Why this is incorrect
Those window times are analysis windows, not finish-line times. The windowing logic is built from event start times and a fixed +120 minute horizon, unrelated to runner finish times.
As a result, predicted_timings reflect window boundaries (e.g., 07:02) rather than actual finishers, and event-level timings often remain empty due to type mismatches in the event column (e.g., list/array types).
2) Correct data inputs for finish times
✅ Use runner-level fields
The runner model includes:
pace (minutes/km)
distance (km)
start_offset (seconds from event start)
The density pipeline already uses pace * 60 as pace_sec_per_km, confirming the intended timing model.
✅ Use event start times
Each event’s start_time (minutes after midnight) is available in analysis.json. This provides the base for runner start time computation.
❌ Do not use bins.parquet or audit
bins.parquet timestamps are analysis windows (not finish times), and audit artifacts are out of scope. The logic must be derived from runner + event data only.
3) Updated recommended architecture
✅ Helper location
Create a dedicated helper in app/core/v2/timings.py to compute predicted timings and return a dict. This matches the modular v2 structure (time-domain logic separated from orchestration).
✅ No parquet persistence
Per your decision, do not write a timing.parquet artifact—no optional flag. The helper should only compute and return timing values.
✅ Metadata writing stays in pipeline.py
Keep create_metadata_json and file persistence in the pipeline. The helper should return a dict, and pipeline.py should insert that dict into metadata (mirroring existing orchestration patterns).
✅ Updated Implementation Guidance (No Parquet Output)
Proposed helper responsibility
Add a helper (e.g., compute_predicted_timings) that:
Receives events, analysis_config, and a day-filtered runners_df
Computes runner finish times per event using:
runner_start_sec = event_start_min * 60 + start_offset_sec
finish_time_sec = runner_start_sec + pace_sec_per_km * distance_km
pace_sec_per_km = pace * 60 as per existing density logic
Aggregates:
event_first_finisher = min finish time per event
event_last_finisher = max finish time per event
actual_event_duration = event_last - event_first
Derives day-level:
day_start = earliest event start time
day_first_finisher / day_last_finisher from event finishers
day_end = day_last_finisher
day_duration = day_end - day_start
Fallbacks if runner data is missing
If no runners are available for an event, use:
event_last_finisher = start_time + event_duration_minutes
leave event_first_finisher empty or set to start_time (depending on product expectations)
still compute day_start from event start times
The fallback values are already present in analysis.json and validated by the system.
✅ Updated Recommendation (Condensed)
Decision	Final Answer
Helper location	app/core/v2/timings.py
Parquet persistence	No (do not write)
Metadata writing	Helper returns dict, pipeline writes
Commands used (for traceability)
sed -n '374,493p' /workspace/run-density/app/core/v2/pipeline.py
sed -n '1997,2014p' /workspace/run-density/app/density_report.py
sed -n '2540,2549p' /workspace/run-density/app/density_report.py
sed -n '36,53p' /workspace/run-density/app/core/v2/models.py
sed -n '29,93p' /workspace/run-density/codex/predicted_timings/QAB5oFK7xx7EoknWgbZ8We/analysis.json
sed -n '1,120p' /workspace/run-density/app/core/v2/bins.py
If you want, I can translate this into a concrete implementation checklist for Cursor (with exact function names and file locations) while keeping it code-free.

---
