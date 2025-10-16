# Data Quality Investigation: Missing 10K Runners in A1 Bins

## 🔍 **Issue:**
10K runners are not appearing in A1 segment bins at their start time (07:20), showing density = 0.0 instead of expected values.

## 📊 **Data Verification:**

### **10K Runners Exist:**
- ✅ Total 10K runners: 618
- ✅ Pace range: 3.37 - 12.08 min/km
- ✅ Start offset range: 0 - 983 seconds (0 - 16.38 minutes)

### **A1 Segment Configuration:**
- ✅ 10K uses A1: 0.0km to 0.9km
- ✅ Half uses A1: 0.0km to 0.9km
- ✅ Full uses A1: 0.0km to 0.9km
- ✅ Width: 5.0m

### **Expected Timing:**
- **10K start time:** 07:20 (440 minutes from midnight)
- **Fastest 10K reaches 0.2km:** 07:20:40 (40 seconds after start)
- **Slowest 10K reaches 0.2km:** 07:38 (18 minutes after start)

**Expected:** 10K runners should appear in A1 bins from 07:20 onwards

---

## ❌ **Actual Results:**

### **A1 Bins at 07:20-07:22 (10K start time):**
```
bin_id          start_km  end_km  t_start              t_end                density
A1:0.000-0.200  0.0       0.2     2025-10-15 07:20:00  2025-10-15 07:22:00  0.0
A1:0.200-0.400  0.2       0.4     2025-10-15 07:20:00  2025-10-15 07:22:00  0.0
A1:0.400-0.600  0.4       0.6     2025-10-15 07:20:00  2025-10-15 07:22:00  0.0
A1:0.600-0.800  0.6       0.8     2025-10-15 07:20:00  2025-10-15 07:22:00  0.0
A1:0.800-1.000  0.8       1.0     2025-10-15 07:20:00  2025-10-15 07:22:00  0.0
```

**All bins show density = 0.0 at 10K start time!**

### **A1 Time Window Pattern:**
```
Time Window              Max Density  Notes
07:00-07:02             0.199        Full start (07:00) - has density
07:02-07:04             0.182        Full runners present
07:04-07:06             0.157        Full runners present
...
07:16-07:18             0.013        Full runners thinning out
07:18-07:20             0.000        Gap before 10K start
07:20-07:22             0.000        10K start - MISSING!
07:22-07:24             0.000        10K should be here - MISSING!
...
07:40-07:42             0.254        Half start (07:40) - has density
```

---

## 🔍 **Possible Root Causes:**

### **1. Runner Mapping Logic Issue:**
The vectorized `build_runner_window_mapping()` function might have a bug in:
- Time window midpoint calculation
- Runner position calculation at time window midpoint
- Event start time handling for 10K

### **2. Time Window Alignment:**
- Time windows are 2-minute intervals (07:20-07:22)
- Window midpoint: 07:21
- 10K starts at 07:20
- At 07:21 (1 minute after start), fastest 10K runner would be at ~0.06km
- This SHOULD be captured in the 0.0-0.2km bin

### **3. Start Offset Handling:**
- 10K runners have start_offset values (0-983 seconds)
- These are added to the event start time
- Possible issue: start_offset might not be applied correctly for 10K

---

## 🧪 **Debug Steps for ChatGPT:**

### **Check 1: Verify runner mapping for 10K at 07:21**
```python
# For 10K event at t=07:21 (1 minute after start)
# Expected: Some 10K runners should be in A1 (0-0.9km)

event = '10K'
t_mid_sec = (7 * 3600) + (21 * 60)  # 07:21 in seconds from midnight
start_time_sec = 440 * 60  # 07:20 in seconds

# For a runner with pace=5 min/km, start_offset=0:
# - Runner starts at: 07:20:00
# - At 07:21:00 (60 seconds later): position = 60s / (5*60 s/km) = 0.2km
# - Should be in A1 (0-0.9km) ✅

# For a runner with pace=10 min/km, start_offset=0:
# - Runner starts at: 07:20:00
# - At 07:21:00 (60 seconds later): position = 60s / (10*60 s/km) = 0.1km
# - Should be in A1 (0-0.9km) ✅
```

### **Check 2: Review build_runner_window_mapping() logic**
Look at `app/density_report.py` line ~2220-2324:
- Is event start time correctly converted? (440 minutes → seconds)
- Is runner position calculated correctly?
- Is the segment range check working? (0 <= runner_km <= 0.9)

### **Check 3: Verify bins_accumulator receives runners**
The mapping should have entries like:
```python
mapping['A1'][window_index] = {
    "pos_m": np.array([50, 100, 150, ...]),  # Runner positions in meters
    "speed_mps": np.array([2.5, 2.0, 1.8, ...])  # Runner speeds
}
```

If the arrays are empty for 10K time windows, the bug is in `build_runner_window_mapping()`.

---

## 💡 **Hypothesis:**

The vectorized runner mapping function might have an issue with:
1. **Event filtering:** 10K runners might not be selected correctly
2. **Time calculation:** Window midpoint or runner timing might be off
3. **Segment range check:** The `(runner_abs_km >= from_km) & (runner_abs_km <= to_km)` check might be failing

**Most likely:** A timing calculation bug where 10K runners are calculated to be at position 0 or negative at 07:21, causing them to fail the segment range check.

---

## 🎯 **Recommended Investigation:**

1. Add debug logging to `build_runner_window_mapping()` for 10K event
2. Print runner positions calculated for A1 at 07:21 window
3. Check if any 10K runners pass the segment range filter
4. Verify the vectorized calculations match the expected logic

---

**This is a data quality issue that needs to be resolved before proceeding with Issue #237 frontend work.**

**Files for ChatGPT:**
- `app/density_report.py` (lines 2177-2324) - `build_runner_window_mapping()` function
- `reports/2025-10-15/bins_readable.csv` - Shows zero density at 10K start
- `data/runners.csv` - 618 10K runners with pace and start_offset data
- `data/segments.csv` - A1 segment configuration

