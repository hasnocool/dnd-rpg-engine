// src/dnd_rpg_engine/web/static/workbench-session.js
import { $, closeModal, escapeHtml, jsonFetch, modal, reportError, state, toast } from "./workbench-core.js";
import { addEvent, loadJournal, refreshPlayerRuntime, renderCampaign } from "./workbench-render.js";

export function setView(name) {
  state.activeView = name;
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === `view-${name}`));
  document.querySelectorAll(".rail-link[data-view]").forEach((node) => node.classList.toggle("active", node.dataset.view === name));
  const context = {library:"Create, run, and inspect authoritative campaigns",gm:"Omniscient campaign control",player:"Knowledge-scoped player experience",world:"Authoritative state explorer",journal:"Persistent event history"};
  $("header-context").textContent = context[name] || "Campaign Workbench";
  if (name === "journal") loadJournal().catch(reportError);
  if (name === "player") refreshPlayerRuntime().catch(reportError);
}

function enableSessionViews(enabled) {
  document.querySelectorAll('.rail-link[data-view]:not([data-view="library"])').forEach((node) => { node.disabled = !enabled; });
  $("refresh-current").disabled = !enabled;
}

export async function loadCampaigns() {
  const campaigns = await jsonFetch("/api/v1/campaigns");
  if (!campaigns.length) {
    $("campaign-list").innerHTML = '<div class="empty">No campaigns yet. Create one to start playing.</div>';
    return;
  }
  $("campaign-list").innerHTML = campaigns.map((campaign) => `<article class="campaign-card"><div><h3>${escapeHtml(campaign.name)}</h3><div class="small">${escapeHtml(campaign.id)}</div></div><div class="small">state v${Number(campaign.version ?? 0)} · updated ${escapeHtml(campaign.updated_at ?? "unknown")}</div><div class="actions"><button data-open-gm="${escapeHtml(campaign.id)}">GM</button><button data-open-player="${escapeHtml(campaign.id)}" class="ghost">Player</button></div></article>`).join("");
  document.querySelectorAll("[data-open-gm]").forEach((button) => button.onclick = () => openCampaign(button.dataset.openGm, "gm"));
  document.querySelectorAll("[data-open-player]").forEach((button) => button.onclick = () => openCampaign(button.dataset.openPlayer, "player"));
}

export async function loadMarketplace() {
  const items = await jsonFetch("/api/v1/marketplace");
  $("marketplace-list").innerHTML = items.length ? items.slice(0, 8).map((item) => `<div class="market-card"><strong>${escapeHtml(item.title || item.name || item.id)}</strong><span class="small">${escapeHtml(item.description || item.pack_id || "content pack")}</span></div>`).join("") : '<div class="empty">No published packs in this registry.</div>';
}

export function showCreateCampaign() {
  modal("Create campaign", `<div class="form-grid"><label>Name<input id="new-name" value="New Adventure" /></label><label>Owner ID<input id="new-owner" value="browser-gm" /></label><label>Time mode<select id="new-time-mode"><option value="turn_based">Turn based</option><option value="timed_turn_based">Timed turn based</option><option value="real_time">Real time</option><option value="real_time_with_pause">Real time with pause</option><option value="hybrid" selected>Hybrid</option></select></label><label>Seed<input id="new-seed" type="number" value="42" /></label><label>Decision timeout<input id="new-timeout" type="number" min="1" value="10" /></label><label>Time scale<input id="new-scale" type="number" min="0.01" step="0.25" value="1" /></label></div>`, '<button id="create-confirm" class="primary">Create & open GM console</button>');
  $("create-confirm").onclick = createCampaign;
}

async function createCampaign() {
  const payload = {name:$("new-name").value.trim() || "New Adventure",owner_id:$("new-owner").value.trim() || "browser-gm",seed:Number($("new-seed").value) || 42,time_mode:$("new-time-mode").value,player_decision_timeout_seconds:Number($("new-timeout").value) || 10};
  const body = await jsonFetch("/api/v1/campaigns", {method:"POST", body:JSON.stringify(payload)});
  state.campaignId = body.campaign_id;
  state.clientId = body.owner_client_id;
  state.accessToken = body.access_token;
  state.identity = {user_id:payload.owner_id,display_name:payload.owner_id,role:"owner",actor_ids:[]};
  state.campaign = body;
  await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/timing`, {method:"PATCH", body:JSON.stringify({time_scale:Number($("new-scale").value) || 1})});
  closeModal(); enableSessionViews(true); connectSocket(); await refreshCampaign(); setView("gm"); loadCampaigns().catch(reportError); toast("Campaign created", "success");
}

export function openCampaign(campaignId, mode) {
  state.campaignId = campaignId; state.campaign = null; state.clientId = null; state.accessToken = null; state.identity = null;
  if (mode === "gm") showGmJoin(); else showPlayerJoin();
}

function showGmJoin() {
  modal("Open as Game Master", `<p class="muted">Enter the campaign owner identity. The session layer promotes only the stored owner ID to GM authority.</p><label>Owner ID<input id="gm-owner-id" value="local" /></label>`, '<button id="gm-join-confirm" class="primary">Open GM console</button>');
  $("gm-join-confirm").onclick = async () => {
    const ownerId = $("gm-owner-id").value.trim(); if (!ownerId) return toast("Owner ID is required", "error");
    try { await joinCampaign({userId:ownerId,displayName:ownerId,role:"owner",actorIds:[]}); if (state.identity?.role !== "owner") throw new Error("That identity is not the campaign owner"); closeModal(); setView("gm"); toast(`Opened ${state.campaign?.campaign?.name || state.campaign?.name || state.campaignId} as GM`, "success"); } catch (error) { reportError(error); }
  };
}

export function showPlayerJoin() {
  modal("Join campaign", `<p class="muted">Enter the player identity used as the <code>owner_id</code> on their character entities. The server resolves which actors this identity may control.</p><label>Player ID<input id="join-user" placeholder="player-1" /></label><label>Display name<input id="join-name" placeholder="Player" /></label>`, '<button id="join-confirm" class="primary">Join as player</button>');
  $("join-confirm").onclick = async () => {
    const userId = $("join-user").value.trim(); if (!userId) return toast("Player ID is required", "error");
    try { await joinCampaign({userId,displayName:$("join-name").value.trim() || userId,role:"player",actorIds:[]}); closeModal(); setView("player"); await refreshPlayerRuntime(); } catch (error) { reportError(error); }
  };
}

async function joinCampaign({userId, displayName, role, actorIds}) {
  const joined = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/join`, {method:"POST", body:JSON.stringify({user_id:userId,display_name:displayName,role,actor_ids:actorIds})});
  state.clientId=joined.client_id; state.accessToken=joined.access_token; state.identity=joined; state.selectedPlayerActor=joined.actor_ids?.[0] || null;
  enableSessionViews(true); connectSocket(); await refreshCampaign();
}

export async function refreshCampaign() {
  if (!state.campaignId) return;
  state.campaign = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}`);
  renderCampaign();
}

export async function sendCommand(command, {narrate=true}={}) {
  const result = await jsonFetch(`/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/commands`, {method:"POST", body:JSON.stringify({command,narrate})});
  if (result.narration) addEvent({type:"narration",simulation_time:result.simulation_time,payload:{text:result.narration}});
  await refreshCampaign(); return result;
}

export async function addDemoActors() {
  const existing = new Set(Object.keys(state.campaign?.campaign?.entities || state.campaign?.entities || {}));
  if (!existing.has("hero")) await jsonFetch(`/api/v1/campaigns/${state.campaignId}/entities`, {method:"POST",body:JSON.stringify({id:"hero",name:"Hero",kind:"player",controller:"human",owner_id:state.identity?.user_id || "browser-gm",resources:{hp:30,max_hp:30,energy:5,max_energy:5},position:{area_id:"training_ground",x:0,y:0,z:0},components:{movement:{units_per_second:1.5}}})});
  if (!existing.has("rival")) await jsonFetch(`/api/v1/campaigns/${state.campaignId}/entities`, {method:"POST",body:JSON.stringify({id:"rival",name:"Clockwork Rival",kind:"creature",controller:"ai",resources:{hp:24,max_hp:24,energy:0,max_energy:0},position:{area_id:"training_ground",x:1,y:0,z:0},components:{ai:{target_id:"hero",action_id:"basic_attack"}}})});
  await refreshCampaign(); toast("Training actors ready", "success");
}

export async function tick(seconds) {
  const result = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/tick`, {method:"POST",body:JSON.stringify({seconds,narrate:true})});
  if (result.narration) addEvent({type:"narration",simulation_time:result.simulation_time,payload:{text:result.narration}});
  await refreshCampaign();
}

export async function showDirector() {
  try {
    const proposals = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/director/proposals`);
    modal("AI Director proposals", proposals.length ? `<div class="stack">${proposals.map((proposal) => `<div class="proposal-row"><strong>${escapeHtml(proposal.kind || proposal.type || "proposal")}</strong><div class="small">score ${proposal.score ?? proposal.rank ?? "—"}</div><pre class="output">${escapeHtml(JSON.stringify(proposal,null,2))}</pre></div>`).join("")}</div>` : '<div class="empty">No proposals right now.</div>');
  } catch (error) { modal("AI Director", `<div class="empty">Director endpoint unavailable for this engine profile: ${escapeHtml(error.message)}</div>`); }
}

function connectSocket() {
  if (!state.campaignId || !state.clientId) return;
  if (state.socket) state.socket.close();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const token = state.accessToken ? `&token=${encodeURIComponent(state.accessToken)}` : "";
  const ws = new WebSocket(`${scheme}://${location.host}/api/v1/campaigns/${encodeURIComponent(state.campaignId)}/ws?client_id=${encodeURIComponent(state.clientId)}${token}`);
  state.socket = ws;
  ws.onopen = () => { $("socket-status").textContent="online"; $("socket-status").classList.add("online"); state.reconnectDelay=1000; };
  ws.onclose = () => { $("socket-status").textContent="offline"; $("socket-status").classList.remove("online"); if (state.socket !== ws) return; setTimeout(() => { if (state.socket === ws) connectSocket(); }, state.reconnectDelay); state.reconnectDelay=Math.min(state.reconnectDelay*2,15000); };
  ws.onmessage = (message) => { const payload=JSON.parse(message.data); if (payload.kind === "event") { addEvent(payload.event); refreshCampaign().catch(reportError); if (state.activeView === "player") refreshPlayerRuntime().catch(() => {}); } if (payload.kind === "state") { state.campaign=payload.state; renderCampaign(); } if (payload.kind === "knowledge_checkpoint" && state.activeView === "player") refreshPlayerRuntime().catch(reportError); };
}
