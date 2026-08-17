// src/dnd_rpg_engine/web/static/app.js
import { $, closeModal, reportError, state } from "./workbench-core.js";
import { loadEventHistory, loadJournal, refreshPlayerRuntime } from "./workbench-render.js";
import { addDemoActors, loadCampaigns, loadMarketplace, refreshCampaign, sendCommand, setView, showCreateCampaign, showDirector, showPlayerJoin, tick } from "./workbench-session.js";

document.querySelectorAll(".rail-link[data-view]").forEach((button) => {
  button.onclick = () => { if (!button.disabled) setView(button.dataset.view); };
});
$("modal-root").onclick = (event) => { if (event.target.id === "modal-root") closeModal(); };
$("open-create").onclick = showCreateCampaign;
$("reload-campaigns").onclick = () => loadCampaigns().catch(reportError);
$("reload-marketplace").onclick = () => loadMarketplace().catch(reportError);
$("refresh-current").onclick = () => refreshCampaign().catch(reportError);
$("clear-inspector").onclick = () => { $("gm-inspector").className="inspector empty"; $("gm-inspector").textContent="Select an actor, scene, or proposal."; };
document.querySelectorAll("[data-tick]").forEach((button) => button.onclick = () => tick(Number(button.dataset.tick)).catch(reportError));
$("gm-attack").onclick = () => sendCommand({type:"attack",actor_id:$("gm-actor").value,target_id:$("gm-target").value,action_id:"basic_attack"}).catch(reportError);
$("gm-wait").onclick = () => sendCommand({type:"wait",actor_id:$("gm-actor").value}).catch(reportError);
$("gm-add-demo").onclick = () => addDemoActors().catch(reportError);
$("open-director").onclick = () => showDirector().catch(reportError);
$("reload-director").onclick = () => showDirector().catch(reportError);
$("load-history").onclick = () => loadEventHistory("events").catch(reportError);
$("journal-refresh").onclick = () => loadJournal().catch(reportError);
$("change-player").onclick = showPlayerJoin;
$("player-refresh-knowledge").onclick = () => refreshPlayerRuntime().catch(reportError);
$("player-attack").onclick = () => sendCommand({type:"attack",actor_id:state.selectedPlayerActor,target_id:$("player-target").value,action_id:"basic_attack"}).then(refreshPlayerRuntime).catch(reportError);
$("player-wait").onclick = () => sendCommand({type:"wait",actor_id:state.selectedPlayerActor}).then(refreshPlayerRuntime).catch(reportError);

Promise.all([loadCampaigns(), loadMarketplace()]).catch(reportError);
