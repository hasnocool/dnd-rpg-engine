from __future__ import annotations

import pytest

from dnd_rpg_engine.client import RPGClient


class FakeTransport:
    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, *, json=None, headers=None):
        self.calls.append((method, path, json, headers))
        if path == "/api/v1/auth/bootstrap":
            return {"access_token": "token", "user": {"id": "u1"}}
        if path == "/api/v1/secure/campaigns":
            return {"campaign_id": "c1", "owner_client_id": "client-1", "state": {}}
        if path.endswith("/commands"):
            return {"duplicate": False, "client_sequence": json["client_sequence"]}
        if "/events?" in path:
            return [{"sequence": 4, "type": "test"}]
        raise AssertionError(path)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_python_sdk_tracks_reliable_sequences_and_event_cursor() -> None:
    transport = FakeTransport()
    client = RPGClient(transport=transport)
    await client.bootstrap(user_id="u1", display_name="User", bootstrap_key="bootstrap")
    campaign = await client.create_campaign("Test")
    assert campaign.client_sequence == 1
    await client.command("c1", {"type": "wait", "actor_id": "hero"})
    assert campaign.client_sequence == 2
    events = await client.events("c1")
    assert events[0]["sequence"] == 4
    assert campaign.last_event_sequence == 4
