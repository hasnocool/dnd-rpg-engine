from __future__ import annotations

from pydantic import BaseModel, Field

from dnd_rpg_engine.adventure.dialogue import DialogueGraph
from dnd_rpg_engine.adventure.maps import WorldMap
from dnd_rpg_engine.adventure.npcs import NPCProfile
from dnd_rpg_engine.adventure.quests import QuestDefinition
from dnd_rpg_engine.ai.encounters import EncounterTemplate
from dnd_rpg_engine.creator.content import CampaignTemplate, ContentPack, ContentValidator, RuleDocument


class CreatorProject(BaseModel):
    id: str
    name: str
    campaigns: dict[str, CampaignTemplate] = Field(default_factory=dict)
    maps: dict[str, WorldMap] = Field(default_factory=dict)
    encounters: dict[str, EncounterTemplate] = Field(default_factory=dict)
    npcs: dict[str, NPCProfile] = Field(default_factory=dict)
    dialogues: dict[str, DialogueGraph] = Field(default_factory=dict)
    quests: dict[str, QuestDefinition] = Field(default_factory=dict)
    rules: dict[str, RuleDocument] = Field(default_factory=dict)
    notes: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_pack(cls, pack: ContentPack) -> "CreatorProject":
        return cls(
            id=pack.manifest.id,
            name=pack.manifest.name,
            campaigns={k: v.model_copy(deep=True) for k, v in pack.campaigns.items()},
            maps={k: v.model_copy(deep=True) for k, v in pack.maps.items()},
            encounters={k: v.model_copy(deep=True) for k, v in pack.encounters.items()},
            npcs={k: v.model_copy(deep=True) for k, v in pack.npcs.items()},
            dialogues={k: v.model_copy(deep=True) for k, v in pack.dialogues.items()},
            quests={k: v.model_copy(deep=True) for k, v in pack.quests.items()},
            rules={k: v.model_copy(deep=True) for k, v in pack.rules.items()},
        )

    def apply_to_pack(self, pack: ContentPack) -> ContentPack:
        updated = pack.model_copy(deep=True)
        updated.campaigns = {k: v.model_copy(deep=True) for k, v in self.campaigns.items()}
        updated.maps = {k: v.model_copy(deep=True) for k, v in self.maps.items()}
        updated.encounters = {k: v.model_copy(deep=True) for k, v in self.encounters.items()}
        updated.npcs = {k: v.model_copy(deep=True) for k, v in self.npcs.items()}
        updated.dialogues = {k: v.model_copy(deep=True) for k, v in self.dialogues.items()}
        updated.quests = {k: v.model_copy(deep=True) for k, v in self.quests.items()}
        updated.rules = {k: v.model_copy(deep=True) for k, v in self.rules.items()}
        return updated


class CreatorStudio:
    def __init__(self) -> None:
        self.validator = ContentValidator()

    def inspect(self, pack: ContentPack) -> dict[str, object]:
        return {
            "project": CreatorProject.from_pack(pack).model_dump(mode="json"),
            "valid": not self.validator.validate(pack),
            "errors": self.validator.validate(pack),
            "content_hash": pack.content_hash(),
            "counts": {
                "campaigns": len(pack.campaigns), "maps": len(pack.maps), "encounters": len(pack.encounters), "npcs": len(pack.npcs),
                "dialogues": len(pack.dialogues), "quests": len(pack.quests), "rules": len(pack.rules),
            },
        }
