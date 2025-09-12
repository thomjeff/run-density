# Issue #131 Investigation Summary - Density Enhancements

## Overview
Issue #131 is a comprehensive enhancement to transform `run-density` from a metrics-only report into operational intelligence for race management. This is a **major feature enhancement** that builds on the v2.0 rulebook work completed in Issue #134.

## Functional Requirements Analysis

### **Core Enhancement Goals**
1. **Start-corral LOS Schema (A1 only)** - Context-specific density interpretation for managed starts
2. **Flow Rate Metric** - `runners/min/m` calculation for throughput analysis
3. **Dual Triggers** - Density OR flow-based mitigations with debounce/cooldown
4. **Scenario Overrides** - CLI/env overrides for "what-if" planning (Option A)

### **Research Foundation**
- **Academic Grounding**: Based on Fruin's pedestrian LOS framework (1971) and marathon-specific research
- **Start-corral Research**: Controlled corral designs reduce density (0.5-1.2 runners/m²) and cap throughput (36-59 runners/min/m)
- **On-course Application**: Standard Fruin A-F thresholds for running segments

### **Key Technical Concepts**

#### **Schema Binding System**
- `start_corral` - A1 only, more tolerant thresholds, flow-enabled
- `on_course_narrow` - Merges, funnels, bridges, finish (flow-enabled)
- `on_course_open` - General running segments (density only)

#### **Flow Rate Calculation**
```python
def compute_flow_rate(runners_crossing: int, width_m: float, bin_seconds: int) -> float:
    minutes = max(bin_seconds / 60.0, 1e-9)
    return runners_crossing / (width_m * minutes)  # runners/min/m
```

#### **Dual Trigger System**
- `density_gte` - Density-based triggers (e.g., "E" = 1.20 runners/m²)
- `flow_gte` - Flow-based triggers (e.g., "critical" = 110 runners/min/m)
- Debounce/cooldown to prevent noise

## Technical Implementation Analysis

### **Files to Modify**
1. **`app/density.py`** - Parse Option A overrides from CLI/env
2. **`app/flow.py`** - Add per-segment count-line flow calculation
3. **`app/density_template_engine.py`** - New module for v2.0 rulebook processing
4. **`app/density_report.py`** - Render Peak Flow and fired mitigations

### **New Module: `density_template_engine.py`**
This appears to be a new module that would:
- Load `Density_Rulebook_v2.yml`
- Bind segment types to schemas
- Map density to LOS using appropriate schema
- Compute flow rates where enabled
- Evaluate dual triggers with debounce/cooldown

### **Option A Parser Implementation**
The provided `option_a_parser.py` shows:
- CLI argument parsing for scenario overrides
- Environment variable fallbacks
- Basic validation and clamping
- In-memory only (no persistence)

### **Enhanced Rulebook Structure**
The v2.0 rulebook includes:
- **Schemas** with different LOS thresholds for different segment types
- **Flow references** for flow-based triggers
- **Debounce/cooldown** configuration
- **Binding rules** to map segments to schemas
- **Triggers** with dual density/flow conditions

## Questions and Considerations

### **Architecture Questions**
1. **Module Structure**: Should `density_template_engine.py` be a new module or integrated into existing `density.py`?
2. **Flow Integration**: How does this integrate with existing `app/flow.py` temporal flow analysis?
3. **Data Flow**: How are flow rates calculated and passed between modules?

### **Implementation Complexity**
1. **Scope**: This is a significant enhancement that touches multiple core modules
2. **Testing**: Requires comprehensive unit tests, integration tests, and E2E tests
3. **Backward Compatibility**: Must maintain existing functionality while adding new features

### **Technical Challenges**
1. **Flow Calculation**: Need to implement count-line flow calculation at segment entrances
2. **Schema Binding**: Complex logic to determine which schema applies to each segment
3. **Trigger Evaluation**: Dual trigger system with debounce/cooldown state management
4. **Rendering**: Enhanced report formatting with Peak Flow and mitigations

### **Integration Points**
1. **Existing v2.0 Work**: How does this build on the v2.0 rulebook work from Issue #134?
2. **Flow Analysis**: How does this relate to existing temporal flow analysis?
3. **Report Generation**: How does this enhance existing density report generation?

## Risk Assessment

### **High Risk Areas**
1. **Complexity**: This is a major feature that could introduce bugs
2. **Integration**: Multiple modules need to work together seamlessly
3. **Testing**: Comprehensive testing required to ensure reliability
4. **Performance**: Flow calculations could impact performance

### **Mitigation Strategies**
1. **Incremental Implementation**: Implement in chunks as specified
2. **Comprehensive Testing**: Unit, integration, and E2E tests
3. **Backward Compatibility**: Ensure existing functionality remains intact
4. **Documentation**: Clear documentation of new features and APIs

## Recommendations

### **Implementation Approach**
1. **Start with Chunk 1**: Implement start-corral LOS schema for A1
2. **Add Flow Calculation**: Implement flow rate computation
3. **Implement Triggers**: Add dual trigger system with debounce/cooldown
4. **Add Scenario Overrides**: Implement Option A CLI/env overrides

### **Testing Strategy**
1. **Unit Tests**: Test each component individually
2. **Integration Tests**: Test module interactions
3. **E2E Tests**: Test complete workflow with sample data
4. **Scenario Tests**: Test with and without overrides

### **Documentation Needs**
1. **API Documentation**: Document new functions and classes
2. **User Guide**: Update user guide with new features
3. **Technical Documentation**: Document architecture decisions

## Conclusion

Issue #131 is a **major enhancement** that would significantly improve the operational intelligence capabilities of `run-density`. The requirements are well-defined with clear acceptance criteria, and the technical approach is sound.

**Key Success Factors:**
- Incremental implementation following the chunk-based approach
- Comprehensive testing at each stage
- Careful integration with existing v2.0 rulebook work
- Clear documentation and user guidance

**Estimated Complexity:** High - This is a significant feature that will require careful planning and implementation.

**Recommended Next Steps:**
1. Review integration with existing v2.0 rulebook work
2. Plan incremental implementation approach
3. Design comprehensive testing strategy
4. Consider breaking into smaller, manageable issues
