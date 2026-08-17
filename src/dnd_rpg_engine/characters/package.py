from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import Entity
from .models import CharacterState


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (set, frozenset)):
        items = [_canonicalize(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


class CharacterPackage(BaseModel):
    schema_version: int = 1
    entity: Entity
    character: CharacterState
    metadata: dict[str, Any] = Field(default_factory=dict)
    sha256: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entity": _canonicalize(self.entity.model_dump(mode="python")),
            "character": _canonicalize(self.character.model_dump(mode="python")),
            "metadata": _canonicalize(self.metadata),
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def from_entity(cls, entity: Entity, character: CharacterState) -> "CharacterPackage":
        package = cls(entity=entity.model_copy(deep=True), character=character.model_copy(deep=True), metadata={"format": "dnd-rpg-engine-character"})
        package.sha256 = package.content_hash()
        return package

    def verify(self) -> None:
        if self.sha256 is None:
            return
        expected = self.sha256
        self.sha256 = None
        actual = self.content_hash()
        self.sha256 = expected
        if expected != actual:
            raise ValueError("character package checksum mismatch")
