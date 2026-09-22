from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.security import COOKIE_MAX_AGE, COOKIE_NAME, clear_session_cookie, issue_dev_session
from app.dependencies import CurrentAccountId, SessionDep
from app.schemas.api import AccountOut, DevSessionIn
from app.services import projects as project_service

router = APIRouter(prefix="/auth", tags=["auth"])

_MS_SCOPES = "offline_access Files.ReadWrite User.Read"


@router.post("/dev-session", response_model=AccountOut)
def create_dev_session(body: DevSessionIn, session: SessionDep, response: Response) -> AccountOut:
    settings = get_settings()
    if not settings.dev_auth:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dev auth is disabled")
    account = project_service.upsert_dev_account(
        session, email=str(body.email), display_name=body.display_name.strip()
    )
    token = issue_dev_session(account.id)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    return AccountOut.model_validate(account)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_session_cookie(response)


@router.get("/me", response_model=AccountOut)
def me(session: SessionDep, account_id: CurrentAccountId) -> AccountOut:
    account = project_service.get_account(session, account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown account")
    return AccountOut.model_validate(account)


@router.get("/microsoft/status")
def microsoft_status(session: SessionDep, account_id: CurrentAccountId) -> dict:
    account = project_service.get_account(session, account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown account")
    settings = get_settings()
    return {
        "configured": bool(settings.microsoft_client_id)
        or bool(settings.onedrive_local_mirror_dir),
        "connected": bool(account.ms_refresh_token)
        or bool(settings.onedrive_local_mirror_dir),
        "local_mirror": bool(settings.onedrive_local_mirror_dir),
        "connected_at": account.ms_connected_at.isoformat() if account.ms_connected_at else None,
    }


@router.get("/microsoft/start")
def microsoft_start(account_id: CurrentAccountId) -> RedirectResponse:
    settings = get_settings()
    if not settings.microsoft_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Microsoft OAuth not configured")
    params = urlencode(
        {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": settings.microsoft_redirect_uri,
            "response_mode": "query",
            "scope": _MS_SCOPES,
            "state": str(account_id),
        }
    )
    url = (
        f"https://login.microsoftonline.com/{settings.microsoft_tenant}"
        f"/oauth2/v2.0/authorize?{params}"
    )
    return RedirectResponse(url)


@router.get("/microsoft/callback")
def microsoft_callback(
    session: SessionDep,
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    settings = get_settings()
    frontend = settings.frontend_origin.rstrip("/")
    if error or not code or not state:
        return RedirectResponse(f"{frontend}/?onedrive=error")
    try:
        account_id = UUID(state)
    except ValueError:
        return RedirectResponse(f"{frontend}/?onedrive=error")
    account = project_service.get_account(session, account_id)
    if account is None:
        return RedirectResponse(f"{frontend}/?onedrive=error")

    token_url = (
        f"https://login.microsoftonline.com/{settings.microsoft_tenant}/oauth2/v2.0/token"
    )
    try:
        token_res = httpx.post(
            token_url,
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "code": code,
                "redirect_uri": settings.microsoft_redirect_uri,
                "grant_type": "authorization_code",
                "scope": _MS_SCOPES,
            },
            timeout=30.0,
        )
        token_res.raise_for_status()
        body = token_res.json()
    except httpx.HTTPError:
        return RedirectResponse(f"{frontend}/?onedrive=error")

    account.ms_refresh_token = body.get("refresh_token") or account.ms_refresh_token
    account.ms_connected_at = datetime.now(UTC)
    account.ms_drive_id = "me"
    session.commit()
    return RedirectResponse(f"{frontend}/?onedrive=connected")


@router.post("/microsoft/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def microsoft_disconnect(session: SessionDep, account_id: CurrentAccountId) -> None:
    account = project_service.get_account(session, account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown account")
    account.ms_refresh_token = None
    account.ms_drive_id = None
    account.ms_connected_at = None
    session.commit()
