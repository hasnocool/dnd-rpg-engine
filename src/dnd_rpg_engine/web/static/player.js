const classes = ["barbarian","bard","cleric","druid","fighter","monk","paladin","ranger","rogue","sorcerer","warlock","wizard"];
const species = ["dragonborn","dwarf","elf","gnome","goliath","halfling","human","orc","tiefling"];
const backgrounds = ["acolyte","criminal","sage","soldier"];
for (const [id, values] of [["class-id", classes], ["species-id", species], ["background-id", backgrounds]]) {
  const el = document.getElementById(id);
  for (const value of values) el.append(new Option(value.replaceAll("_", " "), value));
}
let campaignId = null, characterId = null, clientId = null;
const log = (value) => {
  const line = document.createElement("div");
  line.textContent = typeof value === "string" ? value : JSON.stringify(value);
  document.getElementById("events").prepend(line);
};
async function api(path, options={}) {
  const headers = {"content-type":"application/json", ...(options.headers || {})};
  if (clientId) headers["X-RPG-Client-ID"] = clientId;
  const response = await fetch(path, {...options, headers});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || response.statusText);
  return data;
}
async function refresh() {
  if (!campaignId || !characterId) return;
  const data = await api(`/api/v1/campaigns/${campaignId}/characters/${characterId}`);
  document.getElementById("sheet").textContent = JSON.stringify(data, null, 2);
  document.getElementById("turn").textContent = JSON.stringify(data.legal_actions.turn || {}, null, 2);
  const actions = document.getElementById("actions"); actions.replaceChildren();
  for (const action of data.legal_actions.available || []) {
    const card = document.createElement("div"); card.className="card"; card.textContent=action; actions.append(card);
  }
}
async function command(type, extra={}) {
  const result = await api(`/api/v1/campaigns/${campaignId}/commands`, {method:"POST", body: JSON.stringify({command:{type, actor_id:characterId, ...extra}, client_id:clientId})});
  for (const event of result.events) log(event);
  await refresh();
}
document.getElementById("create").onclick = async () => {
  try {
    const body = {
      campaign_name: document.getElementById("campaign").value,
      owner_id: "browser-player", seed: 42, time_mode: "turn_based",
      character: {
        name: document.getElementById("name").value,
        class_id: document.getElementById("class-id").value,
        species_id: document.getElementById("species-id").value,
        background_id: document.getElementById("background-id").value,
        level: 1,
        stats: {strength:14,dexterity:14,constitution:14,intelligence:10,wisdom:12,charisma:10}
      }
    };
    const data = await api("/api/v2/playable-campaigns", {method:"POST", body:JSON.stringify(body)});
    campaignId=data.campaign_id; characterId=data.character_id; clientId=data.owner_client_id;
    document.getElementById("ids").textContent=`campaign=${campaignId}\ncharacter=${characterId}`;
    for (const el of document.querySelectorAll("button[disabled]")) el.disabled=false;
    await refresh(); log("Playable campaign created");
  } catch (error) { log(error.message); }
};
document.getElementById("refresh").onclick = refresh;
for (const button of document.querySelectorAll("button[data-command]")) button.onclick = () => command(button.dataset.command);
document.getElementById("short-rest").onclick = () => command("rest", {rest_kind:"short", hit_dice_to_spend:1});
document.getElementById("long-rest").onclick = () => command("rest", {rest_kind:"long"});
