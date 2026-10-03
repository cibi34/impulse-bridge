"""Admin API for site settings: submission address, SMTP account and the
licence conditions IMPULSE accepts.

The SMTP password is never returned; the response only says whether one is
set and whether it comes from the environment (BRIDGE_SMTP_PASSWORD).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.licensing import Condition
from app.mail import MailError, build_message, send
from app.settings import settings
from app.site_settings import SiteSettings, SiteSettingsStore
from app.storage import get_site_store

router = APIRouter(prefix="/admin/api/settings", tags=["admin"])

Site = Annotated[SiteSettingsStore, Depends(get_site_store)]


class SettingsUpdate(BaseModel):
    """Only the fields sent are changed. `smtp_password: ""` removes it."""

    submission_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_security: Literal["starttls", "ssl", "none"] | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    mail_from: str | None = None
    licence_conditions: list[Condition] | None = None


class TestEmail(BaseModel):
    to: str = Field(min_length=3, max_length=254)


def _out(site: SiteSettings) -> dict:
    data = site.model_dump(exclude={"smtp_password"})
    data["smtp_password_set"] = bool(site.effective_smtp_password)
    data["smtp_password_from_env"] = bool(settings.smtp_password)
    data["mail_configured"] = site.mail_configured
    data["mail_log_only"] = settings.mail_log_only
    # Deployment settings from the environment, shown read-only.
    data["server"] = {
        "public_base_url": settings.public_base_url,
        "collection_owner_id": settings.collection_owner_id,
        "default_organization": settings.default_organization,
        "max_assets_per_collection": settings.max_assets_per_collection,
        "config_dir": str(settings.config_dir),
        "database": str(settings.database_file),
    }
    return data


@router.get("")
def read(site: Site):
    return _out(site.load())


@router.put("")
def update(body: SettingsUpdate, site: Site):
    changes = {k: (v.strip() if isinstance(v, str) and k != "smtp_password" else v)
               for k, v in body.model_dump(exclude_none=True).items()}
    try:
        return _out(site.save(changes))
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": list(err["loc"]), "msg": err["msg"]} for err in e.errors()],
        ) from None


@router.post("/test-email")
async def test_email(body: TestEmail, site: Site):
    """Send a test message with the saved settings."""
    site_settings = site.load()
    message = build_message(
        site_settings,
        body.to.strip(),
        "IMPULSE Curator: test email",
        ["This is a test message. Email is set up correctly."],
    )
    try:
        await send(site_settings, message)
    except MailError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    return {"sent_to": body.to.strip()}
