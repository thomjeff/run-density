"""Execute operator APIs.

Leftover analysis-board routes keyed by `run_id` were removed in #924.
Operations uses `/api/execute/ops/*` on the imported plan.
"""

from app.routes.api_execute_runtime import router

__all__ = ["router"]
