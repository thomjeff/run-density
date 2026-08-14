# Execute clock (v1)

**Audience:** Race-day Health & Safety / ops  
**Issue:** #830 (v1). Clearance rules are authored in Build (#832).

This page compares the **device clock** (or a rehearsal preview time) to the analysis playbook. It is **plan vs clock**, not live GPS.

Expect this surface to move when chrome becomes **Build → Plan → Execute**.

## What you see

| Piece | Meaning |
|-------|---------|
| Clock | Wall clock, or a preview time you set |
| Guns | Event start times from `analysis.json` for this run/day |
| Playbook | Package clearance rules + last-runner times from Locations |

A location **may reopen** when the clock is at or after `max(last_runner)` of its until-locations. That is last runner **at the point**, not Stream Passage, not a pin radius.

## Rehearsal

Before race day, set **Preview time** or **First gun** to walk Closed → May reopen. **Wall clock** returns to the device clock.

## Where it lives today

Results → **Execute** (after Locations). Rules are still edited on the package **Clearance** tab.
