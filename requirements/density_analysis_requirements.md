# Density Analysis Requirements & Workplan

**Version**: 1.1  
**Date**: 2025-09-03  
**Status**: Updated with ChatGPT Corrections  
**Dependencies**: Temporal Flow Analysis (v1.5.0) Complete  

**Note**: This document has been updated to incorporate ChatGPT's corrections, including:
- Corrected width handling (use `width_m` directly, no division)
- Improved data structures and API contracts
- Enhanced module design with dataclass-based approach
- Clearer integration patterns with orchestrator approach  

## 1. Overview

### 1.1 Purpose
Density analysis provides the "how tight" component that complements temporal flow's "when" and "how many" insights. While temporal flow measures runner interactions and timing, density analysis quantifies the spatial concentration of runners within segments.

### 1.2 Key Distinction: Flow vs Density
- **Temporal Flow**: Measures runner interactions, overtakes, merges, and timing patterns
- **Density Analysis**: Measures spatial concentration of runners per unit area/volume
- **Integration**: Flow provides the temporal context; density provides the spatial context

### 1.3 Architecture Principle
- **Separate Module**: `density.py` remains independent from `temporal_flow.py`
- **Single Source of Truth**: `segments.csv` serves both modules
- **No Hardcoding**: All parameters configurable via segments.csv or function parameters
- **Functional Separation**: Strict boundaries between flow and density calculations

## 2. Density Types & Definitions

### 2.1 Areal Density
**Definition**: Runners per square meter (runners/m²)  
**Purpose**: Measures how tightly packed runners are within a given area  
**Use Case**: Course width planning, safety assessments, marshalling decisions  
**Formula**: `areal_density = concurrent_runners / (segment_length_m × effective_width_m)`

### 2.2 Crowd Density  
**Definition**: Runners per meter of course length (runners/m)  
**Purpose**: Measures linear concentration along the course  
**Use Case**: Flow rate analysis, bottleneck identification, pacing considerations  
**Formula**: `crowd_density = concurrent_runners / segment_length_m`

### 2.3 Why Both Are Calculated
- **Areal Density**: Critical for safety (overcrowding risks) and course design
- **Crowd Density**: Essential for flow management and operational planning
- **Complementary**: Together they provide complete spatial understanding

## 3. Data Structures & API Contracts

### 3.1 Input Data
- `segments.csv` (single source of truth for `from_km`, `to_km`, `width_m`, `direction`)
- `concurrent_runners` per segment per time bin (from temporal flow)
- **Config** (defaults but overridable):
  - `bin_seconds` (default: 30)
  - `threshold_areal` (default: 1.2 runners/m²)
  - `threshold_crowd` (default: 2.0 runners/m)

### 3.2 Core Derived Fields
- `segment_length_m = (to_km - from_km) × 1000`
- `width_m = actual usable course width from segments.csv`

### 3.3 Output Data Structures

#### Per-Segment, Per-Time-Bin Output
```json
{
  "segment_id": "A1a",
  "t_start": "08:45:00",
  "t_end": "08:45:30",
  "concurrent_runners": 234,
  "areal_density": 1.62,
  "crowd_density": 2.34,
  "los_areal": "Busy",
  "los_crowd": "Medium",
  "flags": []
}
```

#### Per-Segment Aggregate Output
```json
{
  "segment_id": "A1a",
  "peak_areal_density": 1.87,
  "peak_areal_time_window": ["08:44:30","08:48:30"],
  "peak_crowd_density": 3.12,
  "peak_crowd_time_window": ["08:45:00","08:46:00"],
  "tot_areal_sec": 720,
  "tot_crowd_sec": 420,
  "los_areal_distribution": {"Comfortable": 0.40, "Busy": 0.45, "Constrained": 0.15},
  "los_crowd_distribution": {"Low": 0.35, "Medium": 0.40, "High": 0.25}
}
```

### 3.4 Module Surface (Dataclass-Based Design)
```python
@dataclass(frozen=True)
class DensityConfig:
    bin_seconds: int = 30
    threshold_areal: float = 1.2  # runners/m^2
    threshold_crowd: float = 2.0  # runners/m

@dataclass(frozen=True)
class SegmentMeta:
    segment_id: str
    from_km: float
    to_km: float
    width_m: float
    direction: str  # "uni" | "bi"

def compute_density_timeseries(...): ...
def summarize_density(...): ...
```

## 4. Mathematical Formulas

### 4.1 Core Density Calculations

#### Areal Density
```
areal_density = concurrent_runners / (segment_length_m × width_m)

Where:
- concurrent_runners = runners present in segment at time t
- segment_length_m = (to_km - from_km) × 1000
- width_m = actual usable course width from segments.csv
```

#### Crowd Density
```
crowd_density = concurrent_runners / segment_length_m

Where:
- concurrent_runners = runners present in segment at time t  
- segment_length_m = (to_km - from_km) × 1000
```

#### Effective Width (Corrected)
```
effective_width_m = width_m  (always, regardless of direction)

Note: segments.csv contains the actual usable course width (width_m) 
for each segment, with bi-directional adjustments already calculated.
```

### 4.2 Time-Over-Threshold (TOT) Calculations

#### TOT for Areal Density
```
tot_areal = Σ(time_bins where areal_density > threshold_areal)

Where:
- threshold_areal = configurable (default: 1.2 runners/m²)
- time_bins = temporal resolution (default: 30 seconds)
```

#### TOT for Crowd Density
```
tot_crowd = Σ(time_bins where crowd_density > threshold_crowd)

Where:
- threshold_crowd = configurable (default: 2.0 runners/m)
- time_bins = temporal resolution (default: 30 seconds)
```

### 4.3 Level of Service (LOS) Classification

#### Areal Density LOS
```
LOS_areal = {
    "Comfortable": areal_density < 1.0 runners/m²
    "Busy": 1.0 ≤ areal_density < 1.8 runners/m²  
    "Constrained": areal_density ≥ 1.8 runners/m²
}
```

#### Crowd Density LOS
```
LOS_crowd = {
    "Low": crowd_density < 1.5 runners/m
    "Medium": 1.5 ≤ crowd_density < 3.0 runners/m
    "High": crowd_density ≥ 3.0 runners/m
}
```

## 5. Dependencies with Temporal Flow

### 5.1 Data Dependencies
- **Runner Counts**: Density analysis uses concurrent runner counts from temporal flow
- **Timing Data**: Entry/exit times from temporal flow for temporal density calculations
- **Segment Data**: Both modules share segments.csv as single source of truth

### 5.2 Calculation Dependencies
- **Independent Calculations**: Density calculations are independent of flow calculations
- **Shared Inputs**: Both use same runner data and segment definitions
- **No Circular Dependencies**: Flow does not depend on density results

### 5.3 Integration Points (Orchestrator Pattern)
- **No Circular Dependencies**: Orchestrator calls both flow and density independently
- **Combined Reporting**: Both analyses can be reported together via orchestrator
- **Shared Parameters**: Both use same time bins and segment definitions
- **Complementary Insights**: Flow provides "when", density provides "how tight"

## 6. Reporting Integration

### 6.1 Flow Summary Integration
```
Segment Summary Report:
├── Flow Analysis
│   ├── Peak concurrent runners
│   ├── Peak time window
│   ├── Total interactions
│   └── Flow type (overtake/merge/diverge)
└── Density Analysis
    ├── Peak areal density (runners/m²)
    ├── Peak crowd density (runners/m)
    ├── LOS classification
    └── TOT metrics
```

### 6.2 Flow Detailed Analysis Integration
```
Detailed Analysis Report:
├── Temporal Flow Details
│   ├── Entry/exit times
│   ├── Overlap windows
│   ├── Runner characteristics
│   └── Deep dive analysis
└── Density Analysis Details
    ├── Density time series
    ├── LOS transitions
    ├── TOT breakdowns
    └── Operational recommendations
```

### 6.3 Combined Narrative
- **Flow Narrative**: "Peak interactions occur at 08:45 with 234 concurrent runners"
- **Density Narrative**: "Peak density reaches 1.6 runners/m² (Busy LOS) for 12 minutes"
- **Combined**: "Peak interactions at 08:45 with 234 runners create Busy conditions (1.6/m²) for 12 minutes"

## 7. Test Plan Strategy

### 7.1 Unit Testing
- **Density Calculations**: Test areal and crowd density formulas with known inputs
- **LOS Classification**: Verify LOS thresholds and classifications
- **TOT Calculations**: Test time-over-threshold logic
- **Width Adjustments**: Test bi-directional width calculations

### 7.2 Integration Testing
- **Segments.csv Integration**: Verify width_m parameter usage
- **Temporal Flow Integration**: Test combined reporting
- **API Endpoint Testing**: Verify density endpoints work correctly

### 7.3 Validation Testing
- **Known Segments**: Test against segments with known density characteristics
- **Edge Cases**: Test with very narrow/wide segments, high/low runner counts
- **Performance Testing**: Verify calculations complete within acceptable time

### 7.4 Comprehensive Testing
- **All 36 Segments**: Run density analysis on all segments
- **Expected vs Actual**: Compare against expected density values
- **Regression Testing**: Ensure changes don't break existing functionality

## 8. Workplan & Milestones

### Phase 1: Core Density Engine (Week 1)
**Milestone 1.1**: Basic density calculations
- [ ] Implement areal density calculation
- [ ] Implement crowd density calculation  
- [ ] Add effective width adjustment logic
- [ ] **Commit**: "Implement core density calculations"

**Milestone 1.2**: LOS classification system
- [ ] Implement areal density LOS classification
- [ ] Implement crowd density LOS classification
- [ ] Add configurable thresholds
- [ ] **Commit**: "Add LOS classification system"

### Phase 2: TOT & Advanced Metrics (Week 1)
**Milestone 2.1**: Time-over-threshold calculations
- [ ] Implement TOT for areal density
- [ ] Implement TOT for crowd density
- [ ] Add configurable thresholds
- [ ] **Commit**: "Implement TOT calculations"

**Milestone 2.2**: Density time series analysis
- [ ] Generate density time series data
- [ ] Add peak density identification
- [ ] Implement density distribution analysis
- [ ] **Commit**: "Add density time series analysis"

### Phase 3: Integration & Reporting (Week 2)
**Milestone 3.1**: API endpoint integration
- [ ] Create density analysis endpoint
- [ ] Integrate with existing API structure
- [ ] Add error handling and validation
- [ ] **Commit**: "Add density API endpoint"

**Milestone 3.2**: Combined reporting
- [ ] Integrate density with flow summary reports
- [ ] Add combined narrative generation
- [ ] Implement detailed analysis integration
- [ ] **Commit**: "Integrate density with flow reporting"

### Phase 4: Testing & Validation (Week 2)
**Milestone 4.1**: Comprehensive testing
- [ ] Run density analysis on all 36 segments
- [ ] Generate comprehensive test report
- [ ] Validate against expected values
- [ ] **Commit**: "Complete comprehensive density testing"

**Milestone 4.2**: Documentation & release
- [ ] Update CHANGELOG.md with density features
- [ ] Create density analysis documentation
- [ ] Prepare for v1.6.0 release
- [ ] **Commit**: "Prepare density analysis for v1.6.0 release"

## 9. Success Criteria

### 9.1 Functional Requirements
- [ ] All 36 segments can be analyzed for density
- [ ] Both areal and crowd density calculations work correctly
- [ ] LOS classification provides meaningful insights
- [ ] TOT metrics support operational planning
- [ ] Integration with temporal flow reporting works seamlessly

### 9.2 Performance Requirements
- [ ] Density calculations complete within 5 seconds per segment
- [ ] Combined flow+density reports generate within 10 seconds
- [ ] API endpoints respond within 2 seconds
- [ ] Memory usage remains within acceptable limits

### 9.3 Quality Requirements
- [ ] 100% test coverage for density calculations
- [ ] All 36 segments pass comprehensive validation
- [ ] No hardcoded values in density module
- [ ] Clear separation between flow and density functionality

## 10. Risk Mitigation

### 10.1 Technical Risks
- **Risk**: Performance issues with large datasets
- **Mitigation**: Implement efficient algorithms and caching

- **Risk**: Integration complexity with existing flow system
- **Mitigation**: Maintain strict module separation and clear interfaces

### 10.2 Data Risks
- **Risk**: Missing or incorrect width_m values in segments.csv
- **Mitigation**: Add validation and default values

- **Risk**: Inconsistent density calculations across segments
- **Mitigation**: Comprehensive testing and validation framework

## 11. Future Enhancements

### 11.1 Advanced Features
- **Dynamic Width**: Use GPX data for actual course width
- **Weather Adjustments**: Factor in weather conditions on density
- **Historical Analysis**: Compare density across multiple race years

### 11.2 Visualization
- **Density Heatmaps**: Visual representation of density over time
- **LOS Transitions**: Charts showing LOS changes over time
- **Combined Dashboards**: Flow and density visualizations together

---

**Document Status**: Ready for Review  
**Next Step**: Begin Phase 1 implementation  
**Estimated Completion**: 2 weeks  
**Dependencies**: Temporal Flow Analysis (v1.5.0) Complete ✅
