# src/dnd_rpg_engine/creator/marketplace.py
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from dnd_rpg_engine.creator.content import ContentPack


class MarketplaceItem(BaseModel):
    id: str
    pack_id: str
    title: str
    description: str = ""
    author: str = "unknown"
    version: str
    license: str = "unspecified"
    content_hash: str
    tags: set[str] = Field(default_factory=set)
    downloads: int = Field(default=0, ge=0)
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    moderation_status: str = "unreviewed"


class MarketplaceRegistry:
    """Community metadata registry. Payment processing is intentionally external."""

    def __init__(self) -> None:
        self.items: dict[str, MarketplaceItem] = {}
        self.packs: dict[str, ContentPack] = {}

    def publish(self, pack: ContentPack, *, description: str | None = None) -> MarketplaceItem:
        item_id = f"{pack.manifest.id}@{pack.manifest.version}"
        item = MarketplaceItem(
            id=item_id,
            pack_id=pack.manifest.id,
            title=pack.manifest.name,
            description=description if description is not None else pack.manifest.description,
            author=pack.manifest.author,
            version=pack.manifest.version,
            license=pack.manifest.license,
            content_hash=pack.content_hash(),
            tags=set(pack.manifest.tags),
        )
        self.items[item_id] = item
        self.packs[item_id] = pack
        return item

    def search(self, query: str = "", *, tags: set[str] | None = None) -> list[MarketplaceItem]:
        q = query.casefold().strip()
        results = []
        for item in self.items.values():
            if q and q not in f"{item.title} {item.description} {item.author}".casefold():
                continue
            if tags and not tags.issubset(item.tags):
                continue
            results.append(item)
        return sorted(results, key=lambda item: (item.downloads, item.published_at), reverse=True)

    def install(self, item_id: str) -> ContentPack:
        if item_id not in self.packs:
            raise KeyError(item_id)
        self.items[item_id].downloads += 1
        return self.packs[item_id].model_copy(deep=True)
