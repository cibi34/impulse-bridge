"""Pure helpers used by the transform engine and adapters."""

from __future__ import annotations

import base64
import binascii
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


def base32_id(value: str) -> str:
    """Encode any string into an id-schema compliant, fully reversible id.

    Standard base32 (RFC 4648) in lowercase without padding: the alphabet is
    ``a-z2-7``, so the result is valid Impulse id-schema for any input while,
    unlike slugify(), losing nothing. Use it for upstream ids that are not
    id-schema safe AND that must be fed back verbatim to an exact-match detail
    endpoint (see the REST adapter's ``{asset_id_from_base32}`` placeholder).
    Costs: ids become opaque and ~1.6x longer."""
    if not value:
        return "untitled"
    return base64.b32encode(value.encode("utf-8")).decode("ascii").lower().rstrip("=")


def base32_id_decode(value: str) -> str | None:
    """Inverse of base32_id(). Returns None if `value` is not a base32 id."""
    if not value:
        return None
    padded = value.upper() + "=" * (-len(value) % 8)
    try:
        return base64.b32decode(padded).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


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


_SLUG_SEPARATOR_CLASS = "[^a-zA-Z0-9]"


def slug_to_regex(slug: str) -> str:
    """Build a regular expression that matches exactly the strings whose
    ``slugify()`` result equals ``slug`` — i.e. the inverse of slugify.

    slugify() is lossy (case is dropped, every run of non-alphanumerics becomes
    one hyphen), so a slug cannot be turned back into the original id. It can,
    however, be turned into a pattern that the original id — and only ids that
    slugify the same way — will match:

    * a letter matches itself in either case (``a`` -> ``[aA]``)
    * a digit matches itself
    * a hyphen matches one or more non-alphanumeric characters
    * leading / trailing non-alphanumerics are allowed (slugify strips them)

    Example: ``"90402-sk-a-3262"`` matches Europeana's ``"/90402/SK_A_3262"``.

    The pattern only uses character classes and ``+`` / ``*`` quantifiers, so it
    is valid both as a Python regex and as a Lucene/Solr regex (``field:/.../``),
    which is what the REST adapter's ``{asset_id_regex}`` placeholder is for."""
    sep = _SLUG_SEPARATOR_CLASS
    parts: list[str] = []
    for ch in slug:
        if ch == "-":
            parts.append(sep + "+")
        elif "a" <= ch <= "z":
            parts.append(f"[{ch}{ch.upper()}]")
        elif "A" <= ch <= "Z":
            parts.append(f"[{ch.lower()}{ch}]")
        elif "0" <= ch <= "9":
            parts.append(ch)
        else:
            # Not a valid slug character; match it literally rather than fail.
            parts.append(re.escape(ch))
    return f"{sep}*{''.join(parts)}{sep}*"
