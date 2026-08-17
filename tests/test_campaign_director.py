from __future__ import annotations

from dnd_rpg_engine.ai.director import CampaignDirector, DirectorIntentKind, StoryThread
from dnd_rpg_engine.core.events import GameEvent
from dnd_rpg_engine.core.models import CampaignState


def event(campaign_id: str, sequence: int, event_type: str) -> GameEvent:
    return GameEvent(
        campaign_id=campaign_id,
        sequence=sequence,
        simulation_time=float(sequence),
        type=event_type,
    )


def test_director_tracks_tension_threads_and_only_proposes() -> None:
    state = CampaignState(id="campaign", name="Campaign", simulation_time=100.0)
    director = CampaignDirector()
    director.add_thread(state, StoryThread(id="lost-crown", title="The Lost Crown", weight=3.0, tags={"quest"}))
    director.observe(state, [event(state.id, 1, "character.rested"), event(state.id, 2, "quest.updated")])
    before_entities = state.entities.copy()
    proposals = director.propose(state)
    assert proposals
    assert any(value.kind is DirectorIntentKind.ADVANCE_THREAD for value in proposals)
    assert state.entities == before_entities
    assert all(value.suggested_command is None for value in proposals)


def test_director_attached_commands_are_parsed_before_approval() -> None:
    state = CampaignState(id="campaign", name="Campaign")
    director = CampaignDirector()
    proposal = director.propose(state, limit=1)
    if not proposal:
        # Force low tension so a pressure proposal is generated.
        saved = director.state_for(state)
        saved.tension = 0.0
        director.save_state(state, saved)
        proposal = director.propose(state, limit=1)
    attached = director.attach_command(
        proposal[0].id,
        {"type": "wait", "actor_id": "hero", "command_id": "director-command"},
    )
    command = director.approve(attached.id)
    assert command is not None
    assert command.actor_id == "hero"
