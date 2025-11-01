#!/bin/bash
# Version Bump Script for run-density

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Run-Density Version Bump Script ===${NC}"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not in a git repository${NC}"
    exit 1
fi

# Check if working directory is clean
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ Working directory is not clean. Please commit or stash changes first.${NC}"
    exit 1
fi

# Get bump type from argument
BUMP_TYPE=${1:-patch}

if [[ ! "$BUMP_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo -e "${RED}❌ Invalid bump type: $BUMP_TYPE. Use major, minor, or patch${NC}"
    echo "Usage: $0 [major|minor|patch]"
    exit 1
fi

echo -e "${YELLOW}Bumping $BUMP_TYPE version...${NC}"

# Get current version
CURRENT_VERSION=$(python3 -c "from app.version import get_current_version; print(get_current_version())")
echo -e "Current version: ${CURRENT_VERSION}"

# Get next version
NEXT_VERSION=$(python3 -c "from app.version import get_next_version; print(get_next_version('$BUMP_TYPE'))")
echo -e "Next version: ${NEXT_VERSION}"

# Update version in code
if python3 -c "from app.version import update_version_in_code; update_version_in_code('$NEXT_VERSION')"; then
    echo -e "${GREEN}✅ Version updated in code${NC}"
else
    echo -e "${RED}❌ Failed to update version in code${NC}"
    exit 1
fi

# Commit the version change
git add app/main.py
git commit -m "Bump version to $NEXT_VERSION"

# Create git tag
git tag -a "$NEXT_VERSION" -m "Release $NEXT_VERSION"

echo -e "${GREEN}✅ Version bumped to $NEXT_VERSION${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Push changes: git push origin main"
echo -e "2. Push tag: git push origin $NEXT_VERSION"
echo -e "3. Create GitHub release: gh release create $NEXT_VERSION"
