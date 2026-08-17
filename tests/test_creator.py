# tests/test_creator.py
from dnd_rpg_engine.creator.content import ContentPack, ContentValidator, CreatureTemplate, ModManifest
from dnd_rpg_engine.tactical.actions import ActionDefinition


def test_content_pack_zip_round_trip_and_hash() -> None:
    pack = ContentPack(
        manifest=ModManifest(id="demo.pack", name="Demo", author="tester", license="CC0-1.0"),
        actions={"spark": ActionDefinition(id="spark", name="Spark", damage="1d4")},
        creatures={"sprite": CreatureTemplate(id="sprite", name="Sprite", actions=["spark"])},
    )
    assert ContentValidator().validate(pack) == []
    raw = pack.to_zip_bytes()
    restored = ContentPack.from_zip_bytes(raw)
    assert restored.content_hash() == pack.content_hash()
    assert restored.manifest.id == "demo.pack"
