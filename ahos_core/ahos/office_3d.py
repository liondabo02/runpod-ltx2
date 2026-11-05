"""3B ofis — gerçek bir kat planı hissi: duvarlı odalar, masalar, sandalyeler,
bitkiler, tavan lambaları ve işçi figürleri.

Sunucu: from ahos.office_3d import render_html; html = render_html()
"""

from __future__ import annotations

HTML = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<title>AHOS Ofis Katı — 3B</title>
<style>
  html,body{margin:0;height:100%;background:#0b0f18;color:#dbe7ff;font:13px/1.5 system-ui;overflow:hidden}
  #hud{position:fixed;left:14px;top:12px;background:#101a2ce6;border:1px solid #22314e;border-radius:12px;padding:10px 14px}
  #hud b{color:#8fd3ff}
  #tip{position:fixed;right:14px;top:12px;background:#101a2ce6;border:1px solid #22314e;border-radius:12px;padding:10px 14px;color:#9fb0cc}
  #err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#33131b;border:1px solid #8d2b3d;padding:16px 20px;border-radius:12px;display:none}
</style></head>
<body>
<div id="hud">AHOS · <b>Ofis Katı (3B)</b><br><span id="stats">yükleniyor…</span></div>
<div id="tip">sürükle: döndür · tekerlek: zoom</div>
<div id="err"></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0f18);
scene.fog = new THREE.Fog(0x0b0f18, 900, 2200);

const camera = new THREE.PerspectiveCamera(46, innerWidth/innerHeight, 1, 4000);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

// --- ışık: yumuşak ortam + sıcak ana ışık ---
scene.add(new THREE.HemisphereLight(0xbcd4ff, 0x121820, 0.85));
const sun = new THREE.DirectionalLight(0xfff2dd, 1.15);
sun.position.set(320, 520, 260);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -700; sun.shadow.camera.right = 700;
sun.shadow.camera.top = 700; sun.shadow.camera.bottom = -700;
scene.add(sun);

// --- zemin: büyük parke + ızgara ---
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(2400, 2400),
  new THREE.MeshStandardMaterial({color:0x11161f, roughness:0.95, metalness:0.05})
);
ground.rotation.x = -Math.PI/2; ground.receiveShadow = true; scene.add(ground);

const PALETTE = [0x2f4f72,0x2c5d4f,0x4a3d6b,0x5c4a2f,0x3d5a63,0x6b3d4d,0x37506b,0x4d5c2f];

const rooms = new THREE.Group(); scene.add(rooms);
const people = new THREE.Group(); scene.add(people);

function label(text, x, y, z, color='#cfe3ff'){
  const c = document.createElement('canvas'); c.width = 512; c.height = 96;
  const ctx = c.getContext('2d');
  ctx.font = 'bold 38px system-ui'; ctx.textAlign='center';
  ctx.fillStyle = color; ctx.fillText(text, 256, 60);
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({
    map:new THREE.CanvasTexture(c), transparent:true, depthWrite:false
  }));
  spr.position.set(x, y, z); spr.scale.set(150, 28, 1);
  return spr;
}

function makeRoom(cx, cz, w, d, color, busy){
  const g = new THREE.Group();
  const h = 84, t = 6;

  const floor = new THREE.Mesh(
    new THREE.BoxGeometry(w, t, d),
    new THREE.MeshStandardMaterial({color: busy?0x1c2f28:0x151b26, roughness:0.9})
  );
  floor.position.set(0, t/2, 0); floor.receiveShadow = true; g.add(floor);

  const wallMat = new THREE.MeshStandardMaterial({
    color: busy ? 0x24473c : color, roughness:0.75, metalness:0.1
  });

  // dört duvar (kapı boşluğu ön tarafta)
  const specs = [
    [0, h/2, -d/2, w, h, t],           // arka
    [-w/2, h/2, 0, t, h, d],           // sol
    [w/2, h/2, 0, t, h, d],            // sağ
  ];
  for (const [x,y,z,ww,hh,dd] of specs){
    const wall = new THREE.Mesh(new THREE.BoxGeometry(ww, hh, dd), wallMat);
    wall.position.set(x,y,z); wall.castShadow = true; wall.receiveShadow = true; g.add(wall);
  }
  // ön duvar: iki parça (kapı boşluğu)
  const doorW = 52;
  const side = (w - doorW) / 2;
  for (const sx of [-1, 1]){
    const wall = new THREE.Mesh(new THREE.BoxGeometry(side, h, t), wallMat);
    wall.position.set(sx * (doorW/2 + side/2), h/2, d/2);
    wall.castShadow = true; wall.receiveShadow = true; g.add(wall);
  }

  // masa ızgarası
  const deskMat = new THREE.MeshStandardMaterial({color:0x35455e, roughness:0.6});
  const chairs = new THREE.MeshStandardMaterial({color:0x1d2736, roughness:0.8});
  const cols = Math.max(2, Math.floor((w - 40) / 62));
  const rows = Math.max(1, Math.floor((d - 46) / 58));
  for (let r = 0; r < rows; r++){
    for (let c = 0; c < cols; c++){
      const dx = -w/2 + 34 + c * 62;
      const dz = -d/2 + 40 + r * 58;
      const desk = new THREE.Mesh(new THREE.BoxGeometry(46, 4, 22), deskMat);
      desk.position.set(dx, 34, dz); desk.castShadow = true; g.add(desk);
      for (const lx of [-18, 18]){
        const leg = new THREE.Mesh(new THREE.BoxGeometry(3, 30, 3), deskMat);
        leg.position.set(dx + lx, 17, dz + 8); g.add(leg);
      }
      const seat = new THREE.Mesh(new THREE.BoxGeometry(20, 4, 20), chairs);
      seat.position.set(dx, 20, dz + 26); seat.castShadow = true; g.add(seat);
      const back = new THREE.Mesh(new THREE.BoxGeometry(20, 22, 3), chairs);
      back.position.set(dx, 31, dz + 35); g.add(back);
      const monitor = new THREE.Mesh(new THREE.BoxGeometry(22, 13, 2),
        new THREE.MeshStandardMaterial({color: busy?0x2b6f5c:0x22303f, emissive: busy?0x0f3a2e:0x000000}));
      monitor.position.set(dx, 45, dz - 6); g.add(monitor);
    }
  }

  // bitki
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(7, 5, 12, 10),
    new THREE.MeshStandardMaterial({color:0x4a3627}));
  pot.position.set(w/2 - 18, 6, d/2 - 18); g.add(pot);
  const leaf = new THREE.Mesh(new THREE.ConeGeometry(12, 26, 8),
    new THREE.MeshStandardMaterial({color:0x2f6b45}));
  leaf.position.set(w/2 - 18, 24, d/2 - 18); leaf.castShadow = true; g.add(leaf);

  // tavan lambası
  const lamp = new THREE.PointLight(0xfff0d0, busy ? 1.1 : 0.55, 220, 2);
  lamp.position.set(0, h - 12, 0); g.add(lamp);

  g.position.set(cx, 0, cz);
  rooms.add(g);
  rooms.add(label('', cx, h + 34, cz)); // rezerv
  return g;
}

function person(x, y, z, color, working){
  const grp = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(5.5, 12, 4, 10),
    new THREE.MeshStandardMaterial({color, roughness:0.6}));
  body.position.y = 18; body.castShadow = true; grp.add(body);
  const head = new THREE.Mesh(new THREE.SphereGeometry(5.2, 12, 10),
    new THREE.MeshStandardMaterial({color:0xf0c9a8, roughness:0.8}));
  head.position.y = 30; head.castShadow = true; grp.add(head);
  if (working){
    const ring = new THREE.Mesh(new THREE.TorusGeometry(9, 0.9, 6, 28),
      new THREE.MeshBasicMaterial({color:0x5ee6b8}));
    ring.rotation.x = -Math.PI/2; ring.position.y = 6; grp.add(ring);
  }
  grp.position.set(x, y, z);
  people.add(grp);
  return grp;
}

let built = false;

function build(snap){
  if (built) return;
  const deps = (snap.departments || []).slice(0, 20);
  if (!deps.length) return;
  built = true;

  const cols = Math.ceil(Math.sqrt(deps.length));
  const rows = Math.ceil(deps.length / cols);
  const gw = 235, gd = 250;

  deps.forEach((dep, i) => {
    const cx = (i % cols - (cols-1)/2) * gw;
    const cz = (Math.floor(i/cols) - (rows-1)/2) * gd;
    const busy = (dep.state === 'çalışıyor') || (dep.pending || 0) > 0;
    makeRoom(cx, cz, 190, 200, PALETTE[i % PALETTE.length], busy);
    rooms.add(label(`${dep.name || dep.id}`, cx, 120, cz - 110));

    const list = dep.workers || [];
    const n = Math.min(list.length, 9);
    for (let k = 0; k < n; k++){
      const working = busy && k < Math.min(dep.pending || 0, n);
      const px = cx - 58 + (k % 3) * 58;
      const pz = cz - 46 + Math.floor(k/3) * 52;
      person(px, 8, pz, working ? 0x6ee7c0 : 0x6b8fc9, working);
    }
  });
}

function hud(s){
  const t = s.totals || {};
  document.getElementById('stats').textContent =
    `departman ${(s.departments||[]).length} · işçi ${t.workers ?? 0} · çalışan ${t.working ?? 0}` +
    ` · tamam ${t.completed ?? '-'} · engel ${t.blocked ?? '-'}`;
}

async function sync(){
  try{
    const r = await fetch('/api/agent-office', {cache:'no-store'});
    const s = await r.json();
    build(s); hud(s);
  }catch(e){
    const el = document.getElementById('err');
    el.style.display='block'; el.textContent = 'API bağlantısı yok: ' + e.message;
  }
}

// kamera: eğik izometrik, sürükle-döndür
let yaw = Math.PI * 0.25, pitch = 0.92, dist = 720, drag = false, lx = 0, ly = 0;

function place(){
  const x = Math.sin(yaw) * Math.cos(pitch) * dist;
  const z = Math.cos(yaw) * Math.cos(pitch) * dist;
  const y = Math.sin(pitch) * dist;
  camera.position.set(x, y, z);
  camera.lookAt(0, 40, 0);
}
place();

addEventListener('pointerdown', e => {drag = true; lx = e.clientX; ly = e.clientY;});
addEventListener('pointerup', () => drag = false);
addEventListener('pointermove', e => {
  if (!drag) return;
  yaw -= (e.clientX - lx) * 0.006;
  pitch = Math.min(1.35, Math.max(0.35, pitch + (e.clientY - ly) * 0.004));
  lx = e.clientX; ly = e.clientY; place();
});
addEventListener('wheel', e => {
  dist = Math.min(1800, Math.max(320, dist + e.deltaY * 0.7)); place();
}, {passive:true});
addEventListener('resize', () => {
  camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

sync(); setInterval(sync, 5000);
(function loop(){ requestAnimationFrame(loop); renderer.render(scene, camera); })();
</script></body></html>
"""


def render_html() -> str:
    return HTML
