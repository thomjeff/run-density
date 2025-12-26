# Contributing to Run-Density

**Version:** 1.0  
**Last Updated:** 2025-11-11  
**Architecture:** v1.8.4 (Post-Phase 2)

Thank you for your interest in contributing to Run-Density! This guide will help you get started with local development, testing, and contributing code.

---

## 📋 Quick Start

### Prerequisites

- **Docker** installed and running
- **Git** configured
- **GitHub** access to repository
- **Terminal** with bash/zsh

### Local Setup

```bash
# 1. Clone repository
git clone https://github.com/thomjeff/run-density.git
cd run-density

# 2. Start development container
make dev

# 3. Verify setup
make test         # Run smoke tests (< 5 seconds)
make e2e-local    # Run full E2E tests (~ 2-3 minutes)
make validate-output  # Verify output integrity

# 4. Access UI
open http://localhost:8080/dashboard
```

### Verify Everything Works

✅ **Success Criteria:**
- Docker container starts without errors
- UI loads at http://localhost:8080
- All smoke tests pass (`make test`)
- E2E tests complete successfully (`make e2e-local`)
- Validation passes (`make validate-output`)

---

## 💻 Development Workflow

### 1. Create a Branch

**Branch Naming Convention:**
```
###-feature-description    # For new features
###-bug-description        # For bug fixes
```

**Examples:**
- `467-output-validation`
- `470-fix-latest-json`
- `466-architecture-refinement`

**Always start from main:**
```bash
git checkout main
git pull origin main
git checkout -b ###-your-feature
```

---

### 2. Make Changes

**Key Directories:**
- `app/` - Application code (hot-reload enabled)
- `data/` - Input CSV files
- `config/` - YAML configuration
- `runflow/` - All run outputs (UUID-based)
- `docs/` - Documentation
- `app/tests/` - Validation and test scripts

**Output Structure:**
All outputs go to `runflow/<uuid>/`:
- `reports/` - Markdown and CSV reports
- `bins/` - Bin-level analysis data
- `ui/` - Frontend artifacts and heatmaps
- `metadata.json` - Run metadata with verification status

📖 **See:** `docs/architecture/output.md` for complete structure

---

### 3. Test Your Changes

**Required Before Committing:**

```bash
# 1. Smoke tests (< 5 seconds)
make test

# 2. Full E2E tests (~ 2-3 minutes)
make e2e-local

# 3. Output validation
make validate-output

# 4. Check logs for errors
docker logs run-density-dev | grep -iE "error|failed"
```

**All tests must pass** before committing.

---

### 4. Commit Your Changes

**Commit Message Format:**
```
<type>: <description> (<scope>)

<optional body>

<optional footer>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `chore:` - Maintenance (configs, deps)
- `test:` - Adding or updating tests
- `refactor:` - Code restructuring

**Examples:**
```bash
git commit -m "feat: add output validation framework (Issue #467)"
git commit -m "fix: correct heatmap path resolution (Issue #470)"
git commit -m "docs: update DOCKER_DEV.md for Phase 2"
git commit -m "test: add schema validators for JSON files"
```

---

### 5. Push and Create Pull Request

```bash
# Push your branch
git push origin ###-your-feature

# Create PR via GitHub CLI
gh pr create --title "Your Feature Title" --body "Description"

# Or create PR on GitHub web interface
```

---

## 🧪 Testing & Validation

### Available Test Commands

| Command | Purpose | Duration |
|---------|---------|----------|
| `make test` | Smoke tests (health checks + API validation) | < 5s |
| `make e2e-local` | Full E2E tests | ~ 2-3 min |
| `make validate-output` | Validate latest run output integrity | ~ 1s |
| `make validate-all` | Validate all runs in index.json | Variable |

### What Gets Validated

**Output Validation (`make validate-output`):**
- ✅ File presence (all expected files exist)
- ✅ Schema integrity (JSON, Parquet, PNG, CSV valid)
- ✅ API consistency (APIs serve from correct run_id)
- ✅ latest.json integrity (points to valid run)

**Results in metadata.json:**
```json
{
  "output_verification": {
    "status": "PASS",
    "missing": [],
    "schema_errors": [],
    "checks": {...}
  }
}
```

### Understanding Validation Status

- **PASS** - All checks passed
- **PARTIAL** - Some required files missing (non-critical)
- **FAIL** - Critical files missing or schema errors

Check `runflow/{run_id}/metadata.json` for details.

---

## 📖 Understanding the Codebase

### Architecture Overview

**Local-Only Docker Architecture:**
- No cloud dependencies (Phase 1 declouding complete)
- UUID-based run directories
- Single storage layer (`app/storage.py`)
- Centralized run ID logic (`app/utils/run_id.py`)

### Key Modules

| Module | Purpose |
|--------|---------|
| `app/main.py` | FastAPI application entry point |
| `app/storage.py` | Unified storage abstraction |
| `app/utils/run_id.py` | Run ID generation and retrieval |
| `app/density_report.py` | Density analysis and reporting |
| `app/flow_report.py` | Temporal flow analysis |
| `app/heatmap_generator.py` | Heatmap generation |
| `app/tests/validate_output.py` | Output validation (Phase 3) |

### Documentation

**Start Here:**
- `docs/README.md` - Documentation index by audience
- `docs/dev-guides/docker-dev.md` - Complete Docker development guide
- `docs/user-guide/api-user-guide.md` - Output structure reference

**For Developers:**
- `docs/dev-guides/ai-developer-guide.md` - AI assistant onboarding and rules
- `docs/dev-guides/developer-guide-v2.md` - Complete v2 developer guide
- `docs/reference/QUICK_REFERENCE.md` - Variable names and standards

---

## 🐛 Debugging

### Common Issues

**1. Container won't start**
```bash
# Check if port 8080 is in use
lsof -i :8080

# View Docker logs
docker logs run-density-dev

# Restart container
make stop && make dev
```

**2. Tests failing**
```bash
# Check container health
docker ps

# View recent logs
docker logs run-density-dev --tail 100

# Check latest run_id
docker exec run-density-dev cat /app/runflow/latest.json
```

**3. Validation failing**
```bash
# Run validation manually
make validate-output

# Check metadata for details
cat runflow/$(cat runflow/latest.json | jq -r '.run_id')/metadata.json | jq .output_verification

# Check which files are missing
docker exec run-density-dev ls -la /app/runflow/$(cat runflow/latest.json | jq -r '.run_id')/
```

**4. Heatmaps not displaying**
```bash
# Verify heatmaps exist
docker exec run-density-dev ls /app/runflow/$(cat runflow/latest.json | jq -r '.run_id')/ui/heatmaps/

# Check A1 heatmap specifically
docker exec run-density-dev file /app/runflow/$(cat runflow/latest.json | jq -r '.run_id')/ui/heatmaps/A1.png
```

---

## ✅ Pull Request Checklist

### Before Creating PR

- [ ] **Tests pass**
  - [ ] `make test` - Smoke tests pass
  - [ ] `make e2e-local` - E2E tests pass
  - [ ] `make validate-output` - Output validation passes (exit code 0)
  
- [ ] **Code quality**
  - [ ] No errors in logs: `docker logs run-density-dev | grep -iE "error|failed"`
  - [ ] Code follows project conventions
  - [ ] No FutureWarnings or deprecated patterns
  
- [ ] **Documentation**
  - [ ] Documentation updated if needed
  - [ ] CHANGELOG.md updated for user-facing changes
  - [ ] Code comments added for complex logic
  
- [ ] **Commits**
  - [ ] Commit messages are clear and follow format
  - [ ] Related commits squashed if appropriate

### PR Description Should Include

1. **Issue reference**: "Closes #467" or "Relates to #466"
2. **What changed**: Brief summary of changes
3. **Why it changed**: Problem being solved
4. **Testing performed**: 
   - What tests were run
   - Validation results
   - Screenshots if UI changes
5. **Breaking changes**: Any backwards incompatible changes

### Example PR Description

```markdown
## Overview
Implements output validation framework for automated integrity checking.

Closes #467

## Changes
- Added `tests/validate_output.py` for automated validation
- Extended `config/reporting.yml` with validation schemas
- Added `make validate-output` command
- Updated metadata.json with verification results

## Testing
- ✅ `make test` - All smoke tests pass
- ✅ `make e2e-local` - E2E tests pass
- ✅ `make validate-output` - Validation passes
- ✅ No errors in logs

## Breaking Changes
None - backward compatible
```

---

## 🎯 Common Tasks

### Adding a New API Endpoint

1. Create route handler in `app/api/` or `app/routes/`
2. Add endpoint logic
3. Register router in `app/main.py`
4. Test with curl or browser
5. Add to `docs/ui-testing-checklist.md` if user-facing
6. Update documentation

### Modifying Report Generation

1. Edit `app/density_report.py` or `app/flow_report.py`
2. Run `make e2e-local` to regenerate reports
3. Verify output in `runflow/<uuid>/reports/`
4. Check `make validate-output` still passes
5. Update schemas in `config/reporting.yml` if structure changed

### Adding Output Validation

1. Edit `config/reporting.yml` to add expected file
2. Update `app/tests/validate_output.py` if new validation logic needed
3. Test with `make validate-output`
4. Update `docs/architecture/output.md`

---

## 🔍 Code Review Process

### What We Look For

1. **Functionality** - Does it work as intended?
2. **Tests** - Are there appropriate tests?
3. **Code Quality** - Is it readable and maintainable?
4. **Documentation** - Are changes documented?
5. **Validation** - Does `make validate-output` pass?

### Review Timeline

- Initial review: Within 2-3 business days
- Feedback addressed: Ongoing discussion
- Merge: After approval and all checks pass

---

## 📚 Additional Resources

### Documentation

- **Architecture** → `docs/architecture/output.md`
- **Development** → `docs/dev-guides/docker-dev.md`
- **AI Assistants** → `docs/dev-guides/ai-developer-guide.md`
- **Testing** → `docs/testing/testing-guide.md`
- **Quick Reference** → `docs/reference/QUICK_REFERENCE.md`

### Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open an Issue with label `bug`
- **Features**: Open an Issue with label `enhancement`

---

## 📜 Code of Conduct

**Be Respectful:** Treat all contributors with respect and kindness.

**Be Collaborative:** Work together to find the best solutions.

**Be Professional:** Keep discussions focused on the code and technical matters.

---

## 🙏 Thank You!

Your contributions make Run-Density better for everyone. We appreciate your time and effort!

---

**Questions?** See `docs/README.md` or open a GitHub Discussion.

**Last Updated:** 2025-11-11 (Issue #467 - Phase 3)

