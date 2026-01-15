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

### Critical Recommendations
Prioritize recommendations:
- **Priority 1:** Immediate action items (must address before race day)
- **Priority 2:** Strategic improvements (planning and resource deployment)

For each recommendation, specify:
- Target segment(s)
- Specific actions
- Expected impact
- Implementation timeline

### Risk Assessment
Categorize risks as:
- **Low Risk:** Acceptable conditions, minimal monitoring needed
- **Medium Risk:** Requires operational attention but manageable
- **High Risk:** Critical conditions requiring immediate mitigation

### Operational Readiness Assessment
Provide readiness level:
- ✅ **OPERATIONAL** - Ready for race day with no changes
- ✅ **OPERATIONAL WITH MONITORING** - Ready with enhanced monitoring
- ⚠️ **CONDITIONAL** - Requires specific mitigations
- 🔴 **NOT READY** - Requires significant changes before race day

Include required actions before race day.

---

## Output Format

Format your response exactly as shown in the example structure below. Use markdown headings, tables, and lists for clarity.

---

Generate your analysis now:
