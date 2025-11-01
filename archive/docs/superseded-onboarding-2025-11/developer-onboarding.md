# Developer Onboarding - Issue #390 Complexity Standards

## **SETUP INSTRUCTIONS**

### **1. Install Development Dependencies**

```bash
# Install development tools
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### **2. Configure Pre-commit Hooks**

```bash
# Install pre-commit hooks
pre-commit install

# Test hooks on all files
pre-commit run --all-files

# Test hooks on staged files only
pre-commit run
```

### **3. Verify Complexity Standards**

```bash
# Run all complexity checks
radon cc . -nc -a --min B
flake8 .
python scripts/check_function_length.py app/ core/
python scripts/check_nesting_depth.py app/ core/

# Run pre-commit hooks
pre-commit run --all-files
```

## **COMPLEXITY STANDARDS REFERENCE**

### **✅ Mandatory Standards**

| Standard | Threshold | Tool | Description |
|----------|-----------|------|-------------|
| **Nesting Depth** | ≤ 4 levels | Custom script | Prevent hard-to-read deep blocks |
| **Cyclomatic Complexity** | ≤ 10 | Radon | Encourage simple, testable functions |
| **Function Length** | ≤ 50 lines | Custom script | Encourage decomposition |
| **Conditional Chains** | ≤ 5 if/elif | Flake8 | Flag logic that could be abstracted |
| **Error Handling** | Specific exceptions | Flake8 | Avoid masking failures |

### **🔧 Common Patterns**

#### **Guard Clauses (Recommended)**
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

#### **Specific Exception Handling (Required)**
```python
try:
    risky_operation()
except (ValueError, TypeError) as e:
    logger.error(f"Operation failed: {e}")
    raise
```

#### **Utility Functions (Encouraged)**
```python
# Use utilities from app/utils/complexity_helpers.py
from app.utils.complexity_helpers import safe_get, validate_required_fields
from app.utils.error_handling import handle_specific_exceptions
```

## **DEVELOPMENT WORKFLOW**

### **1. Before Making Changes**
```bash
# Ensure you're on a feature branch
git checkout -b feature/your-feature-name

# Install pre-commit hooks
pre-commit install
```

### **2. During Development**
```bash
# Run complexity checks frequently
python scripts/check_function_length.py app/your_file.py
python scripts/check_nesting_depth.py app/your_file.py

# Run full checks before committing
pre-commit run --all-files
```

### **3. Before Committing**
```bash
# Ensure all checks pass
pre-commit run --all-files

# If checks fail, fix issues and re-run
pre-commit run --all-files
```

### **4. Before Pushing**
```bash
# Run E2E tests
python e2e.py --local

# Ensure all complexity standards are met
radon cc . -nc -a --min B
flake8 .
```

## **TROUBLESHOOTING**

### **Common Issues**

#### **Pre-commit Hooks Fail**
```bash
# Check specific hook
pre-commit run flake8 --all-files

# Skip hooks temporarily (not recommended)
git commit --no-verify -m "Your message"
```

#### **Complexity Violations**
```bash
# Check specific file
radon cc app/your_file.py -nc -a

# Check function length
python scripts/check_function_length.py app/your_file.py

# Check nesting depth
python scripts/check_nesting_depth.py app/your_file.py
```

#### **Import Errors**
```bash
# Ensure virtual environment is activated
source test_env/bin/activate

# Install missing dependencies
pip install -r requirements-dev.txt
```

### **Getting Help**

1. **Check GUARDRAILS.md** for detailed rules
2. **Review code-review-guidelines.md** for standards
3. **Look at Phases 1-3 examples** in `chatgpt/Phase4-Issue390/`
4. **Use utility functions** from `app/utils/`

## **BEST PRACTICES**

### **✅ Do**
- Use guard clauses for early returns
- Extract utility functions for repeated patterns
- Use specific exception types
- Keep functions focused and small
- Use the provided utility libraries

### **❌ Don't**
- Use bare `except:` statements
- Create functions longer than 50 lines
- Nest more than 4 levels deep
- Use more than 5 consecutive if/elif statements
- Hardcode values (use `app/constants.py`)

## **VALIDATION COMMANDS**

### **Quick Check**
```bash
# Run all complexity checks
make complexity-check
```

### **Full Validation**
```bash
# Run all checks and tests
make test-all
```

### **Pre-commit Test**
```bash
# Test pre-commit hooks
pre-commit run --all-files
```

## **SUCCESS CRITERIA**

Your setup is complete when:
- [ ] All complexity checks pass
- [ ] Pre-commit hooks are installed and working
- [ ] E2E tests run successfully
- [ ] You can commit without violations
- [ ] You understand the complexity standards

## **REFERENCES**

- **Issue #390**: Complex Execution Flow audit and refactoring
- **GUARDRAILS.md**: Updated with complexity standards
- **code-review-guidelines.md**: Detailed review checklist
- **Phases 1-3**: Successful refactoring examples
- **ChatGPT Review**: Architectural validation of standards
