# LOS Tables with Operational Meaning

## Start-corral (A1 only)
| LOS | Density (runners/m²) | What it means operationally |
|---|---:|---|
| A | < 0.40 | Very open pen; easy movement; no intervention. |
| B | 0.40–0.70 | Comfortable staging; routine monitoring only. |
| C | 0.70–0.95 | Noticeably busier; keep metering cadence steady. |
| D | 0.95–1.20 | Tight but acceptable with active control; keep pulses short; eyes on funnel. |
| E | 1.20–1.60 | Crowded—deploy mitigations (hold pulse, narrow gate, widen pen lanes). |
| F | > 1.60 | Over-crowded—stop/hold release; relieve pressure before resuming. |

## On-course (Fruin-derived)
| LOS | Density (runners/m²) | What it means operationally |
|---|---:|---|
| A | < 0.31 | Free flow; no management needed. |
| B | 0.31–0.43 | Comfortable; routine observation. |
| C | 0.43–0.72 | Moderate; watch narrow points/turns. |
| D | 0.72–1.08 | Busy—prep light mitigations at funnels/merges. |
| E | 1.08–1.63 | Constrained—mitigate (widen lane, meter merges, marshal at pinch). |
| F | > 1.63 | Severe—intervene (pause sources, create bypass, relieve blockage). |

**Terminology note:** `gte` means **greater than or equal to** (not “gate”). Used in trigger conditions like `density_gte`, `flow_gte`.
