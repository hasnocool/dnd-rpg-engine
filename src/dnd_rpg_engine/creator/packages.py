from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from pydantic import BaseModel, Field

from dnd_rpg_engine.creator.content import ContentPack

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, order=True, slots=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _SEMVER.match(value.strip())
        if not match:
            raise ValueError(f"invalid semantic version: {value}")
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4) or "")

    def __str__(self) -> str:
        suffix = f"-{self.prerelease}" if self.prerelease else ""
        return f"{self.major}.{self.minor}.{self.patch}{suffix}"


class VersionConstraint:
    def __init__(self, expression: str = "*") -> None:
        self.expression = expression.strip() or "*"
        self.tests = self._parse(self.expression)

    def allows(self, version: Version | str) -> bool:
        candidate = Version.parse(version) if isinstance(version, str) else version
        return all(test(candidate) for test in self.tests)

    @staticmethod
    def _parse(expression: str):
        if expression in {"*", "latest"}:
            return [lambda _: True]
        tests = []
        for part in [item.strip() for item in expression.split(",") if item.strip()]:
            if part.startswith("^"):
                base = Version.parse(_normalize(part[1:]))
                upper = Version(base.major + 1, 0, 0) if base.major > 0 else Version(0, base.minor + 1, 0)
                tests.extend([lambda value, base=base: value >= base, lambda value, upper=upper: value < upper])
                continue
            if part.startswith("~"):
                base = Version.parse(_normalize(part[1:]))
                upper = Version(base.major, base.minor + 1, 0)
                tests.extend([lambda value, base=base: value >= base, lambda value, upper=upper: value < upper])
                continue
            for operator in (">=", "<=", ">", "<", "==", "="):
                if part.startswith(operator):
                    base = Version.parse(_normalize(part[len(operator):]))
                    tests.append(_comparison(operator, base))
                    break
            else:
                if "*" in part:
                    pieces = part.split(".")
                    prefix = tuple(int(piece) for piece in pieces if piece != "*")
                    tests.append(lambda value, prefix=prefix: (value.major, value.minor, value.patch)[: len(prefix)] == prefix)
                else:
                    base = Version.parse(_normalize(part))
                    tests.append(lambda value, base=base: value == base)
        return tests


class DependencySpec(BaseModel):
    package_id: str
    constraint: str = "*"
    optional: bool = False


class PackageRelease(BaseModel):
    package_id: str
    version: str
    content_hash: str
    engine_constraint: str = ">=1.0.0"
    dependencies: list[DependencySpec] = Field(default_factory=list)
    ruleset_constraints: dict[str, str] = Field(default_factory=dict)
    migrations_from: set[str] = Field(default_factory=set)
    metadata: dict[str, object] = Field(default_factory=dict)

    @property
    def parsed_version(self) -> Version:
        return Version.parse(self.version)

    @classmethod
    def from_pack(cls, pack: ContentPack) -> "PackageRelease":
        return cls(
            package_id=pack.manifest.id,
            version=pack.manifest.version,
            content_hash=pack.content_hash(),
            engine_constraint=pack.manifest.engine_version,
            dependencies=[
                DependencySpec(package_id=package_id, constraint=constraint)
                for package_id, constraint in sorted(pack.manifest.dependencies.items())
            ],
        )


class LockedPackage(BaseModel):
    package_id: str
    version: str
    content_hash: str
    dependencies: dict[str, str] = Field(default_factory=dict)


class PackageLock(BaseModel):
    format_version: int = 1
    engine_version: str
    packages: dict[str, LockedPackage]

    def canonical_lines(self) -> list[str]:
        lines = [f"engine={self.engine_version}"]
        for package_id in sorted(self.packages):
            value = self.packages[package_id]
            lines.append(f"{package_id}=={value.version}#{value.content_hash}")
        return lines


class ResolutionError(ValueError):
    pass


class PackageRepository:
    def __init__(self, releases: Iterable[PackageRelease] = ()) -> None:
        self.releases: dict[str, list[PackageRelease]] = {}
        for release in releases:
            self.add(release)

    def add(self, release: PackageRelease) -> None:
        bucket = self.releases.setdefault(release.package_id, [])
        bucket[:] = [value for value in bucket if value.version != release.version]
        bucket.append(release)
        bucket.sort(key=lambda value: value.parsed_version, reverse=True)

    def candidates(self, package_id: str, constraint: str, *, engine_version: str) -> list[PackageRelease]:
        wanted = VersionConstraint(constraint)
        engine = Version.parse(engine_version)
        return [
            release
            for release in self.releases.get(package_id, [])
            if wanted.allows(release.parsed_version) and VersionConstraint(release.engine_constraint).allows(engine)
        ]


class DependencyResolver:
    def __init__(self, repository: PackageRepository) -> None:
        self.repository = repository

    def resolve(self, requirements: dict[str, str], *, engine_version: str) -> PackageLock:
        constraints: dict[str, list[str]] = {key: [value] for key, value in sorted(requirements.items())}
        selected: dict[str, PackageRelease] = {}

        def solve() -> bool:
            unresolved = sorted(package_id for package_id in constraints if package_id not in selected)
            if not unresolved:
                return True
            package_id = unresolved[0]
            combined = constraints[package_id]
            candidates = self.repository.releases.get(package_id, [])
            for candidate in candidates:
                if not all(VersionConstraint(value).allows(candidate.parsed_version) for value in combined):
                    continue
                if not VersionConstraint(candidate.engine_constraint).allows(engine_version):
                    continue
                selected[package_id] = candidate
                added: list[tuple[str, str]] = []
                failed = False
                for dependency in candidate.dependencies:
                    if dependency.optional and dependency.package_id not in self.repository.releases:
                        continue
                    if dependency.package_id not in self.repository.releases:
                        failed = True
                        break
                    constraints.setdefault(dependency.package_id, []).append(dependency.constraint)
                    added.append((dependency.package_id, dependency.constraint))
                    existing = selected.get(dependency.package_id)
                    if existing and not VersionConstraint(dependency.constraint).allows(existing.parsed_version):
                        failed = True
                        break
                if not failed and solve():
                    return True
                for dep_id, dep_constraint in reversed(added):
                    constraints[dep_id].remove(dep_constraint)
                    if not constraints[dep_id]:
                        constraints.pop(dep_id)
                selected.pop(package_id, None)
            return False

        if not solve():
            detail = ", ".join(f"{key}:{' & '.join(value)}" for key, value in sorted(constraints.items()))
            raise ResolutionError(f"unable to resolve content dependency graph: {detail}")
        locked = {
            package_id: LockedPackage(
                package_id=package_id,
                version=release.version,
                content_hash=release.content_hash,
                dependencies={value.package_id: value.constraint for value in release.dependencies},
            )
            for package_id, release in sorted(selected.items())
        }
        return PackageLock(engine_version=engine_version, packages=locked)


class MigrationStep(BaseModel):
    package_id: str
    from_version: str
    to_version: str
    compatible: bool
    reason: str = ""


class PackageUpgradePlan(BaseModel):
    current: PackageLock
    target: PackageLock
    steps: list[MigrationStep]
    safe: bool


class PackagePlanner:
    def __init__(self, repository: PackageRepository) -> None:
        self.repository = repository

    def plan(self, current: PackageLock, target: PackageLock) -> PackageUpgradePlan:
        steps: list[MigrationStep] = []
        for package_id in sorted(set(current.packages) | set(target.packages)):
            before = current.packages.get(package_id)
            after = target.packages.get(package_id)
            if before is None or after is None or before.version == after.version:
                continue
            release = next(
                (value for value in self.repository.releases.get(package_id, []) if value.version == after.version),
                None,
            )
            compatible = bool(release and (not release.migrations_from or before.version in release.migrations_from))
            steps.append(
                MigrationStep(
                    package_id=package_id,
                    from_version=before.version,
                    to_version=after.version,
                    compatible=compatible,
                    reason="migration declared" if compatible else "target release does not declare a migration from installed version",
                )
            )
        return PackageUpgradePlan(current=current, target=target, steps=steps, safe=all(step.compatible for step in steps))


def _normalize(value: str) -> str:
    parts = value.strip().split(".")
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def _comparison(operator: str, base: Version):
    if operator == ">=":
        return lambda value: value >= base
    if operator == "<=":
        return lambda value: value <= base
    if operator == ">":
        return lambda value: value > base
    if operator == "<":
        return lambda value: value < base
    return lambda value: value == base
