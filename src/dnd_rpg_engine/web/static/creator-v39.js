// src/dnd_rpg_engine/web/static/creator-v39.js
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const v39 = { project:null, section:null, selectedId:null };
const labels = {scenes:"Scene Flow",actions:"Actions",conditions:"Conditions",items:"Items",dialogues:"Dialogue Graphs",npcs:"NPC Profiles",shops:"Shops",factions:"Factions",schedules:"NPC Schedules",dynamic_events:"Dynamic Events",personalities:"Personalities",encounters:"Encounter Templates",rules_data:"Rules Data",assets:"Assets"};

function slug(value){return String(value||"new_item").trim().toLowerCase().replace(/[^a-z0-9_.-]+/g,"_").replace(/^[_\-.]+|[_\-.]+$/g,"")||"new_item";}
function titleCase(value){return String(value||"").replace(/[_.-]+/g," ").replace(/\b\w/g,(c)=>c.toUpperCase());}
function escapeHtml(value){return String(value??"").replace(/[&<>'"]/g,(ch)=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));}
async function api(path,options={}){const response=await fetch(path,{headers:{"Content-Type":"application/json",...(options.headers||{})},...options});const text=await response.text();let body=null;if(text){try{body=JSON.parse(text);}catch{body=text;}}if(!response.ok){const detail=body?.detail??body??response.statusText;throw new Error(typeof detail==="string"?detail:JSON.stringify(detail));}return body;}
function projectId(){return localStorage.getItem("rpg.creator.project");}
function collection(){return v39.project?.pack?.[v39.section]||{};}
function selected(){return v39.selectedId ? collection()[v39.selectedId] : null;}
function output(message,error=false){$("#v39-output").textContent=message;$("#v39-output").classList.toggle("error",error);}

const defaults={
  scenes:(id)=>({id,name:titleCase(id),kind:"custom",map_id:null,entity_ids:[],preload_scene_ids:[],next_scene_ids:[],tags:[],metadata:{}}),
  actions:(id)=>({id,name:titleCase(id),time_cost:6,range:1.5,attack_ability:"strength",damage:"1d6",damage_type:"physical",proficiency_key:null,tags:[]}),
  conditions:(id)=>({id,name:titleCase(id),attack_modifier:0,armor_modifier:0,movement_multiplier:1,blocks_actions:false,periodic_damage:null,periodic_interval:null,attack_roll_mode:"normal",attacks_against_mode:"normal",tags:[]}),
  items:(id)=>({id,name:titleCase(id),value:0,stackable:true,max_stack:99,use_time:4,heal:null,energy_restore:0,applies_condition:null,tags:[]}),
  dialogues:(id)=>({id,start_node:"start",nodes:{start:{id:"start",speaker_id:null,text:"New dialogue",options:[]}}}),
  npcs:(id)=>({entity_id:id,role:"resident",dialogue_id:null,shop_id:null,faction_id:null,personality_id:null,schedule_id:null,knowledge_tags:[]}),
  shops:(id)=>({id,name:titleCase(id),keeper_id:null,stock:{},buy_multiplier:1,sell_multiplier:.5,restock_world_minutes:1440,last_restock_at:0}),
  factions:(id)=>({id,name:titleCase(id),tags:[],resources:100,influence:50}),
  schedules:(id)=>({id,entries:[]}),
  dynamic_events:(id)=>({id,event_type:"world.notice",predicates:[],payload:{},once:true}),
  personalities:(id)=>({id,traits:{},goals:[],fears:[],speech_style:"plain"}),
  encounters:(id)=>({id,tags:[],opponent_templates:["creature_id"],min_tier:1,max_tier:20,weight:1}),
  rules_data:(id)=>({name:titleCase(id),value:{}}),
  assets:()=>({value:"assets/example.png"}),
};

async function refresh(){const id=projectId();if(!id){output("Create or load a Creator Studio project first.",true);return;}v39.project=await api(`/api/v1/studio/projects/${encodeURIComponent(id)}`);render();}
function activate(section){v39.section=section;v39.selectedId=null;$("#v39-workspace").classList.remove("hidden");$("#map-workspace").classList.add("hidden");$("#form-workspace").classList.add("hidden");$("#map-inspector").classList.add("hidden");$("#workspace-kicker").textContent="FULL CONTENT PACK";$("#workspace-title").textContent=labels[section]||titleCase(section);$$("[data-v39-section]").forEach((button)=>button.classList.toggle("active",button.dataset.v39Section===section));refresh().catch(showError);}
function deactivate(){v39.section=null;$("#v39-workspace").classList.add("hidden");$$("[data-v39-section]").forEach((button)=>button.classList.remove("active"));}
function render(){if(!v39.section||!v39.project)return;$("#v39-title").textContent=labels[v39.section]||titleCase(v39.section);renderExtendedCounts();renderList();renderEditor();renderSceneGraph();}
function renderExtendedCounts(){const sections=["campaigns","scenes","maps","creatures","npcs","personalities","encounters","actions","conditions","items","spells","dialogues","quests","shops","factions","schedules","dynamic_events","rules","rules_data","assets"];$("#content-counts").innerHTML=sections.map((section)=>`<div class="studio-metric"><strong>${Object.keys(v39.project.pack?.[section]||{}).length}</strong><small>${escapeHtml(section)}</small></div>`).join("");}
function renderList(){const list=$("#v39-list");const filter=$("#v39-filter").value.trim().toLowerCase();const rows=Object.entries(collection()).filter(([id,value])=>!filter||`${id} ${value?.name||value?.entity_id||value||""}`.toLowerCase().includes(filter));list.innerHTML=rows.length?rows.map(([id,value])=>`<button class="studio-object-row ${id===v39.selectedId?"active":""}" data-v39-id="${escapeHtml(id)}"><div><strong>${escapeHtml(value?.name||value?.entity_id||id)}</strong><small>${escapeHtml(id)}</small></div><span>›</span></button>`).join(""):`<div class="studio-summary">No ${escapeHtml(labels[v39.section]||v39.section)} yet.</div>`;$$("[data-v39-id]").forEach((button)=>button.onclick=()=>{v39.selectedId=button.dataset.v39Id;render();});}
function renderEditor(){const value=selected();if(!value){$("#v39-json").value="";$("#v39-delete").disabled=true;output(`Create or select a ${labels[v39.section]||v39.section} object.`);return;}$("#v39-delete").disabled=false;const editable=v39.section==="assets"?{value}:value;$("#v39-json").value=JSON.stringify(editable,null,2);output(`Editing ${v39.section}/${v39.selectedId} · project revision ${v39.project.revision}`);}

async function createObject(){if(!v39.section)return;const proposed=prompt(`New ${v39.section} ID:`,`new_${v39.section.replace(/s$/,"")}`);if(!proposed)return;const id=slug(proposed);if(collection()[id])return showError(new Error(`${id} already exists`));v39.selectedId=id;$("#v39-json").value=JSON.stringify(defaults[v39.section](id),null,2);await saveObject();}
async function saveObject(){if(!v39.section||!v39.selectedId)return;let payload;try{payload=JSON.parse($("#v39-json").value);}catch(error){return showError(new Error(`Invalid JSON: ${error.message}`));}try{v39.project=await api(`/api/v1/studio/projects/${v39.project.id}/${v39.section}/${encodeURIComponent(v39.selectedId)}`,{method:"PUT",body:JSON.stringify({payload})});render();output(`Saved ${v39.section}/${v39.selectedId} at revision ${v39.project.revision}.`);}catch(error){showError(error);}}
async function deleteObject(){if(!v39.selectedId||!confirm(`Delete ${v39.section}/${v39.selectedId}?`))return;try{v39.project=await api(`/api/v1/studio/projects/${v39.project.id}/${v39.section}/${encodeURIComponent(v39.selectedId)}`,{method:"DELETE"});v39.selectedId=null;render();output("Object deleted.");}catch(error){showError(error);}}
function formatJson(){try{$("#v39-json").value=JSON.stringify(JSON.parse($("#v39-json").value),null,2);}catch(error){showError(new Error(`Invalid JSON: ${error.message}`));}}
function showError(error){console.error(error);output(error.message||String(error),true);}

function renderSceneGraph(){const wrap=$("#v39-scene-graph");wrap.classList.toggle("hidden",v39.section!=="scenes");if(v39.section!=="scenes"||!v39.project)return;const scenes=Object.values(v39.project.pack.scenes||{});const edgeLayer=$("#v39-scene-edges"),nodeLayer=$("#v39-scene-nodes");edgeLayer.innerHTML="";nodeLayer.innerHTML="";if(!scenes.length)return;const positions={};scenes.forEach((scene,index)=>{const col=index%4,row=Math.floor(index/4);positions[scene.id]={x:165+col*285,y:105+row*185};});for(const scene of scenes){for(const next of scene.next_scene_ids||[]){if(!positions[next])continue;const a=positions[scene.id],b=positions[next];edgeLayer.appendChild(svg("line",{x1:a.x+90,y1:a.y,x2:b.x-90,y2:b.y,class:"v39-scene-edge"}));}}for(const scene of scenes){const pos=positions[scene.id];const group=svg("g",{class:`v39-scene-node ${scene.id===v39.selectedId?"active":""}`,transform:`translate(${pos.x} ${pos.y})`,"data-scene-id":scene.id});group.appendChild(svg("rect",{x:-92,y:-42,width:184,height:84}));const name=svg("text",{x:0,y:-5});name.textContent=scene.name||scene.id;group.appendChild(name);const kind=svg("text",{x:0,y:18,class:"kind"});kind.textContent=`${scene.kind||"custom"} · ${scene.map_id||"no map"}`;group.appendChild(kind);group.style.cursor="pointer";group.addEventListener("click",()=>{v39.selectedId=scene.id;render();});nodeLayer.appendChild(group);}}
function svg(tag,attrs){const element=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const [key,value] of Object.entries(attrs))element.setAttribute(key,value);return element;}

$$("[data-v39-section]").forEach((button)=>button.onclick=()=>activate(button.dataset.v39Section));
$("#section-tabs").addEventListener("click",()=>deactivate());
$("#v39-filter").oninput=renderList;$("#v39-new").onclick=()=>createObject().catch(showError);$("#v39-save").onclick=()=>saveObject().catch(showError);$("#v39-delete").onclick=()=>deleteObject().catch(showError);$("#v39-refresh").onclick=()=>refresh().catch(showError);$("#v39-format").onclick=formatJson;
$("#new-project").addEventListener("click",()=>setTimeout(()=>{if(v39.section)refresh().catch(showError);},250));$("#restore-project").addEventListener("click",()=>setTimeout(()=>{if(v39.section)refresh().catch(showError);},250));
