// src/dnd_rpg_engine/web/static/workbench-v39-operations.js
import { $, escapeHtml, jsonFetch, state, toast } from "./workbench-core.js";
import { isOwner, metricRows } from "./workbench-v39-utils.js";

let replayData=null;

export async function loadAnalytics() {
  if (!isOwner()) throw new Error("GM owner permission required for campaign analytics");
  const [data, events] = await Promise.all([jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/analytics`),jsonFetch(`/api/v1/campaigns/${state.campaignId}/events?after=0&limit=1000`)]);
  $("analytics-metrics").innerHTML = [["Events",data.event_count],["Simulation",`${Number(data.simulation_time||0).toFixed(1)}s`],["World minutes",data.world_minutes],["Director pressure",Number(data.director_pressure||0).toFixed(2)],["Active scenes",(data.active_scene_ids||[]).length]].map(([label,value])=>`<div class="metric-tile"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  renderBars($("analytics-events"), data.event_types || {});
  renderBars($("analytics-actors"), data.actors || {});
  $("analytics-totals").innerHTML = metricRows(Object.entries(data.numeric_totals || {}));
  $("analytics-health").innerHTML = Object.entries(data.entity_health || {}).map(([id,row])=>`<article class="card"><strong>${escapeHtml(row.name || id)}</strong><div class="small">${escapeHtml(id)} · ${row.alive ? "alive" : "inactive"}</div><div class="small">HP ${escapeHtml(row.hp)}/${escapeHtml(row.max_hp)}</div></article>`).join("") || '<div class="empty">No entities.</div>';
  const rules = events.filter((event)=>String(event.type||"").startsWith("rules.") || event.payload?.trace || event.payload?.traces).slice(-20).reverse();
  $("analytics-rules").innerHTML = rules.map((event)=>`<div class="scene-row"><strong>${escapeHtml(event.type)}</strong><div class="small">t=${Number(event.simulation_time||0).toFixed(2)}</div><pre class="output mono">${escapeHtml(JSON.stringify(event.payload||{},null,2))}</pre></div>`).join("") || '<div class="empty">No rule trace events in the latest history window.</div>';
}

function renderBars(container, values) {
  const entries = Object.entries(values); const max = Math.max(...entries.map(([,value])=>Number(value)||0),1);
  container.innerHTML = entries.slice(0,25).map(([label,value])=>`<div class="bar-row"><span>${escapeHtml(label)}</span><div class="bar-track"><span style="width:${Math.max(2,(Number(value)||0)/max*100)}%"></span></div><strong>${escapeHtml(value)}</strong></div>`).join("") || '<div class="empty">No data.</div>';
}

export async function loadReplay() {
  if (!isOwner()) throw new Error("GM owner permission required for replay/journal inspection");
  replayData = await jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/replay`);
  const events = replayData.events || [];
  $("replay-slider").max = String(Math.max(0,events.length-1));
  $("replay-slider").value = String(Math.max(0,events.length-1));
  renderReplayPosition();
  $("replay-timeline").innerHTML = events.map((event,index)=>`<span class="replay-tick ${index===events.length-1?"active":""}" data-replay-tick="${index}" style="height:${8 + ((index*17)%24)}px" title="${escapeHtml(event.type||"event")}"></span>`).join("");
  $("replay-branch-status").className = replayData.branching_available ? "scene-row" : "empty";
  $("replay-branch-status").textContent = replayData.branching_available ? `Event-source journal detected. Head: ${replayData.event_source_head?.sequence ?? "—"}` : replayData.note;
  $("replay-journal").innerHTML = (replayData.journal_entries||[]).slice(-30).reverse().map((entry)=>`<div class="scene-row"><strong>#${escapeHtml(entry.sequence ?? "?")} ${escapeHtml(entry.command_id || "command")}</strong><div class="small">${escapeHtml(entry.state_hash || "")}</div></div>`).join("") || '<div class="empty">No EventSourcedEngine journal entries for this campaign.</div>';
}

export function renderReplayPosition() {
  const events = replayData?.events || []; const index = Math.min(events.length-1,Math.max(0,Number($("replay-slider").value)||0)); const event = events[index];
  $("replay-position").textContent = events.length ? `${index+1} / ${events.length}` : "0 / 0";
  $("replay-event").className = event ? "replay-card" : "replay-card empty";
  $("replay-event").innerHTML = event ? `<div class="panel-heading"><strong>${escapeHtml(event.type||"event")}</strong><span class="badge">t=${Number(event.simulation_time||0).toFixed(2)}</span></div><div class="small">actor ${escapeHtml(event.actor_id||"—")} · target ${escapeHtml(event.target_id||"—")}</div><pre>${escapeHtml(JSON.stringify(event.payload||{},null,2))}</pre>` : "No events.";
  document.querySelectorAll("[data-replay-tick]").forEach((tick)=>tick.classList.toggle("active",Number(tick.dataset.replayTick)===index));
}

export async function loadContent() {
  if (!isOwner()) throw new Error("GM owner permission required for campaign content management");
  const [content,releases,locks] = await Promise.all([jsonFetch(`/api/v1/campaigns/${state.campaignId}/workbench/content`),jsonFetch("/api/v1/distribution/releases"),jsonFetch("/api/v1/distribution/locks")]);
  $("content-installed").innerHTML = (content.packs||[]).map((pack)=>`<article class="campaign-card"><div><h3>${escapeHtml(pack.name||pack.id||pack.install_id)}</h3><div class="small">${escapeHtml(pack.id||"")} @ ${escapeHtml(pack.version||"?")}</div></div><div class="small">${escapeHtml(pack.author||"unknown")} · ${escapeHtml(pack.license||"unspecified")}</div><div class="small">dependencies ${escapeHtml(JSON.stringify(pack.dependencies||{}))}</div><div class="small">sections ${escapeHtml(JSON.stringify(pack.sections||{}))}</div></article>`).join("") || '<div class="empty">No installed content-pack metadata was found.</div>';
  $("content-releases").innerHTML = (releases||[]).slice().reverse().slice(0,80).map((release)=>`<article class="card"><strong>${escapeHtml(release.package_id||release.id||"package")}</strong><div class="small">version ${escapeHtml(release.version||"?")} · engine ${escapeHtml(release.engine_version||release.engine_requirement||"—")}</div><div class="small">${escapeHtml(release.content_hash||"")}</div></article>`).join("") || '<div class="empty">No distribution releases.</div>';
  $("content-locks").textContent = JSON.stringify(locks,null,2);
  const requirements = Object.fromEntries((content.packs||[]).filter((pack)=>pack.id&&pack.version).map((pack)=>[pack.id,`>=${pack.version}`]));
  if ($("content-requirements").value.trim()==="{}") $("content-requirements").value=JSON.stringify(requirements,null,2);
}

export async function resolveContent() {
  let requirements; try { requirements=JSON.parse($("content-requirements").value||"{}"); } catch { return toast("Requirements must be valid JSON", "error"); }
  const result=await jsonFetch("/api/v1/distribution/resolve",{method:"POST",body:JSON.stringify({requirements})}); $("content-resolution").textContent=JSON.stringify(result,null,2);
}

export function bindOperationsControls(reportError) {
  $("analytics-refresh").onclick=()=>loadAnalytics().catch(reportError);
  $("replay-refresh").onclick=()=>loadReplay().catch(reportError);
  $("replay-slider").oninput=renderReplayPosition;
  $("content-refresh").onclick=()=>loadContent().catch(reportError);
  $("content-resolve").onclick=()=>resolveContent().catch(reportError);
}
