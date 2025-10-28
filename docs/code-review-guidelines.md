# Code Review Guidelines - Issue #390 Complexity Standards

## **COMPLEXITY STANDARDS CHECKLIST**

Before approving any PR, verify compliance with these complexity standards:

### ✅ **Function-Level Checks**
- [ ] **Function Length**: ≤ 50 lines per function
- [ ] **Cyclomatic Complexity**: ≤ 10 per function
- [ ] **Nesting Depth**: ≤ 4 levels of nesting
- [ ] **Single Responsibility**: One function, one purpose
- [ ] **Early Returns**: Guard clauses used to reduce nesting

### ✅ **Error Handling Checks**
- [ ] **Specific Exceptions**: No bare `except:` statements
- [ ] **Error Context**: Meaningful error messages with context
- [ ] **Logging**: Appropriate logging levels used
- [ ] **Failure Handling**: Graceful degradation or proper escalation

### ✅ **Code Structure Checks**
- [ ] **Conditional Chains**: ≤ 5 consecutive if/elif statements
- [ ] **Utility Functions**: Repeated patterns extracted to utilities
- [ ] **Import Organization**: Clean, organized imports
- [ ] **Constants Usage**: No hardcoded values, use `app/constants.py`

### ✅ **Pattern Compliance Checks**
- [ ] **Guard Clauses**: Early returns for error conditions
- [ ] **Data Validation**: Input validation at function boundaries
- [ ] **State Management**: Clear state transitions and lifecycle
- [ ] **Environment Detection**: Consistent environment detection patterns

## **COMMON VIOLATIONS AND FIXES**

### ❌ **Deep Nesting Violation**
```python
def process_data(data):
    if data:
        if data.get('type'):
            if data['type'] == 'important':
                if data.get('value'):
                    if data['value'] > 0:
                        return data['value'] * 2
    return 0
```

### ✅ **Fixed with Guard Clauses**
```python
def process_data(data):
    if not data or not data.get('type'):
        return 0
    if data['type'] != 'important':
        return 0
    if not data.get('value') or data['value'] <= 0:
        return 0
    return data['value'] * 2
```

### ❌ **Bare Exception Violation**
```python
try:
    risky_operation()
except:
    pass  # Silent failure
```

### ✅ **Fixed with Specific Exception**
```python
try:
    risky_operation()
except (ValueError, TypeError) as e:
    logger.error(f"Operation failed: {e}")
    raise
```

### ❌ **Long Function Violation**
```python
def analyze_segment(segment_data):
    # 60+ lines of mixed logic
    # Data validation
    # Processing
    # Error handling
    # Result formatting
    # Logging
    return result
```

### ✅ **Fixed with Utility Functions**
```python
def analyze_segment(segment_data):
    validated_data = _validate_segment_data(segment_data)
    processed_data = _process_segment_data(validated_data)
    result = _format_analysis_result(processed_data)
    _log_analysis_result(result)
    return result

def _validate_segment_data(data):
    # Focused validation logic
    pass

def _process_segment_data(data):
    # Focused processing logic
    pass

def _format_analysis_result(data):
    # Focused formatting logic
    pass

def _log_analysis_result(result):
    # Focused logging logic
    pass
```

## **ESCALATION PROCEDURES**

### **Complexity Violations**
1. **Minor Violations** (1-2 metrics exceeded):
   - Request refactoring before merge
   - Provide specific examples from Phases 1-3

2. **Major Violations** (3+ metrics exceeded):
   - Block merge until refactoring complete
   - Require architectural review
   - Consider breaking into smaller PRs

3. **Critical Violations** (Patterns from original audit):
   - Immediate architectural review required
   - Consider ChatGPT checkpoint
   - May require Phase 1-3 style refactoring

### **Review Process**
1. **Automated Checks**: CI must pass all complexity gates
2. **Manual Review**: Human reviewer checks compliance
3. **Architectural Review**: For complex changes or violations
4. **ChatGPT Checkpoint**: For high-risk refactoring

## **TOOLS AND COMMANDS**

### **Local Validation**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run complexity checks
radon cc . -nc -a
flake8 .

# Run custom checks
python scripts/check_function_length.py app/ core/
python scripts/check_nesting_depth.py app/ core/

# Run pre-commit hooks
pre-commit run --all-files
```

### **CI Validation**
```bash
# CI automatically runs:
radon cc . -nc -a --min B
flake8 .
python scripts/check_function_length.py $(git diff --name-only HEAD~1)
python scripts/check_nesting_depth.py $(git diff --name-only HEAD~1)
```

## **SUCCESS METRICS**

### **Immediate Success**
- [ ] All PRs pass complexity gates
- [ ] No new violations introduced
- [ ] Existing violations addressed

### **Long-term Success**
- [ ] Reduced maintenance burden
- [ ] Improved code readability
- [ ] Faster onboarding for new developers
- [ ] Fewer bugs from complex logic

## **REFERENCES**

- **Issue #390**: Complex Execution Flow audit and refactoring
- **Phases 1-3**: Successful refactoring examples
- **GUARDRAILS.md**: Updated with complexity standards
- **ChatGPT Review**: Architectural validation of standards
