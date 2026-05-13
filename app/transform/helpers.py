"""Pure helpers used by the transform engine and adapters."""

from __future__ import annotations

import mimetypes
import re
from urllib.parse import urlparse

_SLUG_REPLACE = re.compile(r"[^a-z0-9]+")
_HTML_TAG = re.compile(r"<[^>]+>")


def slugify(value: str) -> str:
    """Convert any string to id-schema compliant: lowercase, hyphen-separated.

    Multiple hyphens collapse to one, leading/trailing hyphens are stripped.
    Empty result becomes 'untitled' as a defensive fallback (id-schema requires
    starting with a letter or digit)."""
    if not value:
        return "untitled"
    s = value.lower().strip()
    s = _SLUG_REPLACE.sub("-", s).strip("-")
    return s or "untitled"


def strip_html(value: str) -> str:
    if not value:
        return value
    return _HTML_TAG.sub("", value).strip()


def mime_from_url(url: str, default: str = "application/octet-stream") -> str:
    """Guess MIME type from a URL's path extension."""
    if not url:
        return default
    path = urlparse(url).path
    guessed, _ = mimetypes.guess_type(path)
    return guessed or default
