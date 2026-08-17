# src/dnd_rpg_engine/core/events.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class GameEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    campaign_id: str
    sequence: int = 0
    simulation_time: float = 0.0
    actor_id: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventStream:
    def __init__(self, maxsize: int = 2048) -> None:
        self.queue: asyncio.Queue[GameEvent] = asyncio.Queue(maxsize=maxsize)
        self.closed = False

    async def get(self) -> GameEvent:
        return await self.queue.get()

    def close(self) -> None:
        self.closed = True


class EventBus:
    """Fan-out bus that never runs subscriber callbacks on the simulation loop."""

    def __init__(self) -> None:
        self._streams: set[EventStream] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, maxsize: int = 2048) -> EventStream:
        stream = EventStream(maxsize=maxsize)
        async with self._lock:
            self._streams.add(stream)
        return stream

    async def unsubscribe(self, stream: EventStream) -> None:
        stream.close()
        async with self._lock:
            self._streams.discard(stream)

    async def publish(self, event: GameEvent) -> None:
        async with self._lock:
            streams = tuple(self._streams)
        for stream in streams:
            if stream.closed:
                continue
            try:
                stream.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest event for a slow presentation client; authoritative
                # state and persistence are not tied to client queue throughput.
                try:
                    stream.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    stream.queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass
