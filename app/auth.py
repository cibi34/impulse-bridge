"""Passwordless login: a one-time link by email starts a browser session.

Only hashes of login tokens and session ids are stored. The session cookie is
HttpOnly and SameSite=Lax (browsers do not send it with cross-site requests),
and `__Host-` prefixed in production, so no other subdomain can set or read
it. Signed-in users can edit the collections created with their email.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.curation.db import Database
from app.settings import settings

LOGIN_TOKEN_TTL = timedelta(minutes=15)
SESSION_TTL = timedelta(days=30)


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def secure_cookies() -> bool:
    return settings.public_base_url.startswith("https://")


def session_cookie_name() -> str:
    # __Host- cookies must be Secure, Path=/ and have no Domain attribute.
    return "__Host-curator_session" if secure_cookies() else "curator_session"


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---- login tokens ----

    def create_login_token(self, email: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        with self.db.transaction() as conn:
            self._purge(conn, now)
            conn.execute(
                "INSERT INTO login_tokens (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (_hash(token), normalize_email(email), _iso(now), _iso(now + LOGIN_TOKEN_TTL)),
            )
        return token

    def redeem_login_token(self, token: str) -> str | None:
        """The token's email if it is valid; the token can't be used again."""
        now = _iso(_now())
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT email FROM login_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                (_hash(token), now),
            ).fetchone()
            if row is None:
                return None
            conn.execute("UPDATE login_tokens SET used_at = ? WHERE token_hash = ?", (now, _hash(token)))
        return row["email"]

    def recent_login_tokens(self, email: str, within: timedelta) -> int:
        since = _iso(_now() - within)
        with self.db.read() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM login_tokens WHERE email = ? AND created_at > ?",
                (normalize_email(email), since),
            ).fetchone()[0]

    # ---- sessions ----

    def create_session(self, email: str) -> str:
        session_id = secrets.token_urlsafe(32)
        now = _now()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO sessions (id_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (_hash(session_id), normalize_email(email), _iso(now), _iso(now + SESSION_TTL)),
            )
        return session_id

    def session_email(self, session_id: str) -> str | None:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT email FROM sessions WHERE id_hash = ? AND expires_at > ?",
                (_hash(session_id), _iso(_now())),
            ).fetchone()
        return row["email"] if row else None

    def delete_session(self, session_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE id_hash = ?", (_hash(session_id),))

    @staticmethod
    def _purge(conn, now: datetime) -> None:
        stamp = _iso(now)
        conn.execute("DELETE FROM login_tokens WHERE expires_at <= ?", (stamp,))
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (stamp,))
