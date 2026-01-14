"""
Pytest configuration for v2 E2E tests.

This file contains pytest hooks and fixtures shared across all v2 tests.
"""

import pytest
import os


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Base URL for API requests (default: http://localhost:8080 or BASE_URL env var)"
    )
    parser.addoption(
        "--enable-audit",
        action="store",
        default="n",
        help="Enable audit generation (y/n, default: n)"
    )
    parser.addoption(
        "--run-id",
        action="store",
        default=None,
        help="Run ID to use for contract tests (defaults to latest if not provided)"
    )
    parser.addoption(
        "--day",
        action="store",
        default=None,
        help="Day code (fri|sat|sun|mon) for contract tests (defaults to first available day)"
    )


@pytest.fixture(scope="class")
def base_url(request):
    """Base URL for API requests.
    
    Can be configured via:
    - --base-url pytest CLI argument
    - BASE_URL environment variable
    - Defaults to http://localhost:8080
    """
    # Check for CLI argument first
    base_url_arg = request.config.getoption("--base-url")
    if base_url_arg:
        return base_url_arg
    
    # Fall back to environment variable or default
    return os.getenv("BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="class")
def enable_audit(request):
    """Enable audit generation flag.
    
    Can be configured via:
    - --enable-audit pytest CLI argument (y/n)
    - Defaults to "n" (disabled)
    """
    audit_arg = request.config.getoption("--enable-audit")
    # Normalize to "y" or "n"
    if audit_arg and audit_arg.lower() in ("y", "yes", "true", "1"):
        return "y"
    return "n"


@pytest.fixture(scope="class")
def run_id(request):
    """Run ID for contract tests.
    
    Can be configured via:
    - --run-id pytest CLI argument
    - Defaults to latest run_id if not provided
    """
    run_id_arg = request.config.getoption("--run-id")
    if run_id_arg:
        return run_id_arg
    
    # Fall back to latest run_id
    try:
        from app.utils.run_id import get_latest_run_id
        return get_latest_run_id()
    except (FileNotFoundError, ValueError):
        return None

