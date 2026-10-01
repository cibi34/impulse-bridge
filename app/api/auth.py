"""Web app API: passwordless sign-in by email.

POST /api/auth/login sends a one-time link — but only to addresses that
collections were created with, so the endpoint can't be used to send mail to
arbitrary people. The response never says whether a mail went out.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.web_collections import session_email, summaries_out
from app.auth import (
    LOGIN_TOKEN_TTL,
    SESSION_TTL,
    AuthStore,
    normalize_email,
    secure_cookies,
    session_cookie_name,
)
from app.curation.store import CollectionStore
from app.mail import MailError, build_message, mail_available, send
from app.ratelimit import RateLimit
from app.settings import settings
from app.site_settings import SiteSettingsStore
from app.storage import get_auth_store, get_site_store, get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["web"])

Store = Annotated[CollectionStore, Depends(get_store)]
Auth = Annotated[AuthStore, Depends(get_auth_store)]
Site = Annotated[SiteSettingsStore, Depends(get_site_store)]

login_limit = RateLimit(limit=10, window_seconds=3600)
"""Sign-in requests per client and hour."""
MAX_LINKS_PER_ADDRESS_PER_HOUR = 5

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LOGIN_SENT = "If collections were created with this address, we sent a sign-in link to it."


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/auth/login", status_code=202, dependencies=[Depends(login_limit)])
async def request_login(body: LoginRequest, store: Store, auth: Auth, site: Site):
    email = normalize_email(body.email)
    if not _EMAIL.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    site_settings = await run_in_threadpool(site.load)
    if not mail_available(site_settings):
        raise HTTPException(status_code=503, detail="Sign-in by email is not available on this server")

    owns_collections = bool(await run_in_threadpool(store.list_by_owner, email))
    recent = await run_in_threadpool(auth.recent_login_tokens, email, timedelta(hours=1))
    if owns_collections and recent < MAX_LINKS_PER_ADDRESS_PER_HOUR:
        token = await run_in_threadpool(auth.create_login_token, email)
        link = f"{settings.public_base_url.rstrip('/')}/signin#token={token}"
        minutes = int(LOGIN_TOKEN_TTL.total_seconds() // 60)
        message = build_message(
            site_settings,
            email,
            "Sign in to IMPULSE Curator",
            [
                "Use this link to sign in and see your collections on this device.",
                f"It works once and expires in {minutes} minutes. "
                "If you didn't ask for it, you can ignore this email.",
            ],
            link=("Sign in", link),
        )
        try:
            await send(site_settings, message)
        except MailError:
            logger.exception("Sending the sign-in link failed")
    return {"detail": LOGIN_SENT}


@router.post("/auth/verify")
def verify_login(body: VerifyRequest, response: Response, auth: Auth):
    email = auth.redeem_login_token(body.token)
    if email is None:
        raise HTTPException(status_code=400, detail="This sign-in link is invalid or has expired")
    session_id = auth.create_session(email)
    response.set_cookie(
        session_cookie_name(),
        session_id,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=secure_cookies(),
        httponly=True,
        samesite="lax",
    )
    return {"email": email}


@router.get("/auth/me")
def me(request: Request, auth: Auth):
    return {"email": session_email(request, auth)}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, auth: Auth):
    session_id = request.cookies.get(session_cookie_name())
    if session_id:
        auth.delete_session(session_id)
    response = Response(status_code=204)
    response.delete_cookie(session_cookie_name(), path="/", secure=secure_cookies(), httponly=True, samesite="lax")
    return response


@router.get("/me/collections")
def my_collections(request: Request, store: Store, auth: Auth):
    """Collections created with the signed-in email address."""
    email = session_email(request, auth)
    if email is None:
        raise HTTPException(status_code=401, detail="Sign in to see your collections")
    return summaries_out(store, [r for r in store.list_by_owner(email) if not r.disabled])
