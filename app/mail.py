"""Outgoing email (login links, edit links, test messages) over SMTP.

The account is configured in the admin UI (app/site_settings.py). With
BRIDGE_MAIL_LOG_ONLY=true, messages are written to the log instead — for
local development, where the login link can be copied from the console.
"""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr

from starlette.concurrency import run_in_threadpool

from app.settings import settings
from app.site_settings import SiteSettings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15


class MailError(Exception):
    """Sending failed; the message is safe to show to an administrator."""


def mail_available(site: SiteSettings) -> bool:
    return settings.mail_log_only or site.mail_configured


def build_message(
    site: SiteSettings,
    to: str,
    subject: str,
    paragraphs: list[str],
    link: tuple[str, str] | None = None,
) -> EmailMessage:
    """A plain message with an optional call-to-action link; text and HTML parts."""
    msg = EmailMessage()
    msg["From"] = site.mail_from or "IMPULSE Curator <noreply@localhost>"
    msg["To"] = to
    msg["Subject"] = subject
    _, sender = parseaddr(site.mail_from)
    msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[1] if "@" in sender else None)

    text = "\n\n".join(paragraphs)
    if link is not None:
        label, url = link
        text += f"\n\n{label}:\n{url}"
    text += "\n\n— IMPULSE Curator"
    msg.set_content(text)

    body = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    if link is not None:
        label, url = link
        body += (
            f'<p><a href="{html.escape(url, quote=True)}" style="display:inline-block;padding:12px 20px;'
            f'border-radius:999px;background:#d10a7d;color:#ffffff;text-decoration:none;font-weight:600">'
            f"{html.escape(label)}</a></p>"
            f'<p style="color:#6e6e76;font-size:13px">Or paste this link into your browser:<br>{html.escape(url)}</p>'
        )
    msg.add_alternative(
        '<!doctype html><html><body style="font-family:-apple-system,Segoe UI,sans-serif;'
        f'font-size:15px;line-height:1.5;color:#1d1d1f">{body}'
        '<p style="color:#6e6e76;font-size:13px">— IMPULSE Curator</p></body></html>',
        subtype="html",
    )
    return msg


def _send_sync(site: SiteSettings, msg: EmailMessage) -> None:
    if settings.mail_log_only:
        text = msg.get_body(("plain",)).get_content()
        logger.warning("Mail (log only) to %s — %s\n%s", msg["To"], msg["Subject"], text)
        return
    if not site.mail_configured:
        raise MailError("Email is not configured (SMTP host and sender are required)")
    password = site.effective_smtp_password
    try:
        if site.smtp_security == "ssl":
            server = smtplib.SMTP_SSL(
                site.smtp_host, site.smtp_port,
                timeout=SMTP_TIMEOUT_SECONDS, context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(site.smtp_host, site.smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if site.smtp_security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if site.smtp_username:
                server.login(site.smtp_username, password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise MailError("The SMTP server rejected the username or password") from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Could not send email: {e}") from e


async def send(site: SiteSettings, msg: EmailMessage) -> None:
    await run_in_threadpool(_send_sync, site, msg)
