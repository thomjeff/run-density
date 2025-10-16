# GitHub Issues: Flow Module Systematic Debugging

## Main Issue: Flow Module Critical Debugging and Validation

### Issue Title
**CRITICAL: Flow Module Systematic Debugging - Remove Hardcoded Values, Fix Temporal Analysis**

### Issue Body
```markdown
## 🚨 CRITICAL ISSUE: Flow Module Analysis Failures

### Problem Summary
The flow module has **CRITICAL ISSUES** identified through comprehensive analysis:

1. **HARDCODED VALUES** in `app/overlap.py` (violates core principles)
2. **Unit confusion** - fractions displayed as absolute values
3. **Missing event pairs** in schema conversion
4. **Co-presence counting** instead of true overtaking detection
5. **100m snapshot limitation** missing full segment analysis
6. **Start time inconsistencies** affecting all calculations

### Impact
- **Unrealistic overtaking percentages** (94.8% at L1)
- **Missing convergence segments** (F1 pairs, B2)
- **Validation failures** against known good data
- **Broken temporal analysis** logic

### Root Cause Analysis
- Hardcoded convergence points masking real temporal analysis failures
- Schema conversion dropping event pairs
- Co-presence counting inflating overtaking statistics
- Unit representation confusion causing arithmetic errors

### Success Criteria
- [ ] Remove ALL hardcoded values
- [ ] Achieve >90% convergence count match with old reports
- [ ] Reduce unrealistic overtaking percentages to <60%
- [ ] Restore all missing event pairs
- [ ] Implement true pass detection
- [ ] Fix unit labeling and representation

### Dependencies
- Requires systematic approach with clear commit points
- Must maintain backward compatibility with main.py and dependent modules
- Needs validation framework for each phase

### Labels
`critical`, `bug`, `flow-analysis`, `hardcoded-values`, `temporal-analysis`

### Assignee
@jthompson

### Milestone
Flow Module v1.7.0 - Critical Fixes
```

---

## Sub-Issues for Systematic Debugging

### Phase 1: Schema & Conversion Validation

#### Issue 1.1: Audit segments_new.csv Conversion Logic
```markdown
## Issue Title
**Phase 1.1: Audit segments_new.csv Conversion Logic**

### Description
Validate the `convert_segments_new_to_flow_format` function to ensure all segments and event pairs are correctly generated.

### Tasks
- [ ] Audit conversion function for missing event pairs
- [ ] Verify all `overtake_flag=y` segments are preserved
- [ ] Check `flow_type` assignments are correct
- [ ] Validate distance mappings for all events
- [ ] Add conversion audit logging

### Expected Outcomes
- All expected event pairs generated (F1 should have 3 pairs)
- No segments dropped during conversion
- Clear audit trail of conversion process

### Validation Tests
- Compare old vs new pair generation
- Verify F1 generates: 10K/Half, 10K/Full, Half/Full
- Check B2 segment is not missing

### Commit Strategy
- Commit after each validation test passes
- Tag as `v1.6.3-phase1.1-validation`
- Create rollback point before major changes

### Labels
`phase1`, `schema-validation`, `conversion-audit`
```

#### Issue 1.2: Event Pair Completeness Check
```markdown
## Issue Title
**Phase 1.2: Event Pair Completeness Check**

### Description
Ensure all expected event pairs are generated and no segments are missing from the analysis.

### Tasks
- [ ] Fix event pair generation to include both directions
- [ ] Add missing segments (B2, F1 pairs)
- [ ] Implement pair generation audit trail
- [ ] Add validation warnings for missing pairs

### Code Changes
```python
# Fix in convert_segments_new_to_flow_format:
for i, event_a in enumerate(events):
    for j, event_b in enumerate(events):
        if i != j:  # Include both directions
            # Generate pair
```

### Expected Outcomes
- F1 shows all 3 event pairs with convergence
- B2 segment appears in analysis
- Clear audit trail of generated pairs

### Commit Strategy
- Commit after each pair type is fixed
- Tag as `v1.6.3-phase1.2-pairs-complete`
- Test with known good segments

### Labels
`phase1`, `event-pairs`, `missing-segments`
```

### Phase 2: Temporal Analysis Validation

#### Issue 2.1: Remove Hardcoded Values
```markdown
## Issue Title
**Phase 2.1: Remove Hardcoded Values from Convergence Calculation**

### Description
**CRITICAL**: Remove hardcoded convergence points from `app/overlap.py` that violate core principles.

### Tasks
- [ ] Delete hardcoded convergence points in `calculate_convergence_point`
- [ ] Implement proper temporal overlap detection
- [ ] Add tolerance sensitivity testing
- [ ] Restore dynamic convergence calculation

### Code Changes
```python
# DELETE these lines from app/overlap.py:
# if from_km == 1.8 and to_km == 2.7 and eventA == "10K" and eventB == "Half":
#     return 2.36
# if from_km == 2.7 and to_km == 4.25 and eventA == "10K" and eventB == "Full":
#     return 3.48
# return None
```

### Expected Outcomes
- No hardcoded values in codebase
- Dynamic convergence point calculation
- Proper temporal overlap detection

### Validation Tests
- Test with known segments (A2, A3, F1)
- Verify convergence points are calculated dynamically
- Check tolerance sensitivity (5s, 10s, 15s)

### Commit Strategy
- **CRITICAL**: Commit before removing hardcoded values
- Tag as `v1.6.3-phase2.1-remove-hardcoded`
- Create rollback point immediately

### Labels
`phase2`, `critical`, `hardcoded-values`, `temporal-analysis`
```

#### Issue 2.2: Fix Unit Representation and Labeling
```markdown
## Issue Title
**Phase 2.2: Fix Unit Representation and Labeling**

### Description
Fix the confusion between normalized fractions and absolute values in convergence point representation.

### Tasks
- [ ] Store both absolute and normalized convergence points
- [ ] Fix unit labeling in reports (no "km" on fractions)
- [ ] Implement consistent rounding policies
- [ ] Add clear unit labels in all outputs

### Code Changes
```python
# Store both values:
convergence_point_km = cp_km  # Absolute km
convergence_point_frac = (cp_km - from_km_a) / (to_km_a - from_km_a)  # 0-1 fraction

# Display clearly:
"Convergence Point (fraction): 0.46"
"Convergence Point (km): 1.31"
```

### Expected Outcomes
- Clear separation of absolute vs normalized values
- No unit confusion in reports
- Consistent arithmetic validation

### Validation Tests
- Verify A2: 0.46 fraction + 0.9 from_km = 1.36 (matches zone_end)
- Check A3: 0.31 fraction + 1.8 from_km = 2.11 (should match zone_end)
- Test arithmetic consistency

### Commit Strategy
- Commit after unit representation is fixed
- Tag as `v1.6.3-phase2.2-units-fixed`
- Test with known good segments

### Labels
`phase2`, `units`, `labeling`, `validation`
```

#### Issue 2.3: Start Time Consistency Validation
```markdown
## Issue Title
**Phase 2.3: Start Time Consistency Validation**

### Description
Validate and fix start time inconsistencies that are affecting all downstream calculations.

### Tasks
- [ ] Verify start times match race plan
- [ ] Add validation warnings for non-standard times
- [ ] Test with known good start time sets
- [ ] Add start time audit trail

### Expected Outcomes
- Consistent start times across all analyses
- Clear warnings for non-standard times
- Validated timing calculations

### Validation Tests
- Test A3: Full at 07:00, Half at 07:40 (from analysis)
- Verify MD start times match analysis start times
- Check timing consistency across segments

### Commit Strategy
- Commit after start time validation
- Tag as `v1.6.3-phase2.3-start-times`
- Create rollback point

### Labels
`phase2`, `start-times`, `validation`, `timing`
```

### Phase 3: Overtaking Logic Overhaul

#### Issue 3.1: Implement True Pass Detection
```markdown
## Issue Title
**Phase 3.1: Implement True Pass Detection (Replace Co-presence Counting)**

### Description
Replace co-presence counting with directional pass detection to fix unrealistic overtaking percentages.

### Tasks
- [ ] Implement directional overtaking logic
- [ ] Separate "co-presence" from "overtaking" metrics
- [ ] Add boundary crossing detection
- [ ] Fix unrealistic percentages (94.8% at L1)

### Code Changes
```python
def detect_overtake(enter_a, exit_a, enter_b, exit_b):
    # A overtakes B if A enters after B but exits before B
    return (enter_a > enter_b) and (exit_a < exit_b)
```

### Expected Outcomes
- Realistic overtaking percentages (<60%)
- True directional pass detection
- Separate co-presence metrics

### Validation Tests
- L1: Should NOT show 94.8% overtaking rates
- A2: Should show 4 Half overtaking 1 10K (runner 1529)
- A3: Should show 16 Half overtaking 1 10K (continuation)

### Commit Strategy
- Commit after pass detection implementation
- Tag as `v1.6.3-phase3.1-pass-detection`
- Test with known good segments

### Labels
`phase3`, `pass-detection`, `overtaking-logic`, `critical`
```

#### Issue 3.2: Conflict Zone Analysis Enhancement
```markdown
## Issue Title
**Phase 3.2: Conflict Zone Analysis Enhancement**

### Description
Enhance conflict zone analysis with configurable lengths and analysis modes.

### Tasks
- [ ] Test different conflict lengths (100m, 200m, 400m)
- [ ] Consider "sweep mode" for full segment analysis
- [ ] Add "peak mode" for maximum overlap windows
- [ ] Make conflict_length_m configurable

### Expected Outcomes
- Configurable conflict zone lengths
- Better analysis coverage of segments
- More realistic overtaking counts

### Validation Tests
- F1: Should analyze more than 100m of 5.35km segment
- A2: Should count overtakes over full 0.44km remaining
- Test different conflict lengths

### Commit Strategy
- Commit after each conflict length test
- Tag as `v1.6.3-phase3.2-conflict-zones`
- Create rollback points

### Labels
`phase3`, `conflict-zones`, `analysis-enhancement`
```

### Phase 4: Reporting & Validation

#### Issue 4.1: Restore Missing Data and Samples
```markdown
## Issue Title
**Phase 4.1: Restore Missing Data and Samples**

### Description
Restore missing sample IDs and audit trail data for validation.

### Tasks
- [ ] Add back `sample_a` and `sample_b` columns
- [ ] Include `seg_id_old` mapping
- [ ] Add event pair generation audit trail
- [ ] Restore sample ID formatting

### Expected Outcomes
- Sample IDs for validation (e.g., runner 1529)
- Clear audit trail of generated pairs
- Mapping back to original segments

### Validation Tests
- A2: `sample_a = [1618, 1619, 1620, ...]`, `sample_b = [1529]`
- Verify sample IDs match expected runners
- Check audit trail completeness

### Commit Strategy
- Commit after sample restoration
- Tag as `v1.6.3-phase4.1-samples-restored`
- Test with known good data

### Labels
`phase4`, `samples`, `audit-trail`, `validation`
```

#### Issue 4.2: Comprehensive Validation Framework
```markdown
## Issue Title
**Phase 4.2: Comprehensive Validation Framework**

### Description
Create comprehensive validation framework for testing each phase and ensuring quality.

### Tasks
- [ ] Create validation test suite
- [ ] Add regression testing
- [ ] Implement quality gates
- [ ] Add performance benchmarks

### Expected Outcomes
- Automated validation testing
- Regression test coverage
- Quality gates for each phase
- Performance benchmarks

### Validation Tests
- Test all known good segments
- Verify convergence count matches (>90%)
- Check overtaking percentage realism (<60%)
- Validate sample ID accuracy

### Commit Strategy
- Commit after validation framework
- Tag as `v1.6.3-phase4.2-validation-framework`
- Create final rollback point

### Labels
`phase4`, `validation`, `testing`, `quality-gates`
```

---

## Git Workflow Strategy

### Branch Strategy
- **Main Branch**: `main` (stable, production-ready)
- **Development Branch**: `v1.6.3-flow-debug` (current work)
- **Phase Branches**: `v1.6.3-phase1.1`, `v1.6.3-phase1.2`, etc.

### Commit Strategy
- **Before Each Phase**: Create rollback point
- **After Each Sub-issue**: Commit with clear message
- **Tag Strategy**: `v1.6.3-phaseX.Y-description`
- **Rollback Points**: Tagged as `v1.6.3-rollback-phaseX`

### Quality Gates
- [ ] All tests pass
- [ ] No hardcoded values
- [ ] Validation tests pass
- [ ] Performance benchmarks met
- [ ] Documentation updated

### Rollback Strategy
- Each phase has tagged rollback point
- Clear commit messages for easy identification
- Automated testing before each commit
- Manual validation for critical changes

---

## Success Metrics

### Quantitative Targets
- [ ] Remove ALL hardcoded values from codebase
- [ ] Achieve >90% convergence count match with old reports
- [ ] Reduce unrealistic overtaking percentages to <60%
- [ ] Restore all missing event pairs (F1, B2, etc.)

### Qualitative Targets
- [ ] Clear unit labeling (no "km" on fractions)
- [ ] Sample IDs for validation
- [ ] Audit trail for event pair generation
- [ ] Realistic overtaking scenarios

### Timeline
- **Week 1**: Phase 1 (Schema & Conversion)
- **Week 2**: Phase 2 (Temporal Analysis)
- **Week 3**: Phase 3 (Overtaking Logic)
- **Week 4**: Phase 4 (Reporting & Validation)

---

## Notes
- **NO HARDCODED VALUES** - absolute requirement
- **Long-term maintainability** - focus on clean, readable code
- **Breaking changes** - minimize impact on dependent modules
- **Anti-looping** - clear success criteria and validation tests
- **Traceability** - every change must be traceable and rollback-able
