# tests/test_event_sourcing.py
from __future__ import annotations

from copy import deepcopy

import pytest

from dnd_rpg_engine.core.commands import WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.event_sourcing import (
    CommandLedger,
    CommandReceipt,
    EventJournal,
    EventSourcedEngine,
    apply_patch,
    diff_json,
    state_hash,
)
from dnd_rpg_engine.core.models import CampaignState, ControllerKind, Entity, EntityKind, GameConfig, TimeMode


def test_json_patch_round_trip_is_deterministic() -> None:
    before = {"name": "A", "flags": {"x": 1}, "items": [1, 2]}
    after = {"name": "B", "flags": {"x": 2, "y": True}, "items": [1, 3]}
    operations = diff_json(before, after)
    repeated = diff_json(before, after)
    assert apply_patch(before, operations) == after
    assert [operation.model_dump(mode="json") for operation in operations] == [
        operation.model_dump(mode="json") for operation in repeated
    ]


def test_journal_replay_rewind_branch_and_verify() -> None:
    initial = CampaignState(id="c1", name="Initial", seed=7)
    journal = EventJournal(initial)
    before = initial.model_dump(mode="json")
    after_one = deepcopy(before)
    after_one["name"] = "Changed"
    after_one["flags"]["door"] = "open"
    first = journal.append("command-1", before, after_one)
    after_two = deepcopy(after_one)
    after_two["simulation_time"] = 6.0
    second = journal.append("command-2", after_one, after_two)

    assert first.previous_hash == journal.initial_hash
    assert second.previous_hash == first.entry_hash
    assert journal.replay().simulation_time == 6.0
    assert journal.rewind(1).name == "Changed"
    assert journal.verify().valid is True

    branch = journal.branch(1, "alternate")
    assert branch.metadata.parent_branch_id == "main"
    assert branch.metadata.parent_sequence == 1
    assert branch.initial_state["flags"]["door"] == "open"


def test_command_ledger_enforces_idempotent_result() -> None:
    ledger = CommandLedger()
    receipt = CommandReceipt(
        command_id="same-command",
        journal_sequence=1,
        engine_version=2,
        state_hash=state_hash({"id": "state"}),
    )
    ledger.register(receipt)
    assert ledger.get("same-command") == receipt
    ledger.register(receipt.model_copy())


@pytest.mark.asyncio
async def test_event_sourced_engine_is_idempotent_and_verifies_live_state() -> None:
    engine = await GameEngine.create(config=GameConfig(time_mode=TimeMode.TURN_BASED, seed=17))
    await engine.add_entity(
        Entity(
            id="hero",
            name="Hero",
            kind=EntityKind.PLAYER,
            controller=ControllerKind.HUMAN,
        )
    )
    sourced = EventSourcedEngine(engine)

    first = await sourced.dispatch(WaitCommand(actor_id="hero", command_id="wait-1"))
    assert first.journal_entry is not None
    assert first.receipt.duplicate is False

    duplicate = await sourced.dispatch(WaitCommand(actor_id="hero", command_id="wait-1"))
    assert duplicate.receipt.duplicate is True
    assert duplicate.result is None
    assert duplicate.journal_entry is None
    assert len(sourced.journal.entries) == 1

    second = await sourced.dispatch(WaitCommand(actor_id="hero", command_id="wait-2"))
    assert second.journal_entry is not None
    assert len(sourced.journal.entries) == 2
    assert sourced.verify().valid is True
    assert sourced.replay().simulation_time == engine.state.simulation_time
