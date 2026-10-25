"""Session display name for accountable Execute writes (#928 M2).

Not an account. The operator sets a name or initials once after login.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from starlette.responses import Response

from app.utils.auth import SESSION_DURATION_SECONDS, _is_secure_request
from app.utils.env import env_bool

OPERATOR_COOKIE = "rf_auth_execute_name"
OPERATOR_LIMIT = 40


class OperatorError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def clean_operator(value: object) -> str:
    return str(value or "").strip()[:OPERATOR_LIMIT]


def require_operator(request: Request) -> str:
    name = clean_operator(request.cookies.get(OPERATOR_COOKIE))
    if not name:
        raise OperatorError(
            "Set a session display name before this action."
        )
    return name


def operator_from_request(request: Request) -> str:
    return clean_operator(request.cookies.get(OPERATOR_COOKIE))


def set_operator_cookie(
    response: Response,
    name: str,
    request: Optional[Request] = None,
) -> Response:
    cleaned = clean_operator(name)
    if not cleaned:
        raise OperatorError("Display name is required.")
    secure_cookie = env_bool("COOKIE_SECURE") or _is_secure_request(request)
    response.set_cookie(
        key=OPERATOR_COOKIE,
        value=cleaned,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
    )
    return response


def clear_operator_cookie(
    response: Response,
    request: Optional[Request] = None,
) -> Response:
    secure_cookie = env_bool("COOKIE_SECURE") or _is_secure_request(request)
    response.set_cookie(
        key=OPERATOR_COOKIE,
        value="",
        max_age=0,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
    )
    return response
