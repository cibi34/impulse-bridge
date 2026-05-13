from typing import Protocol, runtime_checkable


@runtime_checkable
class Source(Protocol):
    """A source presents a single Impulse-compatible collection backed by some adapter."""

    collection_meta: dict
    """Impulse collection metadata: id, uri, name, description, organization, owner_id, published."""

    async def search(
        self, query: str | None, offset: int, count: int | None
    ) -> list[dict]:
        """Return a list of Impulse-schema asset dicts."""
        ...

    async def get_asset(self, asset_id: str) -> dict:
        """Return a single Impulse-schema asset dict, or raise AssetNotFound."""
        ...
