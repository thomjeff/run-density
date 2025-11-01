# Variable Naming Reference

**CRITICAL**: This document contains the authoritative variable names used throughout the run-density application. Always reference this document to avoid variable name mismatches that cause bugs and waste development time.

## **🚨 Why This Document Exists**

Variable name mismatches are a common source of bugs and wasted time:
- Using `segment_label` instead of `seg_label` causes data lookup failures
- Inconsistent field names between data sources and API responses
- Different naming conventions across modules
- **Result**: Silent failures, missing data, debugging time waste

---

## **📊 Data Source Variable Names**

### **Segments Data (`data/segments.csv`)**

| **Field Name** | **Type** | **Description** | **Example** |
|----------------|----------|-----------------|-------------|
| `seg_id` | string | Unique segment identifier | `A1` |
| `seg_label` | string | Human-readable segment name | `Start to Queen/Regent` |
| `event` | string | Event name (10K, Half, Full) | `10K` |
| `from_km` | float | Starting kilometer for this event | `0.0` |
| `to_km` | float | Ending kilometer for this event | `0.9` |
| `width_m` | float | Physical width in meters | `5.0` |
| `direction` | string | Traffic direction (uni, bi) | `uni` |
| `step_km` | float | Analysis step size in kilometers | `0.1` |
| `include_y` | string | Include flag for density analysis (y, n) | `y` |
| `physical_name` | string | Human-readable segment name | `Start to Queen/Regent` |
| `notes` | string | Additional segment information | `Start along St John Street` |

### **Runners Data (`data/runners.csv`)**

| **Field Name** | **Type** | **Description** | **Example** |
|----------------|----------|-----------------|-------------|
| `pace` | float | Minutes per kilometer | `4.5` |
| `start_offset` | float | Additional delay in seconds from event start | `30.0` |

### **Event-Specific Field Names (Legacy Format)**

**⚠️ DEPRECATED**: These field names are used in some legacy code and should be avoided in new development:

| **Field Name** | **Description** | **Replacement** |
|----------------|-----------------|-----------------|
| `10K_from_km` | 10K event start kilometer | `from_km` (with `event='10K'`) |
| `10K_to_km` | 10K event end kilometer | `to_km` (with `event='10K'`) |
| `half_from_km` | Half event start kilometer | `from_km` (with `event='Half'`) |
| `half_to_km` | Half event end kilometer | `to_km` (with `event='Half'`) |
| `full_from_km` | Full event start kilometer | `from_km` (with `event='Full'`) |
| `full_to_km` | Full event end kilometer | `to_km` (with `event='Full'`) |

---

## **🔧 API Response Variable Names**

### **Map API Responses**

| **API Field** | **Data Source** | **Description** | **Example** |
|---------------|-----------------|-----------------|-------------|
| `segment_id` | `seg_id` | Unique segment identifier | `A1` |
| `segment_label` | `seg_label` | Human-readable segment name | `Start to Queen/Regent` |
| `from_km` | `from_km` | Starting kilometer | `0.0` |
| `to_km` | `to_km` | Ending kilometer | `0.9` |
| `width_m` | `width_m` | Physical width in meters | `5.0` |
| `flow_type` | `direction` | Traffic direction | `uni` |
| `zone` | calculated | Density zone color | `green` |

### **Density Analysis Results**

| **Field Name** | **Type** | **Description** | **Example** |
|----------------|----------|-----------------|-------------|
| `seg_id` | string | Segment identifier | `A1` |
| `seg_label` | string | Segment name | `Start to Queen/Regent` |
| `peak_areal_density` | float | Peak areal density | `0.45` |
| `peak_crowd_density` | float | Peak crowd density | `0.32` |
| `zone` | string | Density zone | `green` |
| `flow_type` | string | Flow type | `overtake` |

### **Flow Analysis Results**

| **Field Name** | **Type** | **Description** | **Example** |
|----------------|----------|-----------------|-------------|
| `seg_id` | string | Segment identifier | `A1` |
| `seg_label` | string | Segment name | `Start to Queen/Regent` |
| `overtakes` | int | Number of overtakes | `15` |
| `co_presence` | int | Co-presence count | `8` |
| `convergence_point` | float | Normalized convergence point | `0.65` |

---

## **⚠️ Common Variable Name Mistakes**

### **❌ WRONG → ✅ CORRECT**

| **Wrong** | **Correct** | **Context** |
|-----------|-------------|-------------|
| `segment_label` | `seg_label` | Data source field |
| `segment_id` | `seg_id` | Data source field |
| `physical_name` | `seg_label` | Use seg_label for consistency |
| `10K_from_km` | `from_km` | Use event-specific query |
| `half_from_km` | `from_km` | Use event-specific query |
| `full_from_km` | `from_km` | Use event-specific query |

### **Data Lookup Patterns**

**❌ WRONG**:
```python
segment_label = segment_data.get('segment_label', segment_id)
```

**✅ CORRECT**:
```python
seg_label = segment_data.get('seg_label', segment_id)
```

**❌ WRONG**:
```python
from_km = segment.get('10K_from_km')
```

**✅ CORRECT**:
```python
# Filter by event first, then get from_km
segment_10k = segments[segments['event'] == '10K']
from_km = segment_10k['from_km'].iloc[0]
```

---

## **🔍 Module-Specific Naming Conventions**

### **Map API (`app/map_api.py`)**
- **Input**: Uses `seg_label` from data
- **Output**: Converts to `segment_label` for API responses
- **Pattern**: `segment_label = segment.get('seg_label', segment['seg_id'])`

### **Density Analysis (`app/density.py`)**
- **Uses**: `seg_id`, `seg_label` consistently
- **Avoids**: `segment_id`, `segment_label`

### **Flow Analysis (`app/flow.py`)**
- **Uses**: `seg_id`, `seg_label` consistently
- **Avoids**: `segment_id`, `segment_label`

### **Map Data Generator (`app/map_data_generator.py`)**
- **Input**: Expects `seg_label` from density results
- **Output**: Uses `segment_label` for API compatibility
- **Pattern**: `segment_label = segment_data.get('seg_label', segment_id)`

---

## **📋 Quick Reference Checklist**

Before writing code that accesses segment data:

- [ ] **Data Source**: Use `seg_id`, `seg_label`, `from_km`, `to_km`
- [ ] **API Response**: Use `segment_id`, `segment_label` for frontend compatibility
- [ ] **Event Filtering**: Use `event` column, not `10K_from_km` etc.
- [ ] **Consistency**: Check existing code in the same module
- [ ] **Validation**: Test with actual data to verify field names

---

## **🔄 Migration Guidelines**

### **When Updating Legacy Code**

1. **Identify the data source** (segments.csv vs API response)
2. **Use the correct field names** for that context
3. **Add conversion logic** if bridging between contexts
4. **Test thoroughly** with real data
5. **Update this document** if new patterns emerge

### **When Adding New Features**

1. **Follow existing patterns** in the target module
2. **Be consistent** with data source field names
3. **Document any new patterns** in this reference
4. **Test with real data** to verify field names

---

## **📚 Related Documentation**

- **`docs/Application Fundamentals.md`** - Core data concepts
- **`docs/segments_combined_schema.md`** - Complete schema documentation
- **`docs/Application Architecture.md`** - System design patterns

---

**Last Updated**: September 15, 2025  
**Maintained by**: AI Assistant  
**Next Review**: When new variable naming patterns are discovered

---

*This document should be updated whenever new variable naming patterns are discovered or existing ones are changed.*
