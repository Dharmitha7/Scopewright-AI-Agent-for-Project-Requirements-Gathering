"""Session verification (D42, D53).

v1 uses a JWT in an HttpOnly cookie — not Stytch, not localStorage.
The token's `sub` is account_id; display name and email live in accounts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Cookie, HTTPException, status

from app.core.config import get_settings

COOKIE_NAME = "crewlane_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 14
JWT_ALG = "HS256"


def clear_session_cookie(response) -> None:
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax")


def issue_dev_session(account_id: UUID) -> str:
    settings = get_settings()
    if not settings.dev_auth:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dev auth is disabled")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(account_id),
            "iat": now,
            "exp": now + timedelta(seconds=COOKIE_MAX_AGE),
        },
        settings.dev_session_secret,
        algorithm=JWT_ALG,
    )


def read_session_account_id(
    crewlane_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> UUID:
    if not crewlane_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    settings = get_settings()
    try:
        payload = jwt.decode(
            crewlane_session,
            settings.dev_session_secret,
            algorithms=[JWT_ALG],
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc
