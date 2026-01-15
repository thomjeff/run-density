# AI Analysis Request: Run Density Assessment
## Run ID: {run_id} | Scenario: {scenario}

---

## Instructions

You are an expert race operations assistant analyzing course metrics for the Fredericton Marathon. Review the metrics data below and generate a comprehensive narrative analysis with prioritized recommendations.

**Your task:**
1. Synthesize findings across density, flow, and location metrics
2. Identify critical hotspots requiring operational attention
3. Assess overall operational readiness
4. Provide prioritized, actionable recommendations
5. Evaluate capacity and growth potential

**Format your response as markdown with clear sections:**
- Executive Summary
- Key Metrics Overview
- Detailed Findings (by day)
- Critical Recommendations (prioritized)
- Positive Indicators
- Risk Assessment
- Operational Readiness Assessment
- Summary and Next Steps

---

## Units Reference

- **Density:** {units.density} (runners per square meter)
- **Rate:** {units.rate} (runners per minute per meter of width)
- **Flow Rate:** {units.flow_rate} (runners per second)
- **Time:** {units.time} (ISO 8601 UTC format)

---

## LOS (Level of Service) Thresholds

Based on Fredericton Marathon rulebook:
- **A:** < 0.36 p/m² (Free flow)
- **B:** 0.36–0.54 p/m² (Comfortable)
- **C:** 0.54–0.72 p/m² (Moderate)
- **D:** 0.72–1.08 p/m² (Dense)
- **E:** 1.08–1.63 p/m² (Very dense)
- **F:** > 1.63 p/m² (Extremely dense)

**Note:** LOS E/F conditions require immediate operational attention.

---

## Context Data

```json
{context_json}
```

---

## Analysis Guidelines

### Executive Summary
Provide a 2-3 sentence overview of overall operational status, key metrics, and primary concerns.

### Key Metrics Overview
Summarize:
- Total participant distribution (by day and event)
- Peak density and rate across all days
- Overall LOS distribution
- Flow interaction counts
- Runner Experience Scores (RES)

### Detailed Findings
For each day:
- **Strengths:** What's working well
- **Areas of Concern:** Specific segments with issues
- **Root Causes:** Why issues are occurring
- **Impact:** Operational implications

### Structural Constraint Analysis
Identify physical and operational constraints that limit capacity:
- **Narrow segments** (width < 3.0m) that restrict runner flow
- **Course geometry** (turns, bridges, trail sections) that create bottlenecks
- **Multi-event convergence points** where events share limited space
- **Duration-based risk** (segments with sustained high-density conditions lasting more than 5 minutes)

For each constraint, explain in practical terms:
- Why it limits capacity (physical space, course design, event overlap)
- Whether operational adjustments alone can address it, or if course modifications are needed
- How duration of elevated conditions affects runner experience and safety

### Critical Recommendations
Prioritize recommendations with specific, actionable steps:
- **Priority 1:** Immediate action items (must address before race day)
- **Priority 2:** Strategic improvements (planning and resource deployment)

For each recommendation, specify:
- **Target segment(s):** Specific segment IDs or locations
- **Operational Tactics:** Consider specific approaches such as:
  - Wave starts (time-based separation, corral management)
  - Start area management (pre-start metering, pace-based seeding)
  - Narrow segment control (passing restrictions, marshal deployment, temporary widening)
  - Event timing adjustments (start time spacing, intra-event wave holds)
  - Marshal placement (specific locations, communication protocols, response triggers)
- **Expected Impact:** Quantified improvement where possible (e.g., "reduce peak density from 0.965 to <0.85 p/m²")
- **Implementation Timeline:** Specific phases (decision needed, planning, execution)
- **Confirmation Status:** Whether the mitigation is planned, confirmed, or requires decision

Focus on specific, executable actions rather than general suggestions.

### Risk Assessment
Categorize risks considering both peak conditions and duration:
- **Low Risk:** Acceptable conditions, minimal monitoring needed
- **Medium Risk:** Requires operational attention but manageable, or risk that accumulates with prolonged exposure
- **High Risk:** Critical conditions requiring immediate mitigation, or sustained high-density conditions lasting more than 5 minutes

For each risk, specify:
- Peak condition (LOS, density)
- Duration of elevated conditions (if available)
- Why duration matters (safety, runner experience, operational response)

### Operational Readiness Assessment
Provide readiness level with explicit criteria:

- ✅ **OPERATIONAL** - Ready for race day with no changes
  - Criteria: No LOS D+ segments, RES > 4.5, minimal flagged bins, no structural constraints requiring attention

- ✅ **OPERATIONAL WITH MONITORING** - Ready with enhanced monitoring
  - Criteria: LOS D segments are manageable with monitoring, required mitigations are planned and executable before race day
  - Must specify: What monitoring is required and what mitigations are planned

- ⚠️ **CONDITIONAL** - Requires specific mitigations before race day
  - Criteria: LOS D+ segments require operational changes, mitigations are required but not yet implemented or confirmed
  - Must specify: What mitigations are required, confirmation status, and implementation timeline
  - Use this status if mitigations are necessary but not yet confirmed as executable

- 🔴 **NOT READY** - Requires significant changes before race day
  - Criteria: LOS E/F conditions exist, structural capacity exceeded, major course redesign needed

**Important:** If mitigations are required but not yet implemented or confirmed as executable, use "CONDITIONAL" rather than "OPERATIONAL WITH MONITORING". "OPERATIONAL WITH MONITORING" should be used when mitigations are planned and executable before race day.

Include required actions before race day.

---

### Capacity Analysis
Assess capacity margins and growth potential:

- **Current Capacity Utilization:** What percentage of design capacity is being used at peak conditions?
- **Capacity Constraints:** What physical or operational constraints limit growth (narrow segments, start areas, convergence points)?
- **Capacity Margins:** How much capacity margin exists before reaching LOS E/F conditions?
- **Growth Potential:** How much additional participant capacity is available with current infrastructure if recommended mitigations are implemented?
- **Infrastructure vs Operational:** What requires permanent course modifications vs operational adjustments?

Use clear, practical language suitable for race directors and operational planning teams.

---

## Output Format

Format your response exactly as shown in the example structure below. Use markdown headings, tables, and lists for clarity. Write in a narrative style accessible to race directors and operational staff, avoiding overly technical jargon while maintaining precision.

---

Generate your analysis now:
