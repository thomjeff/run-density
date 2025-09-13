# 3. Flow Analysis

## 🌊 **Understanding Flow Analysis**

Flow analysis examines how runners of different events interact over time, identifying patterns of overtaking, convergence, and conflict zones. This analysis is crucial for understanding race dynamics and optimizing course design.

### **Key Concepts**

- **Temporal Flow**: How runner interactions change over time
- **Overtaking**: When faster runners pass slower ones
- **Convergence**: Points where different events meet or merge
- **Conflict Zones**: Areas where high interaction rates occur
- **Flow Types**: Different patterns of runner movement

## 📊 **Flow Metrics Explained**

### **Overtaking Metrics**

#### **Overtaking Count**
- **Definition**: Number of times one event overtakes another in a segment
- **Calculation**: Based on temporal overlaps and pace differences
- **Units**: Count (integer)
- **Interpretation**: Higher counts indicate more passing activity

#### **Overtaking Rate**
- **Definition**: Overtaking count per unit time or distance
- **Calculation**: `overtaking_count / time_window` or `overtaking_count / segment_length`
- **Units**: Events per minute or events per kilometer
- **Interpretation**: Rate of passing activity

#### **Overtaking Load**
- **Definition**: Burden of overtaking on individual runners
- **Calculation**: Based on frequency and intensity of passing events
- **Units**: Load score (0-100)
- **Interpretation**: Higher scores indicate more challenging passing conditions

### **Convergence Metrics**

#### **Convergence Points**
- **Definition**: Specific locations where events meet or merge
- **Calculation**: Based on temporal and spatial overlap analysis
- **Units**: Kilometer markers
- **Interpretation**: Critical points for race management

#### **Convergence Duration**
- **Definition**: How long events remain in close proximity
- **Calculation**: Time difference between first and last overlap
- **Units**: Minutes
- **Interpretation**: Sustained interaction periods

#### **Convergence Intensity**
- **Definition**: Density of interactions at convergence points
- **Calculation**: Overtaking count per convergence duration
- **Units**: Events per minute
- **Interpretation**: Intensity of runner interactions

### **Flow Type Analysis**

#### **Overtake Segments**
- **Characteristics**: Clear passing lanes, minimal congestion
- **Metrics**: High overtaking rates, low conflict intensity
- **Management**: Monitor for safety, ensure adequate space

#### **Parallel Segments**
- **Characteristics**: Events run side-by-side, minimal interaction
- **Metrics**: Low overtaking rates, stable flow patterns
- **Management**: Monitor for congestion, ensure lane separation

#### **Convergence Segments**
- **Characteristics**: Events merge, high interaction potential
- **Metrics**: High convergence intensity, complex flow patterns
- **Management**: Critical for safety, requires careful planning

## 📈 **Reading Flow Reports**

### **Report Structure**

#### **Summary Section**
- **Total Segments**: Number of segments analyzed
- **Events Analyzed**: Which events were included
- **Analysis Duration**: Time taken for analysis
- **Key Findings**: High-level insights

#### **Segment Analysis**
- **Segment ID**: Unique identifier
- **Flow Type**: Type of flow analysis
- **Overtaking Summary**: Counts and rates for each event pair
- **Convergence Analysis**: Convergence points and characteristics
- **Per-Event Details**: Individual event performance

### **Key Tables**

#### **Overtaking Summary Table**
```
Event A | Event B | Overtakes A | Overtakes B | Rate A | Rate B
--------|---------|-------------|-------------|--------|--------
Half    | 10K     | 45          | 12          | 2.3    | 0.6
Full    | Half    | 23          | 8           | 1.2    | 0.4
Full    | 10K     | 67          | 15          | 3.4    | 0.8
```

#### **Convergence Points Table**
```
Segment | Event A | Event B | Convergence Point | Duration | Intensity
--------|---------|---------|-------------------|----------|----------
F1      | Half    | 10K     | 6.5 km           | 15 min   | 3.0
F2      | Full    | Half    | 8.2 km           | 8 min    | 2.9
```

### **Visual Indicators**

#### **Flow Intensity Levels**
- **High**: Red indicators, requires attention
- **Medium**: Yellow indicators, monitor closely
- **Low**: Green indicators, normal operation

#### **Convergence Warnings**
- **Critical**: Multiple events converging simultaneously
- **Moderate**: Two events converging
- **Low**: Minimal convergence activity

## 🔍 **Interpreting Flow Data**

### **High Overtaking Rates**
- **Indicates**: Fast runners catching slower ones
- **Implications**: Potential congestion, safety concerns
- **Management**: Monitor for bottlenecks, ensure adequate space

### **Low Overtaking Rates**
- **Indicates**: Stable flow patterns, good separation
- **Implications**: Efficient race management
- **Management**: Maintain current conditions

### **Convergence Points**
- **Indicates**: Critical interaction zones
- **Implications**: High management priority
- **Management**: Deploy additional resources, monitor closely

### **Flow Type Patterns**
- **Overtake Segments**: Normal passing activity
- **Parallel Segments**: Good event separation
- **Convergence Segments**: Critical management zones

## 🚨 **Troubleshooting Flow Issues**

### **Zero Overtaking Counts**
- **Possible Causes**:
  - Incorrect start times
  - Pace data errors
  - Segment boundary issues
  - Time unit mismatches
- **Solutions**:
  - Verify start times configuration
  - Check pace data accuracy
  - Validate segment boundaries
  - Ensure consistent time units

### **Unexpected Flow Patterns**
- **Possible Causes**:
  - Incorrect flow type assignments
  - Data quality issues
  - Algorithm parameters
- **Solutions**:
  - Review flow type assignments
  - Validate data quality
  - Adjust algorithm parameters

### **Missing Convergence Data**
- **Possible Causes**:
  - No temporal overlaps
  - Incorrect time calculations
  - Data filtering issues
- **Solutions**:
  - Check temporal overlap logic
  - Verify time calculations
  - Review data filtering

## 📋 **Flow Analysis Best Practices**

### **Data Preparation**
1. **Validate Input Data**: Ensure runners and segments data is complete
2. **Check Start Times**: Verify event start times are correct
3. **Review Flow Types**: Ensure segment flow types are appropriate
4. **Validate Parameters**: Check analysis parameters are reasonable

### **Analysis Execution**
1. **Use Automated Scripts**: Always use `python3 -m app.end_to_end_testing`
2. **Test Locally First**: Run local tests before Cloud Run
3. **Verify Results**: Check for reasonable values and patterns
4. **Document Findings**: Record any unusual results or patterns

### **Result Interpretation**
1. **Compare with Expectations**: Check results against known patterns
2. **Look for Anomalies**: Identify unexpected values or patterns
3. **Validate Metrics**: Ensure calculated metrics make sense
4. **Consider Context**: Factor in race conditions and course design

## 🔧 **Advanced Flow Analysis**

### **Custom Parameters**
- **Min Overlap Duration**: Minimum time for valid overlaps
- **Conflict Length**: Length of conflict zones for analysis
- **Time Windows**: Custom time windows for analysis
- **Segment Filtering**: Analyze specific segments or flow types

### **Detailed Analysis**
- **Single Segment Analysis**: Focus on specific segments
- **Event Pair Analysis**: Compare specific event combinations
- **Temporal Analysis**: Examine flow patterns over time
- **Spatial Analysis**: Analyze flow patterns across course

### **Integration with Other Analysis**
- **Density Correlation**: Link flow patterns with density data
- **Performance Analysis**: Connect flow patterns with runner performance
- **Course Optimization**: Use flow data for course design improvements

## 🔍 **F1 Segment Special Analysis**

### **F1 Segment Complexity**

The F1 segment (Friel to Station Rd., 5.0-8.0 km) is the most computationally challenging segment in the race course because:

- **Three-way merge**: All events (Full, Half, 10K) share this segment simultaneously
- **High interaction rates**: 76.1% Half overtaking, 73.0% 10K overtaking
- **Complex temporal dynamics**: Multiple overlapping time windows
- **Risk of over-counting**: Standard algorithms may inflate overtaking numbers

### **Two-Step Validation Process**

F1 uses a sophisticated two-step validation process to ensure accurate overtaking calculations:

#### **Step 1: Main Temporal Flow Calculation**
- **Method**: Standard temporal flow analysis with binning
- **Output**: Initial overtaking counts and percentages
- **Example**: F1 Half vs 10K shows 840/494 (92.1%/79.9%)

#### **Step 2: Per-Runner Validation**
- **Method**: Individual runner entry/exit time tracking
- **Purpose**: Cross-validate main calculation results
- **Output**: Validated overtaking counts
- **Example**: F1 Half vs 10K validation shows 694/451 (76.1%/73.0%)

#### **Automatic Discrepancy Detection**

When the two methods produce different results, the system automatically:

```
WARNING: F1 Half vs 10K DISCREPANCY DETECTED!
  Current calculation: 840 (92.1%), 494 (79.9%)
  Validation results:  694 (76.1%), 451 (73.0%)
  Using validation results.
```

**Why validation results are preferred:**
- More accurate per-runner tracking
- Eliminates over-counting from temporal binning
- Provides conservative, reliable estimates
- Better for race management decisions

### **Flow-Audit Detailed Analysis**

For comprehensive analysis of specific segments, use the Flow-Audit endpoint:

#### **When to Use Flow-Audit**
- **Complex segments** like F1 requiring detailed validation
- **Troubleshooting** unexpected flow patterns
- **Deep analysis** of specific event pairs
- **Validation** of standard flow calculations

#### **Flow-Audit Features**
- **Per-runner validation** for accurate counts
- **Detailed diagnostic data** (33 columns)
- **Discrepancy detection** and correction
- **Comprehensive reporting** with validation results

---

**Next**: [Density Analysis](04-density-analysis.md) - Understanding density metrics and reports
