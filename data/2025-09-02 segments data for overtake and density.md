### overlaps.csv becomes segments.csv
2025-09-02 17:50
Version 1.0

I’ve completed a detailed analysis of overlaps.csv, and I’ve made some significant changes and shifts in my thinking. 

## New Segments:
The course has been divided into 36 logical segments (see segments.csv). 

## Density:
The first change is that all segments (n=36) are analyzed for Density:
- Density is universal: every segment is included in density calculations. This provides the baseline measure of how crowded a segment is at a given time, regardless of whether overtakes are possible.
- Density = how many runners from one or more events are occupying a given segment at the same time, given start times and pace distributions.
- Input fields: event_A, event_B, from_km, to_km, width_m, and direction.

## Overtake:
Only segments flagged as Overtake (n=18) are analyzed for converged zones and converged runners:
- These are locations where runners from different events can physically encounter and pass each other.
- Overtake = two fields flowing with each other, where faster participants may catch slower ones.
- Converged zones (where two event fields overlap in time/space).
- Converged runners (where faster runners from a later event pass slower runners from an earlier one).
- Only segments where overtake_flag = y are analyzed for overtake.
- This should make computation time more efficient as not all segments need Overtake analysis.

## Additional Notes:
•width_m represents the entire usable width of the path. There is no need to divide by 2 in code.
- Lane management (e.g., keeping runners right) is accounted for operationally by course marshals.
- Density calculations should use the full width.
- direction indicates flow: uni (one-way) or bi (two-way), and is separate from width_m.
- Segment IDs (seg_id) have been cleaned and renumbered consistently to avoid duplicates and align with the logical course flow.

This approach ensures:
- Density analysis covers all segments for congestion/risk planning.
- Overtake analysis is focused only where meaningful cross-event interactions occur (overtake_flag = y)
- Files are streamlined, with only essential columns retained for clarity and maintainability.

## Data
- segments.csv is the authoritative source and is found in /data
- this is provided for quick reference only.

Field Naming:
- seg_id: unique ID for the segment
- segment_label: descrption of the segment
- eventA: must be one of Full, 10K or Half.
- eventB: must be one of Full, 10K or Half.
- from_km_A: the starting km distance for the eventA runner for this segment.
- to_km_A: the ending km distance for the eventA runner for this segment.
- from_km_B: the starting km distance for the eventB runner for this segment.
- to_km_B: the ending km distance for the eventB runner for this segment.
- direction: informtation only for the report/results and should not be used in Overtake or Density calculations.
- width_m: represents the entire usable width of the path. There is no need to divide by 2 in code.
- overtake_flag: is y, then calculate Overtake; if n, then do not calculate Overtake. 
- notes: further info./context for the author of the csv. 

Sample Data:
seg_id,segment_label,eventA,eventB,from_km_A,to_km_A,from_km_B,to_km_B,direction,width_m,overtake_flag,notes
A1a,Start to Queen/Regent (10K/Half),10K,Half,0.00,0.90,0.00,0.90,uni,7.00,y,Start along St John Street; Overtake unlikely.
A1b,Queen/Regent to WSB mid-point (10K/Half),10K,Half,0.90,1.80,0.90,1.80,uni,7.00,y,Pointe St. Anne Blvd to half-way on WSB; Overtake unlikely.
A1c,WSB mid-point to Friel (10K/Half),10K,Half,1.80,2.70,1.80,2.70,uni,7.00,y,Half-way on WSB; Overtake likely.
A2a,Start to Queen/Regent (10K/Full),10K,Full,0.00,0.90,0.00,0.90,uni,7.00,y,Start along St John Street; No Overtake expected
A2b,Queen/Regent to WSB mid-point (10K/Full),10K,Full,0.90,1.80,0.90,1.80,uni,7.00,y,Pointe St. Anne Blvd to half-way on WSB; Overtake unlikely.
A2c,WSB mid-point to Friel  (10KFull),10K,Full,1.80,2.70,1.80,2.70,uni,7.00,y,Half-way on WSB; Overtake possible (Fast 10K / Slow Full).
A3a,Start to Queen/Regent (Half/Full),Half,Full,0.00,0.90,0.00,0.90,uni,7.00,y,Start along St John Street; Overtake unlikely.
A3b,Queen/Regent to WSB mid-point (Half/Full),Half,Full,0.90,1.80,0.90,1.80,uni,7.00,y,Pointe St. Anne Blvd to half-way on WSB; Overtake unlikely.
A3c,WSB mid-point to Friel (Half/Full),Half,Full,1.80,2.70,1.80,2.70,uni,7.00,y,Half-way on WSB; Overtake possible (Fast Half / Slow Full).
B1,Friel to 10K Turn (outbound),10K,Full,2.70,4.25,2.70,4.25,bi,1.50,y,On Trail (1.5m lane); Overtake expected (Fast 10K / Slow Full).
B2,Friel to 10K Turn (10K out/return),10K,10K,2.70,4.25,4.25,5.81,bi,1.50,n,On Trail (1.5m lane); 10K outbound and return from 10K Turn. No Overtake - simply Density.
C1,10K Turn to Friel (10K slow vs Full fast),10K,Full,4.25,5.81,14.80,16.34,bi,1.50,y,On Trail (1.5m lane); Expect Overtake by Fast Full / Slow 10K)
C2,10K Turn to Friel (10K fast vs. Full slow),10K,Full,4.25,5.81,2.70,4.25,bi,1.50,n,On Trail (1.5m lane); 10K return from 10K Turn meet Slow Full on their outbound. No Overtake - simply Density.
D1,10K Turn to Full Turn Blake Crt (out/return),Full,Full,4.25,9.52,9.52,14.80,bi,1.50,n,On Trail (1.5m lane) where this is Full out/back from 10K Turn to Full Turn at Blake Crt.
E1,Friel to 10K Turn (late overlaps),10K,Full,2.70,4.25,14.80,16.34,bi,1.50,n,On Trail (1.5m lane) where slow 10K out to 10K Turn meet Fast Full on their return from Blake Crt. Density only as in opposite direction of flow.
F1,Friel to Station Rd. (shared path),10K,Half,5.81,8.10,2.70,4.95,uni,3.00,y,"On Trail (3.0m, two lanes); Overtake expected (Fast 10K / Slow Half)."
F2,Friel to Station Rd. (shared path),10K,Full,5.81,8.10,16.34,18.59,uni,3.00,y,"On Trail (3.0m, two lanes); Overtake possible (Slow 10K / Fast Full)."
F3,Friel to Station Rd. (shared path),Half,Full,2.70,4.95,16.34,18.59,uni,3.00,y,"On Trail (3.0m, two lanes); Overtake possible (Slow Half / Fast Full)."
G1,Full Loop QS to Trail/Aberdeen (Full Only),Full,Full,20.53,21.65,20.53,21.65,uni,3.00,n,"Full Only on Aberdeen, St John, McLeod, Lincoln Trail (Queen Sq. Loop)"
G2,Trail/Aberdeen to Station Rd (Full outbound to Station vs 10K finish),Full,10K,21.65,23.26,8.10,10.00,bi,1.50,n,Trail at Aberdeen (by water pump station) to Station Rd. where Full runners go right to Gibson Trail. 10K heading southbound to Finish. Shared segment with Half.
G3,Trail/Aberdeen to Station Rd. (Full outbound to Station vs Half finish),Full,Half,21.65,23.26,19.35,21.10,bi,1.50,n,Trail at Aberdeen (by water pump station) to Station Rd. where Full and Half runners go right to Gibson Trail. Shared segment with 10K.
H1,Station Rd. to Bridge/Mill (Half + Full co-direction),Half,Full,4.95,10.84,23.26,29.06,uni,3.00,n,"On Trail (3.0m, two lanes) Full/Half runners from Station/Rd. on to the Gibson Trail to Marysville. "
I1,Bridge/Mill to Half Turn (Half + Full co-direction),Half,Full,10.84,13.43,29.06,31.64,bi,1.50,n,On Trial (1.5m lane) Half to Half Turn. Will continue to Full Turn. Shared with Half.
J1,Half Turn to Full Turn (Full outbound spur),Full,Full,31.64,33.11,31.64,33.11,uni,1.50,n,On Trail (1.5m lane) Full outbound to Full Turn.
J2,Full Turn to Half Turn (Full returning spur),Full,Full,33.11,34.34,33.11,34.34,uni,1.50,n,On Trail (1.5m lane) Full returning from Full Turn to Half Turn.
K1,Half Turn to Bridge/Mill (Half + Full co-direction return),Half,Full,13.43,16.02,34.34,36.92,uni,1.50,n,On Trail (1.5m lane) from Half Turn to Bridge/Mill. Full & Half
K2,Half Turn to Bridge/Mill (Slow Half / Fast Full),Full,Half,34.34,36.92,10.84,13.43,bi,1.50,n,On Trail (1.5m lane) with Slow Half meeting Fast Full on Bridge/Mill to Half Turn.
L1,Bridge/Mill to Station Rd. (Full and Half),Full,Half,36.92,40.57,16.02,19.35,bi,3.00,y,"On Trail (3.0m, two lanes), with Full/Half returning from Marysville to Station Rd."
M1a,Station Rd. to Trail/Aberdeen,10K,Half,8.10,9.75,19.35,20.85,bi,1.50,y,On Trail (1.5m lane) with this segment having runners from all events.
M1b,Station Rd. to Trail/Aberdeen,10K,Full,8.10,9.75,18.59,20.28,uni,1.50,y,On Trail (1.5m lane) with this segment having runners from all events.
M1c,Station Rd. to Trail/Aberdeen,Half,Full,19.35,20.85,18.59,20.28,uni,1.50,y,On Trail (1.5m lane) with this segment having runners from all events.
M1d,Station Rd. to Trail/Aberdeen,Full,Full,40.57,41.95,40.57,41.95,uni,1.50,n,On Trail (1.5m lane) with the Full only on their final leg to Finish.
M2a,Trail/Aberdeen to Finish,10K,Half,9.75,10.00,20.85,21.10,uni,3.00,n,Aberdeen Street to Finish
M2b,Trail/Aberdeen to Finish (Full QS Loop),10K,Full,9.75,10.00,20.28,20.53,uni,3.00,n,Aberdeen Street to Finish
M2c,Trail/Aberdeen to Finish (Full QS Loop),Half,Full,20.85,21.10,20.28,20.53,uni,3.00,n,Aberdeen Street to Finish
M2d,Trail/Aberdeen to Finish,Full,Full,41.95,42.20,41.95,42.20,uni,3.00,n,Aberdeen Street to Finish