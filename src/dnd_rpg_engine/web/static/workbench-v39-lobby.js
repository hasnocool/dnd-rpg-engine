// src/dnd_rpg_engine/web/static/workbench-v39-lobby.js
import { $, escapeHtml, jsonFetch, state, toast } from "./workbench-core.js";
import { isOwner, metricRows } from "./workbench-v39-utils.js";

export async function loadLobby() {
  if (!state.campaignId) return;
  if (!isOwner()) throw new Error("GM owner permission required for the session lobby");
  const session = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/workbench/session`);
  $("lobby-owner").textContent = `owner ${session.owner_id}`;
  $("lobby-clients").innerHTML = session.clients.length ? session.clients.map((client) => `
    <article class="card"><strong>${escapeHtml(client.display_name || client.user_id)}</strong><div class="small">${escapeHtml(client.role)} · ${escapeHtml(client.user_id)}</div><div class="small">actors: ${escapeHtml((client.actor_ids || []).join(", ") || "none")}</div></article>`).join("") : '<div class="empty">No clients are joined yet.</div>';
  $("lobby-parties").innerHTML = session.parties.length ? session.parties.map((party) => `
    <div class="scene-row"><div class="row-top"><strong>${escapeHtml(party.name)}</strong><span class="badge">${escapeHtml(party.id)}</span></div><div class="small">actors: ${escapeHtml(party.actor_ids.join(", ") || "none")}</div><div class="small">users: ${escapeHtml(party.member_user_ids.join(", ") || "none")}</div><button data-party-add="${escapeHtml(party.id)}" class="ghost">Add member</button></div>`).join("") : '<div class="empty">No parties yet.</div>';
  $("lobby-scenes").innerHTML = Object.keys(session.scenes || {}).length ? Object.entries(session.scenes).map(([id, row]) => `<article class="card"><strong>${escapeHtml(row.definition?.name || id)}</strong><div class="small">${escapeHtml(row.definition?.kind || "custom")} · ${escapeHtml(row.runtime?.status || "unknown")}</div><div class="small">map ${escapeHtml(row.definition?.map_id || "—")}</div></article>`).join("") : '<div class="empty">No scenes registered.</div>';
  $("lobby-state").innerHTML = metricRows([["Simulation", `${Number(session.simulation_time || 0).toFixed(2)}s`],["World minute", session.world_minutes],["Active scenes", (session.active_scene_ids || []).join(", ") || "none"],["Clients", session.clients.length],["Parties", session.parties.length]]);
  document.querySelectorAll("[data-party-add]").forEach((button) => button.onclick = () => addPartyMember(button.dataset.partyAdd));
}

export async function createParty() {
  if (!isOwner()) return toast("Only the GM owner can create parties", "error");
  const id = prompt("Party ID:", "party-1")?.trim();
  if (!id) return;
  const name = prompt("Party name:", "Adventuring Party")?.trim() || id;
  await jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/parties`, {method:"POST", body:JSON.stringify({id,name})});
  await loadLobby();
  toast("Party created", "success");
}

async function addPartyMember(partyId) {
  const actorId = prompt("Actor ID to add (leave blank to add only a user):", "")?.trim() || null;
  const userId = prompt("User ID to add (optional):", "")?.trim() || null;
  if (!actorId && !userId) return;
  await jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/parties/${encodeURIComponent(partyId)}/members`, {method:"POST",body:JSON.stringify({actor_id:actorId,user_id:userId})});
  await loadLobby();
}

export function bindLobbyControls(reportError) {
  $("lobby-refresh").onclick=()=>loadLobby().catch(reportError);
  $("party-create").onclick=()=>createParty().catch(reportError);
}
