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

---

## Build, Push, Deploy (Makefile)

### 1) Build (only step that needs run_id)
```
make cloud-build RUN_ID=<run_id>
```

### 2) Push (uses latest.json run_id)
```
make cloud-push
```

### 3) Deploy (uses latest.json run_id + cloud.env password)
```
make cloud-deploy
```

### 4) Stop and Clean
```
make cloud-stop
make cloud-clean
```

---

## Local Smoke Test

Run the cloud UI locally on port 8081:
```
make cloud-run
```

Then open:
```
http://localhost:8081/
```

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

