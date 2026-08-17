// src/dnd_rpg_engine/web/static/creator.js
const $ = (id) => document.getElementById(id);
let currentSection = "campaigns";
let pack = freshPack();

function freshPack() {
  return {
    manifest: { id: "example.adventure", name: "Example Adventure", version: "1.0.0", engine_version: ">=1.0.0", author: "creator", description: "", license: "CC0-1.0", dependencies: {}, tags: ["adventure"] },
    campaigns: {}, creatures: {}, actions: {}, conditions: {}, items: {}, spells: {}, maps: {}, dialogues: {}, quests: {}, rules: {}, assets: {},
  };
}

function syncManifest() {
  pack.manifest.id = $("pack-id").value;
  pack.manifest.name = $("pack-name").value;
  pack.manifest.author = $("pack-author").value;
  pack.manifest.version = $("pack-version").value;
  pack.manifest.license = $("pack-license").value;
}

function showSection() { $("section-editor").value = JSON.stringify(pack[currentSection], null, 2); }
function output(value) { $("validation-output").textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); }

async function request(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(body.detail ?? body));
  return body;
}

function applySection() {
  try {
    pack[currentSection] = JSON.parse($("section-editor").value);
    syncManifest();
    output(`Applied ${currentSection}.`);
  } catch (error) { output(`Invalid JSON: ${error.message}`); }
}

async function validatePack() {
  try { applySection(); output(await request("/api/v1/creator/validate", { method: "POST", body: JSON.stringify(pack) })); }
  catch (error) { output(`Validation request failed: ${error.message}`); }
}

async function publishPack() {
  try { applySection(); output(await request("/api/v1/marketplace/publish", { method: "POST", body: JSON.stringify(pack) })); await searchMarket(); }
  catch (error) { output(`Publish failed: ${error.message}`); }
}

async function searchMarket() {
  try {
    const items = await request(`/api/v1/marketplace?q=${encodeURIComponent($("market-search").value)}`);
    $("market-results").innerHTML = items.map(item => `<article class="card"><strong>${esc(item.title)}</strong><div class="small">${esc(item.id)}</div><div>${esc(item.description)}</div><div class="small">${item.downloads} installs · ${esc(item.license)}</div></article>`).join("") || '<div class="small">No items.</div>';
  } catch (error) { output(error.message); }
}

function esc(value) { return String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch])); }

document.querySelectorAll("[data-tab]").forEach(button => button.onclick = () => {
  try { pack[currentSection] = JSON.parse($("section-editor").value); } catch (_) {}
  document.querySelectorAll("[data-tab]").forEach(b => b.classList.remove("active"));
  button.classList.add("active"); currentSection = button.dataset.tab; showSection();
});
$("new-pack").onclick = () => { pack = freshPack(); currentSection = "campaigns"; showSection(); output("Reset."); };
$("apply-section").onclick = applySection;
$("validate-pack").onclick = validatePack;
$("publish-pack").onclick = publishPack;
$("search-market").onclick = searchMarket;
showSection();
