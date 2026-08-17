# src/dnd_rpg_engine/ai/gm.py
from __future__ import annotations

from typing import Protocol

from dnd_rpg_engine.ai.memory import MemoryEntry, MemoryStore
from dnd_rpg_engine.core.events import GameEvent
from dnd_rpg_engine.core.models import CampaignState


class NarrativeProvider(Protocol):
    async def narrate(self, *, state: CampaignState, events: list[GameEvent], context: str) -> str: ...


class TemplateNarrativeProvider:
    """Offline deterministic narrator; useful as a fallback and for tests."""

    async def narrate(self, *, state: CampaignState, events: list[GameEvent], context: str) -> str:
        if not events:
            return f"{state.name}: the world is quiet for the moment."
        lines: list[str] = []
        for event in events[-6:]:
            if event.type == "combat.attack_resolved":
                result = "connects" if event.payload.get("hit") else "misses"
                lines.append(f"{event.actor_id} acts against {event.target_id} and {result}.")
            elif event.type == "entity.moved":
                lines.append(f"{event.actor_id} moves to a new position.")
            elif event.type == "spell.resolved":
                lines.append(f"{event.actor_id} completes {event.payload.get('spell_id', 'a spell')}.")
            elif event.type == "weather.changed":
                lines.append(f"The weather changes to {event.payload.get('weather')}.")
            elif event.type == "quest.completed":
                lines.append(f"A quest is completed: {event.payload.get('quest_id')}.")
            else:
                lines.append(event.type.replace(".", " ").replace("_", " ").capitalize() + ".")
        return " ".join(lines)


class GameMaster:
    """Narrates authoritative events; never mutates simulation truth through prose."""

    def __init__(self, provider: NarrativeProvider | None = None, memory: MemoryStore | None = None) -> None:
        self.provider = provider or TemplateNarrativeProvider()
        self.memory = memory or MemoryStore()

    async def narrate(self, state: CampaignState, events: list[GameEvent], *, subject_id: str = "campaign") -> str:
        context = self.memory.context(subject_id)
        narration = await self.provider.narrate(state=state, events=events, context=context)
        self.memory.add(
            MemoryEntry(
                subject_id=subject_id,
                text=narration,
                importance=0.55,
                tags={"narration"},
            )
        )
        return narration
