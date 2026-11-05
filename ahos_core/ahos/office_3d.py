"""3B ofis — oyun kalitesinde sahne: cam duvarlı odalar, parke zemin, monitörler,
isimli avatarlar, sıcak ışık, hafif animasyon.

Sunucu: from ahos.office_3d import render_html
"""

from __future__ import annotations

HTML = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AHOS · 3D Operasyon Merkezi</title>
<style>
  html,body{margin:0;height:100%;background:#070a12;color:#e8f0ff;font:13px/1.55 system-ui;overflow:hidden}
  #hud{position:fixed;left:16px;top:14px;background:rgba(12,18,30,.82);backdrop-filter:blur(8px);
       border:1px solid #22314e;border-radius:14px;padding:11px 15px}
  #hud b{color:#7fd7ff}
  #chat{position:fixed;right:16px;bottom:16px;width:360px;max-height:46vh;overflow:auto;
        background:rgba(12,18,30,.88);backdrop-filter:blur(8px);border:1px solid #22314e;
        border-radius:14px;padding:11px 13px;font-size:12px}
  #chat h4{margin:0 0 7px;color:#7fd7ff;font-size:11px;letter-spacing:.14em}
  #chat .m{margin:0 0 8px;line-height:1.35;cursor:pointer;padding:5px 6px;border-radius:8px}
  #chat .m:hover{background:#182338}
  #chat .who{color:#7fe3c0;font-weight:600}
  #chat .dept{color:#78889f;font-size:11px}
  #who,#msg{width:100%;background:#0f1728;color:#e8f0ff;border:1px solid #2a3d5c;border-radius:9px;
            padding:6px;margin-top:6px;font:12px system-ui}
  #reply{margin-top:7px;color:#a9e6cf;font-size:12px}
  #renders{position:fixed;right:16px;top:16px;width:260px;max-height:26vh;overflow:auto;
        background:rgba(12,18,30,.88);border:1px solid #22314e;border-radius:14px;padding:10px 12px;font-size:12px}
  #renders h4{margin:0 0 6px;color:#ffd39b;font-size:11px;letter-spacing:.14em}
  #renders a{color:#cfe3ff;display:block;text-decoration:none;margin:2px 0}
  #err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#33131b;
       border:1px solid #8d2b3d;padding:16px 20px;border-radius:14px;display:none;z-index:50}
  *{box-sizing:border-box}
  canvas{display:block;touch-action:none}
  #hud,#chat,#inspector{z-index:10;box-shadow:0 18px 48px rgba(0,0,0,.28);border-color:rgba(130,167,208,.30)}
  #hud{width:min(485px,calc(100vw - 30px));background:rgba(10,19,34,.93);padding:16px 18px}
  #hud .brand{display:flex;justify-content:space-between;align-items:center;gap:8px;
              font-size:14px;font-weight:800;letter-spacing:.035em}
  #hud .brand strong{color:#74d6ff}
  #hud .online{color:#ffd18c;font-size:11px;font-weight:600;white-space:nowrap}
  #hud .online.ok{color:#70efb5}
  #stats{font-variant-numeric:tabular-nums;color:#d6e9ff;margin:7px 0;font-size:12px}
  #toolbar{display:flex;align-items:center;gap:7px;margin:11px 0 6px;flex-wrap:wrap}
  #toolbar select{min-width:155px;max-width:220px;flex:1}
  #toolbar button,#toolbar select,#inspector button{border:1px solid #38506e;border-radius:9px;
     padding:8px 10px;background:#172b43;color:#e1efff;font:600 12px system-ui;cursor:pointer}
  #toolbar button:hover,#inspector button:hover{background:#234363}
  #hud small{font-size:10px;color:#90acc7}
  #inspector{position:fixed;right:16px;top:15px;width:min(330px,calc(100vw - 32px));
       padding:15px 17px;border:1px solid;border-radius:14px;background:rgba(10,19,34,.94)}
  #inspector[hidden]{display:none}
  #inspector h3{color:#92dfff;margin:0 24px 5px 0;font-size:14px}
  #inspector .muted{font-size:12px;color:#a7b9d0}
  #inspector .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:13px 0}
  #inspector .metric{background:#13243b;border-radius:8px;padding:8px;font-size:11px;color:#acc5df}
  #inspector .metric b{display:block;color:#f0f7ff;font-size:18px}
  #inspector .focus-note{font-size:11px;color:#7be8ba}
  #inspector .close{position:absolute;top:9px;right:10px;cursor:pointer}
  #chat{width:min(370px,calc(100vw - 24px));max-height:42vh;display:flex;flex-direction:column;
      overflow:hidden;padding:12px 13px;background:rgba(10,19,34,.94)}
  #chat h4{display:flex;justify-content:space-between;margin:0 0 7px}
  #chatbody{overflow-y:auto;overflow-x:hidden;min-height:30px;max-height:20vh;overflow-wrap:anywhere}
  #chat .m{cursor:pointer}
  #who,#msg{box-sizing:border-box;min-width:0;width:100%;margin-top:7px}
  #reply{overflow:auto;max-height:8vh;overflow-wrap:anywhere}
  @media(max-width:800px){
    #hud{left:9px;top:9px;padding:10px 12px;width:min(430px,calc(100vw - 18px))}
    #inspector{top:auto;right:9px;bottom:235px;padding:10px 12px;max-height:29vh;overflow:auto}
    #chat{right:9px;bottom:9px;max-height:27vh}
    #chatbody{max-height:8vh}
    #toolbar select{min-width:130px}
    #hud small{display:none}
  }
</style></head>
<body>
<div id="hud">
  <div class="brand"><span>AHOS <strong>3D OPERASYON MERKEZİ</strong></span>
    <span id="connection" class="online">● Bağlanıyor</span></div>
  <div id="stats" aria-live="polite">yükleniyor…</div>
  <div id="toolbar">
    <select id="deptNav" aria-label="Departman seç"><option value="">Departman seç…</option></select>
    <button id="resetView" type="button">Genel görünüm</button>
    <button id="toggleLabels" type="button">İsimleri gizle</button>
  </div>
  <small>Fareyle döndür · tekerlekle yakınlaş · odaya veya çalışana tıkla</small>
</div>
<aside id="inspector" hidden aria-live="polite">
  <button class="close" type="button" id="closeInspector" aria-label="Ayrıntıları kapat">×</button>
  <h3 id="inspectorTitle">Departman</h3>
  <div id="inspectorText" class="muted"></div>
  <div class="metrics"><div class="metric">Sırada<b id="detailPending">0</b></div>
    <div class="metric">Tamamlanan<b id="detailDone">0</b></div>
    <div class="metric">Engel<b id="detailBlocked">0</b></div></div>
  <div id="inspectorNote" class="focus-note">Canlı veri · gerçek görev durumu</div>
</aside>
<div id="chat"><h4>CANLI SOHBET <span class="dept">Çalışanla konuş</span></h4><div id="chatbody">…</div>
  <select id="who"></select>
  <input id="msg" placeholder="işçiye yaz, Enter…">
  <div id="reply"></div>
</div>
<div id="renders"><h4>ÜRETİMLER</h4><div id="renderlist">…</div></div>
<div id="err"></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d1827);
scene.fog = new THREE.FogExp2(0x0d1827, 0.00040);

const camera = new THREE.PerspectiveCamera(42, innerWidth/innerHeight, 1, 6000);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.60;
document.body.appendChild(renderer.domElement);

scene.add(new THREE.HemisphereLight(0xd6eaff, 0x273b50, 1.55));
const sun = new THREE.DirectionalLight(0xfff0d4, 2.00);
sun.position.set(420, 620, 320);
sun.castShadow = true;
sun.shadow.mapSize.set(2048,2048);
sun.shadow.camera.left=-900; sun.shadow.camera.right=900;
sun.shadow.camera.top=900; sun.shadow.camera.bottom=-900;
scene.add(sun);
const rim = new THREE.DirectionalLight(0x75b3ff, 0.90); rim.position.set(-400,220,-380); scene.add(rim);

function woodTexture(){
  const c = document.createElement('canvas'); c.width = c.height = 512;
  const g = c.getContext('2d');
  g.fillStyle = '#2b3b50'; g.fillRect(0,0,512,512);
  for (let y=0; y<512; y+=32){
    g.fillStyle = (y/32)%2 ? '#33485e' : '#29394e'; g.fillRect(0,y,512,30);
    g.strokeStyle = 'rgba(90,120,170,.10)'; g.beginPath(); g.moveTo(0,y+31); g.lineTo(512,y+31); g.stroke();
    for (let x=0; x<512; x+=96){ g.strokeStyle='rgba(70,100,150,.08)'; g.beginPath(); g.moveTo(x,y); g.lineTo(x,y+30); g.stroke(); }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(24,24);
  return t;
}

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(3000, 3000),
  new THREE.MeshStandardMaterial({map: woodTexture(), roughness: 0.92, metalness: 0.04})
);
ground.rotation.x = -Math.PI/2; ground.receiveShadow = true; scene.add(ground);

const ACCENT = [0x49c2ff,0x63e6b8,0xa78bfa,0xffb86b,0x7dd3fc,0xf472b6,0x94e2d5,0xc7d2fe];
const rooms = new THREE.Group(); scene.add(rooms);
const people = new THREE.Group(); scene.add(people);
const ROSTER = {};
const roomById = new Map();
const avatarById = new Map();
let currentSnapshot = null;
let labelsVisible = true;
fetch('/api/roster',{cache:'no-store'}).then(r=>r.json()).then(d=>{Object.assign(ROSTER, d||{});}).catch(()=>{});

function label(text, sub, x, y, z, color='#cfe3ff'){
  const c = document.createElement('canvas'); c.width = 640; c.height = 160;
  const g = c.getContext('2d');
  g.textAlign='center';
  g.font='700 44px system-ui'; g.fillStyle=color; g.fillText(text, 320, 62);
  if (sub){ g.font='400 30px system-ui'; g.fillStyle='#8fa6c8'; g.fillText(sub, 320, 108); }
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c), transparent:true, depthWrite:false}));
  spr.position.set(x,y,z); spr.scale.set(170, 42, 1); spr.userData.label = true; return spr;
}

function makeRoom(cx, cz, w, d, accent, busy, title, sub, depId){
  const g = new THREE.Group(); g.position.set(cx, 0, cz);
  g.userData = {depId, name:title};
  roomById.set(depId, g);

  const base = new THREE.Mesh(new THREE.BoxGeometry(w, 10, d),
    new THREE.MeshStandardMaterial({color: busy?0x22554c:0x26394a, roughness:0.85}));
  base.position.y = 5; base.receiveShadow = true; base.castShadow = true; g.add(base);

  const glass = new THREE.MeshPhysicalMaterial({
    color: accent, transparent:true, opacity:0.13, roughness:0.08, metalness:0.0,
    transmission:0.6, thickness:4, side:THREE.DoubleSide
  });
  const frameMat = new THREE.MeshStandardMaterial({color: accent, emissive: accent, emissiveIntensity: busy?0.55:0.16, roughness:0.4});
  const h = 96, t = 4;
  const walls = [
    [0, h/2, -d/2, w, h, t],
    [-w/2, h/2, 0, t, h, d],
    [w/2, h/2, 0, t, h, d],
    [0, h/2, d/2, w, 14, t],
  ];
  for (const [x,y,z,ww,hh,dd] of walls){
    const pane = new THREE.Mesh(new THREE.BoxGeometry(ww,hh,dd), glass);
    pane.position.set(x,y,z); g.add(pane);
    const cap = new THREE.Mesh(new THREE.BoxGeometry(ww, 4, dd), frameMat);
    cap.position.set(x, y + hh/2, z); g.add(cap);
  }

  const deskMat = new THREE.MeshStandardMaterial({color:0x45607a, roughness:0.55});
  const cols = Math.max(2, Math.floor((w-56)/70)), rows = Math.max(1, Math.floor((d-60)/64));
  for (let r=0;r<rows;r++) for (let c=0;c<cols;c++){
    const dx = -w/2 + 44 + c*70, dz = -d/2 + 46 + r*64;
    const desk = new THREE.Mesh(new THREE.BoxGeometry(54,5,26), deskMat);
    desk.position.set(dx, 38, dz); desk.castShadow = true; g.add(desk);
    const leg = new THREE.Mesh(new THREE.BoxGeometry(4,34,4), deskMat);
    leg.position.set(dx-22, 17, dz+9); g.add(leg);
    const leg2 = leg.clone(); leg2.position.x = dx+22; g.add(leg2);
    const chair = new THREE.Mesh(new THREE.BoxGeometry(22,5,22),
      new THREE.MeshStandardMaterial({color:0x1b2434, roughness:0.8}));
    chair.position.set(dx, 24, dz+30); chair.castShadow = true; g.add(chair);
    const back = new THREE.Mesh(new THREE.BoxGeometry(22,26,4),
      new THREE.MeshStandardMaterial({color:0x1b2434, roughness:0.8}));
    back.position.set(dx, 36, dz+40); g.add(back);
    const screen = new THREE.Mesh(new THREE.BoxGeometry(26,15,2),
      new THREE.MeshStandardMaterial({color:0x0e2a3a, emissive: busy?0x2fa98a:0x16405a, emissiveIntensity: busy?1.1:0.5}));
    screen.position.set(dx, 52, dz-8); g.add(screen);
  }

  const pot = new THREE.Mesh(new THREE.CylinderGeometry(8,6,14,12),
    new THREE.MeshStandardMaterial({color:0x3d2f22, roughness:0.9}));
  pot.position.set(w/2-20, 7, d/2-20); g.add(pot);
  const leaves = new THREE.Mesh(new THREE.ConeGeometry(15,34,10),
    new THREE.MeshStandardMaterial({color:0x2f7a4e, roughness:0.75}));
  leaves.position.set(w/2-20, 30, d/2-20); leaves.castShadow = true; g.add(leaves);

  const lamp = new THREE.PointLight(busy?0x9effd6:0x9fc4ff, busy?1.5:0.55, 320, 2);
  lamp.position.set(0, h-14, 0); g.add(lamp);

  const titleSprite = label(title, sub, 0, h+22, -4, busy ? '#9effd6' : '#e4f2ff');
  g.add(titleSprite);
  rooms.add(g);
}

const avatars = [];
function person(x, y, z, color, working, name, depId, workerId){
  const grp = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(5.6,12,6,12),
    new THREE.MeshStandardMaterial({color, roughness:0.55, metalness:0.15}));
  body.position.y = 19; body.castShadow = true; grp.add(body);
  const head = new THREE.Mesh(new THREE.SphereGeometry(5.4,16,14),
    new THREE.MeshStandardMaterial({color:0xf2cfae, roughness:0.75}));
  head.position.y = 31; head.castShadow = true; grp.add(head);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(10,1.0,8,32),
    new THREE.MeshBasicMaterial({color:0x63e6b8}));
  ring.rotation.x=-Math.PI/2; ring.position.y=6;
  ring.visible = Boolean(working); grp.add(ring);
  if (name){
    const c=document.createElement('canvas'); c.width=320; c.height=64;
    const g=c.getContext('2d'); g.font='600 26px system-ui'; g.textAlign='center';
    g.fillStyle='#e9f3ff'; g.fillText(name,160,42);
    const spr=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),transparent:true,depthWrite:false}));
    spr.position.set(0,46,0); spr.scale.set(76,15,1); grp.add(spr);
  }
  grp.position.set(x,y,z);
  grp.userData = {name: name || '', workerId, depId, home: {x, y, z}};
  people.add(grp);
  const entry = {grp, body, ring, phase: Math.random()*Math.PI*2, home:{x,z}};
  avatars.push(entry);
  avatarById.set(workerId, entry);
}

let built=false;
function build(snap){
  if (built) return;
  const deps = (snap.departments||[]).slice(0,20);
  if (!deps.length) return;
  built = true;
  const cols = Math.ceil(Math.sqrt(deps.length));
  const rows = Math.ceil(deps.length/cols);
  const gw = 300, gd = 320;

  deps.forEach((dep,i)=>{
    const cx = (i%cols - (cols-1)/2) * gw;
    const cz = (Math.floor(i/cols) - (rows-1)/2) * gd;
    const busy = dep.state==='çalışıyor';
    const accent = ACCENT[i % ACCENT.length];
    const wname = dep.name || dep.department_id;
    makeRoom(cx, cz, 240, 260, accent, busy, wname, `${(dep.workers||[]).length} kişi`, dep.department_id);
    const list = dep.workers||[];
    for (let k=0;k<Math.min(list.length,9);k++){
      const working = list[k].activity_verified === true;
      const px = cx - 74 + (k%3)*74;
      const pz = cz - 60 + Math.floor(k/3)*66;
      const raw = String(list[k].worker_id || list[k]);
      const rec = ROSTER[raw];
      const nm = list[k].name || (rec ? rec.name : raw.replace(/^mgr-/,'').slice(0,16));
      person(px, 10, pz, working?0x63e6b8:0x6f92cc, working, nm, dep.department_id, raw);
    }
  });
}

function hud(s){
  const t = s.totals||{};
  document.getElementById('stats').textContent =
    `departman ${(s.departments||[]).length} · işçi ${t.workers??0} · çalışan ${t.working??0}`+
    ` · tamam ${t.completed??'-'} · engel ${t.blocked??'-'}`;
}

function chat(list){
  const box=document.getElementById('chatbody'); if(!box) return;
  if(!list||!list.length){ box.textContent='henüz sohbet yok'; return; }
  box.innerHTML = list.slice(-14).reverse().map(m=>
    `<div class="m" onclick="speak(this.innerText)"><span class="who">${m.from||'?'}</span> `+
    `<span class="dept">· ${m.department||''}</span><br>${String(m.body||'').slice(0,150)}</div>`).join('');
}

function fillWho(deps){
  const who=document.getElementById('who'); if(!who||who.dataset.done) return;
  const o=[];
  for(const dep of deps||[]) for(const w of (dep.workers||[])){
    const raw=String(w.worker_id||w); const rec=ROSTER[raw];
    o.push(`<option data-dept="${dep.id||dep.department_id}" value="${raw}">${dep.name||dep.id} · ${rec?rec.name:raw}</option>`);
  }
  if(o.length){ who.innerHTML=o.join(''); who.dataset.done='1'; }
}

function speak(t){
  try{ if(!('speechSynthesis' in window))return;
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(String(t).slice(0,220));
    u.lang='tr-TR'; u.rate=1.02; speechSynthesis.speak(u);
  }catch(_){}
}

async function talk(){
  const who=document.getElementById('who'), msg=document.getElementById('msg'), reply=document.getElementById('reply');
  if(!who.value||!msg.value.trim()) return;
  const dep=who.options[who.selectedIndex].dataset.dept||'';
  try{
    const r=await fetch(`/api/talk?worker=${encodeURIComponent(who.value)}&dept=${encodeURIComponent(dep)}&msg=${encodeURIComponent(msg.value)}`);
    const d=await r.json();
    reply.textContent=d.reply||'(cevap yok)'; speak(d.reply||''); msg.value='';
  }catch(_){ reply.textContent='bağlantı hatası'; }
}

async function sync(){
  try{
    const s=await (await fetch('/api/agent-office',{cache:'no-store'})).json();
    build(s); hud(s); fillWho(s.departments);
    try{ chat(await (await fetch('/api/conversations',{cache:'no-store'})).json()); }catch(_){ chat(null); }
  }catch(e){
    const el=document.getElementById('err'); el.style.display='block';
    el.textContent='API bağlantısı yok: '+e.message;
  }
}

let yaw=Math.PI*0.22, pitch=0.78, dist=900, drag=false, lx=0, ly=0;
function place(){
  camera.position.set(Math.sin(yaw)*Math.cos(pitch)*dist, Math.sin(pitch)*dist, Math.cos(yaw)*Math.cos(pitch)*dist);
  camera.lookAt(0,30,0);
}
place();
addEventListener('pointerdown',e=>{drag=true;lx=e.clientX;ly=e.clientY;});
addEventListener('pointerup',()=>drag=false);
addEventListener('pointermove',e=>{
  if(!drag)return;
  yaw-=(e.clientX-lx)*0.005;
  pitch=Math.min(1.25,Math.max(0.32,pitch+(e.clientY-ly)*0.004));
  lx=e.clientX; ly=e.clientY; place();
});
addEventListener('wheel',e=>{dist=Math.min(2200,Math.max(320,dist+e.deltaY*0.8));place();},{passive:true});
addEventListener('resize',()=>{
  camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth,innerHeight);
});
document.addEventListener('keydown',e=>{ if(e.key==='Enter'&&e.target.id==='msg') talk(); });

sync(); setInterval(sync,5000);

// --- etkileşim: işçiye/odaya tıkla → kamera odaklan + kart ---
const ray = new THREE.Raycaster();
const ptr = new THREE.Vector2();
let focus = null;

function onClick(e){
  ptr.x = (e.clientX/innerWidth)*2-1;
  ptr.y = -(e.clientY/innerHeight)*2+1;
  ray.setFromCamera(ptr, camera);
  const hits = ray.intersectObjects([...people.children, ...rooms.children], true);
  if (!hits.length) return;
  let obj = hits[0].object;
  while (obj.parent && obj.parent !== people && obj.parent !== rooms) obj = obj.parent;
  const world = new THREE.Vector3();
  obj.getWorldPosition(world);
  focus = world.clone();
  const card = document.getElementById('reply');
  const name = obj.userData && obj.userData.name;
  if (card && name) card.textContent = 'Seçili: ' + name;
  if (card && !name) card.textContent = 'Oda odaklandı';
  yaw = Math.atan2(world.x, world.z);
  pitch = 0.62; dist = 520;
  place();
}

function placeAround(){
  if (!focus) return;
  camera.lookAt(focus.x, 30, focus.z);
}

addEventListener('click', onClick);

let t0=0;
(function loop(t){
  requestAnimationFrame(loop);
  const dt = t0 ? Math.min(0.05,(t-t0)/1000) : 0.016; t0 = t;
  for(const a of avatars){
    // nefes + küçük yürüyüş salınımı
    a.grp.position.y = 10 + Math.sin(t/520 + a.phase)*1.6;
    a.grp.position.x += Math.sin(t/2100 + a.phase)*dt*6;
    a.grp.position.z += Math.cos(t/2600 + a.phase)*dt*5;
    a.grp.rotation.y = Math.sin(t/900 + a.phase)*0.5;
  }
  rooms.children.forEach((child,i)=>{
    if (child.isSprite) child.material.opacity = 0.75 + Math.sin(t/1400 + i)*0.2;
  });
  placeAround();
  renderer.render(scene,camera);
})(0);
</script></body></html>
"""


def render_html() -> str:
    return HTML
