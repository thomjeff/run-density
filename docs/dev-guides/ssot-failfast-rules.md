# SSOT & Fail‑Fast Enforcement Rules (Non‑Negotiable)

**Version:** v2.0.4+  
**Last Updated:** 2025-01-10
**Audience:** AI Assistants (Cursor, ChatGPT, Codex, GitHub Copilot)  
**Purpose:** Complete onboarding and critical rules for AI pair programming

## Canonical Rule (Short Form)
**If a value is required, it must exist in configuration. If it does not exist, the run must fail. There are no fallbacks.**

## Pipeline / Order of Events

+-------------------+
|  User Inputs      | <---- CSVs, GPX, analysis.json
+-------------------+
           |
           v
+-------------------+
|  Validate Inputs  | ---> Fail-fast if incomplete or invalid
+-------------------+
           |
           v
+-----------------------------+
|  Persisted Config + Inputs | ---> Cache as DataFrames / parquet / etc.
+-----------------------------+
           |
           v
+------------------------+
|   Analysis Pipeline    | ---> Uses only persisted inputs; generates bins, etc..
+------------------------+
           |
           v
+------------------------+
|  UI Output Artifacts   | ---> JSONs, summaries, visual state
+------------------------+
           |
           v
+------------------------+
|   API/UI Presentation  | ---> Reads *only* the output artifacts
+------------------------+


---

1. Configuration Is the Single Source of Truth (SSOT)
All runtime configuration must originate from analysis.json and be loaded once into a centralized context object (e.g. AnalysisContext, ConfigLoader). The following are end-user provided sources of inputs when calling for a new analysis:
- GPX files for event course(s) that provide geographic information for the analysis. 
- CSV files that provide configuration information on:
	- Segments that break-down an event course into chunks for analysis, where a Segment can be used by more than one event with event-specific metadata (lengths, from_km/to_km, flow_type, direction)
	- Flow that builds on Segments that define event pairings where two or more events shared a segment and the analysis will calculate overtaking by, and copresence of runners
	- Locations that define traffic control, water station and first aid points along a course, or where a location is near the course, define via nearest course location using a proxy
	- Runners that contains a list of runners, their pace and start-offset for an event
- Rulebooks that define LOS thresholds and schema definitions for the reporting and analysis functions.

✅ Required
- Load once → cache → pass references (DataFrames or typed objects)
- Downstream code must consume the already‑loaded data, never re‑load

❌ Prohibited
 - Loading configuration directly from disk (pd.read_csv(...)) outside the config loader
- Re‑reading CSVs in downstream modules
- Constructing derived config implicitly or “on the fly”

⸻

2. Fail Fast, Fail Early, Fail Loud
If required configuration is missing, invalid, or incomplete, the system must raise an explicit error immediately.
- Missing required column → ERROR
- Missing event‑specific metadata (e.g. segment length) → ERROR
- Missing schema / flow_type / width → ERROR
- Missing data_dir or data_files entry → ERROR

❌ Prohibited
- Silent defaults (e.g. on_course_open, width = 3.0)
- “Best guess” inference
- Logging a warning and continuing
- Returning N/A, 0.0, or placeholder values

If the configuration is wrong, the run must not proceed.

⸻

3. Zero Fallbacks Policy
There are **no** fallbacks in runtime logic. Period. If a value is required for computation, visualization, or reporting:
- It must exist in configuration
- It must be validated at load time
- It must be present before any calculation

❌ Explicitly forbidden fallback patterns
- “Try A, else B, else compute it”
- “If missing, calculate from geometry”
- “If not found, use default thresholds”
- “If empty, infer from previous event”

This includes, but not limited to:
- Segment length
- Width
- Schema
- LOS thresholds
- Flow type
- Direction
- Event applicability

⸻

4. Fix Root Causes, Not Symptoms
When QA reveals a defect:
- Do not patch downstream logic
- Do not add conditionals or fallbacks
- Do not infer missing data

Instead:
- Identify where the configuration is incomplete or invalid
- Enforce validation at load time
- Fail the run with a clear, actionable error message

A fix that “makes the UI look right” while hiding config errors is considered incorrect. We are not building a pretty-UI that is powered by band-aids in the back-end. To be clear: we are building a highly configurable run analysis platform that has a UI for visualizing the results of an analysis.

⸻

5. Write Once, Read Many (WORM Rule)
Configuration data must follow a strict WORM model:
- Write: Loaded once from disk
- Read: Passed by reference everywhere
- Never modified, re‑derived, or re‑loaded

❌ Prohibited
- Re‑computing derived fields in multiple places
- Re‑reading CSVs in reports, APIs, or UI artifact generators
- Mutating config-derived DataFrames mid‑pipeline

⸻

6. UI Must Reflect Configuration, Not Repair It
The UI layer (Segments page, Density page, Maps):
- Must display what the configuration defines and persistent in the UI datafiles produced during the analysis.
- Must not compensate for missing data in the UI datafiles by reading from configuration files like segments, flow or locations.
- Must not compute values absent from config

If data is missing:
- The API should error
- The UI should surface that error
- The run should be considered invalid

⸻

7. QA Acceptance Criteria

A fix is not acceptable if:
- It introduces any fallback logic
- It computes values that were missing from configuration
- It hides config defects instead of surfacing them
- It reads CSVs outside the config loader
- It allows a run to succeed with incomplete metadata

A fix is acceptable only if:
- Missing config causes an immediate failure
- All values originate from SSOT
- The same run behaves identically across CLI, API, UI, and reports

⸻

If you want, I can also:
	•	Rewrite this as a PR checklist for Cursor/Codex
	•	Convert it into lint rules / test assertions
	•	Add a “Stop and Ask” policy block specifically for AI agents

But you are absolutely right to be frustrated — the fallback behavior you’re seeing directly violates SSOT, and your instinct is 100% correct.