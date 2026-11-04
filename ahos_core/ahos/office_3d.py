"""3B ofis katı — Three.js tek dosya, mevcut /api/agent-office verisiyle beslenir.

Kullanım (sunucu tarafı):
    from ahos.office_3d import render_html
    html = render_html()          # /ofis3d rotasında döndürülür
"""

from __future__ import annotations

HTML = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<title>AHOS Ofis Katı — 3B</title>
<style>
  html,body{margin:0;height:100%;background:#070b14;color:#cfe0ff;font:13px system-ui;overflow:hidden}
  #hud{position:fixed;left:12px;top:10px;background:#0d1424cc;border:1px solid #1e2c47;border-radius:10px;padding:8px 12px;line-height:1.6}
  #hud b{color:#8fd3ff}
  #tip{position:fixed;right:12px;top:10px;background:#0d1424cc;border:1px solid #1e2c47;border-radius:10px;padding:8px 12px}
  #err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#2a1017;border:1px solid #7a2233;padding:14px 18px;border-radius:10px;display:none}
</style></head>
<body>
<div id="hud">AHOS Ofis Katı · <b>3B</b><br><span id="stats">veri bekleniyor…</span></div>
<div id="tip">fare: döndür · tekerlek: yakınlaş</div>
<div id="err"></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070b14);
scene.fog = new THREE.Fog(0x070b14, 260, 900);

const camera = new THREE.PerspectiveCamera(50, innerWidth/innerHeight, 1, 3000);
camera.position.set(0, 420, 520);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

scene.add(new THREE.HemisphereLight(0xa9c7ff, 0x0a1020, 1.0));
const key = new THREE.DirectionalLight(0xffffff, 1.1); key.position.set(180, 420, 220); scene.add(key);

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(1400, 1400),
  new THREE.MeshStandardMaterial({color:0x0b1322, roughness:0.95})
);
floor.rotation.x = -Math.PI/2; scene.add(floor);
const grid = new THREE.GridHelper(1400, 40, 0x1b2a45, 0x111d31); scene.add(grid);

const rooms = new THREE.Group(); scene.add(rooms);
const people = new THREE.Group(); scene.add(people);
const labels = [];

function label(text, x, y, z, color='#8fd3ff'){
  const c = document.createElement('canvas'); const ctx = c.getContext('2d');
  c.width = 512; c.height = 96;
  ctx.font = 'bold 40px system-ui'; ctx.fillStyle = color; ctx.textAlign='center';
  ctx.fillText(text, 256, 62);
  const tex = new THREE.CanvasTexture(c);
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({map:tex, transparent:true, depthWrite:false}));
  spr.position.set(x, y, z); spr.scale.set(96, 18, 1);
  labels.push(spr); return spr;
}

let built = false;

function build(snapshot){
  if (built) return;
  const deps = (snapshot.departments || []).slice(0, 20);
  if (!deps.length) return;
  built = true;

  const cols = Math.ceil(Math.sqrt(deps.length));
  const gap = 190;
  const w = 150, h = 34 + 10, d = 120;

  deps.forEach((dep, i) => {
    const cx = (i % cols - (cols-1)/2) * gap;
    const cz = (Math.floor(i/cols) - (Math.ceil(deps.length/cols)-1)/2) * gap;

    const busy = (dep.state === 'çalışıyor') || (dep.pending > 0);
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(w, h, d),
      new THREE.MeshStandardMaterial({
        color: busy ? 0x143b2f : 0x141c2e,
        emissive: busy ? 0x0f3a2a : 0x000000,
        roughness: 0.8
      })
    );
    box.position.set(cx, h/2, cz); rooms.add(box);

    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(box.geometry),
      new THREE.LineBasicMaterial({color: busy ? 0x35d39a : 0x2a3d5c})
    );
    edge.position.copy(box.position); rooms.add(edge);

    rooms.add(label(`${dep.name || dep.id} · ${dep.workers?.length || 0}`, cx, h + 26, cz));

    const list = dep.workers || [];
    const n = Math.min(list.length, 8);
    for (let k = 0; k < n; k++){
      const working = busy && k < (dep.pending || 0);
      const px = cx - w/2 + 22 + (k % 4) * 34;
      const pz = cz - d/2 + 26 + Math.floor(k/4) * 34;
      const body = new THREE.Mesh(
        new THREE.CapsuleGeometry(6, 12, 4, 8),
        new THREE.MeshStandardMaterial({color: working ? 0x63e6be : 0x5b7fb5, emissive: working ? 0x123f33 : 0x000000})
      );
      body.position.set(px, h + 12, pz);
      people.add(body);
      if (working){
        const ring = new THREE.Mesh(
          new THREE.TorusGeometry(11, 1.1, 6, 24),
          new THREE.MeshBasicMaterial({color:0x63e6be})
        );
        ring.rotation.x = -Math.PI/2; ring.position.set(px, h + 1.5, pz); people.add(ring);
      }
    }
  });
}

function hud(s){
  const total = (s.totals && s.totals.workers) || 0;
  const busy = (s.totals && s.totals.working) || 0;
  document.getElementById('stats').textContent =
    `departman ${s.departments?.length || 0} · işçi ${total} · çalışan ${busy}` +
    ` · tamam ${s.totals?.completed ?? '-'} · engel ${s.totals?.blocked ?? '-'}`;
}

async function sync(){
  try{
    const r = await fetch('/api/agent-office', {cache:'no-store'});
    const s = await r.json();
    build(s); hud(s);
  }catch(e){
    const el = document.getElementById('err');
    el.style.display='block';
    el.textContent = 'API bağlantısı yok: ' + e.message;
  }
}

// basit orbit
let drag=false, px=0, py=0;
renderer.domElement.addEventListener('pointerdown', e=>{drag=true;px=e.clientX;py=e.clientY;});
addEventListener('pointerup', ()=>drag=false);
addEventListener('pointermove', e=>{
  if(!drag) return;
  const dx=(e.clientX-px)/innerWidth, dy=(e.clientY-py)/innerHeight;
  px=e.clientX; py=e.clientY;
  const r = Math.hypot(camera.position.x, camera.position.z);
  let a = Math.atan2(camera.position.z, camera.position.x) + dx*2.2;
  let y = THREE.MathUtils.clamp(camera.position.y + dy*260, 120, 900);
  camera.position.set(Math.cos(a)*r, y, Math.sin(a)*r);
  camera.lookAt(0, 0, 0);
});
addEventListener('wheel', e=>{
  const r = THREE.MathUtils.clamp(Math.hypot(camera.position.x, camera.position.z) + e.deltaY*0.6, 220, 1200);
  const a = Math.atan2(camera.position.z, camera.position.x);
  camera.position.set(Math.cos(a)*r, camera.position.y, Math.sin(a)*r);
  camera.lookAt(0,0,0);
}, {passive:true});

addEventListener('resize', ()=>{
  camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

sync(); setInterval(sync, 5000);
(function loop(){ requestAnimationFrame(loop); renderer.render(scene, camera); })();
</script></body></html>
"""


def render_html() -> str:
    return HTML
