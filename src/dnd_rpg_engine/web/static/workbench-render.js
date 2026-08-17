// src/dnd_rpg_engine/web/static/workbench-render.js
import { $, escapeHtml, jsonFetch, state, toast } from "./workbench-core.js";

export function renderCampaign() {
  const payload = state.campaign;
  if (!payload) return;
  const campaign = payload.campaign || payload;
  const entities = Object.values(campaign.entities || {});
  const name = campaign.name || state.campaignId;
  $("gm-campaign-name").textContent = name;
  $("player-campaign-name").textContent = name;
  $("gm-time").textContent = `t=${Number(campaign.simulation_time || 0).toFixed(2)}s`;
  $("player-time").textContent = `t=${Number(campaign.simulation_time || 0).toFixed(2)}s`;
  $("gm-world").textContent = `world ${payload.world_time ?? campaign.world_time ?? "—"}`;
  $("gm-weather").textContent = `weather ${payload.weather ?? campaign.weather ?? "—"}`;
  $("ready-summary").textContent = `${(payload.ready_humans || []).length} human actor(s) ready`;
  $("active-map-title").textContent = campaign.active_map_id ? `Map · ${campaign.active_map_id}` : "Active world";
  renderScenes(campaign);
  renderTokens($("gm-map"), entities, true);
  renderTimeline(entities, payload.ready_humans || []);
  renderWorld(entities, campaign.metadata || {});
  fillEntitySelect($("gm-actor"), entities.filter((entity) => entity.alive !== false), $("gm-actor").value);
  fillEntitySelect($("gm-target"), entities.filter((entity) => entity.alive !== false), $("gm-target").value);
  $("player-identity").textContent = state.identity ? `${state.identity.display_name || state.identity.user_id} · ${state.identity.role}` : "not joined";
  if (state.activeView === "player") renderPlayerShell();
}

function renderScenes(campaign) {
  const orchestrator = campaign.metadata?.campaign_orchestrator || {};
  const scenes = orchestrator.scenes || {};
  const activeIds = new Set(orchestrator.active_scene_ids || []);
  $("active-scene-badge").textContent = activeIds.size ? [...activeIds].join(", ") : "no active scene";
  $("active-scene-badge").classList.toggle("active", activeIds.size > 0);
  if (!Object.keys(scenes).length) {
    $("scene-list").innerHTML = '<div class="empty">No runtime scenes registered yet. Build scene content in Creator Studio, then instantiate the campaign.</div>';
    return;
  }
  $("scene-list").innerHTML = Object.entries(scenes).map(([sceneId, runtime]) => `
    <div class="scene-row ${activeIds.has(sceneId) ? "active" : ""}" data-scene="${escapeHtml(sceneId)}">
      <div class="row-top"><strong>${escapeHtml(sceneId)}</strong><span class="badge">${escapeHtml(runtime.status)}</span></div>
      <div class="small">visits ${Number(runtime.visit_count || 0)} · entered ${runtime.entered_at ?? "—"}</div>
      <div class="button-grid"><button data-scene-action="active" data-id="${escapeHtml(sceneId)}">Activate</button><button data-scene-action="suspended" data-id="${escapeHtml(sceneId)}" class="ghost">Suspend</button></div>
    </div>`).join("");
  document.querySelectorAll("[data-scene]").forEach((node) => {
    node.onclick = (event) => {
      if (!event.target.dataset.sceneAction) inspect({scene_id: node.dataset.scene, ...scenes[node.dataset.scene]});
    };
  });
  document.querySelectorAll("[data-scene-action]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      transitionScene(button.dataset.id, button.dataset.sceneAction).catch((error) => toast(error.message, "error"));
    };
  });
}

async function transitionScene(sceneId, status) {
  await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/scenes/${encodeURIComponent(sceneId)}`, {
    method: "PATCH",
    body: JSON.stringify({status, reason: "workbench", exclusive: status === "active"}),
  });
  state.campaign = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}`);
  renderCampaign();
  toast(`${sceneId} → ${status}`, "success");
}

function renderTokens(container, entities, omniscient = false) {
  if (!entities.length) {
    container.innerHTML = '<div class="empty">No entities in this view.</div>';
    return;
  }
  container.innerHTML = entities.map((entity) => {
    const hp = Number(entity.resources?.hp ?? 0);
    const max = Number(entity.resources?.max_hp ?? 0);
    const pct = max > 0 ? Math.max(0, Math.min(100, hp / max * 100)) : 0;
    const role = entity.kind === "player" || entity.controller === "human" ? "player" : "enemy";
    return `<div class="world-token ${role}" data-token="${escapeHtml(entity.id)}"><strong>${escapeHtml(entity.name || entity.id)}</strong><div class="small">${escapeHtml(entity.position?.area_id || "unknown area")} · ${escapeHtml(entity.kind || entity.controller || "entity")}</div>${max ? `<div class="hpbar"><span style="width:${pct}%"></span></div><div class="small">HP ${hp}/${max}</div>` : ""}${omniscient ? `<div class="small">${escapeHtml(entity.id)}</div>` : ""}</div>`;
  }).join("");
  container.querySelectorAll("[data-token]").forEach((node) => {
    node.onclick = () => inspect(entities.find((entity) => entity.id === node.dataset.token));
  });
}

function renderTimeline(entities, readyIds) {
  const ready = new Set(readyIds);
  $("gm-timeline").innerHTML = entities.length ? entities.map((entity) => `
    <div class="timeline-item ${ready.has(entity.id) ? "ready" : ""}" data-actor="${escapeHtml(entity.id)}">
      <strong>${escapeHtml(entity.name || entity.id)}</strong>
      <span class="small">${escapeHtml(entity.controller || entity.kind || "entity")}${ready.has(entity.id) ? " · READY" : ""}</span>
    </div>`).join("") : '<div class="empty">No actors.</div>';
  $("gm-timeline").querySelectorAll("[data-actor]").forEach((node) => {
    node.onclick = () => inspect(entities.find((entity) => entity.id === node.dataset.actor));
  });
}

function renderWorld(entities, metadata) {
  $("world-entities").innerHTML = entities.length ? entities.map((entity) => `
    <article class="card"><strong>${escapeHtml(entity.name || entity.id)}</strong><div class="small">${escapeHtml(entity.id)}</div><div class="small">${escapeHtml(entity.kind || "entity")} · ${escapeHtml(entity.position?.area_id || "no area")}</div></article>`).join("") : '<div class="empty">No entities.</div>';
  $("world-metadata").textContent = JSON.stringify(metadata, null, 2);
}

export function fillEntitySelect(select, entities, previous) {
  select.innerHTML = entities.map((entity) => `<option value="${escapeHtml(entity.id)}">${escapeHtml(entity.name || entity.id)}</option>`).join("");
  if (entities.some((entity) => entity.id === previous)) select.value = previous;
}

export function inspect(value) {
  $("gm-inspector").classList.remove("empty");
  $("gm-inspector").innerHTML = `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

export async function refreshPlayerRuntime() {
  if (!state.campaignId || !state.identity || state.identity.role === "owner") {
    renderPlayerShell();
    return;
  }
  const actorIds = state.identity.actor_ids || [];
  if (!actorIds.length) {
    state.runtime = null;
    renderPlayerShell();
    return;
  }
  if (!state.selectedPlayerActor || !actorIds.includes(state.selectedPlayerActor)) state.selectedPlayerActor = actorIds[0];
  state.runtime = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/runtime?actor_id=${encodeURIComponent(state.selectedPlayerActor)}`);
  renderPlayerShell();
}

function runtimeEntities() {
  const runtime = state.runtime || {};
  if (Array.isArray(runtime.entities)) return runtime.entities;
  return Object.values(runtime.entities || runtime.state?.entities || runtime.snapshot?.entities || {});
}

function renderPlayerShell() {
  const actorIds = state.identity?.actor_ids || [];
  $("player-actors").innerHTML = actorIds.length ? actorIds.map((id) => `<button class="actor-row ${id === state.selectedPlayerActor ? "primary" : "ghost"}" data-player-actor="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join("") : '<div class="empty">This identity does not own any character entities.</div>';
  document.querySelectorAll("[data-player-actor]").forEach((button) => {
    button.onclick = async () => {
      state.selectedPlayerActor = button.dataset.playerActor;
      await refreshPlayerRuntime();
    };
  });
  const entities = runtimeEntities();
  renderTokens($("player-map"), entities, false);
  const selected = entities.find((entity) => entity.id === state.selectedPlayerActor) || state.runtime?.actor || state.runtime?.entity;
  $("player-character").classList.toggle("empty", !selected);
  $("player-character").innerHTML = selected ? `<pre>${escapeHtml(JSON.stringify(selected, null, 2))}</pre>` : "Choose one of your characters.";
  fillEntitySelect($("player-target"), entities.filter((entity) => entity.id !== state.selectedPlayerActor && entity.alive !== false), $("player-target").value);
}

export function addEvent(event) {
  state.events.unshift(event);
  if (state.events.length > 500) state.events.length = 500;
  const html = eventHtml(event);
  $("events").insertAdjacentHTML("afterbegin", html);
  $("player-events").insertAdjacentHTML("afterbegin", html);
  while ($("events").children.length > 300) $("events").lastElementChild.remove();
  while ($("player-events").children.length > 200) $("player-events").lastElementChild.remove();
}

function eventHtml(event) {
  const details = event.type === "narration" ? event.payload?.text : JSON.stringify(event.payload || {});
  return `<div class="event"><span class="type">${escapeHtml(event.type || "event")}</span> <span class="small">t=${Number(event.simulation_time || 0).toFixed(2)}</span><br><span class="${event.type === "narration" ? "narration" : ""}">${escapeHtml(details)}</span></div>`;
}

export async function loadEventHistory(target = "events") {
  if (!state.campaignId) return [];
  const events = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/events?after=0&limit=1000`);
  $(target).innerHTML = events.slice().reverse().map(eventHtml).join("") || '<div class="empty">No events yet.</div>';
  return events;
}

export async function loadJournal() {
  if (state.campaignId) await loadEventHistory("journal-events");
}
