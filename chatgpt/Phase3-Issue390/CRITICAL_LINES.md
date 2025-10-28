# Critical Lines for Phase 3 Refactoring

## **core/flow/flow.py - Complex Conditional Chains**

### **Event Type Conditionals (Lines 1837-1841)**
```python
if 'Full' in events:
    events.append('Full')
if 'Half' in events:
    events.append('Half')
if '10K' in events:
    events.append('10K')
```

### **Flow Type Conditionals (Lines 2394-2398)**
```python
if flow_type == 'merge':
    narrative.append(f"🔄 MERGE ANALYSIS:")
    narrative.append(f"   • {segment['event_a']} runners in merge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
```

### **Convergence Detection (Lines 2240-2249)**
```python
if not has_convergence_policy:
    segment_result["convergence_point"] = None
    segment_result["convergence_point_fraction"] = None
```

### **Binning Logic (Lines 2014-2018)**
```python
if segment_length_km > 5.0:
    dynamic_conflict_length_m = CONFLICT_LENGTH_LONG_SEGMENT_M
elif segment_length_km > 2.0:
    dynamic_conflict_length_m = CONFLICT_LENGTH_MEDIUM_SEGMENT_M
else:
    dynamic_conflict_length_m = CONFLICT_LENGTH_SHORT_SEGMENT_M
```

## **app/flow_report.py - Complex Conditional Patterns**

### **Environment Detection (Lines 158-161)**
```python
if os.environ.get('TEST_CLOUD_RUN', 'false').lower() == 'true':
    content.append("**Environment:** https://run-density-ln4r3sfkha-uc.a.run.app (Cloud Run Production)")
else:
    content.append("**Environment:** http://localhost:8080 (Local Development)")
```

### **Report Section Conditionals (Lines 303-314)**
```python
if has_convergence:
    content.extend(generate_convergence_analysis(segment))
    content.append("")

if segment.get('deep_dive_analysis'):
    content.extend(generate_deep_dive_analysis(segment))
    content.append("")
```

### **Data Validation Conditionals (Lines 377-390)**
```python
if max_load_a > 10 or max_load_b > 10:
    content.append("⚠️ **High Passing Burden Detected**")
    content.append("- Consider wider trails or better event separation")
    content.append("- Monitor for safety concerns during race")
    content.append("")
elif max_load_a > 5 or max_load_b > 5:
    content.append("⚠️ **Moderate Passing Burden**")
    content.append("- Monitor runner experience and safety")
    content.append("- Consider course adjustments if complaints arise")
    content.append("")
else:
    content.append("✅ **Low Passing Burden**")
    content.append("- Good runner experience expected")
    content.append("- Current course design appears adequate")
    content.append("")
```

## **app/routes/api_e2e.py - Complex Conditional Logic**

### **Environment Detection (Lines 55-58)**
```python
is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
environment = "Cloud Run" if is_cloud else "Local"

logger.info(f"Environment: {environment}")
```

### **Error Handling Conditionals (Lines 145-152)**
```python
if is_cloud:
    response["next_steps"].append("Files generated locally in Cloud Run container (ephemeral)")
    response["next_steps"].append("Need to upload to GCS for persistence")
    response["next_steps"].append("Use /api/e2e/upload to persist to GCS")
else:
    response["next_steps"].append("Files generated locally on filesystem")
    response["next_steps"].append("Available immediately to local APIs")
```

### **File Processing Conditionals (Lines 183-187)**
```python
is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
if not is_cloud:
    return JSONResponse(content={
        "status": "skipped",
        "reason": "Not in Cloud Run environment - files already local"
    })
```

## **Shared State Mutation Points**

### **core/flow/flow.py - High Risk Areas**
- **Line 568**: `rows.append({...})` - Building result rows
- **Line 640-642**: `shard_writers[shard_key] = (path, fh, wr)` - Managing file writers
- **Line 823**: `runners_a.append({...})` - Building runner data
- **Line 936-938**: `a_entry_times.append(entry_time)` - Building time arrays
- **Line 1598-1601**: `a_bibs_overtakes.update(bin_bibs_a)` - Updating overtaking data
- **Line 1695**: `analysis.append("🔍 DEEP DIVE ANALYSIS")` - Building analysis text
- **Line 2289**: `results["segments"].append(segment_result)` - Building results

### **app/flow_report.py - Medium Risk Areas**
- **Line 112**: `results.update({...})` - Updating result dictionary
- **Line 136**: `content.append("# Temporal Flow Analysis Report")` - Building report content
- **Line 261**: `flow_types[flow_type] = flow_types.get(flow_type, 0) + 1` - Counting flow types

### **app/routes/api_e2e.py - Low Risk Areas**
- **Line 147-152**: `response["next_steps"].append(...)` - Building API response
- **Line 217**: `upload_results["errors"].append(...)` - Building error list
