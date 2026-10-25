"""Keep Execute login cookies off the leftover combined names."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from starlette.requests import Request
from starlette.responses import Response

COMBINED_AUTH = "rf_auth"
COMBINED_TS = "rf_auth_ts"
EXECUTE_AUTH = "rf_auth_execute"
EXECUTE_TS = "rf_auth_execute_ts"
EXECUTE_NAME = "rf_auth_execute_name"

HeaderList = List[Tuple[bytes, bytes]]


def _split_cookies(raw: bytes) -> List[Tuple[bytes, bytes]]:
    out: List[Tuple[bytes, bytes]] = []
    for part in raw.split(b";"):
        item = part.strip()
        if not item or b"=" not in item:
            continue
        name, value = item.split(b"=", 1)
        out.append((name.strip(), value))
    return out


def incoming_cookie_header(raw: bytes) -> bytes:
    """Accept Execute cookies only; map them to leftover auth names."""
    mapped = dict(_split_cookies(raw))
    parts = []
    auth = mapped.get(EXECUTE_AUTH.encode("ascii"))
    if auth is not None:
        parts.append(COMBINED_AUTH.encode("ascii") + b"=" + auth)
        ts = mapped.get(EXECUTE_TS.encode("ascii"))
        if ts is not None:
            parts.append(COMBINED_TS.encode("ascii") + b"=" + ts)
    name = mapped.get(EXECUTE_NAME.encode("ascii"))
    if name is not None:
        parts.append(EXECUTE_NAME.encode("ascii") + b"=" + name)
    return b"; ".join(parts)


def outgoing_set_cookie(raw: bytes) -> bytes:
    """Rename leftover Set-Cookie names to Execute names."""
    ts_prefix = COMBINED_TS.encode("ascii")
    auth_prefix = COMBINED_AUTH.encode("ascii")
    if raw.startswith(ts_prefix + b"="):
        rest = raw[len(ts_prefix) :]  # noqa: E203
        return EXECUTE_TS.encode("ascii") + rest
    if raw.startswith(auth_prefix + b"="):
        rest = raw[len(auth_prefix) :]  # noqa: E203
        return EXECUTE_AUTH.encode("ascii") + rest
    return raw


def rewrite_request_cookies(request: Request) -> None:
    raw = request.headers.get("cookie")
    if raw is None:
        return
    mapped = incoming_cookie_header(raw.encode("latin-1"))
    headers: HeaderList = []
    for key, value in request.scope["headers"]:
        if key == b"cookie":
            if mapped:
                headers.append((key, mapped))
            continue
        headers.append((key, value))
    request.scope["headers"] = headers


def rewrite_response_cookies(response: Response) -> Response:
    raw_headers: Sequence[Tuple[bytes, bytes]] = list(response.raw_headers)
    out: HeaderList = []
    for key, value in raw_headers:
        if key.lower() == b"set-cookie":
            out.append((key, outgoing_set_cookie(value)))
        else:
            out.append((key, value))
    response.raw_headers[:] = out
    return response
