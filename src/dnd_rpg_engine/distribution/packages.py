from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Any

from pydantic import BaseModel, Field

_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?$")


@total_ordering
@dataclass(frozen=True, slots=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        match = _SEMVER_RE.match(value.strip())
        if not match:
            raise ValueError(f"invalid semantic version: {value}")
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4) or "")

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.prerelease}" if self.prerelease else base

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        core = (self.major, self.minor, self.patch)
        other_core = (other.major, other.minor, other.patch)
        if core != other_core:
            return core < other_core
        if not self.prerelease:
            return False if not other.prerelease else False
        if not other.prerelease:
            return True
        return self._prerelease_key() < other._prerelease_key()

    def _prerelease_key(self) -> tuple[tuple[int, int | str], ...]:
        return tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in self.prerelease.split(".")
        )


class VersionConstraint(BaseModel):
    expression: str = "*"

    def matches(self, version: str | SemanticVersion) -> bool:
        candidate = SemanticVersion.parse(version) if isinstance(version, str) else version
        clauses = [part.strip() for part in self.expression.split(",") if part.strip()]
        if not clauses or clauses == ["*"]:
            return True
        return all(self._clause(candidate, clause) for clause in clauses)

    @staticmethod
    def _clause(candidate: SemanticVersion, clause: str) -> bool:
        if clause == "*":
            return True
        if clause.startswith("^"):
            base = SemanticVersion.parse(clause[1:])
            upper = SemanticVersion(base.major + 1, 0, 0) if base.major else SemanticVersion(0, base.minor + 1, 0)
            return base <= candidate < upper
        if clause.startswith("~"):
            base = SemanticVersion.parse(clause[1:])
            upper = SemanticVersion(base.major, base.minor + 1, 0)
            return base <= candidate < upper
        for operator in (">=", "<=", ">", "<", "=="):
            if clause.startswith(operator):
                expected = SemanticVersion.parse(clause[len(operator):].strip())
                return {
                    ">=": candidate >= expected,
                    "<=": candidate <= expected,
                    ">": candidate > expected,
                    "<": candidate < expected,
                    "==": candidate == expected,
                }[operator]
        return candidate == SemanticVersion.parse(clause)


class PackageSignature(BaseModel):
    algorithm: str = "hmac-sha256"
    key_id: str
    signature: str


class HMACPackageSigner:
    """Small built-in signer for private registries and deterministic tests.

    Public registries can implement an asymmetric signer behind the same
    ``sign``/``verify`` shape without changing package metadata.
    """

    algorithm = "hmac-sha256"

    def __init__(self, key_id: str, secret: bytes) -> None:
        if not key_id:
            raise ValueError("signing key id is required")
        if len(secret) < 16:
            raise ValueError("signing secret must be at least 16 bytes")
        self.key_id = key_id
        self.secret = secret

    def sign(self, payload: bytes) -> PackageSignature:
        signature = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()
        return PackageSignature(algorithm=self.algorithm, key_id=self.key_id, signature=signature)

    def verify(self, payload: bytes, signature: PackageSignature) -> bool:
        if signature.algorithm != self.algorithm or signature.key_id != self.key_id:
            return False
        expected = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.signature)


class PackageRelease(BaseModel):
    package_id: str
    version: str
    content_hash: str
    engine_requirement: str = ">=1.0.0"
    dependencies: dict[str, str] = Field(default_factory=dict)
    signature: PackageSignature | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def semver(self) -> SemanticVersion:
        return SemanticVersion.parse(self.version)

    def signing_payload(self) -> bytes:
        rows = [
            self.package_id,
            self.version,
            self.content_hash,
            self.engine_requirement,
            *[f"{key}={value}" for key, value in sorted(self.dependencies.items())],
        ]
        return "\n".join(rows).encode()


class DependencyResolution(BaseModel):
    releases: dict[str, PackageRelease]
    order: list[str]
    lock_hash: str


class ContentDistributionIndex:
    def __init__(self) -> None:
        self.releases: dict[str, dict[str, PackageRelease]] = {}

    def publish(self, release: PackageRelease, *, artifact: bytes | None = None) -> None:
        if artifact is not None:
            digest = hashlib.sha256(artifact).hexdigest()
            if digest != release.content_hash:
                raise ValueError("package artifact hash does not match release metadata")
        SemanticVersion.parse(release.version)
        self.releases.setdefault(release.package_id, {})[release.version] = release

    def versions(self, package_id: str) -> list[str]:
        versions = list(self.releases.get(package_id, {}))
        return [str(value) for value in sorted((SemanticVersion.parse(version) for version in versions), reverse=True)]

    def latest(self, package_id: str, constraint: str = "*") -> PackageRelease | None:
        matcher = VersionConstraint(expression=constraint)
        candidates = [
            release
            for release in self.releases.get(package_id, {}).values()
            if matcher.matches(release.version)
        ]
        return max(candidates, key=lambda release: release.semver(), default=None)

    def resolve(
        self,
        requirements: dict[str, str],
        *,
        engine_version: str,
    ) -> DependencyResolution:
        constraints: dict[str, list[VersionConstraint]] = {
            package_id: [VersionConstraint(expression=expression)]
            for package_id, expression in sorted(requirements.items())
        }
        selected: dict[str, PackageRelease] = {}
        pending = list(sorted(requirements))
        iterations = 0
        while pending:
            iterations += 1
            if iterations > 10_000:
                raise RuntimeError("dependency resolution exceeded deterministic iteration budget")
            package_id = pending.pop(0)
            matchers = constraints.get(package_id, [VersionConstraint()])
            candidates = [
                release
                for release in self.releases.get(package_id, {}).values()
                if all(matcher.matches(release.version) for matcher in matchers)
                and VersionConstraint(expression=release.engine_requirement).matches(engine_version)
            ]
            if not candidates:
                expressions = ", ".join(matcher.expression for matcher in matchers)
                raise ValueError(f"no compatible release for {package_id}: {expressions}")
            chosen = max(candidates, key=lambda release: release.semver())
            previous = selected.get(package_id)
            if previous is not None and previous.version == chosen.version:
                continue
            selected[package_id] = chosen
            for dependency_id, expression in sorted(chosen.dependencies.items()):
                constraints.setdefault(dependency_id, []).append(VersionConstraint(expression=expression))
                if dependency_id not in pending:
                    pending.append(dependency_id)
            pending.sort()

        order = self._topological_order(selected)
        lock_rows = [f"{package_id}@{selected[package_id].version}#{selected[package_id].content_hash}" for package_id in order]
        lock_hash = hashlib.sha256("\n".join(lock_rows).encode()).hexdigest()
        return DependencyResolution(releases=selected, order=order, lock_hash=lock_hash)

    def update_plan(
        self,
        installed: dict[str, str],
        *,
        engine_version: str,
    ) -> dict[str, PackageRelease]:
        upgrades: dict[str, PackageRelease] = {}
        for package_id, current in sorted(installed.items()):
            current_version = SemanticVersion.parse(current)
            compatible = [
                release
                for release in self.releases.get(package_id, {}).values()
                if VersionConstraint(expression=release.engine_requirement).matches(engine_version)
            ]
            newest = max(compatible, key=lambda release: release.semver(), default=None)
            if newest is not None and newest.semver() > current_version:
                upgrades[package_id] = newest
        return upgrades

    @staticmethod
    def verify_release_signature(release: PackageRelease, signer: HMACPackageSigner) -> bool:
        return release.signature is not None and signer.verify(release.signing_payload(), release.signature)

    @staticmethod
    def _topological_order(selected: dict[str, PackageRelease]) -> list[str]:
        temporary: set[str] = set()
        permanent: set[str] = set()
        order: list[str] = []

        def visit(package_id: str) -> None:
            if package_id in permanent:
                return
            if package_id in temporary:
                raise ValueError(f"cyclic package dependency at {package_id}")
            temporary.add(package_id)
            release = selected[package_id]
            for dependency_id in sorted(release.dependencies):
                if dependency_id in selected:
                    visit(dependency_id)
            temporary.remove(package_id)
            permanent.add(package_id)
            order.append(package_id)

        for package_id in sorted(selected):
            visit(package_id)
        return order
