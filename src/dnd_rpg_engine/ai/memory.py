# src/dnd_rpg_engine/ai/memory.py
from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    subject_id: str
    text: str
    importance: float = Field(default=0.5, ge=0, le=1)
    tags: set[str] = Field(default_factory=set)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryStore:
    def __init__(self, per_subject_limit: int = 200) -> None:
        self.per_subject_limit = per_subject_limit
        self._memories: dict[str, deque[MemoryEntry]] = {}

    def add(self, entry: MemoryEntry) -> None:
        bucket = self._memories.setdefault(entry.subject_id, deque(maxlen=self.per_subject_limit))
        bucket.append(entry)

    def recall(self, subject_id: str, *, tags: set[str] | None = None, limit: int = 12) -> list[MemoryEntry]:
        entries = list(self._memories.get(subject_id, ()))
        if tags:
            entries = [entry for entry in entries if entry.tags & tags]
        entries.sort(key=lambda e: (e.importance, e.created_at), reverse=True)
        return entries[:limit]

    def context(self, subject_id: str, *, limit: int = 8) -> str:
        return "\n".join(f"- {entry.text}" for entry in self.recall(subject_id, limit=limit))
