"""Map raw upstream JSON items to Impulse-schema asset dicts using a declarative
field mapping. JMESPath is the single expression language.

The engine is intentionally side-effect-free and accepts plain dicts so it is
trivially unit-testable against fixture JSON.
"""

from __future__ import annotations

import logging
from typing import Any

import jmespath

from app.config.schema import FieldMapping, FilterCfg, MappingCfg
from app.transform.helpers import slugify, strip_html

logger = logging.getLogger(__name__)


_TRANSFORMS = {
    "slugify": slugify,
    "strip_html": strip_html,
    "lower": lambda s: s.lower() if isinstance(s, str) else s,
    "upper": lambda s: s.upper() if isinstance(s, str) else s,
}


def _evaluate_field(item: dict, fm: FieldMapping) -> Any:
    """Run one FieldMapping against one raw item and return the resolved value
    (possibly None)."""
    if fm.literal is not None:
        value: Any = fm.literal
    elif fm.expr:
        value = jmespath.search(fm.expr, item)
    else:
        value = None

    if value in (None, "", [], {}) and fm.default is not None:
        value = fm.default

    if fm.map and isinstance(value, str) and value in fm.map:
        value = fm.map[value]

    if fm.transform and value is not None:
        transformer = _TRANSFORMS.get(fm.transform)
        if transformer is not None and isinstance(value, str):
            value = transformer(value)

    return value


def transform_item(
    raw: dict,
    mapping: MappingCfg,
    filter_cfg: FilterCfg,
) -> dict | None:
    """Map one raw upstream item to an Impulse asset dict. Returns None when the
    item is dropped due to a filter rule. Never raises on a single bad item —
    callers can keep going through the rest of the upstream list."""
    asset: dict[str, Any] = {}
    try:
        for field_name, fm in mapping.fields.items():
            value = _evaluate_field(raw, fm)
            if value is not None:
                asset[field_name] = value
    except Exception as e:
        logger.warning("Mapping failure for item — skipping. error=%s", e)
        return None

    for required in filter_cfg.drop_if_missing:
        if not asset.get(required):
            return None

    if filter_cfg.allowed_content_types:
        ct = asset.get("contentType")
        if ct not in filter_cfg.allowed_content_types:
            return None

    return asset


def extract_items(raw_response: Any, items_path: str) -> list[dict]:
    """Resolve `items_path` against the upstream response and normalize to list."""
    if not items_path:
        return raw_response if isinstance(raw_response, list) else [raw_response]
    result = jmespath.search(items_path, raw_response)
    if result is None:
        return []
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if isinstance(result, dict):
        return [result]
    return []
