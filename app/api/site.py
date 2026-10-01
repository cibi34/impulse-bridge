"""Web app API: public configuration the browser app needs at start."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.mail import mail_available
from app.settings import settings
from app.site_settings import SiteSettingsStore
from app.storage import get_site_store

router = APIRouter(prefix="/api", tags=["web"])


@router.get("/config")
def config(site: Annotated[SiteSettingsStore, Depends(get_site_store)]):
    site_settings = site.load()
    return {
        "app_name": "IMPULSE Curator",
        "submission_email": site_settings.submission_email or None,
        "sign_in_available": mail_available(site_settings),
        "max_assets_per_collection": settings.max_assets_per_collection,
    }
