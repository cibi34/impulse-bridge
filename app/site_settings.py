"""Settings an administrator edits in the admin UI (stored in SQLite):
where submissions go, and the SMTP account for login and edit-link emails.

The SMTP password is write-only through the API. Operators who prefer not to
keep it in the database set BRIDGE_SMTP_PASSWORD instead, which wins.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.curation.db import Database
from app.settings import settings


class SiteSettings(BaseModel):
    submission_email: str = Field("", max_length=254)
    """Where "Submit to IMPULSE" emails go (the team that registers collections)."""
    smtp_host: str = Field("", max_length=255)
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = Field("", max_length=255)
    smtp_password: str = Field("", max_length=1024)
    mail_from: str = Field("", max_length=320)
    """Sender, e.g. "IMPULSE Curator <curator@example.org>"."""

    @property
    def effective_smtp_password(self) -> str:
        return settings.smtp_password or self.smtp_password

    @property
    def mail_configured(self) -> bool:
        return bool(self.smtp_host and self.mail_from)


_FIELDS = tuple(SiteSettings.model_fields)


class SiteSettingsStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def load(self) -> SiteSettings:
        with self.db.read() as conn:
            rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
        values = {row["key"]: json.loads(row["value"]) for row in rows if row["key"] in _FIELDS}
        return SiteSettings.model_validate(values)

    def save(self, changes: dict) -> SiteSettings:
        """Validate the merged result first, then store only `changes`."""
        merged = SiteSettings.model_validate({**self.load().model_dump(), **changes})
        with self.db.transaction() as conn:
            for key in changes:
                conn.execute(
                    "INSERT INTO site_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(getattr(merged, key))),
                )
        return merged
