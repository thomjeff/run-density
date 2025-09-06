# 2025-09-06 Debug Workplan

**Created:** 2025-09-06 15:51 ADT (11:51 PDT)  
**Session Type:** Remaining Flow Analysis Issues  
**Branch:** v1.6.3-flow-debug  
**Status:** Ready for targeted debugging of specific segments

---

## **🎯 OBJECTIVE**

Complete the remaining flow analysis debugging by addressing specific segment issues identified during systematic debugging approach.

## **📊 CURRENT STATUS**

### **Issues Resolved ✅**
- Hardcoded values removed
- Start times standardized  
- Unit representation fixed
- True pass detection implemented
- Repository structure cleaned
- Documentation restructured

### **Remaining Issues ❌**
- **F1 Segment**: Event A/B swap causing incorrect counts
- **L1 Segment**: Still showing inflated overtaking counts
- **M1 Segment**: Expected 1 vs 1, getting 221 vs 264
- **Some segments**: Missing expected convergence detection

## **🔍 TASK 1: F1 SEGMENT ANALYSIS**

### **Issue Description**
- **Segment**: Friel to Station Rd.
- **Problem**: Event A/B swap causing incorrect counts
- **Expected**: Specific overtaking pattern
- **Actual**: Incorrect event pair analysis

### **Investigation Approach**
1. **Verify event pair generation** in conversion logic
2. **Check flow_type assignment** for F1 segment
3. **Validate from_km/to_km ranges** for each event
4. **Compare against baseline** expectations

### **Testing Strategy**
```bash
# Run conversion audit for F1 segment
python3 -c "
from app.conversion_audit import audit_segments_overview
audit_segments_overview()
"

# Generate flow analysis and check F1 results
python3 -c "
from app.flow import analyze_temporal_flow_segments
results = analyze_temporal_flow_segments('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
# Filter for F1 segment results
f1_segments = [s for s in results['segments'] if s['seg_id'] == 'F1']
print(f'F1 segments found: {len(f1_segments)}')
for seg in f1_segments:
    print(f'Event pair: {seg[\"event_a\"]} vs {seg[\"event_b\"]}')
    print(f'Flow type: {seg.get(\"flow_type\", \"Not set\")}')
    print(f'Overtaking: {seg[\"overtaking_a\"]} vs {seg[\"overtaking_b\"]}')
"
```

### **Success Criteria**
- [ ] F1 segment shows correct event pairs
- [ ] Flow type properly assigned
- [ ] Overtaking counts match expected values
- [ ] Sample data available for verification

## **🔍 TASK 2: L1 SEGMENT ANALYSIS**

### **Issue Description**
- **Segment**: Trail/Aberdeen to/from Station Rd
- **Problem**: Still showing inflated overtaking counts
- **Expected**: Realistic overtaking percentages
- **Actual**: Unrealistic inflated counts

### **Investigation Approach**
1. **Analyze true pass detection** for L1 segment
2. **Check co-presence fallback** behavior
3. **Validate tolerance settings** for L1 conditions
4. **Compare against known-good baseline**

### **Testing Strategy**
```bash
# Run flow validation framework
python3 -c "
from app.flow_validation import FlowValidationFramework
validator = FlowValidationFramework()
results = validator.validate_flow_analysis_results('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
# Focus on L1 segment validation
l1_issues = [issue for issue in results.get('issues', []) if 'L1' in str(issue)]
print(f'L1 validation issues: {len(l1_issues)}')
for issue in l1_issues:
    print(f'Issue: {issue}')
"

# Generate detailed L1 analysis
python3 -c "
from app.flow import analyze_temporal_flow_segments
results = analyze_temporal_flow_segments('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
l1_segments = [s for s in results['segments'] if s['seg_id'] == 'L1']
for seg in l1_segments:
    print(f'L1 Event: {seg[\"event_a\"]} vs {seg[\"event_b\"]}')
    print(f'Convergence: {seg.get(\"has_convergence\", False)}')
    print(f'Overtaking: {seg[\"overtaking_a\"]} vs {seg[\"overtaking_b\"]}')
    print(f'Sample data: {len(seg.get(\"sample_a\", []))} vs {len(seg.get(\"sample_b\", []))}')
"
```

### **Success Criteria**
- [ ] L1 segment shows realistic overtaking counts
- [ ] True pass detection working correctly
- [ ] No co-presence fallback overcounting
- [ ] Sample data quality validated

## **🔍 TASK 3: M1 SEGMENT ANALYSIS**

### **Issue Description**
- **Segment**: Trail/Aberdeen to Finish (Full to Loop)
- **Problem**: Expected 1 vs 1, getting 221 vs 264
- **Expected**: Minimal overtaking (1 runner each)
- **Actual**: Massive overcounting (221 vs 264)

### **Investigation Approach**
1. **Analyze convergence point calculation** for M1
2. **Check conflict length settings** for short segments
3. **Validate tolerance parameters** for M1 conditions
4. **Compare against baseline expectations**

### **Testing Strategy**
```bash
# Test M1 segment specifically
python3 -c "
from app.flow import analyze_temporal_flow_segments
results = analyze_temporal_flow_segments('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
m1_segments = [s for s in results['segments'] if s['seg_id'] == 'M1']
for seg in m1_segments:
    print(f'M1 Event: {seg[\"event_a\"]} vs {seg[\"event_b\"]}')
    print(f'Convergence point: {seg.get(\"convergence_point\", \"None\")}')
    print(f'Conflict length: {seg.get(\"conflict_length_m\", \"Not set\")}')
    print(f'Overtaking: {seg[\"overtaking_a\"]} vs {seg[\"overtaking_b\"]}')
    print(f'Total runners: {seg[\"total_a\"]} vs {seg[\"total_b\"]}')
    print(f'Percentage: {(seg[\"overtaking_a\"]/seg[\"total_a\"]*100):.1f}% vs {(seg[\"overtaking_b\"]/seg[\"total_b\"]*100):.1f}%')
"
```

### **Success Criteria**
- [ ] M1 segment shows minimal overtaking (1 vs 1)
- [ ] Conflict length appropriate for segment size
- [ ] Tolerance parameters correctly tuned
- [ ] Convergence detection accurate

## **🔍 TASK 4: MISSING CONVERGENCE DETECTION**

### **Issue Description**
- **Problem**: Some segments missing expected convergence detection
- **Expected**: All segments with overtake_flag='y' should have convergence
- **Actual**: Only 13 out of 29 segments showing convergence

### **Investigation Approach**
1. **Identify segments** with missing convergence
2. **Check overtake_flag** assignments
3. **Validate convergence detection** algorithm
4. **Compare against baseline** expectations

### **Testing Strategy**
```bash
# Analyze all segments for convergence patterns
python3 -c "
from app.flow import analyze_temporal_flow_segments
results = analyze_temporal_flow_segments('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
segments = results['segments']

# Count convergence patterns
total_segments = len(segments)
convergent_segments = [s for s in segments if s.get('has_convergence', False)]
overtake_flag_segments = [s for s in segments if s.get('overtake_flag') == 'y']

print(f'Total segments: {total_segments}')
print(f'Convergent segments: {len(convergent_segments)}')
print(f'Overtake flag segments: {len(overtake_flag_segments)}')

# Find segments with overtake_flag but no convergence
missing_convergence = [s for s in overtake_flag_segments if not s.get('has_convergence', False)]
print(f'Missing convergence: {len(missing_convergence)}')
for seg in missing_convergence:
    print(f'  {seg[\"seg_id\"]}: {seg[\"event_a\"]} vs {seg[\"event_b\"]}')
"
```

### **Success Criteria**
- [ ] All segments with overtake_flag='y' show convergence
- [ ] Convergence detection algorithm working correctly
- [ ] No false negatives in convergence detection
- [ ] Validation framework confirms results

## **🧪 COMPREHENSIVE TESTING STRATEGY**

### **After Each Task**
1. **Run end-to-end tests**
   ```bash
   python3 -m app.end_to_end_testing
   ```

2. **Generate flow reports**
   ```bash
   python3 -c "
   from app.temporal_flow_report import generate_temporal_flow_report
   generate_temporal_flow_report('data/runners.csv', 'data/segments_new.csv', {'10K': 420, 'Half': 440, 'Full': 460})
   "
   ```

3. **Validate report quality**
   ```bash
   python3 -c "
   from app.end_to_end_testing import test_report_content_quality
   results = test_report_content_quality()
   print(f'Quality Score: {results[\"overall_quality\"]}')
   "
   ```

### **Final Validation**
- [ ] All 4 tasks completed successfully
- [ ] End-to-end tests pass
- [ ] Reports generate correctly
- [ ] No hardcoded values introduced
- [ ] Changes committed to v1.6.3-flow-debug branch

## **📋 EXECUTION ORDER**

1. **Task 1: F1 Segment** (Event A/B swap)
2. **Task 2: L1 Segment** (Inflated counts)
3. **Task 3: M1 Segment** (Expected 1 vs 1)
4. **Task 4: Missing Convergence** (Detection gaps)

## **🎯 SUCCESS METRICS**

- **F1 Segment**: Correct event pairs and overtaking counts
- **L1 Segment**: Realistic overtaking percentages
- **M1 Segment**: Minimal overtaking (1 vs 1)
- **Convergence**: All overtake_flag='y' segments show convergence
- **Overall**: Flow analysis matches baseline expectations

---

**Next Session Start Format:**
```
@Pre-task safeguards.md
@sessions/2025-09-06 Session Summary.md
@sessions/2025-09-06 Debug Workplan.md

Complete the following: Begin Task 1 - F1 Segment Analysis
```
