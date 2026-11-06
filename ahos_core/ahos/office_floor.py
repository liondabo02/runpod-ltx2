"""AHOS Ofis Katı v2 — bina düzeni + canlı simülasyon.

Agent Atrium / Ajan Ofisi / Munder Difflin'de olup bizde olmayan **bina yapısı**
burada uyarlanır:

- **Resepsiyon**: giriş, ön masa listesi (seni bekleyenler)
- **Ortak alan**: lounge, kahve barı, pinpon — boştaki botlar buraya gelir
- **CEO Ofisi**: duvarlarında gerçek sayılar (teslim, engel, çalışan)
- **Departman odaları**: genişlik işçi sayısına göre büyür, kapısı vardır
- **Yürüyüş**: bot önce oda kapısından girer, sonra masasına oturur
- **Pasif odalar söner** (tüm işçiler boştaysa)
- **3 tema** (Tab ile): Glass Studio / Sunset Loft / Neon Night
"""

FLOOR_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS Ofis Katı — bina simülasyonu</title>
<style>
  :root{--ink:#e9eefb;--dim:#8ea3c4;--line:#1f2d47}
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;overflow:hidden;background:#070d18;color:var(--ink);
       font-family:system-ui,"Segoe UI",Roboto,sans-serif}
  header{position:fixed;top:0;left:0;right:0;display:flex;gap:10px;align-items:center;padding:9px 14px;
         background:#070d18dd;backdrop-filter:blur(6px);border-bottom:1px solid var(--line);z-index:10;flex-wrap:wrap}
  h1{font-size:15px;margin:0 6px 0 0}
  .pill{border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12px;color:var(--dim)}
  .pill b{color:var(--ink)}
  canvas{display:block;width:100vw;height:100vh}
  #card{position:fixed;right:14px;bottom:14px;width:300px;background:#0d1729f2;border:1px solid var(--line);
        border-radius:14px;padding:12px;font-size:12.5px;display:none;z-index:12}
  #card h3{margin:0 0 6px;font-size:13px}
  #card .row{display:flex;justify-content:space-between;color:var(--dim);margin:3px 0}
  #card .row b{color:var(--ink)}
  #card button{margin-top:8px;width:100%;padding:6px;border-radius:8px;border:1px solid var(--line);
               background:#16233c;color:var(--ink);cursor:pointer}
  #front{position:fixed;left:14px;bottom:12px;max-width:420px;z-index:11;font-size:11.5px;color:var(--dim)}
  #front div{border-left:3px solid #ffc95e;background:#101b2ee6;border-radius:8px;padding:4px 8px;margin-top:4px}
  #front div.err{border-left-color:#ff6b6b}
</style>
</head>
<body>
<header>
  <h1>🏢 AHOS Ofis Katı</h1>
  <span class="pill">departman <b id="deps">–</b></span>
  <span class="pill">işçi <b id="workers">–</b></span>
  <span class="pill">çalışan <b id="running">–</b></span>
  <span class="pill" id="title">–</span>
  <span class="pill">tema: <b id="theme">Glass</b> (Tab)</span>
  <span class="pill"><a href="/" style="color:#7fa6ff;text-decoration:none">panele dön</a></span>
</header>
<canvas id="stage"></canvas>
<div id="front"></div>
<div id="card"><h3 id="cname">–</h3><div id="crows"></div>
  <button onclick="document.getElementById('card').style.display='none'">kapat</button></div>
<script>
const cv = document.getElementById('stage'), ctx = cv.getContext('2d');
let W = 1700, H = 1000, scale = 1;

const THEMES = [
  {name:'Glass',  floor:'#0b1424', tile:'#10203a', roomA:'#16233c', roomB:'#0f1828', wall:'#22314c', busy:'#2f6b52', ink:'#e9eefb'},
  {name:'Sunset', floor:'#1a1320', tile:'#2a1e2c', roomA:'#2c2030', roomB:'#1e1622', wall:'#45304a', busy:'#c07a3a', ink:'#ffe9d6'},
  {name:'Neon',   floor:'#080b18', tile:'#101a33', roomA:'#121a33', roomB:'#0b1226', wall:'#2d3a6b', busy:'#3ecf8e', ink:'#dff0ff'}
];
let theme = 0;

function resize(){
  cv.width = innerWidth * devicePixelRatio; cv.height = innerHeight * devicePixelRatio;
  scale = Math.min(cv.width / W, cv.height / H);
  ctx.setTransform(scale,0,0,scale,(cv.width-W*scale)/2,(cv.height-H*scale)/2);
}
addEventListener('resize', resize); resize();

let zones = [], rooms = [], agents = [], stats = {deps:0,workers:0,running:0,title:''}, attention = [];

const ROOM_H = 220, GAP = 30, MARGIN = 46, TOP = 250;

function layout(departments){
  zones = [
    {label:'🛎️ Resepsiyon', x: MARGIN, y: 84, w: 340, h: 130},
    {label:'🛋️ Ortak Alan · ☕ · 🏓', x: 396, y: 84, w: 560, h: 130},
    {label:'👔 CEO Ofisi', x: 976, y: 84, w: 420, h: 130}
  ];
  const perRow = 4;
  rooms = departments.map((dep, i) => {
    const col = i % perRow, row = Math.floor(i / perRow);
    const workers = dep.workers || [];
    const w = 250 + Math.min(8, Math.max(1, workers.length)) * 24;
    const x = MARGIN + col * (300 + GAP);
    const y = TOP + row * (ROOM_H + GAP + 16);
    const cols = Math.min(4, Math.max(1, workers.length));
    const desks = workers.map((w2, k) => ({
      x: x + 46 + (k % cols) * 66,
      y: y + 92 + Math.floor(k / cols) * 56
    }));
    return {id: dep.department_id, name: dep.name || dep.department_id, x, y, w, pending: dep.pending || 0, busyCount: dep.pending || 0,
            state: dep.state, busy: dep.state === 'çalışıyor', workers, desks,
            door: {x: x + 24, y: y + ROOM_H + 2},
            coffee: {x: x + w - 58, y: y + ROOM_H - 40},
            active: workers.some(w2 => w2.state === 'çalışıyor' || w2.state === 'sırada')};
  });
}

function sync(){
  const seen = new Set();
  rooms.forEach(room => {
    room.workers.forEach((w2, idx) => {
      seen.add(w2.worker_id);
      let a = agents.find(x => x.id === w2.worker_id);
      const desk = room.desks[idx % room.desks.length];
      if (!a){
        a = {id: w2.worker_id, name: w2.name || w2.worker_id, room, desk,
             x: room.door.x, y: room.door.y, tx: desk.x, ty: desk.y,
             phase:'door', state:'boşta', badge:'·', rate:0, runs:0, avg:0, seed:Math.random()*6.28};
        agents.push(a);
      }
      a.room = room; a.desk = desk;
      a.state = w2.state || 'boşta';
      // Departmanda bekleyen iş varsa işçiyi masada çalışıyor göster.
      if (room.pending && idx < room.pending) a.state = 'çalışıyor'; a.rate = w2.rate || 0;
      a.runs = w2.runs || 0; a.avg = w2.avg_seconds || 0;
      a.badge = a.state === 'çalışıyor' ? '⌨' : a.state === 'engellendi' ? '!' :
                a.state === 'sırada' ? '?' : (a.rate > 0 ? '✓' : '·');
      if (a.state === 'çalışıyor' || a.state === 'engellendi' || a.state === 'sırada'){
        a.target = 'desk';
      } else {
        a.target = 'commons';
        // Ortak alanda yığılma yerine kendi odasının kahve köşesine dağıl.
        const _c = room.coffee || {x: room.x + room.w - 50, y: room.y + 170};
        a.common = { x: _c.x - 34 + Math.random() * 68, y: _c.y + (Math.random() * 20 - 10) };
      }
    });
  });
  agents = agents.filter(a => seen.has(a.id));
}

// ortak alan hedefleri
function commonsPoint(){
  const z = zones[1];
  return {x: z.x + 60 + Math.random() * (z.w - 120), y: z.y + 60 + Math.random() * 50};
}

async function refresh(){
  try{
    const r = await fetch('/api/agent-office', {cache:'no-store'});
    const d = await r.json();
    const t = d.totals || {};
    stats = {deps: t.departments ?? 0, workers: t.workers ?? 0, running: t.running ?? 0,
             title: (d.attention && d.attention.title) || 'sakin',
             completed: t.completed ?? 0, blocked: t.blocked ?? 0};
    attention = (d.attention && d.attention.items) || [];
    document.getElementById('deps').textContent = stats.deps;
    document.getElementById('workers').textContent = stats.workers;
    document.getElementById('running').textContent = stats.running;
    document.getElementById('title').textContent = stats.title;
    const front = document.getElementById('front'); front.innerHTML = '';
    attention.slice(0,4).forEach(item => {
      const el = document.createElement('div');
      el.className = item.kind === 'hata' ? 'err' : '';
      el.textContent = item.badge + ' ' + (item.department || '') + ' · ' + (item.objective || item.mission_id);
      front.appendChild(el);
    });
    layout(d.departments || []);
    sync();
  }catch(e){}
}
// Establish zones before the first animation frame.
layout([]);
refresh(); setInterval(refresh, 5000);

function roundRect(x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}

function step(dt){
  agents.forEach(a => {
    if (!a.room) return;
    let tx, ty;
    if (a.target === 'desk'){ tx = a.desk.x; ty = a.desk.y; }
    else {
      // Boştaki bot kendi odasının kahve köşesine gider (ortak alanda yığılma yok).
      if (!a.common || a.commonRoom !== a.room.id) {
        const c = a.room.coffee;
        a.common = { x: c.x - 26 + Math.random() * 52, y: c.y + (Math.random() * 16 - 8) };
        a.commonRoom = a.room.id;
      }
      tx = a.common.x; ty = a.common.y;
    }
    if (a.target === 'desk' && a.phase === 'door'){
      tx = a.room.door.x; ty = a.room.door.y;
      if (Math.hypot(tx - a.x, ty - a.y) < 6) a.phase = 'desk';
    }
    if (a.target === 'commons') a.phase = 'door';
    const dx = tx - a.x, dy = ty - a.y, d = Math.hypot(dx, dy);
    if (d > 4){ const s = 58; a.x += dx/d*s*dt; a.y += dy/d*s*dt; a.walking = true; }
    else { a.walking = false; if (a.target === 'commons' && Math.random() < 0.006) a.common = commonsPoint(); }
    a.seed += dt * (a.state === 'çalışıyor' ? 7 : 2);
  });
}

function drawZones(){
  const th = THEMES[theme];
  zones.forEach((z, i) => {
    ctx.fillStyle = i === 2 ? '#1b2033' : (i === 1 ? '#12233a' : '#132038');
    roundRect(z.x, z.y, z.w, z.h, 16); ctx.fill();
    ctx.strokeStyle = th.wall; ctx.lineWidth = 1; roundRect(z.x, z.y, z.w, z.h, 16); ctx.stroke();
    ctx.fillStyle = '#9db0d0'; ctx.font = 'bold 13px system-ui';
    ctx.fillText(z.label, z.x + 14, z.y + 24);
  });
  // resepsiyon: banko
  const rec = zones[0];
  ctx.fillStyle = '#1d2b46'; roundRect(rec.x + 20, rec.y + 58, rec.w - 40, 16, 6); ctx.fill();
  ctx.font = '20px system-ui'; ctx.fillText('🛎️', rec.x + rec.w/2 - 10, rec.y + 54);
  // ortak alan: bar + masa + pinpon
  const c = zones[1];
  ctx.font = '22px system-ui';
  ctx.fillText('☕', c.x + 30, c.y + 88);
  ctx.fillText('🍵', c.x + 70, c.y + 88);
  ctx.fillText('🏓', c.x + c.w - 70, c.y + 88);
  ctx.fillStyle = '#1d2b46'; roundRect(c.x + 110, c.y + 66, 120, 28, 8); ctx.fill();
  // CEO ofisi: duvar ekranları (gerçek sayılar)
  const hq = zones[2];
  ctx.fillStyle = '#0d1729'; roundRect(hq.x + 20, hq.y + 44, 150, 58, 8); ctx.fill();
  ctx.fillStyle = '#8ea3c4'; ctx.font = '10.5px system-ui';
  ctx.fillText('kuyruk tamam', hq.x + 30, hq.y + 60);
  ctx.fillStyle = '#3ecf8e'; ctx.font = 'bold 20px system-ui';
  ctx.fillText(String(stats.completed ?? 0), hq.x + 30, hq.y + 84);
  ctx.fillStyle = '#ff6b6b'; ctx.fillText(String(stats.blocked ?? 0), hq.x + 96, hq.y + 84);
  ctx.fillStyle = '#8ea3c4'; ctx.font = '10.5px system-ui';
  ctx.fillText('engel', hq.x + 96, hq.y + 60);
  ctx.font = '30px system-ui'; ctx.fillText('👔', hq.x + 210, hq.y + 90);
}

function drawRooms(){
  const th = THEMES[theme];
  rooms.forEach(room => {
    const dim = !room.active;
    ctx.save(); ctx.globalAlpha = dim ? 0.5 : 1;
    const g = ctx.createLinearGradient(room.x, room.y, room.x, room.y + ROOM_H);
    g.addColorStop(0, room.busy ? th.busy + '33' : th.roomA);
    g.addColorStop(1, th.roomB);
    ctx.fillStyle = g; roundRect(room.x, room.y, room.w, ROOM_H, 18); ctx.fill();
    ctx.strokeStyle = room.busy ? th.busy : th.wall; ctx.lineWidth = room.busy ? 2 : 1;
    roundRect(room.x, room.y, room.w, ROOM_H, 18); ctx.stroke();
    if (room.busy){ ctx.shadowColor = th.busy; ctx.shadowBlur = 16;
      roundRect(room.x, room.y, room.w, ROOM_H, 18); ctx.stroke(); ctx.shadowBlur = 0; }
    ctx.fillStyle = th.ink; ctx.font = 'bold 13px system-ui';
    ctx.fillText(room.name, room.x + 16, room.y + 24);
    ctx.fillStyle = room.busy ? th.busy : '#7d8fb0'; ctx.font = '11px system-ui';
    ctx.fillText(room.state, room.x + room.w - 76, room.y + 24);
    // kapı
    ctx.fillStyle = room.busy ? th.busy : th.wall;
    roundRect(room.door.x - 12, room.y + ROOM_H - 6, 24, 8, 3); ctx.fill();
    // masalar + monitörler
    room.desks.forEach((d, idx) => {
      const w2 = room.workers[idx] || {};
      ctx.fillStyle = '#1c2a44'; roundRect(d.x - 20, d.y + 10, 40, 12, 4); ctx.fill();
      ctx.fillStyle = w2.state === 'engellendi' ? '#6b2f2f' : w2.state === 'çalışıyor' ? '#1d4a3a' : '#22314c';
      roundRect(d.x - 15, d.y - 14, 30, 20, 4); ctx.fill();
    });
    ctx.font = '17px system-ui'; ctx.fillText('☕', room.coffee.x - 8, room.coffee.y + 6);
    ctx.restore();
  });
}

function drawAgent(a){
  const bob = a.walking ? Math.sin(a.seed * 7) * 2 : Math.sin(a.seed) * (a.state === 'çalışıyor' ? 2 : 1);
  const x = a.x, y = a.y + bob;
  ctx.fillStyle = '#00000055'; ctx.beginPath(); ctx.ellipse(a.x, a.y + 15, 12, 5, 0, 0, 6.28); ctx.fill();
  const col = a.state === 'çalışıyor' ? '#2f7d5f' : a.state === 'engellendi' ? '#7d3b3b'
            : a.state === 'sırada' ? '#7d6a2f' : '#394a68';
  ctx.fillStyle = col; roundRect(x - 10, y - 14, 20, 21, 7); ctx.fill();
  ctx.strokeStyle = '#0b1220'; ctx.lineWidth = 1.4; roundRect(x - 10, y - 14, 20, 21, 7); ctx.stroke();
  ctx.fillStyle = '#e9eefb'; ctx.beginPath(); ctx.arc(x, y - 21, 7, 0, 6.28); ctx.fill();
  ctx.fillStyle = '#0b1220';
  ctx.beginPath(); ctx.arc(x - 2.5, y - 22, 1.2, 0, 6.28); ctx.arc(x + 2.5, y - 22, 1.2, 0, 6.28); ctx.fill();
  ctx.beginPath(); ctx.arc(x + 12, y - 27, 8, 0, 6.28); ctx.fill();
  ctx.fillStyle = a.state === 'çalışıyor' ? '#3ecf8e' : a.state === 'engellendi' ? '#ff6b6b'
            : a.state === 'sırada' ? '#ffc95e' : '#8ea3c4';
  ctx.font = '11px system-ui'; ctx.textAlign = 'center';
  ctx.fillText(a.badge, x + 12, y - 23);
  if (a.state === 'boşta') { ctx.textAlign = 'left'; return; }
  ctx.fillStyle = '#a8b8d6'; ctx.font = '9.5px system-ui';
  ctx.fillText(a.name.length > 13 ? a.name.slice(0,12) + '…' : a.name, x, a.y + 28);
  ctx.textAlign = 'left';
}

function draw(){
  const th = THEMES[theme];
  ctx.fillStyle = th.floor; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = th.tile; ctx.lineWidth = 1;
  for (let x = 0; x < W; x += 44){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }
  for (let y = 0; y < H; y += 44){ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }
  drawZones(); drawRooms();
  agents.slice().sort((p,q) => p.y - q.y).forEach(drawAgent);
}

let last = performance.now();
function loop(now){
  const dt = Math.min(0.05, (now - last)/1000); last = now;
  step(dt); draw(); requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

addEventListener('keydown', e => {
  if (e.key === 'Tab'){ theme = (theme + 1) % THEMES.length;
    document.getElementById('theme').textContent = THEMES[theme].name; e.preventDefault(); }
});

cv.addEventListener('click', ev => {
  const rect = cv.getBoundingClientRect();
  const px = (ev.clientX - rect.left - (cv.width - W*scale)/2/devicePixelRatio) / (scale/devicePixelRatio);
  const py = (ev.clientY - rect.top - (cv.height - H*scale)/2/devicePixelRatio) / (scale/devicePixelRatio);
  let hit = null, best = 26;
  agents.forEach(a => { const d = Math.hypot(a.x - px, a.y - py); if (d < best){ best = d; hit = a; } });
  const card = document.getElementById('card');
  if (!hit){ card.style.display = 'none'; return; }
  document.getElementById('cname').textContent = hit.name;
  document.getElementById('crows').innerHTML =
    '<div class="row"><span>departman</span><b>' + (hit.room ? hit.room.name : '-') + '</b></div>' +
    '<div class="row"><span>durum</span><b>' + hit.state + ' ' + hit.badge + '</b></div>' +
    '<div class="row"><span>başarı</span><b>%' + Math.round(hit.rate*100) + '</b></div>' +
    '<div class="row"><span>koşu</span><b>' + hit.runs + '</b></div>' +
    '<div class="row"><span>ort. süre</span><b>' + (hit.avg ? hit.avg + ' sn' : '–') + '</b></div>';
  card.style.display = 'block';
});
</script>
</body>
</html>
"""
