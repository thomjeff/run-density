
## **🎯 RECOMMENDED TASK START FORMAT:**

```
@Pre-task safeguards.md

Complete the following: [your task description]
```

## **📝 EXAMPLES:**

### **For Debugging Tasks:**
```
@Pre-task safeguards.md

Complete the following: Debug the flow analysis convergence detection issue where A2 segment is not showing expected overtaking results.
```

### **For New Features:**
```
@Pre-task safeguards.md

Complete the following: Add a new API endpoint for generating PDF reports from the existing markdown reports.
```

### **For Code Changes:**
```
@Pre-task safeguards.md

Complete the following: Fix the hardcoded values in the overlap calculation module and ensure all tolerance values come from constants.py.
```

### **For Testing Tasks:**
```
@Pre-task safeguards.md

Complete the following: Run comprehensive end-to-end tests and validate that all reports generate correctly with the current codebase.
```

## **✅ WHY THIS WORKS:**

1. **`@Pre-task safeguards.md`** - Automatically loads the guardrails document
2. **"Complete the following:"** - Clear, actionable language
3. **Specific task description** - Gives me clear direction

## **🚀 WHAT HAPPENS NEXT:**

When you use this format, I will:

1. **Reference the three core documents** (CRITICAL_CONFIGURATION.md, Application Fundamentals.md, Application Architecture.md)
2. **Confirm understanding** of the critical rules
3. **Follow the mandatory testing sequence**
4. **Meet the success criteria**

This ensures **100% compliance** with all established principles and prevents regression of the critical issues we've already solved! 🎯