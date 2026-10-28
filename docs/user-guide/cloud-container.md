# Runflow Cloud (Skinny UI) Guide

**Version:** v2.0.2+  
**Last Updated:** 2026-01-26  
**Audience:** External viewers, race ops stakeholders  

---

## Overview

The **cloud (skinny) container** serves the **Locations UI only** (map + table) for a **single run_id**.  
It is read-only, self-contained, and does **not** run the analysis pipeline.

**Key points:**
- One run_id per image (baked into the container at build time).
- UI and data persist across restarts (baked into image).
- Password gate is required for UI and APIs.
- Intended for external sharing (FPF, AWP, YSSR).

---

## Prerequisites

1. Run a full local analysis to produce a run_id.
2. Ensure `RUNFLOW_ROOT` has `analysis/latest.json` and the run folder:
   - Example: `/Users/jthompson/Documents/runflow/analysis/<run_id>`
3. Copy `cloud.env.example` to `cloud.env` and set the password:
   ```
   cp cloud.env.example cloud.env
   # edit cloud.env
   ```

Optional public loc-sheet access (direct one-pager URLs only):
```
PUBLIC_LOCSHEETS=true
```
When enabled, direct loc-sheet HTML routes are accessible without password auth:
- `/locsheets/{day}/{loc_id}` (short weekday form)
- `/locsheets/{run_id}/{loc_id}` (day from the run)
- `/locsheets/{run_id}/{day}/{loc_id}` (legacy; redirects to the two-segment URL)

The `/locsheets` index page remains behind password auth.

---

## Build, Push, Deploy

Makefile `cloud-*` targets were removed in **#935**. `:8081` is now local Execute (`make execute`). `Dockerfile.cloud` and this image remain until volunteer location sheets in Execute (**#936**) replace this path.

To build the skinny image by hand:

```
docker build -f Dockerfile.cloud -t runflow-cloud:local .
```

Do not bind it to host port 8081 while Execute is running.

---

## Accessing the Cloud UI

After deploy, the service URL is stable for the **service name**:
```
https://runflow-cloud-623983224558.us-central1.run.app
```

Login with the password in `cloud.env`.

---

## Behavior Notes

- The cloud container is **read-only** (Locations UI only).
- All data comes from the baked `run_id` artifacts.
- The UI auto-resets to the baked run_id on refresh.

