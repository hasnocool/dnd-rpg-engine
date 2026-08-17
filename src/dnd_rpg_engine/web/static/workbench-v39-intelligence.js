// src/dnd_rpg_engine/web/static/workbench-v39-intelligence.js
import { $, escapeHtml, jsonFetch, state } from "./workbench-core.js";
import { refreshCampaign } from "./workbench-session.js";
import { isOwner, metricRows } from "./workbench-v39-utils.js";

export async function loadDirectorWorkbench() {
  if (!isOwner()) throw new Error("GM owner permission required for AI Director controls");
  const [proposals, analytics, content] = await Promise.all([
    jsonFetch(`/api/v1/campaigns/${state.campaignId}/director/proposals`),
    jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/analytics`),
    jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/content`),
  ]);
  $("director-proposals").innerHTML = proposals.length ? proposals.map((proposal)=>`<article class="proposal-card"><div class="panel-heading"><div><span class="eyebrow">${escapeHtml(proposal.kind)}</span><strong>${escapeHtml(proposal.id)}</strong></div><span class="utility">${Number(proposal.utility ?? proposal.score ?? 0).toFixed(2)}</span></div><ul class="proposal-reasons">${(proposal.reasons||[]).map((reason)=>`<li>${escapeHtml(reason)}</li>`).join("")}</ul><pre class="output mono">${escapeHtml(JSON.stringify(proposal.payload||{},null,2))}</pre><div class="proposal-actions"><button data-director-accept="${escapeHtml(proposal.id)}" class="primary">Accept</button><button data-director-dismiss="${escapeHtml(proposal.id)}" class="ghost">Dismiss</button></div></article>`).join("") : '<div class="empty">No proposals right now.</div>';
  $("director-health").innerHTML = metricRows([["Pressure",Number(analytics.director_pressure||0).toFixed(2)],["Party entities",Object.keys(analytics.entity_health||{}).length],["Events",analytics.event_count],["Active scenes",(analytics.active_scene_ids||[]).join(", ")||"none"]]);
  $("director-decisions").innerHTML = (content.director_decisions||[]).slice().reverse().slice(0,20).map((row)=>`<div class="scene-row"><strong>${escapeHtml(row.proposal_id)}</strong><div class="small">${escapeHtml(row.decision)} · t=${escapeHtml(row.simulation_time)}</div>${row.note?`<div class="small">${escapeHtml(row.note)}</div>`:""}</div>`).join("") || '<div class="empty">No decisions recorded.</div>';
  document.querySelectorAll("[data-director-accept]").forEach((button)=>button.onclick=()=>directorDecision(button.dataset.directorAccept,"accept"));
  document.querySelectorAll("[data-director-dismiss]").forEach((button)=>button.onclick=()=>directorDecision(button.dataset.directorDismiss,"dismiss"));
}

async function directorDecision(proposalId, action) {
  const note = prompt(`${action === "accept" ? "Accept" : "Dismiss"} note (optional):`, "") || "";
  await jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/director/${encodeURIComponent(proposalId)}/${action}`, {method:"POST",body:JSON.stringify({note})});
  await refreshCampaign(); await loadDirectorWorkbench();
}

export async function loadKnowledge() {
  if (!isOwner()) throw new Error("GM owner permission required for knowledge debugging");
  const data = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/knowledge`);
  const truth = data.truth_entity_ids || [];
  const actors = Object.entries(data.actors || {});
  const thead = `<tr><th>Entity</th>${actors.map(([id])=>`<th>${escapeHtml(id)}</th>`).join("")}</tr>`;
  const tbody = truth.map((entityId)=>`<tr><td><strong>${escapeHtml(entityId)}</strong></td>${actors.map(([,knowledge])=>{ const known=(knowledge.known_entity_ids||[]).includes(entityId); const observed=knowledge.last_observed_at?.[entityId]; return `<td class="${known ? (observed == null ? "knowledge-stale" : "knowledge-known") : "knowledge-unknown"}">${known ? `known${observed==null?"":" @ "+Number(observed).toFixed(1)}` : "unknown"}</td>`; }).join("")}</tr>`).join("");
  $("knowledge-matrix").querySelector("thead").innerHTML = thead;
  $("knowledge-matrix").querySelector("tbody").innerHTML = tbody || '<tr><td>No entities.</td></tr>';
  $("knowledge-details").innerHTML = actors.map(([id,knowledge])=>`<article class="card"><strong>${escapeHtml(id)}</strong><div class="small">known entities ${(knowledge.known_entity_ids||[]).length} · facts ${Object.keys(knowledge.facts||{}).length}</div><pre class="output mono">${escapeHtml(JSON.stringify(knowledge.facts||{},null,2))}</pre></article>`).join("") || '<div class="empty">No player/human knowledge stores yet.</div>';
}

export async function loadAutomation() {
  if (!isOwner()) throw new Error("GM owner permission required for automation observability");
  const [content, analytics] = await Promise.all([jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/content`),jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/analytics`)]);
  $("automation-list").innerHTML = (content.automations||[]).map((row)=>`<article class="automation-card"><span class="eyebrow">${escapeHtml(row.section)}</span><strong>${escapeHtml(row.id)}</strong><div class="small">${escapeHtml(row.pack || "installed pack")}</div><pre>${escapeHtml(JSON.stringify(row.definition,null,2))}</pre></article>`).join("") || '<div class="empty">No installed schedules or dynamic events. Add them in Creator Studio.</div>';
  $("automation-clock").innerHTML = metricRows([["Simulation",`${Number(analytics.simulation_time||0).toFixed(2)}s`],["World minutes",analytics.world_minutes],["Active scenes",(analytics.active_scene_ids||[]).join(", ")||"none"],["Automation definitions",(content.automations||[]).length]]);
}

export function bindIntelligenceControls(reportError) {
  $("director-refresh").onclick=()=>loadDirectorWorkbench().catch(reportError);
  $("knowledge-refresh").onclick=()=>loadKnowledge().catch(reportError);
}
