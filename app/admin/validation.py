"""Validate source-config YAML text and point errors at their line.

Schema errors come from Pydantic as a path (["search", "pagination",
"style"]); the YAML node tree knows where each key is, so every error gets
the line of the deepest key on its path that exists in the text.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import ValidationError

from app.config.loader import _expand_env
from app.config.schema import SourceConfig


def _line_of(text: str, loc: list[Any]) -> int | None:
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return None
    line = None
    for key in loc:
        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                if key_node.value == str(key):
                    line = key_node.start_mark.line + 1
                    node = value_node
                    break
            else:
                break
        elif isinstance(node, yaml.SequenceNode) and isinstance(key, int) and key < len(node.value):
            node = node.value[key]
            line = node.start_mark.line + 1
        else:
            break
    return line


def validate_text(text: str) -> dict[str, Any]:
    """{valid, errors: [{loc, msg, line}], parsed, id} — never raises."""
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        problem = getattr(e, "problem", None) or str(e)
        return {
            "valid": False,
            "errors": [{"loc": [], "msg": f"YAML syntax: {problem}", "line": mark.line + 1 if mark else None}],
            "parsed": None,
            "id": None,
        }
    if not isinstance(parsed, dict):
        return {
            "valid": False,
            "errors": [{"loc": [], "msg": "The file must be a YAML mapping (key: value)", "line": 1}],
            "parsed": None,
            "id": None,
        }
    collection = parsed.get("collection")
    raw_id = collection.get("id") if isinstance(collection, dict) else None
    source_id = str(raw_id) if raw_id is not None else None
    try:
        SourceConfig.model_validate(_expand_env(parsed))
    except ValidationError as e:
        errors = [
            {"loc": list(err["loc"]), "msg": err["msg"], "line": _line_of(text, list(err["loc"]))}
            for err in e.errors()
        ]
        return {"valid": False, "errors": errors, "parsed": parsed, "id": source_id}
    return {"valid": True, "errors": [], "parsed": parsed, "id": source_id}
