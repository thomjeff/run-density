# 🚦 Analysis of Temporal-Flow vs Flow-Audit Discrepancies  
**Focus: Segments M1 (Half/10K) and F1 (Half/10K)**  

---

## ✅ Review of Cursor’s Hypothesis  

Cursor’s investigation is strong in several areas:  

1. **Pattern Recognition**  
   - Correctly identified that discrepancies are **not isolated to M1**, but systematically occur in **high-density overtaking segments** (M1, F1).  
   - Correctly noted that **low-overtake and zero-overtake segments match perfectly** (A2, A3, L1).  

2. **Quantification of Over-Counting**  
   - Showed that **Flow Runner consistently reports higher counts** than Main Analysis in dense segments.  
   - Crucially noted that the **magnitude of discrepancy scales with overtake density** (small offset in M1, large offset in F1).  

3. **Root Cause Hypothesis**  
   - Reasonably proposed **double-counting, binning mismatches, or stricter pass-criteria** as possible sources.  
   - Emphasized that the flaw likely appears when algorithms process **dense interactions**.  

**Verdict:** Cursor’s reasoning is sound in pattern identification and hypothesis framing. The next step is to sharpen diagnostic testing to isolate *which* mechanism (counting, binning, or criteria) drives the discrepancy.  

---

## 🔍 My Additions to the Diagnosis  

### 1. **Systematic vs Random Errors**  
   - The discrepancies **scale with overtaking density**, suggesting this is not random noise.  
   - If it were random, we’d expect mismatches in both low and high segments. Since low-density matches perfectly, the flaw likely lies in **how Flow Runner scales events under load**.  

### 2. **Likely Root Causes**  
   - **Double-counting at event boundaries:** When two overtakes occur within a small temporal window, Flow Runner may be logging both the *event* and a *state transition*.  
   - **Bin misalignment:** If Main Analysis and Flow Runner use slightly different **time windows or distance thresholds**, Flow Runner could inflate counts as density rises.  
   - **Order-of-operations difference:** If Main Analysis deduplicates first and Flow Runner deduplicates later (or not at all), Flow Runner will always over-count in dense areas.  

### 3. **Segment-Specific Signals**  
   - **M1 small discrepancy (3/1):** Suggests minimal boundary duplication.  
   - **F1 massive discrepancy (128/14):** Suggests sustained misalignment over many consecutive overtakes.  
   - Together, this supports the **binning misalignment hypothesis** more strongly than pure double-counting.  

---

## 🎯 Recommended Next Steps for Cursor  

To quickly get to a fix:  

1. **Boundary Overtake Audit**  
   - Extract raw overtake events for **M1 and F1 only**.  
   - Compare how many events occur within the **same temporal bin** between Main Analysis and Flow Runner.  
   - If Flow Runner shows multiple events inside a single Main Analysis bin, that’s evidence of **binning misalignment/double-counting**.  

2. **Consistency Check with Synthetic Data**  
   - Run both algorithms on a **synthetic low-density dataset** (manually constructed with controlled overtakes).  
   - Then run on a **synthetic high-density dataset** (stack overtakes artificially close together).  
   - If discrepancies emerge only in high-density synthetic tests, root cause confirmed.  

3. **Cross-Check Deduplication Stage**  
   - Verify whether Main Analysis performs **deduplication before aggregation** while Flow Runner does it **after** (or not at all).  
   - A single-line change in processing order could explain scaling discrepancies.  

4. **Set a Baseline with F1**  
   - Since F1 produces the largest discrepancy, use it as the **stress test case**.  
   - Once you fix F1 alignment, re-test M1 to confirm smaller discrepancies also disappear.  

---

## 📌 My Guidance to Cursor  

Cursor, your hypothesis is well-structured. The fastest way forward is:  

- Don’t broaden testing further yet — focus **only on F1 and M1** since they show the failure clearly.  
- Prioritize a **boundary-overlap audit** — this will immediately reveal whether the Flow Runner is double-counting within bins.  
- Use **synthetic stress tests** to isolate whether the discrepancy is binning vs deduplication.  
- Treat Main Analysis as the **baseline truth** unless proven otherwise.  

Once you prove whether it’s binning or deduplication, you’ll have a clean fix path.  
