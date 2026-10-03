"""Licences of archive assets.

Archives state rights in different ways: Europeana as Creative Commons or
rightsstatements.org URIs, Wikimedia as short names ("CC BY-SA 4.0"), IIIF
manifests in `rights` / `license`. `classify()` turns any of them into a
`Licence`: a readable label, a link, and the conditions it attaches.

Which conditions IMPULSE accepts is an admin setting
(`SiteSettings.licence_conditions`). A licence is *allowed* when it is an
open licence and all of its conditions are accepted. Rights that are not an
open licence — in copyright, not evaluated, unknown, other licences — are
never allowed. Allowed or not decides what the web app offers, what can be
added to a collection, and what the Impulse API serves.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

Condition = Literal["by", "sa", "nc", "nd"]
CONDITIONS: tuple[Condition, ...] = ("by", "sa", "nc", "nd")
DEFAULT_CONDITIONS: list[Condition] = ["by", "sa"]
"""Accepted out of the box: public domain, CC0, CC BY and CC BY-SA."""

LicenceTier = Literal["free", "by"]
TIERS: dict[str, frozenset[str]] = {
    "free": frozenset(),  # public domain and CC0: no conditions
    "by": frozenset({"by"}),  # … plus attribution-only licences
}
"""Narrower choices for the web app's licence filter."""

_RIGHTS_STATEMENTS = {
    "InC": "In copyright",
    "InC-OW-EU": "In copyright – EU orphan work",
    "InC-EDU": "In copyright – educational use permitted",
    "InC-NC": "In copyright – non-commercial use permitted",
    "InC-RUU": "In copyright – rights-holder(s) unlocatable",
    "NoC-CR": "No copyright – contractual restrictions",
    "NoC-NC": "No copyright – non-commercial use only",
    "NoC-OKLR": "No copyright – other known legal restrictions",
    "NoC-US": "No copyright – United States",
    "CNE": "Copyright not evaluated",
    "UND": "Copyright undetermined",
    "NKC": "No known copyright",
}

_CC_URL = re.compile(
    r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)(?:/(\d+(?:\.\d+)?))?(?:/([a-z]{2,}))?",
    re.IGNORECASE,
)
_CC_TEXT = re.compile(
    r"^cc[\s-]*(by(?:[\s-]+(?:nc|nd|sa))*)(?:[\s-]+(\d+(?:\.\d+)?))?(?:[\s-]+([a-z]{2,}))?$",
    re.IGNORECASE,
)
_CC0_TEXT = re.compile(r"^cc[\s-]*(?:0|zero)(?:[\s-]+(\d\.\d))?$", re.IGNORECASE)
_PD_TEXT = re.compile(r"^(?:public[\s-]+domain(?:[\s-]+mark)?(?:[\s-]+\d\.\d)?|pdm|pd)$", re.IGNORECASE)
_RS_URL = re.compile(r"rightsstatements\.org/(?:vocab|page)/([A-Za-z-]+)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"^see\b", re.IGNORECASE)


@dataclass(frozen=True)
class Licence:
    code: str
    """"pd", "cc0", "by", "by-sa", "by-nc", "by-nc-sa", "by-nd", "by-nc-nd",
    "noc-nc" — or "other" for everything that is not an open licence."""
    label: str
    url: str | None
    conditions: frozenset[str]

    @property
    def is_open(self) -> bool:
        return self.code != "other"

    def allowed(self, accepted: Iterable[str]) -> bool:
        return self.is_open and self.conditions <= frozenset(accepted)

    def within(self, tier: str | None) -> bool:
        return tier is None or self.conditions <= TIERS[tier]

    def as_dict(self, accepted: Iterable[str]) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "url": self.url,
            "conditions": [c for c in CONDITIONS if c in self.conditions],
            "allowed": self.allowed(accepted),
        }


def _other(label: str, url: str | None = None) -> Licence:
    return Licence("other", label, url, frozenset())


def _cc(kind: str, version: str | None, port: str | None) -> Licence:
    """A CC licence from its parts, e.g. ("by-sa", "3.0", "de")."""
    parts = set(re.split(r"[\s-]+", kind.lower()))
    if "by" not in parts or not parts <= {"by", "sa", "nc", "nd"} or {"sa", "nd"} <= parts:
        return _other(f"CC {kind.upper()}")
    code = "by" + "-nc" * ("nc" in parts) + "-sa" * ("sa" in parts) + "-nd" * ("nd" in parts)
    label = "CC " + code.upper()
    url = None
    if version:
        label += f" {version}"
        url = f"https://creativecommons.org/licenses/{code}/{version}/"
        if port:
            label += f" {port.upper()}"
            url += f"{port.lower()}/"
    return Licence(code, label, url, frozenset(parts))


def _cc0(version: str | None) -> Licence:
    version = version or "1.0"
    return Licence(
        "cc0", f"CC0 {version}", f"https://creativecommons.org/publicdomain/zero/{version}/", frozenset()
    )


def _public_domain(url: str | None = None) -> Licence:
    return Licence("pd", "Public domain", url, frozenset())


def _from_url(text: str) -> Licence:
    if match := _CC_URL.search(text):
        family, kind, version, port = match.groups()
        if family.lower() == "publicdomain":
            if kind.lower() == "zero":
                return _cc0(version)
            return _public_domain("https://creativecommons.org/publicdomain/mark/1.0/")
        return _cc(kind, version, port)
    if match := _RS_URL.search(text):
        statement = match.group(1)
        key = next((k for k in _RIGHTS_STATEMENTS if k.lower() == statement.lower()), statement)
        label = _RIGHTS_STATEMENTS.get(key, statement)
        url = f"https://rightsstatements.org/vocab/{key}/1.0/"
        if key == "NoC-NC":
            return Licence("noc-nc", label, url, frozenset({"nc"}))
        return _other(label, url)
    return _other(text, text)


@lru_cache(maxsize=4096)
def _classify(text: str) -> Licence:
    if not text or _PLACEHOLDER.match(text):
        return _other("Not specified")
    if re.match(r"^https?://", text, re.IGNORECASE):
        return _from_url(text)
    if match := _CC0_TEXT.match(text):
        return _cc0(match.group(1))
    if _PD_TEXT.match(text):
        return _public_domain()
    if match := _CC_TEXT.match(text):
        return _cc(*match.groups())
    return _other(text)


def classify(rights: Any) -> Licence:
    """The licence an asset's `rights` value states."""
    return _classify(str(rights).strip() if rights is not None else "")
