# src/dnd_rpg_engine/rulesets/srd_5_2_1/catalog_store.py
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import CompiledCatalogManifest


class SRDCatalogStore:
    """Thread-safe async facade over the offline SRD catalog database."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._write_lock = asyncio.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS catalog_manifest (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS catalog_entries (
                    section TEXT NOT NULL,
                    id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_page INTEGER,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(section, id)
                );
                CREATE INDEX IF NOT EXISTS idx_catalog_entries_section_name
                    ON catalog_entries(section, name COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_catalog_entries_section_page
                    ON catalog_entries(section, source_page);
                """
            )

    async def replace_section(self, section: str, entries: Iterable[dict[str, Any]]) -> None:
        rows = list(entries)
        async with self._write_lock:
            await asyncio.to_thread(self._replace_section_sync, section, rows)

    def _replace_section_sync(self, section: str, entries: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM catalog_entries WHERE section=?", (section,))
            conn.executemany(
                """
                INSERT INTO catalog_entries(section, id, name, source_page, payload_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                [
                    (
                        section,
                        str(entry["id"]),
                        str(entry.get("name", entry["id"])),
                        _source_page(entry),
                        json.dumps(entry, sort_keys=True, separators=(",", ":")),
                    )
                    for entry in entries
                ],
            )

    async def put_manifest(self, manifest: CompiledCatalogManifest) -> None:
        payload = manifest.model_dump(mode="json")
        async with self._write_lock:
            await asyncio.to_thread(self._put_manifest_sync, payload)

    def _put_manifest_sync(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO catalog_manifest(key, value_json) VALUES('manifest', ?)",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
            )

    async def manifest(self) -> CompiledCatalogManifest | None:
        raw = await asyncio.to_thread(self._manifest_sync)
        return None if raw is None else CompiledCatalogManifest.model_validate_json(raw)

    def _manifest_sync(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM catalog_manifest WHERE key='manifest'").fetchone()
            return None if row is None else str(row["value_json"])

    async def get(self, section: str, entry_id: str) -> dict[str, Any] | None:
        raw = await asyncio.to_thread(self._get_sync, section, entry_id)
        return None if raw is None else json.loads(raw)

    def _get_sync(self, section: str, entry_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM catalog_entries WHERE section=? AND id=?",
                (section, entry_id),
            ).fetchone()
            return None if row is None else str(row["payload_json"])

    async def search(self, section: str, query: str = "", *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(5000, int(limit)))
        rows = await asyncio.to_thread(self._search_sync, section, query, limit)
        return [json.loads(row) for row in rows]

    def _search_sync(self, section: str, query: str, limit: int) -> list[str]:
        with self._connect() as conn:
            if query.strip():
                rows = conn.execute(
                    """
                    SELECT payload_json FROM catalog_entries
                    WHERE section=? AND name LIKE ? ESCAPE '\\'
                    ORDER BY name COLLATE NOCASE LIMIT ?
                    """,
                    (section, f"%{_escape_like(query.strip())}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM catalog_entries WHERE section=? ORDER BY name COLLATE NOCASE LIMIT ?",
                    (section, limit),
                ).fetchall()
            return [str(row["payload_json"]) for row in rows]

    async def count(self, section: str | None = None) -> int:
        return await asyncio.to_thread(self._count_sync, section)

    def _count_sync(self, section: str | None) -> int:
        with self._connect() as conn:
            if section is None:
                row = conn.execute("SELECT COUNT(*) AS c FROM catalog_entries").fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS c FROM catalog_entries WHERE section=?", (section,)).fetchone()
            return int(row["c"])

    async def sections(self) -> dict[str, int]:
        return await asyncio.to_thread(self._sections_sync)

    def _sections_sync(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT section, COUNT(*) AS c FROM catalog_entries GROUP BY section ORDER BY section"
            ).fetchall()
            return {str(row["section"]): int(row["c"]) for row in rows}


def _source_page(entry: dict[str, Any]) -> int | None:
    source = entry.get("source")
    if isinstance(source, dict) and source.get("source_page") is not None:
        return int(source["source_page"])
    if entry.get("source_page") is not None:
        return int(entry["source_page"])
    return None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
