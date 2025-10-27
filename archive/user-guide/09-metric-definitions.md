# 9. Metric Definition Appendix

## 📐 **Detailed Calculation Formulas**

This appendix provides comprehensive definitions and calculation methods for all metrics used in the run-density application.

## 🌊 **Flow Analysis Metrics**

### **Overtaking Calculations**

#### **Overtaking Count**
**Definition**: Number of times one event overtakes another in a segment

**Formula**:
```
overtaking_count = Σ(overlap_duration > minOverlapDuration)
```

**Where**:
- `overlap_duration` = time when both events are in segment simultaneously
- `minOverlapDuration` = minimum overlap threshold (default: 10 minutes)

**Implementation**:
```python
def calculate_overtaking_count(runners_a, runners_b, segment, min_overlap):
    overtakes = 0
    for runner_a in runners_a:
        for runner_b in runners_b:
            if has_temporal_overlap(runner_a, runner_b, segment, min_overlap):
                overtakes += 1
    return overtakes
```

#### **Overtaking Rate**
**Definition**: Overtaking count per unit time

**Formula**:
```
overtaking_rate = overtaking_count / analysis_duration
```

**Where**:
- `analysis_duration` = total time window for analysis
- Units: events per minute

**Implementation**:
```python
def calculate_overtaking_rate(overtaking_count, analysis_duration):
    return overtaking_count / analysis_duration
```

#### **Overtaking Load**
**Definition**: Burden of overtaking on individual runners

**Formula**:
```
overtaking_load = (overtaking_count / total_runners) * intensity_factor
```

**Where**:
- `total_runners` = total number of runners in segment
- `intensity_factor` = based on pace differences and segment characteristics

**Implementation**:
```python
def calculate_overtaking_load(overtaking_count, total_runners, intensity_factor):
    return (overtaking_count / total_runners) * intensity_factor
```

### **Convergence Calculations**

#### **Convergence Points**
**Definition**: Specific locations where events meet or merge

**Formula**:
```
convergence_point = (from_km + to_km) / 2
```

**Where**:
- `from_km` = segment start kilometer
- `to_km` = segment end kilometer

**Implementation**:
```python
def find_convergence_points(segment):
    return (segment['from_km'] + segment['to_km']) / 2
```

#### **Convergence Duration**
**Definition**: How long events remain in close proximity

**Formula**:
```
convergence_duration = max(end_time) - min(start_time)
```

**Where**:
- `start_time` = when first event enters segment
- `end_time` = when last event exits segment

**Implementation**:
```python
def calculate_convergence_duration(events_in_segment):
    start_times = [event['start_time'] for event in events_in_segment]
    end_times = [event['end_time'] for event in events_in_segment]
    return max(end_times) - min(start_times)
```

#### **Convergence Intensity**
**Definition**: Density of interactions at convergence points

**Formula**:
```
convergence_intensity = overtaking_count / convergence_duration
```

**Where**:
- `overtaking_count` = overtakes during convergence period
- `convergence_duration` = duration of convergence

**Implementation**:
```python
def calculate_convergence_intensity(overtaking_count, convergence_duration):
    return overtaking_count / convergence_duration
```

## 👥 **Density Analysis Metrics**

### **Core Density Calculations**

#### **Peak Density**
**Definition**: Maximum density value observed in a segment

**Formula**:
```
peak_density = max(density_values)
```

**Where**:
- `density_values` = all density calculations for segment

**Implementation**:
```python
def calculate_peak_density(density_series):
    return density_series.max()
```

#### **Average Density**
**Definition**: Mean density value over analysis period

**Formula**:
```
average_density = Σ(density_values) / time_windows
```

**Where**:
- `density_values` = all density calculations for segment
- `time_windows` = number of time windows analyzed

**Implementation**:
```python
def calculate_average_density(density_series):
    return density_series.mean()
```

#### **Sustained Density**
**Definition**: Density maintained above threshold for extended period

**Formula**:
```
sustained_density = Σ(time_windows_above_threshold) * time_window_duration
```

**Where**:
- `time_windows_above_threshold` = consecutive time windows above threshold
- `time_window_duration` = duration of each time window

**Implementation**:
```python
def calculate_sustained_density(density_series, threshold):
    above_threshold = density_series > threshold
    sustained_periods = []
    current_period = 0
    
    for is_above in above_threshold:
        if is_above:
            current_period += 1
        else:
            if current_period > 0:
                sustained_periods.append(current_period)
                current_period = 0
    
    return sum(sustained_periods) * time_window_duration
```

### **Density Classification**

#### **Level of Service (LOS) Calculation**
**Definition**: Classification of density into manageable categories

**Formula**:
```
if density < 2.0:
    los = "A"
elif density < 4.0:
    los = "B"
elif density < 6.0:
    los = "C"
elif density < 8.0:
    los = "D"
elif density < 10.0:
    los = "E"
else:
    los = "F"
```

**Implementation**:
```python
def classify_density_level(density):
    if density < 2.0:
        return "A"
    elif density < 4.0:
        return "B"
    elif density < 6.0:
        return "C"
    elif density < 8.0:
        return "D"
    elif density < 10.0:
        return "E"
    else:
        return "F"
```

## 🔗 **Flow-Density Correlation Metrics**

### **Correlation Analysis**

#### **Flow Intensity Classification**
**Definition**: Categorization of flow intensity based on overtaking rates

**Formula**:
```
if overtaking_rate > 3.0:
    flow_intensity = "High"
elif overtaking_rate > 1.5:
    flow_intensity = "Medium"
else:
    flow_intensity = "Low"
```

**Implementation**:
```python
def classify_flow_intensity(overtaking_rate):
    if overtaking_rate > 3.0:
        return "High"
    elif overtaking_rate > 1.5:
        return "Medium"
    else:
        return "Low"
```

#### **Correlation Type Determination**
**Definition**: Type of correlation between flow and density patterns

**Formula**:
```
if flow_intensity == "High" and density_class in ["C", "D", "E", "F"]:
    correlation_type = "critical_correlation"
elif flow_intensity == "High" and density_class in ["A", "B"]:
    correlation_type = "flow_dominant"
elif flow_intensity in ["Low", "Medium"] and density_class in ["C", "D", "E", "F"]:
    correlation_type = "density_dominant"
else:
    correlation_type = "balanced"
```

**Implementation**:
```python
def determine_correlation_type(flow_intensity, density_class):
    if flow_intensity == "High" and density_class in ["C", "D", "E", "F"]:
        return "critical_correlation"
    elif flow_intensity == "High" and density_class in ["A", "B"]:
        return "flow_dominant"
    elif flow_intensity in ["Low", "Medium"] and density_class in ["C", "D", "E", "F"]:
        return "density_dominant"
    else:
        return "balanced"
```

## ⏱️ **Time Calculations**

### **Time Unit Conversions**

#### **Minutes to Seconds**
**Formula**:
```
seconds = minutes * 60.0
```

**Implementation**:
```python
def minutes_to_seconds(minutes):
    return minutes * 60.0
```

#### **Pace Conversion**
**Formula**:
```
pace_seconds_per_km = pace_minutes_per_km * 60.0
```

**Implementation**:
```python
def convert_pace_to_seconds(pace_min_per_km):
    return pace_min_per_km * 60.0
```

#### **Time Window Calculations**
**Formula**:
```
time_window_start = analysis_start + (window_index * time_window_duration)
time_window_end = time_window_start + time_window_duration
```

**Implementation**:
```python
def calculate_time_window(analysis_start, window_index, time_window_duration):
    start = analysis_start + (window_index * time_window_duration)
    end = start + time_window_duration
    return start, end
```

## 📏 **Spatial Calculations**

### **Segment Area Calculations**

#### **Segment Length**
**Formula**:
```
segment_length = to_km - from_km
```

**Implementation**:
```python
def calculate_segment_length(segment):
    return segment['to_km'] - segment['from_km']
```

#### **Segment Area**
**Formula**:
```
segment_area = segment_length * width_m
```

**Where**:
- `width_m` = segment width in meters (from segments.csv)

**Implementation**:
```python
def calculate_segment_area(segment, width_m):
    length = calculate_segment_length(segment)
    return length * width_m
```

#### **Density Calculation**
**Formula**:
```
density = runner_count / segment_area
```

**Where**:
- `runner_count` = number of runners in segment at time
- `segment_area` = area of segment in square meters

**Implementation**:
```python
def calculate_density(runner_count, segment_area):
    return runner_count / segment_area
```

## 🔍 **Validation Formulas**

### **Data Validation**

#### **Pace Range Validation**
**Formula**:
```
is_valid_pace = 3.0 <= pace_min_per_km <= 8.0
```

**Implementation**:
```python
def validate_pace(pace_min_per_km):
    return 3.0 <= pace_min_per_km <= 8.0
```

#### **Segment Boundary Validation**
**Formula**:
```
is_valid_boundary = 0 <= from_km < to_km
```

**Implementation**:
```python
def validate_segment_boundary(from_km, to_km):
    return 0 <= from_km < to_km
```

#### **Time Overlap Validation**
**Formula**:
```
has_overlap = max(start_a, start_b) < min(end_a, end_b)
```

**Implementation**:
```python
def has_temporal_overlap(start_a, end_a, start_b, end_b):
    return max(start_a, start_b) < min(end_a, end_b)
```

## 📊 **Statistical Calculations**

### **Summary Statistics**

#### **Mean Calculation**
**Formula**:
```
mean = Σ(values) / count(values)
```

**Implementation**:
```python
def calculate_mean(values):
    return sum(values) / len(values)
```

#### **Standard Deviation**
**Formula**:
```
std_dev = sqrt(Σ((value - mean)²) / count(values))
```

**Implementation**:
```python
def calculate_std_dev(values):
    mean = calculate_mean(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)
```

#### **Percentile Calculation**
**Formula**:
```
percentile = sorted_values[int(percentile * len(sorted_values))]
```

**Implementation**:
```python
def calculate_percentile(values, percentile):
    sorted_values = sorted(values)
    index = int(percentile * len(sorted_values))
    return sorted_values[index]
```

## 🔗 **Cross-References to Implementation**

### **Flow Analysis Implementation**
- **File**: `app/flow.py`
- **Functions**: `analyze_temporal_flow_segments()`, `calculate_overtaking()`
- **Classes**: `TemporalFlowAnalyzer`

### **Density Analysis Implementation**
- **File**: `app/density.py`
- **Functions**: `analyze_density_segments()`, `calculate_density()`
- **Classes**: `DensityAnalyzer`

### **Correlation Analysis Implementation**
- **File**: `app/flow_density_correlation.py`
- **Functions**: `analyze_flow_density_correlation()`, `classify_density_level()`
- **Classes**: `FlowDensityCorrelator`

### **Utility Functions**
- **File**: `app/utils.py`
- **Functions**: `convert_time_units()`, `validate_data()`
- **Classes**: `DataValidator`

---

**This completes the comprehensive metric definitions appendix. All formulas are based on the actual implementation in the run-density application.**
