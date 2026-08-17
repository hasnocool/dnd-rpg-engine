from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.models import CampaignState


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


class CampaignPackage(BaseModel):
    schema_version: int = 1
    campaign: CampaignState
    engine_config: dict[str, Any] = Field(default_factory=dict)
    installed_content_packs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sha256: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign": _canonicalize(self.campaign.model_dump(mode="python")),
            "engine_config": _canonicalize(self.engine_config),
            "installed_content_packs": _canonicalize(self.installed_content_packs),
            "metadata": _canonicalize(self.metadata),
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


def export_campaign_package(state: CampaignState, path: str | Path) -> CampaignPackage:
    package = CampaignPackage(
        campaign=state.model_copy(deep=True),
        engine_config=dict(state.metadata.get("engine_config", {})),
        installed_content_packs=dict(state.metadata.get("installed_content_packs", {})),
        metadata={"exported_from": "dnd-rpg-engine"},
    )
    package.sha256 = package.content_hash()
    Path(path).write_text(package.model_dump_json(indent=2), encoding="utf-8")
    return package


def import_campaign_package(path: str | Path) -> CampaignPackage:
    package = CampaignPackage.model_validate_json(Path(path).read_text(encoding="utf-8"))
    expected = package.sha256
    package.sha256 = None
    actual = package.content_hash()
    package.sha256 = expected
    if expected and expected != actual:
        raise ValueError("campaign package checksum mismatch")
    return package
