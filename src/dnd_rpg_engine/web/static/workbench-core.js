// src/dnd_rpg_engine/web/static/workbench-core.js
export const $ = (id) => document.getElementById(id);

export const state = {
  campaignId: null,
  clientId: null,
  accessToken: null,
  identity: null,
  campaign: null,
  runtime: null,
  socket: null,
  reconnectDelay: 1000,
  events: [],
  activeView: "library",
  selectedPlayerActor: null,
};

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    "\"": "&quot;",
  })[ch]);
}

export function toast(message, kind = "info") {
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.textContent = message;
  $("toasts").appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

export async function jsonFetch(url, options = {}) {
  const headers = {"Content-Type": "application/json", ...(options.headers || {})};
  if (state.clientId) headers["X-RPG-Client-ID"] = state.clientId;
  if (state.accessToken) headers.Authorization = `Bearer ${state.accessToken}`;
  const response = await fetch(url, {...options, headers});
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = body?.detail ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export function modal(title, body, actions = "") {
  $("modal-root").innerHTML = `
    <div class="modal">
      <div class="panel-heading"><h2>${escapeHtml(title)}</h2><button id="modal-close" class="ghost">Close</button></div>
      ${body}
      ${actions ? `<div class="modal-actions">${actions}</div>` : ""}
    </div>`;
  $("modal-root").classList.remove("hidden");
  $("modal-close").onclick = closeModal;
}

export function closeModal() {
  $("modal-root").classList.add("hidden");
}

export function reportError(error) {
  console.error(error);
  toast(error?.message || String(error), "error");
}
