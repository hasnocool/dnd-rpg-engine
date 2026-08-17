# tests/test_adventure.py
from dnd_rpg_engine.adventure.dialogue import DialogueGraph, DialogueNode, DialogueOption, DialogueRequirement
from dnd_rpg_engine.adventure.quests import ObjectiveType, QuestDefinition, QuestJournal, QuestObjective
from dnd_rpg_engine.core.events import GameEvent


def test_dialogue_flags_gate_options_and_apply_state() -> None:
    graph = DialogueGraph(
        id="intro",
        start_node="start",
        nodes={
            "start": DialogueNode(
                id="start",
                text="Hello",
                options=[
                    DialogueOption(id="normal", text="Continue", set_flags={"met": True}),
                    DialogueOption(
                        id="secret",
                        text="Secret",
                        requirements=[DialogueRequirement(flag="knows_secret", equals=True)],
                    ),
                ],
            )
        },
    )
    flags: dict[str, object] = {}
    assert [o.id for o in graph.available_options("start", flags)] == ["normal"]
    graph.choose("start", "normal", flags)
    assert flags["met"] is True


def test_quest_progresses_from_engine_events() -> None:
    journal = QuestJournal()
    journal.start(
        QuestDefinition(
            id="visit",
            name="Visit",
            objectives=[QuestObjective(id="o", type=ObjectiveType.VISIT, target_id="tower")],
        )
    )
    event = GameEvent(type="location.visited", campaign_id="c", target_id="tower")
    assert journal.apply_event(event) == ["visit"]
    assert "visit" in journal.completed
