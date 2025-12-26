import os

# Auto-start coverage in subprocesses when COVERAGE_PROCESS_START is set.
# This ensures gunicorn/uvicorn workers and CLI invocations contribute to the
# same coverage data file configured in coverage.rc.
if os.getenv("COVERAGE_PROCESS_START"):
    try:
        import coverage

        coverage.process_startup()
    except Exception:
        # Silently continue if coverage is unavailable; avoids breaking runtime.
        pass

