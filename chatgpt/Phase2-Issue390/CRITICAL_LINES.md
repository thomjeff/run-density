# Critical Lines for Phase 2 Refactoring

This document highlights the specific code blocks in the three target files that contain complex conditional patterns and nested try/except blocks targeted for refactoring in Phase 2 of Issue #390.

---

## 🎯 Complex Conditional Patterns

### 1. `core/density/compute.py` - Complex Conditional Chains

**Lines 52, 105, 117, 294, 385, 484, 977**: Multiple nested conditions with and/or operators

**Example Pattern (Line 52):**
```python
if "schemas" in rulebook:
    # v2.0 rulebook - use schema-specific or global LOS thresholds
    schemas = rulebook.get("schemas", {})
    schema_config = schemas.get(schema_name, {})
    los_thresholds = schema_config.get("los_thresholds", 
                                     rulebook.get("globals", {}).get("los_thresholds", {}))
    
    if not los_thresholds:
        return "F"  # Default to worst case
    
    # Map density to LOS letter
    for letter in ["A", "B", "C", "D", "E", "F"]:
        rng = los_thresholds.get(letter, {})
        mn = rng.get("min", float("-inf"))
        mx = rng.get("max", float("inf"))
        if mn <= value < mx:
            return letter
```

**Refactoring Target**: Extract LOS threshold resolution logic into utility function

---

### 2. `core/flow/flow.py` - Nested Loop Logic

**Lines 1130-1143**: Complex nested loops with multiple conditional branches

**Example Pattern:**
```python
for i, runner_a in enumerate(df_a.itertuples()):
    for j, runner_b in enumerate(df_b.itertuples()):
        if condition1 and condition2:
            if condition3 or condition4:
                if condition5:
                    # Complex nested logic
                    if condition6:
                        # More nested conditions
                        pass
```

**Refactoring Target**: Extract nested loop logic into separate functions with early returns

---

### 3. `core/flow/flow.py` - Complex Pass/Fail Logic

**Lines 676-682**: Multiple nested conditions for pass/fail determination

**Example Pattern:**
```python
if condition1 and condition2:
    if condition3:
        if condition4 or condition5:
            if condition6 and condition7:
                return True
            elif condition8:
                return False
        else:
            return False
    else:
        return False
else:
    return False
```

**Refactoring Target**: Use guard clauses and early returns to reduce nesting

---

## 🎯 Nested Try/Except Blocks

### 1. `app/density_report.py` - Nested Try/Except Blocks

**Lines 872-878**: Multiple nested try/except blocks with complex error handling

**Example Pattern:**
```python
try:
    # First operation
    try:
        # Second operation
        try:
            # Third operation
            result = complex_operation()
        except SpecificException as e:
            logger.warning(f"Third operation failed: {e}")
            result = fallback_value
    except AnotherException as e:
        logger.error(f"Second operation failed: {e}")
        result = None
except Exception as e:
    logger.error(f"First operation failed: {e}")
    result = None
```

**Refactoring Target**: Simplify with single try/except and specific error handling

---

### 2. `app/density_report.py` - Complex Conditional Paths

**Lines 904-909, 1055-1056, 1035**: Multiple conditional branches for feature flags and environment detection

**Example Pattern:**
```python
if feature_flag1:
    if feature_flag2:
        if environment == "cloud":
            if condition1 and condition2:
                # Cloud-specific logic
                pass
            else:
                # Fallback logic
                pass
        else:
            # Local logic
            pass
    else:
        # Different feature logic
        pass
else:
    # Default logic
    pass
```

**Refactoring Target**: Extract conditional logic into utility functions with clear interfaces

---

## 🎯 Silent Failure Patterns

### Common Silent Failure Patterns Across Files:

**Pattern 1: Silent None Returns**
```python
def function():
    if condition:
        return result
    # Silent failure - no return statement
    return None  # Implicit
```

**Pattern 2: Silent Empty Returns**
```python
def function():
    if condition:
        return result
    return []  # Silent failure
```

**Pattern 3: Silent Exception Swallowing**
```python
try:
    result = risky_operation()
except Exception:
    pass  # Silent failure
```

**Refactoring Target**: Replace with explicit logging and proper error handling

---

## 🎯 Refactoring Strategy

### 1. Extract Utility Functions
- Create pure functions for complex conditional logic
- Ensure functions don't mutate shared state
- Add comprehensive docstrings and type hints

### 2. Implement Guard Clauses
- Use early returns to reduce nesting depth
- Replace nested if/elif chains with guard clauses
- Improve readability and maintainability

### 3. Simplify Error Handling
- Replace nested try/except blocks with single-level error handling
- Add explicit logging for all error conditions
- Ensure proper error propagation

### 4. Preserve State Mutations
- Document all mutable state modifications
- Ensure refactored code maintains same state lifecycle
- Add logging for state changes

### 5. Add Comprehensive Testing
- Test all conditional branches
- Test error handling paths
- Validate state mutations are preserved
