"""Pure helpers used by the transform engine and adapters."""

from __future__ import annotations

import base64
import binascii
import html
import mimetypes
import re
from urllib.parse import urlparse

_SLUG_REPLACE = re.compile(r"[^a-z0-9]+")
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


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


_IIIF_INFO = re.compile(r"/info\.json$")
_IIIF_IMAGE_REQUEST = re.compile(
    r"/(?:full|square|pct:[\d.,]+|[\d,]+)/(?:full|max|\^?!?[\d,]*|pct:[\d.]+)/\d+/"
    r"(?:default|color|gray|bitonal|native)\.\w+$"
)


def iiif_image_base(url: str) -> str:
    """The Image API base of `url`: an info.json or any sized image request
    is cut back to the identifier, so a new size can be asked for."""
    base = _IIIF_INFO.sub("", url.strip())
    return _IIIF_IMAGE_REQUEST.sub("", base).rstrip("/")


def iiif_large(url: str) -> str:
    """A JPEG of at most 2048 px on the longer side: what Unity loads."""
    return f"{iiif_image_base(url)}/full/!2048,2048/0/default.jpg" if url else url


def iiif_preview(url: str) -> str:
    """A JPEG of at most 400 px: what the cards show."""
    return f"{iiif_image_base(url)}/full/!400,400/0/default.jpg" if url else url


def strip_html(value: str) -> str:
    """Drop tags, decode entities ("&nbsp;", "&amp;"), collapse whitespace."""
    if not value:
        return value
    text = html.unescape(_HTML_TAG.sub(" ", value))
    return _WHITESPACE.sub(" ", text).strip()


_FILE_PREFIX = re.compile(r"^(file|image|datei):\s*", re.IGNORECASE)
_FILE_EXTENSION = re.compile(
    r"\.(jpe?g|png|gif|tiff?|webp|svg|bmp|jp2|pdf|djvu|glb|gltf|obj|stl|ply|fbx|usdz"
    r"|ogg|ogv|oga|webm|mp3|mp4|wav|flac|midi?)$",
    re.IGNORECASE,
)


def file_title(value: str) -> str:
    """Turn a media file name into a readable title: drop a MediaWiki-style
    namespace prefix and the extension, and use spaces for underscores.
    "File:1665 Girl_with a Pearl Earring.jpg" -> "1665 Girl with a Pearl Earring"."""
    if not value:
        return value
    title = _FILE_PREFIX.sub("", value.strip())
    title = _FILE_EXTENSION.sub("", title).replace("_", " ")
    return " ".join(title.split()) or value


ASSET_TEXT_FIELDS = ("title", "description", "subject", "creator", "contributor", "type", "assetID")
"""Impulse asset fields that local search (fallback sources, curated
collections) looks at."""


def matches_pattern(
    asset: dict, pattern: str | None, fields: tuple[str, ...] = ASSET_TEXT_FIELDS
) -> bool:
    """Case-insensitive search across the asset's text `fields`.

    An empty pattern or "*" matches everything. Inner "*" wildcards separate
    chunks that must all appear, in order ("van*sun" matches "van Gogh,
    Sunflowers")."""
    pattern = (pattern or "").strip()
    if not pattern or pattern == "*":
        return True
    chunks = [c.lower() for c in pattern.split("*") if c]
    haystack = " | ".join(
        v.lower() for v in (asset.get(k) for k in fields) if isinstance(v, str)
    )
    pos = 0
    for chunk in chunks:
        idx = haystack.find(chunk, pos)
        if idx < 0:
            return False
        pos = idx + len(chunk)
    return True


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
