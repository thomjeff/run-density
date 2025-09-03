This is what I'm seeing for times for Half_fast and 10_slow in my Excel:
test	distance	Half_fast	10K_slow	Overtake
A1b		1.80 		7:46:27 AM	7:41:45 AM	FALSE

I also took your distance of 1.31km to confirm the times show no overtake:
test	distance	Half_fast	10K_slow	Overtake
A1b		1.31 		7:44:42 AM	7:35:50 AM	FALSE

These are the pace times my Excel is using:	
event		mm:ss	mins	
10K_fast	03:22 	3.37 
Half_fast 	03:35 	3.58 
Full_fast 	03:56 	3.93 
10K_slow	12:05 	12.08 
Half_slow	12:41 	12.68 
Full-slow	08:31 	8.52 

So I'm questioning your A1b results.

1. Please confirm my timings above are correct.
2. If correct, why are yours incorrect and showing overtake at 1.31km?


Results table for race named: 10K
Place
Click on any of the columns headers to apply sorting
No.
Click on any of the columns headers to apply sorting
Name
Click on any of the columns headers to apply sorting
City
Click on any of the columns headers to apply sorting
Prov
Click on any of the columns headers to apply sorting
Country
Click on any of the columns headers to apply sorting
Div place
Click on any of the columns headers to apply sorting
Div
Click on any of the columns headers to apply sorting
Gun Time
Click on any of the columns headers to apply sorting
Chip time
Click on any of the columns headers to apply sorting
Pace
Click on any of the columns headers to apply sorting

Place	Bib		Name		City		Div Place	Div		Gun Time 	Chip Time 	Pace
530		4729	E. O'Toole	Dartmouth	45 / 65		F5059	1:19:12		1:02:49		6:17


On the 4 Half Runners, the reason runner_id = 1621 isn't included is because of that runner's start_offset = 3s?
event	runner_id	pace 			distance start_offset
Half	1618		3.583333333		21.1		0
Half	1619		3.7				21.1		3
Half	1620		3.8				21.1		0
Half	1621		3.816666667		21.1		3
Half	1622		3.816666667		21.1		1


A1c
Can we dih into the results a bit? I was exepecting an ovetake at 2.36km:
test				distance	Half_fast	10K_slow	Overtake
A1b - Excel Calc	2.36 		7:48:27 AM	7:48:31 AM	TRUE

The app is reporting one at 1.8km, the start of the zone:
test				distance	Half_fast	10K_slow	Overtake
A1b - App (dist)	1.80 		7:46:27 AM	7:41:45 AM	FALSE

I guess it makes sense there will be an overtake at the start of A1c given one exist in A1b.

Can you help me understand the almost 5-minute gap between 07:46 Half_fast and 07:41 10K_slow using my simple Excel calculations -- that do not factor in start_offset. In A1b, the difference between my simple Excel and the app. was the offset. Can it be the explanation behind this almost 5-minute gap?

These are the pace times my Excel is using:	
event		mm:ss	mins	
10K_fast	03:22 	3.37 
Half_fast 	03:35 	3.58 
Full_fast 	03:56 	3.93 
10K_slow	12:05 	12.08 
Half_slow	12:41 	12.68 
Full-slow	08:31 	8.52 



On B1, my simple Excel is showing an overtake at 3.89km:
seg_id			distance	10K_fast	Full_slow	Overtake
B1 - Excel		3.89 		7:33:06 AM	7:33:08 AM	TRUE

The app is reporting at 3.53km, but there is almost a 2-minute difference between 10K_fast (07:31:53) and Full_slow (07:30:04)
seg_id			distance	10K_fast	Full_slow	Overtake
B1 - App		3.53 		7:31:53 AM	7:30:04 AM	FALSE

Does start_offset explain the difference?


"Significant" - enough to warrant race organizer attention (>20%)
"Meaningful" - indicates real interaction patterns (>15%)
"Notable" - worth planning for in race management (>5%)

The percentage would be evaluated against eventA and eventB and report out like this: "Percentage Overtake: 8.7% 10K (Notable), 20.9% Full (Significant)"

---------------

Let's tackle F1 first and I'll offer up my theory of what it is so high:

The results show Overtaking 10K: 487/618 (78.8%) and Overtaking Half: 911/912 (99.9%) with the 10K starting 20-minutes earlier (07:20, 440) than the Half (07:40, 460). Given these two being true,

1. The 131 10K *NOT* included in the overtake are the fastest runners (including the start_offset as a factor). I'd like confirmation for these 131 -- maybe their exit time from F1 is earlier than the first Half runner entry?
2. The 1 Half *NOT* included in the overtake is the slowest Half runner (including start_offset) and this runner must be really slow or has a massive start_offset. Who is this runner and are they not included because of a massive offset like runner_Id = 1529?
3. F1 is a merge and this is an excellent example of two fields of runners (eventA=10K, eventB=Half) merging at Friel Street (start of the segment) and then continuing to F2 and F3 segment (all running in same direction)
4. The count for half is so high because they started 20-minutes later than the 10K, plus took time to run the first 2.7km on segments A1a, A1b, A1c, where the Half is paired with 10K
5. We saw an overlap in A1b with 1 10K runner and 4 Half runners involved in overtakes. Key Runner: ID 1529 (10K, 6.28 min/km, 983s start offset). I'd be curious to know when runner_id = 1529, who must be in the 487 count, experinced a convergence. I'd expect late as this runner would need to run 2.7 to 5.8km (B1 and C1 segments) before being included in a F1 overtake.
6. Conversely, 1529 could be one of the 131 *NOT* included because of their start_offset
7. I'd be interested in seeing entry/exit time summary to better understand the high percentages. 

What are your thoughts? 


F2 Analysis:
1. Interesting the number of 10K being overtaken in F2 (n=110) is much lower than F1. Given the entry times for the 10K and Full, I'm expecting these to be the slower 10K and fast Full. 
2. I'd be interested in know if the C1 Full (n=77) appear in the F1 Full (n=126). I'd expect the answer to be yes. 
3. It makes sense the number of Full would increase from C1 to F1 as there is more distance covered and more opportunity for Full runners to overtake more 10K runners?
4. The number of 10K in F2 (n=110) is down signficantly from F1 (n=487). I assume this is because the slower 10Ks have not made it through F1 by the time the faster Fulls have -- i.e.: the fast Fulls continue to extend the gap between themselves and the 10K over F1 going into F2. Does this make sense as an explanation?
5. Is 1529 included in the F2 overtakes? It says False and then two lines later it says 1529 overlaps with temporal window. Explain.

🏷️ F2 - Friel to Station Rd. (shared path)
   Flow Type: merge
   Events: 10K vs Full
   Range 10K: 5.8km to 8.1km
   Range Full: 16.35km to 18.65km
   Total 10K: 618 runners
   Total Full: 368 runners
   ✅ Convergence Point: 5.8km
   👥 Overtaking 10K: 110/618 (17.8%) 
   👥 Overtaking Full: 126/368 (34.2%)


🔍 F2 DEEP DIVE ANALYSIS (COMPLETED)
============================================================
10K runners involved: 110/618 (17.8%)
Full runners involved: 126/368 (34.2%)

🔍 4. ENTRY/EXIT TIME SUMMARY (FIXED):
--------------------------------------------------
* I edited this and it is in a revised list of enhancements.
10K Entry/Exit:
  First: 07:39:31 07:47:16
  Last:  08:30:26 08:58:14
Full Entry/Exit:
  First: 08:04:19 08:13:22
  Last:  09:21:01 09:40:37  
 

🔍 6. OVERLAP WINDOW ANALYSIS:
--------------------------------------------------
Overlap Start: 08:04:19
Overlap End: 08:58:14
Overlap Duration: 53.9 minutes

🔍 7. RUNNER 1529 TIMING ANALYSIS:
--------------------------------------------------
Runner 1529: pace 6.28, offset 983s
  Entry to F2: 08:12:49
  Exit from F2: 08:27:16
  Included in F2 overtakes: False
  Overlap window: 08:04:19 to 08:58:14
  ✅ Runner 1529 overlaps with the temporal window


Your Analysis Validation:
1. ✅ Slower 10K vs Fast Full Pattern:
Your expectation is correct - the 110 10K runners in F2 should be the slower ones, and the 126 Full runners should be the faster ones.
2. �� C1 Full vs F2 Full Overlap Investigation:
Let me check if the C1 Full runners (n=77) appear in F2 Full runners (n=126).
3. ✅ Distance/Opportunity Logic:
Yes, that makes perfect sense - more distance covered = more opportunity for Full runners to catch 10K runners.
4. ✅ Gap Extension Explanation:
Absolutely correct! Fast Full runners extend their lead over slower 10K runners from F1 to F2, reducing the number of 10K runners available for overtakes.
5. �� Runner 1529 Discrepancy:
This is the key issue - let me investigate why 1529 shows "overlaps with temporal window" but "Included in F2 overtakes: False".
Let me run the investigation:


---
# F3 Analysis
1. I'm not surprised to see the lower counts for Full (F3 = 31, F2 = 126) as I guess it is the Half are coming into this segment at 2.7km and starting at 08:06 when the first Full arrives, meaning only the fastest Fulls will overtake. (07:40 start to 08:06 first full entering).
2. Are the Full in F3 (n=31) also in F2 (n=126) with the 10K? I don't think this is a safe assumption even though F3 is a continuation of F2. What is important to remember is F3 only counts overtakes when Half runners arrive in the same time window as the Full. This window has (most likely has) a different entry/exit than F2. 
3. Not sure what this error is about:

	<string>:81: SettingWithCopyWarning: 
	A value is trying to be set on a copy of a slice from a DataFrame.
	Try using .loc[row_indexer,col_indexer] = value instead
	See the caveats in the documentation: https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#returning-a-view-versus-a-copy

---

🏷️ F3 - Friel to Station Rd. (shared path)
   Flow Type: merge
   Events: Half vs Full
   Range Half: 2.7km to 5.0km
   Range Full: 16.35km to 18.65km
   Total Half: 912 runners
   Total Full: 368 runners
   ✅ Convergence Point: 2.7km
   📊 Conflict Zone: 2.7km to 2.75km
   👥 Overtaking Half: 42/912 (4.6%)
   👥 Overtaking Full: 31/368 (8.4%)
   🔄 Total Interactions: 73


   🔍 F3 DEEP DIVE ANALYSIS
============================================================
Segment: F3 - Friel to Station Rd. (shared path)
Events: Half vs Full
Range A (Half): 2.7km to 5.0km
Range B (Full): 16.35km to 18.65km

📊 F3 OVERTAKE ANALYSIS:
Half runners involved: 42/912 (4.6%)
Full runners involved: 31/368 (8.4%)

🔍 1. HALF RUNNERS NOT INCLUDED:
--------------------------------------------------
Count: 870 runners
Fastest 5 Half runners NOT included:
  Runner 1618: pace 3.58, offset 0s, exit 07:57:54
  Runner 1619: pace 3.70, offset 3s, exit 07:58:33
  Runner 1620: pace 3.80, offset 0s, exit 07:59:00
  Runner 1622: pace 3.82, offset 1s, exit 07:59:06
  Runner 1621: pace 3.82, offset 3s, exit 07:59:08

🔍 2. FULL RUNNERS NOT INCLUDED:
--------------------------------------------------
Count: 337 runners
First 5 Full runners NOT included:
  Runner 2541: pace 4.07, offset 0s, entry 08:06:29
  Runner 2540: pace 4.07, offset 3s, entry 08:06:32
  Runner 2542: pace 4.07, offset 4s, entry 08:06:33
  Runner 2543: pace 4.08, offset 0s, entry 08:06:45
  Runner 2544: pace 4.08, offset 1s, entry 08:06:46

🔍 3. ENTRY/EXIT TIME SUMMARY:
--------------------------------------------------
Half Entry Times:
  First: 07:49:40
  Last:  08:16:02
Full Entry Times:
  First: 08:04:19
  Last:  09:21:01

🔍 4. OVERLAP WINDOW ANALYSIS:
--------------------------------------------------
Overlap Start: 08:04:19
Overlap End: 08:45:12
Overlap Duration: 40.9 minutes

🔍 5. SAMPLE RUNNERS INVOLVED IN OVERTAKES:
--------------------------------------------------
Half runners involved (first 5):
  Runner 2481: pace 8.23, offset 108s, entry 08:04:01
  Runner 2482: pace 8.23, offset 119s, entry 08:04:12
  Runner 2486: pace 8.28, offset 102s, entry 08:04:03
  Runner 2487: pace 8.28, offset 110s, entry 08:04:11
  Runner 2491: pace 8.32, offset 105s, entry 08:04:12

Full runners involved (first 5):
  Runner 2560: pace 4.28, offset 10s, entry 08:10:11
  Runner 2562: pace 4.32, offset 4s, entry 08:10:38
  Runner 2563: pace 4.33, offset 4s, entry 08:10:54
  Runner 2564: pace 4.33, offset 22s, entry 08:11:12
  Runner 2565: pace 4.38, offset 10s, entry 08:11:50
