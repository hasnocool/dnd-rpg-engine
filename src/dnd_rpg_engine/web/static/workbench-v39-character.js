// src/dnd_rpg_engine/web/static/workbench-v39-character.js
import { $, escapeHtml, jsonFetch, reportError, state, toast } from "./workbench-core.js";
import { refreshCampaign } from "./workbench-session.js";
import { campaignEntities, fillSelect, isOwner, metricRows, objectValues, renderTacticalStage, selectedActorId } from "./workbench-v39-utils.js";

export async function loadCharacter() {
  if (!state.campaignId || !state.identity) return;
  const entities = campaignEntities();
  const candidates = isOwner() ? entities.filter((e) => e.kind === "player" || e.controller === "human") : (state.identity.actor_ids || []).map((id) => ({id,name:entities.find((e)=>e.id===id)?.name || id}));
  fillSelect($("character-select"), candidates, $("character-select").value || state.selectedPlayerActor);
  const actorId = $("character-select").value;
  if (!actorId) { $("character-sheet").innerHTML='<div class="empty">No characters available.</div>'; return; }
  try {
    const sheet = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/characters/${encodeURIComponent(actorId)}`);
    renderCharacterSheet(sheet);
  } catch (error) {
    $("character-sheet").innerHTML = `<div class="empty">${escapeHtml(error.message)}. This actor may not use the character lifecycle profile.</div>`;
  }
}

function renderCharacterSheet(sheet) {
  const entity = sheet.entity || {};
  const stats = entity.stats || {};
  $("character-summary").innerHTML = metricRows([["Name",entity.name],["HP",`${entity.resources?.hp ?? "—"}/${entity.resources?.max_hp ?? "—"}`],["Level",sheet.progress?.total_level ?? "—"],["XP",sheet.progress?.xp ?? "—"],["Level ready",sheet.level_ready ? "yes" : "no"]]);
  $("character-sheet").innerHTML = `<section class="sheet-section"><h3>Ability scores</h3><div class="ability-grid">${["strength","dexterity","constitution","intelligence","wisdom","charisma"].map((key)=>`<div class="ability"><strong>${escapeHtml(stats[key] ?? "—")}</strong><span>${escapeHtml(key.slice(0,3))}</span></div>`).join("")}</div></section><section class="sheet-section"><h3>Progression</h3><pre class="output mono">${escapeHtml(JSON.stringify(sheet.progress || {},null,2))}</pre></section><section class="sheet-section"><h3>Class resources</h3><div class="resource-grid">${Object.entries(sheet.resources || {}).map(([id,row])=>`<div class="metric-row"><span>${escapeHtml(id)}</span><strong>${escapeHtml(row.current ?? row.value ?? "—")}/${escapeHtml(row.maximum ?? row.max ?? "—")}</strong></div>`).join("") || '<div class="empty">No class resources.</div>'}</div></section>`;
  const equipment = sheet.equipment || {};
  $("character-equipment").innerHTML = `<article class="card"><strong>Equipment state</strong><pre class="output mono">${escapeHtml(JSON.stringify(equipment,null,2))}</pre></article><article class="card"><strong>Effective modifiers</strong><pre class="output mono">${escapeHtml(JSON.stringify(sheet.equipment_modifiers || {},null,2))}</pre></article>`;
  renderCharacterControls(entity.id, sheet);
}

function renderCharacterControls(actorId, sheet) {
  const controls = [
    ["Short rest", () => lifecyclePost(actorId,"rest",{profile_id:"short_rest"})],
    ["Long rest", () => lifecyclePost(actorId,"rest",{profile_id:"long_rest"})],
    ["Equip item…", async () => { const item_id=prompt("Item ID:")?.trim(); if(item_id) await lifecyclePost(actorId,"equip",{item_id}); }],
    ["Unequip item…", async () => { const item_id=prompt("Item ID:")?.trim(); if(item_id) await lifecyclePost(actorId,"unequip",{item_id}); }],
    ["Spend resource…", async () => { const resource_id=prompt("Resource ID:")?.trim(); if(resource_id) await lifecyclePost(actorId,"resources/spend",{resource_id,amount:Number(prompt("Amount:","1"))||1}); }],
  ];
  if (isOwner()) {
    controls.push(["Award XP…", async () => { const amount=Number(prompt("XP amount:","100")); if(Number.isFinite(amount)&&amount>=0) await lifecyclePost(actorId,"xp",{amount}); }]);
    controls.push(["Level up…", async () => { const class_id=prompt("Class ID:")?.trim(); if(class_id) await lifecyclePost(actorId,"level-up",{class_id}); }]);
    controls.push(["Restore resource…", async () => { const resource_id=prompt("Resource ID:")?.trim(); if(resource_id) await lifecyclePost(actorId,"resources/restore",{resource_id,amount:Number(prompt("Amount:","1"))||1}); }]);
  }
  $("character-controls").innerHTML = controls.map(([label],index)=>`<button data-character-action="${index}" class="${label.startsWith("Level") ? "primary" : "ghost"}">${escapeHtml(label)}</button>`).join("");
  document.querySelectorAll("[data-character-action]").forEach((button)=>button.onclick=()=>Promise.resolve(controls[Number(button.dataset.characterAction)][1]()).catch(reportError));
  if (sheet.level_ready) $("character-controls").insertAdjacentHTML("afterbegin",'<span class="badge active">Level-up available</span>');
}

async function lifecyclePost(actorId, suffix, payload) {
  await jsonFetch(`/api/v1/campaigns/${state.campaignId}/characters/${encodeURIComponent(actorId)}/${suffix}`, {method:"POST",body:JSON.stringify(payload)});
  await refreshCampaign(); await loadCharacter(); toast("Character updated", "success");
}

export async function loadVisualRuntime() {
  if (!state.campaignId || !state.identity) return;
  const actorId = isOwner() ? null : selectedActorId();
  const suffix = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
  const runtime = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/runtime${suffix}`);
  const entities = objectValues(runtime.entities);
  $("visual-scope").textContent = actorId ? `actor ${actorId} · redacted` : "GM canonical";
  renderTacticalStage($("visual-stage"), entities, actorId, null);
  $("visual-metadata").innerHTML = metricRows([["Sequence",runtime.sequence],["Simulation",`${Number(runtime.simulation_time||0).toFixed(2)}s`],["Active map",runtime.active_map_id || "—"],["Entities",Object.keys(runtime.entities||{}).length],["Facts",Object.keys(runtime.facts||{}).length],["Snapshot hash",runtime.snapshot_hash || "—"]]);
  $("visual-bindings").innerHTML = Object.keys(runtime.bindings || {}).length ? Object.entries(runtime.bindings).map(([id,binding])=>`<div class="binding-card"><strong>${escapeHtml(id)}</strong><div class="small">scene ${escapeHtml(binding.scene || "—")} · sprite ${escapeHtml(binding.sprite || "—")} · model ${escapeHtml(binding.model || "—")}</div></div>`).join("") : '<div class="empty">No explicit visual bindings registered.</div>';
  $("visual-json").textContent = JSON.stringify(runtime,null,2);
}

export function bindCharacterControls(reportErrorHandler) {
  $("character-refresh").onclick=()=>loadCharacter().catch(reportErrorHandler);
  $("character-select").onchange=()=>loadCharacter().catch(reportErrorHandler);
  $("visual-refresh").onclick=()=>loadVisualRuntime().catch(reportErrorHandler);
}
