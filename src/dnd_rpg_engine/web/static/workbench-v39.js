// src/dnd_rpg_engine/web/static/workbench-v39.js
import { $, escapeHtml, modal, reportError, state } from "./workbench-core.js";
import { refreshCampaign, setView, showDirector, tick } from "./workbench-session.js";
import { bindLobbyControls, loadLobby } from "./workbench-v39-lobby.js";
import { bindTacticalControls, loadTactical } from "./workbench-v39-tactical.js";
import { bindCharacterControls, loadCharacter, loadVisualRuntime } from "./workbench-v39-character.js";
import { bindIntelligenceControls, loadAutomation, loadDirectorWorkbench, loadKnowledge } from "./workbench-v39-intelligence.js";
import { bindOperationsControls, loadAnalytics, loadContent, loadReplay } from "./workbench-v39-operations.js";

// Static authority contract: v3.x UI stays bound to server-owned APIs.
const AUTHORITY_ROUTE_CONTRACT = [
  "/api/v1/campaigns", "/commands", "/timing", "/scenes/",
  "/director/proposals", "/runtime", "/events?after=0", "/ws?client_id=",
  "/workbench/session", "/workbench/tactical", "/workbench/analytics",
  "/workbench/knowledge", "/workbench/replay", "/workbench/content",
  "/characters/", "/distribution/releases", "/distribution/resolve",
];
void AUTHORITY_ROUTE_CONTRACT;

const viewLoaders={lobby:loadLobby,tactical:loadTactical,character:loadCharacter,visual:loadVisualRuntime,director:loadDirectorWorkbench,knowledge:loadKnowledge,automation:loadAutomation,analytics:loadAnalytics,replay:loadReplay,content:loadContent};
const viewContext={lobby:"Session identities, actor ownership, and parties",tactical:"Authoritative tactical play and action economy",character:"Character lifecycle, resources, and equipment",visual:"Canonical/redacted renderer projection",director:"Explainable GM intelligence proposals",knowledge:"GM-only knowledge authority debugger",automation:"Living-world schedules and dynamic triggers",analytics:"Persisted event and campaign analytics",replay:"Authoritative event timeline and event-source journal",content:"Installed packs, releases, dependencies, and locks"};

function handleViewError(error){reportError(error);const target=document.querySelector(`#view-${state.activeView} .panel`);if(target&&error?.message?.includes("permission"))target.insertAdjacentHTML("afterbegin",`<div class="empty">${escapeHtml(error.message)}</div>`);}
export function openV39View(name){setView(name);$("header-context").textContent=viewContext[name]||$("header-context").textContent;return viewLoaders[name]?.();}
document.querySelectorAll(".rail-link[data-view]").forEach((button)=>button.addEventListener("click",()=>{const name=button.dataset.view;if(button.disabled||!viewLoaders[name])return;$("header-context").textContent=viewContext[name]||$("header-context").textContent;viewLoaders[name]().catch(handleViewError);}));

function showCommandPalette(){
  const commands=[["GM Console",()=>setView("gm")],["Session Lobby",()=>openV39View("lobby")],["Tactical Workspace",()=>openV39View("tactical")],["Character Sheet",()=>openV39View("character")],["AI Director",()=>openV39View("director")],["Knowledge Inspector",()=>openV39View("knowledge")],["Analytics",()=>openV39View("analytics")],["Replay",()=>openV39View("replay")],["Automation",()=>openV39View("automation")],["Content Ecosystem",()=>openV39View("content")],["Advance time +10s",()=>tick(10)],["Advance time +1m",()=>tick(60)],["Refresh campaign",()=>refreshCampaign()],["Director quick view",()=>showDirector()]];
  modal("Command palette",`<label>Filter<input id="palette-filter" autofocus placeholder="Type a command…" /></label><div id="palette-results" class="stack compact"></div>`);
  const render=()=>{const q=$("palette-filter").value.toLowerCase();const filtered=commands.map((row,index)=>({...row,index})).filter((row)=>row[0].toLowerCase().includes(q));$("palette-results").innerHTML=filtered.map((row)=>`<button data-command-index="${row.index}" class="ghost">${escapeHtml(row[0])}</button>`).join("");document.querySelectorAll("[data-command-index]").forEach((button)=>button.onclick=()=>Promise.resolve(commands[Number(button.dataset.commandIndex)][1]()).catch(reportError));};
  $("palette-filter").oninput=render;render();
}

bindLobbyControls(reportError);bindTacticalControls(reportError);bindCharacterControls(reportError);bindIntelligenceControls(reportError);bindOperationsControls(reportError);
$("refresh-current").addEventListener("click",()=>{const loader=viewLoaders[state.activeView];if(loader)loader().catch(reportError);});
$("command-palette").onclick=showCommandPalette;
document.addEventListener("keydown",(event)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){event.preventDefault();showCommandPalette();}});
window.addEventListener("focus",()=>{const loader=viewLoaders[state.activeView];if(loader&&state.campaignId)loader().catch(()=>{});});
