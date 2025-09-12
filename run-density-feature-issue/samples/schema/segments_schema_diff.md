# Optional schema change for `segments.csv`

## Current (example)
segment_id,name,width_m,segment_type
A1,Start to Queen/Regent,5.0,start
F1,Bridge merge southbound,5.0,merge

## Proposed additions
segment_id,name,width_m,segment_type,flow_rate_required,notes
A1,Start to Queen/Regent,5.0,start,true,"Enable flow & start-corral schema"
F1,Bridge merge southbound,5.0,merge,true,"Enable flow at merge"
B2,Trail straightaway,7.0,trail,false,"Density-only"

- `flow_rate_required`: boolean; if omitted, engine derives from `segment_type` (start,funnel,merge,bridge,finish → true).
