# Issue #283 - Follow-up Questions for ChatGPT

## Question 1: Units Consistency (p/s vs p/min)

You mentioned:
> **The report shows Peak Rate in p/s.** Some pipelines and UI code use p/min. **SSOT must standardize units (recommend p/s)**, and the UI/report must both label accordingly.

**Questions:**

1. **Where specifically in the codebase is p/min used?** 
   - I need to know which modules/files to update during implementation.
   - Are there specific field names that indicate p/min vs p/s?

2. **Conversion strategy:**
   - Should SSOT always compute in p/s and let consumers convert if needed?
   - Or should SSOT store both and let consumers choose?
   - What's the recommended approach for backwards compatibility during migration?

3. **Field naming:**
   - Currently `bins.parquet` has a `rate` column. Is this p/s or p/min?
   - Should we rename to `rate_p_per_s` to be explicit?
   - Or add metadata/units field to the schema?

4. **CI unit check:**
   - What specifically should the CI gate check?
   - Compare rate values between report and artifacts with tolerance for rounding?
   - Verify unit labels in JSON/MD match?

## Question 2: Final Acceptance Checklist

You offered:
> Want me to drop a concise "Final Acceptance Checklist" in Issue #283 so the PR can be reviewed against it?

**Yes, please!** This would be extremely helpful for:
- Ensuring I implement all 7 clarifications correctly
- Providing clear PR review criteria
- Documenting Definition of Done for the issue

Could you provide:
1. A checklist of implementation tasks (tied to the 7 clarifications)
2. A checklist of verification/testing steps
3. Specific acceptance criteria for the PR review

---

**Context for ChatGPT:**

Current understanding of rate fields in codebase (from `bins.csv` inspection):
- `bins.parquet`/`bins.csv` has **TWO rate columns**:
  - `rate`: 5.528... (appears to be p/s)
  - `rate_per_m_per_min`: 66.340... (clearly p/m/min - larger values)
- Report shows "Peak Rate: X.XX p/s" in tables
- 13 files in `/app` reference rate units (found via grep)
- Need guidance on which field(s) should be canonical and how to handle both

---

**Ready to implement once these clarifications are provided!**

