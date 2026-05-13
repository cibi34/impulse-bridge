"""Pydantic models for the per-source YAML config files.

Each YAML file under configs/sources/*.yaml is validated against `SourceConfig`.
Validation runs at startup and is fail-fast: invalid configs prevent the app
from starting so misconfigurations surface immediately.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class CollectionMeta(BaseModel):
    """Impulse collection metadata published via /collections."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None
    organization: str
    owner_id: str
    published: int = 1

    @field_validator("id")
    @classmethod
    def _id_schema(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(
                f"collection.id '{v}' must follow id-schema (lowercase, digits, hyphens, "
                "starting with letter/digit)"
            )
        return v


class AuthCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["none", "query_param", "header"] = "none"
    name: str | None = None
    value: str | None = None


class AdapterCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["rest", "fallback", "custom"]
    base_url: str | None = None
    auth: AuthCfg = Field(default_factory=AuthCfg)
    timeout_seconds: float = 10.0
    default_query: dict[str, str] = Field(default_factory=dict)

    # Fallback-specific
    manifest_path: str | None = None
    static_mount: bool = True
    """If True, the bridge mounts the manifest's parent directory at the collection's
    URI path so relative assetURIs/previewURIs resolve correctly."""

    # Custom-specific
    custom_class: str | None = None
    """For kind=custom: dotted Python path to a Source class."""


class PaginationCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Literal["page_size", "offset_limit", "cursor", "none"] = "offset_limit"
    page_param: str | None = None
    size_param: str | None = None
    offset_param: str | None = None
    limit_param: str | None = None
    cursor_param: str | None = None
    cursor_response_path: str | None = None
    page_base: int = 0
    max_size: int = 100


class WildcardCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_: str = Field(default="*", alias="from")
    to: str = "*"


class QueryCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_param: str | None = None
    pattern_when_empty: str = ""
    wildcard_translation: WildcardCfg = Field(default_factory=WildcardCfg)


class SearchCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = ""
    method: Literal["GET", "POST"] = "GET"
    pagination: PaginationCfg = Field(default_factory=PaginationCfg)
    query: QueryCfg = Field(default_factory=QueryCfg)


class FieldMapping(BaseModel):
    """Mapping for a single Impulse asset field.

    Exactly one of `expr` or `literal` must be set. Optional modifiers (default,
    transform, map) apply post-extraction.
    """
    model_config = ConfigDict(extra="forbid")

    expr: str | None = None
    """JMESPath expression evaluated against the raw item dict."""
    literal: Any | None = None
    """A constant value to use directly."""
    default: Any | None = None
    """Fallback if the JMESPath result is None or empty."""
    transform: Literal["slugify", "strip_html", "lower", "upper"] | None = None
    map: dict[str, Any] | None = None
    """Value-to-value mapping (e.g. {"IMAGE": "image/jpeg"})."""


class MappingCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items_path: str = ""
    """JMESPath to the list of raw items in the upstream response."""
    total_path: str | None = None
    fields: dict[str, FieldMapping] = Field(default_factory=dict)


class FilterCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_content_types: list[str] = Field(default_factory=list)
    """If non-empty, drop any asset whose `contentType` is not in this list."""
    drop_if_missing: list[str] = Field(default_factory=list)
    """List of Impulse-schema field names; drop the asset if any are missing/empty."""


class AssetDetailCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    path: str | None = None
    """URL path template with {asset_id} placeholder."""
    query: dict[str, str] = Field(default_factory=dict)
    """Detail-endpoint query params. Values may contain {asset_id} which will be
    substituted at lookup time. These are merged onto adapter.default_query."""
    mapping: MappingCfg | None = None
    """If None, the search-mapping is reused (with items_path treated as identity)."""


class CacheCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ttl_seconds: int | None = None


class SourceConfig(BaseModel):
    """Top-level YAML schema for one external source."""
    model_config = ConfigDict(extra="forbid")

    collection: CollectionMeta
    adapter: AdapterCfg
    search: SearchCfg = Field(default_factory=SearchCfg)
    mapping: MappingCfg = Field(default_factory=MappingCfg)
    filter: FilterCfg = Field(default_factory=FilterCfg)
    asset_detail: AssetDetailCfg = Field(default_factory=AssetDetailCfg)
    cache: CacheCfg = Field(default_factory=CacheCfg)
