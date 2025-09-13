# 8. Troubleshooting

## 🚨 **Common Issues and Solutions**

This section covers the most frequently encountered issues and their solutions, organized by category for easy reference.

## 🔧 **Environment and Setup Issues**

### **ModuleNotFoundError: No module named 'fastapi'**

**Symptoms:**
- Python import errors when running commands
- Missing dependency errors
- Command not found errors

**Root Cause:**
Virtual environment not activated

**Solution:**
```bash
# Always activate virtual environment first
source .venv/bin/activate

# Then run your commands
python3 -m app.end_to_end_testing
```

**Prevention:**
- Always activate virtual environment before running Python commands
- Check for virtual environment activation in scripts
- Use consistent environment setup procedures

### **Permission Denied Errors**

**Symptoms:**
- `zsh: permission denied: app/`
- `zsh: permission denied: reports/`
- File access errors

**Root Cause:**
Shell interpretation errors with complex commands

**Solution:**
```bash
# Use simple commands
gh issue close 142

# For complex content, write to file first
echo "Complex content" > temp_file.txt
gh issue comment 142 --body-file temp_file.txt
```

**Prevention:**
- Use simple, single-line commands
- Write complex content to files first
- Avoid special characters in shell commands

## 📊 **Data and Analysis Issues**

### **Zero Overtaking Counts in Flow Analysis**

**Symptoms:**
- All overtaking counts show 0
- No convergence points identified
- Empty analysis results

**Root Cause:**
Time unit inconsistencies or data filtering issues

**Solution:**
1. **Check Time Units:**
   ```python
   # Ensure consistent time conversion
   start_a = start_times.get(event_a, 0) * 60.0  # Convert to seconds
   start_b = start_times.get(event_b, 0) * 60.0  # Convert to seconds
   ```

2. **Verify Data Filtering:**
   ```python
   # Check if filtered datasets are empty
   print(f"Filtered runners A: {len(runners_a)}")
   print(f"Filtered runners B: {len(runners_b)}")
   ```

3. **Validate Algorithm Parameters:**
   - Check `minOverlapDuration` settings
   - Verify `conflictLengthM` values
   - Ensure segment boundaries are correct

**Prevention:**
- Always convert time units consistently
- Validate data filtering logic
- Test with known good data first

### **Unrealistic Density Values**

**Symptoms:**
- Density values outside expected range (0-10 runners/m²)
- Negative density values
- Extremely high density values

**Root Cause:**
Incorrect area calculations or data quality issues

**Solution:**
1. **Check Area Calculations:**
   ```python
   # Verify segment area calculations
   segment_length = to_km - from_km
   segment_area = segment_length * width_m
   ```

2. **Validate Data Quality:**
   - Check for missing or invalid pace data
   - Verify segment boundary definitions
   - Ensure consistent units

3. **Review Algorithm Parameters:**
   - Check `stepKm` settings
   - Verify `timeWindow` values
   - Ensure proper data filtering

**Prevention:**
- Validate input data before analysis
- Use consistent units throughout
- Test with known good datasets

### **Missing Report Content**

**Symptoms:**
- Empty report files
- Missing markdown content
- Incomplete CSV data

**Root Cause:**
File I/O issues or incomplete analysis

**Solution:**
1. **Check File Permissions:**
   ```bash
   # Ensure write permissions
   chmod 755 reports/
   chmod 644 reports/*.md
   ```

2. **Verify Analysis Completion:**
   - Check for analysis errors in logs
   - Ensure all required data is present
   - Validate report generation logic

3. **Use API Endpoints:**
   - Generate reports via API endpoints
   - Check for API errors
   - Verify response content

**Prevention:**
- Always check file permissions
- Validate analysis completion
- Use automated testing scripts

## 🌐 **API and Network Issues**

### **500 Internal Server Error**

**Symptoms:**
- HTTP 500 status codes
- Server error messages
- Analysis failures

**Root Cause:**
Server-side errors in analysis or data processing

**Solution:**
1. **Check Server Logs:**
   ```bash
   # View Cloud Run logs
   gcloud logging read "resource.type=cloud_run_revision" --limit=50
   ```

2. **Validate Request Data:**
   - Check request parameters
   - Verify data file paths
   - Ensure proper data format

3. **Test with Simple Requests:**
   ```bash
   # Test health endpoint first
   curl -X GET "https://run-density-ln4r3sfkha-uc.a.run.app/health"
   ```

**Prevention:**
- Always validate input data
- Use proper error handling
- Test with known good data

### **404 Not Found Errors**

**Symptoms:**
- HTTP 404 status codes
- File not found messages
- Missing resource errors

**Root Cause:**
Incorrect file paths or missing resources

**Solution:**
1. **Check File Paths:**
   - Verify file exists in correct location
   - Check file naming conventions
   - Ensure proper path formatting

2. **Validate Resource Availability:**
   - Check if files are accessible
   - Verify file permissions
   - Ensure proper file structure

**Prevention:**
- Use consistent file naming
- Validate file paths before use
- Check file availability

### **Timeout Errors**

**Symptoms:**
- Request timeouts
- Analysis incomplete
- Cloud Run timeouts

**Root Cause:**
Analysis taking too long for Cloud Run limits

**Solution:**
1. **Use Local Analysis:**
   ```bash
   # Run full analysis locally
   python3 -m app.end_to_end_testing
   ```

2. **Optimize Analysis Parameters:**
   - Reduce dataset size
   - Increase time windows
   - Simplify analysis complexity

3. **Use Cloud Run E2E Mode:**
   ```bash
   # Use lightweight Cloud Run testing
   TEST_CLOUD_RUN=true python3 -m app.end_to_end_testing
   ```

**Prevention:**
- Test locally before Cloud Run
- Use appropriate analysis parameters
- Consider Cloud Run resource limits

## 🔍 **Debugging Techniques**

### **Enable Debug Logging**

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Add debug statements
print(f"Debug: start_a = {start_a}, start_b = {start_b}")
print(f"Debug: runners_a count = {len(runners_a)}")
print(f"Debug: segment boundaries = {from_km} to {to_km}")
```

### **Validate Data at Each Step**

```python
# Check data at each processing step
print(f"Step 1: Loaded {len(runners)} runners")
print(f"Step 2: Filtered to {len(filtered_runners)} runners")
print(f"Step 3: Found {len(overlaps)} overlaps")
print(f"Step 4: Calculated {len(overtakes)} overtakes")
```

### **Use Test Data**

```python
# Create simple test data
test_runners = [
    {"runner_id": 1, "event": "Half", "pace_min_per_km": 5.0},
    {"runner_id": 2, "event": "10K", "pace_min_per_km": 4.0}
]
test_segments = [
    {"seg_id": "F1", "from_km": 5.0, "to_km": 8.0, "flow_type": "parallel"}
]
```

## 📋 **Performance Optimization**

### **Large Dataset Issues**

**Symptoms:**
- Slow analysis performance
- Memory usage issues
- Timeout errors

**Solution:**
1. **Optimize Data Processing:**
   - Use pandas vectorized operations
   - Process data in chunks
   - Filter data early in pipeline

2. **Adjust Analysis Parameters:**
   - Increase time windows
   - Reduce segment granularity
   - Use sampling for large datasets

3. **Use Local Processing:**
   - Run analysis locally with full resources
   - Use Cloud Run only for final validation

### **Memory Issues**

**Symptoms:**
- Out of memory errors
- Slow performance
- Analysis failures

**Solution:**
1. **Optimize Data Structures:**
   - Use appropriate data types
   - Remove unnecessary columns
   - Process data incrementally

2. **Monitor Resource Usage:**
   - Check memory usage during analysis
   - Optimize algorithm efficiency
   - Use streaming processing

## 🆘 **Getting Help**

### **Check Documentation**
- Review this troubleshooting guide
- Check API reference documentation
- Look for similar issues in GitHub issues

### **Use Automated Tools**
- Run automated testing scripts
- Use built-in validation tools
- Check for common configuration issues

### **Report Issues**
- Create detailed GitHub issues
- Include error messages and logs
- Provide steps to reproduce
- Include sample data if possible

### **Community Support**
- Check GitHub discussions
- Review existing issues
- Ask for help with specific problems

## 🔍 **F1 Segment Troubleshooting**

### **Understanding F1 Discrepancy Warnings**

If you see warnings like this in your flow analysis:

```
WARNING: F1 Half vs 10K DISCREPANCY DETECTED!
  Current calculation: 840 (92.1%), 494 (79.9%)
  Validation results:  694 (76.1%), 451 (73.0%)
  Using validation results.
```

**This is normal and expected behavior for F1 segment analysis.**

#### **Why Discrepancies Occur**
- **F1 complexity**: Three-way merge with high interaction rates
- **Temporal binning**: Standard calculation may over-count overlaps
- **Per-runner validation**: More accurate individual tracking
- **Conservative approach**: System uses validation results for reliability

#### **What This Means**
- **Validation results are more accurate** for F1 segment
- **System automatically corrects** the calculation
- **No action required** - this is working as designed
- **Results are reliable** for race management decisions

### **Flow-Audit Troubleshooting**

#### **When Flow-Audit Fails**
- **Check segment ID**: Ensure segment exists in segments.csv
- **Verify event names**: Use exact event names (Full, Half, 10K)
- **Validate data files**: Ensure pace and segments data are valid
- **Check parameters**: Verify minOverlapDuration and conflictLengthM

#### **Common Flow-Audit Issues**

**Issue**: "Segment not found"
- **Solution**: Verify segId exists in segments.csv
- **Check**: Use exact segment ID (e.g., "F1", not "f1")

**Issue**: "No convergence detected"
- **Solution**: Check if events actually overlap in time
- **Check**: Verify start times and segment boundaries

**Issue**: "Validation failed"
- **Solution**: This is normal for F1 - system uses main calculation
- **Check**: Review logs for specific validation errors

#### **Interpreting Flow-Audit Results**

**High overtaking percentages (>80%)**
- **Normal for F1**: Complex merge point with high interaction
- **Check validation**: Look for discrepancy warnings
- **Use validation results**: When available, these are more accurate

**Low overtaking percentages (<20%)**
- **Check timing**: Events may not overlap significantly
- **Verify data**: Ensure runner data covers the segment
- **Review parameters**: Adjust minOverlapDuration if needed

### **F1 Segment Best Practices**

#### **For Race Directors**
- **Trust validation results**: When discrepancies occur, validation is more accurate
- **Plan for complexity**: F1 requires special attention due to three-way merge
- **Monitor warnings**: Discrepancy warnings indicate complex interactions
- **Use conservative estimates**: Validation results are designed to be reliable

#### **For Technical Users**
- **Use Flow-Audit**: For detailed F1 analysis with validation
- **Expect discrepancies**: Normal behavior for complex segments
- **Review validation data**: Check per-runner analysis details
- **Compare methods**: Understand differences between calculation approaches

---

**Next**: [Metric Definitions](09-metric-definitions.md) - Detailed calculation formulas and methodology
