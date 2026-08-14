# Clearance playbook (Health & Safety)

**Audience:** Package owners and Health & Safety coordinators  
**Issue:** #832 (data model). Live race-day clock is #830 — not this page.

Race-day reopen order is **authored in the config package**, not inferred from Flow zones or Motion pin windows.

## What “clear” means

A **location** is clear when the **last runner has passed that point** (`last_runner` on Locations — the same trajectory-backed timing as Results).

That is **not**:

- Peak window
- A radius around a pin
- Stream Passage enter/exit
- A Flow zone

Off-course operational points (traffic holds, extract, proxy-timed pins) are still **locations** if they have a `loc_id`. There is no separate “asset” type.

## Rules

Every rule is:

- **Blocked** — the location that stays closed
- **Until** — one location (pair) or several (group). Groups are **AND**: every member must be clear
- **Clear when** — always last runner (v1)

Derived reopen:

```text
reopen(blocked) = max(last_runner(u) for u in until)
```

If location B waits on A, B reopens at **A’s last runner**, even if A is itself waiting on someone else.

Cycles are rejected on save.

## Where to author

Race Configuration → open the package → **Clearance** tab.

1. **Add rule** — pick the blocked location (filter by zone).
2. **Choose locations…** — search and multi-select the until-set (AND). Same-zone locations are listed first.
3. Optional H&S **note**.
4. **Save clearance** (writes `runflow/config/{config_id}/clearance.json`).
5. **Reopen order** — pick a prior analysis of this package from the dropdown so last-runner clocks fill in. This is the sequence the rules produce, not a unit test of one rule.

## Results

On **Locations**, a **Reopen** column appears for blocked locations: reopen clock plus the until-members. Hover the clock for the full explanation.

Race-day **Execute** (`/execute`) ticks a clock against the same playbook. See [Execute clock](execute.md).

## Out of scope here

- Live “now vs reopen” clock (#830)
- Inferring rules from Flow
- Density/Flow v3 substrate
