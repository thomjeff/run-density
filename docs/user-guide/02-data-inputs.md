# 2. Data Inputs

## 📊 **Required Data Files**

The run-density application requires two primary CSV files to perform analysis:

### **1. Runners Data (`data/runners.csv`)**

Contains individual runner pace information and event assignments.

#### **Required Columns**
- **`runner_id`**: Unique identifier for each runner (integer)
- **`event`**: Event type - must match start times configuration (string)
- **`pace_min_per_km`**: Runner's pace in minutes per kilometer (float)

#### **Sample Data**
```csv
runner_id,event,pace_min_per_km
1,Full,5.5
2,Full,6.2
3,Half,4.8
4,Half,5.1
5,10K,4.2
6,10K,4.7
```

#### **Data Validation Rules**
- **Runner ID**: Must be unique integers
- **Event**: Must be one of: `Full`, `Half`, `10K` (case-sensitive)
- **Pace**: Must be positive numbers (typically 3.0-8.0 minutes/km)
- **No Missing Values**: All fields must be populated

### **2. Segments Data (`data/segments.csv`)**

Contains course segment definitions with flow analysis parameters.

#### **Required Columns**
- **`seg_id`**: Unique segment identifier (string)
- **`from_km`**: Starting kilometer of segment (float)
- **`to_km`**: Ending kilometer of segment (float)
- **`flow_type`**: Type of flow analysis for segment (string)
- **`description`**: Human-readable segment description (string)

#### **Sample Data**
```csv
seg_id,from_km,to_km,flow_type,description
A1,0.0,1.0,overtake,Start to Queen/Regent
A2,1.0,2.0,overtake,Queen/Regent to First Bridge
F1,5.0,8.0,parallel,Friel to Station Rd
F2,8.0,10.0,convergence,Station Rd to Finish
```

#### **Flow Types**
- **`overtake`**: Segments where faster runners overtake slower ones
- **`parallel`**: Segments where events run side-by-side
- **`convergence`**: Segments where events merge or converge
- **`divergence`**: Segments where events split apart

#### **Data Validation Rules**
- **Segment ID**: Must be unique strings
- **Kilometer Range**: `from_km` < `to_km`, no negative values
- **Flow Type**: Must be one of the valid flow types
- **No Overlaps**: Segments should not overlap (except at boundaries)
- **Complete Coverage**: Segments should cover the entire course

## ⚙️ **Configuration Files**

### **Start Times Configuration**

Event start times are configured in the API request, not in files:

```json
{
  "startTimes": {
    "Full": 420,    // 7:00 AM (420 minutes from midnight)
    "10K": 440,     // 7:20 AM (440 minutes from midnight)
    "Half": 460     // 7:40 AM (460 minutes from midnight)
  }
}
```

### **Analysis Parameters**

#### **Density Analysis Parameters**
- **`stepKm`**: Analysis step size in kilometers (default: 0.1)
- **`timeWindow`**: Time window for density calculations in seconds (default: 120)

#### **Flow Analysis Parameters**
- **`minOverlapDuration`**: Minimum overlap duration in minutes (default: 10)
- **`conflictLengthM`**: Conflict zone length in meters (default: 100)

## 🔍 **Data Quality Requirements**

### **Completeness Checks**
- All required columns present
- No missing values in any field
- All runners assigned to valid events
- All segments have valid flow types

### **Consistency Checks**
- Event names match between runners and start times
- Segment boundaries are logical (from_km < to_km)
- Pace values are realistic for running events
- Flow types are valid for analysis

### **Range Validation**
- **Pace Range**: 3.0-8.0 minutes per kilometer (typical running range)
- **Distance Range**: Segments should cover 0.0 to maximum course distance
- **Time Range**: Start times should be reasonable (early morning to late morning)

## 🛠️ **Data Preparation Tools**

### **Validation Script**
```bash
# Run data validation
python3 -m app.validation.preflight
```

### **Sample Data Generation**
```bash
# Generate sample data for testing
python3 -m app.io.loader --generate-sample
```

### **Data Format Conversion**
```bash
# Convert from other formats
python3 -m app.io.loader --convert --input old_format.csv --output runners.csv
```

## 📋 **File Format Specifications**

### **CSV Format Requirements**
- **Encoding**: UTF-8
- **Delimiter**: Comma (`,`)
- **Quote Character**: Double quote (`"`)
- **Line Endings**: Unix-style (`\n`)
- **Header Row**: Required with exact column names

### **Naming Conventions**
- **File Names**: Use descriptive names with underscores
- **Column Names**: Use snake_case for consistency
- **Event Names**: Use title case (Full, Half, 10K)
- **Segment IDs**: Use alphanumeric with descriptive prefixes

## ⚠️ **Common Data Issues**

### **Missing Data**
- **Symptom**: Empty cells or missing rows
- **Solution**: Fill in all required fields or remove incomplete records
- **Prevention**: Use data validation tools before analysis

### **Invalid Event Names**
- **Symptom**: `ValueError: Invalid event name`
- **Solution**: Ensure event names match exactly: `Full`, `Half`, `10K`
- **Prevention**: Use consistent naming conventions

### **Overlapping Segments**
- **Symptom**: Analysis produces unexpected results
- **Solution**: Ensure segments don't overlap (except at boundaries)
- **Prevention**: Validate segment boundaries before analysis

### **Unrealistic Pace Values**
- **Symptom**: Analysis produces extreme results
- **Solution**: Check pace values are in reasonable range (3.0-8.0 min/km)
- **Prevention**: Use data validation tools

## 🔧 **Troubleshooting Data Issues**

### **Data Loading Errors**
1. **Check file encoding**: Ensure UTF-8 encoding
2. **Verify CSV format**: Check delimiter and quote characters
3. **Validate column names**: Ensure exact match with requirements
4. **Check file permissions**: Ensure files are readable

### **Analysis Errors**
1. **Validate data completeness**: Check for missing values
2. **Verify data types**: Ensure numeric columns contain numbers
3. **Check data ranges**: Ensure values are within expected ranges
4. **Validate relationships**: Ensure runners and segments are consistent

### **Performance Issues**
1. **Check data size**: Large datasets may require more processing time
2. **Optimize segment count**: Too many segments can slow analysis
3. **Validate time windows**: Smaller time windows require more computation

## 📚 **Data Examples**

### **Complete Runners File**
```csv
runner_id,event,pace_min_per_km
1,Full,5.5
2,Full,6.2
3,Full,5.8
4,Half,4.8
5,Half,5.1
6,Half,4.9
7,10K,4.2
8,10K,4.7
9,10K,4.5
```

### **Complete Segments File**
```csv
seg_id,from_km,to_km,flow_type,description
A1,0.0,1.0,overtake,Start to Queen/Regent
A2,1.0,2.0,overtake,Queen/Regent to First Bridge
A3,2.0,3.0,overtake,First Bridge to Second Bridge
F1,5.0,8.0,parallel,Friel to Station Rd
F2,8.0,10.0,convergence,Station Rd to Finish
```

---

**Next**: [Flow Analysis](03-flow-analysis.md) - Understanding flow metrics and reports
