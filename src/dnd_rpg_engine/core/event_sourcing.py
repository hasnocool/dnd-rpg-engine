# src/dnd_rpg_engine/core/event_sourcing.py
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from dnd_rpg_engine.core.commands import GameCommand
from dnd_rpg_engine.core.engine import EngineResult, GameEngine
from dnd_rpg_engine.core.models import CampaignState

JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None

_JOURNAL_BOOKKEEPING_METADATA = frozenset({"command_ledger", "event_source_head"})


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _state_hash_payload(value: CampaignState | dict[str, Any]) -> dict[str, Any]:
    payload = value.model_dump(mode="json") if isinstance(value, CampaignState) else copy.deepcopy(value)
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in _JOURNAL_BOOKKEEPING_METADATA:
            metadata.pop(key, None)
    return payload


def state_hash(value: CampaignState | dict[str, Any]) -> str:
    """Hash authoritative campaign state while ignoring journal bookkeeping.

    ``command_ledger`` and ``event_source_head`` describe the journal itself.
    Excluding them prevents the act of recording a command from changing the
    gameplay-state hash that the record is intended to verify.
    """
    return hashlib.sha256(canonical_json(_state_hash_payload(value)).encode("utf-8")).hexdigest()


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _unescape_pointer(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def _join_pointer(parent: str, key: str) -> str:
    escaped = _escape_pointer(key)
    return f"{parent}/{escaped}" if parent else f"/{escaped}"


class PatchOperation(BaseModel):
    op: Literal["add", "remove", "replace"]
    path: str
    value: Any = None


def diff_json(before: JsonValue, after: JsonValue, path: str = "") -> list[PatchOperation]:
    """Create a deterministic bounded JSON patch.

    Dictionaries are diffed recursively; lists are replaced atomically. Treating
    lists atomically keeps replay deterministic and avoids index-shift ambiguity.
    """
    if type(before) is not type(after):
        return [PatchOperation(op="replace", path=path, value=copy.deepcopy(after))]
    if isinstance(before, dict) and isinstance(after, dict):
        operations: list[PatchOperation] = []
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys):
            operations.append(PatchOperation(op="remove", path=_join_pointer(path, str(key))))
        for key in sorted(after_keys - before_keys):
            operations.append(PatchOperation(op="add", path=_join_pointer(path, str(key)), value=copy.deepcopy(after[key])))
        for key in sorted(before_keys & after_keys):
            operations.extend(diff_json(before[key], after[key], _join_pointer(path, str(key))))
        return operations
    if isinstance(before, list) and isinstance(after, list):
        return [] if before == after else [PatchOperation(op="replace", path=path, value=copy.deepcopy(after))]
    return [] if before == after else [PatchOperation(op="replace", path=path, value=copy.deepcopy(after))]


def _pointer_parts(path: str) -> list[str]:
    if path in {"", "/"}:
        return []
    if not path.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {path}")
    return [_unescape_pointer(part) for part in path[1:].split("/")]


def apply_patch(document: JsonValue, operations: list[PatchOperation]) -> JsonValue:
    result: JsonValue = copy.deepcopy(document)
    for operation in operations:
        parts = _pointer_parts(operation.path)
        if not parts:
            if operation.op == "remove":
                result = None
            else:
                result = copy.deepcopy(operation.value)
            continue
        parent: Any = result
        for part in parts[:-1]:
            if isinstance(parent, list):
                parent = parent[int(part)]
            else:
                parent = parent[part]
        key = parts[-1]
        if isinstance(parent, list):
            index = int(key)
            if operation.op == "remove":
                parent.pop(index)
            elif operation.op == "add":
                parent.insert(index, copy.deepcopy(operation.value))
            else:
                parent[index] = copy.deepcopy(operation.value)
        else:
            if operation.op == "remove":
                parent.pop(key, None)
            else:
                parent[key] = copy.deepcopy(operation.value)
    return result


class JournalEntry(BaseModel):
    sequence: int = Field(ge=1)
    command_id: str
    operations: list[PatchOperation]
    state_hash: str
    previous_hash: str
    entry_hash: str

    @classmethod
    def build(
        cls,
        *,
        sequence: int,
        command_id: str,
        operations: list[PatchOperation],
        resulting_state_hash: str,
        previous_hash: str,
    ) -> "JournalEntry":
        body = {
            "sequence": sequence,
            "command_id": command_id,
            "operations": [operation.model_dump(mode="json") for operation in operations],
            "state_hash": resulting_state_hash,
            "previous_hash": previous_hash,
        }
        entry_hash = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
        return cls(entry_hash=entry_hash, **body)


class BranchMetadata(BaseModel):
    branch_id: str = "main"
    parent_branch_id: str | None = None
    parent_sequence: int | None = None
    parent_state_hash: str | None = None


class VerificationResult(BaseModel):
    valid: bool
    checked_entries: int
    state_hash: str
    error: str | None = None


class EventJournal:
    def __init__(
        self,
        initial_state: CampaignState | dict[str, Any],
        *,
        metadata: BranchMetadata | None = None,
    ) -> None:
        self.initial_state = (
            initial_state.model_dump(mode="json") if isinstance(initial_state, CampaignState) else copy.deepcopy(initial_state)
        )
        self.initial_hash = state_hash(self.initial_state)
        self.metadata = metadata or BranchMetadata()
        self.entries: list[JournalEntry] = []

    @property
    def head_hash(self) -> str:
        return self.entries[-1].entry_hash if self.entries else self.initial_hash

    def append(self, command_id: str, before: dict[str, Any], after: dict[str, Any]) -> JournalEntry:
        expected_before = self.state_at(len(self.entries))
        if state_hash(expected_before) != state_hash(before):
            raise ValueError("journal head does not match command pre-state")
        operations = diff_json(before, after)
        entry = JournalEntry.build(
            sequence=len(self.entries) + 1,
            command_id=command_id,
            operations=operations,
            resulting_state_hash=state_hash(after),
            previous_hash=self.head_hash,
        )
        self.entries.append(entry)
        return entry

    def state_at(self, sequence: int | None = None) -> dict[str, Any]:
        target = len(self.entries) if sequence is None else sequence
        if target < 0 or target > len(self.entries):
            raise ValueError("journal sequence is out of range")
        current: JsonValue = copy.deepcopy(self.initial_state)
        for entry in self.entries[:target]:
            current = apply_patch(current, entry.operations)
        if not isinstance(current, dict):
            raise ValueError("campaign replay did not produce an object state")
        return current

    def replay(self, sequence: int | None = None) -> CampaignState:
        return CampaignState.model_validate(self.state_at(sequence))

    def rewind(self, sequence: int) -> CampaignState:
        return self.replay(sequence)

    def branch(self, sequence: int, branch_id: str) -> "EventJournal":
        parent_state = self.state_at(sequence)
        return EventJournal(
            parent_state,
            metadata=BranchMetadata(
                branch_id=branch_id,
                parent_branch_id=self.metadata.branch_id,
                parent_sequence=sequence,
                parent_state_hash=state_hash(parent_state),
            ),
        )

    def verify(self) -> VerificationResult:
        current: JsonValue = copy.deepcopy(self.initial_state)
        previous_hash = self.initial_hash
        for expected_sequence, entry in enumerate(self.entries, start=1):
            if entry.sequence != expected_sequence:
                return VerificationResult(
                    valid=False,
                    checked_entries=expected_sequence - 1,
                    state_hash=state_hash(current if isinstance(current, dict) else {}),
                    error="journal sequence gap",
                )
            if entry.previous_hash != previous_hash:
                return VerificationResult(
                    valid=False,
                    checked_entries=expected_sequence - 1,
                    state_hash=state_hash(current if isinstance(current, dict) else {}),
                    error="journal hash chain mismatch",
                )
            rebuilt = JournalEntry.build(
                sequence=entry.sequence,
                command_id=entry.command_id,
                operations=entry.operations,
                resulting_state_hash=entry.state_hash,
                previous_hash=entry.previous_hash,
            )
            if rebuilt.entry_hash != entry.entry_hash:
                return VerificationResult(
                    valid=False,
                    checked_entries=expected_sequence - 1,
                    state_hash=state_hash(current if isinstance(current, dict) else {}),
                    error="journal entry hash mismatch",
                )
            current = apply_patch(current, entry.operations)
            if not isinstance(current, dict) or state_hash(current) != entry.state_hash:
                return VerificationResult(
                    valid=False,
                    checked_entries=expected_sequence,
                    state_hash=state_hash(current if isinstance(current, dict) else {}),
                    error="replayed state hash mismatch",
                )
            previous_hash = entry.entry_hash
        final_hash = state_hash(current if isinstance(current, dict) else {})
        return VerificationResult(valid=True, checked_entries=len(self.entries), state_hash=final_hash)


class CommandReceipt(BaseModel):
    command_id: str
    journal_sequence: int
    engine_version: int
    state_hash: str
    duplicate: bool = False


class CommandLedger:
    def __init__(self, initial: dict[str, dict[str, Any]] | None = None) -> None:
        self._receipts: dict[str, CommandReceipt] = {
            command_id: CommandReceipt.model_validate(receipt)
            for command_id, receipt in (initial or {}).items()
        }

    def get(self, command_id: str) -> CommandReceipt | None:
        return self._receipts.get(command_id)

    def register(self, receipt: CommandReceipt) -> None:
        existing = self._receipts.get(receipt.command_id)
        if existing is not None and existing.state_hash != receipt.state_hash:
            raise ValueError("command id was already used for a different authoritative result")
        self._receipts[receipt.command_id] = receipt

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {key: value.model_dump(mode="json") for key, value in sorted(self._receipts.items())}


@dataclass(slots=True)
class EventSourcedDispatch:
    receipt: CommandReceipt
    result: EngineResult | None
    journal_entry: JournalEntry | None


class EventSourcedEngine:
    """Compatibility bridge that adds deterministic journaling to GameEngine.

    It derives authoritative state patches around normal command dispatch, so the
    existing engine can gain replay/rewind/branching and idempotent command IDs
    without blocking the event loop or changing renderer/network contracts.
    """

    def __init__(self, engine: GameEngine, *, journal: EventJournal | None = None) -> None:
        self.engine = engine
        self.journal = journal or EventJournal(engine.state)
        stored = engine.state.metadata.get("command_ledger", {})
        self.ledger = CommandLedger(stored if isinstance(stored, dict) else {})

    async def dispatch(self, command: GameCommand, *, narrate: bool = False) -> EventSourcedDispatch:
        duplicate = self.ledger.get(command.command_id)
        if duplicate is not None:
            return EventSourcedDispatch(
                receipt=duplicate.model_copy(update={"duplicate": True}),
                result=None,
                journal_entry=None,
            )
        before = self.engine.state.model_dump(mode="json")
        result = await self.engine.dispatch(command, narrate=narrate)
        after = self.engine.state.model_dump(mode="json")
        entry = self.journal.append(command.command_id, before, after)
        receipt = CommandReceipt(
            command_id=command.command_id,
            journal_sequence=entry.sequence,
            engine_version=result.version,
            state_hash=entry.state_hash,
        )
        self.ledger.register(receipt)
        self.engine.state.metadata["command_ledger"] = self.ledger.snapshot()
        self.engine.state.metadata["event_source_head"] = {
            "branch_id": self.journal.metadata.branch_id,
            "sequence": entry.sequence,
            "entry_hash": entry.entry_hash,
            "state_hash": entry.state_hash,
        }
        if self.engine.store is not None:
            key = f"{self.engine.state.id}:{self.journal.metadata.branch_id}:{entry.sequence:012d}"
            await self.engine.store.put_json("event_source.entry", key, entry.model_dump(mode="json"))
            await self.engine.save()
        return EventSourcedDispatch(receipt=receipt, result=result, journal_entry=entry)

    def replay(self, sequence: int | None = None) -> CampaignState:
        return self.journal.replay(sequence)

    def rewind(self, sequence: int) -> CampaignState:
        return self.journal.rewind(sequence)

    def branch(self, sequence: int, branch_id: str) -> EventJournal:
        return self.journal.branch(sequence, branch_id)

    def verify(self) -> VerificationResult:
        result = self.journal.verify()
        if not result.valid:
            return result
        live_hash = state_hash(self.engine.state)
        if live_hash != result.state_hash:
            return VerificationResult(
                valid=False,
                checked_entries=result.checked_entries,
                state_hash=result.state_hash,
                error=f"live state hash mismatch: {live_hash}",
            )
        return result
