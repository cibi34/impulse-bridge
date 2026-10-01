from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchPage:
    items: list[dict]
    """Mapped assets that passed the source's filter."""
    upstream_count: int
    """How many items the upstream returned for this page, before filtering.
    The next page starts at offset + upstream_count."""
    page_size: int | None
    """The page size actually requested upstream (None: everything)."""

    @property
    def has_more(self) -> bool:
        return self.page_size is not None and self.upstream_count >= self.page_size


@runtime_checkable
class Source(Protocol):
    """An archive the web app searches (Europeana, Wikimedia, a local folder…).
    Adapters may also implement `search_page()` (see `search_page()` below)."""

    collection_meta: dict
    """Metadata of the source: id, name, description, organization, …"""

    async def search(
        self, query: str | None, offset: int, count: int | None
    ) -> list[dict]:
        """Return a list of Impulse-schema asset dicts."""
        ...

    async def get_asset(self, asset_id: str) -> dict:
        """Return a single Impulse-schema asset dict, or raise AssetNotFound."""
        ...


async def search_page(source: Source, query: str | None, offset: int, count: int | None) -> SearchPage:
    """Search one page, with paging information. Sources that filter items
    after fetching (REST) implement `search_page()` themselves; for the
    others the result list is the page."""
    native = getattr(source, "search_page", None)
    if native is not None:
        return await native(query=query, offset=offset, count=count)
    items = await source.search(query=query, offset=offset, count=count)
    return SearchPage(items=items, upstream_count=len(items), page_size=count)
