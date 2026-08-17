// src/dnd_rpg_engine/web/static/workbench-v39-tactical.js
import { $, escapeHtml, jsonFetch, state, toast } from "./workbench-core.js";
import { loadEventHistory } from "./workbench-render.js";
import { refreshCampaign, sendCommand } from "./workbench-session.js";
import { fillSelect, isOwner, metricRows, objectValues, renderTacticalStage, selectedActorId } from "./workbench-v39-utils.js";

let tactical=null;
let catalog=null;
let lastEncounterId=null;

async function ensureCatalog() {
  if (!catalog) catalog = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/workbench/catalog`);
  return catalog;
}

export async function loadTactical() {
  if (!state.campaignId || !state.identity) return;
  await ensureCatalog();
  const actorId = selectedActorId();
  const query = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
  tactical = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/workbench/tactical${query}`);
  const entities = objectValues(tactical.entities);
  const controllable = isOwner() ? entities.filter((e) => e.alive !== false) : entities.filter((e) => state.identity.actor_ids?.includes(e.id));
  fillSelect($("tactical-actor"), controllable, actorId);
  const chosen = $("tactical-actor").value || actorId;
  const targets = entities.filter((e) => e.id !== chosen && e.alive !== false);
  fillSelect($("tactical-target"), targets, $("tactical-target").value);
  $("tactical-scope").textContent = tactical.knowledge_scoped ? "knowledge scoped" : "GM omniscient";
  $("tactical-map-title").textContent = tactical.active_map_id ? `Map · ${tactical.active_map_id}` : "Tactical map";
  renderTacticalStage($("tactical-map"), entities, chosen, $("tactical-target").value);
  renderTacticalEconomy(tactical.action_economy, tactical.spaces);
  renderInitiative(entities);
  renderActionPalette();
  renderTargetCard(entities.find((e) => e.id === $("tactical-target").value));
  const actor = entities.find((e) => e.id === chosen);
  if (actor?.position) { $("move-x").value = actor.position.x ?? 0; $("move-y").value = actor.position.y ?? 0; }
  await loadEventHistory("tactical-log");
}

function renderTacticalEconomy(economy, spaces) {
  const rows = [];
  if (economy && typeof economy === "object") for (const [key, value] of Object.entries(economy)) rows.push([key.replaceAll("_", " "), typeof value === "object" ? JSON.stringify(value) : value]);
  rows.push(["Active scene", (tactical?.active_scene_ids || []).join(", ") || "none"]);
  rows.push(["Spatial spaces", (spaces || []).map((space) => `${space.id}:${space.kind}`).join(", ") || "none registered"]);
  $("tactical-economy").innerHTML = metricRows(rows);
}

function renderInitiative(entities) {
  const ready = new Set(state.campaign?.ready_humans || []);
  $("tactical-initiative").innerHTML = entities.map((entity) => `<div class="scene-row"><div class="row-top"><strong>${escapeHtml(entity.name || entity.id)}</strong><span class="badge">${ready.has(entity.id) ? "READY" : "waiting"}</span></div><div class="small">${escapeHtml(entity.controller || entity.kind || "entity")}</div></div>`).join("") || '<div class="empty">No actors.</div>';
}

function renderTargetCard(entity) {
  if (!entity) { $("tactical-target-card").className = "inspector empty"; $("tactical-target-card").textContent = "Select a target."; return; }
  $("tactical-target-card").className = "inspector";
  $("tactical-target-card").innerHTML = `<strong>${escapeHtml(entity.name || entity.id)}</strong><div class="small">${escapeHtml(entity.id)}</div><div class="small">HP ${escapeHtml(entity.resources?.hp ?? "—")}/${escapeHtml(entity.resources?.max_hp ?? "—")}</div><div class="small">${escapeHtml(entity.position?.area_id || "unknown area")} · (${escapeHtml(entity.position?.x ?? 0)}, ${escapeHtml(entity.position?.y ?? 0)})</div>`;
}

function renderActionPalette() {
  const rows = [];
  for (const action of catalog?.actions || []) rows.push(actionCard("Action", action, () => tacticalAttack(action.id)));
  for (const spell of catalog?.spells || []) rows.push(actionCard("Spell", spell, () => tacticalCast(spell.id)));
  for (const item of catalog?.items || []) rows.push(actionCard("Item", item, () => tacticalUseItem(item.id)));
  for (const rule of catalog?.rule_graphs || []) rows.push(actionCard("Rule", rule, () => tacticalRule(rule.id)));
  $("tactical-actions").innerHTML = rows.map((row) => row.html).join("") || '<div class="empty">No registered actions.</div>';
  rows.forEach((row) => { const button = document.querySelector(`[data-palette-id="${CSS.escape(row.key)}"]`); if (button) button.onclick = row.handler; });
}

function actionCard(kind, value, handler) {
  const key = `${kind}:${value.id}`;
  const detail = kind === "Action" ? `range ${value.range ?? "—"} · ${value.damage || "no damage"}` : kind === "Spell" ? `range ${value.range ?? "—"} · cost ${value.energy_cost ?? 0}` : kind === "Item" ? `value ${value.value ?? 0}` : `time ${value.action_time_seconds ?? "—"}s`;
  return { key, handler, html:`<div class="action-card"><div><span class="eyebrow">${escapeHtml(kind)}</span><strong>${escapeHtml(value.name || value.id)}</strong></div><div class="small">${escapeHtml(detail)}</div><button data-palette-id="${escapeHtml(key)}">Use</button></div>` };
}

async function tacticalAttack(actionId) { const actor = $("tactical-actor").value, target = $("tactical-target").value; if (!actor || !target) return toast("Actor and target are required", "error"); await sendCommand({type:"attack",actor_id:actor,target_id:target,action_id:actionId}); await loadTactical(); }
async function tacticalCast(spellId) { const actor=$("tactical-actor").value,target=$("tactical-target").value||null; if(!actor) return; await sendCommand({type:"cast",actor_id:actor,target_id:target,spell_id:spellId}); await loadTactical(); }
async function tacticalUseItem(itemId) { const actor=$("tactical-actor").value,target=$("tactical-target").value||actor; if(!actor) return; await sendCommand({type:"use_item",actor_id:actor,target_id:target,item_id:itemId}); await loadTactical(); }
async function tacticalRule(ruleId) { const actor=$("tactical-actor").value,target=$("tactical-target").value||null; if(!actor) return; await sendCommand({type:"custom",actor_id:actor,name:"rule.execute",payload:{rule_id:ruleId,target_id:target,variables:{}}}); await loadTactical(); }

async function tacticalMove() {
  const actor = $("tactical-actor").value;
  if (!actor) return toast("Choose an actor", "error");
  const x = Number($("move-x").value), y = Number($("move-y").value);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return toast("Enter valid X and Y coordinates", "error");
  await sendCommand({type:"move",actor_id:actor,map_id:tactical?.active_map_id || null,x,y,z:0});
  await loadTactical();
}

async function startEncounter() {
  if (!isOwner()) return toast("Only the GM can start an encounter", "error");
  const participants = objectValues(tactical?.entities).filter((e) => e.alive !== false).map((e) => e.id);
  if (participants.length < 2) return toast("At least two active entities are required", "error");
  const result = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/encounters`, {method:"POST", body:JSON.stringify({participant_ids:participants})});
  lastEncounterId = result.id || result.encounter_id || null;
  toast("Encounter started", "success"); await refreshCampaign(); await loadTactical();
}

async function endEncounter() {
  if (!isOwner()) return toast("Only the GM can end an encounter", "error");
  const encounterId = lastEncounterId || prompt("Encounter ID:", "")?.trim();
  if (!encounterId) return;
  await jsonFetch(`/api/v1/campaigns/${state.campaignId}/encounters/${encodeURIComponent(encounterId)}`, {method:"DELETE"});
  lastEncounterId = null; toast("Encounter ended", "success"); await refreshCampaign(); await loadTactical();
}

export function bindTacticalControls(reportError) {
  $("tactical-refresh").onclick=()=>loadTactical().catch(reportError);
  $("tactical-actor").onchange=()=>loadTactical().catch(reportError);
  $("tactical-target").onchange=()=>{
    const entity=objectValues(tactical?.entities).find((row)=>row.id===$("tactical-target").value);
    renderTargetCard(entity);
    renderTacticalStage($("tactical-map"),objectValues(tactical?.entities),$("tactical-actor").value,$("tactical-target").value);
  };
  $("tactical-move").onclick=()=>tacticalMove().catch(reportError);
  $("tactical-start-encounter").onclick=()=>startEncounter().catch(reportError);
  $("tactical-end-encounter").onclick=()=>endEncounter().catch(reportError);
  $("tactical-history").onclick=()=>loadEventHistory("tactical-log").catch(reportError);
  $("tactical-grid-toggle").onchange=()=>$("tactical-map").classList.toggle("no-grid",!$("tactical-grid-toggle").checked);
  $("tactical-label-toggle").onchange=()=>$("tactical-map").classList.toggle("no-labels",!$("tactical-label-toggle").checked);
}
