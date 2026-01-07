## Flow UI Enhancement Proposal
_This is part of Flow enhancements for the end-user via UI (this issue) and CSV (#629)._

## Files for Codex:
- Are located in /codex/7iHmDgGFMZdpjLmZRVgYWY
- UI artifacts (sunday): /codex/7iHmDgGFMZdpjLmZRVgYWY/sun/ui
- captions.json: /codex/7iHmDgGFMZdpjLmZRVgYWY/sun/ui/visualizations

**Definition of Done:** this enhancement will require changes to the UI, the .json files that serve the UI and the API. The issue is considered complete when the end-to-end from analysis that produces the UI artifacts to rendering the UI is successful._

### Overview
This proposal outlines enhancements to the **Flow Analysis UI**, bringing it in line with the improved usability and interpretability of the **Density UI**. These changes aim to support:
- Quicker detection of problem zones  
- Deeper drilldown into flow dynamics  
- Clearer narrative context for flow metrics  

Flow UI (current)
_Codex:_ view file: /codex/issue628/flow.png
<img width="754" height="1205" alt="Image" src="https://github.com/user-attachments/assets/cb40d1a4-ff8c-4376-b158-aac1cbf4680e" />

Density UI (current)
_Codex:_ view file: /codex/issue628/density.png

<img width="754" height="1400" alt="Image" src="https://github.com/user-attachments/assets/6d46e25f-df67-41df-a03b-a3388bdd7528" />

---

###  1. Segment Table Enhancements

**Current:**  
The Flow UI displays segment-level totals with no reference to which zone(s) contribute to the congestion.

**Enhancement:**  
Add a new column to the segment table:

| Column Name        | Description |
|--------------------|-------------|
| `Worst Zone`       | Displays the highest-flow zone within the segment, e.g., `8/11` meaning zone 8 of 11 |
| `Worst Metric` (optional) | Displays the dominant metric in the worst zone, e.g., `copresence=1466` |

**Design Notes:**
- Clicking on a segment row will expand zone-level detail below.

---

### 2. Zone-Level Table (Drilldown)

**Inspired by:** Density’s zone drilldown table.

**Behavior:**
When a user selects a segment row, show a secondary table displaying all associated zones.

| zone_index | cp_km | event_a | event_b | overtaking_a | overtaking_b | overtaken_a | overtaken_b | copresence_a | copresence_b |
|------------|-------|---------|---------|---------------|---------------|--------------|--------------|----------------|----------------|

**Optional Columns:**
- `multi_category_runners`
- `participants_involved`
- `unique_encounters`

**Design Notes:**
- Columns should be sortable.
- Support filtering or toggling between views: `All`, `High Co-presence`, `High Overtaking`, etc.
- Unlike density, there is *no heatmap* or other visual for flow at this time.

---

### 3. Narrative Caption Generator

**Purpose:**
Add a contextual, human-readable summary for each zone, helping users interpret the raw numbers.

**Example (F1a, Zone 8):**
> In Zone 8 of segment F1a (230m), 89.6% of 10K runners and 100% of Half runners were co-present. 555 Half runners overtook 275 10K runners, forming a 2:1 overtaking ratio. Meanwhile, 127 fast 10K runners overtook slower Half runners. This zone demonstrates peak congestion and bidirectional overtaking pressure.

**Implementation:**
- Research how [captions.json](https://github.com/user-attachments/files/24482018/captions.json) is being generated in code for density heatmaps. Consider adopting similar approach. TODO: Codex research how this is done today. 
- Auto-display caption under zone row when expanded.

---

### Future Enhancements
- Visualization like Density that shows a heatmap type visual across all zones in a segment.

---

### Benefits
| Feature                   | Value                                                                 |
|---------------------------|-----------------------------------------------------------------------|
| Worst zone summary        | Surfaces hidden trouble areas in otherwise “fine” segments            |
| Zone-level drilldown      | Aligns Flow UX with Density, empowers deeper diagnosis                |
| Narrative interpretation  | Bridges data to insight — great for reports and user comprehension    |
| Toggleable metrics        | Makes UI more flexible for various analytic needs                     |
