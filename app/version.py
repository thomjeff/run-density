"""
Version Management Module

Handles automated versioning for releases to prevent version mismatches.
Provides functions to bump version numbers and validate version consistency.

Usage:
    from app.version import get_next_version, update_version_in_code
    next_version = get_next_version()
    update_version_in_code(next_version)
"""

import os
import re
import subprocess
import sys
from typing import Optional, Tuple
from pathlib import Path


def get_current_version() -> str:
    """
    Get the current version from app/main.py.

    Returns:
        Current version string (e.g., "v1.6.14")
    """
    main_py_path = Path("app/main.py")
    if not main_py_path.exists():
        raise FileNotFoundError("app/main.py not found")

    content = main_py_path.read_text()
    match = re.search(r'version="([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in app/main.py")

    return match.group(1)


def get_latest_git_tag() -> Optional[str]:
    """
    Get the latest git tag.

    Returns:
        Latest tag name or None if no tags exist
    """
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-version:refname"],
            capture_output=True,
            text=True,
            check=True
        )
        tags = result.stdout.strip().split('\n')
        return tags[0] if tags and tags[0] else None
    except subprocess.CalledProcessError:
        return None


def get_version() -> str:
    """
    Get application version with fallback logic.
    
    Priority order:
    1. Latest git tag (preferred)
    2. APP_VERSION environment variable
    3. Default fallback ("v2.0.0")
    
    Returns:
        Version string (e.g., "v2.0.6")
    
    Issue #550: Make version dynamic from GitHub tag/release
    """
    # Try git tag first (preferred)
    git_tag = get_latest_git_tag()
    if git_tag:
        return git_tag
    
    # Fall back to environment variable
    env_version = os.getenv("APP_VERSION")
    if env_version:
        return env_version
    
    # Default fallback
    return "v2.0.0"


def parse_version(version: str) -> Tuple[int, int, int]:
    """
    Parse version string into major, minor, patch components.

    Args:
        version: Version string (e.g., "v1.6.14")

    Returns:
        Tuple of (major, minor, patch) integers
    """
    # Remove 'v' prefix if present
    version = version.lstrip('v')

    # Split by dots and convert to integers
    parts = version.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        raise ValueError(f"Invalid version format: {version}")


def format_version(major: int, minor: int, patch: int) -> str:
    """
    Format version components into version string.

    Args:
        major: Major version number
        minor: Minor version number
        patch: Patch version number

    Returns:
        Version string (e.g., "v1.6.14")
    """
    return f"v{major}.{minor}.{patch}"


def get_next_version(bump_type: str = "patch") -> str:
    """
    Get the next version number based on current version and bump type.

    Args:
        bump_type: Type of version bump ("major", "minor", "patch")

    Returns:
        Next version string
    """
    current_version = get_current_version()
    major, minor, patch = parse_version(current_version)

    if bump_type == "major":
        return format_version(major + 1, 0, 0)
    elif bump_type == "minor":
        return format_version(major, minor + 1, 0)
    elif bump_type == "patch":
        return format_version(major, minor, patch + 1)
    else:
        raise ValueError(f"Invalid bump_type: {bump_type}. Must be 'major', 'minor', or 'patch'")


def update_version_in_code(new_version: str) -> bool:
    """
    Update version in app/main.py.

    Args:
        new_version: New version string (e.g., "v1.6.15")

    Returns:
        True if successful, False otherwise
    """
    main_py_path = Path("app/main.py")
    if not main_py_path.exists():
        print("❌ app/main.py not found")
        return False

    try:
        content = main_py_path.read_text()

        # Replace version in FastAPI app definition
        pattern = r'version="[^"]+"'
        replacement = f'version="{new_version}"'
        new_content = re.sub(pattern, replacement, content)

        if new_content == content:
            print("❌ Version not found or not updated in app/main.py")
            return False

        main_py_path.write_text(new_content)
        print(f"✅ Updated version in app/main.py to {new_version}")
        return True

    except Exception as e:
        print(f"❌ Error updating version: {e}")
        return False


def validate_version_consistency() -> bool:
    """
    Validate that version in code matches the latest git tag.

    Returns:
        True if versions match, False otherwise
    """
    try:
        code_version = get_current_version()
        git_tag = get_latest_git_tag()

        if not git_tag:
            print("⚠️  No git tags found")
            return True  # No tags to compare against

        if code_version == git_tag:
            print(f"✅ Version consistency: {code_version} matches git tag")
            return True
        else:
            print(f"❌ Version mismatch: code={code_version}, git_tag={git_tag}")
            return False

    except Exception as e:
        print(f"❌ Error validating version consistency: {e}")
        return False


def create_version_bump_script() -> str:
    """
    Create a version bump script for easy use.

    Returns:
        Path to the created script
    """
    script_content = '''#!/bin/bash
# Version Bump Script for run-density

set -e

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

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
NEXT_VERSION=$(python3 -c \
    "from app.version import get_next_version; \
     print(get_next_version('$BUMP_TYPE'))")
echo -e "Next version: ${NEXT_VERSION}"

# Update version in code
if python3 -c \
    "from app.version import update_version_in_code; \
     update_version_in_code('$NEXT_VERSION')"; then
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
'''

    script_path = Path("scripts/bump_version.sh")
    script_path.parent.mkdir(exist_ok=True)
    script_path.write_text(script_content)
    script_path.chmod(0o755)

    return str(script_path)


if __name__ == "__main__":
    # Command line interface
    if len(sys.argv) < 2:
        print("Usage: python3 -m app.version <command> [args]")
        print("Commands:")
        print("  current          - Show current version")
        print("  next <type>      - Show next version (major|minor|patch)")
        print("  bump <type>      - Bump version in code")
        print("  validate         - Validate version consistency")
        print("  create-script    - Create version bump script")
        sys.exit(1)

    command = sys.argv[1]

    if command == "current":
        print(get_current_version())
    elif command == "next":
        bump_type = sys.argv[2] if len(sys.argv) > 2 else "patch"
        print(get_next_version(bump_type))
    elif command == "bump":
        bump_type = sys.argv[2] if len(sys.argv) > 2 else "patch"
        next_version = get_next_version(bump_type)
        if update_version_in_code(next_version):
            print(f"Version bumped to {next_version}")
        else:
            sys.exit(1)
    elif command == "validate":
        if validate_version_consistency():
            sys.exit(0)
        else:
            sys.exit(1)
    elif command == "create-script":
        script_path = create_version_bump_script()
        print(f"Version bump script created: {script_path}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
