"""
Authentication utilities for password gate and session management.

Issue #314: Password Gate with Session Management
"""
import os
import time
from typing import Optional, Union
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

from app.utils.env import env_bool, env_str

# Session configuration
SESSION_COOKIE_NAME = "rf_auth"
SESSION_TIMESTAMP_COOKIE_NAME = "rf_auth_ts"
SESSION_DURATION_SECONDS = 8 * 60 * 60  # 8 hours
SESSION_VALUE = "authenticated"


def get_dashboard_password() -> str:
    """
    Get dashboard password from environment variable.
    
    Returns:
        str: Password from DASHBOARD_PASSWORD env var, defaults to empty string
        
    Issue #314: Password stored server-side in env/config
    """
    return env_str("DASHBOARD_PASSWORD", "")


def validate_password(password: str) -> bool:
    """
    Validate password against configured value.
    
    Args:
        password: Password to validate
        
    Returns:
        bool: True if password matches, False otherwise
        
    Issue #314: Server-side password validation
    """
    expected_password = get_dashboard_password()
    if not expected_password:
        # If no password configured, allow access (development mode)
        return True
    return password == expected_password


def is_session_valid(request: Request) -> bool:
    """
    Check if user has a valid session.
    
    Args:
        request: FastAPI request object
        
    Returns:
        bool: True if session is valid and not expired, False otherwise
        
    Issue #314: Server-side session validation with 8-hour expiry
    """
    cookies = request.cookies
    
    # Check if session cookie exists
    session_value = cookies.get(SESSION_COOKIE_NAME)
    if session_value != SESSION_VALUE:
        return False
    
    # Check if timestamp cookie exists and is valid
    timestamp_str = cookies.get(SESSION_TIMESTAMP_COOKIE_NAME)
    if not timestamp_str:
        return False
    
    try:
        timestamp = float(timestamp_str)
        current_time = time.time()
        
        # Check if session has expired (8 hours)
        if current_time - timestamp > SESSION_DURATION_SECONDS:
            return False
        
        return True
    except (ValueError, TypeError):
        return False


def _is_secure_request(request: Optional[Request]) -> bool:
    if not request:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return forwarded_proto.lower() == "https"
    return request.url.scheme.lower() == "https"


def create_session_response(
    redirect_url: str = "/dashboard",
    request: Optional[Request] = None
) -> RedirectResponse:
    """
    Create a redirect response with session cookies set.
    
    Args:
        redirect_url: URL to redirect to after login
        
    Returns:
        RedirectResponse: Response with session cookies set
        
    Issue #314: Set rf_auth and rf_auth_ts cookies
    """
    response = RedirectResponse(url=redirect_url, status_code=303)
    secure_cookie = env_bool("COOKIE_SECURE") or _is_secure_request(request)
    
    # Set session cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=SESSION_VALUE,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,  # Prevent JavaScript access for security
        secure=secure_cookie,
        samesite="lax"
    )
    
    # Set timestamp cookie
    response.set_cookie(
        key=SESSION_TIMESTAMP_COOKIE_NAME,
        value=str(time.time()),
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        secure=secure_cookie,
        samesite="lax"
    )
    
    return response


def clear_session_response(
    redirect_url: str = "/",
    request: Optional[Request] = None
) -> RedirectResponse:
    """
    Create a redirect response that clears session cookies.
    
    Args:
        redirect_url: URL to redirect to after logout
        
    Returns:
        RedirectResponse: Response with session cookies cleared
        
    Issue #314: Clear rf_auth and rf_auth_ts cookies
    """
    response = RedirectResponse(url=redirect_url, status_code=303)
    secure_cookie = env_bool("COOKIE_SECURE") or _is_secure_request(request)
    
    # Clear session cookies by setting them to empty with max_age=0
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=secure_cookie,
        samesite="lax"
    )
    
    response.set_cookie(
        key=SESSION_TIMESTAMP_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=secure_cookie,
        samesite="lax"
    )
    
    return response


def require_auth(request: Request) -> Optional[RedirectResponse]:
    """
    Check if user is authenticated, return redirect if not.
    
    Args:
        request: FastAPI request object
        
    Returns:
        RedirectResponse if not authenticated, None if authenticated
        
    Issue #314: Server-side authentication check with redirect
    """
    if not is_session_valid(request):
        return RedirectResponse(url="/", status_code=303)
    return None
