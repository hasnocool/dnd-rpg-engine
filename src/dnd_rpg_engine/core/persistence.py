# src/dnd_rpg_engine/core/persistence.py
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from dnd_rpg_engine.core.events import GameEvent
from dnd_rpg_engine.core.models import CampaignState


class SQLiteStore:
    """Async facade over SQLite using short-lived worker-thread connections.

    No sqlite call runs on the event loop, and no connection is shared between
    threads. WAL mode allows readers while the single SQLite writer serializes
    commits safely.
    """

    def __init__(self, path: str | Path = "rpg_engine.sqlite3") -> None:
        self.path = str(path)
        self._write_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _initialize_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS events (
                    campaign_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (campaign_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS idx_events_campaign_type
                    ON events(campaign_id, type);
                CREATE TABLE IF NOT EXISTS snapshots (
                    campaign_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    dice_json TEXT NOT NULL,
                    scheduler_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (campaign_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS kv (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(namespace, key)
                );
                CREATE TABLE IF NOT EXISTS content_packs (
                    id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS hosted_campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    public INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS marketplace_items (
                    id TEXT PRIMARY KEY,
                    pack_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    async def save_campaign(self, state: CampaignState, version: int) -> None:
        payload = state.model_dump_json()
        async with self._write_lock:
            await asyncio.to_thread(self._save_campaign_sync, state.id, state.name, payload, version)

    def _save_campaign_sync(self, campaign_id: str, name: str, payload: str, version: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO campaigns(id, name, state_json, version)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,
                  state_json=excluded.state_json,
                  version=excluded.version,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (campaign_id, name, payload, version),
            )

    async def list_campaigns(self, limit: int = 100) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_campaigns_sync, limit)

    def _list_campaigns_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, version, updated_at FROM campaigns ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    async def load_campaign(self, campaign_id: str) -> tuple[CampaignState, int] | None:
        row = await asyncio.to_thread(self._load_campaign_sync, campaign_id)
        if row is None:
            return None
        return CampaignState.model_validate_json(row[0]), int(row[1])

    def _load_campaign_sync(self, campaign_id: str) -> tuple[str, int] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json, version FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            return None if row is None else (row["state_json"], row["version"])

    async def append_event(self, event: GameEvent) -> None:
        async with self._write_lock:
            await asyncio.to_thread(self._append_event_sync, event)

    def _append_event_sync(self, event: GameEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO events(campaign_id, sequence, event_id, type, event_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (event.campaign_id, event.sequence, event.id, event.type, event.model_dump_json()),
            )

    async def list_events(self, campaign_id: str, *, after_sequence: int = 0, limit: int = 1000) -> list[GameEvent]:
        rows = await asyncio.to_thread(self._list_events_sync, campaign_id, after_sequence, limit)
        return [GameEvent.model_validate_json(row) for row in rows]

    def _list_events_sync(self, campaign_id: str, after_sequence: int, limit: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_json FROM events
                WHERE campaign_id=? AND sequence>?
                ORDER BY sequence ASC LIMIT ?
                """,
                (campaign_id, after_sequence, limit),
            ).fetchall()
            return [row["event_json"] for row in rows]

    async def save_snapshot(
        self,
        state: CampaignState,
        sequence: int,
        dice_counters: dict[str, int],
        scheduler: list[dict[str, Any]],
    ) -> None:
        async with self._write_lock:
            await asyncio.to_thread(
                self._save_snapshot_sync,
                state.id,
                sequence,
                state.model_dump_json(),
                json.dumps(dice_counters, sort_keys=True),
                json.dumps(scheduler, sort_keys=True),
            )

    def _save_snapshot_sync(
        self,
        campaign_id: str,
        sequence: int,
        state_json: str,
        dice_json: str,
        scheduler_json: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots(campaign_id, sequence, state_json, dice_json, scheduler_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (campaign_id, sequence, state_json, dice_json, scheduler_json),
            )

    async def latest_snapshot(self, campaign_id: str) -> dict[str, Any] | None:
        row = await asyncio.to_thread(self._latest_snapshot_sync, campaign_id)
        if row is None:
            return None
        return {
            "sequence": row[0],
            "state": CampaignState.model_validate_json(row[1]),
            "dice_counters": json.loads(row[2]),
            "scheduler": json.loads(row[3]),
        }

    def _latest_snapshot_sync(self, campaign_id: str) -> tuple[int, str, str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT sequence, state_json, dice_json, scheduler_json FROM snapshots
                WHERE campaign_id=? ORDER BY sequence DESC LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()
            if row is None:
                return None
            return row["sequence"], row["state_json"], row["dice_json"], row["scheduler_json"]

    async def put_json(self, namespace: str, key: str, value: Any) -> None:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        async with self._write_lock:
            await asyncio.to_thread(self._put_json_sync, namespace, key, payload)

    def _put_json_sync(self, namespace: str, key: str, payload: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kv(namespace, key, value_json) VALUES(?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                  value_json=excluded.value_json,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (namespace, key, payload),
            )

    async def list_json(self, namespace: str) -> dict[str, Any]:
        rows = await asyncio.to_thread(self._list_json_sync, namespace)
        return {key: json.loads(raw) for key, raw in rows}

    def _list_json_sync(self, namespace: str) -> list[tuple[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value_json FROM kv WHERE namespace=? ORDER BY key", (namespace,)
            ).fetchall()
            return [(row["key"], row["value_json"]) for row in rows]

    async def get_json(self, namespace: str, key: str) -> Any | None:
        raw = await asyncio.to_thread(self._get_json_sync, namespace, key)
        return None if raw is None else json.loads(raw)

    def _get_json_sync(self, namespace: str, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM kv WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
            return None if row is None else row["value_json"]
