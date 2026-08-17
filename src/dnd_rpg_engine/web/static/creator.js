// src/dnd_rpg_engine/web/static/creator.js

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  project: null,
  section: "maps",
  selectedId: null,
  selectedNodes: [],
  dragging: null,
  dirty: false,
};

const sectionLabels = {
  maps: "MAP EDITOR",
  creatures: "CREATURE EDITOR",
  rules: "RULES EDITOR",
  spells: "SPELL EDITOR",
  quests: "QUEST EDITOR",
  campaigns: "CAMPAIGN EDITOR",
};

const defaults = {
  maps: (id) => ({ id, name: titleCase(id), nodes: {}, edges: [] }),
  creatures: (id) => ({
    id,
    name: titleCase(id),
    tier: 1,
    hp: 10,
    stats: { strength: 10, dexterity: 10, constitution: 10, intelligence: 10, wisdom: 10, charisma: 10 },
    actions: ["basic_attack"],
    tags: [],
    ai_profile: "hostile_basic",
  }),
  rules: (id) => ({ id, name: titleCase(id), settings: {}, expressions: {} }),
  spells: (id) => ({
    id,
    name: titleCase(id),
    cast_time: 6,
    range: 12,
    energy_cost: 0,
    attack_ability: "intelligence",
    damage: null,
    heal: null,
    damage_type: "arcane",
    applies_condition: null,
    duration: null,
    interruptible: true,
    tags: [],
  }),
  quests: (id) => ({ id, name: titleCase(id), description: "", objectives: [], reward_currency: 0, set_flags: {} }),
  campaigns: (id) => ({ id, name: titleCase(id), description: "", active_rule_id: null, start_map_id: null, entities: [], flags: {} }),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let body = null;
  const text = await response.text();
  if (text) {
    try { body = JSON.parse(text); } catch { body = text; }
  }
  if (!response.ok) {
    const detail = body?.detail ?? body ?? `${response.status} ${response.statusText}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

function slug(value) {
  return String(value || "new_item")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, "_")
    .replace(/^[_\-.]+|[_\-.]+$/g, "") || "new_item";
}

function titleCase(value) {
  return String(value || "")
    .replace(/[_.-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function csv(value) {
  return String(value || "").split(",").map((part) => part.trim()).filter(Boolean);
}

function nullable(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed : null;
}

function numberOrNull(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed === "" ? null : Number(trimmed);
}

function pack() {
  return state.project?.pack || null;
}

function currentCollection() {
  return pack()?.[state.section] || {};
}

function selectedObject() {
  return state.selectedId ? currentCollection()[state.selectedId] : null;
}

function markDirty(dirty = true) {
  state.dirty = dirty;
  const pill = $("#save-state");
  pill.textContent = dirty ? "Unsaved changes" : "Saved";
  pill.classList.toggle("dirty", dirty);
  pill.classList.toggle("saved", !dirty);
}

function applyProject(project) {
  state.project = project;
  state.dirty = false;
  localStorage.setItem("rpg.creator.project", project.id);
  $("#project-name").value = project.name;
  $("#pack-id").value = project.pack.manifest.id;
  $("#pack-version").value = project.pack.manifest.version;
  $("#pack-license").value = project.pack.manifest.license;
  $("#pack-author").value = project.pack.manifest.author;
  $("#revision-state").textContent = `Revision ${project.revision}`;
  $("#restore-revision").max = String(project.revision);
  $("#restore-revision").value = String(project.revision);
  markDirty(false);
  renderAll();
}

async function createProject() {
  const manifest = {
    id: slug($("#pack-id").value),
    name: $("#project-name").value.trim() || "New Adventure",
    version: $("#pack-version").value.trim() || "1.0.0",
    author: $("#pack-author").value.trim() || "creator",
    license: $("#pack-license").value.trim() || "unspecified",
    description: "",
    dependencies: {},
    tags: [],
  };
  const project = await api("/api/v1/studio/projects", {
    method: "POST",
    body: JSON.stringify({ name: manifest.name, manifest }),
  });
  state.selectedId = null;
  state.selectedNodes = [];
  applyProject(project);
  log(`Created project ${project.id}`);
}

async function loadInitialProject() {
  const id = localStorage.getItem("rpg.creator.project");
  if (id) {
    try {
      applyProject(await api(`/api/v1/studio/projects/${encodeURIComponent(id)}`));
      return;
    } catch (error) {
      localStorage.removeItem("rpg.creator.project");
      log(`Previous project unavailable: ${error.message}`);
    }
  }
  await createProject();
}

async function saveManifest() {
  if (!state.project) return;
  const manifest = {
    ...state.project.pack.manifest,
    id: slug($("#pack-id").value),
    name: $("#project-name").value.trim() || "New Adventure",
    version: $("#pack-version").value.trim() || "1.0.0",
    author: $("#pack-author").value.trim() || "creator",
    license: $("#pack-license").value.trim() || "unspecified",
  };
  applyProject(await api(`/api/v1/studio/projects/${state.project.id}/manifest`, {
    method: "PUT",
    body: JSON.stringify(manifest),
  }));
  log("Project metadata saved.");
}

async function upsert(section, id, payload) {
  const project = await api(
    `/api/v1/studio/projects/${state.project.id}/${section}/${encodeURIComponent(id)}`,
    { method: "PUT", body: JSON.stringify({ payload }) },
  );
  applyProject(project);
  state.section = section;
  state.selectedId = id;
  renderAll();
  return project;
}

async function deleteSelected() {
  if (!state.selectedId || !state.project) return;
  if (!confirm(`Delete ${state.section.slice(0, -1)} “${state.selectedId}”?`)) return;
  try {
    const project = await api(
      `/api/v1/studio/projects/${state.project.id}/${state.section}/${encodeURIComponent(state.selectedId)}`,
      { method: "DELETE" },
    );
    state.selectedId = null;
    state.selectedNodes = [];
    applyProject(project);
    log("Object deleted.");
  } catch (error) {
    showError(error);
  }
}

function renderAll() {
  renderObjectList();
  renderWorkspace();
  renderCounts();
}

function renderObjectList() {
  const list = $("#object-list");
  list.innerHTML = "";
  if (!state.project) return;
  const filter = $("#library-filter").value.trim().toLowerCase();
  const rows = Object.values(currentCollection())
    .filter((row) => !filter || `${row.id} ${row.name || ""}`.toLowerCase().includes(filter))
    .sort((a, b) => String(a.name || a.id).localeCompare(String(b.name || b.id)));
  if (!rows.length) {
    list.innerHTML = `<div class="studio-summary">No ${state.section} yet. Use <strong>New</strong> to create one.</div>`;
    return;
  }
  for (const row of rows) {
    const element = document.createElement("div");
    element.className = `studio-object-row ${state.selectedId === row.id ? "active" : ""}`;
    element.innerHTML = `<div><strong>${escapeHtml(row.name || row.id)}</strong><small>${escapeHtml(row.id)}</small></div><span>›</span>`;
    element.addEventListener("click", () => {
      state.selectedId = row.id;
      state.selectedNodes = [];
      renderAll();
    });
    list.appendChild(element);
  }
}

function renderWorkspace() {
  $("#workspace-kicker").textContent = sectionLabels[state.section];
  const object = selectedObject();
  $("#workspace-title").textContent = object?.name || `Select or create ${state.section.slice(0, -1)}`;
  $("#map-workspace").classList.toggle("hidden", state.section !== "maps");
  $("#form-workspace").classList.toggle("hidden", state.section === "maps");
  $("#map-inspector").classList.toggle("hidden", state.section !== "maps");
  renderWorkspaceActions();
  if (state.section === "maps") renderMap();
  else renderObjectForm();
}

function renderWorkspaceActions() {
  const actions = $("#workspace-actions");
  actions.innerHTML = "";
  if (!state.selectedId) return;
  const remove = document.createElement("button");
  remove.className = "danger";
  remove.textContent = "Delete";
  remove.addEventListener("click", deleteSelected);
  actions.appendChild(remove);
}

async function createObject() {
  if (!state.project) return;
  const proposed = prompt(`New ${state.section.slice(0, -1)} ID:`, `new_${state.section.slice(0, -1)}`);
  if (!proposed) return;
  const id = slug(proposed);
  if (currentCollection()[id]) {
    showError(new Error(`${id} already exists`));
    return;
  }
  try {
    await upsert(state.section, id, defaults[state.section](id));
    log(`Created ${state.section.slice(0, -1)} ${id}.`);
  } catch (error) {
    showError(error);
  }
}

function renderMap() {
  const worldMap = selectedObject();
  const canvas = $("#map-canvas");
  $("#map-edges").innerHTML = "";
  $("#map-nodes").innerHTML = "";
  $("#node-inspector").classList.add("hidden");
  $("#edge-inspector").classList.add("hidden");
  if (!worldMap) {
    $("#map-summary").textContent = "No map selected.";
    canvas.classList.add("empty");
    return;
  }
  canvas.classList.remove("empty");
  const nodes = worldMap.nodes || {};
  const edges = worldMap.edges || [];
  $("#map-summary").textContent = `${Object.keys(nodes).length} nodes · ${edges.length} connections`;

  for (const edge of edges) {
    const source = nodes[edge.source];
    const target = nodes[edge.target];
    if (!source || !target) continue;
    const group = svg("g", {});
    const line = svg("line", {
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
      class: `studio-edge ${edge.bidirectional ? "" : "directed"}`,
    });
    group.appendChild(line);
    const label = svg("text", {
      x: (source.x + target.x) / 2,
      y: (source.y + target.y) / 2 - 7,
      class: "studio-edge-label",
    });
    label.textContent = `${edge.travel_time ?? 1}`;
    group.appendChild(label);
    $("#map-edges").appendChild(group);
  }

  for (const node of Object.values(nodes)) {
    const group = svg("g", {
      transform: `translate(${node.x} ${node.y})`,
      class: `studio-node ${state.selectedNodes.includes(node.id) ? "selected" : ""}`,
      "data-node-id": node.id,
    });
    group.appendChild(svg("circle", { cx: 0, cy: 0 }));
    const name = svg("text", { x: 0, y: -3 });
    name.textContent = node.name || node.id;
    group.appendChild(name);
    const id = svg("text", { x: 0, y: 13, class: "node-id" });
    id.textContent = node.id;
    group.appendChild(id);
    bindNodePointer(group, node.id);
    $("#map-nodes").appendChild(group);
  }
  renderNodeInspector();
}

function bindNodePointer(element, nodeId) {
  element.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    element.setPointerCapture(event.pointerId);
    if (event.shiftKey) toggleNodeSelection(nodeId, true);
    else if (!state.selectedNodes.includes(nodeId)) state.selectedNodes = [nodeId];
    const point = svgPoint(event);
    const node = selectedObject().nodes[nodeId];
    state.dragging = { nodeId, offsetX: point.x - node.x, offsetY: point.y - node.y, pointerId: event.pointerId };
    element.classList.add("dragging");
    renderNodeInspector();
    renderMapSelectionOnly();
  });
  element.addEventListener("pointermove", (event) => {
    if (!state.dragging || state.dragging.nodeId !== nodeId) return;
    const point = svgPoint(event);
    const node = selectedObject().nodes[nodeId];
    node.x = Math.round(point.x - state.dragging.offsetX);
    node.y = Math.round(point.y - state.dragging.offsetY);
    markDirty();
    renderMap();
  });
  element.addEventListener("pointerup", async () => {
    if (!state.dragging || state.dragging.nodeId !== nodeId) return;
    state.dragging = null;
    try {
      const node = selectedObject().nodes[nodeId];
      const project = await api(
        `/api/v1/studio/projects/${state.project.id}/maps/${state.selectedId}/nodes/${nodeId}`,
        { method: "PATCH", body: JSON.stringify({ x: node.x, y: node.y, z: node.z ?? 0 }) },
      );
      applyProject(project);
      state.selectedId = state.selectedId || selectedObject()?.id;
    } catch (error) {
      showError(error);
    }
  });
  element.addEventListener("click", (event) => {
    if (event.shiftKey) toggleNodeSelection(nodeId, true);
    else state.selectedNodes = [nodeId];
    renderMap();
  });
}

function renderMapSelectionOnly() {
  $$(".studio-node").forEach((node) => node.classList.toggle("selected", state.selectedNodes.includes(node.dataset.nodeId)));
}

function toggleNodeSelection(nodeId, multi = false) {
  if (!multi) state.selectedNodes = [nodeId];
  else if (state.selectedNodes.includes(nodeId)) state.selectedNodes = state.selectedNodes.filter((id) => id !== nodeId);
  else state.selectedNodes = [...state.selectedNodes, nodeId].slice(-2);
  renderNodeInspector();
}

function renderNodeInspector() {
  const worldMap = selectedObject();
  if (!worldMap) return;
  const nodeId = state.selectedNodes.at(-1);
  const node = nodeId ? worldMap.nodes?.[nodeId] : null;
  $("#node-inspector").classList.toggle("hidden", !node);
  if (node) {
    $("#node-id").value = node.id;
    $("#node-name").value = node.name || "";
    $("#node-description").value = node.description || "";
    $("#node-x").value = node.x ?? 0;
    $("#node-y").value = node.y ?? 0;
    $("#node-z").value = node.z ?? 0;
    $("#node-tags").value = [...(node.tags || [])].join(", ");
  }
  const canConnect = state.selectedNodes.length === 2;
  $("#map-connect").disabled = !canConnect;
  $("#edge-selection").textContent = canConnect ? `${state.selectedNodes[0]} → ${state.selectedNodes[1]}` : "Select two nodes.";
}

async function addMapNode() {
  const worldMap = selectedObject();
  if (!worldMap) return showError(new Error("Select a map first."));
  const proposed = prompt("Node ID:", `node_${Object.keys(worldMap.nodes || {}).length + 1}`);
  if (!proposed) return;
  const id = slug(proposed);
  const count = Object.keys(worldMap.nodes || {}).length;
  const node = { id, name: titleCase(id), description: "", x: 160 + (count % 4) * 220, y: 130 + Math.floor(count / 4) * 170, z: 0, tags: [] };
  try {
    const project = await api(`/api/v1/studio/projects/${state.project.id}/maps/${state.selectedId}/nodes`, {
      method: "POST",
      body: JSON.stringify(node),
    });
    applyProject(project);
    state.selectedId = worldMap.id;
    state.selectedNodes = [id];
    renderAll();
  } catch (error) { showError(error); }
}

async function saveNode() {
  const worldMap = selectedObject();
  const nodeId = state.selectedNodes.at(-1);
  if (!worldMap || !nodeId) return;
  const node = worldMap.nodes[nodeId];
  node.name = $("#node-name").value.trim() || node.id;
  node.description = $("#node-description").value;
  node.x = Number($("#node-x").value || 0);
  node.y = Number($("#node-y").value || 0);
  node.z = Number($("#node-z").value || 0);
  node.tags = csv($("#node-tags").value);
  try {
    await upsert("maps", worldMap.id, worldMap);
    state.selectedNodes = [nodeId];
    renderAll();
  } catch (error) { showError(error); }
}

async function createEdge() {
  if (state.selectedNodes.length !== 2) return;
  const [source, target] = state.selectedNodes;
  try {
    const project = await api(`/api/v1/studio/projects/${state.project.id}/maps/${state.selectedId}/edges`, {
      method: "POST",
      body: JSON.stringify({
        source,
        target,
        travel_time: Math.max(.01, Number($("#edge-travel-time").value || 1)),
        bidirectional: $("#edge-bidirectional").checked,
        requirements: {},
      }),
    });
    applyProject(project);
    state.selectedId = selectedObject()?.id || state.selectedId;
    state.selectedNodes = [];
    $("#edge-inspector").classList.add("hidden");
    renderAll();
  } catch (error) { showError(error); }
}

function svgPoint(event) {
  const svgElement = $("#map-canvas");
  const rect = svgElement.getBoundingClientRect();
  const viewBox = svgElement.viewBox.baseVal;
  return {
    x: viewBox.x + ((event.clientX - rect.left) / rect.width) * viewBox.width,
    y: viewBox.y + ((event.clientY - rect.top) / rect.height) * viewBox.height,
  };
}

function svg(tag, attributes) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

function renderObjectForm() {
  const form = $("#object-form");
  const object = selectedObject();
  if (!object) {
    form.innerHTML = `<div class="studio-summary">Select an object from the library or create a new one.</div>`;
    return;
  }
  if (state.section === "creatures") renderCreatureForm(form, object);
  else if (state.section === "spells") renderSpellForm(form, object);
  else if (state.section === "quests") renderQuestForm(form, object);
  else if (state.section === "rules") renderRuleForm(form, object);
  else if (state.section === "campaigns") renderCampaignForm(form, object);
  form.oninput = () => markDirty();
}

function renderCreatureForm(form, creature) {
  const stats = creature.stats || {};
  form.innerHTML = `
    <section class="studio-form-section"><h3>Identity</h3><div class="studio-form-grid">
      ${field("Name", "name", creature.name, "wide")}
      ${numberField("Tier", "tier", creature.tier ?? 1, 1)}
      ${numberField("Hit points", "hp", creature.hp ?? 10, 1)}
      ${field("AI profile", "ai_profile", creature.ai_profile || "hostile_basic")}
      ${field("Actions", "actions", (creature.actions || []).join(", "))}
      ${field("Tags", "tags", (creature.tags || []).join(", "), "wide")}
    </div></section>
    <section class="studio-form-section"><h3>Ability scores</h3><div class="studio-form-grid studio-stat-grid">
      ${["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"].map((key) => numberField(titleCase(key), `stat-${key}`, stats[key] ?? 10, 1)).join("")}
    </div></section>
    ${saveButtons()}`;
  bindSave(async () => {
    const payload = {
      ...creature,
      name: value("name"),
      tier: num("tier"),
      hp: num("hp"),
      ai_profile: value("ai_profile"),
      actions: csv(value("actions")),
      tags: csv(value("tags")),
      stats: Object.fromEntries(["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"].map((key) => [key, num(`stat-${key}`)])),
    };
    await upsert("creatures", creature.id, payload);
  });
}

function renderSpellForm(form, spell) {
  form.innerHTML = `
    <section class="studio-form-section"><h3>Spell</h3><div class="studio-form-grid">
      ${field("Name", "name", spell.name, "wide")}
      ${numberField("Cast time (s)", "cast_time", spell.cast_time ?? 6, .1)}
      ${numberField("Range", "range", spell.range ?? 12, .1)}
      ${numberField("Energy cost", "energy_cost", spell.energy_cost ?? 0, 1)}
      ${selectField("Attack ability", "attack_ability", spell.attack_ability || "intelligence", ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"])}
      ${field("Damage formula", "damage", spell.damage || "")}
      ${field("Healing formula", "heal", spell.heal || "")}
      ${field("Damage type", "damage_type", spell.damage_type || "arcane")}
      ${field("Condition", "applies_condition", spell.applies_condition || "")}
      ${numberField("Duration (s)", "duration", spell.duration ?? "", .1)}
      ${field("Tags", "tags", (spell.tags || []).join(", "), "wide")}
      ${checkField("Interruptible", "interruptible", spell.interruptible !== false)}
    </div></section>
    ${saveButtons()}`;
  bindSave(async () => upsert("spells", spell.id, {
    ...spell,
    name: value("name"), cast_time: num("cast_time"), range: num("range"), energy_cost: num("energy_cost"),
    attack_ability: value("attack_ability"), damage: nullable(value("damage")), heal: nullable(value("heal")),
    damage_type: value("damage_type"), applies_condition: nullable(value("applies_condition")), duration: numberOrNull(value("duration")),
    interruptible: checked("interruptible"), tags: csv(value("tags")),
  }));
}

function renderQuestForm(form, quest) {
  const objectives = quest.objectives || [];
  form.innerHTML = `
    <section class="studio-form-section"><h3>Quest</h3><div class="studio-form-grid">
      ${field("Name", "name", quest.name, "wide")}
      ${textareaField("Description", "description", quest.description || "", "wide")}
      ${numberField("Reward currency", "reward_currency", quest.reward_currency ?? 0, 1)}
    </div></section>
    <section class="studio-form-section"><div class="studio-panel-title"><h3>Objectives</h3><button type="button" id="add-objective">Add objective</button></div>
      <div id="objective-list" class="studio-inline-list">
        ${objectives.map((objective, index) => objectiveRow(objective, index)).join("") || '<div class="studio-summary">No objectives yet.</div>'}
      </div>
    </section>${saveButtons()}`;
  $("#add-objective").onclick = () => {
    quest.objectives = [...(quest.objectives || []), { id: `objective_${quest.objectives.length + 1}`, type: "visit", target_id: "", required: 1, progress: 0 }];
    renderQuestForm(form, quest);
    markDirty();
  };
  $$("[data-remove-objective]").forEach((button) => button.onclick = () => {
    quest.objectives.splice(Number(button.dataset.removeObjective), 1);
    renderQuestForm(form, quest);
    markDirty();
  });
  bindSave(async () => {
    const parsedObjectives = $$("[data-objective-row]").map((row) => ({
      id: row.querySelector("[data-o=id]").value.trim() || `objective_${Number(row.dataset.objectiveRow) + 1}`,
      type: row.querySelector("[data-o=type]").value,
      target_id: row.querySelector("[data-o=target]").value.trim(),
      required: Math.max(1, Number(row.querySelector("[data-o=required]").value || 1)),
      progress: 0,
    }));
    await upsert("quests", quest.id, {
      ...quest,
      name: value("name"), description: value("description"), reward_currency: num("reward_currency"), objectives: parsedObjectives,
    });
  });
}

function renderRuleForm(form, rule) {
  const settings = rule.settings || {};
  const common = [
    ["round_seconds", "Round seconds", "number", settings.round_seconds ?? 6],
    ["base_armor_class", "Base armor class", "number", settings.base_armor_class ?? 10],
    ["critical_hit_roll", "Critical hit roll", "number", settings.critical_hit_roll ?? 20],
    ["critical_miss_roll", "Critical miss roll", "number", settings.critical_miss_roll ?? 1],
    ["death_saves_enabled", "Death saves", "check", settings.death_saves_enabled ?? false],
  ];
  form.innerHTML = `
    <section class="studio-form-section"><h3>Rules document</h3><div class="studio-form-grid">
      ${field("Name", "name", rule.name, "wide")}
      ${common.map(([key, label, type, val]) => type === "check" ? checkField(label, `setting-${key}`, val) : numberField(label, `setting-${key}`, val, .1)).join("")}
    </div></section>
    <section class="studio-form-section"><h3>Additional settings</h3><p class="studio-summary">Use compact key/value settings for ruleset-specific fields not shown above.</p><div id="settings-list" class="studio-inline-list"></div><button type="button" id="add-setting">Add setting</button></section>
    ${saveButtons()}`;
  const known = new Set(common.map(([key]) => key));
  const extras = Object.entries(settings).filter(([key]) => !known.has(key));
  renderKeyValueRows($("#settings-list"), extras, "setting-extra");
  $("#add-setting").onclick = () => addKeyValueRow($("#settings-list"), "setting-extra");
  bindSave(async () => {
    const next = {
      round_seconds: num("setting-round_seconds"),
      base_armor_class: num("setting-base_armor_class"),
      critical_hit_roll: num("setting-critical_hit_roll"),
      critical_miss_roll: num("setting-critical_miss_roll"),
      death_saves_enabled: checked("setting-death_saves_enabled"),
      ...readKeyValueRows("setting-extra"),
    };
    await upsert("rules", rule.id, { ...rule, name: value("name"), settings: next });
  });
}

function renderCampaignForm(form, campaign) {
  const mapOptions = ["", ...Object.keys(pack().maps || {})];
  const ruleOptions = ["", ...Object.keys(pack().rules || {})];
  form.innerHTML = `
    <section class="studio-form-section"><h3>Campaign template</h3><div class="studio-form-grid">
      ${field("Name", "name", campaign.name, "wide")}
      ${textareaField("Description", "description", campaign.description || "", "wide")}
      ${selectField("Start map", "start_map_id", campaign.start_map_id || "", mapOptions)}
      ${selectField("Active rules", "active_rule_id", campaign.active_rule_id || "", ruleOptions)}
    </div></section>
    <section class="studio-form-section"><h3>Starting flags</h3><div id="flags-list" class="studio-inline-list"></div><button type="button" id="add-flag">Add flag</button></section>
    ${saveButtons()}`;
  renderKeyValueRows($("#flags-list"), Object.entries(campaign.flags || {}), "campaign-flag");
  $("#add-flag").onclick = () => addKeyValueRow($("#flags-list"), "campaign-flag");
  bindSave(async () => upsert("campaigns", campaign.id, {
    ...campaign,
    name: value("name"), description: value("description"),
    start_map_id: nullable(value("start_map_id")), active_rule_id: nullable(value("active_rule_id")),
    flags: readKeyValueRows("campaign-flag"),
  }));
}

function objectiveRow(objective, index) {
  return `<div class="studio-inline-row" data-objective-row="${index}">
    <label>ID<input data-o="id" value="${escapeAttr(objective.id || "")}" /></label>
    <label>Type<select data-o="type">${["visit", "interact", "defeat", "collect", "custom"].map((type) => `<option ${objective.type === type ? "selected" : ""}>${type}</option>`).join("")}</select></label>
    <button type="button" class="danger" data-remove-objective="${index}">×</button>
    <label>Target<input data-o="target" value="${escapeAttr(objective.target_id || "")}" /></label>
    <label>Required<input data-o="required" type="number" min="1" value="${objective.required ?? 1}" /></label>
  </div>`;
}

function renderKeyValueRows(container, entries, prefix) {
  container.innerHTML = "";
  for (const [key, val] of entries) addKeyValueRow(container, prefix, key, val);
}

function addKeyValueRow(container, prefix, key = "", val = "") {
  const row = document.createElement("div");
  row.className = "studio-inline-row";
  row.dataset.kvPrefix = prefix;
  row.innerHTML = `<label>Key<input data-kv="key" value="${escapeAttr(key)}" /></label><label>Value<input data-kv="value" value="${escapeAttr(typeof val === "object" ? JSON.stringify(val) : String(val))}" /></label><button type="button" class="danger">×</button>`;
  row.querySelector("button").onclick = () => { row.remove(); markDirty(); };
  container.appendChild(row);
}

function readKeyValueRows(prefix) {
  const result = {};
  $$(`[data-kv-prefix="${prefix}"]`).forEach((row) => {
    const key = row.querySelector("[data-kv=key]").value.trim();
    if (!key) return;
    const raw = row.querySelector("[data-kv=value]").value.trim();
    result[key] = parsePrimitive(raw);
  });
  return result;
}

function parsePrimitive(raw) {
  if (raw === "true") return true;
  if (raw === "false") return false;
  if (raw === "null") return null;
  if (raw !== "" && Number.isFinite(Number(raw))) return Number(raw);
  if ((raw.startsWith("[") && raw.endsWith("]")) || (raw.startsWith("{") && raw.endsWith("}"))) {
    try { return JSON.parse(raw); } catch { /* keep string */ }
  }
  return raw;
}

function field(label, id, val = "", className = "") {
  return `<label class="${className}">${label}<input id="f-${id}" value="${escapeAttr(val ?? "")}" /></label>`;
}
function numberField(label, id, val = "", step = 1, className = "") {
  return `<label class="${className}">${label}<input id="f-${id}" type="number" step="${step}" value="${escapeAttr(val ?? "")}" /></label>`;
}
function textareaField(label, id, val = "", className = "") {
  return `<label class="${className}">${label}<textarea id="f-${id}" rows="5">${escapeHtml(val ?? "")}</textarea></label>`;
}
function selectField(label, id, val, options) {
  return `<label>${label}<select id="f-${id}">${options.map((option) => `<option value="${escapeAttr(option)}" ${String(option) === String(val) ? "selected" : ""}>${escapeHtml(option || "— none —")}</option>`).join("")}</select></label>`;
}
function checkField(label, id, val) {
  return `<label class="studio-check"><input id="f-${id}" type="checkbox" ${val ? "checked" : ""} /> ${label}</label>`;
}
function saveButtons() {
  return `<section class="studio-form-section studio-toolbar"><button type="button" id="save-object" class="primary">Save changes</button><button type="button" id="delete-object" class="danger">Delete</button></section>`;
}
function value(id) { return $(`#f-${id}`)?.value ?? ""; }
function num(id) { return Number(value(id) || 0); }
function checked(id) { return Boolean($(`#f-${id}`)?.checked); }
function bindSave(handler) {
  $("#save-object").onclick = async () => { try { await handler(); log("Changes saved."); } catch (error) { showError(error); } };
  $("#delete-object").onclick = deleteSelected;
}

function renderCounts() {
  const container = $("#content-counts");
  if (!pack()) return container.replaceChildren();
  const sections = ["maps", "creatures", "rules", "spells", "quests", "campaigns"];
  container.innerHTML = sections.map((section) => `<div class="studio-metric"><strong>${Object.keys(pack()[section] || {}).length}</strong><small>${section}</small></div>`).join("");
}

async function validateProject() {
  if (!state.project) return;
  try {
    const result = await api(`/api/v1/studio/projects/${state.project.id}/validate`, { method: "POST" });
    const banner = $("#validation-banner");
    banner.classList.remove("hidden", "success", "error");
    banner.classList.add(result.valid ? "success" : "error");
    banner.textContent = result.valid ? `Valid pack · ${result.content_hash.slice(0, 12)}…` : `${result.errors.length} validation issue(s)`;
    log(result.valid ? `Validation passed.\nHash: ${result.content_hash}` : `Validation failed:\n${result.errors.join("\n")}`);
    return result.valid;
  } catch (error) { showError(error); return false; }
}

async function publishProject() {
  if (!(await validateProject())) return;
  try {
    const item = await api(`/api/v1/studio/projects/${state.project.id}/publish`, { method: "POST" });
    log(`Published ${item.title || item.id}.`);
  } catch (error) { showError(error); }
}

async function exportProject() {
  try {
    const exported = await api(`/api/v1/studio/projects/${state.project.id}/export`);
    const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${state.project.pack.manifest.id}-${state.project.pack.manifest.version}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    log("Exported validated content pack.");
  } catch (error) { showError(error); }
}

async function restoreRevision() {
  const revision = Number($("#restore-revision").value);
  if (!Number.isInteger(revision) || revision < 0) return showError(new Error("Revision must be a non-negative integer."));
  if (!confirm(`Restore revision ${revision}? The current project remains in history.`)) return;
  try {
    const project = await api(`/api/v1/studio/projects/${state.project.id}/restore`, {
      method: "POST",
      body: JSON.stringify({ revision }),
    });
    state.selectedId = null;
    state.selectedNodes = [];
    applyProject(project);
    log(`Restored revision ${revision} as new revision ${project.revision}.`);
  } catch (error) { showError(error); }
}

function showEdgeInspector() {
  if (state.selectedNodes.length !== 2) return;
  $("#edge-inspector").classList.remove("hidden");
}

function fitMap() {
  const worldMap = selectedObject();
  const nodes = Object.values(worldMap?.nodes || {});
  const svgElement = $("#map-canvas");
  if (!nodes.length) return svgElement.setAttribute("viewBox", "0 0 1200 720");
  const padding = 120;
  const xs = nodes.map((node) => Number(node.x || 0));
  const ys = nodes.map((node) => Number(node.y || 0));
  const minX = Math.min(...xs) - padding;
  const minY = Math.min(...ys) - padding;
  const width = Math.max(500, Math.max(...xs) - Math.min(...xs) + padding * 2);
  const height = Math.max(350, Math.max(...ys) - Math.min(...ys) + padding * 2);
  svgElement.setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`);
}

function changeSection(section) {
  state.section = section;
  state.selectedId = null;
  state.selectedNodes = [];
  $$("#section-tabs button").forEach((button) => button.classList.toggle("active", button.dataset.section === section));
  renderAll();
}

function log(message) {
  $("#validation-output").textContent = String(message);
}
function showError(error) {
  console.error(error);
  log(`Error: ${error.message || error}`);
  const banner = $("#validation-banner");
  banner.className = "studio-validation error";
  banner.textContent = error.message || String(error);
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}
function escapeAttr(value) { return escapeHtml(value); }

$("#new-project").addEventListener("click", async () => {
  if (state.project && !confirm("Create a new Creator Studio project?")) return;
  try { await createProject(); } catch (error) { showError(error); }
});
$("#save-manifest").addEventListener("click", () => saveManifest().catch(showError));
$("#validate-project").addEventListener("click", validateProject);
$("#publish-project").addEventListener("click", publishProject);
$("#export-project").addEventListener("click", exportProject);
$("#restore-project").addEventListener("click", restoreRevision);
$("#refresh-history").addEventListener("click", () => {
  $("#restore-revision").max = String(state.project?.revision ?? 0);
  $("#restore-revision").value = String(state.project?.revision ?? 0);
});
$("#add-object").addEventListener("click", createObject);
$("#library-filter").addEventListener("input", renderObjectList);
$("#map-add-node").addEventListener("click", addMapNode);
$("#map-connect").addEventListener("click", showEdgeInspector);
$("#create-edge").addEventListener("click", createEdge);
$("#save-node").addEventListener("click", saveNode);
$("#map-fit").addEventListener("click", fitMap);
$$("#section-tabs button").forEach((button) => button.addEventListener("click", () => changeSection(button.dataset.section)));

for (const input of ["#project-name", "#pack-id", "#pack-version", "#pack-license", "#pack-author"]) {
  $(input).addEventListener("input", () => markDirty());
}

loadInitialProject().catch(showError);
