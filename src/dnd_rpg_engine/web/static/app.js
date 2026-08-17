// src/dnd_rpg_engine/web/static/app.js
const $ = (id) => document.getElementById(id);
let campaignId = null;
let clientId = null;
let socket = null;
let state = null;

function enableGame(enabled) {
  ["add-demo", "action-basic", "action-quick", "cast", "wait", "tick", "refresh"].forEach(id => $(id).disabled = !enabled);
}

async function jsonFetch(url, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (clientId) headers["X-RPG-Client-ID"] = clientId;
  const response = await fetch(url, { ...options, headers });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ? JSON.stringify(body.detail) : response.statusText);
  return body;
}

async function createCampaign() {
  const timeout = Number($("decision-timeout").value);
  const body = await jsonFetch("/api/v1/campaigns", {
    method: "POST",
    body: JSON.stringify({
      name: $("campaign-name").value,
      owner_id: "browser",
      seed: 42,
      time_mode: $("time-mode").value,
      player_decision_timeout_seconds: Number.isFinite(timeout) ? timeout : 10,
    }),
  });
  campaignId = body.campaign_id;
  clientId = body.owner_client_id;
  $("campaign-id").textContent = campaignId;
  enableGame(true);
  connectSocket();
  await refreshState();
}

async function addDemo() {
  const player = await jsonFetch(`/api/v1/campaigns/${campaignId}/entities`, {
    method: "POST",
    body: JSON.stringify({
      id: "hero",
      name: "Hero",
      kind: "player",
      controller: "human",
      owner_id: "browser",
      resources: { hp: 30, max_hp: 30, energy: 5, max_energy: 5 },
      position: { area_id: "training_ground", x: 0, y: 0, z: 0 },
      components: { movement: { units_per_second: 1.5 }, inventory: { currency: 100, items: { minor_restorative: 2 } } },
    }),
  });
  await jsonFetch(`/api/v1/campaigns/${campaignId}/entities`, {
    method: "POST",
    body: JSON.stringify({
      id: "rival",
      name: "Clockwork Rival",
      kind: "creature",
      controller: "ai",
      resources: { hp: 24, max_hp: 24, energy: 0, max_energy: 0 },
      position: { area_id: "training_ground", x: 1, y: 0, z: 0 },
      components: { ai: { target_id: "hero", action_id: "basic_attack" }, movement: { units_per_second: 1.2 } },
    }),
  });
  await refreshState();
}

async function sendCommand(command) {
  try {
    const result = await jsonFetch(`/api/v1/campaigns/${campaignId}/commands`, {
      method: "POST",
      body: JSON.stringify({ command, narrate: true }),
    });
    if (result.narration) addEvent({ type: "narration", simulation_time: result.simulation_time, payload: { text: result.narration } });
    await refreshState();
  } catch (error) {
    addEvent({ type: "client.error", simulation_time: state?.campaign?.simulation_time ?? 0, payload: { detail: error.message } });
  }
}

async function refreshState() {
  if (!campaignId) return;
  state = await jsonFetch(`/api/v1/campaigns/${campaignId}`);
  renderState();
}

function renderState() {
  if (!state) return;
  $("metrics").innerHTML = [
    ["Mode", state.time_mode],
    ["Sim time", `${state.campaign.simulation_time.toFixed(2)}s`],
    ["World", state.world_time],
    ["Weather", state.weather],
    ["Ready", state.ready_humans.join(", ") || "—"],
    ["Pause", state.decision_pause_remaining == null ? "none" : `${state.decision_pause_remaining.toFixed(1)}s`],
  ].map(([k,v]) => `<div class="metric"><strong>${escapeHtml(v)}</strong><span>${escapeHtml(k)}</span></div>`).join("");

  const entities = Object.values(state.campaign.entities);
  $("entities").innerHTML = entities.map(entity => {
    const pct = entity.resources.max_hp ? (entity.resources.hp / entity.resources.max_hp) * 100 : 0;
    return `<article class="card">
      <div class="card-title"><strong>${escapeHtml(entity.name)}</strong><span class="small">${escapeHtml(entity.controller)}</span></div>
      <div class="small">${escapeHtml(entity.id)} · ${entity.alive ? "active" : "inactive"}</div>
      <div class="hp"><div style="width:${Math.max(0, pct)}%"></div></div>
      <div class="small">HP ${entity.resources.hp}/${entity.resources.max_hp} · energy ${entity.resources.energy}/${entity.resources.max_energy}</div>
    </article>`;
  }).join("");

  const humans = entities.filter(e => e.controller === "human" && e.alive);
  const targets = entities.filter(e => e.alive);
  fillSelect($("actor"), humans, $("actor").value);
  fillSelect($("target"), targets, $("target").value);
}

function fillSelect(select, entities, previous) {
  select.innerHTML = entities.map(e => `<option value="${escapeHtml(e.id)}">${escapeHtml(e.name)} (${escapeHtml(e.id)})</option>`).join("");
  if (entities.some(e => e.id === previous)) select.value = previous;
}

function connectSocket() {
  if (socket) socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/api/v1/campaigns/${campaignId}/ws?client_id=${encodeURIComponent(clientId)}`);
  socket.onopen = () => { $("socket-status").textContent = "online"; $("socket-status").classList.add("online"); };
  socket.onclose = () => { $("socket-status").textContent = "offline"; $("socket-status").classList.remove("online"); };
  socket.onmessage = (message) => {
    const payload = JSON.parse(message.data);
    if (payload.kind === "event") { addEvent(payload.event); refreshState(); }
    if (payload.kind === "state") { state = payload.state; renderState(); }
  };
}

function addEvent(event) {
  const node = document.createElement("div");
  node.className = "event";
  const details = event.type === "narration" ? event.payload.text : JSON.stringify(event.payload || {});
  node.innerHTML = `<span class="type">${escapeHtml(event.type)}</span> <span class="small">t=${Number(event.simulation_time || 0).toFixed(2)}</span><br>${escapeHtml(details)}`;
  $("events").prepend(node);
  while ($("events").children.length > 300) $("events").lastChild.remove();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
}

$("create-campaign").onclick = createCampaign;
$("add-demo").onclick = addDemo;
$("refresh").onclick = refreshState;
$("action-basic").onclick = () => sendCommand({ type: "attack", actor_id: $("actor").value, target_id: $("target").value, action_id: "basic_attack" });
$("action-quick").onclick = () => sendCommand({ type: "attack", actor_id: $("actor").value, target_id: $("target").value, action_id: "quick_attack" });
$("cast").onclick = () => sendCommand({ type: "cast", actor_id: $("actor").value, target_id: $("target").value, spell_id: "arcane_bolt" });
$("wait").onclick = () => sendCommand({ type: "wait", actor_id: $("actor").value });
$("tick").onclick = async () => { await jsonFetch(`/api/v1/campaigns/${campaignId}/tick`, { method: "POST", body: JSON.stringify({ seconds: Number($("tick-seconds").value), narrate: true }) }); await refreshState(); };
