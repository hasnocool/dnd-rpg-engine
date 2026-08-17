from __future__ import annotations

from typing import Any, Protocol

from dnd_rpg_engine.creator.content import ContentPack
from dnd_rpg_engine.distribution.packages import ContentDistributionIndex, DependencyResolution, PackageRelease


class JSONStore(Protocol):
    async def put_json(self, namespace: str, key: str, value: Any) -> None: ...
    async def list_json(self, namespace: str) -> dict[str, Any]: ...


class ContentDistributionService:
    """Persistent facade around deterministic package dependency resolution."""

    release_namespace = "distribution.release"
    lock_namespace = "distribution.lock"

    def __init__(self, store: JSONStore) -> None:
        self.store = store

    async def index(self) -> ContentDistributionIndex:
        registry = ContentDistributionIndex()
        rows = await self.store.list_json(self.release_namespace)
        for payload in rows.values():
            try:
                registry.publish(PackageRelease.model_validate(payload))
            except (ValueError, KeyError, TypeError):
                continue
        return registry

    async def publish_release(self, release: PackageRelease) -> PackageRelease:
        registry = await self.index()
        registry.publish(release)
        key = f"{release.package_id}@{release.version}"
        await self.store.put_json(self.release_namespace, key, release.model_dump(mode="json"))
        return release

    async def publish_pack(self, pack: ContentPack) -> PackageRelease:
        release = PackageRelease(
            package_id=pack.manifest.id,
            version=pack.manifest.version,
            content_hash=pack.content_hash(),
            engine_requirement=pack.manifest.engine_version,
            dependencies=dict(pack.manifest.dependencies),
            metadata={
                "name": pack.manifest.name,
                "author": pack.manifest.author,
                "license": pack.manifest.license,
                "tags": sorted(pack.manifest.tags),
            },
        )
        return await self.publish_release(release)

    async def resolve(
        self,
        requirements: dict[str, str],
        *,
        engine_version: str,
        lock_id: str | None = None,
    ) -> DependencyResolution:
        registry = await self.index()
        resolution = registry.resolve(requirements, engine_version=engine_version)
        if lock_id:
            await self.store.put_json(
                self.lock_namespace,
                lock_id,
                {
                    "lock_id": lock_id,
                    "engine_version": engine_version,
                    "requirements": dict(sorted(requirements.items())),
                    "order": resolution.order,
                    "lock_hash": resolution.lock_hash,
                    "releases": {
                        package_id: release.model_dump(mode="json")
                        for package_id, release in sorted(resolution.releases.items())
                    },
                },
            )
        return resolution

    async def locks(self) -> dict[str, Any]:
        return await self.store.list_json(self.lock_namespace)

    async def releases(self, package_id: str | None = None) -> list[PackageRelease]:
        registry = await self.index()
        rows = [
            release
            for current_id, versions in registry.releases.items()
            for release in versions.values()
            if package_id is None or current_id == package_id
        ]
        return sorted(rows, key=lambda value: (value.package_id, value.semver()), reverse=False)
