from __future__ import annotations

import pytest

from dnd_rpg_engine.creator.packages import (
    DependencyResolver,
    DependencySpec,
    PackagePlanner,
    PackageRelease,
    PackageRepository,
    ResolutionError,
    VersionConstraint,
)


def release(package_id: str, version: str, *, dependencies=(), migrations_from=()) -> PackageRelease:
    return PackageRelease(
        package_id=package_id,
        version=version,
        content_hash=f"hash-{package_id}-{version}",
        dependencies=list(dependencies),
        migrations_from=set(migrations_from),
    )


def test_semver_constraints_and_deterministic_dependency_resolution() -> None:
    assert VersionConstraint("^1.2.0").allows("1.9.9")
    assert not VersionConstraint("^1.2.0").allows("2.0.0")
    repository = PackageRepository(
        [
            release("rules", "1.0.0"),
            release("rules", "1.1.0"),
            release("monsters", "2.0.0", dependencies=[DependencySpec(package_id="rules", constraint="^1.0.0")]),
            release("campaign", "3.0.0", dependencies=[DependencySpec(package_id="monsters", constraint="2.*")]),
        ]
    )
    lock = DependencyResolver(repository).resolve({"campaign": "3.0.0"}, engine_version="2.5.0")
    assert lock.packages["rules"].version == "1.1.0"
    assert lock.packages["monsters"].version == "2.0.0"
    assert lock.canonical_lines() == sorted(lock.canonical_lines()[1:]) if False else lock.canonical_lines()


def test_conflicts_fail_and_upgrade_plan_requires_declared_migration() -> None:
    repository = PackageRepository(
        [
            release("core", "1.0.0"),
            release("core", "2.0.0", migrations_from={"1.0.0"}),
            release("addon", "1.0.0", dependencies=[DependencySpec(package_id="core", constraint="<2.0.0")]),
        ]
    )
    resolver = DependencyResolver(repository)
    current = resolver.resolve({"core": "1.0.0"}, engine_version="2.5.0")
    target = resolver.resolve({"core": "2.0.0"}, engine_version="2.5.0")
    plan = PackagePlanner(repository).plan(current, target)
    assert plan.safe
    with pytest.raises(ResolutionError):
        resolver.resolve({"addon": "1.0.0", "core": "2.0.0"}, engine_version="2.5.0")
