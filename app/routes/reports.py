# app/routes/reports.py
# Phase 3 cleanup: Removed all legacy endpoints and helper functions
# - Legacy endpoints (/reports/list, /reports/open, /reports/preview) were not used by frontend
# - Frontend uses /api/reports/list and /api/reports/download from app/routes/api_reports.py instead
# - All helper functions were only used by the removed legacy endpoints

from fastapi import APIRouter

# Empty router - kept for potential future use or backward compatibility
# If this file becomes completely unused, the router registration in main.py can be removed
router = APIRouter(prefix="/reports", tags=["reports"])
