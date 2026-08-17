# TypeScript client SDK

The v2.5 TypeScript SDK wraps the authenticated campaign and reliable-command APIs while keeping authoritative outcomes on the server.

```ts
import { RPGClient } from "@dnd-rpg-engine/client";

const client = new RPGClient({ baseUrl: "https://rpg.example" });
await client.bootstrap("local-user", "Local User", bootstrapKey);
const campaign = await client.createCampaign("Example", 42, "hybrid");

const socket = client.reliableSocket(campaign.campaignId);
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.kind === "event") console.log(message.event);
});

await client.command(campaign.campaignId, {
  type: "wait",
  actor_id: "hero"
});
```

`bootstrap()` is intended for controlled/local provisioning. Production deployments should protect provisioning and session issuance behind the deployment's identity onboarding flow. Never expose the bootstrap key to browser clients.

The SDK tracks the reliable client sequence automatically. Retrying the same command with the same sequence is idempotent server-side.
