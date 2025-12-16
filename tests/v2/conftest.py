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

