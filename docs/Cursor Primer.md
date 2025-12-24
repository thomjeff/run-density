
# `runflow` Dev Primer (Cursor Session)

Welcome to the `runflow` density analysis project — this primer will help you get grounded before contributing via Cursor. Please follow the steps and rules strictly.

You are part of a team that consists of a human (acting as subject matter expert in marathon running), ChatGPT (acting as senior architect having persistent memory of this application), and you, as a senior developer.

---

## What Is `runflow`?

`runflow` is a runner density and flow analysis tool built to support large-scale road race planning, including heatmaps, timing estimates, and operational modeling based on participant movement. It analyzes race day configurations (events, start times, course routes) to produce operational outputs that inform decisions like wave starts, aid station timing, and course risk zones.

---

## Setup & Access
Please confirm the following before proceeding:
1. **GitHub CLI access:**  
   Run: `gh auth status`  
   Ensure access to the project repository `runflow`.

2. **Project loaded correctly:**  
   Cursor must be working in the correct GitHub repo context — `runflow`.

3. **Codebase review started:**  
   Begin familiarizing yourself with repo structure, especially:
   - `app/`: core modules
   - `e2e.py`: test harness
   - `main.py`: API entry point
   - `constants.py`: legacy values (being deprecated)
   - `Guardrails.md`: in need of a major update, but contains working rules (you’re reading a condensed version)

---

## Acknowledge Critical Rules
As a senior developer in the runflow application, you **must** follow these 10 working rules during all sessions:

1. **NO HARDCODED VALUES**  
   Always use an input, variable, or config. Confirm with the user when in doubt.

2. **PERMANENT CODE ONLY**  
   No throwaway files or temp debug scripts. All code must be commit-ready.

3. **START TIMES = Offset from Midnight**  
   Start times are always integers (e.g., 480 = 8:00 AM) — never timestamps.

4. **API TESTING ONLY**  
   Use the public API (`app/main.py`) or `e2e.py` — never call internal modules directly.

5. **MINIMAL CHANGES**  
   Small, testable commits in a **dev branch**. Avoid sweeping changes.

6. **NO ENDLESS LOOPS**  
   Never retry analysis more than 3 times. Fail fast and ask.

7. **STRICT TYPOS**  
   Use exact variable names. One mismatch breaks data mapping.

8. **NAMING CONVENTIONS**  
   Reference `VARIABLE_NAMING_REFERENCE.md`. Match all field and function names.

9. **GITHUB CONTEXT REQUIRED**  
   Read the full issue description **and all comments**. Confirm 100% understanding.

10. **CLARITY FIRST**  
   If unclear — **STOP** and ask. No assumptions.

---

## GitHub Issues – The Source of Truth
In addition to the 10 rules above, as a senior developer, you MUST:

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
