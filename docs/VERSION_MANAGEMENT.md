# Version Management Guide

This document describes the automated versioning system implemented to prevent version mismatches between code and releases.

## Problem Solved

Previously, we experienced version mismatches where:
- Git tags were created with version X (e.g., v1.6.13)
- But `app/main.py` still contained version Y (e.g., v1.6.12)
- This caused confusion about which version was actually deployed

## Solution Overview

The automated versioning system provides:
1. **Version Management Module** (`app/version.py`) - Core versioning functions
2. **Version Bump Script** (`scripts/bump_version.sh`) - Easy command-line tool
3. **GitHub Actions Workflows** - Automated validation and release
4. **Validation Checks** - Ensure version consistency

## Usage

### Command Line Interface

```bash
# Show current version
python3 -m app.version current

# Show next version
python3 -m app.version next patch    # v1.6.15
python3 -m app.version next minor    # v1.7.0
python3 -m app.version next major    # v2.0.0

# Bump version in code
python3 -m app.version bump patch

# Validate version consistency
python3 -m app.version validate
```

### Version Bump Script

```bash
# Bump patch version (recommended for most changes)
./scripts/bump_version.sh patch

# Bump minor version (for new features)
./scripts/bump_version.sh minor

# Bump major version (for breaking changes)
./scripts/bump_version.sh major
```

The script will:
1. Check that working directory is clean
2. Get current version from `app/main.py`
3. Calculate next version
4. Update `app/main.py` with new version
5. Commit the change
6. Create git tag
7. Provide next steps for pushing

### GitHub Actions

#### Version Consistency Check
- Runs on every push to `main`
- Validates that code version matches latest git tag
- Fails if versions don't match

#### Automated Release
- Triggers when git tags are pushed
- Validates version consistency
- Runs E2E tests
- Creates GitHub release automatically

## Version Bump Types

### Patch (v1.6.14 → v1.6.15)
- Bug fixes
- Documentation updates
- Minor improvements
- **Most common** - use for most changes

### Minor (v1.6.14 → v1.7.0)
- New features
- New API endpoints
- Significant enhancements
- Backward compatible changes

### Major (v1.6.14 → v2.0.0)
- Breaking changes
- API changes that break compatibility
- Major architectural changes
- **Rare** - only for significant changes

## Workflow Examples

### Standard Release Process

```bash
# 1. Make your changes and commit them
git add .
git commit -m "Add new feature X"

# 2. Bump version
./scripts/bump_version.sh patch

# 3. Push changes and tag
git push origin main
git push origin v1.6.15

# 4. GitHub Actions will automatically create the release
```

### Emergency Hotfix Process

```bash
# 1. Create hotfix branch
git checkout -b hotfix/critical-bug-fix

# 2. Make fix and commit
git add .
git commit -m "Fix critical bug in density calculation"

# 3. Bump patch version
./scripts/bump_version.sh patch

# 4. Push and create PR
git push origin hotfix/critical-bug-fix
# Create PR, merge to main

# 5. Push tag for release
git push origin v1.6.15
```

## Validation

The system includes several validation checks:

### Pre-commit Checks
- Working directory must be clean
- Version format must be valid (vX.Y.Z)

### Version Consistency
- Code version must match git tag
- No version mismatches allowed

### E2E Testing
- All tests must pass before release
- Preflight validation included

## Troubleshooting

### Version Mismatch Error
```
❌ Version mismatch: code=v1.6.14, git_tag=v1.6.13
```

**Solution**: Update code version to match tag or create new tag
```bash
# Option 1: Update code to match tag
python3 -m app.version bump patch

# Option 2: Create new tag for current code
git tag -a v1.6.14 -m "Release v1.6.14"
git push origin v1.6.14
```

### Working Directory Not Clean
```
❌ Working directory is not clean. Please commit or stash changes first.
```

**Solution**: Commit or stash changes first
```bash
git add .
git commit -m "Your changes"
# Then run version bump
```

### Invalid Version Format
```
❌ Invalid version format: 1.6.14
```

**Solution**: Use proper format with 'v' prefix
```bash
# Correct format
python3 -m app.version bump patch  # Creates v1.6.15
```

## Benefits

1. **Prevents Version Mismatches**: Automated validation ensures consistency
2. **Reduces Human Error**: Scripts handle version updates correctly
3. **Streamlines Releases**: One command creates version bump + tag
4. **CI/CD Integration**: GitHub Actions automate validation and releases
5. **Clear Documentation**: Easy to understand and follow process

## Files

- `app/version.py` - Core version management functions
- `scripts/bump_version.sh` - Version bump script
- `.github/workflows/version-check.yml` - Version consistency validation
- `.github/workflows/release.yml` - Automated release workflow
- `docs/VERSION_MANAGEMENT.md` - This documentation

## Future Enhancements

- [ ] Automatic changelog generation
- [ ] Semantic versioning based on commit messages
- [ ] Integration with Cloud Run deployment
- [ ] Version rollback capabilities
- [ ] Release notes generation from commits
