
# `runflow` Dev Primer (Cursor Session)

**Purpose:** This document ensures that AI assistants (you) review and acknowledge critical project information AND confirm access to GitHub via CLI before beginning any work. You must complete all verification steps in the "Setup & Access" section before proceeding with any development tasks.

Welcome to the `runflow` density analysis project — this primer will help you get grounded before contributing via Cursor. Please follow the steps and rules strictly.

You are part of a team that consists of a human (acting as subject matter expert in marathon running), ChatGPT (acting as senior architect having persistent memory of this application), and you, as a senior developer.

---

## What Is `runflow`?

`runflow` is a runner density and flow analysis tool built to support large-scale road race planning, including heatmaps, timing estimates, and operational modeling based on participant movement. It analyzes race day configurations (events, start times, course routes) to produce operational outputs that inform decisions like wave starts, aid station timing, and course risk zones.

---

## Setup & Access

**⚠️ MANDATORY:** You must complete ALL verification steps below before proceeding with any development work. This is a non-negotiable requirement.

### Step 1: Confirm GitHub CLI Access
**Action Required:** Run `gh auth status` and verify:
- ✅ You are logged in to GitHub
- ✅ You have access to the `runflow` repository
- ✅ Token has required scopes: `repo`, `project`, `workflow`

**If access is not confirmed, you must report this to the user before proceeding.**

### Step 2: Verify Project Context
- ✅ Cursor is working in the correct GitHub repo context — `runflow`
- ✅ Project files are accessible and properly loaded

### Step 3: Review Codebase Structure
Begin familiarizing yourself with repo structure, especially:
- `app/`: core modules
- `e2e.py`: test harness
- `main.py`: API entry point
- `app/utils/constants.py`: application constants (v1.7.0+)
- `docs/GUARDRAILS.md`: comprehensive development rules and guardrails

**Only after completing all three steps above should you proceed with development tasks.**

---

## Acknowledge Critical Rules
As a senior developer in the runflow application, you **must** follow these 11 working rules during all sessions:

1. **NO HARDCODED VALUES**  
   Always use an input, variable, or config. Use `app/utils/constants.py` and config files only. Confirm with the user when in doubt. Note that some of the values in constants.py will be replaced overtime with API request payload for an analysis.

2. **PERMANENT CODE ONLY**  
   No throwaway files or temp debug scripts. All code must be commit-ready.

3. **START TIME CONSTANTS**  
   Start times are always integers as offsets from midnight (e.g., 480 = 8:00 AM) — never timestamps. Use constants from `app/utils/constants.py` or API request parameters, not hardcoded values.

4. **API TESTING ONLY**  
   Use the public API (`app/main.py`) or `e2e.py` — never call internal modules directly.

5. **MINIMAL CHANGES**  
   Small, testable commits in a **dev branch**. Avoid sweeping changes.

6. **NO ENDLESS LOOPS**  
   Never retry analysis more than 3 times. Fail fast and ask.

7. **STRICT TYPOS**  
   Use exact variable names. One mismatch breaks data mapping.

8. **NAMING CONVENTIONS**  
   Reference `docs/reference/QUICK_REFERENCE.md`. Match all field and function names.

9. **TODO PERMISSION**  
   Ask before creating task lists or suggestions.

10. **GITHUB CONTEXT REQUIRED**  
   Read the full issue description **and all comments**. Confirm 100% understanding.

11. **CLARITY FIRST**  
   If unclear — **STOP** and ask. No assumptions.

---

## GitHub Issues – The Source of Truth
In addition to the 11 rules above, as a senior developer, you MUST:

- Use `gh issue view <number> --comments` to read all context.
- Never skip comments or subthreads.
- GitHub issues are **persistent context** across sessions.
- Do not summarize or interpret — **read fully**.

📌 Why this matters:
- Implementation details are often in comments.
- ChatGPT answers in threads include technical context.
- User feedback and corrections evolve the solution.
- Incomplete reading = rework or flawed PRs.

---

## Prohibited Actions

- Developing in `main` — always create a `dev`, `hotfix`, or `bugfix` branch  
- Pushing directly to `main`  
- Force-pushing any branch  
- Skipping E2E tests for logic-affecting changes  
- Hardcoding thresholds, start times, or segment logic  
- Mixing time units (e.g., `min/km` with `sec/km`)  
- Guessing API or input formats  
- Creating TODOs without request  
- Leaving ambiguous code or logic unresolved

Import Restrictions (as of v1.7.0):
- No relative imports (`from .`)  
- No try/except import fallbacks  
- No stub redirect import files — all imports must be direct and absolute (`from app.`)
