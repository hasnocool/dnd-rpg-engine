// src/dnd_rpg_engine/web/static/workbench-v39-utils.js
import { $, escapeHtml, state } from "./workbench-core.js";

export function campaignEntities() {
  const payload = state.campaign?.campaign || state.campaign || {};
  return Object.values(payload.entities || {});
}

export function isOwner() {
  return state.identity?.role === "owner";
}

export function selectedActorId() {
  if (!isOwner()) return state.selectedPlayerActor || state.identity?.actor_ids?.[0] || null;
  return $("tactical-actor")?.value || $("character-select")?.value || campaignEntities()[0]?.id || null;
}

export function fillSelect(select, rows, previous, label = (row) => row.name || row.id) {
  if (!select) return;
  select.innerHTML = rows.map((row) => `<option value="${escapeHtml(row.id)}">${escapeHtml(label(row))}</option>`).join("");
  if (rows.some((row) => row.id === previous)) select.value = previous;
}

export function metricRows(rows) {
  return rows.map(([label, value]) => `<div class="metric-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "—")}</strong></div>`).join("");
}

export function objectValues(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return Object.values(value);
  return [];
}

export function renderTacticalStage(container, entities, actorId, targetId) {
  container.innerHTML = "";
  if (!entities.length) { container.innerHTML = '<div class="empty">No visible entities.</div>'; return; }
  const xs = entities.map((e) => Number(e.position?.x ?? 0));
  const ys = entities.map((e) => Number(e.position?.y ?? 0));
  const minX = Math.min(...xs, 0), minY = Math.min(...ys, 0);
  const scale = 52;
  const width = Math.max(700, (Math.max(...xs, 8) - minX + 4) * scale);
  const height = Math.max(440, (Math.max(...ys, 6) - minY + 4) * scale);
  container.style.minWidth = `${Math.min(width, 2200)}px`;
  container.style.minHeight = `${Math.min(height, 1600)}px`;
  for (const entity of entities) {
    const x = 80 + (Number(entity.position?.x ?? 0) - minX) * scale;
    const y = 80 + (Number(entity.position?.y ?? 0) - minY) * scale;
    const node = document.createElement("button");
    node.className = `tactical-token ${entity.kind === "player" || entity.controller === "human" ? "player" : "enemy"} ${entity.id === actorId ? "selected" : ""} ${entity.id === targetId ? "targeted" : ""}`;
    node.style.left = `${x}px`; node.style.top = `${y}px`; node.type = "button";
    node.innerHTML = `<span class="token-label">${escapeHtml(entity.name || entity.id)}</span><span class="token-hp">HP ${escapeHtml(entity.resources?.hp ?? "—")}/${escapeHtml(entity.resources?.max_hp ?? "—")}</span>`;
    node.onclick = () => { if (entity.id !== actorId) { $("tactical-target").value = entity.id; $("tactical-target").dispatchEvent(new Event("change")); } };
    container.appendChild(node);
  }
}
