const OPS = [
  "noop", "roll", "damage", "heal", "set", "increment", "consume_resource",
  "restore_resource", "apply_effect", "open_reaction", "if", "emit", "stop",
];

let editor = null;
let renderToken = 0;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let body = null;
  if (text) {
    try { body = JSON.parse(text); } catch { body = text; }
  }
  if (!response.ok) throw new Error(body?.detail || body || `${response.status} ${response.statusText}`);
  return body;
}

function activeRuleId() {
  if (document.querySelector("#workspace-kicker")?.textContent !== "RULES EDITOR") return null;
  return document.querySelector(".studio-object-row.active small")?.textContent?.trim() || null;
}

async function hydrateEditor() {
  const token = ++renderToken;
  const projectId = localStorage.getItem("rpg.creator.project");
  const ruleId = activeRuleId();
  const form = document.querySelector("#object-form");
  if (!projectId || !ruleId || !form || form.querySelector(".rule-graph-card")) return;
  try {
    const project = await request(`/api/v1/studio/projects/${encodeURIComponent(projectId)}`);
    if (token !== renderToken || activeRuleId() !== ruleId) return;
    const rule = project.pack?.rules?.[ruleId];
    if (!rule) return;
    const graph = structuredClone(rule.graph || {});
    graph.nodes ||= {};
    graph.effects ||= {};
    graph.entry ||= Object.keys(graph.nodes)[0] || null;
    graph.action_time_seconds ??= 0;
    graph.capabilities ||= [];
    editor = { projectId, ruleId, rule, graph, selected: graph.entry };
    mount(form);
  } catch (error) {
    console.warn("Rule graph editor unavailable", error);
  }
}

function mount(form) {
  const card = document.createElement("section");
  card.className = "rule-graph-card";
  card.innerHTML = `
    <div class="rule-graph-header">
      <div><h3>Executable Rule Graph</h3><small>Bounded declarative nodes compile directly into the authoritative RulesRuntime.</small></div>
      <div class="rule-graph-actions">
        <button type="button" data-rg="add">Add node</button>
        <button type="button" data-rg="validate">Validate graph</button>
        <button type="button" class="primary" data-rg="save">Save graph</button>
      </div>
    </div>
    <div class="rule-graph-toolbar">
      <label>Entry <select data-rg="entry"></select></label>
      <label>Action time <input data-rg="action-time" type="number" min="0" step="0.1" /></label>
      <label>Capabilities <input data-rg="capabilities" placeholder="reactions, conditions" /></label>
      <span data-rg="effects"></span>
    </div>
    <div class="rule-graph-layout">
      <div class="rule-graph-canvas-wrap"><svg id="rule-graph-canvas" viewBox="0 0 900 390"></svg></div>
      <aside class="rule-graph-inspector" data-rg="inspector"></aside>
    </div>
    <div class="rule-graph-status" data-rg="status">Graph has not been compiled yet.</div>`;
  const toolbar = form.querySelector(".studio-toolbar");
  if (toolbar) form.insertBefore(card, toolbar); else form.appendChild(card);

  card.querySelector('[data-rg="add"]').onclick = addNode;
  card.querySelector('[data-rg="validate"]').onclick = () => compileGraph(false);
  card.querySelector('[data-rg="save"]').onclick = () => compileGraph(true);
  card.querySelector('[data-rg="entry"]').onchange = (event) => {
    editor.graph.entry = event.target.value || null;
    editor.selected = editor.graph.entry;
    draw();
  };
  card.querySelector('[data-rg="action-time"]').oninput = (event) => editor.graph.action_time_seconds = Math.max(0, Number(event.target.value || 0));
  card.querySelector('[data-rg="capabilities"]').oninput = (event) => editor.graph.capabilities = csv(event.target.value);
  render();
}

function render() {
  const card = document.querySelector(".rule-graph-card");
  if (!card || !editor) return;
  const ids = Object.keys(editor.graph.nodes).sort();
  const entry = card.querySelector('[data-rg="entry"]');
  entry.innerHTML = `<option value="">— none —</option>${ids.map((id) => `<option value="${esc(id)}" ${editor.graph.entry === id ? "selected" : ""}>${esc(id)}</option>`).join("")}`;
  card.querySelector('[data-rg="action-time"]').value = editor.graph.action_time_seconds ?? 0;
  card.querySelector('[data-rg="capabilities"]').value = (editor.graph.capabilities || []).join(", ");
  card.querySelector('[data-rg="effects"]').textContent = `${Object.keys(editor.graph.effects || {}).length} effect definition(s)`;
  draw();
  inspector();
}

function layout() {
  const ids = Object.keys(editor.graph.nodes).sort();
  const positions = {};
  ids.forEach((id, index) => {
    const node = editor.graph.nodes[id];
    const stored = node.args?._ui;
    positions[id] = stored && Number.isFinite(Number(stored.x)) && Number.isFinite(Number(stored.y))
      ? { x: Number(stored.x), y: Number(stored.y) }
      : { x: 45 + (index % 4) * 205, y: 48 + Math.floor(index / 4) * 120 };
  });
  return positions;
}

function draw() {
  const svg = document.querySelector("#rule-graph-canvas");
  if (!svg || !editor) return;
  const positions = layout();
  const ids = Object.keys(editor.graph.nodes).sort();
  const rows = Math.max(1, Math.ceil(ids.length / 4));
  svg.setAttribute("viewBox", `0 0 900 ${Math.max(390, 70 + rows * 125)}`);
  svg.innerHTML = `<defs><marker id="rg-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="context-stroke"/></marker></defs>`;

  for (const id of ids) {
    const node = editor.graph.nodes[id];
    const from = positions[id];
    for (const [key, klass] of [["next", ""], ["on_success", "success"], ["on_failure", "failure"]]) {
      const targetId = node[key];
      const to = positions[targetId];
      if (!to) continue;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const x1 = from.x + 145, y1 = from.y + 32, x2 = to.x, y2 = to.y + 32;
      const bend = Math.max(45, Math.abs(x2 - x1) * .45);
      path.setAttribute("d", `M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`);
      path.setAttribute("class", `rule-graph-edge ${klass}`);
      path.setAttribute("marker-end", "url(#rg-arrow)");
      svg.appendChild(path);
    }
  }

  for (const id of ids) {
    const node = editor.graph.nodes[id];
    const p = positions[id];
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("transform", `translate(${p.x} ${p.y})`);
    group.setAttribute("class", `rule-graph-node ${id === editor.graph.entry ? "entry" : ""} ${id === editor.selected ? "selected" : ""}`);
    group.innerHTML = `<rect width="145" height="64"></rect><text x="12" y="25">${esc(id)}</text><text class="op" x="12" y="45">${esc(node.op)}</text>`;
    group.onclick = () => { editor.selected = id; draw(); inspector(); };
    svg.appendChild(group);
  }
}

function inspector() {
  const panel = document.querySelector('[data-rg="inspector"]');
  if (!panel || !editor) return;
  const node = editor.graph.nodes[editor.selected];
  if (!node) {
    panel.innerHTML = `<p class="studio-summary">Select a node to edit it.</p>`;
    return;
  }
  const ids = Object.keys(editor.graph.nodes).sort();
  const linkOptions = (value) => `<option value="">— none —</option>${ids.map((id) => `<option value="${esc(id)}" ${id === value ? "selected" : ""}>${esc(id)}</option>`).join("")}`;
  const args = Object.entries(node.args || {}).filter(([key]) => key !== "_ui");
  panel.innerHTML = `
    <h3>${esc(node.id)}</h3>
    <label>Operation<select data-rgi="op">${OPS.map((op) => `<option ${node.op === op ? "selected" : ""}>${op}</option>`).join("")}</select></label>
    <label>Next<select data-rgi="next">${linkOptions(node.next)}</select></label>
    <label>On success<select data-rgi="success">${linkOptions(node.on_success)}</select></label>
    <label>On failure<select data-rgi="failure">${linkOptions(node.on_failure)}</select></label>
    <h4>Arguments</h4>
    <div data-rgi="args">${args.map(([key, value], index) => argRow(key, value, index)).join("")}</div>
    <button type="button" data-rgi="add-arg">Add argument</button>
    <hr />
    <button type="button" class="danger" data-rgi="delete">Delete node</button>`;

  panel.querySelector('[data-rgi="op"]').onchange = (event) => { node.op = event.target.value; };
  panel.querySelector('[data-rgi="next"]').onchange = (event) => { node.next = event.target.value || null; draw(); };
  panel.querySelector('[data-rgi="success"]').onchange = (event) => { node.on_success = event.target.value || null; draw(); };
  panel.querySelector('[data-rgi="failure"]').onchange = (event) => { node.on_failure = event.target.value || null; draw(); };
  panel.querySelector('[data-rgi="add-arg"]').onclick = () => {
    const host = panel.querySelector('[data-rgi="args"]');
    host.insertAdjacentHTML("beforeend", argRow("", "", host.children.length));
    bindArgRows(node);
  };
  panel.querySelector('[data-rgi="delete"]').onclick = deleteNode;
  bindArgRows(node);
}

function argRow(key, value, index) {
  const printable = Array.isArray(value) ? value.join(", ") : (typeof value === "object" ? String(value ?? "") : String(value ?? ""));
  return `<div class="rule-arg-row" data-arg-row="${index}"><label>Key<input data-arg="key" value="${esc(key)}" /></label><label>Value<input data-arg="value" value="${esc(printable)}" /></label><button type="button" class="danger" data-arg="remove">×</button></div>`;
}

function bindArgRows(node) {
  const rows = [...document.querySelectorAll(".rule-arg-row")];
  const commit = () => {
    const ui = node.args?._ui;
    const next = {};
    for (const row of rows) {
      const key = row.querySelector('[data-arg="key"]').value.trim();
      if (!key) continue;
      next[key] = parseArg(key, row.querySelector('[data-arg="value"]').value);
    }
    if (ui) next._ui = ui;
    node.args = next;
  };
  for (const row of rows) {
    row.querySelector('[data-arg="key"]').oninput = commit;
    row.querySelector('[data-arg="value"]').oninput = commit;
    row.querySelector('[data-arg="remove"]').onclick = () => { row.remove(); bindArgRows(node); commit(); };
  }
}

function parseArg(key, rawValue) {
  const raw = String(rawValue ?? "").trim();
  if (["tags", "options"].includes(key)) return csv(raw);
  if (raw === "true") return true;
  if (raw === "false") return false;
  if (raw === "null") return null;
  if (raw !== "" && Number.isFinite(Number(raw))) return Number(raw);
  return raw;
}

function csv(value) { return String(value || "").split(",").map((item) => item.trim()).filter(Boolean); }

function addNode() {
  if (!editor) return;
  let index = Object.keys(editor.graph.nodes).length + 1;
  let id = `node_${index}`;
  while (editor.graph.nodes[id]) id = `node_${++index}`;
  editor.graph.nodes[id] = { id, op: "noop", args: {}, next: null, on_success: null, on_failure: null };
  editor.graph.entry ||= id;
  editor.selected = id;
  render();
}

function deleteNode() {
  if (!editor?.selected) return;
  const removed = editor.selected;
  delete editor.graph.nodes[removed];
  for (const node of Object.values(editor.graph.nodes)) {
    if (node.next === removed) node.next = null;
    if (node.on_success === removed) node.on_success = null;
    if (node.on_failure === removed) node.on_failure = null;
  }
  if (editor.graph.entry === removed) editor.graph.entry = Object.keys(editor.graph.nodes).sort()[0] || null;
  editor.selected = editor.graph.entry;
  render();
}

async function compileGraph(save) {
  if (!editor) return;
  const status = document.querySelector('[data-rg="status"]');
  status.className = "rule-graph-status";
  status.textContent = save ? "Validating and saving…" : "Compiling…";
  try {
    const result = await request(`/api/v1/studio/projects/${encodeURIComponent(editor.projectId)}/rules/${encodeURIComponent(editor.ruleId)}/compile`, {
      method: "POST",
      body: JSON.stringify({ graph: editor.graph, save }),
    });
    status.className = "rule-graph-status good";
    status.textContent = `Valid · ${result.node_count} nodes · hash ${result.graph_hash.slice(0, 16)}…${save ? ` · revision ${result.revision}` : ""}`;
    if (save) setTimeout(() => window.location.reload(), 350);
  } catch (error) {
    status.className = "rule-graph-status bad";
    status.textContent = `Invalid graph: ${error.message}`;
  }
}

const observer = new MutationObserver(() => queueMicrotask(hydrateEditor));
const form = document.querySelector("#object-form");
if (form) observer.observe(form, { childList: true, subtree: false });
document.querySelector("#section-tabs")?.addEventListener("click", () => setTimeout(hydrateEditor, 0));
document.querySelector("#object-list")?.addEventListener("click", () => setTimeout(hydrateEditor, 0));
hydrateEditor();
