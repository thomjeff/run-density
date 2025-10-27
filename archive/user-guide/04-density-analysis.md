# 4. Density Analysis

## 👥 **Understanding Density Analysis**

Density analysis calculates crowd density at different course locations over time, identifying peak periods, sustained congestion, and event distribution patterns. This analysis is essential for crowd management, safety planning, and course optimization.

### **Key Concepts**

- **Crowd Density**: Number of runners per unit area at specific locations
- **Peak Density**: Maximum density values during analysis period
- **Sustained Periods**: Extended periods of high density
- **Event Distribution**: How different events contribute to density
- **Density Levels**: Classification of density into manageable categories

## 📊 **Density Metrics Explained**

### **Core Density Metrics**

#### **Peak Density**
- **Definition**: Maximum density value observed in a segment
- **Calculation**: Highest density across all time windows
- **Units**: Runners per square meter
- **Interpretation**: Maximum crowding level experienced

#### **Average Density**
- **Definition**: Mean density value over analysis period
- **Calculation**: Sum of all density values divided by time windows
- **Units**: Runners per square meter
- **Interpretation**: Typical crowding level

#### **Sustained Density**
- **Definition**: Density maintained above threshold for extended period
- **Calculation**: Continuous periods above defined threshold
- **Units**: Minutes above threshold
- **Interpretation**: Duration of high crowding conditions

### **Density Classification**

#### **Level of Service (LOS) Categories**
- **LOS A**: Low density, comfortable movement
- **LOS B**: Moderate density, some restriction
- **LOS C**: High density, noticeable restriction
- **LOS D**: Very high density, significant restriction
- **LOS E**: Extreme density, severe restriction
- **LOS F**: Maximum density, dangerous conditions

#### **Density Thresholds**
- **Low**: 0-2 runners per square meter
- **Moderate**: 2-4 runners per square meter
- **High**: 4-6 runners per square meter
- **Very High**: 6-8 runners per square meter
- **Extreme**: 8+ runners per square meter

### **Temporal Density Patterns**

#### **Peak Periods**
- **Definition**: Time windows with highest density values
- **Calculation**: Top 10% of density values by time
- **Units**: Time windows
- **Interpretation**: Critical periods for crowd management

#### **Sustained Periods**
- **Definition**: Continuous periods above density threshold
- **Calculation**: Consecutive time windows above threshold
- **Units**: Minutes
- **Interpretation**: Extended crowding conditions

#### **Event Contribution**
- **Definition**: How each event contributes to total density
- **Calculation**: Density contribution by event type
- **Units**: Percentage of total density
- **Interpretation**: Event-specific crowding patterns

## 📈 **Reading Density Reports**

### **Report Structure**

#### **Summary Section**
- **Total Segments**: Number of segments analyzed
- **Events Analyzed**: Which events were included
- **Analysis Duration**: Time taken for analysis
- **Peak Density**: Highest density observed
- **Critical Segments**: Segments requiring attention

#### **Segment Analysis**
- **Segment ID**: Unique identifier
- **Peak Density**: Maximum density in segment
- **Average Density**: Mean density over time
- **Sustained Periods**: High density durations
- **Event Distribution**: Contribution by event type

### **Key Tables**

#### **Density Summary Table**
```
Segment | Peak Density | Avg Density | Sustained Periods | LOS Level
--------|--------------|-------------|-------------------|----------
A1      | 3.2          | 1.8         | 15 min           | B
F1      | 6.8          | 4.2         | 45 min           | D
F2      | 8.1          | 5.6         | 60 min           | E
```

#### **Event Contribution Table**
```
Segment | Full % | Half % | 10K % | Total Density
--------|--------|--------|-------|--------------
A1      | 45     | 35     | 20    | 1.8
F1      | 60     | 30     | 10    | 4.2
F2      | 70     | 25     | 5     | 5.6
```

#### **Sustained Periods Table**
```
Segment | Start Time | End Time | Duration | Peak Density | LOS Level
--------|------------|----------|----------|--------------|----------
F1      | 08:15      | 09:00    | 45 min   | 6.8          | D
F2      | 08:30      | 09:30    | 60 min   | 8.1          | E
```

### **Visual Indicators**

#### **Density Level Colors**
- **Green (LOS A-B)**: Low to moderate density
- **Yellow (LOS C-D)**: High density, monitor closely
- **Red (LOS E-F)**: Very high density, requires attention

#### **Sustained Period Warnings**
- **Critical**: Extended periods above LOS E
- **Moderate**: Extended periods above LOS D
- **Low**: Normal density patterns

## 🔍 **Interpreting Density Data**

### **High Peak Density**
- **Indicates**: Maximum crowding at specific times
- **Implications**: Safety concerns, potential bottlenecks
- **Management**: Deploy additional resources, monitor closely

### **Sustained High Density**
- **Indicates**: Extended periods of crowding
- **Implications**: Chronic congestion, runner discomfort
- **Management**: Consider course modifications, flow control

### **Event Distribution Patterns**
- **Full Event Dominance**: Marathon runners creating density
- **Half Event Dominance**: Half marathon runners creating density
- **10K Event Dominance**: 10K runners creating density
- **Balanced Distribution**: Even contribution from all events

### **LOS Level Interpretation**
- **LOS A-B**: Comfortable conditions, normal operation
- **LOS C-D**: Moderate crowding, monitor closely
- **LOS E-F**: Severe crowding, immediate action required

## 🚨 **Troubleshooting Density Issues**

### **Zero Density Values**
- **Possible Causes**:
  - No runners in segment
  - Incorrect segment boundaries
  - Data filtering issues
  - Time window problems
- **Solutions**:
  - Check segment boundaries
  - Verify data filtering logic
  - Review time window settings
  - Validate runner data

### **Unrealistic Density Values**
- **Possible Causes**:
  - Incorrect area calculations
  - Data quality issues
  - Algorithm parameters
  - Unit conversion errors
- **Solutions**:
  - Verify area calculations
  - Check data quality
  - Review algorithm parameters
  - Ensure consistent units

### **Missing Sustained Periods**
- **Possible Causes**:
  - Threshold too high
  - Short analysis period
  - Data gaps
- **Solutions**:
  - Adjust threshold settings
  - Extend analysis period
  - Check for data gaps

## 📋 **Density Analysis Best Practices**

### **Data Preparation**
1. **Validate Runner Data**: Ensure complete and accurate pace data
2. **Check Segment Boundaries**: Verify segment definitions are correct
3. **Review Time Windows**: Ensure appropriate time window settings
4. **Validate Parameters**: Check analysis parameters are reasonable

### **Analysis Execution**
1. **Use Automated Scripts**: Always use `python3 -m app.end_to_end_testing`
2. **Test Locally First**: Run local tests before Cloud Run
3. **Verify Results**: Check for reasonable density values
4. **Document Findings**: Record any unusual patterns

### **Result Interpretation**
1. **Compare with Expectations**: Check results against known patterns
2. **Look for Anomalies**: Identify unexpected density values
3. **Validate LOS Levels**: Ensure density classifications make sense
4. **Consider Context**: Factor in race conditions and course design

## 🔧 **Advanced Density Analysis**

### **Custom Parameters**
- **Step Size**: Granularity of density calculations
- **Time Windows**: Custom time windows for analysis
- **Thresholds**: Custom density thresholds for sustained periods
- **Segment Filtering**: Analyze specific segments or areas

### **Detailed Analysis**
- **Single Segment Analysis**: Focus on specific segments
- **Event-Specific Analysis**: Analyze density by event type
- **Temporal Analysis**: Examine density patterns over time
- **Spatial Analysis**: Analyze density patterns across course

### **Integration with Other Analysis**
- **Flow Correlation**: Link density patterns with flow data
- **Performance Analysis**: Connect density with runner performance
- **Course Optimization**: Use density data for course design improvements

## 📚 **Density Analysis Examples**

### **Typical Density Patterns**
- **Start Area**: High initial density, rapid dispersion
- **Mid-Course**: Moderate density, stable patterns
- **Convergence Points**: High density, sustained periods
- **Finish Area**: High density, extended periods

### **Management Recommendations**
- **LOS A-B**: Normal operation, maintain current conditions
- **LOS C-D**: Monitor closely, prepare for intervention
- **LOS E-F**: Immediate action required, deploy additional resources

### **Course Design Implications**
- **Wide Segments**: Better for high density areas
- **Narrow Segments**: Avoid in high density areas
- **Convergence Points**: Design for maximum density
- **Dispersion Areas**: Provide space for density reduction

---

**Next**: [Flow Runner](05-flow-runner.md) - Understanding detailed segment analysis
