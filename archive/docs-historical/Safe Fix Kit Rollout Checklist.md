# ✅ Safe Fix Kit Rollout Checklist

The Safe Fix Kit is invaluable for development, both as a way of working and as a ready-made code solution. It gives Cursor a framework to fix the algorithm inconsistencies without breaking anything that’s already running.

Why Use It?
* Keeps Main Analysis and Flow Runner consistent (no more 0/0 vs 9/9 mismatches).
* Fixes are additive-only (no changes to existing logic).
* Every fix is wrapped in config flags so they can be turned on/off instantly.
* Provides a rollback path if anything goes wrong.

Here’s a simple adoption guide with a step-by-step rollout playbook with flags, actions, and success criteria.

---

## ⚙️ Config Flags
- `ENABLE_STRICT_FIRST` → Prevents raw fallback, uses strict passes only
- `ENABLE_BIN_SELECTOR_UNIFICATION` → Standardizes ≥100m binning rule
- `PARITY_PIN = {"M1:Half_vs_10K": "binned"}` → Forces M1 to use binned path until parity confirmed
- `EPS_CONFLICT_LEN_M` → 1e-6 (snap values at 100m)
- `EPS_OVERLAP_S` → 1e-6 (snap values at 600s, if used)

---

## 🚦 Rollout Phases

### Phase 1 – Preparation
- [ ] Merge Safe Fix Kit modules into branch
- [ ] Run **contract tests** (pytest / Vitest) → must pass
- [ ] Confirm server starts normally with all flags = False

### Phase 2 – Controlled Enablement
- [ ] Enable `ENABLE_STRICT_FIRST = true`
- [ ] Verify **F1** → Flow Runner = Main Analysis = **694/451**
- [ ] Enable `ENABLE_BIN_SELECTOR_UNIFICATION = true` + M1 parity pin
- [ ] Verify **M1** → Flow Runner = Main Analysis = **9/9**

### Phase 3 – Validation
- [ ] Run side-by-side tests on: **A2, A3, L1, M1, F1**
- [ ] Confirm telemetry (`PUB_DECISION`) matches between systems
- [ ] Verify expected results file alignment (esp. M1, F1)

### Phase 4 – Rollout
- [ ] Deploy with flags enabled to staging
- [ ] Monitor telemetry for 24–48h → no mismatches allowed
- [ ] Deploy to production
- [ ] Remove M1 parity pin once stable

### Phase 5 – Rollback (if needed)
- [ ] Toggle flags to **False**
- [ ] Restart service → full reversion, no code revert needed

---

## 🎯 Success Criteria
- M1 parity: Flow Runner = Main Analysis = **9/9**
- F1 parity: Matches validated baseline = **694/451**
- Control segments (A2, A3, L1) remain exact matches
- No raw fallback in logs
- `PUB_DECISION` telemetry is identical across systems
- Performance stable, no timeouts

---

**Definition of Done**: All target segments (M1, F1, A2, A3, L1) match exactly; telemetry confirms unified path selection; production stable with fixes enabled.
